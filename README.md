# AquaSense AI (HydroInsight)

HydroInsight is a schema-driven water quality and groundwater monitoring dashboard. The frontend is wired to a trained quality screening profile with simulated live readings for five configured parameters:

- pH
- EC / conductivity (µS/cm)
- TDS (mg/L)
- total hardness (mg/L as CaCO3)
- chloride (mg/L)

The quality artifact is a five-class XGBoost classifier trained from 3,218 complete records in the supplied CGWB Andhra Pradesh and Karnataka chemistry CSVs. Labels are generated with a weighted-arithmetic WQI formula, and the model metadata is saved in `ml/artifacts/quality_model_metadata.json`. Replace the artifact only after evaluating a new model with the same inference contract.

## Run

```bash
npm install
npm run dev
```

For a reproducible container stack, review the included `docker-compose.yml`. It starts PostgreSQL, runs the Alembic baseline before the API, and serves the Vite build through Nginx. Replace the example database password and secret before using it outside local development.

## Important production boundary

The UI describes predictions as sensor-based screening. It does not claim potability and explicitly notes that nitrate, fluoride, and heavy-metal parameters are not measured by this five-input profile. A real backend should reject inference requests unless the feature vector matches the model's expected feature names, order, units, and valid sensor ranges. `ml/quality_inference.py` provides that validation.

## Prototype account and location flow

- Users must sign up or sign in before entering the workspace. The first account is assigned `admin`; every later account is assigned `user`, so nobody is asked to choose a role.
- The map is a Leaflet map with street, satellite, and terrain tile layers. Users can select a precise point or two-corner area, search a city/address manually, request browser geolocation, and see country, state, district, and city/town fields for a selected place.
- Search uses OpenStreetMap Nominatim only after the user submits a place query. Reverse-geocoding a precise map-selected coordinate is an explicit `Identify area` action rather than an automatic background request.
- The browser requests live location through `navigator.geolocation`, watches for updates, and uses the current coordinates as the test site.
- Quality inputs are editable numeric fields. A user submission stores the five values, timestamp, role, and live coordinates, then appears in the admin inbox.
- Bright/dark preference, accounts, sessions, locations, and updates are stored in browser `localStorage` for this prototype.

This is a front-end prototype flow. Cross-device authentication and shared admin updates require a backend with password hashing, authorization, a database, and a map/location privacy policy; `localStorage` is intentionally not presented as production account storage.

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

- New registration collects full name, email, international mobile number, password confirmation, and optional weekly-reminder consent. The first backend account is an administrator; later accounts are standard users.
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
- `ml/artifacts/` contains the current five-parameter quality profile. Groundwater forecasting uses a labelled transparent fallback until a compatible trained groundwater artifact is configured.
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

