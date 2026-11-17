"""One-command orientation for this folder.

Prints the state a new session needs before touching anything. No network calls,
no writes. Run this first.

    python status.py
"""
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).parent

LEDGERS = {
    "applied.json": "applied",
    "rejected.json": "rejected",
    "closed_roles.json": "closed",
}
SWEEPS = [
    "jobs_found.md",
    "new_jobs.md",
    "linkedin_jobs.md",
    "indeed_jobs.md",
    "stepstone_jobs.md",
    "ba_new.md",
    "glassdoor_jobs.md",
    "emea_eligible.md",
]


def load(name, default):
    p = HERE / name
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def ledger_line():
    applied = load("applied.json", [])
    rejected = load("rejected.json", [])
    closed = load("closed_roles.json", [])
    pending = len(applied) - len(rejected)
    return (
        f"applied {len(applied)} | rejected {len(rejected)} | pending {pending} | closed {len(closed)}",
        applied,
        rejected,
    )


def sweep_line():
    out = []
    for name in SWEEPS:
        p = HERE / name
        if p.exists():
            age = (datetime.now() - datetime.fromtimestamp(p.stat().st_mtime)).days
            out.append(f"{name} ({age}d)")
    return "  ".join(out) if out else "no sweep output yet"


def top_new(limit=6):
    p = HERE / "new_jobs.md"
    if not p.exists():
        return []
    text = p.read_text(encoding="utf-8", errors="replace")
    blocks = re.findall(r"### (?:\[ \] )?(.+?)\s+\(score (\d+)\)\n(.*?)(?=\n\n|\Z)", text, re.S)
    rows = []
    for title, score, body in blocks:
        loc = re.search(r"- loc: (.+)", body)
        url = re.search(r"- url: (.+)", body)
        rows.append((int(score), title.strip(), (loc.group(1).strip() if loc else ""), (url.group(1).strip() if url else "")))
    rows.sort(reverse=True)
    return rows[:limit]


def recent_applications(days=7):
    base = HERE / "applications"
    if not base.exists():
        return []
    cutoff = datetime.now() - timedelta(days=days)
    rows = []
    for d in base.iterdir():
        if not d.is_dir():
            continue
        files = [f for f in d.iterdir() if f.is_file()]
        if not files:
            continue
        newest = max(f.stat().st_mtime for f in files)
        if datetime.fromtimestamp(newest) >= cutoff:
            rows.append((datetime.fromtimestamp(newest).strftime("%Y-%m-%d"), d.name))
    rows.sort(reverse=True)
    return rows


def main():
    counts, applied, rejected = ledger_line()
    print("JOB SEARCH STATUS", datetime.now().strftime("%Y-%m-%d %H:%M"))
    print(counts)
    print()
    print("SWEEP AGE")
    print("  " + sweep_line())
    print()
    rows = top_new()
    if rows:
        print("TOP NEW ROLES IN new_jobs.md")
        for score, title, loc, url in rows:
            print(f"  [{score}] {title[:62]} | {loc[:28]}")
            print(f"       {url}")
        print()
    recent = recent_applications()
    if recent:
        print("APPLICATION PACKAGES TOUCHED IN LAST 7 DAYS")
        for when, name in recent:
            print(f"  {when}  {name}")
        print()
    for name in ("followups_2026-10-28.md", "scheduled_actions.md"):
        if (HERE / name).exists():
            print(f"PENDING ACTION FILE  {name}")
    print()
    print("NEXT  python status.py, then read AGENT.md")


if __name__ == "__main__":
    main()
