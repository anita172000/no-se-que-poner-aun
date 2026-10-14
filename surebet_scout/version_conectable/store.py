"""Persistencia local en SQLite (un único archivo). Sin secretos."""
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Store:
    def __init__(self, path):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.lock = threading.RLock()
        with self.lock, self.db:
            self.db.executescript("""
                CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT);
                CREATE TABLE IF NOT EXISTS opportunities (id TEXT PRIMARY KEY, found_at TEXT, data TEXT);
                CREATE TABLE IF NOT EXISTS operations (id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT, data TEXT);
            """)

    def get_kv(self, key, default=None):
        with self.lock:
            row = self.db.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set_kv(self, key, value):
        with self.lock, self.db:
            self.db.execute("INSERT OR REPLACE INTO kv VALUES (?, ?)", (key, json.dumps(value)))

    def replace_opportunities(self, opps):
        ts = now_iso()
        with self.lock, self.db:
            self.db.execute("DELETE FROM opportunities")
            self.db.executemany("INSERT INTO opportunities VALUES (?, ?, ?)",
                                [(o["id"], ts, json.dumps({**o, "found_at": ts})) for o in opps])

    def opportunities(self):
        with self.lock:
            rows = self.db.execute("SELECT data FROM opportunities").fetchall()
        return sorted((json.loads(r[0]) for r in rows), key=lambda o: -o["margin"])

    def opportunity(self, opp_id):
        with self.lock:
            row = self.db.execute("SELECT data FROM opportunities WHERE id=?", (opp_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def add_operation(self, op):
        with self.lock, self.db:
            cur = self.db.execute("INSERT INTO operations (created_at, data) VALUES (?, ?)",
                                  (op["created_at"], "{}"))
            op["id"] = cur.lastrowid
            self.db.execute("UPDATE operations SET data=? WHERE id=?", (json.dumps(op), op["id"]))
        return op

    def save_operation(self, op):
        with self.lock, self.db:
            self.db.execute("UPDATE operations SET data=? WHERE id=?", (json.dumps(op), op["id"]))

    def operation(self, op_id):
        with self.lock:
            row = self.db.execute("SELECT data FROM operations WHERE id=?", (op_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def operations(self):
        with self.lock:
            rows = self.db.execute("SELECT data FROM operations ORDER BY id DESC").fetchall()
        return [json.loads(r[0]) for r in rows]
