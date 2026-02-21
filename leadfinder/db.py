import sqlite3
from datetime import datetime

from .models import Lead
from .utils import ensure_parent_dir, write_csv


class LeadStore:
    def __init__(self, path: str):
        self.path = path

    def connect(self):
        ensure_parent_dir(self.path)
        return sqlite3.connect(self.path)

    def init_db(self) -> None:
        with self.connect() as con:
            con.execute(
                '''
                CREATE TABLE IF NOT EXISTS leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL DEFAULT '',
                    phone TEXT NOT NULL DEFAULT '',
                    website TEXT NOT NULL DEFAULT '',
                    city TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT '',
                    category TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                )
                '''
            )
            con.execute(
                '''
                CREATE UNIQUE INDEX IF NOT EXISTS leads_unique
                ON leads (name, city, website)
                '''
            )

    def upsert(self, lead: Lead) -> None:
        with self.connect() as con:
            con.execute(
                '''
                INSERT INTO leads (name, email, phone, website, city, source, category, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name, city, website) DO UPDATE SET
                    email = CASE WHEN excluded.email != '' THEN excluded.email ELSE leads.email END,
                    phone = CASE WHEN excluded.phone != '' THEN excluded.phone ELSE leads.phone END,
                    source = CASE WHEN excluded.source != '' THEN excluded.source ELSE leads.source END,
                    category = CASE WHEN excluded.category != '' THEN excluded.category ELSE leads.category END
                ''',
                (
                    lead.name,
                    lead.email or "",
                    lead.phone or "",
                    lead.website or "",
                    lead.city or "",
                    lead.source or "",
                    lead.category or "",
                    lead.created_at.isoformat(),
                ),
            )

    def fetch_all(self):
        with self.connect() as con:
            rows = con.execute(
                "SELECT name, email, phone, website, city, source, category, created_at FROM leads ORDER BY created_at DESC"
            ).fetchall()
        leads = []
        for r in rows:
            created = datetime.fromisoformat(r[7]) if r[7] else datetime.utcnow()
            leads.append(
                Lead(
                    name=r[0],
                    email=r[1] or None,
                    phone=r[2] or None,
                    website=r[3] or None,
                    city=r[4] or None,
                    source=r[5] or None,
                    category=r[6] or None,
                    created_at=created,
                )
            )
        return leads

    def export_csv(self, path: str) -> None:
        leads = self.fetch_all()
        write_csv(path, leads)
