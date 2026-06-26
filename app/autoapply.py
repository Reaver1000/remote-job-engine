"""
Auto-apply worker for the STACK lane (small, automatable, stackable roles).

Design + guardrails (these are deliberate, not limitations to remove):
  - OFF by default. Set AUTOAPPLY_ENABLED=1 to arm it.
  - DRY-RUN by default. It fills the form but does NOT submit until AUTOAPPLY_DRY_RUN=0.
  - DAILY CAP (AUTOAPPLY_DAILY_CAP, default 10) so you don't get flagged as a bulk spammer.
  - SAFE STOPS: anything with a CAPTCHA, login/account wall, or a required custom question it
    can't answer truthfully from your profile is PARKED for you to finish — never guessed.
  - Never fabricates answers. Premium roles do not pass through here (they stay manual).
  - Every attempt is logged to state/autoapply_log.csv.

Real submission uses Playwright (per-ATS). Greenhouse is implemented as the worked example;
Lever/Ashby follow the same pattern (selectors marked TODO). If Playwright isn't installed,
calls return 'parked' with an explanatory reason so the app keeps working.
"""
import os, csv, time

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "state"); os.makedirs(STATE, exist_ok=True)
LOG = os.path.join(STATE, "autoapply_log.csv")

def status():
    return {"enabled": os.environ.get("AUTOAPPLY_ENABLED") == "1",
            "dry_run": os.environ.get("AUTOAPPLY_DRY_RUN", "1") != "0",
            "cap": int(os.environ.get("AUTOAPPLY_DAILY_CAP", "10")),
            "used_today": _count_today()}

def detect_ats(url):
    u = (url or "").lower()
    if "greenhouse.io" in u: return "greenhouse"
    if "lever.co" in u: return "lever"
    if "ashbyhq.com" in u: return "ashby"
    return "unknown"

def _count_today():
    if not os.path.exists(LOG): return 0
    today = time.strftime("%Y-%m-%d")
    n = 0
    with open(LOG) as f:
        for r in csv.reader(f):
            if r and r[0].startswith(today) and len(r) > 4 and r[4] == "submitted":
                n += 1
    return n

def _log(job, st, reason):
    new = not os.path.exists(LOG)
    with open(LOG, "a", newline="") as f:
        w = csv.writer(f)
        if new: w.writerow(["ts", "id", "company", "title", "status", "reason", "url"])
        w.writerow([time.strftime("%Y-%m-%d %H:%M"), job.get("id"), job.get("company"),
                    job.get("title"), st, reason, job.get("url")])

def _result(job, st, reason):
    _log(job, st, reason)
    return {"status": st, "reason": reason}

def apply_one(job, cv_path, profile, dry_run=None):
    """Returns {status: submitted|dry_run|parked|disabled|error, reason}."""
    s = status()
    if not s["enabled"]:
        return {"status": "disabled", "reason": "auto-apply OFF (set AUTOAPPLY_ENABLED=1)"}
    if s["used_today"] >= s["cap"]:
        return _result(job, "parked", f"daily cap reached ({s['cap']})")
    ats = detect_ats(job.get("url"))
    if ats == "unknown":
        return _result(job, "parked", "unsupported ATS — apply manually")
    dry = s["dry_run"] if dry_run is None else dry_run
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return _result(job, "parked", "Playwright not installed (pip install playwright && playwright install chromium)")
    try:
        with sync_playwright() as pw:
            br = pw.chromium.launch(headless=True)
            pg = br.new_page()
            apply_url = _apply_url(ats, job["url"])
            pg.goto(apply_url, timeout=30000)
            parked = _fill(ats, pg, job, cv_path, profile)
            if parked:
                br.close(); return _result(job, "parked", parked)
            # safety: bail on visible bot-checks / auth walls only
            # (don't bail on reCAPTCHA v3 which just loads a script invisibly)
            html = pg.content().lower()
            has_visible_captcha = bool(pg.query_selector("iframe[src*='recaptcha'][style*='width']") or
                                       pg.query_selector(".g-recaptcha:visible") or
                                       pg.query_selector("iframe[src*='hcaptcha']"))
            if has_visible_captcha or any(k in html for k in ["are you human", "sign in to apply", "create an account"]):
                br.close(); return _result(job, "parked", "CAPTCHA or login required — finish manually")
            if dry:
                br.close(); return _result(job, "dry_run", "form filled, NOT submitted (dry-run)")
            _submit(ats, pg)
            br.close(); return _result(job, "submitted", "auto-applied")
    except Exception as e:
        return _result(job, "error", str(e)[:160])

def _apply_url(ats, url):
    """Return the direct application form URL for each ATS."""
    url = (url or "").rstrip("/")
    if ats == "ashby":
        return url if url.endswith("/application") else url + "/application"
    if ats == "greenhouse":
        # job-boards.greenhouse.io pages embed the form; boards.greenhouse.io needs #app
        if "job-boards.greenhouse.io" in url:
            return url
        return url if "#" in url else url + "#app"
    return url  # lever: form is on the listing page


def _fill(ats, pg, job, cv_path, profile):
    """Fill standard fields (verified against live Greenhouse/Ashby forms). Returns a park
    reason if a required CUSTOM question is present (we never guess answers), else None."""
    name = profile.get("name", ""); email = profile.get("email", "")
    first, last = (name.split(" ", 1) + [""])[:2] if name else ("", "")
    full = (name or (first + " " + last)).strip()
    def setfile(selectors):
        if not (cv_path and os.path.exists(cv_path)): return
        for sel in selectors:
            try: pg.set_input_files(sel, cv_path); return
            except Exception: continue
    try:
        if ats == "greenhouse":
            pg.wait_for_selector("#first_name", timeout=15000)
            pg.fill("#first_name", first); pg.fill("#last_name", last); pg.fill("#email", email)
            setfile(["input[type=file]"])
        elif ats == "lever":
            # Lever listing pages show "Apply Now" — click it to reveal the inline form
            try:
                btn = pg.query_selector("a.template-btn-submit, a[href*='/apply'], button:has-text('Apply')")
                if btn:
                    btn.click()
                    pg.wait_for_timeout(1500)
            except Exception:
                pass
            pg.wait_for_selector("input[name=name]", timeout=20000)
            pg.fill("input[name=name]", full); pg.fill("input[name=email]", email)
            setfile(["input[name=resume]", "input[type=file]"])
        elif ats == "ashby":
            pg.wait_for_selector("#_systemfield_name", timeout=15000)
            pg.fill("#_systemfield_name", full); pg.fill("#_systemfield_email", email)
            setfile(["#_systemfield_resume", "input[type=file]"])
        else:
            return ats + " not supported — finish manually"
    except Exception as e:
        return ats + " form changed: " + str(e)[:80]
    # Fill common profile fields matched by label text (Ashby uses UUID ids).
    _fill_by_labels(pg, profile)
    # Park if any REMAINING required field is a custom question we can't answer.
    try:
        for el in pg.query_selector_all("input[required],textarea[required],select[required],[aria-required=true]"):
            if (el.get_attribute("type") or "").lower() == "file": continue
            fid = el.get_attribute("id") or ""; fname = el.get_attribute("name") or ""
            known = (fid.startswith("_systemfield_") or fid in ("first_name", "last_name", "email")
                     or fname in ("name", "email", "first_name", "last_name")
                     or _is_profile_label(pg, fid))
            if not known:
                label_el = pg.query_selector(f"label[for='{fid}']") if fid else None
                label_text = label_el.inner_text().strip() if label_el else ""
                return "required custom question: %r — finish manually" % (label_text or fid)
    except Exception:
        pass
    return None


_LABEL_MAP = {
    # label text (lowercase) -> profile key
    "phone": "phone", "phone number": "phone", "mobile": "phone", "telephone": "phone",
    "linkedin": "linkedin_url", "linkedin url": "linkedin_url", "linkedin profile": "linkedin_url",
    "github": "github_url", "github url": "github_url",
    "portfolio": "portfolio_url", "website": "portfolio_url",
    "notice period": "notice_period", "availability": "notice_period",
    "country": "country", "country of residence": "country", "current country": "country",
    "country of residence *": "country", "country/region": "country",
    "monthly salary": "salary_expectation_monthly_eur",
    "monthly salary expectation": "salary_expectation_monthly_eur",
    "expected monthly salary": "salary_expectation_monthly_eur",
    "salary expectation": "salary_expectation_monthly_eur",
    "expected salary": "salary_expectation_monthly_eur",
    "location": "location", "city": "location", "current location": "location",
}


def _is_profile_label(pg, fid):
    if not fid: return False
    label_el = pg.query_selector(f"label[for='{fid}']")
    if not label_el: return False
    return label_el.inner_text().strip().lower() in _LABEL_MAP


def _fill_by_labels(pg, profile):
    """Fill fields that match known label text from the profile."""
    try:
        labels = pg.query_selector_all("label")
        for lbl in labels:
            text = lbl.inner_text().strip().lower().rstrip("*").strip()
            key = _LABEL_MAP.get(text)
            if not key: continue
            val = profile.get(key, "")
            if not val: continue
            fid = lbl.get_attribute("for") or ""
            el = pg.query_selector(f"#{fid}") if fid else None
            if not el: continue
            tag = el.evaluate("e => e.tagName.toLowerCase()")
            if tag in ("input", "textarea"):
                try: el.fill(str(val))
                except Exception: pass
    except Exception:
        pass

def _submit(ats, pg):
    if ats == "ashby":
        pg.click("button:has-text('Submit Application'), button:has-text('Submit')")
    elif ats == "lever":
        pg.click("button[type=submit], .template-btn-submit")
    else:
        pg.click("#submit_app, button[type=submit]")
    pg.wait_for_timeout(2500)
