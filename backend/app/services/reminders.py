"""Persistent weekly reminder scheduling with idempotent development delivery.

Provider calls are intentionally isolated here. Development mode records a
simulated delivery; production providers can be wired without changing the
database or scheduling contract.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
import json
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import NotificationDelivery, ReminderSchedule, SubmissionBatch, User, UserContact, utc_now


settings = get_settings()


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def next_occurrence(schedule: ReminderSchedule, now: datetime | None = None) -> datetime:
    now_utc = now or utc_now()
    local_now = now_utc.replace(tzinfo=timezone.utc).astimezone(_zone(schedule.timezone))
    hour, minute = (int(part) for part in schedule.local_time.split(":", 1))
    target_time = time(hour=hour, minute=minute)
    days_ahead = (schedule.weekday - local_now.weekday()) % 7
    candidate = (local_now + timedelta(days=days_ahead)).replace(hour=target_time.hour, minute=target_time.minute, second=0, microsecond=0)
    if candidate <= local_now:
        candidate += timedelta(days=7)
    return candidate.astimezone(timezone.utc).replace(tzinfo=None)


def ensure_schedule(db: Session, user: User, contact: UserContact) -> ReminderSchedule:
    schedule = db.query(ReminderSchedule).filter(ReminderSchedule.user_id == user.id).first()
    if schedule:
        return schedule
    schedule = ReminderSchedule(
        user_id=user.id,
        enabled=contact.reminder_consent,
        weekday=0,
        local_time="09:00",
        timezone=contact.timezone,
        channels_json=json.dumps([contact.preferred_reminder_channel] if contact.preferred_reminder_channel != "both" else ["email", "sms"]),
    )
    schedule.next_run_at = next_occurrence(schedule)
    db.add(schedule)
    db.flush()
    return schedule


def _submitted_this_period(db: Session, user_id: str, since: datetime) -> bool:
    return db.query(SubmissionBatch).filter(
        SubmissionBatch.user_id == user_id,
        SubmissionBatch.status.in_(["Submitted", "Under Review", "Approved"]),
        SubmissionBatch.submitted_at >= since,
    ).first() is not None


def _channel_allowed(channel: str, contact: UserContact) -> bool:
    return (channel == "email" and contact.email_verified) or (channel == "sms" and contact.mobile_verified)


def _provider_delivery(user: User, contact: UserContact, channel: str) -> tuple[str, str | None, str | None]:
    if settings.app_env != "production":
        return "simulated", f"dev-{user.id[:8]}-{channel}-{int(datetime.now().timestamp())}", None
    if channel == "email" and settings.email_provider == "development":
        return "blocked", None, "Email provider is not configured"
    if channel == "sms" and settings.sms_provider == "development":
        return "blocked", None, "SMS provider is not configured"
    return "queued", None, "Provider adapter is configured but delivery worker is not installed"


def run_reminder_cycle(db: Session, now: datetime | None = None, force_user_id: str | None = None) -> int:
    now_utc = now or utc_now()
    delivered = 0
    schedules = db.query(ReminderSchedule).filter(ReminderSchedule.enabled.is_(True), ReminderSchedule.next_run_at <= now_utc).all()
    for schedule in schedules:
        contact = db.query(UserContact).filter(UserContact.user_id == schedule.user_id).first()
        user = db.get(User, schedule.user_id)
        if not contact or not user or not contact.reminder_consent:
            schedule.next_run_at = next_occurrence(schedule, now_utc)
            continue
        period_start = (schedule.next_run_at or now_utc) - timedelta(days=7)
        channels = json.loads(schedule.channels_json or "[]")
        if _submitted_this_period(db, user.id, period_start) and user.id != force_user_id:
            for channel in channels:
                key = f"{user.id}:{schedule.next_run_at.isoformat()}:{channel}:skipped"
                if not db.query(NotificationDelivery).filter(NotificationDelivery.idempotency_key == key).first():
                    db.add(NotificationDelivery(user_id=user.id, reminder_type="weekly_submission", scheduled_at=schedule.next_run_at or now_utc, channel=channel, status="skipped_submitted", idempotency_key=key))
        else:
            for channel in channels:
                key = f"{user.id}:{schedule.next_run_at.isoformat()}:{channel}"
                if db.query(NotificationDelivery).filter(NotificationDelivery.idempotency_key == key).first():
                    continue
                if not _channel_allowed(channel, contact):
                    db.add(NotificationDelivery(user_id=user.id, reminder_type="weekly_submission", scheduled_at=schedule.next_run_at or now_utc, channel=channel, status="blocked_unverified", failure_reason="Contact channel is not verified", idempotency_key=key))
                    continue
                status, provider_id, failure = _provider_delivery(user, contact, channel)
                db.add(NotificationDelivery(user_id=user.id, reminder_type="weekly_submission", scheduled_at=schedule.next_run_at or now_utc, sent_at=now_utc if status == "simulated" else None, channel=channel, status=status, provider_message_id=provider_id, failure_reason=failure, idempotency_key=key))
                if status in ("simulated", "queued"):
                    delivered += 1
                    contact.last_reminder_sent_at = now_utc
        schedule.last_run_at = now_utc
        schedule.next_run_at = next_occurrence(schedule, now_utc)
    db.commit()
    return delivered
