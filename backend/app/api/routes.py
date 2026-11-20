from datetime import datetime, timedelta, timezone
import csv
import hashlib
import io
import json
from pathlib import Path
import secrets
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, File, Header, HTTPException, Query, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse
from fastapi import Response
from sqlalchemy import desc, text
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import (
    Alert,
    AuditEvent,
    DataQualityResult,
    Device,
    Measurement,
    ModelExecutionRecord,
    NotificationDelivery,
    PasswordResetToken,
    PasswordRecoveryCode,
    QualityObservation,
    ReminderSchedule,
    SessionToken,
    Station,
    SubmissionAttachment,
    SubmissionBatch,
    SubmissionReview,
    User,
    UserContact,
    VerificationCode,
    utc_now,
)
from ..schemas import (
    AdvisorRequest,
    AdvisorResponse,
    AlertOut,
    AlertStateUpdate,
    AccountRoleUpdate,
    AuthResponse,
    DashboardResponse,
    DeviceCreate,
    DeviceOut,
    DeviceUpdate,
    ForgotPassword,
    GroundwaterSubmission,
    MeasurementIn,
    MeasurementOut,
    LocationSyncIn,
    NotificationDeliveryOut,
    ProfileUpdate,
    QualityObservationIn,
    QualityObservationOut,
    ReminderScheduleIn,
    ReminderScheduleOut,
    SignIn,
    ResetPassword,
    SmsPasswordReset,
    SubmissionCreate,
    SubmissionListResponse,
    SubmissionOut,
    SubmissionReviewIn,
    StationCreate,
    StationOut,
    AdminStats,
    UserCreate,
    UserOut,
    VerificationConfirm,
    VerificationRequest,
)
from ..security import get_current_user, hash_password, issue_token, require_admin, verify_password
from ..services.forecast import fallback_forecast
from ..services.ingestion import save_measurement, save_measurement_with_key
from ..services.quality import calculate_wqi
from ..services.uploads import sanitize_image_upload
from ml.quality_inference import predict_quality
from ..services.reminders import ensure_schedule, next_occurrence, run_reminder_cycle
from ..services.recovery_delivery import send_reset_email, send_reset_sms


router = APIRouter(prefix="/api")
PROJECT_ROOT = Path(__file__).resolve().parents[3]
QUALITY_MODEL_DIR = PROJECT_ROOT / "ml" / "artifacts"
settings = get_settings()


class SocketManager:
    def __init__(self) -> None:
        self.connections: list[tuple[WebSocket, str]] = []

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        await websocket.accept()
        self.connections.append((websocket, user_id))

    def disconnect(self, websocket: WebSocket) -> None:
        self.connections = [(connection, user_id) for connection, user_id in self.connections if connection is not websocket]

    async def broadcast(self, payload: dict) -> None:
        owner_id = payload.get("measurement", {}).get("owner_id")
        for websocket, user_id in list(self.connections):
            role = getattr(websocket.state, "aquasense_role", "user")
            if role != "admin" and (not owner_id or user_id != owner_id):
                continue
            try:
                await websocket.send_json(payload)
            except Exception:
                self.disconnect(websocket)


socket_manager = SocketManager()


def as_user(user: User, contact: UserContact | None = None) -> UserOut:
    return UserOut(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        created_at=user.created_at,
        mobile_number=contact.mobile_e164 if contact else None,
        email_verified=contact.email_verified if contact else False,
        mobile_verified=contact.mobile_verified if contact else False,
        account_status=contact.account_status if contact else "active",
        reminder_consent=contact.reminder_consent if contact else False,
        preferred_reminder_channel=contact.preferred_reminder_channel if contact else "email",
        timezone=contact.timezone if contact else "Asia/Kolkata",
    )


def as_submission(submission: SubmissionBatch) -> SubmissionOut:
    return SubmissionOut(
        id=submission.id,
        user_id=submission.user_id,
        station_id=submission.station_id,
        device_id=submission.device_id,
        measurement_at=submission.measurement_at,
        submitted_at=submission.submitted_at,
        status=submission.status,
        source=submission.source,
        measurement_method=submission.measurement_method,
        remarks=submission.remarks,
        groundwater=json.loads(submission.groundwater_json) if submission.groundwater_json else None,
        quality=json.loads(submission.quality_json) if submission.quality_json else None,
        validation_warnings=json.loads(submission.validation_json or "[]"),
        review_feedback=submission.review_feedback,
        reviewed_by=submission.reviewed_by,
        reviewed_at=submission.reviewed_at,
        version=submission.version,
        parent_submission_id=submission.parent_submission_id,
        created_at=submission.created_at,
        updated_at=submission.updated_at,
    )


def as_schedule(schedule: ReminderSchedule) -> ReminderScheduleOut:
    return ReminderScheduleOut(
        id=schedule.id,
        user_id=schedule.user_id,
        enabled=schedule.enabled,
        weekday=schedule.weekday,
        local_time=schedule.local_time,
        timezone=schedule.timezone,
        channels=json.loads(schedule.channels_json or "[]"),
        next_run_at=schedule.next_run_at,
        last_run_at=schedule.last_run_at,
    )


def _otp_hash(code: str) -> str:
    return hashlib.sha256(f"{settings.secret_key}:{code}".encode()).hexdigest()


def _otp_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _quality_warnings(payload: SubmissionCreate) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    if payload.measurement_at.replace(tzinfo=None) > utc_now() + timedelta(minutes=10):
        warnings.append({"severity": "warning", "code": "future_timestamp", "field": "measurement_at", "detail": "Measurement timestamp is in the future."})
    if payload.measurement_at.replace(tzinfo=None) < utc_now() - timedelta(days=30):
        warnings.append({"severity": "warning", "code": "stale_observation", "field": "measurement_at", "detail": "Observation is older than 30 days and should be reviewed."})
    groundwater = payload.groundwater.model_dump(exclude_none=True) if payload.groundwater else {}
    quality = payload.quality.model_dump(exclude_none=True) if payload.quality else {}
    if not groundwater and not quality:
        warnings.append({"severity": "error", "code": "empty_submission", "field": "submission", "detail": "Provide groundwater or water-quality values."})
    if groundwater.get("water_level_percent") is not None and groundwater.get("distance_cm") is not None and groundwater["water_level_percent"] == 0 and groundwater["distance_cm"] == 0:
        warnings.append({"severity": "warning", "code": "sensor_consistency", "field": "groundwater", "detail": "Distance and water-level percentage are both zero; verify the sensor state."})
    if quality.get("tds_mg_l") is not None and quality.get("ec_us_cm") is not None:
        ratio = quality["tds_mg_l"] / quality["ec_us_cm"] if quality["ec_us_cm"] else None
        if ratio is not None and not 0.3 <= ratio <= 0.9:
            warnings.append({"severity": "warning", "code": "tds_ec_mismatch", "field": "quality", "detail": "TDS is not within the expected approximate relationship to EC; check calibration."})
    return warnings


def _run_quality_model(quality: dict) -> dict:
    artifact = QUALITY_MODEL_DIR / "quality_model.joblib"
    if not artifact.exists():
        return {"status": "fallback", "reason": "compatible model artifact unavailable"}
    required = {"pH": quality.get("ph"), "TDS_mg_L": quality.get("tds_mg_l"), "Turbidity_NTU": quality.get("turbidity_ntu"), "Temperature_C": quality.get("temperature_c")}
    if any(value is None for value in required.values()):
        return {"status": "fallback", "reason": "one or more four-parameter inputs are missing"}
    try:
        result = predict_quality(required, artifact)
        return {"status": "model", **result}
    except (ValueError, OSError, RuntimeError) as error:
        return {"status": "fallback", "reason": str(error)}


@router.get("/health")
def health(request: Request, db: Session = Depends(get_db)) -> dict:
    database_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        database_status = "error"
    scheduler_enabled = bool(settings.scheduler_enabled)
    scheduler_running = bool(getattr(request.app.state, "reminder_worker_running", False))
    artifact_status = "available" if (QUALITY_MODEL_DIR / "quality_model_metadata.json").exists() else "unavailable"
    overall = "ok" if database_status == "ok" else "degraded"
    return {
        "status": overall,
        "service": "aquasense-ai-api",
        "database": {"engine": settings.database_url.split(":", 1)[0], "status": database_status},
        "workers": {"reminders": "running" if scheduler_enabled and scheduler_running else "disabled"},
        "model_service": artifact_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "station_count": db.query(Station).count() if database_status == "ok" else None,
    }


@router.post("/auth/signup", response_model=AuthResponse, status_code=201)
def signup(payload: UserCreate, response: Response, db: Session = Depends(get_db)) -> AuthResponse:
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    if db.query(UserContact).filter(UserContact.mobile_e164 == payload.mobile_number).first():
        raise HTTPException(status_code=409, detail="An account with this mobile number already exists")
    has_active_admin = db.query(User).filter(User.role == "admin", User.is_active.is_(True)).first() is not None
    bootstrap_email = settings.bootstrap_admin_email.strip().lower()
    if settings.app_env.lower() == "production" and not has_active_admin:
        if not bootstrap_email:
            raise HTTPException(status_code=503, detail="Initial administrator email is not configured. Set BOOTSTRAP_ADMIN_EMAIL before account creation.")
        if payload.email != bootstrap_email:
            raise HTTPException(status_code=403, detail="The initial production account must use the configured administrator email")
    bootstrap_admin = not has_active_admin and (settings.app_env.lower() != "production" or payload.email == bootstrap_email)
    role = "admin" if bootstrap_admin else "user"
    user = User(name=payload.name.strip(), email=payload.email, password_hash=hash_password(payload.password), role=role)
    db.add(user)
    db.flush()
    contact = UserContact(
        user_id=user.id,
        mobile_e164=payload.mobile_number,
        reminder_consent=payload.reminder_consent,
        preferred_reminder_channel=payload.preferred_reminder_channel,
        timezone=payload.timezone,
    )
    db.add(contact)
    db.flush()
    schedule = ensure_schedule(db, user, contact)
    schedule.enabled = payload.reminder_consent
    db.add(AuditEvent(user_id=user.id, event_type="auth.signup", detail=json.dumps({"role": role})))
    db.commit()
    db.refresh(user)
    token = issue_token(db, user)
    csrf = secrets.token_urlsafe(32)
    cross_site = settings.app_env.lower() == "production"
    response.set_cookie("aquasense_session", token, httponly=True, secure=cross_site, samesite="none" if cross_site else "lax", max_age=604800, path="/")
    response.set_cookie("aquasense_csrf", csrf, httponly=False, secure=cross_site, samesite="none" if cross_site else "lax", max_age=604800, path="/")
    return AuthResponse(user=as_user(user, contact))


@router.post("/auth/signin", response_model=AuthResponse)
def signin(payload: SignIn, response: Response, db: Session = Depends(get_db)) -> AuthResponse:
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect")
    token = issue_token(db, user)
    csrf = secrets.token_urlsafe(32)
    cross_site = settings.app_env.lower() == "production"
    response.set_cookie("aquasense_session", token, httponly=True, secure=cross_site, samesite="none" if cross_site else "lax", max_age=604800, path="/")
    response.set_cookie("aquasense_csrf", csrf, httponly=False, secure=cross_site, samesite="none" if cross_site else "lax", max_age=604800, path="/")
    return AuthResponse(user=as_user(user, db.query(UserContact).filter(UserContact.user_id == user.id).first()))


@router.post("/auth/forgot-password")
def forgot_password(payload: ForgotPassword, db: Session = Depends(get_db)) -> dict:
    user = db.query(User).filter(User.email == payload.email).first()
    response = {"status": "accepted", "channel": payload.channel, "message": "If the account exists, recovery instructions are ready."}
    if not user:
        return response
    expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=30)
    if payload.channel == "email":
        token = secrets.token_urlsafe(32)
        db.add(PasswordResetToken(token=token, user_id=user.id, expires_at=expires_at))
        reset_link = f"{settings.app_base_url}/?reset_token={token}"
        if settings.app_env != "production":
            response["development_link"] = reset_link
            response["development_token"] = token
            response["message"] = "Development fallback: use the reset link below. Configure email delivery for production."
        else:
            try:
                send_reset_email(user.email, reset_link)
            except RuntimeError:
                raise HTTPException(status_code=503, detail="Email recovery delivery is not configured")
    else:
        code = f"{secrets.randbelow(1_000_000):06d}"
        db.add(PasswordRecoveryCode(user_id=user.id, code_hash=_otp_hash(code), expires_at=expires_at))
        if settings.app_env != "production":
            response["development_otp"] = code
            response["message"] = "Development fallback: use the returned SMS OTP. Configure an SMS provider for production."
        else:
            contact = db.query(UserContact).filter(UserContact.user_id == user.id).first()
            if not contact:
                raise HTTPException(status_code=400, detail="No registered mobile number is available")
            try:
                send_reset_sms(contact.mobile_e164, code)
            except RuntimeError:
                raise HTTPException(status_code=503, detail="SMS recovery delivery is not configured")
    db.commit()
    return response


@router.post("/auth/reset-password")
def reset_password(payload: ResetPassword, db: Session = Depends(get_db)) -> dict:
    reset = db.get(PasswordResetToken, payload.token)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if not reset or reset.used or reset.expires_at < now:
        raise HTTPException(status_code=400, detail="Reset token is invalid or expired")
    user = db.get(User, reset.user_id)
    if not user:
        raise HTTPException(status_code=400, detail="Reset token is invalid")
    user.password_hash = hash_password(payload.new_password)
    reset.used = True
    db.query(SessionToken).filter(SessionToken.user_id == user.id).delete(synchronize_session=False)
    db.commit()
    return {"status": "password_reset", "message": "Password updated. Sign in with the new password."}


@router.post("/auth/reset-password-sms")
def reset_password_sms(payload: SmsPasswordReset, db: Session = Depends(get_db)) -> dict:
    user = db.query(User).filter(User.email == payload.email).first()
    recovery = db.query(PasswordRecoveryCode).filter(PasswordRecoveryCode.user_id == (user.id if user else ""), PasswordRecoveryCode.used.is_(False)).order_by(PasswordRecoveryCode.created_at.desc()).first()
    now = utc_now()
    if not recovery or recovery.expires_at < now or recovery.attempts >= 5:
        raise HTTPException(status_code=400, detail="SMS OTP is invalid or expired")
    recovery.attempts += 1
    if recovery.code_hash != _otp_hash(payload.otp):
        db.commit()
        raise HTTPException(status_code=400, detail="SMS OTP is invalid")
    recovery.used = True
    user.password_hash = hash_password(payload.new_password)
    db.query(SessionToken).filter(SessionToken.user_id == user.id).delete(synchronize_session=False)
    db.commit()
    return {"status": "password_reset", "message": "Password updated. Sign in with the new password."}


@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> UserOut:
    return as_user(user, db.query(UserContact).filter(UserContact.user_id == user.id).first())


@router.post("/auth/logout")
def logout(response: Response, authorization: Annotated[str | None, Header()] = None, session_cookie: Annotated[str | None, Cookie(alias="aquasense_session")] = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    token = authorization.split(" ", 1)[1].strip() if authorization and authorization.lower().startswith("bearer ") else session_cookie
    if token:
        session = db.get(SessionToken, token)
        if session:
            db.delete(session)
            db.commit()
    response.delete_cookie("aquasense_session", path="/")
    response.delete_cookie("aquasense_csrf", path="/")
    return {"status": "signed_out", "user_id": user.id}


@router.patch("/profile", response_model=UserOut)
def update_profile(payload: ProfileUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> UserOut:
    contact = db.query(UserContact).filter(UserContact.user_id == user.id).first()
    if payload.name is not None:
        user.name = payload.name.strip()
    if contact:
        values = payload.model_dump(exclude_none=True)
        values.pop("name", None)
        for key, value in values.items():
            setattr(contact, key, value)
        if payload.reminder_consent is not None:
            schedule = ensure_schedule(db, user, contact)
            schedule.enabled = payload.reminder_consent
            if payload.reminder_consent and not schedule.next_run_at:
                schedule.next_run_at = next_occurrence(schedule)
    db.add(AuditEvent(user_id=user.id, event_type="profile.updated", detail=json.dumps(payload.model_dump(exclude_none=True))))
    db.commit()
    db.refresh(user)
    return as_user(user, contact)


@router.delete("/account")
def delete_account(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    # Preserve audit history but remove the account and its directly owned data.
    if user.role == "admin" and db.query(User).filter(User.role == "admin", User.id != user.id, User.is_active.is_(True)).count() == 0:
        raise HTTPException(status_code=409, detail="Promote another active administrator before deleting the last administrator account")
    owned_submissions = db.query(SubmissionBatch).filter(SubmissionBatch.user_id == user.id).all()
    submission_ids = [item.id for item in owned_submissions]
    if submission_ids:
        db.query(ModelExecutionRecord).filter(ModelExecutionRecord.submission_id.in_(submission_ids)).delete(synchronize_session=False)
        db.query(SubmissionReview).filter(SubmissionReview.submission_id.in_(submission_ids)).delete(synchronize_session=False)
        db.query(DataQualityResult).filter(DataQualityResult.submission_id.in_(submission_ids)).delete(synchronize_session=False)
        attachments = db.query(SubmissionAttachment).filter(SubmissionAttachment.submission_id.in_(submission_ids)).all()
        for attachment in attachments:
            try:
                Path(attachment.storage_path).unlink(missing_ok=True)
            except OSError:
                pass
        db.query(SubmissionAttachment).filter(SubmissionAttachment.submission_id.in_(submission_ids)).delete(synchronize_session=False)
        db.query(SubmissionBatch).filter(SubmissionBatch.id.in_(submission_ids)).delete(synchronize_session=False)
    # Preserve review history while detaching personal identifiers.
    db.query(SubmissionReview).filter(SubmissionReview.reviewer_id == user.id).update({SubmissionReview.reviewer_id: None}, synchronize_session=False)
    db.query(SubmissionBatch).filter(SubmissionBatch.reviewed_by == user.id).update({SubmissionBatch.reviewed_by: None}, synchronize_session=False)
    db.query(Measurement).filter(Measurement.owner_id == user.id).delete(synchronize_session=False)
    db.query(QualityObservation).filter(QualityObservation.owner_id == user.id).delete(synchronize_session=False)
    db.query(Alert).filter(Alert.owner_id == user.id).delete(synchronize_session=False)
    db.query(ReminderSchedule).filter(ReminderSchedule.user_id == user.id).delete(synchronize_session=False)
    db.query(NotificationDelivery).filter(NotificationDelivery.user_id == user.id).delete(synchronize_session=False)
    db.query(VerificationCode).filter(VerificationCode.user_id == user.id).delete(synchronize_session=False)
    db.query(PasswordRecoveryCode).filter(PasswordRecoveryCode.user_id == user.id).delete(synchronize_session=False)
    db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id).delete(synchronize_session=False)
    db.query(SessionToken).filter(SessionToken.user_id == user.id).delete(synchronize_session=False)
    db.query(UserContact).filter(UserContact.user_id == user.id).delete(synchronize_session=False)
    db.query(Station).filter(Station.owner_id == user.id).update({Station.owner_id: None}, synchronize_session=False)
    db.query(AuditEvent).filter(AuditEvent.user_id == user.id).update({AuditEvent.user_id: None}, synchronize_session=False)
    user_id = user.id
    db.delete(user)
    db.commit()
    return {"status": "deleted", "user_id": user_id}


@router.post("/verification/request")
def request_verification(payload: VerificationRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    contact = db.query(UserContact).filter(UserContact.user_id == user.id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact profile not found")
    if payload.channel == "email" and contact.email_verified:
        return {"status": "already_verified", "channel": payload.channel}
    if payload.channel == "mobile" and contact.mobile_verified:
        return {"status": "already_verified", "channel": payload.channel}
    code = _otp_code()
    verification = VerificationCode(user_id=user.id, channel=payload.channel, code_hash=_otp_hash(code), expires_at=utc_now() + timedelta(minutes=10))
    db.add(verification)
    db.commit()
    response = {"status": "accepted", "channel": payload.channel, "message": "Verification is queued. Configure an email or SMS provider for real delivery."}
    if settings.app_env != "production":
        response["development_code"] = code
        response["message"] = "Development fallback: use the returned code. No real message was sent."
    return response


@router.post("/verification/confirm", response_model=UserOut)
def confirm_verification(payload: VerificationConfirm, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> UserOut:
    verification = db.query(VerificationCode).filter(VerificationCode.user_id == user.id, VerificationCode.channel == payload.channel, VerificationCode.used.is_(False)).order_by(VerificationCode.created_at.desc()).first()
    if not verification or verification.expires_at < utc_now():
        raise HTTPException(status_code=400, detail="Verification code is invalid or expired")
    verification.attempts += 1
    if verification.attempts > 5 or verification.code_hash != _otp_hash(payload.code):
        db.commit()
        raise HTTPException(status_code=400, detail="Verification code is invalid")
    verification.used = True
    contact = db.query(UserContact).filter(UserContact.user_id == user.id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact profile not found")
    if payload.channel == "email":
        contact.email_verified = True
    else:
        contact.mobile_verified = True
    db.add(AuditEvent(user_id=user.id, event_type=f"contact.{payload.channel}_verified"))
    db.commit()
    return as_user(user, contact)


@router.get("/reminders", response_model=ReminderScheduleOut)
def get_reminder_schedule(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> ReminderScheduleOut:
    contact = db.query(UserContact).filter(UserContact.user_id == user.id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact profile not found")
    schedule = ensure_schedule(db, user, contact)
    db.commit()
    return as_schedule(schedule)


@router.put("/reminders", response_model=ReminderScheduleOut)
def update_reminder_schedule(payload: ReminderScheduleIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> ReminderScheduleOut:
    contact = db.query(UserContact).filter(UserContact.user_id == user.id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact profile not found")
    schedule = ensure_schedule(db, user, contact)
    schedule.enabled = payload.enabled and contact.reminder_consent
    schedule.weekday = payload.weekday
    schedule.local_time = payload.local_time
    schedule.timezone = payload.timezone
    schedule.channels_json = json.dumps(payload.channels)
    schedule.next_run_at = next_occurrence(schedule) if schedule.enabled else None
    contact.timezone = payload.timezone
    contact.preferred_reminder_channel = "both" if len(payload.channels) == 2 else payload.channels[0]
    db.add(AuditEvent(user_id=user.id, event_type="reminders.updated", detail=json.dumps(payload.model_dump())))
    db.commit()
    db.refresh(schedule)
    return as_schedule(schedule)


@router.get("/notifications", response_model=list[NotificationDeliveryOut])
def list_notifications(limit: int = Query(default=100, ge=1, le=500), db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[NotificationDelivery]:
    return db.query(NotificationDelivery).filter(NotificationDelivery.user_id == user.id).order_by(NotificationDelivery.scheduled_at.desc()).limit(limit).all()


@router.post("/admin/reminders/test")
def test_reminder(user_id: str | None = None, db: Session = Depends(get_db), admin: User = Depends(require_admin)) -> dict:
    target_id = user_id or admin.id
    schedule = db.query(ReminderSchedule).filter(ReminderSchedule.user_id == target_id).first()
    if not schedule:
        target = db.get(User, target_id)
        contact = db.query(UserContact).filter(UserContact.user_id == target_id).first() if target else None
        if not target or not contact:
            raise HTTPException(status_code=404, detail="User contact profile not found")
        schedule = ensure_schedule(db, target, contact)
    schedule.next_run_at = utc_now() - timedelta(seconds=1)
    # SessionLocal deliberately disables autoflush. Persist the temporary due
    # timestamp before the reminder worker queries due schedules.
    db.flush()
    delivered = run_reminder_cycle(db, force_user_id=target_id)
    db.add(AuditEvent(user_id=admin.id, event_type="reminders.tested", detail=json.dumps({"user_id": target_id, "delivered": delivered})))
    db.commit()
    return {"status": "processed", "user_id": target_id, "delivered": delivered, "note": "Development mode records simulated delivery; it does not send real messages."}


def _submission_datetime(value: datetime) -> datetime:
    if value.tzinfo:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _persist_quality_and_groundwater(db: Session, submission: SubmissionBatch) -> None:
    groundwater = json.loads(submission.groundwater_json) if submission.groundwater_json else {}
    quality = json.loads(submission.quality_json) if submission.quality_json else {}
    if groundwater and submission.device_id:
        existing = db.query(Measurement).filter(Measurement.device_id == submission.device_id, Measurement.timestamp == _submission_datetime(submission.measurement_at)).first()
        if existing:
            existing.station_id = submission.station_id
            existing.distance_cm = groundwater.get("distance_cm")
            existing.water_level_percent = groundwater.get("water_level_percent")
            existing.water_depth_cm = groundwater.get("water_depth_cm")
            existing.temperature_c = quality.get("temperature_c")
            existing.source = "user-submission"
            existing.quality_status = "reviewed"
            existing.raw_json = json.dumps({"submission_id": submission.id, "groundwater": groundwater})
        else:
            db.add(Measurement(
                owner_id=submission.user_id,
                device_id=submission.device_id,
                station_id=submission.station_id,
                timestamp=submission.measurement_at,
                distance_cm=groundwater.get("distance_cm"),
                water_level_percent=groundwater.get("water_level_percent"),
                water_depth_cm=groundwater.get("water_depth_cm"),
                temperature_c=quality.get("temperature_c"),
                source="user-submission",
                quality_status="reviewed",
                raw_json=json.dumps({"submission_id": submission.id, "groundwater": groundwater}),
            ))
    if quality:
        wqi, classification, missing = calculate_wqi({"measured_at": submission.measurement_at, "station_id": submission.station_id, **quality})
        model_result = _run_quality_model(quality)
        if model_result.get("status") == "model":
            classification = model_result.get("class") or classification
        db.add(QualityObservation(
            owner_id=submission.user_id,
            station_id=submission.station_id,
            measured_at=submission.measurement_at,
            ph=quality.get("ph"),
            tds_mg_l=quality.get("tds_mg_l"),
            ec_us_cm=quality.get("ec_us_cm"),
            turbidity_ntu=quality.get("turbidity_ntu"),
            temperature_c=quality.get("temperature_c"),
            dissolved_oxygen_mg_l=quality.get("dissolved_oxygen_mg_l"),
            hardness_mg_l=quality.get("hardness_mg_l"),
            chloride_mg_l=quality.get("chloride_mg_l"),
            wqi=wqi,
            classification=classification,
            source="user-submission",
            data_quality="partial" if missing else "valid",
        ))
    db.add(ModelExecutionRecord(submission_id=submission.id, model_name="quality-screening", model_version="extra-trees-four-parameter-0.2" if quality and model_result.get("status") == "model" else "screening-wqi-fallback-0.2", status="completed", input_json=submission.quality_json, output_json=json.dumps({"classification": classification if quality else None, "model": model_result if quality else None})))


@router.post("/submissions", response_model=SubmissionOut, status_code=201)
def create_submission(payload: SubmissionCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> SubmissionOut:
    station = db.get(Station, payload.station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Monitoring station not found")
    if payload.device_id:
        device = db.query(Device).filter(Device.device_id == payload.device_id).first()
        if not device:
            raise HTTPException(status_code=422, detail="Device identifier is not registered")
        if device.station_id and device.station_id != payload.station_id:
            raise HTTPException(status_code=422, detail="Device is assigned to another monitoring station")
    measurement_at = _submission_datetime(payload.measurement_at)
    duplicate = db.query(SubmissionBatch).filter(SubmissionBatch.user_id == user.id, SubmissionBatch.station_id == payload.station_id, SubmissionBatch.measurement_at == measurement_at, SubmissionBatch.status != "Rejected").first()
    if duplicate:
        raise HTTPException(status_code=409, detail="A submission already exists for this user, station and measurement timestamp")
    warnings = _quality_warnings(payload)
    if any(item["severity"] == "error" for item in warnings):
        raise HTTPException(status_code=422, detail=warnings[0]["detail"])
    groundwater = payload.groundwater.model_dump(exclude_none=True) if payload.groundwater else None
    quality = payload.quality.model_dump(exclude_none=True) if payload.quality else None
    status = "Draft" if payload.save_as_draft else "Submitted"
    submission = SubmissionBatch(user_id=user.id, station_id=payload.station_id, device_id=payload.device_id, measurement_at=measurement_at, submitted_at=None if status == "Draft" else utc_now(), status=status, source=payload.source, measurement_method=payload.measurement_method, remarks=payload.remarks, groundwater_json=json.dumps(groundwater) if groundwater else None, quality_json=json.dumps(quality) if quality else None, validation_json=json.dumps(warnings))
    db.add(submission)
    db.flush()
    for warning in warnings:
        db.add(DataQualityResult(submission_id=submission.id, severity=warning["severity"], code=warning["code"], field=warning.get("field"), detail=warning["detail"]))
    if status != "Draft":
        db.add(SubmissionReview(submission_id=submission.id, reviewer_id=user.id, from_status=None, to_status="Submitted", reason="User submission received"))
        db.add(Alert(owner_id=user.id, station_id=payload.station_id, severity="info", title="New monitoring submission", detail=f"Submission {submission.id} is awaiting administrator review."))
        contact = db.query(UserContact).filter(UserContact.user_id == user.id).first()
        if contact:
            contact.last_submission_at = utc_now()
    db.add(AuditEvent(user_id=user.id, event_type="submission.created", detail=json.dumps({"submission_id": submission.id, "status": status, "warnings": len(warnings)})))
    db.commit()
    db.refresh(submission)
    return as_submission(submission)


@router.get("/submissions/mine", response_model=SubmissionListResponse)
def list_my_submissions(status: str | None = None, limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0), db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> SubmissionListResponse:
    query = db.query(SubmissionBatch).filter(SubmissionBatch.user_id == user.id)
    if status:
        query = query.filter(SubmissionBatch.status == status)
    total = query.count()
    items = query.order_by(SubmissionBatch.created_at.desc()).offset(offset).limit(limit).all()
    return SubmissionListResponse(items=[as_submission(item) for item in items], total=total)


@router.get("/submissions/{submission_id}", response_model=SubmissionOut)
def get_submission(submission_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> SubmissionOut:
    submission = db.get(SubmissionBatch, submission_id)
    if not submission or (submission.user_id != user.id and user.role != "admin"):
        raise HTTPException(status_code=404, detail="Submission not found")
    return as_submission(submission)


@router.post("/submissions/{submission_id}/correction", response_model=SubmissionOut, status_code=201)
def submit_correction(submission_id: str, payload: SubmissionCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> SubmissionOut:
    original = db.get(SubmissionBatch, submission_id)
    if not original or (original.user_id != user.id and user.role != "admin"):
        raise HTTPException(status_code=404, detail="Submission not found")
    if original.status not in ("Correction Requested", "Rejected", "Draft"):
        raise HTTPException(status_code=409, detail="Only a draft, rejected, or correction-requested submission can be corrected")
    payload = payload.model_copy(update={"save_as_draft": False, "station_id": original.station_id, "device_id": payload.device_id or original.device_id})
    measurement_at = _submission_datetime(payload.measurement_at)
    warnings = _quality_warnings(payload)
    groundwater = payload.groundwater.model_dump(exclude_none=True) if payload.groundwater else None
    quality = payload.quality.model_dump(exclude_none=True) if payload.quality else None
    version = (db.query(SubmissionBatch).filter(SubmissionBatch.parent_submission_id == original.id).count() + 2)
    submission = SubmissionBatch(user_id=original.user_id, station_id=original.station_id, device_id=payload.device_id, measurement_at=measurement_at, submitted_at=utc_now(), status="Submitted", source=payload.source, measurement_method=payload.measurement_method, remarks=payload.remarks, groundwater_json=json.dumps(groundwater) if groundwater else None, quality_json=json.dumps(quality) if quality else None, validation_json=json.dumps(warnings), version=version, parent_submission_id=original.id)
    db.add(submission)
    db.flush()
    db.add(SubmissionReview(submission_id=submission.id, reviewer_id=user.id, from_status=original.status, to_status="Submitted", reason="Correction submitted"))
    db.add(Alert(owner_id=original.user_id, station_id=original.station_id, severity="info", title="Corrected submission received", detail=f"Submission {submission.id} supersedes {original.id}."))
    db.add(AuditEvent(user_id=user.id, event_type="submission.corrected", detail=json.dumps({"submission_id": submission.id, "parent_submission_id": original.id})))
    db.commit()
    db.refresh(submission)
    return as_submission(submission)


@router.post("/submissions/{submission_id}/attachments")
async def upload_submission_attachment(submission_id: str, file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    submission = db.get(SubmissionBatch, submission_id)
    if not submission or (submission.user_id != user.id and user.role != "admin"):
        raise HTTPException(status_code=404, detail="Submission not found")
    allowed_types = {"text/csv", "application/pdf", "text/plain", "application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=422, detail="Only CSV, PDF, text, Excel, JPEG, PNG, or WebP attachments are allowed")
    content = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Attachment exceeds {settings.max_upload_mb} MB")
    safe_suffix = Path(file.filename or "attachment").suffix.lower()
    if safe_suffix not in {".csv", ".pdf", ".txt", ".xls", ".xlsx", ".jpg", ".jpeg", ".png", ".webp"}:
        raise HTTPException(status_code=422, detail="Unsupported attachment extension")
    if safe_suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        try:
            content, safe_suffix = sanitize_image_upload(content, safe_suffix)
        except Exception as error:
            raise HTTPException(status_code=422, detail="Image could not be decoded and sanitized") from error
    signatures = {".pdf": b"%PDF", ".png": b"\x89PNG\r\n\x1a\n", ".jpg": b"\xff\xd8\xff", ".jpeg": b"\xff\xd8\xff", ".webp": b"RIFF"}
    signature = signatures.get(safe_suffix)
    if signature and not content.startswith(signature):
        raise HTTPException(status_code=422, detail="File content does not match its extension")
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    target = upload_dir / f"{submission.id}-{secrets.token_hex(8)}{safe_suffix}"
    target.write_bytes(content)
    attachment = SubmissionAttachment(submission_id=submission.id, filename=Path(file.filename or "attachment").name[:255], content_type=file.content_type or "application/octet-stream", size_bytes=len(content), storage_path=str(target), sha256=hashlib.sha256(content).hexdigest())
    db.add(attachment)
    db.add(AuditEvent(user_id=user.id, event_type="submission.attachment_uploaded", detail=json.dumps({"submission_id": submission.id, "filename": attachment.filename})))
    db.commit()
    return {"id": attachment.id, "filename": attachment.filename, "size_bytes": attachment.size_bytes, "status": "stored"}


@router.get("/submissions/{submission_id}/attachments")
def list_submission_attachments(submission_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict]:
    submission = db.get(SubmissionBatch, submission_id)
    if not submission or (submission.user_id != user.id and user.role != "admin"):
        raise HTTPException(status_code=404, detail="Submission not found")
    return [{"id": item.id, "filename": item.filename, "content_type": item.content_type, "size_bytes": item.size_bytes} for item in db.query(SubmissionAttachment).filter(SubmissionAttachment.submission_id == submission_id).all()]


@router.get("/submissions/{submission_id}/attachments/{attachment_id}")
def download_submission_attachment(submission_id: str, attachment_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> FileResponse:
    submission = db.get(SubmissionBatch, submission_id)
    attachment = db.get(SubmissionAttachment, attachment_id)
    if not submission or not attachment or attachment.submission_id != submission_id or (submission.user_id != user.id and user.role != "admin"):
        raise HTTPException(status_code=404, detail="Attachment not found")
    path = Path(attachment.storage_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Attachment file is unavailable")
    return FileResponse(path, media_type=attachment.content_type, filename=attachment.filename)


@router.get("/admin/submissions", response_model=SubmissionListResponse)
def admin_submissions(status: str | None = None, user_id: str | None = None, station_id: str | None = None, limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0), db: Session = Depends(get_db), admin: User = Depends(require_admin)) -> SubmissionListResponse:
    query = db.query(SubmissionBatch)
    if status:
        query = query.filter(SubmissionBatch.status == status)
    if user_id:
        query = query.filter(SubmissionBatch.user_id == user_id)
    if station_id:
        query = query.filter(SubmissionBatch.station_id == station_id)
    total = query.count()
    items = query.order_by(SubmissionBatch.created_at.desc()).offset(offset).limit(limit).all()
    return SubmissionListResponse(items=[as_submission(item) for item in items], total=total)


@router.post("/admin/submissions/{submission_id}/review", response_model=SubmissionOut)
def review_submission(submission_id: str, payload: SubmissionReviewIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)) -> SubmissionOut:
    submission = db.get(SubmissionBatch, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    if payload.status in ("Rejected", "Correction Requested") and not payload.reason:
        raise HTTPException(status_code=422, detail="A reason is required for rejection or correction requests")
    previous = submission.status
    submission.status = payload.status
    submission.review_feedback = payload.reason
    submission.reviewed_by = admin.id
    submission.reviewed_at = utc_now()
    db.add(SubmissionReview(submission_id=submission.id, reviewer_id=admin.id, from_status=previous, to_status=payload.status, reason=payload.reason))
    db.add(AuditEvent(user_id=admin.id, event_type="submission.reviewed", detail=json.dumps({"submission_id": submission.id, "from": previous, "to": payload.status})))
    if payload.status == "Approved":
        _persist_quality_and_groundwater(db, submission)
    db.commit()
    db.refresh(submission)
    return as_submission(submission)


@router.get("/admin/stats", response_model=AdminStats)
def admin_stats(db: Session = Depends(get_db), admin: User = Depends(require_admin)) -> AdminStats:
    total_submissions = db.query(SubmissionBatch).count()
    return AdminStats(
        total_users=db.query(User).count(),
        verified_users=db.query(UserContact).filter(UserContact.email_verified.is_(True), UserContact.mobile_verified.is_(True)).count(),
        active_stations=db.query(Station).count(),
        total_submissions=total_submissions,
        awaiting_review=db.query(SubmissionBatch).filter(SubmissionBatch.status.in_(["Submitted", "Under Review"])).count(),
        approved_submissions=db.query(SubmissionBatch).filter(SubmissionBatch.status == "Approved").count(),
        rejected_submissions=db.query(SubmissionBatch).filter(SubmissionBatch.status == "Rejected").count(),
        failed_reminders=db.query(NotificationDelivery).filter(NotificationDelivery.status.in_(["failed", "blocked_unverified"])).count(),
        warning_count=db.query(DataQualityResult).filter(DataQualityResult.severity != "error").count(),
    )


@router.get("/admin/users", response_model=list[UserOut])
def admin_users(limit: int = Query(default=200, ge=1, le=500), db: Session = Depends(get_db), admin: User = Depends(require_admin)) -> list[UserOut]:
    users = db.query(User).order_by(User.created_at.asc()).limit(limit).all()
    contacts = {contact.user_id: contact for contact in db.query(UserContact).filter(UserContact.user_id.in_([user.id for user in users])).all()}
    return [as_user(user, contacts.get(user.id)) for user in users]


@router.patch("/admin/users/{user_id}/role", response_model=UserOut)
def update_user_role(user_id: str, payload: AccountRoleUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)) -> UserOut:
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == admin.id and payload.role != "admin":
        raise HTTPException(status_code=409, detail="You cannot remove your own administrator role")
    target.role = payload.role
    db.add(AuditEvent(user_id=admin.id, event_type="user.role_changed", detail=json.dumps({"target_user_id": target.id, "role": payload.role})))
    db.commit()
    db.refresh(target)
    return as_user(target, db.query(UserContact).filter(UserContact.user_id == target.id).first())


@router.get("/admin/notifications", response_model=list[NotificationDeliveryOut])
def admin_notifications(limit: int = Query(default=100, ge=1, le=500), db: Session = Depends(get_db), admin: User = Depends(require_admin)) -> list[NotificationDelivery]:
    return db.query(NotificationDelivery).order_by(NotificationDelivery.scheduled_at.desc()).limit(limit).all()


@router.get("/stations", response_model=list[StationOut])
def list_stations(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[Station]:
    query = db.query(Station)
    if user.role != "admin":
        query = query.filter(Station.owner_id == user.id)
    return query.order_by(Station.name.asc()).all()


@router.post("/stations", response_model=StationOut, status_code=201)
def create_station(payload: StationCreate, db: Session = Depends(get_db), user: User = Depends(require_admin)) -> Station:
    station = Station(owner_id=user.id, **payload.model_dump())
    db.add(station)
    db.add(AuditEvent(user_id=user.id, event_type="station.created", detail=station.name))
    db.commit()
    db.refresh(station)
    return station


@router.patch("/stations/{station_id}", response_model=StationOut)
def update_station(station_id: str, payload: StationCreate, db: Session = Depends(get_db), user: User = Depends(require_admin)) -> Station:
    station = db.get(Station, station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Monitoring station not found")
    for key, value in payload.model_dump().items():
        setattr(station, key, value)
    db.add(AuditEvent(user_id=user.id, event_type="station.updated", detail=station.name))
    db.commit()
    db.refresh(station)
    return station


@router.delete("/stations/{station_id}")
def delete_station(station_id: str, db: Session = Depends(get_db), user: User = Depends(require_admin)) -> dict:
    station = db.get(Station, station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Monitoring station not found")
    if db.query(Measurement).filter(Measurement.station_id == station_id).first() or db.query(SubmissionBatch).filter(SubmissionBatch.station_id == station_id).first():
        raise HTTPException(status_code=409, detail="Station has stored readings or submissions and cannot be deleted")
    db.add(AuditEvent(user_id=user.id, event_type="station.deleted", detail=station.name))
    db.delete(station)
    db.commit()
    return {"status": "deleted", "station_id": station_id}


@router.get("/devices", response_model=list[DeviceOut])
def list_devices(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[DeviceOut]:
    query = db.query(Device)
    if user.role != "admin":
        query = query.join(Station, Device.station_id == Station.id).filter(Station.owner_id == user.id)
    now = utc_now()
    devices = query.order_by(Device.created_at.desc()).all()
    result: list[DeviceOut] = []
    for device in devices:
        status = device.status
        if status == "online" and (not device.last_seen_at or device.last_seen_at < now - timedelta(seconds=10)):
            status = "offline"
        result.append(DeviceOut.model_validate(device).model_copy(update={"status": status}))
    return result


@router.post("/devices", response_model=DeviceOut, status_code=201)
def create_device(payload: DeviceCreate, db: Session = Depends(get_db), user: User = Depends(require_admin)) -> Device:
    if db.query(Device).filter(Device.device_id == payload.device_id).first():
        raise HTTPException(status_code=409, detail="Device identifier already registered")
    if not payload.ingest_key:
        raise HTTPException(status_code=422, detail="A unique device ingestion key is required")
    if payload.station_id and not db.get(Station, payload.station_id):
        raise HTTPException(status_code=404, detail="Monitoring station not found")
    device = Device(device_id=payload.device_id, name=payload.name, device_type=payload.device_type, station_id=payload.station_id, ingest_key=payload.ingest_key)
    db.add(device)
    db.add(AuditEvent(user_id=user.id, event_type="device.created", detail=device.device_id))
    db.commit()
    db.refresh(device)
    return device


@router.patch("/devices/{device_id}", response_model=DeviceOut)
def update_device(device_id: str, payload: DeviceUpdate, db: Session = Depends(get_db), user: User = Depends(require_admin)) -> Device:
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    values = payload.model_dump(exclude_unset=True)
    if values.get("station_id") and not db.get(Station, values["station_id"]):
        raise HTTPException(status_code=404, detail="Monitoring station not found")
    for key, value in values.items():
        setattr(device, key, value)
    db.add(AuditEvent(user_id=user.id, event_type="device.updated", detail=json.dumps({"device_id": device_id, "fields": list(values)})))
    db.commit()
    db.refresh(device)
    return device


@router.delete("/devices/{device_id}")
def delete_device(device_id: str, db: Session = Depends(get_db), user: User = Depends(require_admin)) -> dict:
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    if db.query(Measurement).filter(Measurement.device_id == device_id).first():
        raise HTTPException(status_code=409, detail="Device has measurement history; mark it offline instead of deleting it")
    db.add(AuditEvent(user_id=user.id, event_type="device.deleted", detail=device_id))
    db.delete(device)
    db.commit()
    return {"status": "deleted", "device_id": device_id}


@router.post("/ingest/http", response_model=MeasurementOut, status_code=201)
async def ingest_http(payload: MeasurementIn, x_device_key: Annotated[str | None, Header()] = None, x_idempotency_key: Annotated[str | None, Header()] = None, db: Session = Depends(get_db)) -> Measurement:
    device = db.query(Device).filter(Device.device_id == payload.device_id).first()
    # The deployment key can securely provision the first known ESP32 device.
    # The measurement remains pending_review and still requires admin approval.
    if device is None and x_device_key and secrets.compare_digest(x_device_key, settings.device_ingest_key):
        device = Device(device_id=payload.device_id, name=f"{payload.device_id} ultrasonic level sensor", device_type="ESP32", ingest_key=x_device_key, status="online")
        db.add(device)
        db.flush()
    allowed = bool(x_device_key and device and secrets.compare_digest(x_device_key, device.ingest_key))
    if not allowed:
        raise HTTPException(status_code=401, detail="Valid device ingestion key required")
    measurement = save_measurement_with_key(db, payload, source="http", idempotency_key=x_idempotency_key)
    # Ownerless pending packets are delivered only to admin WebSocket clients;
    # owner-scoped packets remain restricted to that owner and admins.
    await socket_manager.broadcast({"event": "measurement.created", "measurement": MeasurementOut.model_validate(measurement).model_dump(mode="json")})
    return measurement


@router.post("/location/sync")
def sync_live_location(payload: LocationSyncIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    """Update the active station so subsequent device packets carry this site snapshot."""
    station = db.query(Station).filter(Station.owner_id == user.id).order_by(Station.created_at.asc()).first()
    if not station:
        station = Station(name="Live browser site", owner_id=user.id)
        db.add(station)
    station.latitude = payload.latitude
    station.longitude = payload.longitude
    station.country = payload.country or station.country
    station.state = payload.state or station.state
    station.district = payload.district or station.district
    if payload.label:
        station.description = payload.label
    db.add(AuditEvent(user_id=user.id, event_type="location.synced", detail=json.dumps(payload.model_dump(mode="json"))))
    db.commit()
    return {"station_id": station.id, "latitude": station.latitude, "longitude": station.longitude, "updated_at": payload.updated_at}


@router.get("/measurements", response_model=list[MeasurementOut])
def list_measurements(station_id: str | None = None, status: str | None = None, limit: int = Query(default=200, ge=1, le=2000), db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[Measurement]:
    query = db.query(Measurement)
    if user.role != "admin":
        query = query.filter(Measurement.owner_id == user.id)
        query = query.filter(Measurement.quality_status == (status or "reviewed"))
    elif status:
        query = query.filter(Measurement.quality_status == status)
    else:
        query = query.filter(Measurement.quality_status == "reviewed")
    if station_id:
        query = query.filter(Measurement.station_id == station_id)
    return query.order_by(desc(Measurement.timestamp)).limit(limit).all()


def _latest_measurement_per_device(rows: list[Measurement], limit: int) -> list[Measurement]:
    latest: list[Measurement] = []
    seen: set[str] = set()
    for row in rows:
        if row.device_id in seen:
            continue
        seen.add(row.device_id)
        latest.append(row)
        if len(latest) >= limit:
            break
    return latest


@router.get("/measurements/live", response_model=list[MeasurementOut])
def live_measurements(limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[Measurement]:
    """Recent device packets only; this endpoint drives online/offline state."""
    query = db.query(Measurement).filter(
        Measurement.source == "http",
        Measurement.quality_status == "pending_review",
        Measurement.created_at >= utc_now() - timedelta(seconds=10),
    )
    if user.role != "admin":
        query = query.filter(Measurement.owner_id == user.id)
    recent = query.order_by(desc(Measurement.created_at)).limit(2000).all()
    return _latest_measurement_per_device(recent, limit)


@router.get("/measurements/live-preview", response_model=list[MeasurementOut])
def live_measurements_preview(limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[Measurement]:
    """Compatibility alias for the authenticated live-reading list."""
    query = db.query(Measurement).filter(Measurement.source == "http")
    if user.role != "admin":
        query = query.filter(Measurement.owner_id == user.id)
    return query.order_by(desc(Measurement.timestamp)).limit(limit).all()


@router.get("/admin/measurements", response_model=list[MeasurementOut])
def admin_measurements(status: str = "pending_review", limit: int = Query(default=200, ge=1, le=2000), db: Session = Depends(get_db), admin: User = Depends(require_admin)) -> list[Measurement]:
    return db.query(Measurement).filter(Measurement.quality_status == status).order_by(desc(Measurement.timestamp)).limit(limit).all()


@router.get("/admin/measurements/live", response_model=list[MeasurementOut])
def admin_live_measurements(limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db), admin: User = Depends(require_admin)) -> list[Measurement]:
    recent = db.query(Measurement).filter(
        Measurement.source == "http",
        Measurement.quality_status == "pending_review",
        Measurement.created_at >= utc_now() - timedelta(seconds=10),
    ).order_by(desc(Measurement.created_at)).limit(2000).all()
    return _latest_measurement_per_device(recent, limit)


@router.post("/admin/measurements/{measurement_id}/review", response_model=MeasurementOut)
async def review_measurement(measurement_id: str, payload: SubmissionReviewIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)) -> Measurement:
    if payload.status not in {"Approved", "Rejected"}:
        raise HTTPException(status_code=422, detail="Live readings can only be approved or rejected")
    measurement = db.get(Measurement, measurement_id)
    if not measurement:
        raise HTTPException(status_code=404, detail="Measurement not found")
    measurement.quality_status = "reviewed" if payload.status == "Approved" else "rejected"
    pending_title = f"Device review required · {measurement.device_id}"
    pending_alerts = db.query(Alert).filter(Alert.title == pending_title, Alert.state == "active").all()
    for alert in pending_alerts:
        alert.state = "resolved"
        alert.resolved_at = utc_now()
    db.add(Alert(owner_id=measurement.owner_id, station_id=measurement.station_id, severity="info", title=f"Device reading {payload.status.lower()} · {measurement.device_id}", detail=f"Measurement {measurement.id} was {payload.status.lower()} by the administrator."))
    db.add(AuditEvent(user_id=admin.id, event_type="measurement.reviewed", detail=json.dumps({"measurement_id": measurement.id, "status": payload.status, "reason": payload.reason})))
    db.commit()
    db.refresh(measurement)
    await socket_manager.broadcast({"event": "measurement.reviewed", "measurement": MeasurementOut.model_validate(measurement).model_dump(mode="json")})
    return measurement


@router.post("/quality", response_model=QualityObservationOut, status_code=201)
def create_quality(payload: QualityObservationIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> QualityObservation:
    values = payload.model_dump()
    wqi, classification, missing = calculate_wqi(values)
    model_result = _run_quality_model(values)
    if model_result.get("status") == "model":
        classification = model_result.get("class") or classification
    observation = QualityObservation(owner_id=user.id, **values, wqi=wqi, classification=classification, data_quality="pending_review" if user.role != "admin" else ("partial" if missing else "valid"))
    db.add(observation)
    db.add(AuditEvent(user_id=user.id, event_type="quality.created", detail=json.dumps({"station_id": payload.station_id, "missing": missing})))
    db.commit()
    db.refresh(observation)
    return observation


@router.get("/quality", response_model=list[QualityObservationOut])
def list_quality(station_id: str | None = None, limit: int = Query(default=200, ge=1, le=2000), db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[QualityObservation]:
    query = db.query(QualityObservation)
    if user.role != "admin":
        query = query.filter(QualityObservation.owner_id == user.id)
    if station_id:
        query = query.filter(QualityObservation.station_id == station_id)
    return query.order_by(desc(QualityObservation.measured_at)).limit(limit).all()


@router.post("/imports/inspect")
async def inspect_dataset(file: UploadFile = File(...), user: User = Depends(require_admin)) -> dict:
    if not file.filename or not file.filename.lower().endswith((".csv", ".tsv")):
        raise HTTPException(status_code=422, detail="Upload a CSV or TSV dataset")
    content = await file.read()
    try:
        import pandas as pd

        separator = "\t" if file.filename.lower().endswith(".tsv") else ","
        frame = pd.read_csv(io.BytesIO(content), sep=separator, nrows=5000)
        columns = [str(column) for column in frame.columns]
        lower_columns = {column.lower(): column for column in columns}
        datetime_candidates = [column for column in columns if any(token in column.lower() for token in ("date", "time", "timestamp"))]
        station_candidates = [column for column in columns if any(token in column.lower() for token in ("station", "well", "site", "location"))]
        level_candidates = [column for column in columns if any(token in column.lower() for token in ("water_level", "groundwater", "depth", "level"))]
        return {"filename": file.filename, "sample_rows": len(frame), "columns": columns, "datetime_candidates": datetime_candidates, "station_candidates": station_candidates, "groundwater_candidates": level_candidates, "missing_values": {str(key): int(value) for key, value in frame.isna().sum().items()}, "note": "Inspection only. Confirm mappings before importing observations."}
    except Exception as error:
        raise HTTPException(status_code=422, detail=f"Could not inspect dataset: {error}") from error


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(station_id: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> DashboardResponse:
    # Only reviewed readings are official analytics. Demo and raw live device
    # readings stay out of the official dashboard until an administrator approves them.
    measurement_query = db.query(Measurement).filter(Measurement.quality_status == "reviewed")
    quality_query = db.query(QualityObservation).filter(QualityObservation.data_quality != "pending_review")
    if user.role != "admin":
        measurement_query = measurement_query.filter(Measurement.owner_id == user.id)
        quality_query = quality_query.filter(QualityObservation.owner_id == user.id)
    if station_id:
        measurement_query = measurement_query.filter(Measurement.station_id == station_id)
        quality_query = quality_query.filter(QualityObservation.station_id == station_id)
    measurements = measurement_query.order_by(desc(Measurement.timestamp)).limit(500).all()
    latest = measurements[0] if measurements else None
    latest_quality = quality_query.order_by(desc(QualityObservation.measured_at)).first()
    levels = [item.water_level_percent for item in reversed(measurements) if item.water_level_percent is not None]
    forecast = fallback_forecast(levels) if levels else None
    alert_query = db.query(Alert).filter(Alert.state != "resolved")
    if user.role != "admin":
        alert_query = alert_query.filter(Alert.owner_id == user.id)
    alerts = alert_query.order_by(desc(Alert.created_at)).limit(5).all()
    online = db.query(Device).filter(Device.status == "online").count()
    approved_count = db.query(Measurement).filter(Measurement.quality_status == "reviewed").count()
    return DashboardResponse(status="online" if online else "offline", measurement_count=approved_count, station_count=db.query(Station).count(), device_count=db.query(Device).count(), online_devices=online, latest_measurement=MeasurementOut.model_validate(latest) if latest else None, latest_quality=QualityObservationOut.model_validate(latest_quality) if latest_quality else None, active_alerts=[AlertOut.model_validate(alert) for alert in alerts], forecast=forecast, limitations=["Only administrator-approved readings enter official dashboard analytics.", "Forecast is a transparent trend fallback until a compatible trained groundwater artifact is configured.", "Water quality screening does not certify potability or detect all contaminants."])


@router.get("/alerts", response_model=list[AlertOut])
def list_alerts(state: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[Alert]:
    query = db.query(Alert)
    if user.role != "admin":
        query = query.filter(Alert.owner_id == user.id)
    if state:
        query = query.filter(Alert.state == state)
    return query.order_by(desc(Alert.created_at)).limit(500).all()


@router.get("/alerts/live-preview", response_model=list[AlertOut])
def live_alerts_preview(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[Alert]:
    # Retain this route for existing clients, but scope it exactly like /alerts.
    query = db.query(Alert).filter(Alert.state != "resolved")
    if user.role != "admin":
        query = query.filter(Alert.owner_id == user.id)
    return query.order_by(desc(Alert.created_at)).limit(100).all()


@router.patch("/alerts/{alert_id}", response_model=AlertOut)
def update_alert(alert_id: str, payload: AlertStateUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Alert:
    alert = db.query(Alert).filter(Alert.id == alert_id, *( [] if user.role == "admin" else [Alert.owner_id == user.id] )).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.state = payload.state
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if payload.state == "acknowledged":
        alert.acknowledged_at = now
    if payload.state == "resolved":
        alert.resolved_at = now
    db.commit()
    db.refresh(alert)
    return alert


@router.post("/advisor", response_model=AdvisorResponse)
def advisor(payload: AdvisorRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> AdvisorResponse:
    question = payload.question.lower()
    latest = db.query(Measurement).order_by(desc(Measurement.timestamp)).first()
    quality = db.query(QualityObservation).order_by(desc(QualityObservation.measured_at)).first()
    active = db.query(Alert).filter(Alert.state != "resolved").count()
    if "wqi" in question or "quality" in question:
        quality_query = db.query(QualityObservation).filter(QualityObservation.data_quality != "pending_review")
        if user.role != "admin":
            quality_query = quality_query.filter(QualityObservation.owner_id == user.id)
        quality = quality_query.order_by(desc(QualityObservation.measured_at)).first()
        answer = f"The latest available quality screening is {quality.classification or 'not classified'} with WQI {quality.wqi if quality.wqi is not None else 'unavailable'}. This is a screening result, not a potability certificate." if quality else "No approved water-quality observation is available yet. Add or approve an observation to calculate the screening score."
        links = ["/quality", "/reports"]
    elif "alert" in question:
        alert_query = db.query(Alert).filter(Alert.state != "resolved")
        if user.role != "admin":
            alert_query = alert_query.filter(Alert.owner_id == user.id)
        active = alert_query.count()
        answer = f"There are {active} unresolved alerts. Review their severity, evidence and station before taking action." 
        links = ["/alerts"]
    elif "level" in question or "groundwater" in question or "fall" in question:
        measurement_query = db.query(Measurement).filter(Measurement.quality_status == "reviewed")
        if user.role != "admin":
            measurement_query = measurement_query.filter(Measurement.owner_id == user.id)
        latest = measurement_query.order_by(desc(Measurement.timestamp)).first()
        answer = f"The latest stored groundwater reading is {latest.water_level_percent if latest and latest.water_level_percent is not None else 'unavailable'}% level. Forecasts use the transparent fallback unless a trained artifact is configured." if latest else "No groundwater readings are stored yet. Register a device or import a dataset."
        links = ["/groundwater", "/history"]
    elif "conserve" in question:
        answer = "Prioritize leak checks, stagger pumping, record daily levels, protect recharge areas and investigate rapid declines before increasing extraction."
        links = ["/education", "/groundwater"]
    else:
        answer = "I can answer about current groundwater status, WQI, alerts, forecast meaning and conservation using the data currently stored in HydroInsight."
        links = ["/dashboard", "/advisor"]
    return AdvisorResponse(answer=answer, sources=["Stored measurements", "Stored quality observations", "Transparent fallback logic"], links=links)


@router.get("/reports/measurements.csv")
def measurements_csv(station_id: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> StreamingResponse:
    query = db.query(Measurement)
    if user.role != "admin":
        query = query.filter(Measurement.owner_id == user.id)
    if station_id:
        query = query.filter(Measurement.station_id == station_id)
    rows = query.order_by(Measurement.timestamp.asc()).all()
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["device_id", "station_id", "timestamp", "distance_cm", "water_level_percent", "water_depth_cm", "temperature_c", "source", "quality_status"])
    for row in rows:
        writer.writerow([row.device_id, row.station_id, row.timestamp.isoformat(), row.distance_cm, row.water_level_percent, row.water_depth_cm, row.temperature_c, row.source, row.quality_status])
    return StreamingResponse(iter([stream.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=hydroinsight-measurements.csv"})


@router.get("/reports/summary.pdf")
def summary_pdf(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> StreamingResponse:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except ImportError as error:
        raise HTTPException(status_code=503, detail="PDF export requires reportlab; install backend requirements") from error
    stream = io.BytesIO()
    document = canvas.Canvas(stream, pagesize=A4)
    measurement_query = db.query(Measurement)
    quality_query = db.query(QualityObservation)
    station_query = db.query(Station)
    device_query = db.query(Device)
    if user.role != "admin":
        measurement_query = measurement_query.filter(Measurement.owner_id == user.id)
        quality_query = quality_query.filter(QualityObservation.owner_id == user.id)
        station_query = station_query.filter(Station.owner_id == user.id)
        device_query = device_query.outerjoin(Station, Device.station_id == Station.id).filter((Station.owner_id == user.id) | (Device.station_id.is_(None)))
    measurements = measurement_query.filter(Measurement.quality_status == "reviewed").order_by(Measurement.timestamp.desc()).limit(500).all()
    quality_rows = quality_query.order_by(QualityObservation.measured_at.desc()).limit(10).all()
    document.setTitle("AquaSense AI monitoring summary")
    document.drawString(50, 800, "AquaSense AI monitoring summary")
    document.drawString(50, 780, f"Generated: {datetime.now(timezone.utc).isoformat()}")
    document.drawString(50, 750, f"Stations: {station_query.count()}   Devices: {device_query.count()}   Approved measurements: {len(measurements)}")
    document.drawString(50, 720, "Forecast model: transparent-fallback (not a trained model output)")
    document.drawString(50, 700, "Quality limitation: measured inputs do not certify potability or detect all contaminants.")
    y = 670
    document.drawString(50, y, "Latest approved readings (device | timestamp | distance cm | level %)")
    for row in measurements[:25]:
        y -= 18
        if y < 55:
            document.showPage()
            y = 800
        document.drawString(50, y, f"{row.device_id} | {row.timestamp.isoformat()} | {row.distance_cm if row.distance_cm is not None else '—'} | {row.water_level_percent if row.water_level_percent is not None else '—'}")
    y -= 28
    if y < 80:
        document.showPage()
        y = 800
    document.drawString(50, y, "Recent water quality screening")
    for row in quality_rows:
        y -= 18
        if y < 55:
            document.showPage()
            y = 800
        document.drawString(50, y, f"{row.measured_at.isoformat()} | pH {row.ph} | TDS {row.tds_mg_l} mg/L | turbidity {row.turbidity_ntu} NTU | {row.classification or 'unclassified'}")
    document.save()
    stream.seek(0)
    return StreamingResponse(stream, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=hydroinsight-summary.pdf"})


@router.websocket("/ws/measurements")
async def measurements_socket(websocket: WebSocket) -> None:
    # Authenticate from the HttpOnly cookie; never put bearer tokens in URLs.
    token = websocket.cookies.get("aquasense_session")
    from ..db import SessionLocal
    db = SessionLocal()
    try:
        session = db.get(SessionToken, token) if token else None
        if not session or session.expires_at < utc_now():
            await websocket.close(code=4401)
            return
        user = db.get(User, session.user_id)
        if not user or not user.is_active:
            await websocket.close(code=4401)
            return
        websocket.state.aquasense_role = user.role
        await socket_manager.connect(websocket, user.id)
    finally:
        db.close()
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        socket_manager.disconnect(websocket)

