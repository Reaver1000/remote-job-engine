# Prompts (A–H)

Copy-paste prompts written so a cheaper model needs little judgment: explicit rules, fixed
output formats. Replace `{{PROFILE}}`, `{{BASE_CV_MD}}`, `{{JOB_JSON}}` with real values.
Onboarding (A), fit-score (E), CV tailoring (F), and cover letters (G) run best on a mid-tier
model. **Discovery is the script `scripts/poll_jobs.py`, not a prompt.**

---

## Prompt A — Onboarding interview (mid-tier, first run)

```
You are onboarding a new user to their job hunt. Be warm and brief — this is a chat, not a
form. Ask a few things at a time. Goal: produce profile/profile.yaml, profile/base_cv.md,
and config.json. Never assume a country or region.

Cover, conversationally:
1. Where do you live, and where can you legally work? (citizenship/visa; open to an
   Employer-of-Record or contracting?) This sets eligibility.
2. Paste your LinkedIn (About, Experience, Skills, Education). I'll turn it into your CV.
3. What are you hoping for? Role types and domains; what a good workday looks like; what to
   avoid; seniority; comp range; notice period; languages + levels; hours/time-zone
   flexibility; any work-style needs or accommodations you'd like factored in (optional).

Then:
- Write profile/base_cv.md from the pasted LinkedIn — clean, structured, truthful, no inventing.
- Write profile/profile.yaml using the schema in SKILL.md.
- Write config.json from assets/config.example.json: role_keywords from target_roles;
  acceptable_locations ONLY if they want to restrict (else leave []); block_locations for
  places they can't work; adzuna_country = their country code if applicable.
- Summarize what you captured; ask them to confirm or correct before searching.
```

---

## Prompt B — Build / expand the company watchlist (mid-tier, occasional)

```
Build a watchlist of companies to monitor for fast discovery. Find companies that:
- hire where the user can work (per profile.yaml location/work_authorization),
- regularly post the user's target roles,
- use a PUBLIC, pollable ATS (Greenhouse, Lever, Ashby, SmartRecruiters).

Confirm the ATS from the careers/apply-link domain:
  boards.greenhouse.io/<token> -> greenhouse | jobs.lever.co/<co> -> lever
  jobs.ashbyhq.com/<org> -> ashby | *.smartrecruiters.com -> smartrecruiters

OUTPUT 1 — JSON: [{"company","ats","token","careers_url","why_fit"}]
OUTPUT 2 — ready-to-paste config.json arrays: greenhouse_boards / lever_boards / ashby_boards.
Start with 20–50; expand over time.
```

---

## Prompt C — Extract structured fields (cheap)

Use for sparse postings (e.g. HN comments). Most API/ATS results arrive already structured.

```
Extract facts from ONE posting into JSON. Infer only what the text supports; else null.

POSTING: {{RAW_POSTING_TEXT_OR_URL}}

OUTPUT (JSON only):
{
  "title","company","url",
  "location_policy":"remote|remote-region-locked|hybrid|onsite|unclear",
  "regions_allowed":"e.g. 'EU','US only','worldwide',null",
  "eligible_for_user":"yes|no|unclear",   // vs profile location/work_authorization
  "phone_load":"none|occasional|heavy|unclear",
  "language_required":"e.g. 'German C1', null",
  "seniority":"intern|entry|junior|mid|senior|lead|unclear",
  "role_family":"data|analytics-engineering|data-science|ai-eval|support|other",
  "comp_range":"text or null",
  "key_requirements":["bullets"],
  "notable_perks_or_culture":["async","inclusive","structured onboarding",...]
}
```

---

## Prompt D — Pre-filter against dealbreakers (cheap)

```
KEEP or REJECT one role using its fields + the user's profile. Pure rule-application.

PROFILE (dealbreakers, languages, work_authorization, seniority): {{PROFILE}}
ROLE: {{ROLE_JSON}}

Reject if: not eligible for the user's location/authorization; a profile dealbreaker is
present (e.g. heavy phone if flagged, required onsite); a required language exceeds the user's
level; seniority is above the user's target.

OUTPUT (JSON only):
{"decision":"keep|reject","reasons":[...],"uncertainties":["unclear fields"]}
If a must-have is "unclear", KEEP and flag it — don't reject on missing info alone.
```

---

## Prompt E — Fit-score, automatability & rank (mid-tier)

```
Score how well ONE role fits this user, AND how much of the day-to-day is automatable with
SQL/Python/LLM/n8n. The user wants roles they can automate most of, so ranking is weighted to
automatability. Honest and specific — a wrong "strong" wastes time.

PROFILE: {{PROFILE}}
ROLE: {{ROLE_JSON}}

FIT RUBRIC (sum 100): role-type match 30; eligibility clarity 20; phone fit 15; seniority match
15; async/time-zone fit 10; culture/values fit (incl. nice_to_haves) 10.
AUTOMATABILITY (0-100): how much of the work is automatable. HIGH = recurring reporting, ETL,
data entry, monitoring, reconciliation, ticket triage, tagging. LOW = strategy, stakeholder,
research, creative. PAY (0-100) from posting comp or seniority. STACKABLE if runnable alongside other jobs (contract/freelance/part-time/async). ROUTE: 'stack' if automatable+stackable (run several), 'premium' if well-paid (do one manually), else 'other'. VALUE = euro/time = pay scaled up by automatability. COMBINED = VALUE for stack, PAY for premium, else a blend. Goal: maximise euro/time.

OUTPUT (JSON only):
{"fit_score":0-100,"auto_score":0-100,"pay_score":0-100,"value_score":0-100,
 "stackable":true/false,"route":"stack|premium|other","combined":0-100,
 "tier":"strong|maybe|weak", // by COMBINED: strong>=70, maybe 40-69, weak<40
 "automation_plan":"<=2 lines: what you'd automate and with what",
 "why_it_fits":[...],"concerns":[...],"phone_risk":"low|medium|high","verify_before_applying":[...]}
```

---

## Prompt F — Tailor the CV to this posting (mid-tier) — the per-job module core

```
Tailor the user's CV to ONE posting. Truthful: reorder and re-emphasize, NEVER invent.

BASE CV: {{BASE_CV_MD}}
PROFILE: {{PROFILE}}
JOB: {{ROLE_JSON + posting highlights}}

DO:
- Lead with the experience, skills, and projects most relevant to THIS posting.
- Mirror the posting's key terminology and named skills for ATS matching — only where the
  user genuinely has them.
- Trim or shorten irrelevant items; keep to ~1–2 pages.
- Mark any genuine gap or unverifiable claim with [BRACKETS]; never fabricate titles, dates,
  employers, or metrics.

OUTPUT:
1) cv.md — a complete tailored CV in clean Markdown.
2) tailoring_notes — what you emphasized + every [BRACKET] the user must resolve.
```

---

## Prompt G — Cover letter + common answers (mid-tier)

```
Write a cover letter + common application answers for this role, consistent with the tailored CV.

PROFILE: {{PROFILE}}   TAILORED CV: {{CV_MD}}   JOB: {{ROLE_JSON}}

RULES: ground every claim in the CV/profile; ~180–250 words; no clichés; plain warm tone;
frame time-zone flexibility and relevant strengths as concrete value; mark gaps with [BRACKETS],
never invent.

OUTPUT (JSON only):
{"cover_letter":"...","common_answers":{"why_this_company":"...","relevant_experience":"...",
 "salary_expectation":"range + [confirm]","availability":"[confirm]"},"gaps_for_human":[...]}
```

---

## Prompt H — Assemble the job module & queue (cheap) — STOP before sending

```
Assemble the per-job module and tracker row. DO NOT SUBMIT.

INPUTS: {{ROLE_JSON}}, {{FIT_JSON}}, {{CV_MD}}, {{COVER_JSON}}.

Create jobs/<date>_<company>_<role-slug>_<id>/ with:
  job.json (posting+fields), fit.json, cv.md, cover_letter.md, application.md (answers +
  status + submit checklist). Set status = ready_to_submit. Add a tracker row.
If the application needs login/CAPTCHA/assessment, set needs_human_finish = true.

Then output a compact review card and STOP. Submit only after an explicit human "submit".
Never auto-submit; never automate LinkedIn Easy Apply.

OUTPUT (JSON only): {"module_path":"...","tracker_row":{...},"review_card":"...","needs_human_finish":bool}
```
