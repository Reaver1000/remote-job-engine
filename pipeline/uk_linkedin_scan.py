"""UK remote LinkedIn guest scan. Writes uk_remote_jobs.md."""
import re
import time
from datetime import datetime

import requests

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0"}

QUERIES = [
    "IT support",
    "technical support",
    "application support",
    "support engineer",
    "data analyst",
    "junior data",
    "operations analyst",
    "graduate",
    "QA engineer",
    "python",
]

BASE = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

CARD = re.compile(r"<li>.*?</li>", re.S)
TITLE = re.compile(r'base-search-card__title">\s*(.*?)\s*</h3>', re.S)
COMPANY = re.compile(r'base-search-card__subtitle">\s*<a[^>]*>\s*(.*?)\s*</a>', re.S)
LOC = re.compile(r'job-search-card__location">\s*(.*?)\s*</span>', re.S)
LINK = re.compile(r'base-card__full-link[^"]*"\s+href="([^"]+)"')
TIME = re.compile(r'datetime="([^"]+)"')


def clean(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()


rows = []
seen = set()
statuses = []

for q in QUERIES:
    for start in (0, 10):
        try:
            r = requests.get(
                BASE,
                params={
                    "keywords": q,
                    "location": "United Kingdom",
                    "f_WT": "2",
                    "f_TPR": "r604800",
                    "start": start,
                },
                headers=H,
                timeout=25,
            )
        except Exception as exc:
            statuses.append(f"{q} start={start} error {exc}")
            continue
        statuses.append(f"{q} start={start} status={r.status_code}")
        if r.status_code != 200:
            time.sleep(3)
            continue
        for card in CARD.findall(r.text):
            t = TITLE.search(card)
            c = COMPANY.search(card)
            l = LOC.search(card)
            href = LINK.search(card)
            tm = TIME.search(card)
            if not (t and href):
                continue
            url = href.group(1).split("?")[0]
            if url in seen:
                continue
            seen.add(url)
            rows.append(
                {
                    "title": clean(t.group(1)),
                    "company": clean(c.group(1)) if c else "",
                    "loc": clean(l.group(1)) if l else "",
                    "date": tm.group(1)[:10] if tm else "",
                    "url": url,
                }
            )
        time.sleep(2)

rows.sort(key=lambda x: x["date"], reverse=True)

with open("uk_remote_jobs.md", "w", encoding="utf-8") as f:
    f.write(f"# UK REMOTE LINKEDIN - {datetime.now():%Y-%m-%d}\n\n")
    f.write(f"{len(rows)} unique roles across {len(QUERIES)} queries, past week, remote filter.\n\n")
    for r in rows:
        f.write(f'### {r["title"]} @ {r["company"]}\n')
        f.write(f'- loc: {r["loc"]} | posted: {r["date"]}\n')
        f.write(f'- url: {r["url"]}\n\n')

print(f"{len(rows)} unique UK remote roles written to uk_remote_jobs.md")
for s in statuses:
    print("  ", s)
