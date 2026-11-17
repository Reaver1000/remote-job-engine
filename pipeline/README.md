# Daily pipeline

The sweep engine behind the dashboard. Nineteen scripts, fourteen scheduled steps, run by
`daily.py`. Everything here is source code only. Runtime state, ledgers and CVs are gitignored.

## Run

```bash
python daily.py             # full run, 14 steps, roughly 25 minutes
python daily.py --quick     # board scans only, about 2 minutes
python daily.py --dry-run   # print the step list without running anything
```

Single lanes:

```bash
python job_sweep.py
python linkedin_sweep.py
python uk_linkedin_scan.py
python uk_remote_scan.py --days 30
python broad_rank.py --all
```

## What runs

| Step | Script | Source |
|---|---|---|
| 0 | `ats_scan.py` | 438 ATS boards across eight provider plugins |
| 1 | `job_sweep.py` | Aggregators and ATS feeds, wide pull then eliminate |
| 2 | `linkedin_sweep.py` | LinkedIn guest API, 50+ query terms, remote filter, 7 day window |
| 3 | `indeed_sweep.py` | Indeed |
| 4 | `stepstone_sweep.py` | Stepstone |
| 5 | `ba_sweep.py` | Bundesagentur fuer Arbeit |
| 6 | `glassdoor_sweep.py` | Glassdoor |
| 7 | `corporate_sweep.py` | Named corporate careers pages |
| 8 | `fintech_sweep.py` | Fintech company boards, Greenhouse plus aggregators |
| 9 | `yc_sweep.py` | Y Combinator startup board |
| 10 | `emea_ashby_scan.py` | Ashby boards, EMEA |
| 11 | `lever_scan.py` | Lever boards |
| 12 | `remote_first_scan.py` | Remote-first company list |
| 13 | `remote_first_scan_gh.py` | Remote-first Greenhouse boards |
| 14 | `scored_queue.py` | Prints the scored apply queue |

Additional lanes: `fresh24.py` for a 24 hour recency pass, `uk_linkedin_scan.py` for the UK
remote lane, `uk_remote_scan.py` for UK and Ireland roles verified against employer ATS data,
and `status.py` for a pipeline summary.

## Elimination, not keyword guessing

`job_sweep.py` pulls wide and then removes what the candidate cannot do. First failing check
wins.

1. `not_remote` — no remote signal anywhere in title, location or body
2. `region_blocked` — US-only or Americas-only, or requires work authorisation there
3. `seniority` — senior, lead, principal, staff, head, director, manager
4. `internship` — intern, praktikum, werkstudent
5. `alien_stack` — title demands a stack the candidate does not have
6. `licensed_job` — nurse, lawyer, accountant, electrician and similar
7. `german_c1` — posting demands fluent or C1 German
8. `posting_language` — body is in a language the candidate does not work in
9. `hybrid_disguised` — says remote, body reveals mandatory office days
10. `low_pay` — quoted pay below the configured floor
11. `irrelevant_field` — clinical, legal, beauty, warehouse, driving, construction

Survivors are family tagged and written to `jobs_found.md`. Kills and reasons go to
`jobs_eliminated.md` so the rules can be audited.

## Ranking

`broad_rank.py` merges every source file, normalises fields, dedupes by URL, and scores by
role family, location eligibility, remote status, pay, seniority and recency. Output is
`broad_shortlist.md`.

## ATS plugin layer

`ats_scan.py` drives one Python module per provider. Each module exposes `fetch(slug)` and returns
a normalised job dict, so adding a provider is a single file plus an entry in the registry.

| Provider | Endpoint | Notes |
|---|---|---|
| Greenhouse | `boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true` | public, no key |
| Lever | `api.lever.co/v0/postings/{slug}?mode=json` | public, no key |
| Ashby | `api.ashbyhq.com/posting-api/job-board/{slug}` | public, `workplaceType` is honest about hybrid |
| Workable | `apply.workable.com/api/v1/widget/accounts/{slug}` | public widget feed |
| SmartRecruiters | `api.smartrecruiters.com/v1/companies/{slug}/postings` | public |
| Recruitee | `{slug}.recruitee.com/api/offers/` | public |
| BambooHR | `{slug}.bamboohr.com/careers/list` | public |
| Personio | `{slug}.jobs.personio.de/xml` | public XML feed |

`boards.json` holds one slug list per provider. The current seed is 438 boards, taken from the
curated lists already in `job_sweep.py` plus a few probed Workable, Recruitee, BambooHR and
Personio accounts. A dead slug fails quietly, so pruning is optional.

A full run of 438 boards takes about 25 seconds with 16 workers and returns roughly 14,000 roles.
That is the reason the local OpenPostings dependency was retired: same idea, more control, and
the scan is worldwide by design rather than filtered to one market.

## A note on remote filters
Job board remote filters overstate remote work. On a single day, roles flagged remote on
LinkedIn turned out to be hybrid or office based once the advert was read. Treat a role as
remote only when the employer's own ATS record says so (`workplaceType == "Remote"` on Ashby,
or the equivalent on Greenhouse). `uk_remote_scan.py` encodes that rule.

## Adapting it

Candidate-specific rules live in constants at the top of each script: `ELIGIBLE` city and
country lists, pay floors, kill words, and source lists. Change those before running for a
different market or a different candidate.

Runtime files are never committed: `applied.json`, `rejected.json`, `logs/`, `applications/`,
and the generated `*_jobs.md` snapshots.
