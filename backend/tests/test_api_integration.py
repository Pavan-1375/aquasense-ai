import unittest
from datetime import timedelta

from fastapi import HTTPException, Response
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import admin_live_measurements, admin_users, delete_account, get_submission, list_measurements, live_measurements, logout, signin
from app.db import Base
from app.models import Device, Measurement, ModelExecutionRecord, SessionToken, Station, SubmissionBatch, SubmissionReview, User, utc_now
from app.security import hash_password, require_admin
from app.schemas import SignIn


class ApiIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, _record) -> None:
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False)
        db = self.Session()
        self.alice = User(id="user-a", name="Alice", email="alice@example.test", password_hash=hash_password("Correct-Horse-42!"), role="user")
        self.bob = User(id="user-b", name="Bob", email="bob@example.test", password_hash="x", role="user")
        self.admin = User(id="admin", name="Admin", email="admin@example.test", password_hash="x", role="admin")
        db.add_all([self.alice, self.bob, self.admin])
        db.flush()
        self.station_a = Station(id="station-a", owner_id=self.alice.id, name="Alice site")
        self.station_b = Station(id="station-b", owner_id=self.bob.id, name="Bob site")
        db.add_all([self.station_a, self.station_b])
        db.flush()
        now = utc_now()
        self.device_a = Device(device_id="ESP-A", name="Alice ESP", station_id=self.station_a.id, ingest_key="key-a", status="online", last_seen_at=now)
        self.device_b = Device(device_id="ESP-B", name="Bob ESP", station_id=self.station_b.id, ingest_key="key-b", status="online", last_seen_at=now - timedelta(seconds=30))
        db.add_all([self.device_a, self.device_b])
        db.flush()
        self.pending_a = Measurement(owner_id=self.alice.id, device_id=self.device_a.device_id, station_id=self.station_a.id, timestamp=now, distance_cm=21, source="http", quality_status="pending_review")
        self.pending_b = Measurement(owner_id=self.bob.id, device_id=self.device_b.device_id, station_id=self.station_b.id, timestamp=now, distance_cm=42, source="http", quality_status="pending_review")
        self.newest_a = Measurement(owner_id=self.alice.id, device_id=self.device_a.device_id, station_id=self.station_a.id, timestamp=now + timedelta(seconds=1), distance_cm=19, source="http", quality_status="pending_review", created_at=now + timedelta(seconds=1))
        self.stale_a = Measurement(owner_id=self.alice.id, device_id=self.device_a.device_id, station_id=self.station_a.id, timestamp=now - timedelta(minutes=1), distance_cm=99, source="http", quality_status="pending_review", created_at=now - timedelta(minutes=1))
        db.add_all([self.pending_a, self.pending_b, self.newest_a, self.stale_a])
        db.flush()
        self.submission_a = SubmissionBatch(user_id=self.alice.id, station_id=self.station_a.id, measurement_at=now, submitted_at=now, status="Submitted", source="test", measurement_method="manual")
        self.submission_b = SubmissionBatch(user_id=self.bob.id, station_id=self.station_b.id, measurement_at=now, submitted_at=now, status="Approved", source="test", measurement_method="manual", reviewed_by=self.alice.id)
        db.add_all([self.submission_a, self.submission_b])
        db.flush()
        self.review_by_alice = SubmissionReview(submission_id=self.submission_b.id, reviewer_id=self.alice.id, to_status="Approved")
        db.add_all([self.review_by_alice, ModelExecutionRecord(submission_id=self.submission_a.id, model_name="test", model_version="test", status="completed")])
        db.add(SessionToken(token="session-a", user_id=self.alice.id, expires_at=now + timedelta(days=1)))
        db.commit()
        self.ids = {"a": self.pending_a.id, "newest_a": self.newest_a.id, "b": self.pending_b.id, "stale": self.stale_a.id, "submission_a": self.submission_a.id, "submission_b": self.submission_b.id}
        self.db = db

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_live_monitoring_returns_owned_recent_pending_packets(self) -> None:
        result = live_measurements(20, self.db, self.alice)
        self.assertEqual([row.id for row in result], [self.ids["newest_a"]])

    def test_pending_filter_is_owner_scoped_and_default_history_is_approved_only(self) -> None:
        pending = list_measurements(None, "pending_review", 20, self.db, self.alice)
        self.assertEqual({row.id for row in pending}, {self.ids["a"], self.ids["newest_a"], self.ids["stale"]})
        history = list_measurements(None, None, 20, self.db, self.alice)
        self.assertEqual(history, [])

    def test_admin_live_queue_includes_ownerless_scope_without_exposing_to_users(self) -> None:
        response = admin_live_measurements(20, self.db, self.admin)
        self.assertEqual({row.id for row in response}, {self.ids["newest_a"], self.ids["b"]})
        with self.assertRaises(HTTPException) as forbidden:
            require_admin(self.alice)
        self.assertEqual(forbidden.exception.status_code, 403)

    def test_cross_user_submission_lookup_is_hidden(self) -> None:
        with self.assertRaises(HTTPException) as hidden:
            get_submission(self.ids["submission_a"], self.db, self.bob)
        self.assertEqual(hidden.exception.status_code, 404)

    def test_admin_user_management_requires_admin(self) -> None:
        with self.assertRaises(HTTPException) as forbidden:
            require_admin(self.alice)
        self.assertEqual(forbidden.exception.status_code, 403)
        self.assertEqual(len(admin_users(200, self.db, self.admin)), 3)

    def test_device_visibility_is_restricted_to_owned_stations(self) -> None:
        from app.api.routes import list_devices

        owned = list_devices(self.db, self.alice)
        self.assertEqual([device.device_id for device in owned], ["ESP-A"])
        self.assertEqual(owned[0].status, "online")
        all_devices = {device.device_id: device.status for device in list_devices(self.db, self.admin)}
        self.assertEqual(all_devices, {"ESP-A": "online", "ESP-B": "offline"})

    def test_account_erasure_removes_owned_records_and_anonymizes_review_history(self) -> None:
        response = delete_account(self.db, self.alice)
        self.assertEqual(response["status"], "deleted")
        self.assertIsNone(self.db.get(User, self.alice.id))
        self.assertIsNone(self.db.get(SubmissionBatch, self.ids["submission_a"]))
        retained = self.db.get(SubmissionBatch, self.ids["submission_b"])
        self.assertIsNotNone(retained)
        self.assertIsNone(retained.reviewed_by)
        self.db.refresh(self.review_by_alice)
        self.assertIsNone(self.review_by_alice.reviewer_id)

    def test_account_erasure_prevents_deleting_the_last_active_admin(self) -> None:
        with self.assertRaises(HTTPException) as blocked:
            delete_account(self.db, self.admin)
        self.assertEqual(blocked.exception.status_code, 409)

    def test_cookie_logout_revokes_server_session(self) -> None:
        response = Response()
        result = logout(response, None, "session-a", self.alice, self.db)
        self.assertEqual(result["status"], "signed_out")
        self.assertIsNone(self.db.get(SessionToken, "session-a"))
        self.assertIn("aquasense_session", response.headers.get("set-cookie", ""))

    def test_signin_issues_http_only_session_cookie_without_returning_bearer_token(self) -> None:
        response = Response()
        result = signin(SignIn(email=" Alice@Example.Test ", password="Correct-Horse-42!"), response, self.db)
        self.assertIsNone(result.token)
        cookie_headers = response.headers.getlist("set-cookie")
        self.assertTrue(any("aquasense_session=" in value and "httponly" in value.lower() for value in cookie_headers))
        self.assertTrue(any("aquasense_csrf=" in value for value in cookie_headers))


if __name__ == "__main__":
    unittest.main()
