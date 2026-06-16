import sqlite3, json
from datetime import datetime

DB_PATH = "consensus_ai.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS queries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        query_text TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        successful_models INTEGER DEFAULT 0,
        total_models INTEGER DEFAULT 5,
        broadcast_time REAL,
        responses_json TEXT,
        ranked_json TEXT,
        consensus_answer TEXT,
        conversation_id TEXT
    )''')
    # Add conversation_id to existing DB if missing
    try:
        c.execute("ALTER TABLE queries ADD COLUMN conversation_id TEXT")
        conn.commit()
    except Exception:
        pass  # Column already exists
    c.execute('''CREATE TABLE IF NOT EXISTS account (
        id INTEGER PRIMARY KEY,
        name TEXT DEFAULT 'AI Researcher',
        email TEXT DEFAULT '',
        organization TEXT DEFAULT '',
        avatar_color TEXT DEFAULT '#6366f1',
        created_at TEXT,
        total_queries INTEGER DEFAULT 0
    )''')
    c.execute("SELECT COUNT(*) FROM account")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO account VALUES (1,'AI Researcher','','','#6366f1',?,0)",
                  (datetime.now().isoformat(),))
    conn.commit(); conn.close()

def save_query(query_text, successful_models, total_models, broadcast_time,
               responses_json, ranked_json, consensus_answer, conversation_id=None):
    conn = get_conn(); c = conn.cursor()
    c.execute('''INSERT INTO queries (query_text,timestamp,successful_models,total_models,
                 broadcast_time,responses_json,ranked_json,consensus_answer,conversation_id)
                 VALUES (?,?,?,?,?,?,?,?,?)''',
              (query_text, datetime.now().isoformat(), successful_models, total_models,
               broadcast_time, json.dumps(responses_json), json.dumps(ranked_json),
               consensus_answer, conversation_id))
    qid = c.lastrowid
    c.execute("UPDATE account SET total_queries=total_queries+1 WHERE id=1")
    conn.commit(); conn.close()
    return qid

def get_history(page=1, per_page=25):
    conn = get_conn(); c = conn.cursor()
    offset = (page-1)*per_page
    c.execute('''SELECT id,query_text,timestamp,successful_models,total_models,broadcast_time,consensus_answer
                 FROM queries ORDER BY timestamp DESC LIMIT ? OFFSET ?''', (per_page, offset))
    rows = [dict(r) for r in c.fetchall()]
    c.execute("SELECT COUNT(*) FROM queries")
    total = c.fetchone()[0]
    conn.close()
    return {"items": rows, "total": total}

def get_query(qid):
    conn = get_conn(); c = conn.cursor()
    c.execute("SELECT * FROM queries WHERE id=?", (qid,))
    row = c.fetchone(); conn.close()
    if not row: return None
    d = dict(row)
    d['responses_json'] = json.loads(d['responses_json'] or '[]')
    d['ranked_json']    = json.loads(d['ranked_json']    or '[]')
    return d

def delete_query(qid):
    conn = get_conn(); c = conn.cursor()
    c.execute("DELETE FROM queries WHERE id=?", (qid,))
    ok = c.rowcount > 0
    conn.commit(); conn.close()
    return ok

def get_account():
    conn = get_conn(); c = conn.cursor()
    c.execute("SELECT * FROM account WHERE id=1")
    row = c.fetchone(); conn.close()
    return dict(row) if row else {}

def update_account(name=None, email=None, organization=None, avatar_color=None):
    fields, vals = [], []
    for k,v in [("name",name),("email",email),("organization",organization),("avatar_color",avatar_color)]:
        if v is not None:
            fields.append(f"{k}=?"); vals.append(v)
    if fields:
        conn = get_conn(); c = conn.cursor()
        c.execute(f"UPDATE account SET {','.join(fields)} WHERE id=1", vals)
        conn.commit(); conn.close()

def get_stats():
    conn = get_conn(); c = conn.cursor()
    c.execute("SELECT COUNT(*) as total, AVG(broadcast_time) as avg_time, AVG(successful_models) as avg_success FROM queries")
    row = c.fetchone(); conn.close()
    return dict(row) if row else {"total":0,"avg_time":0,"avg_success":0}
