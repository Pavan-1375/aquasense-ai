# No-card backend deployment with Hugging Face Spaces

Create a new Hugging Face Space using the **Docker** SDK and select the free CPU hardware. Upload the repository contents, set the Space Dockerfile to `Dockerfile.huggingface`, and add the production secrets in the Space Settings → Variables and secrets panel.

Required secrets:

- `APP_ENV=production`
- `SECRET_KEY`
- `DEVICE_INGEST_KEY`
- `DATABASE_URL` (Neon PostgreSQL URL using `postgresql+psycopg://`)
- `APP_BASE_URL` (the Vercel frontend URL)
- `CORS_ORIGINS` (the Vercel frontend URL)
- `EMAIL_PROVIDER=smtp`
- `EMAIL_FROM`
- `SMTP_HOST`
- `SMTP_PORT=587`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_USE_TLS=true`

The Space URL becomes the backend URL. Free Spaces can sleep when idle; the first request after sleeping may take longer. No card details are required for the free CPU tier.
