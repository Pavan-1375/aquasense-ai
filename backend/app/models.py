from datetime import datetime, timezone
import uuid

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def new_id() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    role: Mapped[str] = mapped_column(String(20), default="user", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class UserContact(Base):
    __tablename__ = "user_contacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    mobile_e164: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    mobile_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    account_status: Mapped[str] = mapped_column(String(30), default="active")
    preferred_language: Mapped[str] = mapped_column(String(20), default="en-IN")
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
    reminder_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    preferred_reminder_channel: Mapped[str] = mapped_column(String(20), default="email")
    last_reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_scheduled_reminder_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_submission_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class SessionToken(Base):
    __tablename__ = "session_tokens"

    token: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    token: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class PasswordRecoveryCode(Base):
    __tablename__ = "password_recovery_codes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    code_hash: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class VerificationCode(Base):
    __tablename__ = "verification_codes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    channel: Mapped[str] = mapped_column(String(20), index=True)
    code_hash: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class Station(Base):
    __tablename__ = "stations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    district: Mapped[str | None] = mapped_column(String(120), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_level: Mapped[str] = mapped_column(String(30), default="unknown")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    device_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    device_type: Mapped[str] = mapped_column(String(60), default="ESP32")
    station_id: Mapped[str | None] = mapped_column(ForeignKey("stations.id"), nullable=True, index=True)
    ingest_key: Mapped[str] = mapped_column(String(180))
    status: Mapped[str] = mapped_column(String(30), default="offline")
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    calibration_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class Measurement(Base):
    __tablename__ = "measurements"
    __table_args__ = (UniqueConstraint("device_id", "timestamp", name="uq_measurement_device_timestamp"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    device_id: Mapped[str] = mapped_column(String(100), ForeignKey("devices.device_id"), index=True)
    station_id: Mapped[str | None] = mapped_column(ForeignKey("stations.id"), nullable=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    distance_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    water_level_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    water_depth_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    site_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    site_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    site_accuracy_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source: Mapped[str] = mapped_column(String(30), default="device")
    quality_status: Mapped[str] = mapped_column(String(30), default="valid")
    raw_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class IngestionReceipt(Base):
    """Durable idempotency record for device-originated measurements."""

    __tablename__ = "ingestion_receipts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    idempotency_key: Mapped[str] = mapped_column(String(220), unique=True, index=True)
    device_id: Mapped[str] = mapped_column(String(100), ForeignKey("devices.device_id"), index=True)
    measurement_id: Mapped[str] = mapped_column(String(36), ForeignKey("measurements.id"), unique=True, index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)


class QualityObservation(Base):
    __tablename__ = "quality_observations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    station_id: Mapped[str | None] = mapped_column(ForeignKey("stations.id"), nullable=True, index=True)
    measured_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    ph: Mapped[float | None] = mapped_column(Float, nullable=True)
    tds_mg_l: Mapped[float | None] = mapped_column(Float, nullable=True)
    ec_us_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    turbidity_ntu: Mapped[float | None] = mapped_column(Float, nullable=True)
    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    dissolved_oxygen_mg_l: Mapped[float | None] = mapped_column(Float, nullable=True)
    hardness_mg_l: Mapped[float | None] = mapped_column(Float, nullable=True)
    chloride_mg_l: Mapped[float | None] = mapped_column(Float, nullable=True)
    wqi: Mapped[float | None] = mapped_column(Float, nullable=True)
    classification: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source: Mapped[str] = mapped_column(String(30), default="manual")
    data_quality: Mapped[str] = mapped_column(String(30), default="valid")


class Forecast(Base):
    __tablename__ = "forecasts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    station_id: Mapped[str | None] = mapped_column(ForeignKey("stations.id"), nullable=True, index=True)
    forecast_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    horizon_days: Mapped[int] = mapped_column(Integer)
    predicted_level_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    lower_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    upper_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_name: Mapped[str] = mapped_column(String(80), default="transparent-fallback")
    model_version: Mapped[str] = mapped_column(String(80), default="fallback-0.1")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    station_id: Mapped[str | None] = mapped_column(ForeignKey("stations.id"), nullable=True, index=True)
    severity: Mapped[str] = mapped_column(String(20), default="info")
    title: Mapped[str] = mapped_column(String(180))
    detail: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(20), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ModelMetadata(Base):
    __tablename__ = "model_metadata"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), index=True)
    version: Mapped[str] = mapped_column(String(80))
    task: Mapped[str] = mapped_column(String(80))
    training_timestamp: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    metrics_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifact_path: Mapped[str | None] = mapped_column(String(300), nullable=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)


class ReminderSchedule(Base):
    __tablename__ = "reminder_schedules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    weekday: Mapped[int] = mapped_column(Integer, default=0)
    local_time: Mapped[str] = mapped_column(String(5), default="09:00")
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
    channels_json: Mapped[str] = mapped_column(Text, default='["email"]')
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    reminder_type: Mapped[str] = mapped_column(String(40), default="weekly_submission")
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    channel: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    idempotency_key: Mapped[str] = mapped_column(String(220), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class SubmissionBatch(Base):
    __tablename__ = "submission_batches"
    __table_args__ = (UniqueConstraint("user_id", "station_id", "measurement_at", "version", name="uq_submission_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    station_id: Mapped[str] = mapped_column(ForeignKey("stations.id"), index=True)
    device_id: Mapped[str | None] = mapped_column(ForeignKey("devices.device_id"), nullable=True, index=True)
    measurement_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="Draft", index=True)
    source: Mapped[str] = mapped_column(String(30), default="user-entered")
    measurement_method: Mapped[str] = mapped_column(String(60), default="manual")
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    groundwater_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    quality_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_json: Mapped[str] = mapped_column(Text, default="[]")
    review_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    parent_submission_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class SubmissionAttachment(Base):
    __tablename__ = "submission_attachments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    submission_id: Mapped[str] = mapped_column(ForeignKey("submission_batches.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer)
    storage_path: Mapped[str] = mapped_column(String(400))
    sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class SubmissionReview(Base):
    __tablename__ = "submission_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    submission_id: Mapped[str] = mapped_column(ForeignKey("submission_batches.id"), index=True)
    reviewer_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    from_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    to_status: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class DataQualityResult(Base):
    __tablename__ = "data_quality_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    submission_id: Mapped[str] = mapped_column(ForeignKey("submission_batches.id"), index=True)
    severity: Mapped[str] = mapped_column(String(20), default="warning")
    code: Mapped[str] = mapped_column(String(80))
    field: Mapped[str | None] = mapped_column(String(100), nullable=True)
    detail: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class ModelExecutionRecord(Base):
    __tablename__ = "model_execution_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    submission_id: Mapped[str | None] = mapped_column(ForeignKey("submission_batches.id"), nullable=True, index=True)
    model_name: Mapped[str] = mapped_column(String(120))
    model_version: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(30), default="pending")
    input_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

