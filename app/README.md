# Job-Hunt Dashboard

A local web app that watches for matching jobs, auto-tailors a CV for strong matches, and
gives you a one-click (assisted) apply — with email-based pipeline tracking. Companion to the
`remote-job-hunt` skill (it reads that poller's output).

## What it does
- **Refresh & score** — ingests new postings (from the poller's `state/new_matches.csv`, or
  seeds samples on first run), scores each 0–100, and **auto-tailors a CV for anything ≥ 70**.
- **Two strategies (goal = €/time):**
  - **♻ Stack & automate:** automatable + stackable roles, ranked by effective €/time — run several in parallel (VA / contract / part-time friendly).
  - **💰 Premium:** roles that pay enough to be worth doing manually — one big role.
  - Strong matches auto-tailor a CV (Apply enabled); others show **Generate CV**, which then ungreys **Apply**.
  - Note: stacking several roles is cleanest with freelance/contract/part-time; full-time contracts often have exclusivity clauses.
- **Apply (assisted):** opens the posting and serves your tailored CV + cover letter so you do
  the final submit. (Reliable, ToS-safe — see "Why assisted".)
- **Pipeline:** mark/track `applied → advanced / rejected`. Email can populate this read-only.

## Run it
```bash
pip install -r requirements.txt
# optional — turns on real AI scoring + CV tailoring (otherwise an offline heuristic is used):
export ANTHROPIC_API_KEY=sk-...        # or OPENAI_API_KEY + JOBHUNT_LLM=openai
uvicorn app:app --reload               # open http://localhost:8000
```

## Data it uses
- `data/config.json` — role keywords / filters (seeded from your `remote-job-hunt` config).
- `data/base_cv.md` — your base CV, the source of truth for tailoring (seeded from onboarding).
- `jobs/<id>/cv.md`, `cover_letter.md` — generated per job.
- `jobhunt.db` — SQLite state (set `JOBHUNT_DB` to relocate).

## How it connects to discovery
Point it at the `remote-job-hunt` poller: it auto-reads `../remote-job-hunt/state/new_matches.csv`.
Run the poller on a schedule (the included GitHub Action), then hit **Refresh** here — or add a
cron call to `/api/refresh`.

## Apply behaviour (per route)
- **Premium = manual / assisted.** These are your main, high-stakes targets. Clicking **Apply
  (review)** opens the posting with your tailored CV + cover letter so you submit yourself.
- **Stack = auto-apply.** High-volume, low-stakes. **⚡ Auto-apply** (per card) or **Auto-apply
  all** generates the CV and applies via browser automation. Guardrails (deliberate):
  - **OFF by default.** Arm with `AUTOAPPLY_ENABLED=1`.
  - **Dry-run by default** (fills, does NOT submit) until `AUTOAPPLY_DRY_RUN=0`. Review the
    first batch before going live.
  - **Daily cap** `AUTOAPPLY_DAILY_CAP` (default 10) so you aren't flagged as a bulk spammer.
  - **Safe stops:** CAPTCHA, login/account walls, or required custom questions it can't answer
    truthfully from your profile are **parked** for you — never guessed. No fabricated answers.
  - Every attempt is logged to `state/autoapply_log.csv`. The header chip shows OFF / DRY-RUN /
    LIVE and today's count vs. cap.
- Real submission uses Playwright (`pip install playwright && playwright install chromium`).
  Greenhouse is implemented as the worked example; Lever/Ashby follow the same pattern (selectors
  marked TODO in `autoapply.py`) — tune against live forms before trusting LIVE mode.

Recommended first run: `AUTOAPPLY_ENABLED=1` (leave dry-run on), hit **Auto-apply all**, read
the parked/filled results, then set `AUTOAPPLY_DRY_RUN=0` with a low cap.

## Email tracking (read-only, never deletes)
`/api/sync_email` is implemented in `email_sync.py` (IMAP). Enable it by setting `GMAIL_USER` and `GMAIL_APP_PASSWORD` (a Gmail App Password: Google Account > Security > App passwords). It searches your inbox for each applied company, classifies the latest message as rejected/advanced (LLM if a key is set, else keywords), and tags the pipeline. It never deletes — rejected rows show an Open in Gmail link so you delete them yourself.

## Files
- `app.py` — FastAPI backend + single-page dashboard (inline HTML/JS).
- `engine.py` — scoring + CV/cover tailoring (Claude or OpenAI when a key is set; offline fallback).
- `store.py` — SQLite persistence.
- `data/` — your config + base CV.  `jobs/` — generated per-job modules.

## Roadmap
- Live Gmail sync + auto-classification into the pipeline.
- Playwright assisted form-fill per ATS (Greenhouse/Lever/Ashby) with pause-to-confirm.
- Auth + multi-user, so it can be hosted (fits the open-source plan).
