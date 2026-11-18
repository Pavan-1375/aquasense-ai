# AquaSense AI deployment

The application is configured to fail closed in production. It will not start with development secrets, SQLite, HTTP URLs, localhost CORS origins, or simulated email/SMS providers.

## Required external accounts

Create a PostgreSQL database with any provider that supports a standard PostgreSQL connection string. Create an SMTP account for email and a Twilio-compatible SMS account for OTP delivery. Free tiers may impose quotas or require sender/recipient verification; no service can automatically provide unlimited free credentials.

Put the real values in the hosting provider's secret manager or an untracked `.env`. Do not create a file containing real API keys and do not commit secrets to GitHub.

## Run the production stack

1. Copy `.env.production.example` to `.env`.
2. Replace every placeholder.
3. Configure DNS and HTTPS at the reverse proxy or hosting platform.
4. Run `docker compose up --build`.
5. Apply migrations with `docker compose exec api alembic upgrade head`.
6. Check `/api/health`; it must report database `ok` and model service `available`.

Password recovery sends through SMTP or Twilio in production. Development-only reset links and OTPs are never returned when `APP_ENV=production`.

Provider failover is intentionally not automatic across unrelated vendors: silently switching providers can misroute messages and create duplicate OTPs. Configure provider-level retry/backup routing at the vendor or add a second adapter with verified credentials and an explicit policy.
