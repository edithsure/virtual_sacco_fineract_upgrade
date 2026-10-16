import sqlite3
from datetime import datetime

"""Simple double-entry accounting helpers and payment allocation.

This module provides:
- init_accounting_tables(conn)
- create_journal(conn, description)
- post_journal_entry(conn, journal_id, account_code, debit, credit, reference=None)
- post_payment(conn, member_id, kind, amount, reference=None)
- allocate_payment_to_loan(conn, loan_id, amount)

Notes:
- This is intentionally simple: journals + journal_entries store debits/credits.
- The application `transactions` table remains for UI; we add corresponding journal entries.
"""

DEFAULT_ACCOUNTS = {
    "savings_liability": "LIAB:SA",
    "cash": "ASSET:CASH",
    "loan_principal": "ASSET:LOAN_PRINCIPAL",
    "loan_interest_income": "INCOME:INTEREST",
    "interest_receivable": "ASSET:INT_REC",
    "prepayments": "LIAB:PREPAY",
}


def init_accounting_tables(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS accounts (
      code TEXT PRIMARY KEY, name TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS journals (
      id INTEGER PRIMARY KEY AUTOINCREMENT, description TEXT, created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS journal_entries (
      id INTEGER PRIMARY KEY AUTOINCREMENT, journal_id INTEGER NOT NULL,
      account_code TEXT NOT NULL, debit REAL NOT NULL DEFAULT 0, credit REAL NOT NULL DEFAULT 0,
      reference TEXT, created_at TEXT NOT NULL,
      FOREIGN KEY(journal_id) REFERENCES journals(id), FOREIGN KEY(account_code) REFERENCES accounts(code)
    );
    CREATE TABLE IF NOT EXISTS external_payments (
      id INTEGER PRIMARY KEY AUTOINCREMENT, provider TEXT NOT NULL, external_id TEXT NOT NULL,
      member_id INTEGER, amount REAL NOT NULL, received_at TEXT NOT NULL, reconciled INTEGER NOT NULL DEFAULT 0
    );
        CREATE TABLE IF NOT EXISTS installments (
            id INTEGER PRIMARY KEY AUTOINCREMENT, loan_id INTEGER NOT NULL, due_date TEXT NOT NULL,
            principal_due REAL NOT NULL DEFAULT 0, interest_due REAL NOT NULL DEFAULT 0,
            principal_paid REAL NOT NULL DEFAULT 0, interest_paid REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'due', created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS installments (
            id INTEGER PRIMARY KEY AUTOINCREMENT, loan_id INTEGER NOT NULL, due_date TEXT NOT NULL,
            principal_due REAL NOT NULL DEFAULT 0, interest_due REAL NOT NULL DEFAULT 0,
            principal_paid REAL NOT NULL DEFAULT 0, interest_paid REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'due', created_at TEXT NOT NULL,
            FOREIGN KEY(loan_id) REFERENCES loans(id)
        );
    """)
    # ensure default accounts exist
    for code, name in DEFAULT_ACCOUNTS.items():
        acct_code = DEFAULT_ACCOUNTS[code]
        try:
            cur.execute("INSERT OR IGNORE INTO accounts(code,name) VALUES(?,?)", (acct_code, name))
        except Exception:
            cur.execute("INSERT OR IGNORE INTO accounts(code,name) VALUES(?,?)", (acct_code, name))
    conn.commit()


def create_journal(conn: sqlite3.Connection, description: str) -> int:
    cur = conn.cursor()
    cur.execute("INSERT INTO journals(description,created_at) VALUES(?,?)", (description, datetime.now().isoformat()))
    conn.commit()
    return cur.lastrowid


def post_journal_entry(conn: sqlite3.Connection, journal_id: int, account_code: str, debit: float = 0.0, credit: float = 0.0, reference: str = None):
    cur = conn.cursor()
    cur.execute("INSERT INTO journal_entries(journal_id,account_code,debit,credit,reference,created_at) VALUES(?,?,?,?,?,?)",
                (journal_id, account_code, round(float(debit or 0), 2), round(float(credit or 0), 2), reference, datetime.now().isoformat()))
    conn.commit()


def post_payment(conn: sqlite3.Connection, member_id: int, kind: str, amount: float, reference: str = None):
    """Post a member-facing payment into the journal and the transactions UI table.

    kind: 'deposit'|'withdrawal'|'loan_repayment'
    """
    amount = round(float(amount), 2)
    description = f"{kind.title()} by member {member_id}"
    journal_id = create_journal(conn, description)

    # Basic allocations:
    # - deposit: debit cash, credit savings liability
    # - withdrawal: debit savings liability, credit cash
    # - loan_repayment: debit cash, credit loan principal/interest allocation (handled separately)
    if kind == "deposit":
        post_journal_entry(conn, journal_id, DEFAULT_ACCOUNTS["cash"], debit=amount, reference=reference)
        post_journal_entry(conn, journal_id, DEFAULT_ACCOUNTS["savings_liability"], credit=amount, reference=reference)
    elif kind == "withdrawal":
        post_journal_entry(conn, journal_id, DEFAULT_ACCOUNTS["savings_liability"], debit=amount, reference=reference)
        post_journal_entry(conn, journal_id, DEFAULT_ACCOUNTS["cash"], credit=amount, reference=reference)
    elif kind == "loan_repayment":
        # create a cash debit first; allocation to interest/principal happens when matching loans
        post_journal_entry(conn, journal_id, DEFAULT_ACCOUNTS["cash"], debit=amount, reference=reference)
        # temporarily credit prepayments until allocation occurs
        post_journal_entry(conn, journal_id, DEFAULT_ACCOUNTS["prepayments"], credit=amount, reference=reference)
    else:
        raise ValueError("Unsupported payment kind")

    # also record a user-facing transaction for compatibility with the existing UI
    conn.execute("INSERT INTO transactions(user_id,kind,amount,reference,note,created_at) VALUES(?,?,?,?,?,?)",
                 (member_id, kind, amount, reference or f"TX-{datetime.now().strftime('%Y%m%d%H%M%S%f')}", None, datetime.now().isoformat(timespec="seconds")))
    conn.commit()


def allocate_payment_to_loan(conn: sqlite3.Connection, loan_id: int, amount: float):
    """Allocate an amount (from prepayments) to a loan's principal and interest.

    Very simple allocation: first pay interest_receivable, then principal.
    """
    cur = conn.cursor()
    amount = round(float(amount), 2)
    # fetch loan
    loan = cur.execute("SELECT * FROM loans WHERE id=?", (loan_id,)).fetchone()
    if not loan:
        raise ValueError("Loan not found")

    # Allocate to oldest unpaid installments: interest first, then principal
    journal_id = create_journal(conn, f"Allocation to loan {loan_id}")
    remaining = amount
    cur = conn.cursor()
    rows = cur.execute("SELECT * FROM installments WHERE loan_id=? AND (principal_paid < principal_due OR interest_paid < interest_due) ORDER BY due_date ASC", (loan_id,)).fetchall()
    for inst in rows:
        if remaining <= 0:
            break
        interest_due = round(inst["interest_due"] - inst["interest_paid"], 2)
        pay_interest = round(min(remaining, interest_due), 2)
        if pay_interest > 0:
            post_journal_entry(conn, journal_id, DEFAULT_ACCOUNTS["prepayments"], debit=pay_interest, reference=f"LN-{loan_id}")
            post_journal_entry(conn, journal_id, DEFAULT_ACCOUNTS["loan_interest_income"], credit=pay_interest, reference=f"LN-{loan_id}")
            cur.execute("UPDATE installments SET interest_paid = interest_paid + ? WHERE id=?", (pay_interest, inst["id"]))
            remaining = round(remaining - pay_interest, 2)

        if remaining <= 0:
            break
        principal_due = round(inst["principal_due"] - inst["principal_paid"], 2)
        pay_principal = round(min(remaining, principal_due), 2)
        if pay_principal > 0:
            post_journal_entry(conn, journal_id, DEFAULT_ACCOUNTS["prepayments"], debit=pay_principal, reference=f"LN-{loan_id}")
            post_journal_entry(conn, journal_id, DEFAULT_ACCOUNTS["loan_principal"], credit=pay_principal, reference=f"LN-{loan_id}")
            cur.execute("UPDATE installments SET principal_paid = principal_paid + ? WHERE id=?", (pay_principal, inst["id"]))
            remaining = round(remaining - pay_principal, 2)

        # update installment status
        cur.execute("UPDATE installments SET status = CASE WHEN principal_paid >= principal_due AND interest_paid >= interest_due THEN 'paid' ELSE 'partial' END WHERE id=?", (inst["id"],))

    # if any remaining amount after allocation, keep as prepayment (already credited to prepayments)
    conn.commit()


def record_external_payment(conn: sqlite3.Connection, provider: str, external_id: str, member_id: int, amount: float):
    cur = conn.cursor()
    cur.execute("INSERT INTO external_payments(provider,external_id,member_id,amount,received_at) VALUES(?,?,?,?,?)",
                (provider, external_id, member_id, round(float(amount), 2), datetime.now().isoformat()))
    conn.commit()


def add_months(dt: datetime, months: int) -> datetime:
    """Add months to a date (approximate month arithmetic)."""
    year = dt.year + (dt.month - 1 + months) // 12
    month = (dt.month - 1 + months) % 12 + 1
    day = min(dt.day, 28)
    return datetime(year, month, day)


def generate_installments(conn: sqlite3.Connection, loan_id: int, principal: float, term_months: int, annual_rate: float = 0.12, start_date: datetime = None):
    """Generate a simple amortization schedule (level-payment) and insert into `installments`.

    Payments rounded to 2 decimals; last payment adjusted for rounding.
    """
    if start_date is None:
        start_date = datetime.now()
    r = annual_rate / 12.0
    n = int(term_months)
    P = float(principal)
    if r == 0:
        payment = round(P / n, 2)
    else:
        payment = round(P * (r / (1 - (1 + r) ** (-n))), 2)

    # clear any existing installments for the loan
    cur = conn.cursor()
    cur.execute("DELETE FROM installments WHERE loan_id=?", (loan_id,))

    remaining = P
    installments = []
    for i in range(1, n + 1):
        due = add_months(start_date, i)
        if r == 0:
            interest = 0.00
            principal_portion = round(payment, 2) if i < n else round(remaining, 2)
        else:
            interest = round(remaining * r, 2)
            principal_portion = round(payment - interest, 2)
            if i == n:
                # last payment adjust
                principal_portion = round(remaining, 2)
                payment = round(principal_portion + interest, 2)

        remaining = round(remaining - principal_portion, 2)
        installments.append((loan_id, due.isoformat(), principal_portion, interest, 0.0, 0.0, 'due', datetime.now().isoformat()))

    cur.executemany("INSERT INTO installments(loan_id,due_date,principal_due,interest_due,principal_paid,interest_paid,status,created_at) VALUES(?,?,?,?,?,?,?,?)", installments)
    conn.commit()


def reverse_entries_by_reference(conn: sqlite3.Connection, reference: str) -> int:
    """Create reversal journal entries for all entries with a given reference.

    Returns the reversal journal id.
    """
    cur = conn.cursor()
    rows = cur.execute("SELECT journal_id, account_code, debit, credit FROM journal_entries WHERE reference=?", (reference,)).fetchall()
    if not rows:
        return 0
    rev_journal = create_journal(conn, f"Reversal of {reference}")
    for r in rows:
        acct = r[1]
        debit = float(r[2] or 0)
        credit = float(r[3] or 0)
        # reverse: debit<->credit
        post_journal_entry(conn, rev_journal, acct, debit=credit, credit=debit, reference=f"REV-{reference}")
    conn.commit()
    return rev_journal


def export_external_payments_csv(conn: sqlite3.Connection):
    """Return CSV string of external_payments for export."""
    import io, csv
    cur = conn.cursor()
    rows = cur.execute("SELECT id,provider,external_id,member_id,amount,received_at,reconciled FROM external_payments ORDER BY received_at DESC").fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "provider", "external_id", "member_id", "amount", "received_at", "reconciled"])
    for r in rows:
        writer.writerow([r[0], r[1], r[2], r[3], r[4], r[5], r[6]])
    return output.getvalue()
