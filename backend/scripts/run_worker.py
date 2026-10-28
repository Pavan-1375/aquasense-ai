"""Run AquaSense background work separately from the API process.

This is intentionally a small durable polling worker for a modest deployment.
It can later be replaced by Celery/RQ without changing reminder business logic.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.services.reminders import run_reminder_cycle  # noqa: E402


def main() -> None:
    settings = get_settings()
    init_db()
    print(f"AquaSense worker started; interval={settings.scheduler_interval_seconds}s")
    while True:
        db = SessionLocal()
        try:
            run_reminder_cycle(db)
        except Exception as error:  # pragma: no cover - operational guard
            db.rollback()
            print(f"worker cycle failed: {error}", file=sys.stderr)
        finally:
            db.close()
        time.sleep(max(30, settings.scheduler_interval_seconds))


if __name__ == "__main__":
    main()
