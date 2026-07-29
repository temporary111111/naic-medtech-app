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
os.environ["NDHI_AFTER_CHANGE_BACKUP_DISABLED"] = "1"

from naic_builder.database import (
    Base,
    SKIP_CHANGE_BACKUP_SESSION_KEY,
    engine as runtime_engine,
    migrate_form_versions_legacy_schema_nullable,
)
from naic_builder.models import FormDefinition, FormVersion, Record, User
from naic_builder.schemas import ClinicProfilePayload, FormSavePayload
from naic_builder.services import (
    apply_print_presentation,
    build_block_storage_document_from_legacy_storage,
    build_print_clinic_profile,
    build_print_display_value,
    build_print_items,
    build_print_summary_items,
    build_signatory_snapshot,
    default_signatory_slots,
    ensure_client_signatory_defaults,
    ensure_default_pathologist_stamp,
    ensure_form_version_storage_documents,
    format_print_temporal_value,
    list_record_completion_issues,
    normalize_print_profile,
    normalize_signatory_slot,
    print_orientation_options,
    print_presentation_details,
    print_style_options,
    print_template_id_for,
    print_text_size_options,
    save_user_print_preferences,
    save_clinic_profile,
    signatory_snapshots_for_print,
    update_form,
)


def tearDownModule() -> None:
    runtime_engine.dispose()
    TEST_RUNTIME.cleanup()


class ClientPrintAdjustmentTests(unittest.TestCase):
    def test_top_level_builder_actions_keep_fields_and_containers_flexible(self) -> None:
        source = (ROOT / "app" / "naic_builder" / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn(
            'if (action === "add-content-container") {\n    insertTopLevelContentBlock("container");',
            source,
        )
        self.assertIn(
            'if (action === "add-content-field") {\n    insertTopLevelContentBlock("field");',
            source,
        )
        self.assertNotIn("function addTopLevelFieldInContainer()", source)

    def test_legacy_schema_column_becomes_nullable_before_container_save(self) -> None:
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        initial_schema = {
            "schema_version": 2,
            "source_kind": "builder_blocks_v2",
            "meta": {
                "form_id": "form.blood_gas_analysis",
                "form_key": "blood_gas_analysis",
                "form_name": "Blood Gas Analysis",
                "form_order": 1,
            },
            "blocks": [],
        }

        with engine.begin() as connection:
            connection.exec_driver_sql("DROP TABLE form_versions")
            connection.exec_driver_sql(
                """
                CREATE TABLE form_versions (
                    id INTEGER NOT NULL PRIMARY KEY,
                    form_id INTEGER NOT NULL,
                    version_number INTEGER NOT NULL,
                    summary TEXT,
                    legacy_schema_json TEXT NOT NULL,
                    block_schema_json TEXT,
                    source VARCHAR(40) NOT NULL,
                    is_current BOOLEAN NOT NULL,
                    created_at DATETIME NOT NULL,
                    CONSTRAINT uq_form_version UNIQUE (form_id, version_number),
                    FOREIGN KEY(form_id) REFERENCES form_definitions (id)
                )
                """
            )

        with Session() as session:
            session.info[SKIP_CHANGE_BACKUP_SESSION_KEY] = True
            definition = FormDefinition(slug="blood_gas_analysis", name="Blood Gas Analysis")
            session.add(definition)
            session.flush()
            session.add(FormVersion(
                form_id=definition.id,
                version_number=1,
                summary="Legacy snapshot",
                legacy_schema_json=json.dumps({"id": "form.blood_gas_analysis"}),
                block_schema_json=json.dumps(initial_schema),
                source="builder",
                is_current=True,
            ))
            session.commit()

        with engine.begin() as connection:
            migrate_form_versions_legacy_schema_nullable(connection)
            columns = {row[1]: row for row in connection.exec_driver_sql("PRAGMA table_info(form_versions)")}
            self.assertEqual(columns["legacy_schema_json"][3], 0)
            self.assertEqual(connection.exec_driver_sql("PRAGMA foreign_key_check").all(), [])

        with Session() as session:
            session.info[SKIP_CHANGE_BACKUP_SESSION_KEY] = True
            saved = update_form(session, "blood_gas_analysis", FormSavePayload(
                slug="blood_gas_analysis",
                name="Blood Gas Analysis",
                summary="Add container",
                form_schema={
                    **initial_schema,
                    "blocks": [{
                        "id": "container.new",
                        "kind": "container",
                        "name": "New Container",
                        "props": {"key": "new_container", "order": 1, "notes": []},
                        "children": [{
                            "id": "field.new",
                            "kind": "field",
                            "name": "New Field",
                            "props": {"key": "new_field", "order": 1, "data_type": "text"},
                            "children": [],
                        }],
                    }, {
                        "id": "field.root",
                        "kind": "field",
                        "name": "Root Field",
                        "props": {"key": "root_field", "order": 2, "data_type": "text"},
                        "children": [],
                    }],
                },
            ))
            self.assertEqual(saved["block_schema"]["blocks"][0]["kind"], "container")
            self.assertEqual(saved["block_schema"]["blocks"][0]["children"][0]["kind"], "field")
            self.assertEqual(saved["block_schema"]["blocks"][1]["kind"], "field")
            self.assertEqual(saved["block_schema"]["blocks"][1]["name"], "Root Field")
            versions = session.scalars(select(FormVersion).order_by(FormVersion.version_number)).all()
            self.assertIsNone(versions[-1].legacy_schema_json)

    def test_legacy_forms_preserve_root_fields_and_convert_legacy_containers(self) -> None:
        schema = build_block_storage_document_from_legacy_storage({
            "id": "form.blood_bank",
            "key": "blood_bank",
            "name": "Blood Bank",
            "order": 1,
            "fields": [{
                "id": "blood_bank.examination",
                "key": "examination",
                "name": "Examination",
                "kind": "field",
                "order": 1,
                "control": "input",
                "data_type": "text",
            }],
            "sections": [{
                "id": "blood_bank.crossmatching",
                "key": "crossmatching",
                "name": "Crossmatching",
                "order": 1,
                "fields": [{
                    "id": "blood_bank.crossmatching.vital_signs",
                    "key": "vital_signs",
                    "name": "Vital Signs",
                    "kind": "field_group",
                    "order": 1,
                    "fields": [{
                        "id": "blood_bank.crossmatching.vital_signs.pulse",
                        "key": "pulse",
                        "name": "Pulse",
                        "kind": "field",
                        "order": 1,
                        "control": "input",
                        "data_type": "text",
                    }],
                }],
            }],
        })

        self.assertEqual(schema["schema_version"], 2)
        self.assertEqual(schema["source_kind"], "builder_blocks_v2")
        self.assertEqual(
            [block["name"] for block in schema["blocks"]],
            ["Examination", "Crossmatching"],
        )
        self.assertEqual([block["kind"] for block in schema["blocks"]], ["field", "container"])
        self.assertEqual(schema["blocks"][1]["children"][0]["kind"], "container")

        printed = build_print_items(
            schema["blocks"],
            values={},
            asset_by_field={},
            record_id=1,
            print_config={
                "show_top_level_container_titles": True,
                "show_nested_container_titles": True,
            },
        )
        self.assertEqual(printed[0]["kind"], "field")
        self.assertEqual(printed[1]["kind"], "section")
        self.assertEqual(printed[1]["items"][0]["kind"], "group")

    def test_saved_v1_form_version_upgrades_without_losing_legacy_archive(self) -> None:
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        with Session() as session:
            definition = FormDefinition(slug="blood_bank", name="Blood Bank")
            session.add(definition)
            session.flush()
            legacy_archive = {
                "id": "form.blood_bank",
                "key": "blood_bank",
                "name": "Blood Bank",
                "order": 1,
                "fields": [],
                "sections": [],
            }
            v1_schema = {
                "schema_version": 1,
                "source_kind": "builder_blocks_v1",
                "meta": {"form_id": "form.blood_bank", "form_key": "blood_bank", "form_order": 1},
                "blocks": [
                    {
                        "id": "blood_bank.examination",
                        "kind": "field",
                        "name": "Examination",
                        "props": {"key": "examination", "data_type": "text"},
                        "children": [],
                    },
                    {
                        "id": "blood_bank.crossmatching",
                        "kind": "section",
                        "name": "Crossmatching",
                        "props": {"key": "crossmatching"},
                        "children": [],
                    },
                ],
            }
            version = FormVersion(
                form_id=definition.id,
                version_number=1,
                summary="Legacy v1",
                legacy_schema_json=json.dumps(legacy_archive),
                block_schema_json=json.dumps(v1_schema),
                source="builder",
                is_current=True,
            )
            session.add(version)
            session.commit()

            ensure_form_version_storage_documents(session)
            session.refresh(version)
            upgraded = json.loads(version.block_schema_json)
            self.assertEqual(upgraded["schema_version"], 2)
            self.assertEqual(upgraded["source_kind"], "builder_blocks_v2")
            self.assertEqual(
                [block["name"] for block in upgraded["blocks"]],
                ["Examination", "Crossmatching"],
            )
            self.assertEqual([block["kind"] for block in upgraded["blocks"]], ["field", "container"])
            self.assertEqual(json.loads(version.legacy_schema_json), legacy_archive)

    def test_print_presentation_uses_known_choices_and_user_defaults(self) -> None:
        presentation = apply_print_presentation(
            {"density": "compact"},
            template_id="classic_landscape",
            text_size="large",
        )
        self.assertEqual(presentation["template_id"], "classic_landscape")
        self.assertEqual(presentation["style"], "classic")
        self.assertEqual(presentation["orientation"], "landscape")
        self.assertEqual(presentation["text_size"], "large")

        modern = apply_print_presentation(
            {"density": "compact"},
            template_id="modern_portrait",
            text_size="large",
        )
        self.assertEqual(modern["template_id"], "modern_portrait")
        self.assertEqual(modern["text_size"], "large")
        self.assertEqual(
            apply_print_presentation({}, template_id="unknown", text_size="huge")["template_id"],
            "modern_portrait",
        )
        self.assertEqual(print_template_id_for("classic", "portrait"), "classic_portrait")
        self.assertEqual(print_template_id_for("classic", "landscape"), "classic_landscape")
        self.assertEqual(print_template_id_for("modern", "portrait"), "modern_portrait")
        self.assertEqual(print_template_id_for("modern", "landscape"), "modern_landscape")
        self.assertEqual(print_template_id_for("legacy", "landscape"), "legacy_landscape")
        for template_id in (
            "modern_portrait",
            "classic_portrait",
            "modern_landscape",
            "classic_landscape",
            "legacy_landscape",
        ):
            self.assertEqual(
                apply_print_presentation({}, template_id=template_id, text_size="large")["text_size"],
                "large",
            )
            self.assertEqual(
                [option["id"] for option in print_text_size_options(template_id)],
                ["standard", "large"],
            )

        profile = normalize_print_profile(
            template_id="classic_landscape",
            style="modern",
            text_size="large",
        )
        self.assertEqual(profile["template_id"], "modern_landscape")
        self.assertEqual(profile["style"], "modern")
        self.assertEqual(profile["orientation"], "landscape")
        self.assertEqual(profile["text_size"], "large")
        legacy_profile = normalize_print_profile(
            template_id="legacy_landscape",
            style="legacy",
            orientation="portrait",
            text_size="large",
        )
        self.assertEqual(legacy_profile["template_id"], "legacy_landscape")
        self.assertEqual(legacy_profile["style"], "legacy")
        self.assertEqual(legacy_profile["orientation"], "landscape")
        self.assertEqual(legacy_profile["text_size"], "large")
        modern_landscape = print_presentation_details("modern_landscape")
        self.assertEqual(modern_landscape["style"], "modern")
        self.assertEqual(modern_landscape["orientation_key"], "landscape")
        self.assertEqual(
            [option["id"] for option in print_style_options()],
            ["modern", "classic", "legacy"],
        )
        orientation_options = {option["id"]: option for option in print_orientation_options()}
        self.assertEqual(orientation_options["portrait"]["supported_styles"], ["modern", "classic"])
        self.assertEqual(
            orientation_options["landscape"]["supported_styles"],
            ["modern", "classic", "legacy"],
        )

        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        with Session() as session:
            user = User(
                email="print-default@example.test",
                login_id="print_default",
                full_name="Print Default",
                role="medtech",
                status="active",
                must_change_password=False,
            )
            session.add(user)
            session.commit()

            saved = save_user_print_preferences(
                session,
                user,
                template_id="modern_portrait",
                text_size="large",
            )
            self.assertEqual(saved["template_id"], "modern_portrait")
            self.assertEqual(saved["style"], "modern")
            self.assertEqual(saved["orientation"], "portrait")
            self.assertEqual(saved["text_size"], "large")
            session.refresh(user)
            self.assertEqual(user.print_template_id, "modern_portrait")
            self.assertEqual(user.print_text_size, "large")

            saved = save_user_print_preferences(
                session,
                user,
                template_id="classic_portrait",
                text_size="large",
            )
            self.assertEqual(saved["template_id"], "classic_portrait")
            self.assertEqual(saved["style"], "classic")
            self.assertEqual(saved["orientation"], "portrait")
            self.assertEqual(saved["text_size"], "large")
            session.refresh(user)
            self.assertEqual(user.print_template_id, "classic_portrait")
            self.assertEqual(user.print_text_size, "large")

            saved = save_user_print_preferences(
                session,
                user,
                template_id="legacy_landscape",
                text_size="large",
            )
            self.assertEqual(saved["template_id"], "legacy_landscape")
            self.assertEqual(saved["style"], "legacy")
            self.assertEqual(saved["orientation"], "landscape")
            self.assertEqual(saved["text_size"], "large")
            session.refresh(user)
            self.assertEqual(user.print_template_id, "legacy_landscape")
            self.assertEqual(user.print_text_size, "large")

    def test_print_layout_uses_style_and_orientation_controls(self) -> None:
        source = (ROOT / "app" / "naic_builder" / "templates" / "records" / "print.html").read_text(encoding="utf-8")

        self.assertIn('name="style" value="{{ option.id }}"', source)
        self.assertIn("print_style_options", source)
        self.assertIn("print_orientation_options", source)
        self.assertIn("data-orientation-choice", source)
        self.assertIn("data-supported-styles", source)
        self.assertIn("print-segmented-control--single", source)
        self.assertIn('name="text_size"', source)
        self.assertIn('<span>Text size</span>', source)
        self.assertNotIn("data-template-select", source)
        self.assertNotIn("data-modern-text-options", source)

    def test_selected_font_is_not_overridden_by_classic_or_legacy_pages(self) -> None:
        source = (ROOT / "app" / "naic_builder" / "static" / "print.css").read_text(encoding="utf-8")
        self.assertNotIn(".print-template-classic-portrait .print-page", source)
        for selector in (
            ".print-template-classic-landscape .print-page",
            ".print-template-legacy-landscape .print-page",
        ):
            start = source.index(selector)
            block = source[start:source.index("}", start)]
            self.assertNotIn("font-family:", block)

    def test_builder_and_record_print_use_normal_values_wording(self) -> None:
        builder_source = (ROOT / "app" / "naic_builder" / "static" / "app.js").read_text(encoding="utf-8")
        print_source = (ROOT / "app" / "naic_builder" / "templates" / "records" / "_print_document.html").read_text(encoding="utf-8")
        edit_source = (ROOT / "app" / "naic_builder" / "templates" / "records" / "edit.html").read_text(encoding="utf-8")
        view_source = (ROOT / "app" / "naic_builder" / "templates" / "records" / "view.html").read_text(encoding="utf-8")

        self.assertNotIn("<span>Reference</span>", builder_source)
        self.assertIn("<span>Normal values</span>", builder_source)
        self.assertIn("Normal values ${compactReference}", builder_source)
        self.assertIn("Normal values: {{ field.reference_text }}", print_source)
        self.assertIn("Normal values: {{ item.reference_text }}", print_source)
        self.assertNotIn("Reference:", print_source)
        self.assertIn("Normal values: {{ props.reference_text }}", edit_source)
        self.assertIn("Normal values: {{ props.reference_text }}", view_source)

    def test_shared_print_template_places_units_and_labels_correctly(self) -> None:
        environment = Environment(loader=FileSystemLoader(ROOT / "app" / "naic_builder" / "templates"))
        macro = environment.get_template("records/_print_document.html").module.render_print_page
        row_field = {
            "kind": "field",
            "name": "PULSE RATE",
            "unit_hint": "bpm",
            "reference_text": "60 - 100",
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
        self.assertEqual(html.count("Normal values: 60 - 100"), 2)
        self.assertNotIn("Reference: 60 - 100", html)
        self.assertIn("DOH License No.: 03-123456-10", html)
        label_at = html.index('class="print-signature-label">Analyzed by:')
        name_at = html.index('class="print-signature-name">Crystel C. Tesoro, RMT')
        designation_at = html.index('class="print-signature-designation">Medical Technologist (RMT)')
        self.assertLess(label_at, name_at)
        self.assertLess(name_at, designation_at)
        self.assertNotIn(">Examination<", html)
        self.assertNotIn('class="print-row-unit"', html)

        legacy_html = macro({
            "items": [],
            "clinic": {
                "name": "NDH",
                "logo_url": "/settings/clinic/logo",
                "address": "Naic, Cavite",
                "contact_line": "(046) 412-1443",
                "doh_license_number": "03-123456-10",
            },
            "print_config": {
                "style": "legacy",
                "show_logo": True,
                "show_clinic_info": True,
                "show_status": False,
                "show_summary": False,
                "show_signatures": False,
            },
            "report_title": "Blood Bank",
            "form_name": "Blood Bank",
            "form_path_label": "Blood Bank",
            "status": "completed",
            "summary_items": [],
            "signatures": [],
        })
        self.assertIn('class="print-legacy-header"', legacy_html)
        self.assertIn('src="/settings/clinic/logo"', legacy_html)
        self.assertIn('class="print-legacy-title"', legacy_html)
        self.assertNotIn('class="print-exam-head"', legacy_html)
        self.assertLess(legacy_html.index('src="/settings/clinic/logo"'), legacy_html.index("Blood Bank"))
        self.assertLess(legacy_html.index("Blood Bank"), legacy_html.index("Naic, Cavite"))

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
        self.assertEqual(format_print_temporal_value("time", "10:15"), "10:15 AM")
        self.assertEqual(format_print_temporal_value("time", "22:05"), "10:05 PM")
        self.assertEqual(format_print_temporal_value("time", "00:05"), "12:05 AM")
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
        time_summary = build_print_summary_items(
            {
                "show_summary": True,
                "summary_items": [{"source": "field", "field_id": "collected_time"}],
            },
            {
                "entry_schema": {
                    "blocks": [{
                        "id": "collected_time",
                        "kind": "field",
                        "name": "Collected time",
                        "props": {"data_type": "time"},
                    }],
                },
                "record_identity": {},
                "record_key": "TEST-1",
            },
            {"collected_time": "22:05"},
            issued_at_label="",
        )
        self.assertEqual(time_summary[0]["value"], "10:05 PM")

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
                legacy_schema_json=json.dumps({
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
            legacy_schema_json="{}",
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
