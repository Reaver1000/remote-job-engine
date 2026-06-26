"""SQLite persistence for the job-hunt dashboard."""
import sqlite3, os, time

DB = os.environ.get("JOBHUNT_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "jobhunt.db"))

COLUMNS = [
    ("id","TEXT PRIMARY KEY"),("source","TEXT"),("company","TEXT"),("title","TEXT"),
    ("url","TEXT"),("location","TEXT"),("score","INTEGER DEFAULT 0"),
    ("auto_score","INTEGER DEFAULT 0"),("pay_score","INTEGER DEFAULT 0"),("value_score","INTEGER DEFAULT 0"),
    ("stackable","INTEGER DEFAULT 0"),("route","TEXT DEFAULT ''"),("combined","INTEGER DEFAULT 0"),
    ("tier","TEXT DEFAULT ''"),("reasons","TEXT DEFAULT ''"),
    ("automation_plan","TEXT DEFAULT ''"),("cv_path","TEXT"),("cover_path","TEXT"),
    ("cv_ready","INTEGER DEFAULT 0"),("status","TEXT DEFAULT 'new'"),
    ("found_at","TEXT"),("applied_at","TEXT"),("email_state","TEXT DEFAULT ''"),("notes","TEXT DEFAULT ''"),
]

def _conn():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; return c

def init():
    cols = ", ".join(f"{n} {d}" for n, d in COLUMNS)
    with _conn() as c:
        c.execute(f"CREATE TABLE IF NOT EXISTS jobs({cols})")
        existing = {r[1] for r in c.execute("PRAGMA table_info(jobs)")}
        for n, d in COLUMNS:                       # migrate older DBs
            if n not in existing:
                try: c.execute(f"ALTER TABLE jobs ADD COLUMN {n} {d}")
                except Exception: pass

def upsert(job):
    with _conn() as c:
        if c.execute("SELECT 1 FROM jobs WHERE id=?", (job["id"],)).fetchone():
            return
        c.execute("""INSERT INTO jobs(id,source,company,title,url,location,found_at,status)
                     VALUES(?,?,?,?,?,?,?, 'new')""",
                  (job["id"], job.get("source",""), job.get("company",""), job.get("title",""),
                   job.get("url",""), job.get("location",""), time.strftime("%Y-%m-%d %H:%M")))

def update(job_id, **fields):
    if not fields: return
    cols = ", ".join(f"{k}=?" for k in fields)
    with _conn() as c:
        c.execute(f"UPDATE jobs SET {cols} WHERE id=?", (*fields.values(), job_id))

def get(job_id):
    with _conn() as c:
        r = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return dict(r) if r else None

def all_jobs():
    with _conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM jobs ORDER BY combined DESC, found_at DESC")]
