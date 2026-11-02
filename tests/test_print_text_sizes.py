from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
TEST_RUNTIME = tempfile.TemporaryDirectory(prefix="ndhi-text-sizes-")
os.environ.setdefault("NDHI_LABRECORDS_DATA_DIR", TEST_RUNTIME.name)
os.environ["NDHI_AFTER_CHANGE_BACKUP_DISABLED"] = "1"

from naic_builder import database, main
from naic_builder.config import SESSION_SECRET
from naic_builder.database import Base, SKIP_CHANGE_BACKUP_SESSION_KEY, get_session
from naic_builder.models import FormDefinition, FormVersion, Record, User
from naic_builder.services import (
    build_form_print_preview_document,
    effective_record_print_presentation,
    form_print_text_sizes,
    normalize_print_profile,
    save_form_print_text_sizes,
    snapshot_completed_record_print_presentation,
)


def tearDownModule() -> None:
    TEST_RUNTIME.cleanup()


class PrintTextSizeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, info={SKIP_CHANGE_BACKUP_SESSION_KEY: True})
        with self.Session() as session:
            owner = User(login_id="owner", full_name="Owner", role="medtech", status="active")
            other = User(login_id="other", full_name="Other", role="medtech", status="active")
            definition = FormDefinition(slug="sample", name="Sample")
            session.add_all([owner, other, definition])
            session.flush()
            version = FormVersion(form_id=definition.id, version_number=1, block_schema_json="{}", is_current=True)
            session.add(version)
            session.flush()
            records = [Record(record_key=f"SIZE-{i}", form_id=definition.id, form_version_id=version.id,
                              status="completed", created_by_user_id=owner.id) for i in range(2)]
            session.add_all(records)
            session.flush()
            for record in records:
                snapshot_completed_record_print_presentation(session, record, user=owner)
            session.commit()
            self.owner_id, self.other_id, self.form_id = owner.id, other.id, definition.id
            self.record_id, self.old_record_id = [record.id for record in records]

        def get_test_session():
            with self.Session() as session:
                yield session

        main.app.dependency_overrides[get_session] = get_test_session
        self.session_patch = patch.object(main, "SessionLocal", self.Session)
        self.session_patch.start()
        self.client = TestClient(main.app)
        self.sign_in(self.owner_id)

    def tearDown(self) -> None:
        self.client.close()
        main.app.dependency_overrides.pop(get_session, None)
        self.session_patch.stop()
        self.engine.dispose()

    def sign_in(self, user_id: int) -> None:
        raw = base64.b64encode(json.dumps({"user_id": user_id}).encode())
        self.client.cookies.set("session", TimestampSigner(SESSION_SECRET).sign(raw).decode())

    def save_sizes(self, **overrides):
        payload = dict(style="legacy", orientation="landscape", paper_size="a5", text_size="standard",
                       save_text_sizes="1", test_name_scale="110", result_scale="125")
        payload.update(overrides)
        return self.client.post(f"/records/{self.record_id}/print-options", data=payload, follow_redirects=False)

    def test_sizes_persist_for_form_layout_and_future_staff_records_without_changing_reprints(self) -> None:
        response = self.save_sizes()
        self.assertEqual(response.status_code, 303)
        page = self.client.get(response.headers["location"])
        self.assertEqual(page.status_code, 200)
        self.assertIn('--print-test-name-scale: 1.1;', page.text)
        self.assertIn('--print-result-scale: 1.25;', page.text)
        with self.Session() as session:
            record = session.get(Record, self.record_id)
            old = session.get(Record, self.old_record_id)
            self.assertEqual(record.print_presentation.test_name_scale, 110)
            self.assertEqual(record.print_presentation.result_scale, 125)
            self.assertEqual(old.print_presentation.result_scale, 100)
            profile = normalize_print_profile(template_id="legacy_landscape", paper_size="a5")
            self.assertEqual(form_print_text_sizes(record.form, profile), dict(test_name_scale=110, result_scale=125))
            for other_profile in (
                normalize_print_profile(template_id="legacy_landscape", paper_size="a4"),
                normalize_print_profile(template_id="modern_landscape", paper_size="a5"),
                normalize_print_profile(template_id="modern_portrait", paper_size="a5"),
            ):
                self.assertEqual(form_print_text_sizes(record.form, other_profile)["result_scale"], 100)
            another_form = FormDefinition(slug="another", name="Another")
            session.add(another_form)
            session.flush()
            self.assertEqual(form_print_text_sizes(another_form, profile)["result_scale"], 100)
            future = Record(record_key="FUTURE", form_id=record.form_id, form_version_id=record.form_version_id,
                            status="completed", created_by_user_id=self.other_id)
            session.add(future)
            session.flush()
            snapshot_completed_record_print_presentation(session, future, user=session.get(User, self.other_id))
            session.commit()
            self.assertEqual(future.print_presentation.result_scale, 125)
            profile["result_scale"] = 150
            save_form_print_text_sizes(session, record.form, profile)
            session.commit()
            self.assertEqual(effective_record_print_presentation(future, fallback_profile=profile)["profile"]["result_scale"], 125)
            self.assertEqual(len(session.scalars(select(FormVersion)).all()), 1)

    def test_invalid_sizes_are_rejected_without_partial_saves(self) -> None:
        for invalid in ("0", "49", "201", "nan", "110.5", "", "100%"):
            with self.subTest(invalid=invalid):
                self.assertEqual(self.save_sizes(result_scale=invalid).status_code, 422)
        with self.Session() as session:
            self.assertEqual(session.get(FormDefinition, self.form_id).print_text_defaults_json, "{}")
            self.assertEqual(session.get(Record, self.record_id).print_presentation.test_name_scale, 100)

    def test_other_staff_cannot_change_another_staffs_record(self) -> None:
        self.sign_in(self.other_id)
        self.assertEqual(self.save_sizes().status_code, 403)

    def test_form_layout_preview_uses_the_shared_text_sizes(self) -> None:
        self.save_sizes()
        with self.Session() as session:
            session.get(User, self.owner_id).role = "admin"
            session.commit()
        page = self.client.get('/forms/sample/print-layout?style=legacy&orientation=landscape&paper_size=a5')
        self.assertEqual(page.status_code, 200)
        self.assertIn('--print-test-name-scale: 1.1;', page.text)
        self.assertIn('--print-result-scale: 1.25;', page.text)

    def test_layout_save_keeps_custom_sizes_even_for_older_clients(self) -> None:
        self.save_sizes()
        response = self.client.post(f"/records/{self.record_id}/print-layout", json={
            "template_id": "legacy_landscape", "paper_size": "a5", "text_size": "standard", "layout": {},
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["presentation"]["result_scale"], 125)

    def test_fit_feedback_accounts_for_custom_sizes_and_never_blocks_printing(self) -> None:
        kwargs = dict(form_name="Sample", block_schema={"schema_version": 2, "meta": {}, "blocks": [
            {"id": f"test-{i}", "kind": "field", "name": f"Test {i}", "props": {"field_type": "text"}}
            for i in range(20)
        ]}, template_id="legacy_landscape", paper_size="a5")
        normal = build_form_print_preview_document(**kwargs)
        large = build_form_print_preview_document(**kwargs, test_name_scale=140, result_scale=180)
        self.assertGreater(large["fit_estimate"]["estimated_units"], normal["fit_estimate"]["estimated_units"])
        self.assertTrue(large["fit_estimate"]["can_print"])

    def test_existing_database_migration_is_idempotent_and_preserves_old_sizes(self) -> None:
        with self.engine.begin() as connection:
            connection.exec_driver_sql("ALTER TABLE form_definitions DROP COLUMN print_text_defaults_json")
            connection.exec_driver_sql("ALTER TABLE record_print_presentations DROP COLUMN test_name_scale")
            connection.exec_driver_sql("ALTER TABLE record_print_presentations DROP COLUMN result_scale")
        with patch.object(database, "engine", self.engine):
            database.ensure_runtime_schema()
            database.ensure_runtime_schema()
        with self.Session() as session:
            record = session.get(Record, self.old_record_id)
            self.assertEqual(record.print_presentation.test_name_scale, 100)
            self.assertEqual(record.print_presentation.result_scale, 100)
            self.assertEqual(record.record_key, "SIZE-1")


if __name__ == "__main__":
    unittest.main()
