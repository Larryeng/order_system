import sqlite3
from flask import g
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "orders.db")

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

def init_db():
    db = sqlite3.connect(DB_PATH)
    cursor = db.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT,
            items TEXT,
            total_price INTEGER,
            status TEXT,
            created_at TEXT
        )
    """)
    db.commit()
    db.close()
