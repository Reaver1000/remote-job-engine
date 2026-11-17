"""Ashby public job board API. No key required."""

from urllib.parse import quote

from .base import get_json, job


def fetch(slug):
    data = get_json(
        f"https://api.ashbyhq.com/posting-api/job-board/{quote(slug)}?includeCompensation=true"
    )
    out = []
    for j in data.get("jobs", []):
        workplace = (j.get("workplaceType") or "").lower()
        remote = workplace == "remote" or (bool(j.get("isRemote")) and workplace != "hybrid")
        out.append(
            job(
                title=j.get("title"),
                company=slug,
                location=j.get("location") or "",
                url=j.get("jobUrl") or f"https://jobs.ashbyhq.com/{slug}",
                source=f"ats:ashby:{slug}",
                remote=remote,
                posted=str(j.get("publishedAt") or "")[:10],
                description=j.get("descriptionPlain") or "",
            )
        )
    return out
