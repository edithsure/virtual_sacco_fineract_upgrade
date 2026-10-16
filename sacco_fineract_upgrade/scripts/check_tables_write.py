import os, sqlite3
BASE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE)
DB = os.path.join(PROJECT_ROOT, 'sacco.db')
out = os.path.join(BASE, 'tables_out.txt')
try:
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    rows = cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    with open(out, 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(r[0] + "\n")
    print('WROTE', out)
except Exception as e:
    with open(out, 'w', encoding='utf-8') as f:
        f.write('ERROR:' + str(e))
    print('ERROR_WRITTEN')
