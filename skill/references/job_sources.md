# Job sources & low-latency discovery design

Goal: surface new remote, Germany-eligible data/analyst postings **within minutes** of
release, cheaply and without scraping LinkedIn. All endpoints below were verified live; see
"Sources" at the bottom. Treat field names as a starting point and confirm against a live
response, since APIs evolve.

## The core idea: two tiers

| Tier | Sources | Latency | Auth | Use for |
|------|---------|---------|------|---------|
| 1. ATS feeds (watchlist) | Greenhouse, Lever, Ashby, SmartRecruiters | **minutes** | none | Speed — be first to apply |
| 2. Aggregators | Arbeitnow, RemoteOK, Remotive, Adzuna, The Muse, HN | hours/daily | none/free key | Breadth — catch the rest |

Aggregators re-crawl on their own slow schedule (and Remotive is rate-limited), so they
cannot give true minutes-level freshness. Polling individual company ATS boards can, because
the board reflects a new posting the instant HR publishes it. So: curate a **watchlist** of
remote-friendly, Germany/EU-hiring companies in data/AI and poll their ATS boards often;
use the aggregators as a wider net on a gentler schedule.

---

## Tier 1 — Company ATS feeds (no auth, poll often)

### Greenhouse
- Jobs: `GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs`
- Full descriptions: add `?content=true`
- No auth for GET (public board data). `board_token` = the slug in `boards.greenhouse.io/{token}`.
- Response: `{"jobs":[{"id","title","absolute_url","updated_at","location":{"name"}, ...}]}`

### Lever
- Jobs: `GET https://api.lever.co/v0/postings/{company}?mode=json`
- No auth. Filter params: `team`, `department`, `location`, `commitment`, `level`, `limit`.
- Response: list of `{"id","text","hostedUrl","createdAt","categories":{"location","commitment","team"}}`

### Ashby
- Jobs: `GET https://api.ashbyhq.com/posting-api/job-board/{org}?includeCompensation=true`
- No auth. No server-side filtering — filter client-side.
- Response: `{"jobs":[{"id","title","location","department","team","isRemote","jobUrl", ...}]}`

### SmartRecruiters (verify fields)
- Jobs: `GET https://api.smartrecruiters.com/v1/companies/{company}/postings`
- No auth for public postings. Paginated (`offset`,`limit`).

> Finding a company's ATS + token: open the company careers page; the apply links reveal it
> (`boards.greenhouse.io/<token>`, `jobs.lever.co/<company>`, `jobs.ashbyhq.com/<org>`).
> Arbeitnow (below) also tells you which ATS a job came from.

---

## Tier 2 — Aggregator APIs

### Arbeitnow — best for Germany/EU, no key
- `GET https://www.arbeitnow.com/api/job-board-api` (paginated, newest first)
- Aggregates many ATSes (Greenhouse, SmartRecruiters, Join, TeamTailor, Recruitee, Comeet,
  Lever, Personio). Fields include `title`, `company_name`, `url`, `location`, `remote` (bool),
  `tags`, `job_types`, `created_at`, and a `visa_sponsorship` flag.
- No auth, CORS enabled. Poll every ~10–15 min is fine.

### RemoteOK — no key, attribution REQUIRED
- `GET https://remoteok.com/api` (first array element is a legal/notice object — skip it)
- Fields: `id`, `company`, `position`, `url`, `location`, `tags`, `date`, salary fields.
- Terms: you must credit RemoteOK and link back with a direct (no-redirect) link. Send a
  `User-Agent`. Hourly polling is reasonable.

### Remotive — no key, RATE-LIMITED
- `GET https://remotive.com/api/remote-jobs?category=data` (also `search=`, `company_name=`, `limit=`)
- Fields under `jobs[]`: `id`, `company_name`, `title`, `url`, `candidate_required_location`,
  `tags`, `publication_date`.
- **Limit: >2 requests/min are blocked; they recommend a couple of calls per day.** Use as a
  daily sweep, not a fast poller.

### Adzuna — free key, strong Germany filtering
- Register for `app_id` + `app_key` at developer.adzuna.com (free tier).
- `GET https://api.adzuna.com/v1/api/jobs/{country}/search/1?app_id=..&app_key=..&results_per_page=50&what=data%20analyst&max_days_old=1&sort_by=date&content-type=application/json`
- Country code comes from `config.adzuna_country` (e.g. `de`, `gb`, `us`). `sort_by=date` + `max_days_old=1` keeps it fresh.
- Fields under `results[]`: `id`, `title`, `company.display_name`, `redirect_url`,
  `location.display_name`, `created`.

### The Muse — free key, has explicit levels (verify)
- `GET https://www.themuse.com/api/public/jobs?category=Data%20and%20Analytics&level=Entry%20Level&page=0`
- Useful because `level=Entry Level` matches a near-grad directly.

### Hacker News "Who is Hiring" — no key (startups/remote)
- Monthly thread, searchable via Algolia: `https://hn.algolia.com/api/v1/search_by_date?tags=comment,story_<THREAD_ID>&query=remote`
- Find the current thread: `https://hn.algolia.com/api/v1/search?query=Ask%20HN%20Who%20is%20hiring&tags=story&restrictSearchableAttributes=title`
- Comments are free-text; have the cheap model parse remote + role + how-to-apply.

---

## Polling schedule (respect rate limits)

| Source | Suggested interval |
|--------|--------------------|
| Greenhouse / Lever / Ashby watchlist | every 10–15 min |
| Arbeitnow | every 15 min |
| Adzuna (sort_by=date, max_days_old=1) | every 30–60 min |
| RemoteOK | hourly |
| Remotive | 2–3× per day |
| HN Who-is-Hiring | daily (monthly thread) |

## Dedupe & state
- Keep a `state/seen_ids.json` set of `"{source}:{id}"`. A job is "new" only if its id is not
  in the set. Add new ids after processing.
- Persist across runs so the scheduled poller only ever surfaces genuinely new postings.

## Be a polite client
- Send a descriptive `User-Agent`. Add small jitter between calls. Cache the watchlist.
- Honour each source's terms (RemoteOK attribution; Remotive frequency; LinkedIn = discovery
  only, never automated apply).

## Sources (verified)
- Remotive API: https://github.com/remotive-com/remote-jobs-api , https://remotive.com/remote-jobs/api
- RemoteOK API: https://remoteok.com/api , https://remoteok.com/remote-api-jobs
- Arbeitnow API: https://www.arbeitnow.com/blog/job-board-api
- Adzuna API: https://developer.adzuna.com/overview
- Greenhouse Job Board API: https://developers.greenhouse.io/job-board.html
- Lever Postings API: https://github.com/lever/postings-api
- Ashby Public Job Posting API: https://developers.ashbyhq.com/docs/public-job-posting-api
- HN Algolia Search API: https://hn.algolia.com/api
