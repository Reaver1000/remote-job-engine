"""Shared helpers for the ATS provider plugins.

Each provider module exposes:

    fetch(slug: str) -> list[dict]

A job dict has these keys:

    title, company, location, remote (bool), url, source, posted, description

`source` is "ats:<provider>:<slug>" so the ranker can trace a row back.
"""

import html
import re
from urllib.request import Request, urlopen

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0"
TIMEOUT = 25


def get(url, timeout=TIMEOUT):
    req = Request(url, headers={"User-Agent": UA, "Accept": "application/json, text/xml, */*"})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


import json


def get_json(url, timeout=TIMEOUT):
    return json.loads(get(url, timeout))


def strip_html(text):
    if not text:
        return ""
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<br\s*/?>|</p>|</li>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def looks_remote(*parts):
    blob = " ".join(str(p or "") for p in parts).lower()
    return any(w in blob for w in ("remote", "home office", "homeoffice", "anywhere", "distributed", "telearbeit"))


def job(title, company, location, url, source, remote=None, posted="", description=""):
    return {
        "title": re.sub(r"\s+", " ", str(title or "")).strip(),
        "company": company,
        "location": re.sub(r"\s+", " ", str(location or "")).strip(),
        "remote": looks_remote(location, title) if remote is None else bool(remote),
        "url": url or "",
        "source": source,
        "posted": str(posted or "")[:10],
        "description": strip_html(description)[:4000],
    }


def company_from_slug(slug):
    return re.sub(r"[-_]+", " ", slug).strip().title()
