from __future__ import annotations

import base64
import json
from pathlib import Path
import tempfile
import unittest
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
from naic_builder.models import FormDefinition, FormVersion, Record, RecordAsset, RecordRevision, User
from naic_builder.schemas import RecordCreatePayload, RecordUpdatePayload
from naic_builder.services import create_record, complete_record, get_record_or_none, save_record_print_presentation


class CompletedRecordEditingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, info={SKIP_CHANGE_BACKUP_SESSION_KEY: True})
        self.files = tempfile.TemporaryDirectory(prefix="ndhi-record-edit-")
        self.image_patch = patch.object(services, "RECORD_UPLOADS_DIR", Path(self.files.name))
        self.image_patch.start()
        self.values = {"name": "Maria Cruz", "case": "CASE-123", "result": "120"}
        schema = {
            "schema_version": 2, "source_kind": "builder_blocks_v2",
            "meta": {"signatories": [], "record_identity": {
                "primary_field_id": "name", "secondary_field_id": "case", "searchable_field_ids": ["result"],
            }},
            "blocks": [{"id": "details", "kind": "container", "name": "Patient and results", "children": [
                {"id": field_id, "kind": "field", "name": label, "props": {
                    "data_type": kind, "required": required, "control": "input", "unit_hint": "mg/dL" if field_id == "result" else "",
                }} for field_id, label, kind, required in (
                    ("name", "Name", "text", True), ("case", "Case number", "number", True),
                    ("result", "Glucose", "number", True), ("image", "Image", "image", False),
                )
            ]}],
        }
        schema['blocks'][0]['children'].append({
            'id': 'room', 'kind': 'field', 'name': 'Room',
            'props': {'data_type':'text', 'control':'select', 'options':[{'name':'New room'}]},
        })
        self.values['room'] = 'Original room'
        with self.Session() as session:
            owner = User(login_id="owner", full_name="Original Staff", status="active", role="medtech")
            editor = User(login_id="editor", full_name="Editing Staff", status="active", role="medtech")
            definition = FormDefinition(slug="sample", name="Sample")
            session.add_all([owner, editor, definition])
            session.flush()
            session.add(FormVersion(form_id=definition.id, version_number=1, is_current=True,
                                    block_schema_json=json.dumps(schema), source="builder"))
            session.commit()
            created = create_record(session, RecordCreatePayload(form_slug="sample", values=self.values), actor_user_id=owner.id)
            self.record_id = created["id"]
            complete_record(session, self.record_id, RecordUpdatePayload(values=self.values), actor_user_id=owner.id)
            record = get_record_or_none(session, self.record_id)
            profile = services.normalize_print_profile(template_id="legacy_landscape", paper_size="a5", test_name_scale=110, result_scale=125)
            save_record_print_presentation(session, record, user=owner, profile=profile, layout={})
            self.editor_id, self.owner_id = editor.id, owner.id
            self.original_completed_at = record.completed_at
            self.form_version_id = record.form_version_id

        def test_session():
            with self.Session() as session:
                yield session
        main.app.dependency_overrides[get_session] = test_session
        self.session_patch = patch.object(main, "SessionLocal", self.Session)
        self.session_patch.start()
        self.client = TestClient(main.app)
        raw = base64.b64encode(json.dumps({"user_id": self.editor_id}).encode())
        self.client.cookies.set("session", TimestampSigner(SESSION_SECRET).sign(raw).decode())

    def tearDown(self) -> None:
        self.client.close()
        main.app.dependency_overrides.pop(get_session, None)
        self.session_patch.stop()
        self.image_patch.stop()
        self.engine.dispose()
        self.files.cleanup()

    def revision_token(self):
        return self.client.get(f"/api/records/{self.record_id}").json()["updated_at"]

    def save(self, values=None, **extra):
        return self.client.put(f"/api/records/{self.record_id}", json={"values": values or self.values, **extra})

    def html_save(self, **extra):
        data = {f"value__{key}": value for key, value in self.values.items()}
        data.update(action="save", expected_updated_at=self.revision_token())
        data.update(extra)
        return self.client.post(f"/records/{self.record_id}/edit?from=history&return_to=%2Frecords%2Fhistory%3Fq%3DMaria", data=data, follow_redirects=False)

    def test_completed_editor_is_direct_and_history_has_edit_and_print(self):
        page = self.client.get(f"/records/{self.record_id}/edit")
        self.assertEqual(page.status_code, 200)
        self.assertIn('>Save changes</button>', page.text)
        self.assertNotIn('>Complete and print</button>', page.text)
        self.assertNotIn('>View</a>', page.text)
        self.assertIn('value="120"', page.text)
        self.assertIn('<input type="text" step="any" name="value__case" value="CASE-123">', page.text)
        self.assertIn('<option value="Original room" selected>Original room</option>', page.text)
        history = self.client.get('/records/history')
        self.assertEqual(history.status_code, 200)
        self.assertIn(f'/records/{self.record_id}/edit?', history.text)
        self.assertIn('>Edit</a>', history.text)
        self.assertIn('>Print</a>', history.text)
        self.assertNotIn('>View</a>', history.text)

    def test_completed_save_preserves_status_original_form_print_settings_and_audits_both_versions(self):
        old_token = self.revision_token()
        response = self.save({**self.values, "name": "Maria Santos", "result": "135"}, expected_updated_at=old_token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["patient_name"], "Maria Santos")
        with self.Session() as session:
            record = get_record_or_none(session, self.record_id)
            self.assertEqual(record.status, "completed")
            self.assertEqual(record.completed_at, self.original_completed_at)
            self.assertEqual(record.form_version_id, self.form_version_id)
            self.assertEqual(record.print_presentation.result_scale, 125)
            self.assertEqual(record.print_presentation.paper_size, 'a5')
            self.assertEqual(record.updated_by_user_id, self.editor_id)
            revision = session.scalar(select(RecordRevision))
            self.assertEqual(json.loads(revision.before_json)["values"]["result"], '120')
            self.assertEqual(json.loads(revision.after_json)["values"]["result"], '135')
            self.assertEqual(json.loads(revision.actor_json)["full_name"], 'Editing Staff')
        printed = self.client.get(f'/records/{self.record_id}/print')
        self.assertIn('>135</span>', printed.text)
        self.assertIn('--print-result-scale: 1.25;', printed.text)

    def test_invalid_completed_save_retains_attempt_on_screen_and_preserves_saved_record(self):
        response = self.html_save(value__name='', value__result='175')
        self.assertEqual(response.status_code, 422)
        self.assertIn('value="175"', response.text)
        self.assertIn('data-initial-dirty="true"', response.text)
        with self.Session() as session:
            record = get_record_or_none(session, self.record_id)
            self.assertEqual(json.loads(record.values_json)["result"], '120')
            self.assertEqual(record.patient_name, 'Maria Cruz')
            self.assertIsNone(session.scalar(select(RecordRevision)))

    def test_save_returns_to_editor_and_preserves_search_context(self):
        response = self.html_save(value__result='130')
        self.assertEqual(response.status_code, 303)
        location = response.headers['location']
        self.assertIn('/edit?', location)
        self.assertIn('from=history', location)
        self.assertIn('saved=1', location)
        page = self.client.get(location)
        self.assertIn('Changes saved.', page.text)
        self.assertIn('href="/records/history?q=Maria"', page.text)

    def test_stale_saves_cannot_overwrite_a_newer_result(self):
        stale = self.revision_token()
        self.assertEqual(self.save({**self.values, 'result':'130'}, expected_updated_at=stale).status_code, 200)
        self.assertEqual(self.save({**self.values, 'result':'150'}, expected_updated_at=stale).status_code, 409)
        response = self.html_save(value__result='160', expected_updated_at=stale)
        self.assertEqual(response.status_code, 409)
        self.assertIn('>Reload record</a>', response.text)
        self.assertNotIn('>Save changes</button>', response.text)
        self.assertEqual(self.client.get(f'/api/records/{self.record_id}').json()['values']['result'], '130')

    def test_voided_and_deleted_records_remain_locked(self):
        for status in ('voided','deleted'):
            with self.subTest(status=status), self.Session() as session:
                record = session.get(Record, self.record_id)
                record.status = status
                session.commit()
                response = self.save({**self.values, 'result':'200'})
                self.assertIn(response.status_code, (404,422))
                session.refresh(record)
                self.assertEqual(json.loads(record.values_json)['result'], '120')

    def test_noop_save_does_not_add_repeated_history(self):
        self.assertEqual(self.save().status_code,200)
        with self.Session() as session:
            count_before=len(session.scalars(select(RecordRevision)).all())
        self.assertEqual(self.save().status_code,200)
        with self.Session() as session:
            self.assertEqual(len(session.scalars(select(RecordRevision)).all()),count_before)

    def test_images_only_change_on_save_and_original_file_survives_in_history(self):
        png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aZ1sAAAAASUVORK5CYII=')
        first = self.client.post(f'/api/records/{self.record_id}/assets', data={'field_block_id':'image'}, files={'image_file':('first.png',png,'image/png')})
        self.assertEqual(first.status_code,200)
        asset_id=first.json()['staged_asset']['id']
        self.assertNotIn('image', self.client.get(f'/api/records/{self.record_id}').json()['asset_by_field_id'])
        self.assertEqual(self.html_save(image__image=str(asset_id)).status_code,303)
        token=self.revision_token()
        second = self.client.post(f'/api/records/{self.record_id}/assets', data={'field_block_id':'image'}, files={'image_file':('second.png',png,'image/png')})
        self.assertEqual(second.status_code,200)
        self.assertEqual(self.revision_token(),token)
        self.assertEqual(self.client.get(f'/api/records/{self.record_id}').json()['asset_by_field_id']['image']['id'],asset_id)
        self.assertEqual(self.client.delete(f'/api/records/{self.record_id}/assets/{asset_id}').status_code,422)
        self.assertEqual(self.html_save(image__image='').status_code,303)
        self.assertNotIn('image', self.client.get(f'/api/records/{self.record_id}').json()['asset_by_field_id'])
        with self.Session() as session:
            self.assertTrue(Path(session.get(RecordAsset,asset_id).storage_path).exists())
            self.assertEqual(len(session.scalars(select(RecordRevision)).all()),2)

    def test_drafts_keep_continue_and_completion_workflow(self):
        with self.Session() as session:
            created=create_record(session,RecordCreatePayload(form_slug='sample',values=self.values),actor_user_id=self.owner_id)
        queue=self.client.get('/records')
        self.assertIn('>Continue</a>',queue.text)
        self.assertNotIn('>View</a>',queue.text)
        page=self.client.get(f"/records/{created['id']}/edit")
        self.assertIn('>Complete and print</button>',page.text)
        response=self.client.post(f"/records/{created['id']}/edit",data={
            **{f'value__{k}':v for k,v in self.values.items()},'action':'complete',
        },follow_redirects=False)
        self.assertEqual(response.status_code,303)
        self.assertEqual(response.headers['location'],f"/records/{created['id']}/edit")


if __name__ == '__main__':
    unittest.main()
