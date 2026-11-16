import sqlite3
from datetime import datetime, timezone
from pathlib import Path

db_path = Path("C:/Users/Student/.gemini/antigravity/scratch/dropkit/dropkit.db")
conn = sqlite3.connect(db_path)
now = datetime.now(timezone.utc).isoformat()
conn.execute("""
    INSERT INTO system_settings (key, value, updated_at)
    VALUES ('base_url', 'https://dropkit.com', ?)
    ON CONFLICT(key) DO UPDATE SET value = 'https://dropkit.com', updated_at = ?
""", (now, now))
conn.commit()
r = conn.execute("SELECT key, value FROM system_settings WHERE key = 'base_url'").fetchone()
print("Saved setting:", r)
conn.close()
