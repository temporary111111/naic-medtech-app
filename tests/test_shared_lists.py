from __future__ import annotations

import base64
import json
import unittest
from copy import deepcopy
from unittest.mock import patch

from tests import test_client_print_adjustments as _runtime_fixture
from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from naic_builder import main, services
from naic_builder.config import SESSION_SECRET
from naic_builder.database import Base, SKIP_CHANGE_BACKUP_SESSION_KEY, get_session
from naic_builder.models import FormDefinition, FormVersion, SharedChoiceList, User
from naic_builder.schemas import FormSavePayload, RecordCreatePayload, RecordUpdatePayload
from naic_builder.shared_lists import (
    SharedListConflict, change_shared_list, create_shared_list, ensure_standard_shared_lists,
    get_shared_list, list_shared_lists, resolve_shared_choices, shared_list_usage,
)


class SharedListsTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, info={SKIP_CHANGE_BACKUP_SESSION_KEY: True})
        with self.Session() as session:
            admin = User(login_id="admin", full_name="Admin", role="admin", status="active")
            staff = User(login_id="staff", full_name="Staff", role="medtech", status="active")
            session.add_all([admin, staff]); session.flush()
            self.admin_id, self.staff_id = admin.id, staff.id
            for slug, physician in [("alpha", "Dr. Alpha"), ("beta", "Dr. Beta")]:
                form = FormDefinition(slug=slug, name=slug.title())
                session.add(form); session.flush()
                schema = {"schema_version": 2, "source_kind": "builder_blocks_v2",
                    "meta": {"signatories": [], "record_identity": {"primary_field_id": "name"}},
                    "blocks": [{"id": "name", "kind": "field", "name": "Name", "props": {"data_type": "text", "control": "input", "required": True}},
                        {"id": f"form.{slug}.patient_information.requesting_physician", "kind": "field", "name": "Requesting Physician",
                         "props": {"data_type": "text", "control": "select", "options": [{"name": physician}]}},
                        {"id": f"form.{slug}.patient_information.room", "kind": "field", "name": "Room",
                         "props": {"data_type": "text", "control": "select", "options": [{"name": "Room 1"}]}},
                        {"id": "custom", "kind": "field", "name": "Custom choices", "props": {"control": "select", "data_type": "text", "options": [{"name": "Local"}]}}]}
                session.add(FormVersion(form_id=form.id, version_number=1, is_current=True, block_schema_json=json.dumps(schema), source="builder"))
            session.commit()
            self.values = {"name": "Patient Example", "form.alpha.patient_information.requesting_physician": "Dr. Alpha"}
            self.record_id = services.create_record(session, RecordCreatePayload(form_slug="alpha", values=self.values), actor_user_id=self.admin_id)["id"]
            services.complete_record(session, self.record_id, RecordUpdatePayload(values=self.values), actor_user_id=self.admin_id)

        def db():
            with self.Session() as session:
                yield session
        main.app.dependency_overrides[get_session] = db
        self.session_patch = patch.object(main, "SessionLocal", self.Session)
        self.session_patch.start()
        self.client = TestClient(main.app)
        self.login(self.admin_id)

    def tearDown(self):
        self.client.close()
        main.app.dependency_overrides.pop(get_session, None)
        self.session_patch.stop()
        self.engine.dispose()

    def login(self, user_id):
        self.client.cookies.clear()
        raw = base64.b64encode(json.dumps({"user_id": user_id}).encode())
        self.client.cookies.set("session", TimestampSigner(SESSION_SECRET).sign(raw).decode())

    def seed(self):
        with self.Session() as session:
            ensure_standard_shared_lists(session)
            return next(item for item in list_shared_lists(session) if item["name"] == "Requesting physicians")

    def test_standard_setup_uses_new_versions_and_preserves_historical_prints(self):
        with self.Session() as session:
            record = services.get_record_or_none(session, self.record_id)
            previous_version = record.form_version_id
            before = services.build_record_print_document(record)
            frozen = record.form_version.block_schema_json
            self.assertEqual(ensure_standard_shared_lists(session), 2)
            record = services.get_record_or_none(session, self.record_id)
            self.assertEqual(record.form_version_id, previous_version)
            self.assertEqual(record.form_version.block_schema_json, frozen)
            self.assertEqual(services.build_record_print_document(record), before)
            self.assertEqual(ensure_standard_shared_lists(session), 0)
            lists = list_shared_lists(session)
            doctors = next(row for row in lists if row["name"] == "Requesting physicians")
            self.assertEqual([row["name"] for row in doctors["items"]], ["Dr. Alpha", "Dr. Beta"])
            self.assertEqual(len(shared_list_usage(session, doctors["id"])), 2)
            schema = services.serialize_form(services.get_form_or_none(session, "alpha"))["block_schema"]
            self.assertNotIn("shared_list_id", schema["blocks"][3]["props"])

    def test_latest_choices_reach_both_forms_without_new_form_versions(self):
        doctors = self.seed()
        with self.Session() as session:
            change_shared_list(session, doctors["id"], doctors["revision"], "add", name="Dr. New")
            for slug in ["alpha", "beta"]:
                version = services.current_version(services.get_form_or_none(session, slug))
                frozen = version.block_schema_json
                schema, _ = services.load_block_storage_document(version)
                resolved = resolve_shared_choices(session, schema)
                self.assertIn("Dr. New", [row["name"] for row in resolved["blocks"][1]["props"]["options"]])
                self.assertEqual(version.block_schema_json, frozen)
                self.assertEqual(version.version_number, 2)
        old_record_editor = self.client.get(f"/records/{self.record_id}/edit")
        self.assertIn('<option value="Dr. New"', old_record_editor.text)
        self.assertIn('<option value="Dr. Alpha" selected>Dr. Alpha</option>', old_record_editor.text)

    def test_rename_deactivate_and_reactivate_preserve_saved_draft_and_completed_answers(self):
        doctors = self.seed()
        with self.Session() as session:
            draft = services.create_record(session, RecordCreatePayload(form_slug="alpha", values=self.values), actor_user_id=self.admin_id)
            completed = services.create_record(session, RecordCreatePayload(form_slug="alpha", values=self.values), actor_user_id=self.admin_id)
            services.complete_record(session, completed["id"], RecordUpdatePayload(values=self.values), actor_user_id=self.admin_id)
            before_print = services.build_record_print_document(services.get_record_or_none(session, completed["id"]))
            old_item = next(row for row in doctors["items"] if row["name"] == "Dr. Alpha")
            change_shared_list(session, doctors["id"], 1, "rename", item_id=old_item["id"], name="Dr. Renamed")
            change_shared_list(session, doctors["id"], 2, "deactivate", item_id=old_item["id"])
            self.assertEqual(ensure_standard_shared_lists(session), 0)
            self.assertEqual(services.build_record_print_document(services.get_record_or_none(session, completed["id"])), before_print)
        for record_id in [draft["id"], completed["id"]]:
            page = self.client.get(f"/records/{record_id}/edit")
            self.assertEqual(page.status_code, 200)
            self.assertIn('<option value="Dr. Alpha" selected>Dr. Alpha</option>', page.text)
            self.assertNotIn('<option value="Dr. Renamed"', page.text)
            saved = self.client.post(f"/records/{record_id}/edit", data={**{f"value__{key}": value for key, value in self.values.items()}, "action": "save"}, follow_redirects=False)
            self.assertEqual(saved.status_code, 303)
            self.assertEqual(self.client.get(f"/api/records/{record_id}").json()["values"], self.values)
        with self.Session() as session:
            change_shared_list(session, doctors["id"], 3, "reactivate", item_id=old_item["id"])
            self.assertTrue(next(row for row in get_shared_list(session, doctors["id"]).items if row.id == old_item["id"]).active)

    def test_empty_and_renamed_lists_keep_their_binding_and_original_answer(self):
        doctors = self.seed()
        with self.Session() as session:
            for revision, item in enumerate(doctors["items"], 1):
                change_shared_list(session, doctors["id"], revision, "deactivate", item_id=item["id"])
            change_shared_list(session, doctors["id"], 3, "rename_list", name="Physicians")
            self.assertEqual(get_shared_list(session, doctors["id"]).name, "Physicians")
            schema = services.serialize_form(services.get_form_or_none(session, 'alpha'))['block_schema']
            self.assertEqual(resolve_shared_choices(session, schema)['blocks'][1]['props']['options'], [])
        page = self.client.get(f"/records/{self.record_id}/edit")
        self.assertIn('<option value="Dr. Alpha" selected>Dr. Alpha</option>', page.text)
        self.assertIn('Physicians', self.client.get('/settings/shared-lists').text)

    def test_duplicate_names_and_stale_updates_do_not_partially_write(self):
        doctors = self.seed()
        with self.Session() as session:
            with self.assertRaises(ValueError):
                change_shared_list(session, doctors["id"], 1, "add", name="  dr.   alpha  ")
            self.assertEqual(get_shared_list(session, doctors["id"]).revision, 1)
            change_shared_list(session, doctors["id"], 1, "add", name="Dr. New")
            with self.assertRaises(SharedListConflict):
                change_shared_list(session, doctors["id"], 1, "add", name="Lost update")
            self.assertEqual(get_shared_list(session, doctors["id"]).revision, 2)
            self.assertNotIn("Lost update", [row.name for row in get_shared_list(session, doctors["id"]).items])
            with self.assertRaises(ValueError): create_shared_list(session, "REQUESTING PHYSICIANS")

    def test_optional_links_validate_and_survive_builder_save(self):
        doctors = self.seed()
        with self.Session() as session:
            form = services.serialize_form(services.get_form_or_none(session, "alpha"))
            schema = form["block_schema"]
            snapshot = deepcopy(schema)
            field = schema["blocks"][3]
            field["props"]["shared_list_id"] = doctors["id"]
            saved = services.update_form(session, "alpha", FormSavePayload(name=form["name"], form_schema=schema))
            self.assertEqual(saved["block_schema"]["blocks"][3]["props"]["shared_list_id"], doctors["id"])
            for bad_id in [0, -1, True, "1", 99999]:
                invalid = deepcopy(snapshot); invalid["blocks"][1]["props"]["shared_list_id"] = bad_id
                with self.assertRaises(ValueError):
                    services.update_form(session, "alpha", FormSavePayload(form_schema=invalid))
            invalid = deepcopy(snapshot); invalid["blocks"][0]["props"]["shared_list_id"] = doctors["id"]
            with self.assertRaises(ValueError): resolve_shared_choices(session, invalid, validate=True)
            self.assertEqual(services.current_version(services.get_form_or_none(session, "alpha")).version_number, 3)

    def test_admin_only_management_and_staff_record_access(self):
        doctors = self.seed()
        self.assertEqual(self.client.get('/settings/shared-lists').status_code, 200)
        self.assertEqual(self.client.get(f'/settings/shared-lists/{doctors["id"]}').status_code, 200)
        self.assertEqual(self.client.get('/settings/clinic').status_code, 200)
        self.assertIn('shared_lists', self.client.get('/api/builder/bootstrap').json())
        self.login(self.staff_id)
        for url in ['/settings/shared-lists', f'/settings/shared-lists/{doctors["id"]}']:
            self.assertEqual(self.client.get(url, follow_redirects=False).status_code, 303)
            self.assertEqual(self.client.post(url, data={"name": "Unauthorized", "revision": 1, "action": "add"}, follow_redirects=False).status_code, 303)
        self.assertEqual(self.client.get(f'/records/{self.record_id}/edit').status_code, 200)
        with self.Session() as session:
            self.assertEqual(get_shared_list(session, doctors["id"]).revision, 1)

    def test_management_posts_validate_and_keep_changes_on_the_selected_list(self):
        doctors = self.seed(); url = f'/settings/shared-lists/{doctors["id"]}'
        response = self.client.post(url, data={"name": "Dr. UI", "revision": 1, "action": "add"}, follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers['location'], url+'?saved=1')
        response = self.client.post(url, data={"name": "Lost change", "revision": 1, "action": "add"})
        self.assertEqual(response.status_code, 409)
        self.assertIn('updated elsewhere', response.text)
        response = self.client.post('/settings/shared-lists', data={"name": "  "})
        self.assertEqual(response.status_code, 422)
        response = self.client.post('/settings/shared-lists', data={"name": "Departments"}, follow_redirects=False)
        self.assertEqual(response.status_code, 303)


if __name__ == "__main__":
    unittest.main()
