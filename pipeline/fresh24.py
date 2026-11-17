"""Fresh remote roles from timestamped feeds, then the normal filter.

Instead of sweeping a fixed list of company boards, this pulls the firehose of
new remote postings and keeps only what was published inside the window. Recency
is the point. A role posted today has had almost no applicants.

    python fresh24.py                 last 24 hours
    python fresh24.py --hours 48
    python fresh24.py --ashby         also poll the 211 Ashby boards
"""
import argparse
import html
import json
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

from job_sweep import eliminate, family_of, score

HERE = Path(__file__).parent
OUT = HERE / "fresh24.md"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0"}

# Firehose feeds have weak location fields. These catch what job_sweep's
# eliminate() was not built to see.
US_BASED = re.compile(
    r"\(u\.?s\.? based|u\.?s\.? only|united states only|must be based in the (us|united states)|"
    r"remote \(us|us remote|americas only|canada only|philippines|india only|latam only|"
    r"must reside in the (us|united states)", re.I)
SALES = re.compile(
    r"\b(account executive|sales development|business development|bdr|sdr|"
    r"account manager|sales manager|account director|sales representative)\b", re.I)
LEGAL_FIN = re.compile(
    r"\b(counsel|lawyer|attorney|paralegal|finance business partner|"
    r"financial controller|auditor|tax manager)\b", re.I)
ONSITE_TELL = re.compile(
    r"\b(on-?site only|fully on-?site|in-?office|hybrid|"
    r"days? (a|per) week in the office|vor ort|im b[üu]ro)\b", re.I)
REMOTE_EVIDENCE = re.compile(
    r"\b(remote|homeoffice|home office|home-office|telearbeit|"
    r"work from home|ortsunabh[äa]ngig|deutschlandweit)\b", re.I)


def pre_kill(j):
    blob = f"{j['title']} {j['location']}"
    if US_BASED.search(blob):
        return "us_based"
    if SALES.search(j["title"]):
        return "sales"
    if LEGAL_FIN.search(j["title"]):
        return "legal_finance"
    return None


def post_kill(j):
    # arbeitnow's remote flag is optimistic. If it names a German city and the
    # body never says remote, treat it as on-site until proven otherwise.
    if j["source"] == "arbeitnow" and re.search(
            r"germany|deutschland|berlin|m[üu]nchen|munich|hamburg|frankfurt|"
            r"stuttgart|k[öo]ln|cologne|d[üu]sseldorf|dresden|leipzig|erfurt|"
            r"heidelberg|karlsruhe|n[üu]rnberg", j["location"], re.I):
        if not REMOTE_EVIDENCE.search(j["desc"]):
            return "no_remote_evidence"
    return None



def strip_html(s):
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s or "", flags=re.S | re.I)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


def parse_dt(value):
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except Exception:
            return None
    s = str(value).strip()
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        try:
            dt = parsedate_to_datetime(s)
        except Exception:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def job(title, company, loc, desc, url, src, posted, salary="", tags=None, remote=True):
    return {
        "title": (title or "").strip(),
        "company": (company or "").strip(),
        "location": (loc or "").strip(),
        "desc": strip_html(desc)[:4000],
        "url": (url or "").strip(),
        "source": src,
        "posted": posted,
        "salary": salary or "",
        "tags": tags or [],
        "remote_flag": remote,
    }


def src_arbeitnow():
    d = requests.get("https://www.arbeitnow.com/api/job-board-api", headers=H, timeout=40).json()
    out = []
    for j in d.get("data", []):
        out.append(job(j.get("title"), j.get("company_name"), j.get("location"),
                       j.get("description"), j.get("url"), "arbeitnow",
                       parse_dt(j.get("created_at")), tags=j.get("tags") or [],
                       remote=bool(j.get("remote"))))
    return out


def src_remotive():
    d = requests.get("https://remotive.com/api/remote-jobs?limit=200", headers=H, timeout=40).json()
    out = []
    for j in d.get("jobs", []):
        out.append(job(j.get("title"), j.get("company_name"), j.get("candidate_required_location"),
                       j.get("description"), j.get("url"), "remotive",
                       parse_dt(j.get("publication_date")), salary=j.get("salary") or "",
                       tags=j.get("tags") or []))
    return out


def src_remoteok():
    d = requests.get("https://remoteok.com/api", headers=H, timeout=40).json()
    out = []
    for j in d:
        if not isinstance(j, dict) or "position" not in j:
            continue
        salary = ""
        if j.get("salary_min"):
            salary = f"{j.get('salary_min')}-{j.get('salary_max')} USD"
        out.append(job(j.get("position"), j.get("company"), j.get("location"),
                       j.get("description"), j.get("url"), "remoteok",
                       parse_dt(j.get("date") or j.get("epoch")), salary=salary,
                       tags=j.get("tags") or []))
    return out


def src_jobicy():
    d = requests.get("https://jobicy.com/api/v2/remote-jobs?count=100", headers=H, timeout=40).json()
    out = []
    for j in d.get("jobs", []):
        out.append(job(j.get("jobTitle"), j.get("companyName"),
                       ", ".join(j.get("jobGeo") or []) if isinstance(j.get("jobGeo"), list) else j.get("jobGeo"),
                       j.get("jobDescription") or j.get("jobExcerpt"), j.get("url"), "jobicy",
                       parse_dt(j.get("pubDate")), tags=j.get("jobIndustry") or []))
    return out


def src_himalayas():
    d = requests.get("https://himalayas.app/jobs/api?limit=100", headers=H, timeout=40).json()
    out = []
    for j in d.get("jobs", []):
        locs = j.get("locationRestrictions") or []
        loc = ", ".join(locs) if isinstance(locs, list) else str(locs)
        salary = ""
        if j.get("minSalary"):
            salary = f"{j.get('minSalary')}-{j.get('maxSalary')} {j.get('currency') or ''}".strip()
        out.append(job(j.get("title"), j.get("companyName"), loc,
                       j.get("description") or j.get("excerpt"),
                       j.get("applicationLink") or j.get("guid"), "himalayas",
                       parse_dt(j.get("pubDate")), salary=salary,
                       tags=j.get("categories") or []))
    return out


def src_wwr():
    out = []
    for feed in ("https://weworkremotely.com/remote-jobs.rss",
                 "https://weworkremotely.com/categories/remote-customer-support-jobs.rss"):
        try:
            r = requests.get(feed, headers=H, timeout=30)
            root = ET.fromstring(r.content)
        except Exception:
            continue
        for item in root.iter("item"):
            raw_title = (item.findtext("title") or "").strip()
            company, _, role = raw_title.partition(": ")
            if not role:
                company, role = "", raw_title
            region = (item.findtext("region") or "").strip()
            out.append(job(role, company, region or "Remote",
                           item.findtext("description"), item.findtext("link"), "wwr",
                           parse_dt(item.findtext("pubDate"))))
    return out


def src_ashby():
    try:
        from uk_remote_scan import load_slugs
    except Exception:
        return []
    slugs = load_slugs()

    def one(slug):
        try:
            r = requests.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}",
                             headers=H, timeout=20)
            if r.status_code != 200:
                return []
            return r.json().get("jobs", [])
        except Exception:
            return []

    out = []
    with ThreadPoolExecutor(max_workers=16) as ex:
        for jobs in ex.map(one, slugs):
            for j in jobs:
                out.append(job(j.get("title"), j.get("companyName") or "",
                               j.get("location"), j.get("descriptionHtml") or j.get("descriptionPlain"),
                               j.get("jobUrl"), "ashby", parse_dt(j.get("publishedAt")),
                               remote=bool(j.get("isRemote"))))
    return out


SOURCES = {
    "arbeitnow": src_arbeitnow,
    "remotive": src_remotive,
    "remoteok": src_remoteok,
    "jobicy": src_jobicy,
    "himalayas": src_himalayas,
    "wwr": src_wwr,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=24)
    ap.add_argument("--ashby", action="store_true", help="also poll the 211 Ashby boards")
    args = ap.parse_args()

    cutoff = datetime.now(timezone.utc) - timedelta(hours=args.hours)
    raw, by_src, failures = [], {}, []

    for name, fn in SOURCES.items():
        try:
            rows = fn()
            by_src[name] = len(rows)
            raw.extend(rows)
        except Exception as exc:
            failures.append((name, repr(exc)[:120]))

    if args.ashby:
        rows = src_ashby()
        by_src["ashby"] = len(rows)
        raw.extend(rows)

    fresh = [j for j in raw if j["posted"] and j["posted"] >= cutoff and j["title"] and j["url"]]

    seen, uniq = set(), []
    for j in fresh:
        key = re.sub(r"[?#].*$", "", j["url"]).rstrip("/").lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(j)

    kept, killed = [], []
    for j in uniq:
        reason = pre_kill(j) or eliminate(j) or post_kill(j)
        if reason:
            j["kill_reason"] = reason
            killed.append(j)
        else:
            j["family"] = family_of(j["title"], j["desc"])
            j["score"] = score(j)
            kept.append(j)
    kept.sort(key=lambda j: -j["score"])

    from collections import Counter
    kc = Counter(j["kill_reason"] for j in killed)

    print(f"window: last {args.hours}h (since {cutoff:%Y-%m-%d %H:%M} UTC)")
    print("raw by source:", by_src)
    for name, err in failures:
        print(f"  FAILED {name}: {err}")
    print(f"raw {len(raw)} | in window {len(fresh)} | unique {len(uniq)} | "
          f"survived {len(kept)} | killed {len(killed)}")
    print("kill breakdown:", dict(kc))
    print()
    for j in kept[:25]:
        print(f"[{j['score']:>2}] {j['posted']:%d %b %H:%M} | {j['title'][:56]:56} | {j['location'][:26]}")
        print(f"     {j['url']}")

    lines = [f"# FRESH REMOTE - last {args.hours}h - {datetime.now():%Y-%m-%d %H:%M}", "",
             f"raw {len(raw)} | in window {len(fresh)} | unique {len(uniq)} | "
             f"survived {len(kept)} | killed {len(killed)}", ""]
    if kc:
        lines.append("killed: " + ", ".join(f"{k} {v}" for k, v in kc.most_common()))
        lines.append("")
    cur = None
    for j in kept:
        if j["family"] != cur:
            cur = j["family"]
            lines.append(f"\n## {cur.upper()}\n")
        comp = f" @ {j['company']}" if j["company"] else ""
        lines.append(f"### [ ] {j['title']}{comp}  (score {j['score']})")
        lines.append(f"- loc: {j['location']}")
        lines.append(f"- posted: {j['posted']:%Y-%m-%d %H:%M} UTC")
        lines.append(f"- src: {j['source']}")
        lines.append(f"- url: {j['url']}")
        lines.append("")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwrote {OUT}")

    payload = [{
        "title": j["title"],
        "company": j["company"],
        "location": j["location"],
        "salary": j["salary"],
        "url": j["url"],
        "source": j["source"],
        "posted": j["posted"].isoformat() if j["posted"] else None,
        "score": j["score"],
        "family": j["family"],
        "tags": j["tags"],
        "remote_flag": j["remote_flag"],
    } for j in kept]
    out_json = HERE / "fresh24.json"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {out_json} ({len(payload)} roles)")


if __name__ == "__main__":
    main()
