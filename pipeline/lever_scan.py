"""Lever public postings scan for EMEA-remote support/QA/data/ops roles."""
import re
import requests
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

H = {"User-Agent": "Mozilla/5.0"}
SLUGS = [
    "pipedrive", "mews", "showpad", "teamleader", "backbase", "mollie", "bunq",
    "tiqets", "sennder", "personio", "wefox", "contentful", "typeform", "hotjar",
    "sitecore", "optimizely", "unily", "matillion", "peakon", "attio", "pleo",
    "qonto", "spendesk", "payfit", "lucca", "365talents", "swile", "alan",
    "ledger", "qonto", "beleap", "gymlib", "didomi", "october", "sinequa",
    "botify", "datadome", "contentsquare", "teads", "ogury", "dailymotion",
    "deezer", "qwant", "blablacar", "doctolib", "manomano", "veepee",
    "trainline", "skyscanner", "transferwise", "monzo", "starling", "revolut",
    "zopa", "funding-circle", "checkout", "go-cardless", "tide", "cleo",
    "thoughtmachine", "form3", "onfido", "compliancy-group", "featurespace",
    "trustpilot", "peak", "signal-ai", "unbabel", "talkdesk", "zendesk",
    "intercom", "front", "canny", "miro", "pitch", "notion", "slite",
    "algolia", "meilisearch", "contentful", "sanity", "storyblok", "prismic",
    "strapi", "hygraph", "cloudinary", "imgix", "mux", "vimeo", "wistia",
]

TITLE = re.compile(
    r"support|qa\b|test|quality|data|analyst|operations|ops\b|junior|associate|"
    r"coordinator|specialist|success|onboarding|implementation|solutions|technical|\bit\b",
    re.I,
)
KILL = re.compile(
    r"\b(head|director|vp|principal|staff|lead|manager|architect|scientist|"
    r"intern|sales|account executive|counsel|recruiter)\b",
    re.I,
)
LOC_OK = re.compile(
    r"remote|anywhere|worldwide|global|emea|europe|germany|deutschland|"
    r"united kingdom|\buk\b|london|berlin|munich|amsterdam|dublin|ireland|"
    r"spain|portugal|poland|france|netherlands|sweden|denmark|norway|"
    r"switzerland|austria|italy|belgium|czech|estonia",
    re.I,
)
LOC_KILL = re.compile(
    r"united states|usa|us only|canada|apac|asia|australia|india|singapore|"
    r"japan|brazil|latam|mexico|philippines|nigeria|kenya|south africa",
    re.I,
)


def fetch(slug):
    try:
        r = requests.get(f"https://api.lever.co/v0/postings/{slug}?mode=json", headers=H, timeout=20)
        if r.status_code != 200:
            return slug, []
        return slug, r.json()
    except Exception:
        return slug, []


def main():
    rows, seen = [], set()
    cutoff = datetime.now() - timedelta(days=75)
    with ThreadPoolExecutor(max_workers=12) as ex:
        for slug, jobs in ex.map(fetch, dict.fromkeys(SLUGS)):
            for j in jobs:
                t = (j.get("text") or "").strip()
                cats = j.get("categories") or {}
                loc = (cats.get("location") or "").strip()
                url = j.get("hostedUrl") or ""
                if not t or not url or url in seen:
                    continue
                if not TITLE.search(t) or KILL.search(t):
                    continue
                if not LOC_OK.search(loc) or LOC_KILL.search(loc):
                    continue
                ts = j.get("createdAt")
                pub = ""
                if isinstance(ts, (int, float)):
                    dt = datetime.fromtimestamp(ts / 1000)
                    if dt < cutoff:
                        continue
                    pub = dt.strftime("%Y-%m-%d")
                seen.add(url)
                rows.append((pub, slug, t, loc, url))
    rows.sort(reverse=True)
    print(f"{len(rows)} candidates\n")
    for pub, slug, t, loc, u in rows[:50]:
        print(f"{pub} | {slug:14} | {t[:52]:52} | {loc[:34]}")
        print(f"    {u}")


if __name__ == "__main__":
    main()
