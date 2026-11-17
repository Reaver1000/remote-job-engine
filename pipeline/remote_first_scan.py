"""Scan remote-first company boards (Ashby public API) for EMEA/worldwide
junior support, QA, data, ops and analyst roles. Reliable, no scraping."""
import requests, re, json
from datetime import datetime, timedelta

H = {"User-Agent": "Mozilla/5.0"}
BOARDS = [
    "supabase", "clickhouse", "n8n", "posthog", "linear", "vercel", "raycast",
    "cal", "resend", "neon", "turso", "convex", "browserbase", "mintlify",
    "elevenlabs", "deepgram", "modal", "replit", "runway", "hex", "retool",
    "temporal", "grafana", "sentry", "postman", "airtable", "notion", "loom",
    "descript", "framer", "paddle", "gocardless", "monzo", "wise", "revolut",
    "personio", "pitch", "contentful", "typeform", "hotjar", "doist", "gitlab",
    "zapier", "buffer", "doppler", "render", "fly", "planetscale", "cockroachlabs",
    "timescale", "tinybird", "materialize", "dagster", "prefect", "astronomer",
    "dbtlabs", "fivetran", "hightouch", "census", "segment", "amplitude",
    "mixpanel", "heap", "posthog", "statsig", "launchdarkly", "split",
]

TITLE = re.compile(
    r"support|qa|test|quality|data|analyst|analytics|operations|ops|"
    r"junior|associate|coordinator|specialist|success|onboarding|"
    r"implementation|solutions|technical|administrator|it\b",
    re.I,
)
# kill senior / manager / sales-heavy
KILL_TITLE = re.compile(
    r"\b(head|director|vp|vice president|principal|staff|lead|manager|"
    r"architect|scientist|intern|working student|werkstudent)\b",
    re.I,
)
LOC_OK = re.compile(
    r"remote|anywhere|worldwide|global|emea|europe|eu\b|germany|deutschland|"
    r"united kingdom|uk\b|london|berlin|munich|amsterdam|dublin|ireland|"
    r"spain|portugal|poland|france|netherlands|sweden|denmark|norway|"
    r"switzerland|austria|italy|belgium|czech|estonia|lithuania|latvia",
    re.I,
)
LOC_KILL = re.compile(
    r"united states|usa|us only|canada|apac|asia|australia|india|singapore|"
    r"japan|brazil|latam|mexico|philippines|nigeria|kenya|south africa|"
    r"new york|san francisco|seattle|austin|toronto|chicago|boston",
    re.I,
)

cutoff = datetime.now() - timedelta(days=75)
seen = set()
rows = []
for slug in dict.fromkeys(BOARDS):
    try:
        r = requests.get(
            f"https://api.ashbyhq.com/posting-api/job-board/{slug}",
            headers=H, timeout=20,
        )
        if r.status_code != 200:
            continue
        jobs = r.json().get("jobs", [])
    except Exception:
        continue
    for j in jobs:
        title = (j.get("title") or "").strip()
        loc = (j.get("location") or "").strip()
        url = j.get("jobUrl") or ""
        pub = str(j.get("publishedAt") or "")[:10]
        if not title or not url or url in seen:
            continue
        if not TITLE.search(title) or KILL_TITLE.search(title):
            continue
        if not LOC_OK.search(loc) or LOC_KILL.search(loc):
            continue
        try:
            if pub and datetime.fromisoformat(pub) < cutoff:
                continue
        except Exception:
            pass
        seen.add(url)
        rows.append((slug, title, loc, pub, url, j.get("isRemote")))

rows.sort(key=lambda r: r[3], reverse=True)
print(f"{len(rows)} candidates from {len(set(r[0] for r in rows))} boards\n")
for slug, title, loc, pub, url, remote in rows:
    print(f"{pub} | {slug:14} | {title[:52]:52} | {loc[:30]:30} | {'R' if remote else '-'}")
    print(f"    {url}")
