# Apache Fineract integration — developer scaffold

## What this upgrade does

- Adds a Python HTTP client for Apache Fineract.
- Adds an administrator-only `/admin/fineract` page that checks the Fineract health endpoint and reads configured loan products.
- Reads connection settings from environment variables; credentials are not hard-coded in the integration module.
- Keeps the existing web app operational while making the integration boundary explicit.

## What it does NOT do yet

This integration keeps the existing local workflow in place while the Fineract connection is validated. Fineract is not yet the source of truth for member loans, balances, savings, or accounting data. The current Fineract screen is read-only. Before enabling write operations, complete the security, accounting, regulatory, and operational review steps outlined below.

## Prerequisites

- Python 3.11+ recommended for this application.
- Apache Fineract and its PostgreSQL databases deployed separately using the official, version-pinned Fineract deployment instructions.
- A configured Fineract tenant and at least one test loan product.

Official resources:
- https://fineract.apache.org/
- https://fineract.apache.org/docs/stable/
- https://github.com/apache/fineract

The official repository's quick start currently describes Java, PostgreSQL, and local development commands. Its Docker images are explicitly intended for development/test convenience; do not treat the default compose configuration or default credentials as production-ready.

## Run the web app

1. Create and activate a Python virtual environment.
2. Install dependencies: `python -m pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and set secure values. The current Flask app does not automatically load `.env`; export variables in your shell or use a reviewed environment loader in local development.
4. Start the web app with `python app.py`.
5. Start/configure Fineract independently and verify its health endpoint.
6. Sign in as an administrator and visit `/admin/fineract`.

Windows PowerShell example for setting variables in the current terminal:

```powershell
$env:FINERACT_BASE_URL = "https://localhost:8443/fineract-provider"
$env:FINERACT_USERNAME = "mifos"
$env:FINERACT_PASSWORD = "YOUR_LOCAL_TEST_PASSWORD"
$env:FINERACT_TENANT_ID = "default"
$env:FINERACT_VERIFY_TLS = "false" # local self-signed TLS only
python app.py
```

Never use a default password or disable TLS verification in production.

## Production architecture and mandatory work

1. **System of record:** Fineract owns financial loan/savings state and accounting. The web app must not independently calculate or mutate official balances.
2. **Identity mapping:** add a durable mapping between SACCO member IDs and Fineract client IDs; never rely on matching by email/name alone.
3. **Loan lifecycle:** configure products, eligibility, approval steps, disbursement, repayment schedules, arrears, write-offs, rescheduling, guarantors, and audit requirements for each SACCO policy.
4. **Idempotency and reconciliation:** payment callbacks must be authenticated, deduplicated, replay-safe, and reconciled to Fineract journal entries and provider statements.
5. **Security:** replace default administrative credentials; enforce MFA for privileged roles, secure session/cookie settings, CSRF protection, rate limits, least-privilege service accounts, secrets management, TLS, security logging, and independent penetration testing.
6. **Data and availability:** use managed/high-availability PostgreSQL, tested backups and point-in-time recovery, disaster recovery drills, monitoring, alerting, tracing, capacity tests, and a documented incident response plan.
7. **Kenya compliance:** obtain legal/compliance advice on the SACCO's licensing and governance obligations, data protection, KYC/AML, consumer disclosures, records retention, and payment-provider agreements before launch.
8. **Scale:** load test realistic concurrent users and peak transactions. Use a queue for asynchronous notifications/reconciliation, caching only for non-authoritative reads, and horizontal web/API scaling behind a load balancer.
9. **Migration:** reconcile every legacy SQLite member, loan and transaction against approved source records before cutover; retain immutable migration evidence and rollback plans.
10. **Independent review:** financial accountant, SACCO operations owner, security engineer, and Kenya legal/compliance advisor sign off before live funds are handled.

## Safe next integration milestones

- Milestone 1: connectivity and read-only loan-product display (implemented here).
- Milestone 2: sandbox member/client mapping and read-only member/loan views.
- Milestone 3: sandbox loan application and approval workflow with strict authorization and duplicate-request protection.
- Milestone 4: payment provider sandbox, callback verification, ledger reconciliation and failure recovery.
- Milestone 5: security review, operational runbooks, performance/recovery testing and controlled pilot.

Do not skip the sandbox and reconciliation milestones.
