"""Ashby EMEA-eligibility scan.

The public posting API exposes address.postalAddress.addressCountry, which is
the real hiring-eligibility field. Location strings lie; this does not.
Keeps roles a Germany-based candidate can legally hold."""
import json, re, requests
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

H = {"User-Agent": "Mozilla/5.0"}

TITLE = re.compile(
    r"support|qa\b|test|quality|data|analyst|analytics|operations|ops\b|"
    r"junior|associate|coordinator|specialist|success|onboarding|"
    r"implementation|solutions|technical|administrator|\bit\b",
    re.I,
)
KILL = re.compile(
    r"\b(head|director|vp|vice president|principal|staff|lead|manager|"
    r"architect|scientist|intern|working student|werkstudent|sales|"
    r"account executive|counsel|recruiter|engineer,? (?:backend|frontend|"
    r"fullstack|full-stack|software|platform|security|machine learning)|"
    r"software engineer|backend engineer|frontend engineer)\b",
    re.I,
)

COUNTRY_OK = re.compile(
    r"eu\b|europe|european union|germany|deutschland|united kingdom|\buk\b|"
    r"worldwide|anywhere|global|emea|remote|austria|switzerland|netherlands|"
    r"ireland|spain|portugal|poland|france|italy|belgium|denmark|sweden|"
    r"norway|finland|czech|estonia|lithuania|latvia|slovakia|slovenia|"
    r"croatia|romania|bulgaria|hungary|greece|luxembourg",
    re.I,
)
COUNTRY_KILL = re.compile(
    r"united states|\busa\b|us only|canada|apac|asia|australia|india|"
    r"singapore|japan|brazil|latam|mexico|philippines|nigeria|kenya|"
    r"south africa|colombia|argentina|israel|turkey|egypt|morocco",
    re.I,
)

BOARD_FILE = "ashby_slugs.json"


def load_slugs():
    src = open("job_sweep.py", encoding="utf-8").read()
    i = src.find("def src_ashby")
    j = src.find("slugs.update([", i)
    k = src.find("])", j)
    body = src[j:k]
    slugs = re.findall(r'"([^"]+)"', body)
    return list(dict.fromkeys(slugs))


def fetch(slug):
    try:
        r = requests.get(
            f"https://api.ashbyhq.com/posting-api/job-board/{slug}",
            headers=H, timeout=20,
        )
        if r.status_code != 200:
            return []
        return r.json().get("jobs", [])
    except Exception:
        return []


def eligible(j):
    country = ((j.get("address") or {}).get("postalAddress") or {}).get("addressCountry") or ""
    loc = j.get("location") or ""
    blob = f"{country} | {loc}"
    if COUNTRY_KILL.search(blob):
        return None
    if not COUNTRY_OK.search(blob):
        return None
    return country.strip() or loc.strip()


def main():
    slugs = load_slugs()
    print(f"scanning {len(slugs)} boards")
    out, seen = [], set()
    cutoff = datetime.now() - timedelta(days=60)
    with ThreadPoolExecutor(max_workers=16) as ex:
        for slug, jobs in zip(slugs, ex.map(fetch, slugs)):
            for j in jobs:
                t = (j.get("title") or "").strip()
                u = j.get("jobUrl") or ""
                if not t or not u or u in seen:
                    continue
                if not TITLE.search(t) or KILL.search(t):
                    continue
                where = eligible(j)
                if not where:
                    continue
                pub = str(j.get("publishedAt") or "")[:10]
                try:
                    if pub and datetime.fromisoformat(pub) < cutoff:
                        continue
                except Exception:
                    pass
                seen.add(u)
                out.append((pub, slug, t, where, u))

    out.sort(reverse=True)
    print(f"\n{len(out)} EMEA-eligible candidates\n")
    for pub, slug, t, where, u in out[:60]:
        print(f"{pub} | {slug[:16]:16} | {t[:52]:52} | {where[:28]}")
        print(f"    {u}")

    with open("emea_eligible.md", "w", encoding="utf-8") as f:
        f.write(f"# EMEA-eligible roles - {datetime.now():%Y-%m-%d}\n\n")
        for pub, slug, t, where, u in out:
            f.write(f"- {pub} | {slug} | {t} | {where}\n  {u}\n")


if __name__ == "__main__":
    main()
