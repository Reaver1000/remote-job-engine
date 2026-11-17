# v1.1.0 — the ATS plugin layer

v1.0 polled three ATS feeds through a borrowed adapter and scored what came back. v1.1.0 replaces
the discovery layer with eight provider plugins we own, a 438 board watchlist, a worldwide scan,
and a 14 step daily runner.

## Added

- **Eight ATS provider plugins** in `pipeline/ats/`, each a small module exposing `fetch(slug)`:
  Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Recruitee, BambooHR, Personio.
- **`boards.json`** with 438 seeded boards. Adding a company is one line. Dead slugs fail quietly.
- **`ats_scan.py`**, a threaded driver that dedupes by URL and writes the same markdown schema as
  the board sweeps, so the ranker needs no special case.
- **`daily.py`**, a 14 step runner with per-step timeouts. A failing step is logged and skipped.
- **UK remote lane.** Ten LinkedIn queries returning about 155 unique roles per pass, plus a UK
  and Ireland ATS scan.

## Changed

- `broad_rank.py` ingests `ats_jobs.md` with no special casing.
- A bare "remote" no longer counts as an eligible location.

## Fixed

- US-only roles leaked into the shortlist through the token `remote`. The shortlist fell from
  2,359 to 1,885 roles after tightening.
- US hiring cities were missing from the block list. Twenty added.
- Hybrid postings were counted as remote on Ashby. The scan now requires
  `workplaceType == "Remote"`.
- A hardcoded working directory was removed from `scored_queue.py`.

## Removed

- The local OpenPostings dependency. Its index held 70 remote postings with no descriptions or
  pay. The local scans return 14,108 roles in 24 seconds.

## By the numbers

| Metric | v1.0 | v1.1.0 |
|---|---|---|
| ATS providers | 3 | 8 |
| Boards watched | 3 feed types | 438 |
| Roles per ATS scan | not measured | 14,108 |
| ATS scan runtime | not measured | 24 s |
| Daily pipeline steps | poll only | 14 |
| UK remote lane | none | 2 scripts, ~155 roles per pass |
| Ranked shortlist | not measured | 1,885 roles |

Full details in `CHANGELOG.md`.
