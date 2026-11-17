"""ATS scan: one plugin per provider, driven by boards.json.

    python ats_scan.py                        # every board in boards.json
    python ats_scan.py --providers greenhouse,ashby
    python ats_scan.py --board greenhouse:canonical --verbose
    python ats_scan.py --limit-per-board 200

Writes ats_jobs.md in the same markdown schema as the board sweeps, so
broad_rank.py can rank it without special casing.

No personal data is read or written. The scan is worldwide by design; region
filtering happens later in the ranker.
"""

import argparse
import json
import re
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

from ats.registry import PROVIDERS, get

BOARDS = "boards.json"
OUT = "ats_jobs.md"


def load_boards():
    with open(BOARDS, encoding="utf-8") as f:
        raw = json.load(f)
    boards = []
    for provider, slugs in raw.items():
        if provider.startswith("_"):
            continue
        if provider not in PROVIDERS:
            print(f"  skipping unknown provider {provider}")
            continue
        for slug in dict.fromkeys(slugs):
            boards.append((provider, slug))
    return boards


def scan_one(provider, slug, limit):
    mod = get(provider)
    try:
        rows = mod.fetch(slug)
    except Exception as exc:
        return provider, slug, [], str(exc)[:120]
    if limit and len(rows) > limit:
        rows = rows[:limit]
    return provider, slug, rows, ""


def write_md(rows, path):
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# ATS SCAN - {time.strftime('%Y-%m-%d')}\n\n")
        f.write(f"{len(rows)} roles across {len(set(r['source'] for r in rows))} boards.\n\n")
        for r in rows:
            f.write(f"### {r['title']} @ {r['company']}\n")
            f.write(f"- loc: {r['location']}\n")
            f.write(f"- src: {r['source']}\n")
            if r["posted"]:
                f.write(f"- posted: {r['posted']}\n")
            f.write(f"- url: {r['url']}\n\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--providers", default="", help="comma separated subset")
    ap.add_argument("--board", default="", help="single provider:slug")
    ap.add_argument("--limit-per-board", type=int, default=0)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    boards = load_boards()
    if args.providers:
        keep = {p.strip() for p in args.providers.split(",") if p.strip()}
        boards = [b for b in boards if b[0] in keep]
    if args.board:
        provider, _, slug = args.board.partition(":")
        boards = [(provider, slug)]

    if not boards:
        raise SystemExit("No boards selected.")

    print(f"scanning {len(boards)} boards with {args.workers} workers")
    rows, failures, per_provider = [], [], Counter()
    started = time.time()

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {
            ex.submit(scan_one, p, s, args.limit_per_board): (p, s) for p, s in boards
        }
        for i, fut in enumerate(as_completed(futures), 1):
            provider, slug, jobs, err = fut.result()
            if err:
                failures.append((provider, slug, err))
                if args.verbose:
                    print(f"  {provider}:{slug} failed - {err}")
            elif jobs:
                rows.extend(jobs)
                per_provider[provider] += len(jobs)
                if args.verbose:
                    print(f"  {provider}:{slug} {len(jobs)} roles")
            if i % 50 == 0:
                print(f"  {i}/{len(boards)} boards, {len(rows)} roles")

    # dedupe by url
    seen, unique = set(), []
    for r in rows:
        key = re.sub(r"[?#].*$", "", r["url"]).rstrip("/").lower()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(r)

    write_md(unique, args.out)
    elapsed = time.time() - started

    print(f"\n{len(unique)} unique roles from {len(boards)} boards in {elapsed:.0f}s")
    print(f"written to {args.out}")
    for p, n in per_provider.most_common():
        print(f"  {p:16} {n}")
    if failures:
        print(f"  {len(failures)} boards failed (404 or timeout)")


if __name__ == "__main__":
    main()
