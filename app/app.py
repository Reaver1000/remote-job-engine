"""
Job-Hunt dashboard — FastAPI backend + single-page UI.

Flow:
  - /api/refresh ingests new postings (from the poller CSV if present, else seeds samples),
    scores each, and AUTO-tailors a CV for anything scoring >= 70.
  - >=70  -> "Ready to apply" (CV already generated, Apply enabled).
  - 40-69 -> "Needs a CV": click Generate CV; when it's ready, Apply ungreys.
  - <40   -> "Low matches" (kept, no CV/apply).
  - Apply is ASSISTED: it opens the posting + serves your tailored CV/cover for final submit.
  - Email: rejections are marked on the tracker; the app never deletes email. The Gmail
    connector is read-only, so rejected rows show an "Open in Gmail" link to delete yourself.

Run:  pip install -r requirements.txt  &&  uvicorn app:app --reload
"""
import os, re, csv, json, time
from fastapi import FastAPI, Body
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
import store, engine, autoapply, cvpdf

HERE = os.path.dirname(os.path.abspath(__file__))
JOBS_DIR = os.path.join(HERE, "jobs")
DATA = os.path.join(HERE, "data")

DEFAULT_CONFIG = {
    "role_keywords": ["data analyst", "data analytics", "bi analyst", "business intelligence",
                      "analytics engineer", "data scientist", "business analyst", "operations analyst",
                      "junior developer", "software engineer", "python developer", "technical support",
                      "customer support", "automation", "virtual assistant", "executive assistant",
                      "administrative assistant", "data entry", "operations assistant", "back office"],
    "exclude_titles": ["senior", "lead", "principal", "staff", "manager", "head of", "director"],
    "phone_block": ["call center", "call centre", "outbound call", "cold call", "phone sales"],
}

def load_config():
    p = os.path.join(DATA, "config.json")
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(p):
        try: cfg.update({k: v for k, v in json.load(open(p)).items() if not k.startswith("_")})
        except Exception: pass
    return cfg

def load_profile():
    cfg = load_config()
    base = ""
    for c in (os.path.join(DATA, "base_cv.md"),):
        if os.path.exists(c): base = open(c, encoding="utf-8").read()
    if not base:
        base = "# David A. Buchan\nJunior Developer & Data Analyst — SQL, Python, ETL, dashboards.\ngithub.com/Reaver1000"
    return {**cfg, "base_cv": base,
            "name": cfg.get("name", "David A. Buchan"),
            "email": cfg.get("email", os.environ.get("JOBHUNT_EMAIL", "davidbuchan1000@googlemail.com")),
            "summary": "Junior developer & data analyst, SQL/Python/ETL, CS degree (Open University 2026), remote."}

SAMPLE = [
    {"id": "sample:1", "source": "sample", "company": "n8n", "title": "Data Analyst (Remote Europe)", "url": "https://example.com/1", "location": "Remote - Europe"},
    {"id": "sample:2", "source": "sample", "company": "Remote.com", "title": "Junior Data Analyst (Remote)", "url": "https://example.com/2", "location": "Remote - Worldwide"},
    {"id": "sample:3", "source": "sample", "company": "Acme BI", "title": "Business Intelligence Analyst, Remote", "url": "https://example.com/3", "location": "Remote"},
    {"id": "sample:4", "source": "sample", "company": "DataOps Co", "title": "Data Operations Specialist", "url": "https://example.com/4", "location": "Remote (EMEA)"},
    {"id": "sample:5", "source": "sample", "company": "HelpDesk Inc", "title": "Customer Support (Chat) - Remote", "url": "https://example.com/5", "location": "Remote"},
    {"id": "sample:6", "source": "sample", "company": "BigCorp", "title": "Senior Data Scientist", "url": "https://example.com/6", "location": "Remote US only"},
]

def _poller_csv():
    cands = [os.environ.get("JOBHUNT_MATCHES", ""),
             os.path.join(HERE, "state", "new_matches.csv"),
             os.path.join(HERE, "..", "skill", "state", "new_matches.csv"),
             os.path.join(HERE, "..", "remote-job-hunt", "state", "new_matches.csv")]
    for p in cands:
        if p and os.path.exists(p): return p
    return None

def ingest():
    src = _poller_csv()
    rows = []
    if src:
        with open(src, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                rows.append({"id": f"{r.get('source','')}:{r.get('url','')}", "source": r.get("source", ""),
                             "company": r.get("company", ""), "title": r.get("title", ""),
                             "url": r.get("url", ""), "location": r.get("location", "")})
    if not rows and not store.all_jobs():
        rows = SAMPLE
    for j in rows:
        store.upsert(j)

def _safe(s): return re.sub(r"[^a-zA-Z0-9_-]+", "-", s)[:60]

def score_and_autocv():
    prof = load_profile()
    for j in store.all_jobs():
        if j["status"] in ("applied", "rejected", "advanced"): continue
        if not j["combined"]:
            s = engine.score(j, prof)
            store.update(j["id"], score=s["fit_score"], auto_score=s["auto_score"],
                         pay_score=s["pay_score"], value_score=s["value_score"],
                         stackable=s["stackable"], route=s["route"], combined=s["combined"],
                         tier=s["tier"], reasons=s["reasons"], automation_plan=s["automation_plan"])
            j = store.get(j["id"])
        strong = (j["route"] == "stack" and j["auto_score"] >= 70) or \
                 (j["route"] == "premium" and j["pay_score"] >= 80)
        if strong and not j["cv_ready"]:
            _make_cv(j["id"])

def _make_cv(job_id):
    prof = load_profile(); j = store.get(job_id)
    cv = engine.tailor_cv(j, prof, prof["base_cv"])
    cover = engine.cover_letter(j, prof, cv)
    # Fixed filenames — overwritten per job so recruiters always see a clean name
    cvp_pdf = os.path.join(HERE, "david_buchan_cv.pdf")
    cvp_md  = os.path.join(HERE, "david_buchan_cv.md")
    cvp_c   = os.path.join(HERE, "david_buchan_cover_letter.md")
    open(cvp_md, "w", encoding="utf-8").write(cv)
    open(cvp_c,  "w", encoding="utf-8").write(cover)
    try:
        cvpdf.md_to_pdf(cv, cvp_pdf)
    except Exception as e:
        print(f"PDF generation failed ({e}), CV saved as .md only")
        cvp_pdf = cvp_md
    store.update(job_id, cv_path=cvp_pdf, cover_path=cvp_c, cv_ready=1)
    return cvp_pdf

app = FastAPI(title="Job-Hunt Dashboard")
store.init()

@app.get("/", response_class=HTMLResponse)
def home(): return PAGE

@app.get("/api/jobs")
def api_jobs():
    jobs = store.all_jobs()
    pipeline = [j for j in jobs if j["status"] in ("applied", "rejected", "advanced")]
    active = [j for j in jobs if j["status"] not in ("applied", "rejected", "advanced")]
    return {"stack": [j for j in active if j["route"] == "stack"],
            "premium": [j for j in active if j["route"] == "premium"],
            "other": [j for j in active if j["route"] not in ("stack", "premium")],
            "pipeline": pipeline}

@app.post("/api/refresh")
def api_refresh():
    ingest(); score_and_autocv()
    return api_jobs()

@app.post("/api/generate_cv/{job_id:path}")
def api_generate_cv(job_id: str):
    if not store.get(job_id): return JSONResponse({"error": "not found"}, status_code=404)
    _make_cv(job_id)
    return store.get(job_id)

@app.post("/api/apply/{job_id:path}")
def api_apply(job_id: str):
    j = store.get(job_id)
    if not j: return JSONResponse({"error": "not found"}, status_code=404)
    if not j["cv_ready"]:
        return JSONResponse({"error": "CV not ready — generate it first"}, status_code=400)
    store.update(job_id, status="applied", applied_at=time.strftime("%Y-%m-%d %H:%M"))
    return {"ok": True, "url": j["url"], "cv_path": j["cv_path"], "cover_path": j["cover_path"],
            "note": "Assisted apply: posting opened; review the tailored CV/cover and submit on the site."}

@app.post("/api/status/{job_id:path}")
def api_status(job_id: str, body: dict = Body(...)):
    st = body.get("status", "")
    if st not in ("new", "applied", "rejected", "advanced"):
        return JSONResponse({"error": "bad status"}, status_code=400)
    store.update(job_id, status=st)
    return store.get(job_id)

@app.post("/api/sync_email")
def api_sync_email():
    import email_sync
    tracked = [(j["id"], j["company"]) for j in store.all_jobs() if j["status"] in ("applied", "advanced")]
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY"))
    res = email_sync.sync(tracked, llm=engine._call_llm if has_key else None)
    if not res.get("ok"):
        return res
    for u in res["updates"]:
        store.update(u["job_id"], status=u["status"], email_state=u["subject"])
    return {"ok": True, "updated": len(res["updates"]), "details": res["updates"],
            "message": "Pipeline updated from inbox (%d tagged). Rejected rows are flagged, never deleted." % len(res["updates"])}

@app.get("/api/autoapply_status")
def api_autoapply_status():
    return autoapply.status()

@app.post("/api/autoapply/{job_id:path}")
def api_autoapply_one(job_id: str):
    j = store.get(job_id)
    if not j: return JSONResponse({"error": "not found"}, status_code=404)
    if not autoapply.status()["enabled"]:
        return {"status": "disabled", "reason": "auto-apply OFF (set AUTOAPPLY_ENABLED=1)"}
    if not j["cv_ready"]:
        _make_cv(job_id); j = store.get(job_id)
    r = autoapply.apply_one(j, j.get("cv_path"), load_profile())
    if r["status"] == "submitted":
        store.update(job_id, status="applied", applied_at=time.strftime("%Y-%m-%d %H:%M"), notes="auto-applied")
    else:
        store.update(job_id, notes=r["status"] + ": " + r["reason"])
    return r

@app.post("/api/autoapply_stack")
def api_autoapply_stack():
    st = autoapply.status()
    out = {"enabled": st["enabled"], "dry_run": st["dry_run"], "submitted": 0, "dry_run_count": 0,
           "parked": 0, "error": 0, "details": []}
    if not st["enabled"]:
        out["message"] = "Auto-apply is OFF. Set AUTOAPPLY_ENABLED=1 (stays dry-run until AUTOAPPLY_DRY_RUN=0)."
        return out
    prof = load_profile()
    for j in store.all_jobs():
        if j["route"] != "stack" or j["status"] != "new":
            continue
        cur = autoapply.status()
        if cur["used_today"] >= cur["cap"]:
            out["message"] = f"Daily cap of {cur['cap']} reached ({cur['used_today']} submitted today)."
            break
        if not j["cv_ready"]:
            _make_cv(j["id"]); j = store.get(j["id"])
        r = autoapply.apply_one(j, j.get("cv_path"), prof)
        key = "dry_run_count" if r["status"] == "dry_run" else r["status"]
        out[key] = out.get(key, 0) + 1
        out["details"].append({"title": j["title"], **r})
        if r["status"] in ("submitted", "dry_run"):
            store.update(j["id"], status="applied", applied_at=time.strftime("%Y-%m-%d %H:%M"),
                         notes="auto-applied" if r["status"] == "submitted" else "dry-run")
        else:
            store.update(j["id"], notes=r["status"] + ": " + r["reason"])
    return out

@app.get("/api/cv/{job_id:path}")
def api_cv(job_id: str):
    j = store.get(job_id)
    if not j or not j.get("cv_path"):
        return HTMLResponse("<p>No CV generated yet.</p>", status_code=404)
    md_path = os.path.join(HERE, "david_buchan_cv.md")
    pdf_path = os.path.join(HERE, "david_buchan_cv.pdf")
    if os.path.exists(md_path):
        md = open(md_path, encoding="utf-8").read()
        return HTMLResponse("<pre style='white-space:pre-wrap;font:14px system-ui;max-width:800px;margin:40px auto;padding:0 16px'>"
                            + md.replace("&","&amp;").replace("<","&lt;") + "</pre>")
    if os.path.exists(pdf_path):
        return FileResponse(pdf_path, media_type="application/pdf", filename="david_buchan_cv.pdf")
    return HTMLResponse("<p>CV file not found — click Generate CV first.</p>", status_code=404)

PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><title>Job-Hunt Dashboard</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{--bg:#0f1115;--card:#181b22;--ink:#e9edf2;--mut:#9aa4b2;--acc:#4f8cff;--ok:#2fbf71;--warn:#e0a23b;--bad:#e0564b;--line:#262b34}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 system-ui,Segoe UI,Roboto,sans-serif}
header{padding:14px 22px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:12px;position:sticky;top:0;background:var(--bg);z-index:5}
header h1{font-size:17px;margin:0}.sp{flex:1}
.note{padding:7px 22px;background:#15181f;border-bottom:1px solid var(--line);color:var(--mut);font-size:12px}
button{background:var(--acc);color:#fff;border:0;border-radius:8px;padding:8px 12px;font-weight:600;cursor:pointer}
button.ghost{background:#222733;color:var(--ink);border:1px solid var(--line)}
button:disabled{background:#2a2f3a;color:#6b7480;cursor:not-allowed}
.cols{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;padding:18px;align-items:start}
.col h2{font-size:13px;margin:0 0 10px;color:var(--ink)}.col small{color:var(--mut);font-weight:400}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:13px;margin-bottom:11px}
.card h3{margin:0 0 2px;font-size:14px}.card .co{color:var(--mut);font-size:12.5px;margin-bottom:8px}
.badge{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:700}
.s-strong{background:rgba(47,191,113,.15);color:var(--ok)}.s-maybe{background:rgba(224,162,59,.15);color:var(--warn)}.s-weak{background:rgba(224,86,75,.15);color:var(--bad)}
.pill{font-size:11px;color:var(--mut);border:1px solid var(--line);border-radius:6px;padding:1px 6px;display:inline-block}
.row{display:flex;gap:8px;margin-top:9px;flex-wrap:wrap}.row a{color:var(--acc);font-size:12.5px;text-decoration:none;align-self:center}
.reasons{color:var(--mut);font-size:12px;margin-top:6px}.empty{color:#5b626d;font-size:13px;padding:8px}
#pipeline{padding:0 18px 24px}.pl{display:flex;gap:10px;align-items:center;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin-bottom:8px}
.dot{width:8px;height:8px;border-radius:50%}.applied{background:var(--acc)}.advanced{background:var(--ok)}.rejected{background:var(--bad)}
small{color:var(--mut)}select{background:#222733;color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:3px}
</style></head><body>
<header><h1>🛰️ Job-Hunt Dashboard</h1><span class="pill" id="summary"></span><span class="pill" id="aastate"></span><span class="pill" id="stamp"></span><span class="sp"></span>
<button class="ghost" onclick="syncEmail()">Sync email</button><button onclick="refresh()">↻ Refresh &amp; score</button></header>
<div class="note">Goal: maximise €/time. <b>Stack</b> = automatable + stackable (run several). <b>Premium</b> = pays enough to do one manually. Stacking several roles is cleanest with freelance/contract/part-time — full-time contracts often have exclusivity clauses.</div>
<div class="cols">
  <div class="col"><h2>♻ Stack &amp; automate <small>· best €/time</small> <button class="ghost" style="font-size:11px;padding:4px 8px" onclick="autoapplyAll()">⚡ Auto-apply all</button></h2><div id="stack"></div></div>
  <div class="col"><h2>💰 Premium <small>· worth doing manually</small></h2><div id="premium"></div></div>
  <div class="col"><h2>· Other</h2><div id="other"></div></div>
</div>
<h2 style="padding:0 18px;color:var(--mut);font-size:13px;text-transform:uppercase">📨 Pipeline</h2>
<div id="pipeline"></div>
<script>
const E=(s)=>document.querySelector(s);
function esc(x){return (x||'').toString().replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
function card(j){
  const ready=j.cv_ready==1; const isStack=j.route=='stack';
  const cvLink = ready?`<a href="#" onclick="viewCV('${j.id}');return false">view CV</a>`:'';
  let buttons;
  if(isStack){ buttons = `<button onclick="autoapply('${j.id}')">⚡ Auto-apply</button>`; }
  else { const gen = ready?'':`<button class="ghost" onclick="gen('${j.id}')">Generate CV</button>`;
         buttons = `${gen}<button ${ready?'':'disabled'} onclick="apply('${j.id}')">Apply (review)</button>`; }
  const head = j.route=='premium' ? `💰 pay ${j.pay_score}/100 ${j.tier}` : `💶 €/time ${j.value_score}/100 ${j.tier}`;
  const stk = j.stackable==1 ? `<span class="pill">♻ stackable</span>` : '';
  return `<div class="card"><h3>${esc(j.title)}</h3><div class="co">${esc(j.company)} · ${esc(j.location)||'—'}</div>
   <span class="badge s-${j.tier}">${head}</span>
   <span class="pill">🤖 auto ${j.auto_score}%</span> <span class="pill">fit ${j.score}</span> ${stk} <span class="pill">${esc(j.source)}</span>
   <div class="reasons">🤖 <b>automatable:</b> ${esc(j.automation_plan)}</div>
   <div class="row">${buttons}${cvLink}<a href="${esc(j.url)}" target="_blank">posting ↗</a></div></div>`;
}
function plRow(j){
  return `<div class="pl"><span class="dot ${j.status}"></span><b>${esc(j.title)}</b><small>· ${esc(j.company)} · ${j.status}${j.applied_at?(' · '+j.applied_at):''}</small><span style="flex:1"></span>
   <select onchange="setStatus('${j.id}',this.value)"><option ${j.status=='applied'?'selected':''}>applied</option>
   <option ${j.status=='advanced'?'selected':''}>advanced</option><option ${j.status=='rejected'?'selected':''}>rejected</option></select>
   ${j.status=='rejected'?`<a href="https://mail.google.com/mail/u/0/#search/${encodeURIComponent(j.company)}" target="_blank">Open in Gmail</a>`:''}</div>`;
}
async function load(){
  const d=await (await fetch('/api/jobs')).json();
  E('#stack').innerHTML=d.stack.map(card).join('')||'<div class="empty">Nothing yet — hit Refresh.</div>';
  E('#premium').innerHTML=d.premium.map(card).join('')||'<div class="empty">—</div>';
  E('#other').innerHTML=d.other.map(card).join('')||'<div class="empty">—</div>';
  E('#pipeline').innerHTML=d.pipeline.map(plRow).join('')||'<div class="empty">No applications yet.</div>';
  E('#summary').textContent=`stack ${d.stack.length} · premium ${d.premium.length} · tracked ${d.pipeline.length}`;
  try{const a=await (await fetch('/api/autoapply_status')).json();
    E('#aastate').textContent='auto-apply: '+(a.enabled?(a.dry_run?'DRY-RUN':'LIVE'):'OFF')+` ${a.used_today}/${a.cap}`;}catch(e){}
  E('#stamp').textContent='updated '+new Date().toLocaleTimeString();
}
async function autoapply(id){const r=await (await fetch('/api/autoapply/'+encodeURIComponent(id),{method:'POST'})).json();alert('Auto-apply: '+(r.status||'')+(r.reason?(' — '+r.reason):''));load()}
async function autoapplyAll(){const r=await (await fetch('/api/autoapply_stack',{method:'POST'})).json();alert(r.message?r.message:`Auto-apply stack → submitted ${r.submitted}, dry-run ${r.dry_run_count}, parked ${r.parked}`);load()}
async function refresh(){E('#stamp').textContent='scoring…';await fetch('/api/refresh',{method:'POST'});load()}
async function gen(id){E('#stamp').textContent='tailoring CV…';await fetch('/api/generate_cv/'+encodeURIComponent(id),{method:'POST'});load()}
async function apply(id){const r=await (await fetch('/api/apply/'+encodeURIComponent(id),{method:'POST'})).json();if(r.url)window.open(r.url,'_blank');alert(r.note||'Applied');load()}
async function setStatus(id,st){await fetch('/api/status/'+encodeURIComponent(id),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:st})});load()}
async function viewCV(id){window.open('/api/cv/'+encodeURIComponent(id),'_blank')}
async function syncEmail(){const r=await (await fetch('/api/sync_email',{method:'POST'})).json();alert(r.message||'synced');load()}
load();
</script></body></html>"""
