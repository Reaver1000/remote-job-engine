# remote-job-engine

A personal job-hunt machine that optimises for **money per hour of your time**: it finds fresh
remote roles fast (free), scores each for fit **and automatability + pay**, routes them into
**Stack** (automate & run several) vs **Premium** (one well-paid role, done manually), tailors a
CV per posting, and applies — auto for Stack, review-first for Premium.

## Parts
- **skill/** — the discovery engine + prompts (the `remote-job-hunt` Claude skill). The poller
  (`skill/scripts/poll_jobs.py`) polls company ATS feeds (Greenhouse/Lever/Ashby) and aggregator
  APIs, dedupes, and writes `skill/state/new_matches.csv`. Zero LLM tokens.
- **app/** — the FastAPI dashboard: scores + routes jobs, auto-tailors CVs, and handles applying
  (auto-apply for Stack, assisted for Premium) + pipeline tracking.
- **profile/** — your `config.json` (targets + ATS watchlist) and `base_cv.md` (source of truth).
- **.github/workflows/poll.yml** — runs the poller on a schedule (GitHub has real internet).

## Quick start
```bash
./setup.sh                                   # puts your profile where the skill + app read it
python skill/scripts/poll_jobs.py            # discover (schedule this every ~15 min)
cd app && pip install -r requirements.txt
uvicorn app:app --reload                      # http://localhost:8000  ->  Refresh & score
```

## Make scoring + tailoring real (optional but recommended)
```bash
export ANTHROPIC_API_KEY=sk-...               # or OPENAI_API_KEY + JOBHUNT_LLM=openai
```
Without a key it uses a transparent offline heuristic (conservative, but runs).

## Auto-apply (Stack lane only) — off by default
```bash
export AUTOAPPLY_ENABLED=1      # arm it (still dry-run)
# review the dry-run batch in the dashboard, then:
export AUTOAPPLY_DRY_RUN=0      # actually submit
export AUTOAPPLY_DAILY_CAP=10   # stay under spam-flag thresholds
pip install playwright && playwright install chromium
```
It parks anything with a CAPTCHA, login, or required custom question; never fabricates answers;
logs to `app/state/autoapply_log.csv`. **Premium roles are always review-before-submit.**

## Honest limits
- "Apply" to arbitrary sites is browser automation per ATS (Greenhouse done; Lever/Ashby
  best-effort) — test in dry-run on a couple of real postings before trusting LIVE mode.
- Stacking several roles is cleanest with **freelance/contract/part-time**; full-time contracts
  often have exclusivity clauses. Right-to-work from Germany still depends on the employer.
- Pay/€-time figures are estimates until you add an API key and/or postings include comp.

See `skill/references/runbook.md` and `app/README.md` for detail. `SHORTLIST.md` has a starter
set of real openings (as of 2026-06-25).
