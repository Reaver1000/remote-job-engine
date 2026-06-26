# Runbook — operating the job hunt

How to run it, how to get minutes-level freshness, how to ship it on GitHub, and the answer
to "cheap model or max settings?"

## Cheap model or max settings? (the direct answer)

You do **not** need max settings to RUN this. Spend the expensive model once — on designing
and revising the skill — then run it cheap.

- **No LLM at all** — discovery (`scripts/poll_jobs.py`). Just HTTP + filtering. Free and
  instant; this is the "find within minutes" part and needs no model.
- **Cheap / fast model (Haiku-class)** — extract/enrich, pre-filter, assemble modules.
- **Mid model (Sonnet-class)** — onboarding synthesis, fit-scoring, CV tailoring, cover
  letters, occasional watchlist builds. These need judgment and carry the user's reputation.
- **Frontier model (Opus-class)** — not needed to run; use it to evolve the skill itself.

Names at time of writing: Haiku 4.5 (cheap), Sonnet 4.6 (mid), Opus 4.8 (frontier).
Rule of thumb: fixed format + clear rules → cheap; a human reads/judges it → mid.

## First run

Run onboarding (Prompt A): capture where the user lives + can work, ingest their pasted
LinkedIn into `profile/base_cv.md`, and chat through their hopes/constraints. It writes
`profile/profile.yaml` and `config.json`. Nothing about a region is assumed — eligibility
comes entirely from what the user tells you.

## Getting "within minutes" freshness

1. Build the watchlist (Prompt B); paste tokens into `config.json`
   (`greenhouse_boards`/`lever_boards`/`ashby_boards`). The watchlist is the speed engine —
   ATS boards reflect a new posting the instant it's published.
2. Schedule `poll_jobs.py` every ~10–15 min. Each run only surfaces new postings (dedupes via
   `state/seen_ids.json`) into `state/new_matches.csv`.
3. Optional breadth: set `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` env vars and `config.adzuna_country`.

Ask to wire this as a recurring scheduled task ("poll every 15 min and message me on a strong
match") so you only ever see fresh, pre-qualified roles.

## Daily flow

1. Poller fills `state/new_matches.csv`.
2. On new rows: (cheap) extract/pre-filter where needed → (mid) fit-score.
3. For `strong`/chosen `maybe`: (mid) tailor the CV (Prompt F) and write the cover letter
   (Prompt G) → a per-job module under `jobs/`.
4. (cheap) assemble the module + tracker row; review the batch.
5. Confirm; submit yourself on the company site (or let the assistant fill + pause for your OK).

Quality over volume — a handful of genuinely-fresh, CV-tailored applications beat mass-spam,
and they don't risk your accounts or your name.

## Per-job modules

Each role lives in `jobs/<date>_<company>_<role-slug>_<id>/` with `job.json`, `fit.json`,
`cv.md` (tailored to that posting), `cover_letter.md`, and `application.md`. `profile/base_cv.md`
stays the single source of truth; each module is a view of it aimed at one job. Tailoring only
ever reorders/re-emphasizes real content — gaps are marked `[BRACKETS]` for the user.

## Shipping it on GitHub

- Commit: `SKILL.md`, `references/`, `scripts/`, `assets/` (incl. `config.example.json`).
- Do **not** commit personal data. Add a `.gitignore` with:
  `config.json`, `profile/`, `jobs/`, `state/`
- Users clone, run onboarding (which generates their own `config.json` + `profile/`), and go.
- Keep source terms intact in the README (RemoteOK attribution; Remotive rate limit;
  LinkedIn = discovery only).

## Legal / practical

- **Eligibility** depends entirely on the user's country + work authorization. "Remote" still
  needs an employer able to engage someone where the user lives (local entity, Employer of
  Record, or contractor invoicing). The poller flags only what the user chose to block.
- **LinkedIn = discovery only.** Automated activity (incl. Easy Apply) breaks its terms.
- **Source terms.** RemoteOK requires attribution + direct link back; Remotive is rate-limited.
- Tax/registration for contracting varies by country — suggest the user check locally.
  (Informational, not legal advice.)

## Why the submit gate stays

Fully automated, no-review submission breaks job-board terms (account-ban risk) and sends
irreversible applications under the user's name. The confirm-batch flow keeps nearly all the
speed while keeping the user in control of what's sent.
