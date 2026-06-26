# HANDOVER — remote-job-engine

Status: the system is built, runs end-to-end, and is unit-tested. This doc lists the few things
that need YOUR machine/accounts to go fully live, with exact steps. Point Claude Code at this file
(or do it yourself) to finish.

## What's done (works now)
- **Discovery** (`skill/`): `poll_jobs.py` polls Greenhouse/Lever/Ashby + Arbeitnow/RemoteOK/
  Remotive (Adzuna optional), dedupes, filters by `config.json`. Zero LLM tokens.
- **Dashboard** (`app/`): scores fit + automatability + pay, routes Stack vs Premium, ranks by
  €/time, auto-tailors CVs for strong matches, gates Apply on CV readiness, tracks a pipeline.
- **Apply**: Premium = assisted (open + review + submit). Stack = auto-apply via Playwright
  (`autoapply.py`) — OFF by default, dry-run first, daily cap, parks CAPTCHA/login/custom
  questions, never fabricates. Greenhouse + Ashby selectors verified against live forms; Lever
  uses the documented-standard selectors.
- **Email pipeline** (`app/email_sync.py`): IMAP read-only; tags applied jobs rejected/advanced;
  never deletes.
- Logic is unit-tested (scoring, routing, €/time, CV-gating, auto-apply safe paths, email classify).

## What needs you (and why it can't be done unattended)
1. **API key** — turns on real scoring + CV tailoring (otherwise an offline heuristic runs):
   `export ANTHROPIC_API_KEY=sk-...`  (or `OPENAI_API_KEY` + `JOBHUNT_LLM=openai`).
2. **Live auto-apply test** — needs your browser/accounts and human eyes on real forms:
   ```
   cd app && pip install -r requirements.txt && playwright install chromium
   export AUTOAPPLY_ENABLED=1        # stays dry-run
   # In autoapply.py temporarily set headless=False to watch it fill a real Stack posting.
   # Verify fields fill correctly on 2-3 Greenhouse/Lever/Ashby postings.
   export AUTOAPPLY_DRY_RUN=0 AUTOAPPLY_DAILY_CAP=5   # go live, low cap
   ```
   Submitting applications under your name is intentionally NOT automated end-to-end without your
   sign-off — keep the cap low to avoid bulk-application flags, and let it park anything unusual.
3. **Email sync** — set `GMAIL_USER` + `GMAIL_APP_PASSWORD` (Gmail App Password), then click
   "Sync email" in the dashboard.
4. **Profile brackets** — finish `profile/base_cv.md` / `profile.yaml`: work-permit line, notice
   period, comp range.
5. **Watchlist** — expand `profile/config.json` `greenhouse/lever/ashby_boards` (Prompt B in
   `skill/references/prompts.md`) to widen minutes-latency discovery.

## Run order
```
./setup.sh
python skill/scripts/poll_jobs.py          # or schedule via .github/workflows/poll.yml
cd app && pip install -r requirements.txt && uvicorn app:app --reload   # http://localhost:8000
```

## For Claude Code — concrete tasks
- [ ] Run the app, confirm Refresh populates lanes from real `skill/state/new_matches.csv`.
- [ ] Headful dry-run of `autoapply.apply_one` on one live Greenhouse, Lever, and Ashby posting;
      fix any selector drift in `app/autoapply.py` `_fill`/`_submit`.
- [ ] Implement SmartRecruiters/Workable `_fill` branches (same pattern) if those appear in results.
- [ ] Verify `email_sync.sync` against the real inbox; tune `REJECT`/`ADVANCE` keywords.
- [ ] Optional: swap IMAP for Gmail OAuth; add a Slack/desktop notification on new strong matches.

## Boundaries (keep these)
- Never mass-submit without review; keep the daily cap modest.
- Never auto-delete email. LinkedIn = discovery only (automation breaks its terms).
- Auto-apply only the Stack lane; Premium is always human-reviewed.
