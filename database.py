import sqlite3
from typing import List, Tuple

class STTDatabase:
    """Some magic DB bs for saving current/future data."""
    def __init__(self, path="stt_data.sqlite"):
        self.conn = sqlite3.connect(path)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS transcripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                timestamp REAL NOT NULL,
                text TEXT NOT NULL,
                processed INTEGER DEFAULT 0
                UNIQUE(username, text)
            )
        """)
        self.conn.commit()

    def store_transcript(self, username: str, timestamp: float, text: str):
        """Stores transcript in the database. Skips duplicate entries."""
        try:
            self.conn.execute(
                "INSERT OR IGNORE INTO transcripts (username, timestamp, text) VALUES (?, ?, ?)",
                (username, timestamp, text)
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            pass  # duplicate text, skip

    def get_unprocessed(self, limit=100) -> List[Tuple[int, str, float, str]]:
        """Returns unprocessed transcripts. (id?, username, timestamp, text)"""
        cur = self.conn.execute(
            "SELECT id, username, timestamp, text FROM transcripts WHERE processed = 0 LIMIT ?",
            (limit,)
        )
        return cur.fetchall()

    def mark_processed(self, ids: List[int]):
        """Marks transcripts of ids in passed list as processed."""
        self.conn.executemany(
            "UPDATE transcripts SET processed = 1 WHERE id = ?",
            [(i,) for i in ids]
        )
        self.conn.commit()

    def close(self):
        """Close database connection."""
        self.conn.close()
