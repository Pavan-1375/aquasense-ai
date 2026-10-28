import json
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Alert, Device, IngestionReceipt, Measurement, Station
from ..schemas import MeasurementIn


def normalize_timestamp(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value


def save_measurement(db: Session, payload: MeasurementIn, source: str = "device") -> Measurement:
    return save_measurement_with_key(db, payload, source=source, idempotency_key=None)


def save_measurement_with_key(db: Session, payload: MeasurementIn, source: str = "device", idempotency_key: str | None = None) -> Measurement:
    device = db.query(Device).filter(Device.device_id == payload.device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device is not registered")
    if payload.distance_cm is None and payload.water_level_percent is None and payload.water_depth_cm is None:
        raise HTTPException(status_code=422, detail="At least one groundwater measurement is required")
    if idempotency_key:
        receipt = db.query(IngestionReceipt).filter(IngestionReceipt.idempotency_key == idempotency_key).first()
        if receipt:
            if receipt.device_id != payload.device_id:
                raise HTTPException(status_code=409, detail="Idempotency key is already bound to another device")
            existing = db.get(Measurement, receipt.measurement_id)
            if existing:
                return existing
    timestamp = normalize_timestamp(payload.timestamp)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if timestamp > now + timedelta(minutes=10):
        raise HTTPException(status_code=422, detail="Measurement timestamp is too far in the future")
    duplicate = db.query(Measurement).filter(Measurement.device_id == payload.device_id, Measurement.timestamp == timestamp).first()
    if duplicate:
        duplicate.quality_status = "duplicate"
        db.commit()
        raise HTTPException(status_code=409, detail="Duplicate reading for this device and timestamp")
    stale = timestamp < now - timedelta(hours=get_settings().stale_measurement_hours)
    station = db.get(Station, device.station_id) if device.station_id else None
    measurement = Measurement(
        device_id=payload.device_id,
        station_id=device.station_id,
        timestamp=timestamp,
        distance_cm=payload.distance_cm,
        water_level_percent=payload.water_level_percent,
        water_depth_cm=payload.water_depth_cm,
        temperature_c=payload.temperature_c,
        site_latitude=station.latitude if station else None,
        site_longitude=station.longitude if station else None,
        site_accuracy_m=None,
        location_updated_at=now if station and station.latitude is not None and station.longitude is not None else None,
        source=source,
        # Device readings remain raw/pending until an administrator approves them.
        # The live page can show them, but dashboards and official analytics must not.
        quality_status="stale" if stale else "pending_review",
        raw_json=json.dumps(payload.model_dump(mode="json")),
    )
    device.status = "online"
    device.last_seen_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.add(measurement)
    pending_title = f"Device review required · {device.device_id}"
    if not db.query(Alert).filter(Alert.title == pending_title, Alert.state == "active").first():
        db.add(Alert(station_id=device.station_id, severity="info", title=pending_title, detail="A new ESP32 reading is waiting for administrator review. Attach proof and promote it only after verification."))
    try:
        db.flush()
        if idempotency_key:
            db.add(IngestionReceipt(idempotency_key=idempotency_key, device_id=payload.device_id, measurement_id=measurement.id))
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="Duplicate measurement") from error
    db.refresh(measurement)
    return measurement

