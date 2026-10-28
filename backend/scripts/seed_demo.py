from datetime import datetime, timedelta, timezone
import random
import sys

sys.path.insert(0, "backend")

from app.db import SessionLocal, init_db
from app.models import Alert, Device, Measurement, QualityObservation, Station, User, UserContact
from app.security import hash_password
from app.services.quality import calculate_wqi
from app.services.reminders import ensure_schedule


def seed() -> None:
    init_db()
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.email == "admin@hydroinsight.local").first()
        if not admin:
            admin = User(name="Hydro Admin", email="admin@hydroinsight.local", password_hash=hash_password("hydro-demo-2026"), role="admin")
            db.add(admin)
            db.flush()
        contact = db.query(UserContact).filter(UserContact.user_id == admin.id).first()
        if not contact:
            contact = UserContact(user_id=admin.id, mobile_e164="+919999999999", reminder_consent=False, preferred_reminder_channel="email")
            db.add(contact)
            db.flush()
        ensure_schedule(db, admin, contact)
        station = db.query(Station).filter(Station.name == "Demo Recharge Station").first()
        if not station:
            station = Station(name="Demo Recharge Station", description="Clearly labelled local demo station", country="India", state="Karnataka", district="Bengaluru Urban", latitude=12.97679, longitude=77.59008, risk_level="low")
            db.add(station)
            db.flush()
        device = db.query(Device).filter(Device.device_id == "ESP32-DEMO-001").first()
        if not device:
            device = Device(device_id="ESP32-DEMO-001", name="Demo ultrasonic level sensor", station_id=station.id, ingest_key="local-device-key", status="online", last_seen_at=datetime.now(timezone.utc).replace(tzinfo=None))
            db.add(device)
            db.flush()
        if db.query(Measurement).filter(Measurement.device_id == device.device_id).count() == 0:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            for index in range(48):
                timestamp = now - timedelta(hours=47 - index)
                level = max(28, min(62, 48 - index * 0.16 + random.uniform(-1.5, 1.5)))
                db.add(Measurement(device_id=device.device_id, station_id=station.id, timestamp=timestamp, distance_cm=220 - level * 1.5, water_level_percent=round(level, 2), water_depth_cm=round(180 - level, 2), temperature_c=25.4, source="demo", quality_status="demo"))
        if db.query(QualityObservation).filter(QualityObservation.station_id == station.id).count() == 0:
            values = {"ph": 7.34, "tds_mg_l": 284, "ec_us_cm": 486, "turbidity_ntu": 1.8, "temperature_c": 25.4, "hardness_mg_l": 168, "chloride_mg_l": 92}
            wqi, classification, _ = calculate_wqi(values)
            db.add(QualityObservation(station_id=station.id, measured_at=datetime.now(timezone.utc).replace(tzinfo=None), **values, wqi=wqi, classification=classification, source="demo", data_quality="demo"))
        if db.query(Alert).count() == 0:
            db.add(Alert(station_id=station.id, severity="info", title="Demo mode enabled", detail="These readings are labelled demo data and are not live hardware measurements.", state="active"))
        db.commit()
        print("HydroInsight demo data seeded")
    finally:
        db.close()


if __name__ == "__main__":
    seed()

