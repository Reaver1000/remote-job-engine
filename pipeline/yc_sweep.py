"""Y Combinator / Work at a Startup job board sweep.

    python yc_sweep.py

Scrapes https://www.ycombinator.com/jobs for remote support and operations
roles. YC startups are smaller companies with less competition. Many roles
are US-only, so this sweep filters for EU/UK/Germany-eligible remote roles
using the visa field and location text.

Outputs: yc_jobs.md and yc_jobs.json
"""
import html as htmlmod
import json
import re
import time
from pathlib import Path

import job_sweep as js

HERE = Path(__file__).parent
OUT_MD = HERE / "yc_jobs.md"
OUT_JSON = HERE / "yc_jobs.json"

YC_URLS = [
    "https://www.ycombinator.com/jobs/role/support/remote",
    "https://www.ycombinator.com/jobs/role/operations/remote",
]

# Visa values that indicate US-only hiring
US_VISA_MARKERS = ["us citizen/visa only", "us citizen/visa required"]

# Location text markers indicating US-only
US_ONLY_MARKERS = ["remote (us)", "remote (ca, us)", "remote (ca us)", "us only", "united states only"]

# EU/UK/Germany location markers
EU_MARKERS = [
    "remote", "gb", "de", "fr", "nl", "eu", "emea", "europe",
    "united kingdom", "germany", "france", "netherlands", "scotland",
    "london", "berlin", "amsterdam", "paris", "munich", "hamburg",
    "frankfurt", "cologne", "stuttgart", "dusseldorf", "leipzig", "erfurt",
    "dublin", "ireland", "spain", "italy", "portugal", "poland",
    "sweden", "denmark", "norway", "finland", "austria", "belgium",
    "switzerland", "czech", "romania", "greece", "hungary", "croatia",
    "slovenia", "slovakia", "bulgaria", "estonia", "latvia", "lithuania",
]


def is_eu_eligible(location_text, visa_text):
    """Check if a job is EU/UK/Germany eligible for the candidate."""
    loc = location_text.lower()
    visa = visa_text.lower()

    # hard kill: US visa required
    if any(m in visa for m in US_VISA_MARKERS):
        return False

    # hard kill: US-only location
    if any(m in loc for m in US_ONLY_MARKERS):
        return False

    # check for EU/UK/Germany markers
    return any(m in loc for m in EU_MARKERS)


def extract_job_postings(html):
    """Extract job postings JSON from YC page HTML."""
    unescaped = htmlmod.unescape(html)
    pattern = re.search(r'"jobPostings"\s*:\s*\[', unescaped)
    if not pattern:
        return []
    arr_start = pattern.end() - 1
    depth = 0
    arr_end = arr_start
    for i in range(arr_start, len(unescaped)):
        if unescaped[i] == '[':
            depth += 1
        elif unescaped[i] == ']':
            depth -= 1
            if depth == 0:
                arr_end = i + 1
                break
    try:
        return json.loads(unescaped[arr_start:arr_end])
    except Exception:
        return []


def scrape_yc_page(url):
    """Scrape a YC jobs page and return list of EU-eligible job dicts."""
    jobs = []
    try:
        raw = js.fetch(url)
        if isinstance(raw, bytes):
            page = raw.decode("utf-8", errors="replace")
        else:
            page = str(raw)
    except Exception as e:
        print(f"  fetch failed: {str(e)[:80]}")
        return jobs

    data = extract_job_postings(page)
    print(f"  parsed {len(data)} jobs from page")

    for j in data:
        title = j.get("title", "")
        company = j.get("companyName", "")
        location = j.get("location", "")
        salary = j.get("salaryRange", "")
        visa = j.get("visa", "")
        min_exp = j.get("minExperience", "")
        job_url = j.get("url", "")
        full_url = "https://www.ycombinator.com" + job_url if job_url else ""

        if not title:
            continue

        # EU eligibility check
        if not is_eu_eligible(location, visa):
            continue

        # role keyword check
        title_low = title.lower()
        if not any(k in title_low for k in ["support", "operations", "analyst", "data", "customer", "success", "implementation", "onboarding", "technical", "junior", "associate", "coordinator", "specialist", "engineer", "consultant", "trainee", "graduate", "entry"]):
            continue

        jobs.append({
            "title": title,
            "company": company,
            "location": location,
            "remote": "remote" in location.lower(),
            "salary": salary,
            "url": full_url,
            "desc": f"{title} at {company}. Location: {location}. Visa: {visa}. Experience: {min_exp}.",
            "visa": visa,
            "min_exp": min_exp,
        })

    return jobs


def main():
    js.RAW = []
    js.SEEN_FILE = HERE / "yc_seen.json"

    print("=== YC STARTUP SWEEP ===", flush=True)

    all_jobs = []
    for url in YC_URLS:
        print(f"scraping {url}...", flush=True)
        jobs = scrape_yc_page(url)
        print(f"  found {len(jobs)} EU-eligible roles")
        for j in jobs:
            js.collect(j["title"], j["company"], j["location"], j["remote"],
                       [], j["url"], j["desc"], "yc:workatastartup", j["salary"])
            all_jobs.append(j)
        time.sleep(1)

    # dedupe
    seen = set()
    uniq = []
    for j in js.RAW:
        key = (j["title"].lower()[:55], j["company"].lower()[:25])
        if key in seen or not j["title"]:
            continue
        seen.add(key)
        uniq.append(j)
    print(f"unique: {len(uniq)}")

    # eliminate and score
    killed = []
    kept = []
    for j in uniq:
        reason = js.eliminate(j)
        if reason:
            j["kill_reason"] = reason
            killed.append(j)
        else:
            j["family"] = js.family_of(j["title"], j["desc"])
            j["score"] = js.score(j)
            j["why"] = js.why_fit(j)
            kept.append(j)

    kept.sort(key=lambda j: -j["score"])
    print(f"KEPT {len(kept)} | KILLED {len(killed)}")

    # write markdown
    import datetime
    lines = [f"# YC STARTUP SWEEP - {datetime.datetime.now().strftime('%Y-%m-%d')}",
             "", f"{len(kept)} YC startup roles after dedupe and elimination.", ""]
    for i, j in enumerate(kept, 1):
        lines.append(f"## {i}. [{j['score']}] {j['title']}")
        lines.append(f"- company: {j['company']}")
        lines.append(f"- location: {j['location']}")
        if j.get("salary"):
            lines.append(f"- pay: {j['salary']}")
        lines.append(f"- source: {j['source']}")
        lines.append(f"- url: {j['url']}")
        lines.append("")

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT_MD} with {len(kept)} entries")

    # write json
    def slim(j):
        return {k: j.get(k) for k in ("title", "company", "location", "salary", "url",
                                      "source", "score", "family", "why", "remote_flag",
                                      "tags", "is_new")}
    OUT_JSON.write_text(json.dumps([slim(j) for j in kept], ensure_ascii=False, indent=1),
                        encoding="utf-8")
    print(f"wrote {OUT_JSON}")


if __name__ == "__main__":
    main()
