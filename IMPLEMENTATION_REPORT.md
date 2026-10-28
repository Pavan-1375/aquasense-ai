# AquaSense AI implementation report

## Delivered

- Added a FastAPI backend with SQLAlchemy models, SQLite fallback, protected sessions, hashed passwords, role-aware routes, device ingestion, WebSocket support, CSV export, PDF summary export, deterministic local advisor responses, and demo seeding.
- Added account creation, sign-in, logout, forgot-password development flow, protected application navigation, automatic first-account admin assignment, and later-account user assignment.
- Added the formal AquaSense AI account flow: full-name/email/mobile registration, password confirmation, reminder consent, verification-ready email/mobile contact status, profile editing, and a persistent weekly reminder preference screen.
- Added centralized monitoring-data submissions for groundwater and water-quality readings, draft/save/submit states, server-side validation, warnings, optional attachments, versioned correction records, user submission history, and an admin review queue. Only approved submissions are promoted into the existing measurement/quality analytics tables.
- Added reminder schedules, notification delivery logs, development-safe simulated provider delivery, duplicate/idempotency protection, channel-verification checks, and an admin manual reminder test. The worker runs from the FastAPI service when enabled.
- Added functional application surfaces for live monitoring, water quality, groundwater intelligence, advisor, history, devices/stations, alerts, map/locations, reports, education, help, profile, settings, and admin review.
- Preserved the existing map experience and verified Leaflet controls for Street, Satellite, Terrain, Point, Area, zoom, manual place search, current-location linking, mapped-account display, and explicit area identification.
- Added the ESP32 serial bridge contract and an additive Arduino example that can coexist with the existing OLED firmware. Offline hardware is shown explicitly instead of being presented as live.
- Added dataset inspection and import guidance, a Windows Unicode-safe importer, model metadata, backend tests, environment configuration, and setup documentation.

## Verified trained quality model

The serialized profile in `ml/artifacts/quality_model_metadata.json` is an XGBoost classifier trained from 3,218 complete CGWB chemistry rows. The actual five-feature order is:

1. `pH`
2. `EC_uS_cm` — electrical conductivity in µS/cm
3. `TDS_mg_L` — total dissolved solids in mg/L
4. `Total_Hardness_mgCaCO3_L` — total hardness in mg/L as CaCO3
5. `Chloride_mg_L` — chloride in mg/L

The class labels are `Excellent`, `Good`, `Poor`, `Very poor`, and `Unsuitable`. XGBoost was selected by five-fold stratified comparison using macro F1 and balanced accuracy; the recorded metrics were accuracy 0.9773, macro F1 0.9758, and balanced accuracy 0.9786. Random Forest, Extra Trees, and logistic regression metrics are retained in the metadata for comparison.

The labels are derived from the documented weighted-arithmetic WQI screening formula. They are not laboratory-confirmed potability labels. The source data does not provide temperature or turbidity for the trained model, and the application explicitly states that bacteriological, nitrate, fluoride, hardness beyond the measured feature, and heavy-metal testing is not a substitute for laboratory analysis. The app does not claim certification of drinking-water safety.

## Data checks performed

- Chemistry files were inspected for the expected CGWB columns, missingness, and station/time fields.
- Groundwater files were inspected and confirmed to use `Data Acquisition Time`, `Station`, latitude/longitude, and `Groundwater Level Telemetry … (meter)` as the level field.
- The Karnataka 2026–2030 groundwater file is present but currently has zero data rows; the importer reports that condition rather than fabricating values.
- A Windows console encoding issue with the `µ` column name was fixed in `backend/scripts/import_dataset.py`.

## Verification evidence

- `npm run build` passes.
- `py -3 -m compileall -q backend` passes.
- Backend unit tests pass for WQI classification and transparent forecast fallback.
- FastAPI health check passes on `http://127.0.0.1:8000/api/health` with the SQLite database.
- OpenAPI exposes authentication, reset-password, import-inspection, reports, measurements, dashboard, and ingestion routes.
- Protected signup/dashboard/export smoke test passes.
- Frontend smoke test passes for navigation, API status, settings/model contract, and map controls.
- Browser smoke test passes for the new Submit Monitoring Data, My Submissions, Notifications, and Administration surfaces. The admin reminder test was also verified after fixing the explicit flush required by the project's disabled-autoflush session configuration.

## Remaining production configuration

- Set a strong `SECRET_KEY`, `DEVICE_INGEST_KEY`, CORS origins, and a PostgreSQL `DATABASE_URL` for deployment.
- Configure HTTPS and an email provider if reset tokens should be delivered by email; the current development flow returns a token in the API response.
- Register the real ESP32 device and run the serial bridge with its actual COM port and baud rate. Until then, the UI correctly shows hardware offline/demo state.
- Supply trained groundwater forecast artifacts if trained forecasts are required. The current fallback is labelled `transparent-fallback` and is never represented as a trained prediction.
- Configure an external AI provider only if cloud conversational responses are desired; the included advisor remains deterministic and data-grounded locally.
- Configure real email/SMS providers, verified sender identities, and a production delivery worker before treating reminder delivery as external communication. Development mode intentionally records simulated deliveries only.
- The optional `phonenumbers` dependency is listed for production-grade mobile validation; this managed environment could not resolve that package from its configured index, so the application uses its documented international-format fallback until dependencies are installed normally.

## Architecture upgrade

- Added request correlation IDs, structured request timing logs, safe health details for database/model/worker state, and bounded in-process rate limiting for authentication and device ingestion routes.
- Added durable ingestion receipts and `X-Idempotency-Key` support so serial/HTTP retries return the original measurement instead of creating a duplicate. Future timestamps are rejected and delayed readings are marked `stale`.
- Added a separate `backend/scripts/run_worker.py` entry point for reminder processing when the scheduler should run outside the API process.
- Added an additive Alembic baseline, production `SCHEMA_AUTO_CREATE=false` configuration, Dockerfiles, Docker Compose with PostgreSQL, Nginx static serving, frontend `VITE_API_URL` configuration, and a CI workflow.
- Kept the current modular-monolith choice: FastAPI remains the API and worker boundary, SQLite remains the local fallback, PostgreSQL is the production target, and MQTT/Celery/React Router/TanStack Query were not added without a current deployment need.

The managed environment did not have Alembic installed, so `alembic upgrade head` could not be executed locally; it is declared in `backend/requirements.txt` and is invoked by the production container before startup.

## Editorial UI refinement

- Replaced the darker boxed dashboard treatment with a neutral editorial system using Source Sans 3/system fallback, open measurement rows, subtle dividers, intrinsic content sizing, compact navigation, restrained statuses, and accessible reduced-motion behavior.
- Removed visible sparkle-style AI decoration in favor of a simple conversation icon and renamed the navigation item to Water advisor. Existing routes, map controls, manual quality inputs, device states, submissions, reminders and admin actions remain connected.
- Added frontend API configuration through `VITE_API_URL` so container/deployment environments do not depend on a hardcoded localhost backend.
- Refined the dashboard composition from the supplied screenshot: the overview signal row is now fluid and low-emphasis, the map is the dominant monitoring area, map controls share a compact toolbar, selected-site details are open aligned columns, and quality/admin content uses breathable lists instead of nested boxes.
- Removed unsupported dashboard quality counts, arbitrary trend percentages and browser-generated confidence claims. Local screening now explicitly reports that confidence is unavailable unless a calibrated model output is provided; groundwater, alert and report preview surfaces are clearly labeled when approved backend data is absent.
