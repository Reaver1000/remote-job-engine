---
name: remote-job-hunt
description: >-
  An onboarding-first job-hunt copilot for anyone. It learns where the user lives and what
  they want from a short chat plus their pasted LinkedIn, finds fresh remote/role-matched
  postings fast via job APIs and ATS feeds (not LinkedIn scraping), and builds a per-job
  "module" for each opening containing a CV tailored to that exact posting, a cover letter,
  and an application checklist. Use whenever the user wants to set up a job search, discover
  or monitor postings, screen/score roles for fit, tailor a CV or cover letter to a specific
  job, or maintain an application tracker. Trigger even if they just say "find me jobs",
  "help me apply", "tailor my CV to this role", "is this posting a fit?", or paste a LinkedIn
  profile / job description. Location and filters are user-supplied — never assume a region.
---

# Remote Job Hunt

A reusable, shareable job-hunt copilot (designed to be open-sourced). It does four things:

1. **Onboards the user** — learns where they live and can legally work, ingests their pasted
   LinkedIn, and chats with them about their hopes and constraints. Output: a `profile.yaml`,
   a `base_cv.md`, and a machine `config.json`.
2. **Finds jobs fast** — a scheduled, no-LLM script polls job APIs + company ATS feeds and
   surfaces new matches within minutes. Filters are driven by the user's config.
3. **Builds a module per job** — each promising opening becomes its own folder with a CV
   **tailored to that posting**, a cover letter, and an application checklist.
4. **Queues for a human confirm** before anything is submitted.

No region is hardcoded. Everything specific to a person lives in their `profile.yaml` /
`config.json`, generated during onboarding — so the same skill works for any user, anywhere.

Pointers: discovery design → `references/job_sources.md`; the poller → `scripts/poll_jobs.py`;
example config → `assets/config.example.json`; prompts → `references/prompts.md`; operating
guide + model rationale → `references/runbook.md`; tracker → `assets/tracker_template.csv`.

---

## First run: onboarding (do this before anything else)

If `profile/profile.yaml` doesn't exist yet, run onboarding (Prompt A). It is a friendly
conversation, not a form. Cover, in plain language:

1. **Where they live + work authorization** — country/city, and where they may legally work
   (citizenship/visa, willingness to use an Employer of Record or contract). This sets the
   *eligibility* logic — there are no built-in region rules.
2. **Their LinkedIn** — ask them to paste it. Parse it into `base_cv.md` (the canonical CV
   used for tailoring) and pull skills/experience into the profile.
3. **Their hopes** — what they actually want: role types, domains, what a good day looks like,
   what to avoid, seniority, comp range, notice period, languages, hours/time-zone
   flexibility, and any work-style needs or accommodations they choose to share.

Then synthesize and write `profile/profile.yaml`, `profile/base_cv.md`, and `config.json`
(from `assets/config.example.json`). Confirm the summary back to the user before searching.

### profile.yaml schema

```yaml
name:
location:              # where they live
work_authorization:    # where they can legally work; visa/EoR notes
languages:             # e.g. {english: fluent, german: B1}
target_roles:          # list, in priority order
seniority:             # intern | entry | junior | mid | senior | ...
must_haves:            # e.g. fully remote, no relocation
dealbreakers:          # e.g. heavy phone, required onsite, languages they lack
nice_to_haves:         # e.g. async, specific domains, inclusive employers
work_style_needs:      # optional, user-volunteered (e.g. written/async, structured tasks)
hard_skills:           # for CV tailoring + keyword matching
strengths:             # short narrative points
comp_range:            # optional
notice_period:         # optional
links:                 # portfolio, github, etc.
base_cv: profile/base_cv.md
```

---

## Search criteria (all derived from the profile — nothing hardcoded)

- **Eligibility:** keep roles workable from the user's `location`/`work_authorization`.
  By default the poller imposes **no region restriction** (`acceptable_locations: []`); add
  blocks only if the user says they can't work somewhere.
- **Role match:** title matches the user's `target_roles` / `config.role_keywords`.
- **Seniority:** exclude levels above the user's target (`config.exclude_titles`).
- **Language:** reject roles requiring a language above the user's stated level.
- **Phone:** reject phone-heavy roles if the user flagged that as a dealbreaker.
- **Boosters (raise fit score):** async / any-time-zone, written-first culture, structured
  onboarding, inclusive employers, and anything in the user's `nice_to_haves`.

---

## Discovery layer — find jobs within minutes

Two tiers, both config-driven (full catalog: `references/job_sources.md`):

**Tier 1 — Company ATS feeds (SPEED, minutes latency), no auth, poll every ~10–15 min:**
- Greenhouse: `https://boards-api.greenhouse.io/v1/boards/{token}/jobs`
- Lever: `https://api.lever.co/v0/postings/{company}?mode=json`
- Ashby: `https://api.ashbyhq.com/posting-api/job-board/{org}?includeCompensation=true`

**Tier 2 — Aggregator APIs (BREADTH, hourly/daily):**
- Arbeitnow (no key): `https://www.arbeitnow.com/api/job-board-api`
- RemoteOK (no key, attribution required): `https://remoteok.com/api`
- Remotive (no key, rate-limited): `https://remotive.com/api/remote-jobs?category=data`
- Adzuna (free key; country code from `config.adzuna_country`): `https://api.adzuna.com/v1/api/jobs/{country}/search/1?...`

Aggregators refresh slowly; the ATS watchlist is what delivers minutes-level freshness.
`scripts/poll_jobs.py` reads `config.json`, polls both tiers, dedupes against
`state/seen_ids.json`, filters to the user's criteria, and writes `state/new_matches.csv`.

---

## Per-job modules (CV tailored to each posting)

Every promising role gets its own folder so its CV can be tailored to that exact job:

```
jobs/<date>_<company>_<role-slug>_<id>/
├── job.json          # posting + extracted fields + source URL
├── fit.json          # fit score, tier, reasons, concerns
├── cv.md             # CV tailored to THIS posting (from profile/base_cv.md)
├── cover_letter.md   # tailored cover letter
└── application.md    # common-question answers + status + submit checklist
```

Tailoring rules (Prompt F): start from `profile/base_cv.md`, reorder and re-emphasize the
experience, skills, and keywords this posting asks for, mirror the job's terminology for ATS
matching, and trim what's irrelevant — **without inventing anything**. Genuine gaps are marked
`[BRACKETS]` for the user. The base CV stays the single source of truth; each module is a view
of it aimed at one job.

---

## Model routing (run cheap where you can)

| Step | Task | Model tier |
|------|------|-----------|
| Onboard (synthesize profile/CV/config) | judgment + writing | **Mid** (Sonnet-class) |
| Build/refresh watchlist | judgment | **Mid**, occasional |
| Discover (poll, dedupe, filter) | deterministic | **No LLM — script** |
| Extract/enrich, pre-filter, assemble | rules | **Cheap** (Haiku-class) |
| Fit-score + automatability | judgment | **Mid** |
| Tailor CV + cover letter | judgment + writing | **Mid** |

You do **not** need a frontier/"max" model to run this — reserve it for evolving the skill.
Rationale in `references/runbook.md`.

---

## Workflow

Prompts are named A–H in `references/prompts.md`.

- **A. Onboard** (mid, first run) → `profile.yaml`, `base_cv.md`, `config.json`.
- **B. Watchlist** (mid, periodic) → company ATS tokens into `config.json`.
- **Discover** (script, scheduled) → `state/new_matches.csv`. No LLM.
- **C. Extract** (cheap) → structured fields for any sparse posting.
- **D. Pre-filter** (cheap) → drop dealbreakers.
- **E. Fit-score + automatability** (mid) → fit + auto_score + combined (weighted to
  automatability) + an `automation_plan`; tier by combined.
- **F. Tailor CV** (mid) → `cv.md` per job module.
- **G. Cover letter + answers** (mid) → `cover_letter.md`, `application.md`.
- **H. Assemble module + queue** (cheap) → tracker row, status `ready_to_submit`. **Stop.**

---

## The submit gate (the one rule that doesn't bend)

Prepare everything, then let the user confirm before anything is sent:

- **Platform terms:** automated submission (incl. LinkedIn "Easy Apply") breaks most job-board
  terms and risks an account ban. Use LinkedIn for discovery only; apply on company sites.
- **Reputation is irreversible:** every application goes out under the user's real name; a bad
  auto-filled field or generic letter can't be unsent, and ATS/recruiters flag bot applies.
- **The gate is cheap:** confirming a batch takes seconds and still removes ~95% of the effort.

Set modules to `ready_to_submit`, show a compact batch (company, role, fit, link, tailored-CV
+ letter), and submit only after an explicit human "submit". Hand CAPTCHAs/logins/assessments
to the user. If a user insists on lights-out auto-submit, decline that and offer the
confirm-batch flow instead.

---

## Output

- `profile/` (profile.yaml, base_cv.md) and `config.json` — the user's setup.
- `state/new_matches.csv` — fresh discoveries each poll.
- `jobs/<module>/` — one folder per role with a tailored CV, cover letter, and checklist.
- `tracker.csv` (from `assets/tracker_template.csv`) — pipeline status across all roles.
