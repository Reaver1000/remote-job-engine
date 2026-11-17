# Changelog

All notable changes to remote-job-engine. Dates are ISO.

## v1.1.0 — 2026-11-17

The discovery layer is no longer a black box. v1.0 polled three ATS feeds through a borrowed
adapter. v1.1.0 replaces that with eight provider plugins we own, a 438 board watchlist, a
worldwide scan, and a 14 step daily runner.

### Added

- **ATS plugin layer.** One Python module per provider in `pipeline/ats/`, each exposing
  `fetch(slug)` and returning a normalised job dict. Providers: Greenhouse, Lever, Ashby,
  Workable, SmartRecruiters, Recruitee, BambooHR, Personio.
- **`pipeline/boards.json`.** 438 seeded boards across eight providers. Adding a company is one
  line. A dead slug fails quietly.
- **`pipeline/ats_scan.py`.** Threaded scan, 16 workers, dedupes by URL, writes `ats_jobs.md` in
  the same schema as the board sweeps so the ranker needs no special case.
- **`pipeline/daily.py`.** Fourteen step runner with per-step timeouts. A failing step is logged
  and skipped, so one broken scraper cannot stall the run.
- **UK remote lane.** `uk_linkedin_scan.py` runs ten queries against the LinkedIn guest API and
  returns about 155 unique roles per pass. `uk_remote_scan.py` scans UK and Ireland boards.
- **Retirement path for the local OpenPostings app.** The adapter first consumed its API, then
  was removed once the plugin layer proved it could replace it.

### Changed

- **Ranking input.** `broad_rank.py` now ingests `ats_jobs.md` alongside the board sweeps.
- **Location matching.** A bare "remote" no longer counts as an eligible location. A posting
  needs a strict, non-generic place before the mixed-location override applies.
- **README structure.** Discovery, pipeline and app are documented as separate layers.

### Fixed

- **US-only roles leaked into the shortlist.** "Remote - US" passed because the token `remote`
  was treated as an eligible location. Tightened, and the shortlist dropped from 2,359 to 1,885
  roles.
- **US cities were absent from the block list.** Added the twenty largest hiring markets.
- **Hybrid counted as remote.** Ashby reports `isRemote` true on hybrid postings, so the UK scan
  was over-reporting remote roles. It now requires `workplaceType == "Remote"`.
- **Hardcoded working directory.** `scored_queue.py` no longer points at one machine's folder.

### Removed

- **OpenPostings dependency.** Its 89 providers were the reason to look, but its index held 70
  remote postings and carried no description or pay. The local scans return 14,108 roles.
- **Personal data from the public repo.** No ledgers, CVs, application folders, logs or candidate
  details. Runtime state is gitignored.

### Numbers

| Metric | v1.0 | v1.1.0 |
|---|---|---|
| ATS providers | 3 (Greenhouse, Lever, Ashby) | 8 |
| Boards watched | 3 feed types | 438 |
| Roles per ATS scan | not measured | 14,108 |
| ATS scan runtime | not measured | 24 s |
| Daily pipeline steps | poll only | 14 |
| UK remote lane | none | 2 scripts, ~155 roles per pass |
| Ranked shortlist | not measured | 1,885 roles |
| ATS rows in shortlist | — | 143 |

### Upgrade notes

- `boards.json` ships seeded. Prune slugs that 404 if scan time matters.
- `pipeline/` expects the same Python version as the rest of the repo, standard library only.
- The `app/` dashboard is unchanged and still reads its own state.
