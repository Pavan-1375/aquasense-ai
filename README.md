# AquaSense AI (HydroInsight)

HydroInsight is a schema-driven water quality and groundwater monitoring dashboard. The active quality screening profile uses four configured parameters:

- pH
- TDS (ppm)
- turbidity (NTU)
- temperature (°C)

## Final project objectives

1. Develop a machine-learning-assisted system for groundwater-quality assessment using key water-quality parameters.
2. Monitor borewell water levels through IoT-based sensing and analyze temporal variations to assess potential groundwater-depletion risks.
3. Design and implement an integrated platform for groundwater monitoring, data management, visualization, and intelligent analysis.
4. Enhance monitoring reliability and accountability through data validation, monitoring controls, auditability, and systematic reporting.

The active artifact is a compatible Extra Trees classifier trained on 300 four-parameter records. Its classes are derived from the documented screening formula, not independent laboratory labels, so it is a screening aid and not a potability certification.

## Run

```bash
npm install
npm run dev
```

For a reproducible container stack, review the included `docker-compose.yml`. It starts PostgreSQL, runs the Alembic baseline before the API, and serves the Vite build through Nginx. Replace the example database password and secret before using it outside local development.

## Important production boundary

The UI describes predictions as four-parameter sensor-based screening. It does not claim potability and explicitly notes that bacteriological, nitrate, fluoride, hardness and heavy-metal parameters are not measured. The backend rejects inference requests unless the feature vector matches pH, TDS, turbidity and temperature in the expected order and ranges. `ml/quality_inference.py` provides that validation.

## Prototype account and location flow

- Users must sign up or sign in before entering the workspace. Development assigns the first account `admin`. Production requires `BOOTSTRAP_ADMIN_EMAIL` to match the initial administrator account; later registrations are standard users.
- The map is a Leaflet map with street, satellite, and terrain tile layers. Users can select a precise point or two-corner area, search a city/address manually, request browser geolocation, and see country, state, district, and city/town fields for a selected place.
- Search uses OpenStreetMap Nominatim only after the user submits a place query. Reverse-geocoding a precise map-selected coordinate is an explicit `Identify area` action rather than an automatic background request.
- The browser requests live location through `navigator.geolocation`, watches for updates, and uses the current coordinates as the test site.
- Quality inputs are editable numeric fields. A user submission stores pH, TDS, turbidity and temperature, timestamp, role, and live coordinates, then appears in the admin inbox.
- Bright/dark preference is stored in the browser; accounts, sessions, locations, observations, reviews, alerts and reports are persisted by the FastAPI backend database.

## Full-stack backend

The project now includes a FastAPI backend under `backend/`. It uses SQLAlchemy and SQLite by default, and can use PostgreSQL by changing `DATABASE_URL` in `backend/.env`.

PowerShell setup:

```powershell
py -3 -m pip install -r backend/requirements.txt
Copy-Item backend/.env.example backend/.env
py -3 backend/scripts/seed_demo.py
py -3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend
```

Open `http://127.0.0.1:8000/docs` for the OpenAPI contract. The API includes protected sign-up/sign-in, stations, devices, measurements, water quality, dashboard data, alerts, deterministic local advisor responses, CSV/PDF reports, and a WebSocket at `/api/ws/measurements`. The frontend shows `API online` when the health endpoint is reachable and falls back to its local workspace data when it is not.

## Account, reminders and submissions

- New registration collects full name, email, international mobile number, password confirmation, and optional weekly-reminder consent. Configure `BOOTSTRAP_ADMIN_EMAIL` in production before creating the first account; it is only used while no active administrator exists.
- Email and mobile verification endpoints are available at `/api/verification/request` and `/api/verification/confirm`. Development mode returns a short-lived code for testing and explicitly does not claim that a message was delivered.
- `Submit monitoring data` stores groundwater or water-quality values as a versioned `SubmissionBatch`. Draft, Submitted, Under Review, Approved, Rejected, and Correction Requested states are persisted. Original values remain unchanged, validation warnings are stored, and attachments are size/type validated.
- `My submissions` only queries the signed-in user's records. The administrator-only Data Management page reads `/api/admin/stats` and `/api/admin/submissions`, and backend review routes enforce approval permissions.
- Weekly reminders are stored in `ReminderSchedule` and processed by the FastAPI background worker. Idempotency keys prevent duplicate delivery for the same user, channel, and scheduled period. Development mode records `simulated` deliveries; configure email/SMS providers before enabling real delivery.

The new persistence tables are created additively by SQLAlchemy startup initialization for local development: contacts, verification codes, reminder schedules, notification deliveries, submission batches, attachments, review history, data-quality results, model execution records and ingestion receipts. Existing users, stations, devices, measurements and quality records are preserved. Production deployments should run the Alembic baseline with `SCHEMA_AUTO_CREATE=false`.

Useful endpoints include:

```text
POST /api/submissions
GET  /api/submissions/mine
POST /api/submissions/{id}/attachments
POST /api/submissions/{id}/correction
GET  /api/reminders
PUT  /api/reminders
GET  /api/notifications
GET  /api/admin/stats
GET  /api/admin/submissions
POST /api/admin/submissions/{id}/review
```

## ESP32 and dataset integration

- `backend/bridge/serial_bridge.py` reads newline-delimited JSON from a configurable COM port and forwards validated payloads to `/api/ingest/http`.
- `iot/esp32_water_level_example.ino` shows the additive JSON serial integration. It does not replace the existing OLED firmware.
- `backend/scripts/import_dataset.py <path-to-csv>` inspects datetime, station and groundwater-level candidates before any import mapping is applied.
- `ml/artifacts/` contains the active four-parameter quality artifact and clearly separated historical artifacts. Groundwater forecasting currently uses a labelled transparent temporal-trend baseline until a compatible trained groundwater artifact is configured.
- `backend/migrations/` contains the non-destructive Alembic baseline, and `backend/scripts/run_worker.py` runs reminder work independently of the API when a separate process is preferred.

The frontend reads `VITE_API_URL` from the environment; `.env.example` contains the local default. CI is configured in `.github/workflows/ci.yml` for the frontend build, backend compilation and service tests.

## Verification

```powershell
npm run build
$env:PYTHONPATH = "backend"
py -3 -m unittest discover -s backend/tests -v
py -3 -m compileall -q backend
Set-Location backend; py -3 -m alembic check; Set-Location ..
```

The demo seed is clearly labelled and must not be presented as live hardware data. Production deployment still requires a real `SECRET_KEY`, PostgreSQL or managed database, device-specific keys, HTTPS, configured email/SMS providers, sender registration and consent handling, secure file storage, a rate-limit/reverse-proxy layer, password-reset delivery, and a privacy policy for location sharing.
## Local preview

Run `npm run dev` from PowerShell. This starts the Vite frontend and FastAPI backend together, waits for both health endpoints, opens the browser, and stops both child processes when the command exits. Use `npm run stop:stack` if a previous session needs to be stopped.

The backend health endpoint is `http://127.0.0.1:8000/api/health`; the frontend is `http://127.0.0.1:5173/`.

## Publish workflow

`npm run publish` runs the frontend build, Python compilation, backend tests, commits all tracked changes, and pushes the current branch to the configured `origin`. It refuses to run until the project has a GitHub `origin`, so an unrelated repository cannot be overwritten accidentally.

After configuring the exact repository, run `npm run enable:auto-publish` once to make regular Git commits push automatically through the guarded post-commit hook.

