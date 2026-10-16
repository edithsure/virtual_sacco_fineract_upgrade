import sys, os, traceback
BASE_SCRIPT = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_SCRIPT)
# ensure project root is on sys.path so `services` imports resolve
sys.path.insert(0, PROJECT_ROOT)
DB = os.path.join(PROJECT_ROOT, 'sacco.db')
print('PROJECT_ROOT=', PROJECT_ROOT)
print('DB=', DB)
try:
    import sqlite3
    from services import accounting
    conn = sqlite3.connect(DB)
    conn.execute('PRAGMA foreign_keys = ON')
    accounting.init_accounting_tables(conn)
    print('MIGRATE_OK')
except Exception:
    traceback.print_exc()
    print('MIGRATE_FAILED')
