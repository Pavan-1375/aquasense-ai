# AquaSense AI API and IoT bridge

## Run on Windows PowerShell

```powershell
py -3 -m pip install -r backend/requirements.txt
Copy-Item backend/.env.example backend/.env
Set-Location backend; py -3 -m alembic upgrade head; Set-Location ..
py -3 backend/scripts/seed_demo.py
py -3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend
```

Use `http://127.0.0.1:8000/docs` for interactive OpenAPI documentation and `http://127.0.0.1:8000/api/health` for a health check. The default database is `backend/hydroinsight.db`; set `DATABASE_URL=postgresql+psycopg://...` after installing the PostgreSQL driver for deployment. Local development keeps additive metadata creation enabled; production should run Alembic and set `SCHEMA_AUTO_CREATE=false`.

## Core contracts

- `POST /api/auth/signup` requires full name, email, international mobile, password confirmation and reminder consent; development bootstraps the first account as `admin`. Production requires `BOOTSTRAP_ADMIN_EMAIL` to match the initial administrator email; later accounts are `user`.
- `POST /api/auth/signin` returns a seven-day bearer session token.
- `POST /api/verification/request` and `POST /api/verification/confirm` implement short-lived email/mobile verification codes. Development mode returns a code and records that delivery was simulated.
- `POST /api/ingest/http` accepts the ESP32 reading schema and requires `X-Device-Key`; send `X-Idempotency-Key` for safe retries.
- `GET /api/dashboard` returns only administrator-reviewed groundwater readings for official analytics, plus alerts and a labelled transparent fallback forecast. Raw device readings remain visible through `GET /api/measurements` with `quality_status=pending_review`.
- `POST /api/quality` calculates the explicit weighted-arithmetic screening WQI profile in `app/services/quality.py`.
- `GET /api/reports/measurements.csv` and `GET /api/reports/summary.pdf` export stored data.
- `WS /api/ws/measurements` broadcasts accepted ingestion events to connected clients.

## Submission and reminder workflow

`POST /api/submissions` stores a draft or submitted groundwater/quality batch with the original values, measurement timestamp, source, validation warnings, station/device linkage and audit event. Users can list only their own records through `GET /api/submissions/mine`; corrections create a new version instead of overwriting the prior record. Attachments are accepted through `POST /api/submissions/{id}/attachments` with configured size and content-type limits.

Administrators use `GET /api/admin/stats`, `GET /api/admin/submissions`, and `POST /api/admin/submissions/{id}/review`. Only approved batches are promoted into quality/groundwater analytics. Rejected, incomplete and unreviewed records remain preserved but do not become approved training data.

`ReminderSchedule` and `NotificationDelivery` provide persistent weekly scheduling, timezone-aware local delivery times, channel verification checks, delivery status, provider IDs, failure reasons and idempotency. The FastAPI startup worker runs the cycle; for a separately managed process use `py -3 backend/scripts/run_worker.py`. Use `POST /api/admin/reminders/test` in development to exercise it without sending real messages. Provider adapters are intentionally isolated in `app/services/reminders.py` and currently record simulated delivery outside production.

Submission attachments accept CSV, PDF, text, Excel, JPEG, PNG and WebP files. A proof photo can be attached to a groundwater submission; the original observation remains pending until administrator review. Live device readings are stored as `pending_review` and are not promoted to official dashboard analytics until an approved submission or live-reading review changes the status to `reviewed`.

## Reliability and security controls

- Every HTTP response carries an `X-Request-ID` correlation header and request timing is logged without credentials or payload values.
- Authentication, verification and ingestion routes have a bounded in-process rate limiter. A shared reverse-proxy or Redis limiter is recommended for multi-instance production deployments.
- Device readings reject future timestamps, classify delayed readings as `stale`, reject duplicate device/timestamp values, and support durable idempotency receipts for retry-safe delivery.
- `/api/health` reports database connectivity, reminder-worker state and quality-model artifact availability without exposing stack traces or secrets.
- Uploads remain size/type validated and user submission ownership is enforced from the authenticated session, not a client-supplied owner ID.

## Migrations

The first Alembic revision is a non-destructive baseline for the existing schema. It uses SQLAlchemy metadata additively so existing SQLite records remain intact while the database receives a migration revision. Future schema changes should be explicit revisions under `backend/migrations/versions/`; do not drop tables or reset the local database.

## Serial bridge

```powershell
py -3 backend/bridge/serial_bridge.py --port COM5 --baud 115200 --device-key local-device-key
```

For automatic USB reconnect handling, run the watcher instead. It detects the
ESP32 serial adapter, starts the bridge, and restarts it when the device is
unplugged and reconnected:

```powershell
py -3 backend/bridge/auto_bridge.py --device-id ESP32-001 --device-key local-device-key

For the deployed Railway API on Windows, set the device key without committing it and use the project launcher:

```powershell
$env:ESP32_INGEST_KEY = "<the device's Railway ingest key>"
.\scripts\start-esp32-bridge.ps1
```

The bridge must run on the computer physically connected to the ESP32 USB cable. Railway cannot access a local COM port. It automatically detects supported USB serial adapters, reconnects after unplug/replug, accepts the current OLED text format or JSON lines, and forwards validated readings to Railway.
```

Firmware upload is intentionally opt-in because it overwrites the program
currently on the board. After installing Arduino CLI and the correct ESP32
core, use an explicit sketch and board:

```powershell
py -3 backend/bridge/auto_bridge.py --upload --firmware iot/esp32_water_level_example.ino --fqbn esp32:esp32:esp32
```

The bridge accepts newline-delimited JSON such as:

```json
{"device_id":"ESP32-001","timestamp":"2026-10-27T12:00:00Z","distance_cm":20.0,"water_level_percent":null,"water_depth_cm":null,"temperature_c":null}
```

The bundled firmware sends its OLED values together in each JSON packet and writes `millis()` as a quoted numeric timestamp. The bridge recognizes that monotonic timestamp and replaces it with the computer's UTC receipt time; it does not alter the sensor values. Malformed messages, missing groundwater fields, duplicate device/timestamp pairs and invalid device keys are rejected.

## Production configuration

Set a long random `SECRET_KEY`, replace the shared development ingestion key with per-device keys, configure PostgreSQL, restrict `CORS_ORIGINS`, enable HTTPS, configure email/SMS provider credentials and approved sender identities, use secure file storage, and add a production rate-limit/reverse-proxy layer before exposing the API publicly. For a fresh production database, set `BOOTSTRAP_ADMIN_EMAIL` to the first administrator's registered email before sign-up. The local deterministic advisor is deliberately used when no external AI credential is configured.

