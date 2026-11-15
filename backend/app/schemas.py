from datetime import datetime
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

try:
    import phonenumbers
except ImportError:  # pragma: no cover - requirements install provides this in deployment
    phonenumbers = None


class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=255)
    mobile_number: str = Field(min_length=8, max_length=20)
    password: str = Field(min_length=8, max_length=128)
    password_confirmation: str = Field(min_length=8, max_length=128)
    reminder_consent: bool = False
    preferred_reminder_channel: Literal["email", "sms", "both"] = "email"
    timezone: str = Field(default="Asia/Kolkata", min_length=1, max_length=64)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("mobile_number")
    @classmethod
    def normalize_mobile(cls, value: str) -> str:
        normalized = re.sub(r"[\s().-]", "", value.strip())
        if normalized.startswith("00"):
            normalized = "+" + normalized[2:]
        if phonenumbers is not None:
            try:
                parsed = phonenumbers.parse(normalized, None)
                if not phonenumbers.is_valid_number(parsed):
                    raise ValueError("Mobile number is not valid for its country code")
                return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
            except phonenumbers.NumberParseException as error:
                raise ValueError("Mobile number must use international format, for example +919876543210") from error
        if not re.fullmatch(r"\+[1-9]\d{7,14}", normalized):
            raise ValueError("Mobile number must use international format, for example +919876543210")
        return normalized

    @field_validator("password_confirmation")
    @classmethod
    def password_matches(cls, value: str, info: Any) -> str:
        password = info.data.get("password")
        if password and value != password:
            raise ValueError("Password confirmation does not match password")
        return value


class SignIn(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: str
    role: str
    created_at: datetime
    mobile_number: str | None = None
    email_verified: bool = False
    mobile_verified: bool = False
    account_status: str = "active"
    reminder_consent: bool = False
    preferred_reminder_channel: str = "email"
    timezone: str = "Asia/Kolkata"


class AuthResponse(BaseModel):
    token: str | None = None
    user: UserOut


class ForgotPassword(BaseModel):
    email: str = Field(min_length=5, max_length=255)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class ResetPassword(BaseModel):
    token: str = Field(min_length=12, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class StationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str | None = None
    country: str | None = None
    state: str | None = None
    district: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class StationOut(StationCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    risk_level: str
    created_at: datetime


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    preferred_language: str | None = Field(default=None, max_length=20)
    timezone: str | None = Field(default=None, max_length=64)
    reminder_consent: bool | None = None
    preferred_reminder_channel: Literal["email", "sms", "both"] | None = None


class LocationSyncIn(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy: float = Field(default=50, ge=0, le=100000)
    updated_at: datetime
    label: str | None = Field(default=None, max_length=240)
    country: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    district: str | None = Field(default=None, max_length=120)


class VerificationRequest(BaseModel):
    channel: Literal["email", "mobile"]


class VerificationConfirm(BaseModel):
    channel: Literal["email", "mobile"]
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class ReminderScheduleIn(BaseModel):
    enabled: bool = True
    weekday: int = Field(default=0, ge=0, le=6)
    local_time: str = Field(default="09:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    timezone: str = Field(default="Asia/Kolkata", min_length=1, max_length=64)
    channels: list[Literal["email", "sms"]] = Field(default_factory=lambda: ["email"], min_length=1, max_length=2)


class ReminderScheduleOut(ReminderScheduleIn):
    id: str
    user_id: str
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None


class NotificationDeliveryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    reminder_type: str
    scheduled_at: datetime
    sent_at: datetime | None
    channel: str
    status: str
    provider_message_id: str | None
    failure_reason: str | None
    retry_count: int


class DeviceCreate(BaseModel):
    device_id: str = Field(min_length=2, max_length=100)
    name: str = Field(min_length=2, max_length=160)
    device_type: str = "ESP32"
    station_id: str | None = None
    ingest_key: str | None = None


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    device_id: str
    name: str
    device_type: str
    station_id: str | None
    status: str
    last_seen_at: datetime | None
    created_at: datetime


class MeasurementIn(BaseModel):
    device_id: str = Field(min_length=2, max_length=100)
    timestamp: datetime
    distance_cm: float | None = Field(default=None, ge=0)
    water_level_percent: float | None = Field(default=None, ge=0, le=100)
    water_depth_cm: float | None = Field(default=None, ge=0)
    temperature_c: float | None = Field(default=None, ge=-50, le=100)


class MeasurementOut(MeasurementIn):
    model_config = ConfigDict(from_attributes=True)

    id: str
    owner_id: str | None = None
    station_id: str | None
    site_latitude: float | None = None
    site_longitude: float | None = None
    site_accuracy_m: float | None = None
    location_updated_at: datetime | None = None
    source: str
    quality_status: str
    created_at: datetime


class QualityObservationIn(BaseModel):
    station_id: str | None = None
    measured_at: datetime
    ph: float | None = Field(default=None, ge=0, le=14)
    tds_mg_l: float | None = Field(default=None, ge=0)
    ec_us_cm: float | None = Field(default=None, ge=0)
    turbidity_ntu: float | None = Field(default=None, ge=0)
    temperature_c: float | None = Field(default=None, ge=-50, le=100)
    dissolved_oxygen_mg_l: float | None = Field(default=None, ge=0)
    hardness_mg_l: float | None = Field(default=None, ge=0)
    chloride_mg_l: float | None = Field(default=None, ge=0)
    source: str = "manual"


class QualityObservationOut(QualityObservationIn):
    model_config = ConfigDict(from_attributes=True)

    id: str
    wqi: float | None
    classification: str | None
    data_quality: str


class GroundwaterSubmission(BaseModel):
    groundwater_level_m: float | None = Field(default=None, ge=-1000, le=1000)
    distance_cm: float | None = Field(default=None, ge=0, le=100000)
    water_depth_cm: float | None = Field(default=None, ge=0, le=100000)
    water_level_percent: float | None = Field(default=None, ge=0, le=100)
    rainfall_mm: float | None = Field(default=None, ge=0, le=5000)
    contextual_observation: str | None = Field(default=None, max_length=1000)


class QualitySubmission(BaseModel):
    ph: float | None = Field(default=None, ge=0, le=14)
    tds_mg_l: float | None = Field(default=None, ge=0, le=100000)
    ec_us_cm: float | None = Field(default=None, ge=0, le=200000)
    turbidity_ntu: float | None = Field(default=None, ge=0, le=100000)
    temperature_c: float | None = Field(default=None, ge=-50, le=100)
    dissolved_oxygen_mg_l: float | None = Field(default=None, ge=0, le=100)
    hardness_mg_l: float | None = Field(default=None, ge=0, le=100000)
    chloride_mg_l: float | None = Field(default=None, ge=0, le=100000)
    laboratory_results: dict[str, Any] | None = None
    instrument_id: str | None = Field(default=None, max_length=120)


class SubmissionCreate(BaseModel):
    station_id: str
    device_id: str | None = None
    measurement_at: datetime
    measurement_method: str = Field(default="manual", min_length=2, max_length=60)
    source: Literal["user-entered", "device", "laboratory", "imported"] = "user-entered"
    groundwater: GroundwaterSubmission | None = None
    quality: QualitySubmission | None = None
    remarks: str | None = Field(default=None, max_length=2000)
    save_as_draft: bool = False


class SubmissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    station_id: str
    device_id: str | None
    measurement_at: datetime
    submitted_at: datetime | None
    status: str
    source: str
    measurement_method: str
    remarks: str | None
    groundwater: dict[str, Any] | None = None
    quality: dict[str, Any] | None = None
    validation_warnings: list[dict[str, Any]] = Field(default_factory=list)
    review_feedback: str | None
    reviewed_by: str | None
    reviewed_at: datetime | None
    version: int
    parent_submission_id: str | None
    created_at: datetime
    updated_at: datetime


class SubmissionReviewIn(BaseModel):
    status: Literal["Under Review", "Approved", "Rejected", "Correction Requested"]
    reason: str | None = Field(default=None, max_length=2000)


class AdminStats(BaseModel):
    total_users: int
    verified_users: int
    active_stations: int
    total_submissions: int
    awaiting_review: int
    approved_submissions: int
    rejected_submissions: int
    failed_reminders: int
    warning_count: int


class SubmissionListResponse(BaseModel):
    items: list[SubmissionOut]
    total: int


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    station_id: str | None
    severity: str
    title: str
    detail: str
    state: str
    created_at: datetime


class AlertStateUpdate(BaseModel):
    state: str = Field(pattern="^(active|acknowledged|resolved)$")


class AdvisorRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    station_id: str | None = None


class AdvisorResponse(BaseModel):
    answer: str
    sources: list[str]
    links: list[str]


class DashboardResponse(BaseModel):
    status: str
    measurement_count: int
    station_count: int
    device_count: int
    online_devices: int
    latest_measurement: MeasurementOut | None
    latest_quality: QualityObservationOut | None
    active_alerts: list[AlertOut]
    forecast: dict[str, Any] | None
    limitations: list[str]

