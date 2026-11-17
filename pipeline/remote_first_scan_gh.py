"""Greenhouse side of the remote-first scan. Many of these companies are
'all-remote' and hire in Germany/UK. Pulls public board JSON, filters for
junior-friendly support / QA / data / ops roles that are not region-locked
to the US."""
import requests, re
from datetime import datetime, timedelta

H = {"User-Agent": "Mozilla/5.0"}
BOARDS = [
    "gitlab", "automattic", "doist", "hotjar", "typeform", "zapier", "buffer",
    "toggl", "remotecom", "deel", "canonical", "elastic", "mongodb", "datadog",
    "hashicorp", "confluent", "redis", "twilio", "cloudflare", "digitalocean",
    "docker", "sentry", "airtable", "asana", "dropbox", "duolingo", "etsy",
    "figma", "grammarly", "instacart", "intercom", "klaviyo", "lyft", "miro",
    "netlify", "njnal", "patreon", "pinterest", "reddit", "shopify", "spotify",
    "stripe", "webflow", "weworkremotely", "zendesk", "hellofresh", "personio",
    "sumup", "n26", "trade-republic", "getyourguide", "contentful", "typeform2",
]

TITLE = re.compile(
    r"support|qa|test|quality|data|analyst|analytics|operations|ops\b|"
    r"junior|associate|coordinator|specialist|success|onboarding|"
    r"implementation|solutions|technical|administrator|\bit\b",
    re.I,
)
KILL_TITLE = re.compile(
    r"\b(head|director|vp|vice president|principal|staff|lead|manager|"
    r"architect|scientist|intern|working student|werkstudent|sales|"
    r"account executive|counsel|recruiter)\b",
    re.I,
)
LOC_OK = re.compile(
    r"remote|anywhere|worldwide|global|emea|europe|germany|deutschland|"
    r"united kingdom|\buk\b|london|berlin|munich|amsterdam|dublin|ireland|"
    r"spain|portugal|poland|france|netherlands|sweden|denmark|norway|"
    r"switzerland|austria|italy|belgium|czech|estonia|lithuania|latvia",
    re.I,
)
LOC_KILL = re.compile(
    r"united states|usa|us only|canada only|apac|asia|australia|india|"
    r"singapore|japan|brazil|latam|mexico|philippines|nigeria|kenya|"
    r"south africa|new york|san francisco|seattle|austin|toronto|chicago|"
    r"boston|denver|atlanta",
    re.I,
)

cutoff = datetime.now() - timedelta(days=75)
rows, seen = [], set()
for slug in dict.fromkeys(BOARDS):
    try:
        r = requests.get(
            f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
            headers=H, timeout=25,
        )
        if r.status_code != 200:
            continue
        jobs = r.json().get("jobs", [])
    except Exception:
        continue
    for j in jobs:
        title = (j.get("title") or "").strip()
        loc = ((j.get("location") or {}).get("name") or "").strip()
        url = j.get("absolute_url") or ""
        pub = str(j.get("updated_at") or j.get("first_published") or "")[:10]
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
        rows.append((pub, slug, title, loc, url))

rows.sort(reverse=True)
print(f"{len(rows)} candidates from {len(set(r[1] for r in rows))} boards\n")
for pub, slug, title, loc, url in rows:
    print(f"{pub} | {slug:12} | {title[:55]:55} | {loc[:32]}")
    print(f"    {url}")
