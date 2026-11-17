"""Personio public XML feed. No key required."""

import xml.etree.ElementTree as ET
from urllib.parse import quote

from .base import get, job


def fetch(slug):
    raw = get(f"https://{quote(slug)}.jobs.personio.de/xml?language=en")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return []
    out = []
    for pos in root.iter("position"):
        def text(tag):
            el = pos.find(tag)
            return el.text.strip() if el is not None and el.text else ""

        offices = [o.text.strip() for o in pos.findall("office") if o.text]
        pid = text("id")
        out.append(
            job(
                title=text("name"),
                company=slug,
                location=", ".join(offices),
                url=f"https://{slug}.jobs.personio.de/job/{pid}" if pid else f"https://{slug}.jobs.personio.de/",
                source=f"ats:personio:{slug}",
                posted=str(text("createdAt"))[:10],
                description=" ".join(
                    t.text for t in pos.iter() if t.tag in ("jobDescription", "requirements", "yourTasks") and t.text
                ),
            )
        )
    return out
