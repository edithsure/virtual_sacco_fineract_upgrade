import sqlite3
import os

DB = os.path.join(os.path.dirname(__file__), '..', 'sacco.db')
DB = os.path.abspath(DB)

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
print('DB:', DB)
r = conn.execute("SELECT id,provider,external_id,member_id,amount,received_at,reconciled FROM external_payments ORDER BY id DESC LIMIT 1").fetchone()
print('external:', dict(r) if r else None)
rows = conn.execute("SELECT id,user_id,kind,amount,reference,created_at FROM transactions ORDER BY id DESC LIMIT 5").fetchall()
print('transactions:')
for row in rows:
    print(dict(row))
