# RecycleProof

A runnable local MVP for explainable review of e-waste recycling claims. It provides two-stage email OTP authentication, private evidence uploads (local development or genuine S3), manual source-field correction, text extraction for text-based PDFs, deterministic verification checks, persisted verification history, and human review decisions. Automated results are **review signals, not proof of fraud**.

## Repository

- `frontend/` — React, Vite, TypeScript, Tailwind interface.
- `backend/app/` — FastAPI routes, SQLAlchemy models, real/demo auth, private storage, Gemini document extraction and verification engine.
- `backend/app/demo_data.py` and `demo_service.py` — deterministic fictional claims, source PDFs and session-scoped serializers.
- `backend/seed_demo_assets.py` / `cleanup_demo_sessions.py` — idempotent seed and expired/revoked demo-session cleanup commands.
- `backend/tests/` — pytest tests for authentication, demo isolation, verification, authorization, storage and uploads.
- `.env.example` — safe configuration template. Actual secrets belong in ignored `backend/.env` or hosting environment settings.

## Requirements

Python 3.11+, Node 20+, npm. From the repository root:

```bash
cp .env.example backend/.env
# Edit backend/.env. Generate a JWT secret with: python -c "import secrets; print(secrets.token_urlsafe(48))"
python3 -m venv backend/.venv
. backend/.venv/bin/activate
pip install -r backend/requirements.txt
cd backend
set -a; . ./.env; set +a
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

In another terminal:

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0
```

Open <http://localhost:5173>; OpenAPI docs are at <http://localhost:8000/docs>. The SQLite DB and local uploads are created on first use. To recreate after a data reset, stop the backend and remove `backend/recycleproof.db` and `backend/uploads/` manually.

## Authentication / SMTP

Real sign-in follows user ID + password, then a cryptographically random six-digit OTP emailed to the registered address. Passwords use salted scrypt; OTPs are hashed at rest, expire after five minutes, are single-use and limited to five wrong attempts. Login, OTP, resend, and registration endpoints have basic process-local rate limits. JWT secret and expiry are configurable. SMTP is not required for the app to start; `/api/health` reports its actual readiness, and attempting real OTP delivery without configuration returns a setup diagnostic.

For Gmail: enable Google 2-Step Verification; create an **App Password** in Google Account security (use that 16-character app password, not the normal account password); set `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, `SMTP_USERNAME` and `SMTP_FROM_EMAIL` to the Gmail address, `SMTP_PASSWORD` to the app password, and `SMTP_USE_TLS=true`; restart backend, then check `/api/health`. To test delivery, register with an inbox you control and sign in. Verify the message arrives and the emailed code works; the app does not claim delivery until SMTP succeeds.

Local-only no-SMTP testing: set `APP_ENV=development` and explicitly `DEV_OTP_ENABLED=true`; then restart. The API includes `dev_otp` only for this opt-in non-production configuration and prints a local diagnostic. Do **not** enable this setting in a production environment. It is disabled by default.

## Gemini document extraction

The backend uses the official `google-genai` SDK to extract explicit, structured
fields from uploaded invoices, shipment manifests and other accepted evidence. Set
`GEMINI_API_KEY` in the ignored `backend/.env`; it is never read by the frontend or
returned by an API response. The default model is `gemini-2.5-flash` and can be
overridden with `GEMINI_MODEL` if the configured account uses another available
Gemini model. `GEMINI_TIMEOUT_SECONDS` defaults to 30.

Extraction is nullable and schema-validated: missing or uncertain fields remain
missing. Uploads are retained when Gemini is unconfigured, times out, exhausts
quota, returns an API error, or produces malformed data; their extraction status
explains why manual field correction is needed. Before verification, only missing
claim inputs are filled from typed extraction results. The existing deterministic
verification engine remains authoritative for checks and findings, including
document references and compared values. Automated findings are review signals,
not proof of misconduct.

## S3

Default `STORAGE_PROVIDER=local` is explicitly labelled local development storage. To use real S3, create a private bucket in your AWS region with block-public-access enabled and configure a narrowly scoped IAM identity/role permitting only `s3:PutObject`, `s3:GetObject` (and optionally `s3:DeleteObject`) for the app's bucket/prefix. Prefer an IAM role or AWS standard credential chain. For a local workstation, use a dedicated profile (`aws configure --profile recycleproof`) and `AWS_PROFILE=recycleproof`; avoid long-lived keys where possible. If keys are unavoidable, supply them only through the backend process environment or secret manager, never React or Git.

Set `STORAGE_PROVIDER=s3`, `AWS_REGION`, and `S3_BUCKET`; provide AWS credentials via the standard chain/IAM role. The existing private bucket needs `s3:ListBucket` for the live `HeadBucket` check and `s3:GetObject`/`s3:PutObject` limited to the app and `demo-assets/seed/*` prefixes. For the demo, the first session runs a live bucket check and idempotently uploads 26 synthetic, searchable PDFs under `demo-assets/seed/` with server-side AES256 encryption and no public ACL. Evidence is downloaded only through a demo-session-authorized backend route; the browser receives no AWS credentials or public object URL. `GET /api/demo/status` reports AWS as connected only after a live bucket check. An S3 failure rejects session setup or evidence retrieval—there is no local fallback.

To seed those same sample objects before the first visitor (safe to repeat): `cd backend && python seed_demo_assets.py`. This requires the configured AWS credentials when S3 is selected. This project does not create a bucket or change its Block Public Access settings; enable and verify those on the existing bucket.

## One-click demo data and commands

The public landing page's **Explore Interactive Demo** button calls `POST /api/demo/session`; no registration, password, SMTP, or OTP is involved. The backend creates a cryptographically random, signed demo identity (default lifetime: two hours), plus five fictional claims and linked source documents in separate demo-only tables. Its short-lived bearer token has a distinct signing key and `demo` scope, is kept in `rp_demo_token`, and is never sent to real-user claim APIs. Existing `rp_token` authentication remains untouched. Demo records, reports and review decisions are always queried by the current demo-session ID. There are no demo uploads. **Reset demo** replaces only the current session's records; **Exit demo** revokes that session.

The workspace opens the 500-tonne / 320-tonne quantity case first. Inspect its invoice, shipment and weighbridge PDFs, run the backend verifier, and see the resulting 180-tonne discrepancy and cited evidence. The five inputs cover a consistent claim, quantity discrepancy, duplicate shipment reference, expired permit, and facility/chronology mismatch. Findings are generated by `verify_claim`, not precomputed in the page. All organizations, dates, references and records are fictional.

`DEMO_SESSION_TTL_MINUTES` configures lifetime (default `120`; accepted range 5–480). Public creation is limited to 8 sessions per client IP per hour; verification to 12 runs per session per hour; resets to 4 per hour. Limits are process-local for this MVP. Expired sessions are rejected and marked revoked on the next authenticated request. Clean expired/revoked database namespaces periodically (shared seed evidence is retained):

```bash
cd backend
python seed_demo_assets.py       # optional; idempotent local seed or private-S3 seed
python cleanup_demo_sessions.py # removes expired/revoked database records only
pytest -q
```

The older `seed_demo.py` remains for the prior local OTP example and creates an ordinary fictional user with ordinary claims; it is **not** used by the public one-click demo. Do not use that legacy account as the public demo identity. Pytest exercises local storage and mocked S3 behavior, not a real AWS or SMTP integration.

Frontend production build:

```bash
cd frontend
npm run build
```

## API

`/docs` documents registration, two-stage login, resend/logout/current user, claims/list/search/detail/update, uploads/listing/secure downloads, user-confirmed extracted fields, verification runs/reports, review decisions, dashboard, storage status and health. Demo routes include `POST /api/demo/session`, `GET /api/demo/status`, `GET /api/demo/claims`, `GET /api/demo/claims/{id}`, authorized PDF download, `POST /api/demo/claims/{id}/analyze`, `POST /api/demo/claims/{id}/review`, `POST /api/demo/reset`, and `POST /api/demo/session/revoke`. Demo routes require the distinct demo bearer credential; normal private routes still require a real-user bearer token.

Accepted evidence types are PDF, JPEG and PNG with signature validation and a configurable 15 MB default limit. Text-based PDF extraction is attempted; scans/images require manual field entry (optional OCR provider is not wired in this MVP). This app does not infer missing facts, independently certify permits, or apply a universal process energy-per-tonne assumption. Material balance is checked only when all required source values are supplied. Capacity plausibility is unavailable unless trustworthy capacity evidence is added; no unsupported assumptions are fabricated.

## Three-minute demo run-of-show

1. Open `/` and click **Explore Interactive Demo**. No account or email is needed.
2. The `/demo` workspace opens with **DEMO MODE — SYNTHETIC DATA** and preselects the quantity-discrepancy case.
3. Inspect its fictional invoice and shipment manifest, then select **Run Verification**. The backend compares 500 tonnes with 320 tonnes and reports a 180-tonne difference with supporting document references.
4. Expand the finding to inspect values, evidence links and the recommended next action.
5. Record **Mark for Further Review**, then **Reset demo**; the original five scenarios return and this session's reports/reviews are cleared.
6. Exit the demo. The demo credential is revoked; any existing real-user token remains separate.
7. Use **Sign In** only to exercise the regular password + email OTP flow. Local `DEV_OTP_ENABLED=true` is an explicit development-only substitute; SMTP is not needed by the public demo.

## Security / production notes

This is an MVP, not a production security assessment. Before production use, provide a high-entropy JWT secret, HTTPS, managed secrets, persistent database/backups, durable rate limiting, CSRF/session strategy if switching from bearer tokens, audit logging/retention, malware scanning, content-disposition hardening, IAM review, and operational monitoring. SQLite and in-memory rate limiting are intended for local demonstration only. No SMTP or AWS test is claimed unless verified against configured live credentials.

## Public entry page

The public landing page is served at `/`; its primary action starts the protected-by-scope demo at `/demo`, and **Sign In** continues at `/login` with registration at `/register`. Successful real-user OTP authentication opens the same protected dashboard and claim workflows as before. The demo workspace is a separate session-isolated path and does not submit demo evidence to real-user claim endpoints.
