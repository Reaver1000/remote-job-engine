"""Greenhouse public board API. No key required."""

from urllib.parse import quote

from .base import company_from_slug, get_json, job


def fetch(slug):
    data = get_json(f"https://boards-api.greenhouse.io/v1/boards/{quote(slug)}/jobs?content=true")
    out = []
    for j in data.get("jobs", []):
        loc = j.get("location") or {}
        loc = loc.get("name", "") if isinstance(loc, dict) else str(loc)
        out.append(
            job(
                title=j.get("title"),
                company=j.get("company_name") or company_from_slug(slug),
                location=loc,
                url=j.get("absolute_url") or f"https://job-boards.greenhouse.io/{slug}",
                source=f"ats:greenhouse:{slug}",
                posted=str(j.get("updated_at") or "")[:10],
                description=j.get("content") or "",
            )
        )
    return out
