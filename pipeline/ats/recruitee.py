"""Recruitee public offers API. No key required."""

from urllib.parse import quote

from .base import get_json, job


def fetch(slug):
    data = get_json(f"https://{quote(slug)}.recruitee.com/api/offers/")
    out = []
    for j in data.get("offers", []):
        loc = j.get("location") or ""
        if not loc:
            parts = [j.get("city"), j.get("country")]
            loc = ", ".join(p for p in parts if p)
        out.append(
            job(
                title=j.get("title"),
                company=j.get("company_name") or slug,
                location=loc,
                url=j.get("careers_url") or j.get("careers_apply_url") or f"https://{slug}.recruitee.com/",
                source=f"ats:recruitee:{slug}",
                remote=j.get("remote"),
                posted=str(j.get("published_at") or j.get("created_at") or "")[:10],
                description=j.get("description") or "",
            )
        )
    return out
