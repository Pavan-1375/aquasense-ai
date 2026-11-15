"""Delete records past the configured retention window.

Run only after taking a database backup. The default is intentionally disabled
unless RETENTION_DAYS is explicitly supplied.
"""
import os
from datetime import datetime, timedelta

from app.db import SessionLocal
from app.models import AuditEvent, Measurement, QualityObservation, SubmissionAttachment


def main() -> None:
    days = int(os.environ.get("RETENTION_DAYS", "0"))
    if days <= 0:
        raise SystemExit("Set RETENTION_DAYS to a positive value before cleanup")
    cutoff = datetime.utcnow() - timedelta(days=days)
    db = SessionLocal()
    try:
        for model, column in ((Measurement, Measurement.created_at), (QualityObservation, QualityObservation.measured_at), (AuditEvent, AuditEvent.created_at)):
            db.query(model).filter(column < cutoff).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
