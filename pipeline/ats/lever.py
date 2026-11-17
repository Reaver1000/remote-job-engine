"""Lever public postings API. No key required."""

from urllib.parse import quote
from datetime import datetime

from .base import company_from_slug, get_json, job


def fetch(slug):
    data = get_json(f"https://api.lever.co/v0/postings/{quote(slug)}?mode=json")
    if not isinstance(data, list):
        return []
    out = []
    for j in data:
        cats = j.get("categories") or {}
        created = j.get("createdAt")
        posted = ""
        if created:
            try:
                posted = datetime.utcfromtimestamp(int(created) / 1000).strftime("%Y-%m-%d")
            except Exception:
                posted = ""
        out.append(
            job(
                title=j.get("text"),
                company=slug,
                location=cats.get("location", ""),
                url=j.get("hostedUrl") or j.get("applyUrl") or f"https://jobs.lever.co/{slug}",
                source=f"ats:lever:{slug}",
                posted=posted,
                description=j.get("descriptionPlain") or j.get("description") or "",
            )
        )
    return out
