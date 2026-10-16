# Mwangaza Virtual SACCO

A web-based member portal for savings management, loan applications, and operational review workflows.

## Overview
- Responsive landing page and member portal
- Member registration and sign-in with secure password hashing
- Savings deposits and withdrawals with balance validation
- Loan application submission and administration review
- Ledger tracking and member activity reporting
- Automatic SQLite database setup on first run

## Quick start
1. Install Python 3.10 or newer.
2. Open a terminal in this folder.
3. Create and activate a virtual environment:
   - Windows: `py -m venv .venv` then `.venv\Scripts\activate`
   - macOS/Linux: `python3 -m venv .venv` then `source .venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Start the app: `python app.py`
6. Open `http://127.0.0.1:5000`

The system administrator account is created automatically on first startup.

## Administrator access
- Email: `admin@mwangaza.sacco`
- Password: `Admin123!`

Change the administrator password as part of setup and keep the account restricted to authorized staff.

## Operational notes
This application manages member-facing savings and loan records in a local operational ledger. It is designed to support workflow review and system integration testing with a clear separation between member activity and administrative controls.

## Project structure
- `app.py` — routes, authentication, database logic, and workflows
- `templates/` — member and admin pages
- `static/css/style.css` — interface styling
- `static/js/main.js` — client-side interactions

## Apache Fineract integration

The system includes an administrator-only Fineract status page at `/admin/fineract` for connection validation and reading configured product metadata. See `FINERACT_INTEGRATION.md` and `.env.example` for configuration details and integration planning.
