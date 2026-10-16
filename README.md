# Virtual SACCO Fineract Upgrade

This project is a Flask-based SACCO member portal and accounting workflow application. It includes member registration, savings and withdrawal tracking, loan applications, admin review, and a basic accounting ledger with simulated M-Pesa-style payment reconciliation.

## How David can access the project

David can work on the same project by cloning the GitHub repository:

```powershell
git clone https://github.com/edithsure/virtual_sacco_fineract_upgrade.git
cd .\virtual_sacco_fineract_upgrade
```

After cloning, he can run the setup helper:

```powershell
.\setup_project.ps1
```

Then start the app:

```powershell
.\start_app.ps1
```

This repository is already connected to the GitHub remote and the main branch is tracked as `origin/main`.

## Repository layout

- `sacco_fineract_upgrade/` — application code
- `sacco_fineract_upgrade/app.py` — Flask app and routes
- `sacco_fineract_upgrade/services/` — accounting and Fineract integration helpers
- `sacco_fineract_upgrade/templates/` — HTML templates
- `sacco_fineract_upgrade/static/` — CSS and JavaScript
- `sacco_fineract_upgrade/scripts/` — migration and DB helper scripts

## Requirements

- Python 3.10+
- Git
- Windows, macOS, or Linux terminal

## Local setup

From the project root:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r .\sacco_fineract_upgrade\requirements.txt
```

Then start the app:

```powershell
Set-Location .\sacco_fineract_upgrade
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

## Default admin account

The app creates the default admin user automatically on first run.

- Email: `admin@mwangaza.sacco`
- Password: `Admin123!`

## Environment variables

Copy the example file and adjust values for your local environment:

```powershell
Copy-Item .\sacco_fineract_upgrade\.env.example .\sacco_fineract_upgrade\.env
```

Then edit `.env` and set:

- `SECRET_KEY`
- `FINERACT_BASE_URL`
- `FINERACT_USERNAME`
- `FINERACT_PASSWORD`
- `FINERACT_TENANT_ID`
- `FINERACT_VERIFY_TLS`
- `FINERACT_TIMEOUT_SECONDS`

## Working on the project

1. Clone the repo.
2. Create the venv and install dependencies.
3. Run the app.
4. Create/checkout a feature branch.
5. Make changes and commit.
6. Push to GitHub.

Example:

```powershell
git checkout -b feature/my-change
```

## Useful commands

```powershell
# Activate the environment
.\.venv\Scripts\Activate.ps1

# Run the app
Set-Location .\sacco_fineract_upgrade
python app.py

# Check git status
git status

# See the current branch
git branch
```

## Notes for contributors

- Do not commit real secrets or production credentials.
- Keep `.env` local and untracked.
- The SQLite database file is intentionally ignored for local development.
- The project is built for local/demo/dev validation; do not treat it as production-ready without review and hardening.

## Related docs

- `sacco_fineract_upgrade/FINERACT_INTEGRATION.md`
- `sacco_fineract_upgrade/.env.example`

