"""Workable public widget API. No key required."""

from urllib.parse import quote

from .base import get_json, job


def fetch(slug):
    data = get_json(f"https://apply.workable.com/api/v1/widget/accounts/{quote(slug)}?details=true")
    out = []
    for j in data.get("jobs", []):
        loc = j.get("location") or {}
        if isinstance(loc, dict):
            parts = [loc.get("city"), loc.get("region"), loc.get("country")]
            location = ", ".join(p for p in parts if p)
        else:
            location = str(loc)
        code = j.get("shortcode") or j.get("id")
        url = j.get("url") or j.get("application_url")
        if not url and code:
            url = f"https://apply.workable.com/{slug}/j/{code}/"
        out.append(
            job(
                title=j.get("title"),
                company=j.get("company") or slug,
                location=location,
                url=url or f"https://apply.workable.com/{slug}/",
                source=f"ats:workable:{slug}",
                remote=j.get("telecommuting"),
                posted=str(j.get("published_on") or "")[:10],
                description=j.get("description") or "",
            )
        )
    return out
