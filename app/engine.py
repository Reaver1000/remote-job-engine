"""Scoring + CV tailoring. Provider-agnostic: Claude or OpenAI when a key is set, else an
offline heuristic so the app always runs.

Per job it produces fit_score, auto_score (automatability), pay_score, stackable, and a ROUTE:
  - "stack"   -> automatable AND stackable: part of a run-several-in-parallel portfolio
  - "premium" -> pays well enough to be worth doing manually (one big role)
  - "other"   -> neither
combined = a route-appropriate ranking number (stack: auto-weighted; premium: pay; other: blend)."""
import os, json, re

LLM = os.environ.get("JOBHUNT_LLM", "claude").lower()

def _call_llm(prompt, system="You are a precise hiring & automation analyst.", max_tokens=1800):
    try:
        if LLM == "claude" and os.environ.get("ANTHROPIC_API_KEY"):
            import anthropic
            m = anthropic.Anthropic().messages.create(
                model=os.environ.get("JOBHUNT_MODEL", "claude-haiku-4-5"),
                max_tokens=max_tokens, system=system,
                messages=[{"role": "user", "content": prompt}])
            return "".join(b.text for b in m.content if getattr(b, "type", "") == "text")
        if LLM == "openai" and os.environ.get("OPENAI_API_KEY"):
            from openai import OpenAI
            r = OpenAI().chat.completions.create(
                model=os.environ.get("JOBHUNT_MODEL", "gpt-4o-mini"),
                messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}])
            return r.choices[0].message.content
    except Exception as e:
        print("LLM call failed, using offline fallback:", e)
    return None

def _tier(s): return "strong" if s >= 70 else ("maybe" if s >= 40 else "weak")

HIGH_AUTO = ["report", "reporting", "dashboard", "data entry", "manual", "spreadsheet", "excel",
             "etl", "pipeline", "monitoring", "reconcil", "triage", "tagging", "annotation",
             "quality", "processing", "back office", "bookkeep", "scraping", "integration",
             "recurring", "ops", "operations"]
LOW_AUTO = ["strategy", "stakeholder", "research", "design", "negotiat", "creative", "roadmap",
            "leadership", "people management"]
HI_PAY = ["senior", "lead", "staff", "principal", "architect", "manager", "director", "head ", "vp ", "chief"]
LO_PAY = ["junior", "entry", "intern", "graduate", "assistant", "trainee", "apprentice"]
STACK_HINTS = ["contract", "freelance", "part-time", "part time", "hourly", "contractor", "temp", "fractional", "async"]

def _fit_heuristic(job, profile):
    t = (job.get("title", "") + " " + job.get("location", "")).lower()
    kws = [k.lower() for k in profile.get("role_keywords", [])]
    excl = [k.lower() for k in profile.get("exclude_titles", [])]
    hits = sum(1 for k in kws if k in t)
    s = min(60, hits * 20)
    if any(w in t for w in ["remote", "anywhere", "worldwide"]): s += 20
    if any(w in t for w in ["junior", "graduate", "entry"]): s += 10
    if any(e in t for e in excl): s -= 25
    if any(p in t for p in profile.get("phone_block", [])): s -= 40
    return max(0, min(100, s)), str(hits) + " role-keyword hit(s)"

def _auto_heuristic(job):
    t = (job.get("title", "") + " " + job.get("location", "")).lower()
    s = 45 + 12 * sum(1 for w in HIGH_AUTO if w in t) - 14 * sum(1 for w in LOW_AUTO if w in t)
    if any(w in t for w in ["analyst", "data", "report", "bi ", "operations", "support", "automation", "etl"]):
        s += 15
    if any(w in t for w in ["manager", "head", "director", "principal", "scientist", "research"]):
        s -= 15
    s = max(0, min(100, s))
    plan = ("Recurring reports to scheduled SQL + a Python/n8n job; ad-hoc pulls to self-serve query "
            "templates; data checks to automated validation. Heavily automatable.") if s >= 60 else \
           ("Some parts automatable (pulls, formatting), but judgement/communication-heavy parts remain.")
    return s, plan

def _pay_heuristic(job):
    t = (job.get("title", "") + " " + job.get("location", "")).lower()
    base = 50
    if any(w in t for w in HI_PAY): base += 25
    if any(w in t for w in ["engineer", "scientist", "developer"]): base += 8
    if any(w in t for w in LO_PAY): base -= 15
    return max(0, min(100, base))

def _stackable(job, auto):
    t = (job.get("title", "") + " " + job.get("location", "")).lower()
    if any(w in t for w in STACK_HINTS): return True
    if "remote" in t and auto >= 55 and not any(w in t for w in ["senior", "lead", "manager", "director", "head "]):
        return True
    return False

def _route(auto, pay, stackable):
    if stackable and auto >= 55: return "stack"
    if pay >= 70: return "premium"
    return "other"

def _value(pay, auto):
    # effective money-per-time: high automation -> little human time -> better euro/hour
    return round(min(100, pay * (0.6 + 0.8 * auto / 100.0)))

def _combined(route, fit, auto, pay):
    if route == "stack":   return _value(pay, auto)   # rank the portfolio by euro/time
    if route == "premium": return pay                 # one big role: absolute pay
    return round(0.4 * fit + 0.3 * auto + 0.3 * pay)

def score(job, profile):
    prompt = (
        'Output ONLY a raw JSON object — no markdown fences, no explanation:\n'
        '{"fit_score":0-100,"auto_score":0-100,"pay_score":0-100,'
        '"stackable":true/false,"route":"stack|premium|other",'
        '"automation_plan":"one sentence","reasons":"one sentence"}\n\n'
        'fit_score: how well candidate targets/skills match this specific role (0=no match,100=perfect).\n'
        'auto_score: % of daily tasks automatable with SQL/Python/LLM/n8n (0=all human,100=fully automated).\n'
        'pay_score: pay vs EU remote market — 0=very low, 50=market, 70=good, 100=top quartile; '
        'use posted comp if available, else infer from seniority and role type.\n'
        'stackable: true ONLY if role is contract/freelance/part-time/async/deliverable-based '
        'and could plausibly run alongside other jobs; false if full-time exclusive.\n'
        'route: "stack" if stackable=true AND auto_score>=55; "premium" if pay_score>=70; else "other".\n'
        'automation_plan: one concrete sentence on how the routine work could be automated.\n'
        'reasons: one sentence on candidate fit or lack of it.\n\n'
        "CANDIDATE: " + json.dumps(profile.get("summary", "")) +
        " | targets: " + ", ".join(str(k) for k in profile.get("role_keywords", [])) + "\n"
        "JOB: " + str(job.get("title")) + " @ " + str(job.get("company")) +
        " | " + str(job.get("location")) + " | " + str(job.get("url")))
    out = _call_llm(prompt, max_tokens=450)
    if out:
        try:
            d = json.loads(re.search(r"\{.*\}", out, re.S).group())
            fit = int(d.get("fit_score", 0)); auto = int(d.get("auto_score", 0)); pay = int(d.get("pay_score", 0))
            stk = 1 if d.get("stackable") else 0
            route = d.get("route") or _route(auto, pay, bool(stk))
            comb = _combined(route, fit, auto, pay)
            return {"fit_score": fit, "auto_score": auto, "pay_score": pay, "value_score": _value(pay, auto),
                    "stackable": stk, "route": route, "combined": comb, "tier": _tier(comb),
                    "reasons": str(d.get("reasons", "")), "automation_plan": str(d.get("automation_plan", ""))}
        except Exception:
            pass
    fit, reasons = _fit_heuristic(job, profile)
    auto, plan = _auto_heuristic(job)
    pay = _pay_heuristic(job)
    stk = _stackable(job, auto)
    route = _route(auto, pay, stk)
    comb = _combined(route, fit, auto, pay)
    return {"fit_score": fit, "auto_score": auto, "pay_score": pay, "value_score": _value(pay, auto),
            "stackable": 1 if stk else 0, "route": route, "combined": comb, "tier": _tier(comb),
            "reasons": "heuristic: " + reasons, "automation_plan": plan}

def tailor_cv(job, profile, base_cv):
    prompt = ("Rewrite the CV below for ATS and this specific role. Rules:\n"
              "- Mirror the job's exact keywords where the candidate genuinely has that skill or experience\n"
              "- Reorder bullet points within each role to surface the most relevant achievements first\n"
              "- Never invent skills, job titles, employers, or dates\n"
              "- Keep all section headings intact (Work Experience, Education, Skills, etc.)\n"
              "- Output the full CV in Markdown only — no preamble, no commentary, no notes\n\n"
              "=== JOB ===\n" + str(job.get("title")) + " @ " + str(job.get("company")) +
              " — " + str(job.get("url")) + "\n\n"
              "=== BASE CV ===\n" + base_cv)
    out = _call_llm(prompt, max_tokens=2200)
    if out:
        return out
    head = ("> Tailored for **" + str(job.get("title")) + " @ " + str(job.get("company")) + "** (" +
            str(job.get("url")) + ").\n> [Offline draft - set ANTHROPIC_API_KEY/OPENAI_API_KEY for full tailoring.]\n\n")
    return head + base_cv

def cover_letter(job, profile, cv_md):
    prompt = ("Write a 180-210 word cover letter for: " + str(job.get("title")) + " at " +
              str(job.get("company")) + "\n"
              "Rules: grounded only in the CV below, never invent experience; "
              "tone direct and warm, not sycophantic; "
              "open with a specific hook tied to the role or company, not 'I am writing to apply'; "
              "one paragraph on fit, one on what the candidate brings, one-sentence close. "
              "Output the letter text only — no subject line, no date, no bracketed placeholders.\n\n"
              "=== CV ===\n" + cv_md)
    out = _call_llm(prompt, max_tokens=700)
    return out or ("Dear Hiring Team,\n\n[Offline draft] I'm applying for " + str(job.get("title")) +
                   " at " + str(job.get("company")) + ". My background in SQL, Python and data analysis maps "
                   "well to this role; see my CV and github.com/Reaver1000.\n\nBest regards,\nDavid A. Buchan")
