#!/usr/bin/env python3
"""
poll_jobs.py - config-driven, low-latency remote-job discovery poller.

Polls free job APIs + per-company ATS boards, dedupes against prior runs, filters by the
user's config, and appends new matches to state/new_matches.csv.

- Standard library only.  Run:  python3 poll_jobs.py
- Reads config.json (skill root, or scripts/). Copy assets/config.example.json to start.
- No region is hardcoded: with acceptable_locations empty, NO location filter is applied.
- For minutes-level freshness, schedule every ~10-15 min and populate the ATS watchlist.

Honour source terms: RemoteOK requires attribution + a direct link back; Remotive is
rate-limited (a few calls/day); never use this for LinkedIn auto-apply.
"""
import csv, json, os, sys, time, urllib.request, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
STATE = os.path.join(ROOT, "state")
os.makedirs(STATE, exist_ok=True)
SEEN_PATH = os.path.join(STATE, "seen_ids.json")
OUT_CSV = os.path.join(STATE, "new_matches.csv")

UA = "remote-job-hunt/1.0 (personal job search)"
TIMEOUT = 20

DEFAULT_CFG = {
    "role_keywords": ["data analyst", "bi analyst", "business intelligence", "analytics engineer",
                      "data scientist", "business analyst", "reporting analyst"],
    "exclude_titles": ["senior", "sr.", "staff", "principal", "lead ", "manager",
                       "head of", "director", "vp ", "architect"],
    "acceptable_locations": [],   # empty => NO region restriction
    "block_locations": [],        # user-specified places they cannot work
    "phone_block": ["call center", "call centre", "outbound call", "cold call", "phone sales"],
    "adzuna_country": "gb",
    "use": {"arbeitnow": True, "remoteok": True, "remotive": True},
    "greenhouse_boards": [], "lever_boards": [], "ashby_boards": [],
}


def load_cfg():
    for p in (os.path.join(ROOT, "config.json"), os.path.join(HERE, "config.json")):
        if os.path.exists(p):
            with open(p) as f:
                user = json.load(f)
            cfg = dict(DEFAULT_CFG); cfg.update({k: v for k, v in user.items() if not k.startswith("_")})
            return cfg
    return dict(DEFAULT_CFG)


def get(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read().decode("utf-8", "replace")


def getjson(url, headers=None):
    return json.loads(get(url, headers))


def warn(src, e):
    msg = str(e)
    # WinError 10054 = connection reset — Greenhouse rate-limiting, transient
    level = "~" if "10054" in msg or "10053" in msg else "!"
    print("  %s %-16s skipped: %s" % (level, src, msg), file=sys.stderr)


def rec(source, jid, company, title, url, location, remote_only=False):
    return {"id": "%s:%s" % (source, jid), "source": source,
            "company": (company or "").strip(), "title": (title or "").strip(),
            "url": (url or "").strip(), "location": str(location or "").strip(),
            "remote_only": remote_only}


# ------------------------- source fetchers ------------------------
def from_arbeitnow():
    out = []
    for it in getjson("https://www.arbeitnow.com/api/job-board-api").get("data", []):
        loc = it.get("location", "")
        if it.get("remote"):
            loc = ("remote " + str(loc)).strip()
        out.append(rec("arbeitnow", it.get("slug") or it.get("url"),
                       it.get("company_name"), it.get("title"), it.get("url"), loc))
    return out


def from_remoteok():
    out = []
    for it in getjson("https://remoteok.com/api"):
        if not isinstance(it, dict) or "id" not in it:
            continue
        out.append(rec("remoteok", it.get("id"), it.get("company"),
                       it.get("position") or it.get("title"), it.get("url"),
                       it.get("location") or "remote", remote_only=True))
    return out


def from_remotive():
    out = []
    for it in getjson("https://remotive.com/api/remote-jobs?category=data").get("jobs", []):
        out.append(rec("remotive", it.get("id"), it.get("company_name"),
                       it.get("title"), it.get("url"),
                       it.get("candidate_required_location") or "remote", remote_only=True))
    return out


def from_adzuna(country):
    out = []
    app_id, app_key = os.environ.get("ADZUNA_APP_ID", ""), os.environ.get("ADZUNA_APP_KEY", "")
    if not (app_id and app_key):
        return out
    for what in ("data analyst", "business intelligence analyst", "analytics"):
        url = ("https://api.adzuna.com/v1/api/jobs/%s/search/1?app_id=%s&app_key=%s"
               "&results_per_page=50&what=%s&max_days_old=2&sort_by=date"
               "&content-type=application/json"
               % (country, app_id, app_key, urllib.parse.quote(what)))
        for it in getjson(url).get("results", []):
            out.append(rec("adzuna", it.get("id"), (it.get("company") or {}).get("display_name"),
                           it.get("title"), it.get("redirect_url"),
                           (it.get("location") or {}).get("display_name")))
        time.sleep(1)
    return out


def from_greenhouse(board):
    out = []
    for it in getjson("https://boards-api.greenhouse.io/v1/boards/%s/jobs" % board).get("jobs", []):
        out.append(rec("greenhouse:" + board, it.get("id"), board, it.get("title"),
                       it.get("absolute_url"), (it.get("location") or {}).get("name")))
    return out


def from_lever(board):
    out = []
    for it in getjson("https://api.lever.co/v0/postings/%s?mode=json" % board):
        out.append(rec("lever:" + board, it.get("id"), board, it.get("text"),
                       it.get("hostedUrl"), (it.get("categories") or {}).get("location")))
    return out


def from_ashby(board):
    out = []
    url = "https://api.ashbyhq.com/posting-api/job-board/%s?includeCompensation=true" % board
    for it in getjson(url).get("jobs", []):
        loc = it.get("location") or ("remote" if it.get("isRemote") else "")
        out.append(rec("ashby:" + board, it.get("id"), board, it.get("title"),
                       it.get("jobUrl") or it.get("applyUrl"), loc))
    return out


# ---------------------------- filtering ---------------------------
def matches(r, cfg):
    title, loc = r["title"].lower(), r["location"].lower()
    blob = title + " " + loc
    if not any(k in title for k in cfg["role_keywords"]):
        return False
    if any(x in title for x in cfg["exclude_titles"]):
        return False
    if any(b in blob for b in cfg["phone_block"]):
        return False
    if any(b in blob for b in cfg["block_locations"]):   # user-specified blocks only
        return False
    accept = cfg["acceptable_locations"]
    if accept:  # restrict ONLY if the user opted in; default [] => no region filter
        if not (r["remote_only"] or (not loc) or any(a in blob for a in accept)):
            return False
    return True


# ----------------------------- runner -----------------------------
def load_seen():
    try:
        with open(SEEN_PATH) as f:
            return set(json.load(f))
    except Exception:
        return set()


def save_seen(seen):
    with open(SEEN_PATH, "w") as f:
        json.dump(sorted(seen), f)


def append_csv(rows):
    new = not os.path.exists(OUT_CSV)
    with open(OUT_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["found_at", "source", "company", "title", "location", "url"])
        ts = time.strftime("%Y-%m-%d %H:%M")
        for r in rows:
            w.writerow([ts, r["source"], r["company"], r["title"], r["location"], r["url"]])


def main():
    cfg = load_cfg()
    sources = []
    u = cfg.get("use", {})
    if u.get("arbeitnow"): sources.append(("arbeitnow", from_arbeitnow))
    if u.get("remoteok"):  sources.append(("remoteok", from_remoteok))
    if u.get("remotive"):  sources.append(("remotive", from_remotive))
    if os.environ.get("ADZUNA_APP_ID"):
        sources.append(("adzuna", lambda: from_adzuna(cfg["adzuna_country"])))
    for b in cfg["greenhouse_boards"]: sources.append(("greenhouse:" + b, lambda b=b: from_greenhouse(b)))
    for b in cfg["lever_boards"]:      sources.append(("lever:" + b, lambda b=b: from_lever(b)))
    for b in cfg["ashby_boards"]:      sources.append(("ashby:" + b, lambda b=b: from_ashby(b)))

    seen, all_recs, per_source = load_seen(), [], {}
    for name, fn in sources:
        try:
            recs = fn(); per_source[name] = len(recs); all_recs.extend(recs)
        except Exception as e:
            warn(name, e)
        time.sleep(0.5)

    uniq, ids = [], set()
    for r in all_recs:
        if r["id"] not in seen and r["id"] not in ids and matches(r, cfg):
            ids.add(r["id"]); uniq.append(r)

    for r in all_recs:   # remember everything seen so future runs only surface new postings
        seen.add(r["id"])
    save_seen(seen)
    if uniq:
        append_csv(uniq)

    print("Polled %d sources: %s" % (len(sources),
          ", ".join("%s=%d" % kv for kv in per_source.items()) or "none reachable"))
    print("NEW matches this run: %d  (appended to %s)" % (len(uniq), OUT_CSV))
    for r in uniq[:15]:
        print("  - [%s] %s @ %s | %s" % (r["source"], r["title"], r["company"], r["url"]))
    if len(uniq) > 15:
        print("  ... and %d more" % (len(uniq) - 15))


if __name__ == "__main__":
    main()
