import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "x1_data.db"
print(f"DB: {DB_PATH}  存在: {DB_PATH.exists()}  大小: {DB_PATH.stat().st_size if DB_PATH.exists() else 0}")

conn = sqlite3.connect(str(DB_PATH))
tables = [r[0] for r in conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table'"
).fetchall()]
print("表:", tables)
conn.close()