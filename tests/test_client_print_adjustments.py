from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

from jinja2 import Environment, FileSystemLoader
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
TEST_RUNTIME = tempfile.TemporaryDirectory(prefix="ndhi-client-adjustments-")
os.environ["NDHI_LABRECORDS_DATA_DIR"] = TEST_RUNTIME.name

from naic_builder.database import Base
from naic_builder.models import FormDefinition, FormVersion, Record
from naic_builder.schemas import ClinicProfilePayload
from naic_builder.services import (
    build_print_clinic_profile,
    build_print_display_value,
    build_print_summary_items,
    build_signatory_snapshot,
    default_signatory_slots,
    ensure_client_signatory_defaults,
    ensure_default_pathologist_stamp,
    format_print_temporal_value,
    list_record_completion_issues,
    normalize_signatory_slot,
    save_clinic_profile,
    signatory_snapshots_for_print,
)


class ClientPrintAdjustmentTests(unittest.TestCase):
    def test_shared_print_template_places_units_and_labels_correctly(self) -> None:
        environment = Environment(loader=FileSystemLoader(ROOT / "app" / "naic_builder" / "templates"))
        macro = environment.get_template("records/_print_document.html").module.render_print_page
        row_field = {
            "kind": "field",
            "name": "PULSE RATE",
            "unit_hint": "bpm",
            "reference_text": "",
            "display": {"kind": "text", "text": "-2"},
            "is_abnormal": False,
        }
        grid_field = {
            **row_field,
            "name": "TEMPERATURE",
            "unit_hint": "deg C",
            "display": {"kind": "text", "text": "4"},
        }
        html = macro({
            "items": [row_field, {"kind": "field_grid", "items": [grid_field]}],
            "clinic": {
                "name": "NDH",
                "address": "",
                "contact_line": "",
                "doh_license_number": "03-123456-10",
            },
            "print_config": {
                "show_logo": False,
                "show_clinic_info": True,
                "show_status": False,
                "show_summary": False,
                "show_signatures": True,
            },
            "report_title": "Blood Bank",
            "form_name": "Blood Bank",
            "form_path_label": "Blood Bank",
            "status": "completed",
            "summary_items": [],
            "signatures": [{
                "label": "Analyzed by:",
                "designation": "Medical Technologist (RMT)",
                "name": "Crystel C. Tesoro, RMT",
                "license": "0103760",
                "image_url": "",
            }],
        })
        self.assertEqual(html.count('class="print-result-inline"'), 2)
        self.assertIn('class="print-result-unit">bpm', html)
        self.assertIn('class="print-result-unit">deg C', html)
        self.assertIn("DOH License No.: 03-123456-10", html)
        label_at = html.index('class="print-signature-label">Analyzed by:')
        name_at = html.index('class="print-signature-name">Crystel C. Tesoro, RMT')
        designation_at = html.index('class="print-signature-designation">Medical Technologist (RMT)')
        self.assertLess(label_at, name_at)
        self.assertLess(name_at, designation_at)
        self.assertNotIn(">Examination<", html)
        self.assertNotIn('class="print-row-unit"', html)

    def test_print_temporal_values_are_nontechnical(self) -> None:
        self.assertEqual(format_print_temporal_value("date", "2026-07-16"), "07/16/2026")
        self.assertEqual(
            format_print_temporal_value("datetime", "2026-07-16T10:15"),
            "07/16/2026 10:15 AM",
        )
        self.assertEqual(
            format_print_temporal_value("datetime", "2026-07-16T22:05"),
            "07/16/2026 10:05 PM",
        )
        self.assertEqual(format_print_temporal_value("time", "22:05"), "22:05")
        self.assertEqual(format_print_temporal_value("datetime", "legacy value"), "legacy value")
        self.assertEqual(
            build_print_display_value(
                {"data_type": "date"},
                "2026-07-16",
                None,
                record_id=1,
            )["text"],
            "07/16/2026",
        )
        summary = build_print_summary_items(
            {
                "show_summary": True,
                "summary_items": [{"source": "field", "field_id": "collected_at"}],
            },
            {
                "entry_schema": {
                    "blocks": [{
                        "id": "collected_at",
                        "kind": "field",
                        "name": "Collected at",
                        "props": {"data_type": "datetime"},
                    }],
                },
                "record_identity": {},
                "record_key": "TEST-1",
            },
            {"collected_at": "2026-07-16T22:05"},
            issued_at_label="",
        )
        self.assertEqual(summary[0]["value"], "07/16/2026 10:05 PM")

    def test_doh_license_persists_prints_and_clears(self) -> None:
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        with Session() as session:
            saved = save_clinic_profile(session, ClinicProfilePayload(
                clinic_name="Naic Doctors Hospital Inc.",
                doh_license_number="03-123456-10",
            ))
            printed = build_print_clinic_profile(saved)
            self.assertEqual(saved["doh_license_number"], "03-123456-10")
            self.assertEqual(printed["doh_license_number"], "03-123456-10")

            cleared = save_clinic_profile(session, ClinicProfilePayload(
                clinic_name="Naic Doctors Hospital Inc.",
                doh_license_number="",
            ))
            self.assertEqual(cleared["doh_license_number"], "")

    def test_existing_form_defaults_create_one_new_version(self) -> None:
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        with Session() as session:
            definition = FormDefinition(slug="blood_bank", name="Blood Bank")
            session.add(definition)
            session.flush()
            schema = {
                "schema_version": 1,
                "source_kind": "builder_blocks_v1",
                "meta": {
                    "form_key": "blood_bank",
                    "form_order": 1,
                    "signatories": [
                        {
                            "id": "medical_technologist_1",
                            "label": "Medical Technologist",
                            "input_type": "person_dropdown",
                            "options": [],
                        },
                        {
                            "id": "pathologist",
                            "label": "Custom pathologist",
                            "input_type": "stamp_image",
                            "stamp_image_url": "/signatory-stamps/custom.png",
                            "stamp_image_filename": "custom.png",
                            "stamp_image_mime_type": "image/png",
                        },
                        {
                            "id": "custom_release",
                            "label": "Released by",
                            "input_type": "manual",
                            "manual_name": "Staff",
                        },
                    ],
                },
                "blocks": [],
            }
            session.add(FormVersion(
                form_id=definition.id,
                version_number=1,
                summary="Old defaults",
                schema_json=json.dumps({
                    "id": "form.blood_bank",
                    "key": "blood_bank",
                    "name": "Blood Bank",
                    "order": 1,
                    "fields": [],
                    "sections": [],
                }),
                block_schema_json=json.dumps(schema),
                source="builder",
                is_current=True,
            ))
            session.commit()

            self.assertEqual(ensure_client_signatory_defaults(session), 1)
            self.assertEqual(ensure_client_signatory_defaults(session), 0)
            versions = session.scalars(select(FormVersion).order_by(FormVersion.version_number)).all()
            current = json.loads(versions[-1].block_schema_json)
            slots = current["meta"]["signatories"]
            self.assertEqual(len(versions), 2)
            self.assertFalse(versions[0].is_current)
            self.assertTrue(versions[1].is_current)
            self.assertEqual(
                [slot["id"] for slot in slots[:3]],
                ["medical_technologist_1", "medical_technologist_2", "pathologist"],
            )
            self.assertTrue(current["meta"]["client_signatory_defaults_2026_07"])
            self.assertEqual(slots[2]["stamp_image_url"], "/signatory-stamps/custom.png")
            self.assertIn("custom_release", [slot["id"] for slot in slots])

    def test_default_stamp_copy_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "seed.png"
            destination = root / "runtime" / "default.png"
            source.write_bytes(b"approved-stamp")

            first = ensure_default_pathologist_stamp(
                source_path=source,
                destination_path=destination,
            )
            destination.write_bytes(b"existing-runtime-copy")
            second = ensure_default_pathologist_stamp(
                source_path=source,
                destination_path=destination,
            )

            self.assertEqual(first, destination)
            self.assertEqual(second, destination)
            self.assertEqual(destination.read_bytes(), b"existing-runtime-copy")

    def test_default_signatories_match_approved_workflow(self) -> None:
        slots = default_signatory_slots()
        self.assertEqual(
            [(slot["label"], slot["designation"], slot["input_type"], slot["required"]) for slot in slots],
            [
                ("Analyzed by:", "Medical Technologist (RMT)", "person_dropdown", True),
                ("Verified by:", "Medical Technologist (RMT)", "person_dropdown", True),
                ("Noted by:", "Pathologist", "stamp_image", False),
            ],
        )
        self.assertTrue(slots[2]["stamp_image_url"].endswith("default-pathologist-stamp.png"))

    def test_designation_round_trips_to_print_snapshot(self) -> None:
        slot = normalize_signatory_slot(
            {
                "id": "reviewer",
                "label": "Reviewed by:",
                "designation": "Laboratory Reviewer",
                "input_type": "manual",
                "manual_name": "Alex Cruz",
                "manual_license": "1234",
                "signature_line": False,
            },
            1,
        )
        snapshot = build_signatory_snapshot(slot)
        printable = signatory_snapshots_for_print([snapshot])
        self.assertEqual(snapshot["designation"], "Laboratory Reviewer")
        self.assertEqual(printable[0]["designation"], "Laboratory Reviewer")
        self.assertFalse(printable[0]["signature_line"])
        legacy_slot = normalize_signatory_slot(
            {"id": "legacy", "label": "Approved by:", "designation": "   ", "title": "Legacy Title"},
            2,
        )
        self.assertEqual(legacy_slot["designation"], "Legacy Title")

    def test_two_medtech_choices_are_required_but_stamp_needs_no_record_input(self) -> None:
        slots = default_signatory_slots()
        version = FormVersion(
            form_id=1,
            version_number=1,
            schema_json="{}",
            block_schema_json=json.dumps({"meta": {"signatories": slots}, "blocks": []}),
            source="builder",
            is_current=True,
        )
        record = Record(record_key="TEST-1", form_id=1, form_version_id=1, form_version=version)
        self.assertEqual(
            list_record_completion_issues(record, values={}, indexed_meta={}),
            [
                "Choose required signatory: Analyzed by.",
                "Choose required signatory: Verified by.",
            ],
        )

        first_option = slots[0]["options"][0]["id"]
        completed_meta = {
            "signatories": {
                "medical_technologist_1": {"option_id": first_option},
                "medical_technologist_2": {"option_id": first_option},
            }
        }
        self.assertEqual(
            list_record_completion_issues(record, values={}, indexed_meta=completed_meta),
            [],
        )
