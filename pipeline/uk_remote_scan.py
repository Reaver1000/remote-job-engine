"""UK and Ireland remote scan, filtered on the company's own hiring country.

The German market is the binding constraint, not location. This scan targets the
lane where the user is a native speaker with a passport, a UK address and a UK
bank. Ashby only, because addressCountry on Ashby is the one location field that
does not lie.

    python uk_remote_scan.py
    python uk_remote_scan.py --days 90
"""
import argparse
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import requests

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0"}

TITLE = re.compile(
    r"support|helpdesk|help desk|service desk|analyst|analysis|qa\b|quality|tester|"
    r"test automation|data|operations|\bops\b|associate|junior|graduate|entry|"
    r"coordinator|specialist|success|onboarding|implementation|solutions|"
    r"administrator|sysadmin|python|automation|integration|reporting",
    re.I,
)
KILL = re.compile(
    r"\b(senior|sr\.?|lead|principal|staff|head|director|vp|chief|manager|"
    r"architect|scientist|sales|account executive|recruiter|counsel|lawyer)\b",
    re.I,
)
COUNTRY_OK = re.compile(r"united kingdom|ireland", re.I)
LOC_FALLBACK = re.compile(r"united kingdom|\buk\b|england|scotland|wales|"
                          r"northern ireland|london|manchester|edinburgh|glasgow|"
                          r"bristol|leeds|birmingham|belfast|cardiff|dublin|ireland", re.I)


def load_slugs():
    src = open("job_sweep.py", encoding="utf-8").read()
    i = src.find("def src_ashby")
    j = src.find("slugs.update([", i)
    k = src.find("])", j)
    return list(dict.fromkeys(re.findall(r'"([^"]+)"', src[j:k])))


def fetch(slug):
    try:
        r = requests.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}",
                         headers=H, timeout=20)
        if r.status_code != 200:
            return slug, []
        return slug, r.json().get("jobs", [])
    except Exception:
        return slug, []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=120)
    args = ap.parse_args()

    slugs = load_slugs()
    cutoff = datetime.now() - timedelta(days=args.days)
    rows, seen = [], set()

    with ThreadPoolExecutor(max_workers=16) as ex:
        for slug, jobs in ex.map(fetch, slugs):
            for j in jobs:
                title = (j.get("title") or "").strip()
                if not title or not TITLE.search(title) or KILL.search(title):
                    continue
                addr = ((j.get("address") or {}).get("postalAddress") or {})
                country = addr.get("addressCountry") or ""
                loc = j.get("location") or ""
                remote = (j.get("workplaceType") or "").lower() == "remote"
                if not remote:
                    continue
                if not (COUNTRY_OK.search(country) or COUNTRY_OK.search(loc) or LOC_FALLBACK.search(loc)):
                    continue
                if COUNTRY_OK.search(country) is None and re.search(
                        r"united states|canada|india|philippines|australia", loc, re.I):
                    continue
                pub = str(j.get("publishedAt") or "")[:10]
                if pub:
                    try:
                        if datetime.fromisoformat(pub) < cutoff:
                            continue
                    except Exception:
                        pass
                url = j.get("jobUrl") or ""
                if not url or url in seen:
                    continue
                seen.add(url)
                rows.append((pub, slug, title, f"{country} | {loc}".strip(" |"), url))

    rows.sort(reverse=True)
    print(f"{len(rows)} UK/IE remote roles, last {args.days} days\n")
    for pub, slug, title, where, url in rows[:60]:
        print(f"{pub} | {slug:16} | {title[:56]:56} | {where[:30]}")
        print(f"    {url}")


if __name__ == "__main__":
    main()
