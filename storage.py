"""Small SQLite repository; owner checks are part of every query."""
import sqlite3
from contextlib import contextmanager
from uuid import uuid4


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


class Store:
    def __init__(self, path):
        self.path = path
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, title TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
                CREATE INDEX IF NOT EXISTS conversation_owner ON conversations(owner);
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY, conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL, content TEXT NOT NULL,
                    FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys = ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def _owned(self, db, owner, cid):
        row = db.execute('SELECT * FROM conversations WHERE id=? AND owner=?', (cid, owner)).fetchone()
        if not row:
            raise NotFound()
        return dict(row)

    def list(self, owner):
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                'SELECT id,title,created_at FROM conversations WHERE owner=? ORDER BY created_at DESC,rowid DESC',
                (owner,))]

    def create(self, owner, title):
        cid = uuid4().hex
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            count = db.execute('SELECT COUNT(*) FROM conversations WHERE owner=?', (owner,)).fetchone()[0]
            if count >= 50:
                raise Conflict('Delete a conversation before creating another (limit 50).')
            db.execute('INSERT INTO conversations(id,owner,title) VALUES(?,?,?)', (cid, owner, title))
        return self.get(owner, cid)

    def get(self, owner, cid):
        with self.connect() as db:
            conversation = self._owned(db, owner, cid)
            conversation['messages'] = [dict(row) for row in db.execute(
                'SELECT role,content FROM messages WHERE conversation_id=? ORDER BY id', (cid,))]
            return conversation

    def rename(self, owner, cid, title):
        with self.connect() as db:
            self._owned(db, owner, cid)
            db.execute('UPDATE conversations SET title=? WHERE id=? AND owner=?', (title, cid, owner))
        return self.get(owner, cid)

    def delete(self, owner, cid):
        with self.connect() as db:
            self._owned(db, owner, cid)
            db.execute('DELETE FROM conversations WHERE id=? AND owner=?', (cid, owner))

    def append_turn(self, owner, cid, version, message, reply):
        with self.connect() as db:
            result = db.execute(
                'UPDATE conversations SET version=version+1 WHERE id=? AND owner=? AND version=?',
                (cid, owner, version))
            if result.rowcount != 1:
                raise Conflict('Conversation changed while replying; reload and try again.')
            db.executemany('INSERT INTO messages(conversation_id,role,content) VALUES(?,?,?)',
                           [(cid, 'user', message), (cid, 'assistant', reply)])
