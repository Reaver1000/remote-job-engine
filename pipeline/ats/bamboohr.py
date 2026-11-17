"""BambooHR public careers API. No key required."""

from urllib.parse import quote

from .base import get_json, job


def fetch(slug):
    data = get_json(f"https://{quote(slug)}.bamboohr.com/careers/list")
    out = []
    for j in data.get("result", []):
        loc = j.get("location") or {}
        if isinstance(loc, dict):
            parts = [loc.get("city"), loc.get("state"), loc.get("country")]
            location = ", ".join(p for p in parts if p)
        else:
            location = str(loc)
        jid = j.get("id")
        out.append(
            job(
                title=j.get("jobOpeningName") or j.get("title"),
                company=slug,
                location=location,
                url=f"https://{slug}.bamboohr.com/careers/{jid}" if jid else f"https://{slug}.bamboohr.com/careers",
                source=f"ats:bamboohr:{slug}",
                remote=(loc.get("isRemote") if isinstance(loc, dict) else None) or j.get("isRemote"),
                posted=str(j.get("postedDate") or "")[:10],
                description=j.get("jobDescription") or "",
            )
        )
    return out
