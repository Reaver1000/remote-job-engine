"""SmartRecruiters public postings API. No key required."""

from urllib.parse import quote

from .base import get_json, job


def fetch(slug):
    data = get_json(
        f"https://api.smartrecruiters.com/v1/companies/{quote(slug)}/postings?limit=100"
    )
    out = []
    for j in data.get("content", []):
        loc = j.get("location") or {}
        if isinstance(loc, dict):
            parts = [loc.get("city"), loc.get("region"), loc.get("country")]
            location = ", ".join(p for p in parts if p)
        else:
            location = str(loc)
        pid = j.get("id")
        out.append(
            job(
                title=j.get("name"),
                company=(j.get("company") or {}).get("name") if isinstance(j.get("company"), dict) else slug,
                location=location,
                url=j.get("ref") or (f"https://jobs.smartrecruiters.com/{slug}/{pid}" if pid else ""),
                source=f"ats:smartrecruiters:{slug}",
                remote=(loc.get("remote") if isinstance(loc, dict) else None),
                posted=str(j.get("releasedDate") or "")[:10],
                description=(j.get("jobAd") or {}).get("sections", {}).get("jobDescription", {}).get("text", "")
                if isinstance(j.get("jobAd"), dict)
                else "",
            )
        )
    return out
