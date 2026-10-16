import os, sqlite3
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash
from services.fineract_client import FineractClient, FineractError
from services import accounting

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "sacco.db")
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-development-secret-before-deployment")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT, full_name TEXT NOT NULL,
      email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
      role TEXT NOT NULL DEFAULT 'member', created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS transactions (
      id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
      kind TEXT NOT NULL CHECK(kind IN ('deposit','withdrawal','loan_repayment','loan_disbursement')),
      amount REAL NOT NULL CHECK(amount > 0), reference TEXT,
      note TEXT, created_at TEXT NOT NULL,
      FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS loans (
      id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
      amount REAL NOT NULL CHECK(amount > 0), purpose TEXT NOT NULL,
      term_months INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
      admin_note TEXT, created_at TEXT NOT NULL,
      FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """)
    # Default administrator account is created only if the email does not already exist.
    row = conn.execute("SELECT id FROM users WHERE email = ?", ("admin@mwangaza.sacco",)).fetchone()
    if not row:
        conn.execute("INSERT INTO users(full_name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)",
          ("SACCO Administrator", "admin@mwangaza.sacco", generate_password_hash("Admin123!"), "admin", datetime.now().isoformat(timespec="seconds")))
    # initialize accounting tables and default accounts
    try:
        accounting.init_accounting_tables(conn)
    except Exception:
        # best-effort: ignore if accounting tables already exist or fail during CI
        pass
    conn.commit()
    conn.close()

@app.before_request
def load_user():
    g.user = None
    if session.get("user_id"):
        g.user = db().execute("SELECT id,full_name,email,role,created_at FROM users WHERE id=?", (session["user_id"],)).fetchone()

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not g.user:
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not g.user:
            return redirect(url_for("login"))
        if g.user["role"] != "admin":
            flash("Administrator access is required.", "danger")
            return redirect(url_for("dashboard"))
        return fn(*args, **kwargs)
    return wrapper

def money(value):
    return f"KSh {float(value or 0):,.2f}"
app.jinja_env.filters["money"] = money

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 8:
            flash("Enter your name and email, and use a password of at least 8 characters.", "danger")
            return render_template("register.html")
        try:
            cur = db().execute("INSERT INTO users(full_name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)",
                (name, email, generate_password_hash(password), "member", datetime.now().isoformat(timespec="seconds")))
            db().commit()
            session["user_id"] = cur.lastrowid
            flash("Welcome to your SACCO account.", "success")
            return redirect(url_for("dashboard"))
        except sqlite3.IntegrityError:
            flash("An account with that email already exists.", "danger")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            flash("You are signed in.", "success")
            return redirect(url_for("dashboard"))
        flash("Email or password was not recognised.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have signed out.", "info")
    return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    conn = db()
    transactions = conn.execute("SELECT * FROM transactions WHERE user_id=? ORDER BY id DESC LIMIT 8", (g.user["id"],)).fetchall()
    loans = conn.execute("SELECT * FROM loans WHERE user_id=? ORDER BY id DESC LIMIT 5", (g.user["id"],)).fetchall()
    totals = conn.execute("""SELECT
      COALESCE(SUM(CASE WHEN kind='deposit' THEN amount WHEN kind='loan_repayment' THEN 0 WHEN kind='withdrawal' THEN -amount ELSE 0 END),0) AS savings
      FROM transactions WHERE user_id=?""", (g.user["id"],)).fetchone()
    active_loans = conn.execute("SELECT COALESCE(SUM(amount),0) AS total FROM loans WHERE user_id=? AND status='approved'", (g.user["id"],)).fetchone()["total"]
    return render_template("dashboard.html", transactions=transactions, loans=loans,
        savings=totals["savings"], active_loans=active_loans)

@app.route("/savings", methods=["GET", "POST"])
@login_required
def savings():
    if request.method == "POST":
        action = request.form.get("action")
        try:
            amount = round(float(request.form.get("amount", "0")), 2)
        except ValueError:
            amount = 0
        note = request.form.get("note", "").strip()[:200]
        if amount <= 0 or amount > 10000000:
            flash("Enter an amount greater than zero and within the allowed system limit.", "danger")
            return redirect(url_for("savings"))
        conn = db()
        balance = conn.execute("""SELECT COALESCE(SUM(CASE WHEN kind='deposit' THEN amount WHEN kind='withdrawal' THEN -amount ELSE 0 END),0) b
                                  FROM transactions WHERE user_id=?""", (g.user["id"],)).fetchone()["b"]
        if action == "withdrawal":
            if amount > balance:
                flash("Insufficient available savings for this withdrawal.", "danger")
                return redirect(url_for("savings"))
            kind = "withdrawal"
        else:
            kind = "deposit"
        reference = f"VS-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        # use accounting module to post entries and keep transactions table in sync
        accounting.post_payment(conn, g.user["id"], kind, amount, reference=reference)
        flash(f"{kind.title()} recorded in the ledger.", "success")
        return redirect(url_for("savings"))
    rows = db().execute("SELECT * FROM transactions WHERE user_id=? AND kind IN ('deposit','withdrawal') ORDER BY id DESC", (g.user["id"],)).fetchall()
    balance = db().execute("""SELECT COALESCE(SUM(CASE WHEN kind='deposit' THEN amount WHEN kind='withdrawal' THEN -amount ELSE 0 END),0) b
                              FROM transactions WHERE user_id=?""", (g.user["id"],)).fetchone()["b"]
    return render_template("savings.html", transactions=rows, balance=balance)

@app.route("/loans", methods=["GET", "POST"])
@login_required
def loans():
    if request.method == "POST":
        try:
            amount = round(float(request.form.get("amount", "0")), 2)
            term = int(request.form.get("term_months", "0"))
        except ValueError:
            amount, term = 0, 0
        purpose = request.form.get("purpose", "").strip()[:300]
        if amount <= 0 or amount > 5000000 or term not in [1,3,6,9,12,18,24] or len(purpose) < 5:
            flash("Check the amount, purpose and repayment term.", "danger")
            return redirect(url_for("loans"))
        db().execute("INSERT INTO loans(user_id,amount,purpose,term_months,status,created_at) VALUES(?,?,?,?,?,?)",
            (g.user["id"], amount, purpose, term, "pending", datetime.now().isoformat(timespec="seconds")))
        db().commit()
        flash("Loan application submitted for review.", "success")
        return redirect(url_for("loans"))
    rows = db().execute("SELECT * FROM loans WHERE user_id=? ORDER BY id DESC", (g.user["id"],)).fetchall()
    return render_template("loans.html", loans=rows)


@app.route("/admin/fineract")
@admin_required
def fineract_status():
    """Admin-only, read-only status page for the Fineract integration."""
    client = FineractClient()
    health = client.health()
    products = []
    product_error = None
    if health.get("ok"):
        try:
            products = client.get_loan_products()
        except FineractError as exc:
            product_error = str(exc)
    return render_template("fineract_status.html", health=health, products=products, product_error=product_error)

@app.route("/admin")
@admin_required
def admin():
    conn = db()
    members = conn.execute("SELECT id,full_name,email,role,created_at FROM users ORDER BY id DESC").fetchall()
    pending = conn.execute("""SELECT loans.*, users.full_name, users.email FROM loans JOIN users ON users.id=loans.user_id
                              WHERE loans.status='pending' ORDER BY loans.id ASC""").fetchall()
    totals = conn.execute("""SELECT
      COALESCE(SUM(CASE WHEN kind='deposit' THEN amount ELSE 0 END),0) deposits,
      COALESCE(SUM(CASE WHEN kind='withdrawal' THEN amount ELSE 0 END),0) withdrawals
      FROM transactions""").fetchone()
    return render_template("admin.html", members=members, pending=pending, totals=totals)

@app.route("/admin/loan/<int:loan_id>/<decision>", methods=["POST"])
@admin_required
def decide_loan(loan_id, decision):
    if decision not in ("approved", "rejected"):
        flash("Invalid decision.", "danger")
        return redirect(url_for("admin"))
    conn = db()
    loan = conn.execute("SELECT * FROM loans WHERE id=? AND status='pending'", (loan_id,)).fetchone()
    if not loan:
        flash("That loan is no longer pending.", "warning")
        return redirect(url_for("admin"))
    note = request.form.get("admin_note", "").strip()[:200]
    conn.execute("UPDATE loans SET status=?, admin_note=? WHERE id=?", (decision, note, loan_id))
    if decision == "approved":
        # create accounting entries for loan disbursement: debit loan asset, credit cash
        try:
            journal_id = accounting.create_journal(conn, f"Loan disbursement {loan_id}")
            accounting.post_journal_entry(conn, journal_id, accounting.DEFAULT_ACCOUNTS["loan_principal"], debit=loan["amount"], reference=f"LN-{loan_id}")
            accounting.post_journal_entry(conn, journal_id, accounting.DEFAULT_ACCOUNTS["cash"], credit=loan["amount"], reference=f"LN-{loan_id}")
        except Exception:
            # fallback: still insert a transaction if accounting fails
            pass
        conn.execute("INSERT INTO transactions(user_id,kind,amount,reference,note,created_at) VALUES(?,?,?,?,?,?)",
            (loan["user_id"], "loan_disbursement", loan["amount"], f"LN-{loan_id}", "Approved loan", datetime.now().isoformat(timespec="seconds")))
        # generate amortization schedule for the loan (default annual rate 12%)
        try:
            accounting.generate_installments(conn, loan_id, loan["amount"], loan["term_months"], annual_rate=0.12, start_date=datetime.fromisoformat(loan["created_at"]))
        except Exception:
            # ignore schedule creation failures for now
            pass
    conn.commit()
    flash(f"Loan application {decision}.", "success")
    return redirect(url_for("admin"))

@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", message="We couldn't find that page."), 404


@app.route("/webhook/mpesa", methods=["POST"])
def mpesa_webhook():
    """Simple simulator endpoint for incoming payment notifications.

    Expected JSON: {"external_id":"abc123","email":"member@example.com","amount":1000}
    """
    data = request.get_json() or {}
    provider = data.get("provider", "mpesa")
    external_id = data.get("external_id") or data.get("transaction_id")
    amount = float(data.get("amount", 0))
    email = data.get("email")
    conn = db()
    member_id = None
    if email:
        row = conn.execute("SELECT id FROM users WHERE email=?", (email.strip().lower(),)).fetchone()
        if row:
            member_id = row["id"]

    # record external payment then optionally post it as a deposit
    accounting.record_external_payment(conn, provider, external_id or f"ext-{datetime.now().timestamp()}", member_id, amount)
    if member_id:
        # post as a deposit and mark as reconciled
        accounting.post_payment(conn, member_id, "deposit", amount, reference=external_id)
        conn.execute("UPDATE external_payments SET reconciled=1 WHERE external_id=?", (external_id,))
        conn.commit()
    return ("", 204)


@app.route("/admin/reconciliation")
@admin_required
def reconciliation():
    conn = db()
    rows = conn.execute("SELECT * FROM external_payments ORDER BY received_at DESC").fetchall()
    return render_template("reconciliation.html", payments=rows)


@app.route('/admin/reconciliation/match', methods=['POST'])
@admin_required
def reconcile_match():
    external_id = request.form.get('external_id')
    conn = db()
    row = conn.execute('SELECT * FROM external_payments WHERE external_id=?', (external_id,)).fetchone()
    if not row:
        flash('External payment not found.', 'danger')
        return redirect(url_for('reconciliation'))
    if row['reconciled']:
        flash('Already reconciled.', 'info')
        return redirect(url_for('reconciliation'))
    # if member_id present, post as deposit
    if row['member_id']:
        try:
            accounting.post_payment(conn, row['member_id'], 'deposit', row['amount'], reference=row['external_id'])
            conn.execute('UPDATE external_payments SET reconciled=1 WHERE external_id=?', (external_id,))
            conn.commit()
            flash('Payment matched and posted.', 'success')
        except Exception as e:
            flash(f'Failed to post payment: {e}', 'danger')
    else:
        flash('No member associated with this external payment.', 'warning')
    return redirect(url_for('reconciliation'))


@app.route('/admin/reconciliation/unmatch', methods=['POST'])
@admin_required
def reconcile_unmatch():
    external_id = request.form.get('external_id')
    conn = db()
    row = conn.execute('SELECT * FROM external_payments WHERE external_id=?', (external_id,)).fetchone()
    if not row:
        flash('External payment not found.', 'danger')
        return redirect(url_for('reconciliation'))
    if not row['reconciled']:
        flash('Payment is not reconciled.', 'info')
        return redirect(url_for('reconciliation'))
    # NOTE: This is a simple unmatch: it will not reverse journal entries automatically.
    conn.execute('UPDATE external_payments SET reconciled=0 WHERE external_id=?', (external_id,))
    conn.commit()
    flash('Payment unreconciled. Journal reversal not performed automatically.', 'warning')
    return redirect(url_for('reconciliation'))

if __name__ == "__main__":
    init_db()
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1")
