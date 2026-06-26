"""
Live pipeline tracking from Gmail (IMAP, read-only — NEVER deletes).

For each job you've applied to, it searches your inbox for messages mentioning that company,
classifies the latest as rejected / advanced / other (LLM if a key is set, else keywords), and
hands the result back so the dashboard can tag the pipeline. It only reads; rejected rows get an
"Open in Gmail" link so you delete them yourself.

Enable by setting two env vars (use a Gmail App Password, not your main password):
  GMAIL_USER=you@gmail.com
  GMAIL_APP_PASSWORD=xxxxxxxxxxxxxxxx
(Google Account -> Security -> 2-Step Verification -> App passwords.)
"""
import os, imaplib, email, datetime
from email.header import decode_header

REJECT = ["unfortunately", "not moving forward", "decided not to", "other candidates",
          "won't be proceeding", "will not be proceeding", "regret to inform",
          "not be progressing", "unsuccessful", "not selected", "position has been filled"]
ADVANCE = ["interview", "next step", "schedule a call", "schedule a time", "assessment",
           "move forward", "we'd like to", "like to invite", "book a time", "technical screen",
           "availability", "phone screen", "take-home"]

def _decode(s):
    if not s: return ""
    out = []
    for part, enc in decode_header(s):
        out.append(part.decode(enc or "utf-8", "replace") if isinstance(part, bytes) else part)
    return "".join(out)

def _body(msg):
    try:
        if msg.is_multipart():
            for p in msg.walk():
                if p.get_content_type() == "text/plain":
                    return (p.get_payload(decode=True) or b"").decode(p.get_content_charset() or "utf-8", "replace")
            return ""
        return (msg.get_payload(decode=True) or b"").decode(msg.get_content_charset() or "utf-8", "replace")
    except Exception:
        return ""

def classify(subject, body, llm=None):
    text = (subject + " " + body).lower()
    if llm:
        try:
            out = llm("Classify this job-application email as exactly one word: rejected, advanced, or other.\n"
                      "SUBJECT: " + subject + "\nBODY: " + body[:1500])
            w = (out or "").strip().lower()
            for k in ("rejected", "advanced", "other"):
                if k in w: return k
        except Exception:
            pass
    if any(k in text for k in REJECT): return "rejected"
    if any(k in text for k in ADVANCE): return "advanced"
    return "other"

def sync(companies, days=45, llm=None):
    """companies: list of (job_id, company). Returns {ok, updates|message}. Read-only."""
    user = os.environ.get("GMAIL_USER"); pw = os.environ.get("GMAIL_APP_PASSWORD")
    if not (user and pw):
        return {"ok": False, "message": "Email sync off. Set GMAIL_USER + GMAIL_APP_PASSWORD "
                "(Gmail App Password) to enable read-only pipeline tracking."}
    since = (datetime.date.today() - datetime.timedelta(days=days)).strftime("%d-%b-%Y")
    updates = []
    try:
        M = imaplib.IMAP4_SSL("imap.gmail.com")
        M.login(user, pw); M.select("INBOX")
    except Exception as e:
        return {"ok": False, "message": "Gmail login failed: " + str(e)[:120]}
    try:
        seen = set()
        for job_id, company in companies:
            company = (company or "").strip()
            if not company or company.lower() in seen: continue
            seen.add(company.lower())
            try:
                typ, data = M.search(None, '(SINCE %s TEXT "%s")' % (since, company.replace('"', "")))
            except Exception:
                continue
            ids = (data[0].split() if data and data[0] else [])[-3:]
            for i in reversed(ids):
                try:
                    t, md = M.fetch(i, "(RFC822)")
                    msg = email.message_from_bytes(md[0][1])
                except Exception:
                    continue
                subj = _decode(msg.get("Subject"))
                cl = classify(subj, _body(msg), llm)
                if cl in ("rejected", "advanced"):
                    updates.append({"job_id": job_id, "company": company, "status": cl, "subject": subj[:90]})
                    break
    finally:
        try: M.logout()
        except Exception: pass
    return {"ok": True, "updates": updates}
