import sqlite3, os, sys

# Ensure the project package root is on sys.path so `services` imports resolve
BASE = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, BASE)
from services import accounting

# Use the same DB path as the application
DB = os.path.join(BASE, 'sacco.db')

def migrate():
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA foreign_keys = ON")
    accounting.init_accounting_tables(conn)
    print('Migration complete')

if __name__ == '__main__':
    migrate()
