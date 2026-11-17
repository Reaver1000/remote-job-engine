"""Fintech-focused sweep. Runs alongside daily.py.

    python fintech_sweep.py

Searches fintech companies' career pages (via ATS APIs) and job boards
for remote junior/operations/data roles. Outputs fintech_jobs.md and
fintech_jobs.json. Reuses shared logic from job_sweep.py.

This script is designed to be readable by any model or human. It:
1. Searches fintech company career pages via Greenhouse ATS API
2. Searches arbeitnow job board for fintech company roles
3. Searches jobicy for fintech roles
4. Filters existing broad sweep results for fintech companies
5. Eliminates roles that don't match the candidate's constraints (remote, pay, seniority, language)
6. Scores and ranks remaining roles
7. Writes results to fintech_jobs.md and fintech_jobs.json

the candidate's constraints (from profile):
- Remote required (health reasons), no driver's licence
- Based in Erfurt, Germany; British citizen with UK right to work
- English native, German C1 spoken / B1 written (no customer-facing C1 written German)
- Pay floor: 35k EUR or 40k GBP
- Available one month after an offer
- No colons in prose, no em dashes, British spelling
- Never state salary at formula-based companies
- Prefers smaller companies, neurodivergent-friendly
"""
import json
import re
import time
import datetime
from pathlib import Path

import job_sweep as js

HERE = Path(__file__).parent
OUT_MD = HERE / "fintech_jobs.md"
OUT_JSON = HERE / "fintech_jobs.json"

# ---------------------------------------------------------------------------
# Fintech company names (lowercase) — used to filter job board results
# ---------------------------------------------------------------------------
FINTECH_NAMES = {
    "monzo", "starling", "revolut", "wise", "gocardless", "stripe", "plaid",
    "tide", "clearbank", "modulr", "currencycloud", "oaknorth", "monese",
    "checkout", "n26", "sumup", "adyen", "mollie", "klarna", "bunq",
    "transferwise", "mondo", "izettle", "square", "block", "cash app",
}

# ---------------------------------------------------------------------------
# Greenhouse ATS board names for fintech companies (verified working)
# ---------------------------------------------------------------------------
FINTECH_GREENHOUSE = {
    "monzo": "monzo",
    "wise": "wise",
    "gocardless": "gocardless",
    "sumup": "sumup",
    "adyen": "adyen",
    "n26": "n26",
    "tide": "tide",
    "stripe": "stripe",
}

# ---------------------------------------------------------------------------
# Role keywords — job title must contain at least one of these
# ---------------------------------------------------------------------------
ROLE_KEYWORDS = [
    "junior", "associate", "analyst", "operations", "data", "support",
    "billing", "revenue", "technical", "implementation", "onboarding",
    "customer", "product", "automation", "engineer", "coordinator",
    "specialist", "consultant", "trainee", "graduate", "entry",
]


def collect_ft(title, company, location, remote_flag, tags, url, desc, source, salary=""):
    """Wrapper around job_sweep.collect — adds a job to the shared RAW list."""
    js.collect(title, company, location, remote_flag, tags, url, desc, source, salary)


# ---------------------------------------------------------------------------
# Source 1: Greenhouse ATS (fintech company career pages)
# ---------------------------------------------------------------------------
def src_greenhouse_fintech():
    """Fetch jobs from known fintech Greenhouse boards.

    For each company, fetch all jobs from their Greenhouse board.
    Only collect jobs that are remote/EMEA/UK/Germany and match role keywords.
    """
    for name, board in FINTECH_GREENHOUSE.items():
        try:
            import urllib.request
            url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            data = json.loads(urllib.request.urlopen(req, timeout=30).read().decode())
            count = 0
            for j in data.get("jobs", []):
                title = j.get("title", "")
                loc = j.get("location", {}).get("name", "")
                job_url = j.get("absolute_url", "")
                content = j.get("content", "")
                desc = re.sub(r"<[^>]+>", " ", content)[:1500] if content else ""
                loc_low = loc.lower()
                remote = "remote" in loc_low
                # skip on-site roles outside Germany/UK/Europe
                if not remote and not any(k in loc_low for k in ("emea", "europe", "uk", "germany", "remote", "anywhere", "global", "london", "berlin", "amsterdam")):
                    continue
                title_low = title.lower()
                if not any(k in title_low for k in ROLE_KEYWORDS):
                    continue
                collect_ft(title, name.title(), loc, remote, [], job_url, desc, f"greenhouse:{name}")
                count += 1
            print(f"  greenhouse:{name}: {len(data.get('jobs', []))} jobs, {count} collected")
        except Exception as e:
            print(f"  greenhouse:{name} CRASH: {str(e)[:80]}")
        time.sleep(0.5)


# ---------------------------------------------------------------------------
# Source 2: arbeitnow job board (filter by fintech company name)
# ---------------------------------------------------------------------------
def src_arbeitnow_fintech():
    """Scan arbeitnow job board pages 1-10 for fintech company roles.

    Only collects jobs where the company name matches a known fintech.
    """
    for page in range(1, 11):
        try:
            data = json.loads(js.fetch(f"https://www.arbeitnow.com/api/job-board-api?page={page}"))
        except Exception as e:
            print(f"  arbeitnow p{page} stop: {str(e)[:60]}")
            break
        jobs = data.get("data", [])
        if not jobs:
            break
        for j in jobs:
            company = (j.get("company_name") or "").lower()
            title = j.get("title", "")
            desc = js.clean(j.get("description", ""))[:1500]
            # only collect if company is a known fintech
            if not any(c in company for c in FINTECH_NAMES):
                continue
            loc = "REMOTE-flag" if j.get("remote") else j.get("location", "")
            collect_ft(title, j.get("company_name", ""), loc, bool(j.get("remote")),
                       j.get("tags", []), j.get("url", ""), desc, "arbeitnow:fintech")
        time.sleep(0.3)
    print(f"  arbeitnow fintech: scanned {page} pages")


# ---------------------------------------------------------------------------
# Source 3: jobicy job board (filter by fintech company name)
# ---------------------------------------------------------------------------
def src_jobicy_fintech():
    """Fetch remote jobs from jobicy and filter for fintech companies."""
    try:
        data = json.loads(js.fetch("https://jobicy.com/api/v2/remote-jobs?count=50"))
        count = 0
        for j in data.get("jobs", []):
            title = j.get("jobTitle", "")
            company = j.get("companyName", "")
            loc = j.get("jobGeo", "")
            desc = js.clean(j.get("jobDescription", ""))[:1500]
            company_low = company.lower()
            title_low = title.lower()
            # only collect if company is a known fintech
            if not any(c in company_low for c in FINTECH_NAMES):
                continue
            remote = "remote" in loc.lower() or "anywhere" in loc.lower() or "global" in loc.lower()
            salary = j.get("annualSalaryMin", "") or j.get("annualSalaryMax", "")
            collect_ft(title, company, loc, remote, [], j.get("url", ""), desc, "jobicy:fintech", str(salary))
            count += 1
        print(f"  jobicy fintech: {len(data.get('jobs', []))} jobs, {count} collected")
    except Exception as e:
        print(f"  jobicy fintech CRASH: {str(e)[:80]}")


# ---------------------------------------------------------------------------
# Source 4: broad sweep results (filter existing jobs_found.json for fintech)
# ---------------------------------------------------------------------------
def src_broad_fintech():
    """Filter existing broad sweep results for fintech company roles."""
    try:
        data = json.loads((HERE / "jobs_found.json").read_text(encoding="utf-8"))
        count = 0
        for j in data:
            company = (j.get("company") or "").lower()
            if not any(c in company for c in FINTECH_NAMES):
                continue
            tags = j.get("tags", [])
            if isinstance(tags, list):
                tags_str = " ".join(tags)
            else:
                tags_str = str(tags)
            collect_ft(j.get("title", ""), j.get("company", ""), j.get("location", ""),
                       j.get("remote_flag", False), j.get("tags", []),
                       j.get("url", ""), tags_str, "broad:fintech", j.get("salary", ""))
            count += 1
        print(f"  broad fintech: {count} matches from {len(data)} existing jobs")
    except Exception as e:
        print(f"  broad fintech CRASH: {str(e)[:80]}")


# ---------------------------------------------------------------------------
# Main: run all sources, dedupe, eliminate, score, write output
# ---------------------------------------------------------------------------
def main():
    # reset shared state
    js.RAW = []
    js.SEEN_FILE = HERE / "fintech_seen.json"

    print("=== FINTECH SWEEP ===", flush=True)

    sources = [
        ("greenhouse_fintech", src_greenhouse_fintech),
        ("arbeitnow_fintech", src_arbeitnow_fintech),
        ("jobicy_fintech", src_jobicy_fintech),
        ("broad_fintech", src_broad_fintech),
    ]

    for name, fn in sources:
        print(f"{name}...", flush=True)
        try:
            fn()
        except Exception as e:
            print(f"  CRASH {name}: {str(e)[:80]}")
        print(f"  raw total: {len(js.RAW)}", flush=True)

    # dedupe by title+company
    seen = set()
    uniq = []
    for j in js.RAW:
        key = (j["title"].lower()[:55], j["company"].lower()[:25])
        if key in seen or not j["title"]:
            continue
        seen.add(key)
        uniq.append(j)
    print(f"unique: {len(uniq)}")

    # eliminate roles that don't match constraints, score the rest
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

    # write markdown output
    import datetime
    lines = [f"# FINTECH SWEEP - {datetime.datetime.now().strftime('%Y-%m-%d')}",
             "", f"{len(kept)} fintech roles after dedupe and elimination.", ""]
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

    # write json output
    def slim(j):
        return {k: j.get(k) for k in ("title", "company", "location", "salary", "url",
                                      "source", "score", "family", "why", "remote_flag",
                                      "tags", "is_new")}
    OUT_JSON.write_text(json.dumps([slim(j) for j in kept], ensure_ascii=False, indent=1),
                        encoding="utf-8")
    print(f"wrote {OUT_JSON}")


if __name__ == "__main__":
    main()
