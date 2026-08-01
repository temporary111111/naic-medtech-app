from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

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
from naic_builder.models import FormDefinition, FormVersion, LibraryNode, Record, User
from naic_builder.main import normalize_overview_period
from naic_builder.schemas import ClinicProfilePayload, FormSavePayload
from naic_builder.services import (
    apply_print_presentation,
    apply_print_layout_preference,
    build_block_storage_document_from_legacy_storage,
    build_print_clinic_profile,
    build_print_display_value,
    build_form_print_preview_document,
    build_print_items,
    build_print_reference,
    build_print_summary_items,
    build_signatory_snapshot,
    create_container,
    current_version,
    effective_record_print_presentation,
    default_signatory_slots,
    default_patient_info_legacy_group,
    ensure_blood_bank_defaults,
    ensure_blood_gas_analysis_defaults,
    ensure_blood_chemistry_female_defaults,
    ensure_blood_chemistry_male_defaults,
    ensure_cardiaci_defaults,
    ensure_ogtt_defaults,
    ensure_default_blood_gas_analysis_layout,
    ensure_default_blood_bank_layout,
    ensure_default_blood_chemistry_female_layout,
    ensure_default_blood_chemistry_male_layout,
    ensure_default_cardiaci_layout,
    ensure_default_ogtt_layout,
    ensure_default_covid_19_antigen_rapid_test_layout,
    ensure_default_fecalysis_layout,
    ensure_default_hiv_1_and_2_testing_layout,
    ensure_default_microbiology_layout,
    ensure_default_patient_info_fields,
    ensure_default_hematology_layout,
    ensure_hematology_defaults,
    ensure_default_hba1c_layout,
    ensure_default_pro_time_aptt_layout,
    ensure_hba1c_defaults,
    ensure_hiv_1_and_2_testing_defaults,
    ensure_covid_19_antigen_rapid_test_defaults,
    ensure_fecalysis_defaults,
    ensure_microbiology_defaults,
    ensure_serology_defaults,
    ensure_default_serology_layout,
    ensure_pro_time_aptt_defaults,
    ensure_reference_examination_in_patient_info,
    ensure_reference_seed,
    estimate_print_page_fit,
    ensure_client_signatory_defaults,
    ensure_default_pathologist_stamp,
    ensure_form_version_storage_documents,
    evaluate_print_abnormal,
    format_compact_timestamp_label,
    format_print_temporal_value,
    filter_print_layout_preference_for_items,
    form_version_print_layout_preference,
    list_completed_record_activity_by_form,
    list_record_completion_issues,
    load_block_storage_document,
    normalize_print_config,
    normalize_print_header_text_color,
    normalize_print_paper_size,
    normalize_record_date_scope,
    normalize_print_layout_preference,
    normalize_print_profile,
    normalize_signatory_slot,
    print_header_text_color,
    print_orientation_options,
    print_paper_size_options,
    print_page_fit_limit_units,
    print_presentation_details,
    print_style_options,
    print_template_id_for,
    print_text_size_options,
    record_date_scope_start,
    reference_form_slugs,
    resolve_form_location_metadata,
    sample_print_value_for_field,
    save_user_print_preferences,
    save_user_print_layout_preference,
    save_form_print_layout_default,
    save_clinic_profile,
    save_record_print_presentation,
    signatory_snapshots_for_print,
    snapshot_completed_record_print_presentation,
    update_form,
    user_can_manage_record_print_presentation,
    user_print_layout_preference,
)


def tearDownModule() -> None:
    runtime_engine.dispose()
    TEST_RUNTIME.cleanup()


class ClientPrintAdjustmentTests(unittest.TestCase):
    def test_overview_activity_groups_completed_records_by_form(self) -> None:
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        now = datetime.now(timezone.utc)

        try:
            with Session() as session:
                blood_bank = FormDefinition(slug="blood_bank", name="Blood Bank")
                hematology = FormDefinition(slug="hematology", name="Hematology")
                microbiology = FormDefinition(slug="microbiology", name="Microbiology")
                archived_form = FormDefinition(slug="archived_form", name="Archived Form")
                session.add_all([blood_bank, hematology, microbiology, archived_form])
                session.flush()
                blood_bank_version = FormVersion(
                    form_id=blood_bank.id,
                    version_number=1,
                    block_schema_json="{}",
                    source="builder",
                    is_current=True,
                )
                hematology_version = FormVersion(
                    form_id=hematology.id,
                    version_number=1,
                    block_schema_json="{}",
                    source="builder",
                    is_current=True,
                )
                session.add_all([blood_bank_version, hematology_version])
                session.flush()
                session.add_all([
                    LibraryNode(
                        node_key="form:blood_bank",
                        kind="form",
                        name="Blood Bank",
                        form_definition_id=blood_bank.id,
                        archived=False,
                    ),
                    LibraryNode(
                        node_key="form:hematology",
                        kind="form",
                        name="Hematology",
                        form_definition_id=hematology.id,
                        archived=False,
                    ),
                    LibraryNode(
                        node_key="form:microbiology",
                        kind="form",
                        name="Microbiology",
                        form_definition_id=microbiology.id,
                        archived=False,
                    ),
                    LibraryNode(
                        node_key="form:archived_form",
                        kind="form",
                        name="Archived Form",
                        form_definition_id=archived_form.id,
                        archived=True,
                    ),
                ])
                session.add_all([
                    Record(
                        record_key="overview-blood-bank-1",
                        form_id=blood_bank.id,
                        form_version_id=blood_bank_version.id,
                        status="completed",
                        completed_at=now,
                        updated_at=now,
                    ),
                    Record(
                        record_key="overview-blood-bank-2",
                        form_id=blood_bank.id,
                        form_version_id=blood_bank_version.id,
                        status="completed",
                        completed_at=now,
                        updated_at=now,
                    ),
                    Record(
                        record_key="overview-hematology-1",
                        form_id=hematology.id,
                        form_version_id=hematology_version.id,
                        status="completed",
                        completed_at=now,
                        updated_at=now,
                    ),
                    Record(
                        record_key="overview-draft",
                        form_id=hematology.id,
                        form_version_id=hematology_version.id,
                        status="draft",
                        updated_at=now,
                    ),
                ])
                session.commit()

                activity = list_completed_record_activity_by_form(session)

            self.assertEqual(
                activity,
                [
                    {"slug": "blood_bank", "name": "Blood Bank", "count": 2, "percent": 100},
                    {"slug": "hematology", "name": "Hematology", "count": 1, "percent": 50},
                    {"slug": "microbiology", "name": "Microbiology", "count": 0, "percent": 0},
                ],
            )
        finally:
            engine.dispose()

    def test_builder_location_picker_uses_existing_folders_only(self) -> None:
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)

        try:
            with Session() as session:
                session.info[SKIP_CHANGE_BACKUP_SESSION_KEY] = True
                folder = create_container(session, "Routine Tests")

                selected = resolve_form_location_metadata(
                    session,
                    form_name="Example Form",
                    location_name="Routine Tests",
                    library_parent_node_key=folder.node_key,
                    library_new_container_name=None,
                )
                self.assertEqual(selected["resolved_parent_key"], folder.node_key)

                with self.assertRaisesRegex(ValueError, "Select an existing folder"):
                    resolve_form_location_metadata(
                        session,
                        form_name="Example Form",
                        location_name="Accidental Folder",
                        library_parent_node_key=None,
                        library_new_container_name=None,
                    )

                explicit_new_folder = resolve_form_location_metadata(
                    session,
                    form_name="Example Form",
                    location_name="Special Tests",
                    library_parent_node_key=None,
                    library_new_container_name="Special Tests",
                )
                self.assertTrue(explicit_new_folder["resolved_parent_key"])
        finally:
            engine.dispose()

        builder_source = (ROOT / "app" / "naic_builder" / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn('<select data-action="form-location">', builder_source)
        self.assertNotIn('data-bind="location_name"', builder_source)
        self.assertNotIn('function renderLocationSuggestions()', builder_source)

    def test_shared_patient_information_defaults_are_consistent(self) -> None:
        fields = {field["key"]: field for field in default_patient_info_legacy_group()["fields"]}
        self.assertEqual(fields["age"]["data_type"], "number")
        self.assertEqual(fields["date_or_datetime"]["name"], "Date & Time")
        self.assertEqual(fields["date_or_datetime"]["data_type"], "datetime")
        self.assertEqual(fields["case_number"]["data_type"], "number")

        builder_source = (ROOT / "app" / "naic_builder" / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn('{ key: "age", name: "Age", dataType: "number", required: false },', builder_source)
        self.assertIn('{ key: "date_or_datetime", name: "Date & Time", dataType: "datetime", required: false },', builder_source)
        self.assertIn('{ key: "case_number", name: "Case Number", dataType: "number", required: true },', builder_source)

    def test_reference_forms_keep_examination_inside_patient_information(self) -> None:
        schema = json.loads(
            (ROOT / "artifacts" / "schema" / "naic_medtech_app_schema.json").read_text(encoding="utf-8")
        )
        reference_slugs = reference_form_slugs()
        forms = [form for group in schema["groups"] for form in group["forms"]]

        self.assertEqual({form["key"] for form in forms}, reference_slugs)

        for form in forms:
            block_schema = build_block_storage_document_from_legacy_storage(form)
            self.assertTrue(ensure_reference_examination_in_patient_info(block_schema, reference_slugs))

            patient_info = next(
                block
                for block in block_schema["blocks"]
                if block["props"]["key"] == "patient_information"
            )
            patient_field_keys = [child["props"]["key"] for child in patient_info["children"]]
            self.assertIn("examination", patient_field_keys, form["key"])
            self.assertEqual(
                patient_field_keys.index("examination"),
                patient_field_keys.index("date_or_datetime") + 1,
                form["key"],
            )

        custom_schema = build_block_storage_document_from_legacy_storage(forms[0])
        custom_schema["meta"]["form_key"] = "custom_form"
        before = json.dumps(custom_schema, sort_keys=True)
        self.assertFalse(ensure_reference_examination_in_patient_info(custom_schema, reference_slugs))
        self.assertEqual(json.dumps(custom_schema, sort_keys=True), before)

        legacy_schema = build_block_storage_document_from_legacy_storage(
            next(form for form in forms if form["key"] == "blood_gas_analysis")
        )
        examination = next(
            block for block in legacy_schema["blocks"] if block["props"]["key"] == "examination"
        )
        legacy_schema["blocks"].remove(examination)
        legacy_schema["blocks"].insert(
            1,
            {
                "id": f"{legacy_schema['meta']['form_id']}.details",
                "kind": "container",
                "name": "Blood Gas Analysis Details",
                "props": {"key": "details", "order": 2},
                "children": [examination],
            },
        )
        self.assertTrue(ensure_reference_examination_in_patient_info(legacy_schema, reference_slugs))
        self.assertFalse(
            any(
                block["id"] == f"{legacy_schema['meta']['form_id']}.details"
                for block in legacy_schema["blocks"]
            )
        )

    def test_fresh_reference_seed_applies_patient_information_examination_layout(self) -> None:
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)

        try:
            with Session() as session:
                ensure_reference_seed(session)
                self.assertEqual(ensure_default_patient_info_fields(session), len(reference_form_slugs()))
                self.assertEqual(ensure_blood_bank_defaults(session), 1)
                self.assertEqual(ensure_blood_gas_analysis_defaults(session), 1)
                self.assertEqual(ensure_hematology_defaults(session), 1)
                self.assertEqual(ensure_hba1c_defaults(session), 1)
                self.assertEqual(ensure_pro_time_aptt_defaults(session), 1)
                self.assertEqual(ensure_hiv_1_and_2_testing_defaults(session), 1)
                self.assertEqual(ensure_covid_19_antigen_rapid_test_defaults(session), 1)
                self.assertEqual(ensure_microbiology_defaults(session), 1)
                self.assertEqual(ensure_fecalysis_defaults(session), 1)
                self.assertEqual(ensure_blood_chemistry_male_defaults(session), 1)
                self.assertEqual(ensure_blood_chemistry_female_defaults(session), 1)
                self.assertEqual(ensure_serology_defaults(session), 1)
                self.assertEqual(ensure_cardiaci_defaults(session), 1)
                self.assertEqual(ensure_ogtt_defaults(session), 1)

                definitions = session.scalars(select(FormDefinition)).all()
                self.assertEqual(len(definitions), len(reference_form_slugs()))
                for definition in definitions:
                    block_schema, _ = load_block_storage_document(current_version(definition))
                    patient_info = next(
                        block
                        for block in block_schema["blocks"]
                        if block["props"]["key"] == "patient_information"
                    )
                    patient_field_keys = [child["props"]["key"] for child in patient_info["children"]]
                    self.assertIn("examination", patient_field_keys, definition.slug)

                blood_bank = session.scalar(
                    select(FormDefinition).where(FormDefinition.slug == "blood_bank")
                )
                self.assertIsNotNone(blood_bank)
                legacy_layout = form_version_print_layout_preference(
                    current_version(blood_bank),
                    template_id="legacy_landscape",
                    paper_size="a5",
                )
                self.assertEqual(
                    legacy_layout["grids"]["root/form.blood_bank.details:0"]["mode"],
                    "manual",
                )
                self.assertEqual(
                    legacy_layout["grids"]["root/form.blood_bank.details:0"]["spans"][
                        "form.blood_bank.serial_number"
                    ],
                    6,
                )
                blood_gas = session.scalar(
                    select(FormDefinition).where(FormDefinition.slug == "blood_gas_analysis")
                )
                self.assertIsNotNone(blood_gas)
                blood_gas_layout = form_version_print_layout_preference(
                    current_version(blood_gas),
                    template_id="legacy_landscape",
                    paper_size="a5",
                )
                self.assertEqual(
                    blood_gas_layout["containers"]["root:containers:0"]["spans"],
                    {
                        "root/form.blood_gas_analysis.patient_information": 6,
                        "root/form.blood_gas_analysis.blood_gas_values": 2,
                        "root/form.blood_gas_analysis.calculated_values": 4,
                    },
                )
                self.assertEqual(ensure_blood_bank_defaults(session), 0)
                self.assertEqual(ensure_blood_gas_analysis_defaults(session), 0)
        finally:
            engine.dispose()

    def test_qualitative_form_defaults_apply_normal_options_and_required_covid_image(self) -> None:
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)

        try:
            with Session() as session:
                ensure_reference_seed(session)
                ensure_default_patient_info_fields(session)
                self.assertEqual(ensure_hiv_1_and_2_testing_defaults(session), 1)
                self.assertEqual(ensure_covid_19_antigen_rapid_test_defaults(session), 1)
                self.assertEqual(ensure_microbiology_defaults(session), 1)
                self.assertEqual(ensure_hiv_1_and_2_testing_defaults(session), 0)
                self.assertEqual(ensure_covid_19_antigen_rapid_test_defaults(session), 0)
                self.assertEqual(ensure_microbiology_defaults(session), 0)

                schemas: dict[str, dict] = {}
                for definition in session.scalars(select(FormDefinition)).all():
                    if definition.slug in {
                        "hiv_1_and_2_testing",
                        "covid_19_antigen_rapid_test",
                        "microbiology",
                    }:
                        schemas[definition.slug], _ = load_block_storage_document(current_version(definition))

                def fields_by_key(blocks):
                    fields = {}
                    for block in blocks:
                        if block["kind"] == "field":
                            fields[block["props"]["key"]] = block
                        fields.update(fields_by_key(block.get("children") or []))
                    return fields

                hiv_fields = fields_by_key(schemas["hiv_1_and_2_testing"]["blocks"])
                covid_fields = fields_by_key(schemas["covid_19_antigen_rapid_test"]["blocks"])
                microbiology_fields = fields_by_key(schemas["microbiology"]["blocks"])
                hiv_definition = next(
                    definition
                    for definition in session.scalars(select(FormDefinition)).all()
                    if definition.slug == "hiv_1_and_2_testing"
                )
                hiv_layout = form_version_print_layout_preference(
                    current_version(hiv_definition),
                    template_id="legacy_landscape",
                    paper_size="a5",
                )
                covid_definition = next(
                    definition
                    for definition in session.scalars(select(FormDefinition)).all()
                    if definition.slug == "covid_19_antigen_rapid_test"
                )
                covid_layout = form_version_print_layout_preference(
                    current_version(covid_definition),
                    template_id="legacy_landscape",
                    paper_size="a5",
                )
                microbiology_definition = next(
                    definition
                    for definition in session.scalars(select(FormDefinition)).all()
                    if definition.slug == "microbiology"
                )
                microbiology_layout = form_version_print_layout_preference(
                    current_version(microbiology_definition),
                    template_id="legacy_landscape",
                    paper_size="a5",
                )

                self.assertEqual(
                    hiv_layout["grids"]["root/form.hiv_1_and_2_testing.details:0"]["spans"],
                    {
                        "form.hiv_1_and_2_testing.lot_number": 3,
                        "form.hiv_1_and_2_testing.test_result": 3,
                    },
                )
                self.assertEqual(
                    covid_layout["grids"]["root/form.covid_19_antigen_rapid_test.details:0"]["spans"],
                    {
                        "form.covid_19_antigen_rapid_test.test_result": 6,
                        "form.covid_19_antigen_rapid_test.result_image": 6,
                    },
                )
                self.assertEqual(
                    microbiology_layout["grids"]["root/form.microbiology.details:0"]["spans"],
                    {"form.microbiology.result": 6},
                )

                self.assertEqual(
                    [option["name"] for option in hiv_fields["test_result"]["props"]["options"] if option["is_normal"]],
                    ["NON-REACTIVE"],
                )
                self.assertEqual(
                    [option["name"] for option in covid_fields["test_result"]["props"]["options"] if option["is_normal"]],
                    ["NEGATIVE"],
                )
                self.assertEqual(
                    [option["name"] for option in microbiology_fields["result"]["props"]["options"] if option["is_normal"]],
                    ["NO FUNGAL ELEMENTS SEEN"],
                )
                self.assertEqual(evaluate_print_abnormal(hiv_fields["test_result"]["props"], "NON-REACTIVE"), (False, None))
                self.assertEqual(evaluate_print_abnormal(hiv_fields["test_result"]["props"], "REACTIVE"), (True, "abnormal"))
                self.assertEqual(evaluate_print_abnormal(covid_fields["test_result"]["props"], "NEGATIVE"), (False, None))
                self.assertEqual(evaluate_print_abnormal(covid_fields["test_result"]["props"], "POSITIVE"), (True, "abnormal"))
                self.assertEqual(
                    evaluate_print_abnormal(microbiology_fields["result"]["props"], "NO FUNGAL ELEMENTS SEEN"),
                    (False, None),
                )
                self.assertEqual(
                    evaluate_print_abnormal(microbiology_fields["result"]["props"], "POSITIVE FOR FUNGAL ELEMENTS"),
                    (True, "abnormal"),
                )

                result_image = covid_fields["result_image"]
                self.assertEqual(result_image["name"], "Result Image")
                self.assertEqual(result_image["props"]["control"], "input")
                self.assertEqual(result_image["props"]["data_type"], "image")
                self.assertFalse(result_image["props"].get("required", False))

                printed_covid_items = build_print_items(
                    schemas["covid_19_antigen_rapid_test"]["blocks"],
                    values={},
                    asset_by_field={},
                    record_id=1,
                )
                covid_detail_items = printed_covid_items[-1]["items"]
                self.assertNotIn(
                    "Result Image",
                    [item["name"] for item in covid_detail_items if item["kind"] == "field"],
                )
        finally:
            engine.dispose()

    def test_blood_gas_defaults_use_approved_layout_and_ranges(self) -> None:
        schema = json.loads(
            (ROOT / "artifacts" / "schema" / "naic_medtech_app_schema.json").read_text(encoding="utf-8")
        )
        blood_gas = next(
            form
            for group in schema["groups"]
            for form in group["forms"]
            if form["key"] == "blood_gas_analysis"
        )
        block_schema = build_block_storage_document_from_legacy_storage(blood_gas)
        ensure_reference_examination_in_patient_info(block_schema, reference_form_slugs())

        self.assertTrue(ensure_default_blood_gas_analysis_layout(block_schema))
        legacy_layout = block_schema["meta"]["print_layout_defaults"]["profiles"]["legacy_landscape:a5"]
        self.assertEqual(
            legacy_layout["containers"]["root:containers:0"]["spans"],
            {
                "root/form.blood_gas_analysis.patient_information": 6,
                "root/form.blood_gas_analysis.blood_gas_values": 2,
                "root/form.blood_gas_analysis.calculated_values": 4,
            },
        )
        top_level = {block["props"]["key"]: block for block in block_schema["blocks"]}
        self.assertEqual(
            [block["props"]["key"] for block in block_schema["blocks"]],
            ["patient_information", "blood_gas_values", "calculated_values"],
        )
        self.assertEqual(
            [child["props"]["key"] for child in top_level["blood_gas_values"]["children"]],
            ["abg", "note"],
        )
        self.assertEqual(
            [child["props"]["key"] for child in top_level["calculated_values"]["children"]],
            ["oximetry", "acid_base_status"],
        )
        printed = build_print_items(
            block_schema["blocks"],
            values={},
            asset_by_field={},
            record_id=1,
            print_config={
                "show_top_level_container_titles": True,
                "show_nested_container_titles": True,
            },
        )
        printed_sections = {
            item["name"]: item
            for top_level_item in printed
            for item in (
                top_level_item["items"]
                if top_level_item["kind"] == "container_run"
                else [top_level_item]
            )
            if item["kind"] == "section"
        }

        def print_item_names(items):
            names = []
            for item in items:
                if item["kind"] == "field_run":
                    names.extend(child["name"] for child in item["items"])
                elif item["kind"] in {"container_run", "block_run"}:
                    names.extend(print_item_names(item["items"]))
                else:
                    names.append(item["name"])
            return names

        self.assertEqual(
            print_item_names(printed_sections["Blood Gas Values"]["items"]),
            ["ABG", "NOTE"],
        )
        self.assertEqual(
            print_item_names(printed_sections["Calculated Values"]["items"]),
            ["Oximetry", "Acid-Base Status"],
        )
        preview = build_form_print_preview_document(
            form_name="Blood Gas Analysis",
            block_schema=block_schema,
        )
        legacy_a5_fit = estimate_print_page_fit(
            {
                "print_config": apply_print_presentation(
                    {},
                    template_id="legacy_landscape",
                    text_size="standard",
                    paper_size="a5",
                ),
                "items": preview["items"],
            }
        )
        self.assertTrue(legacy_a5_fit["requires_one_page"])
        self.assertTrue(legacy_a5_fit["can_print"])
        preview_with_layout = build_form_print_preview_document(
            form_name="Blood Gas Analysis",
            block_schema=block_schema,
            template_id="legacy_landscape",
            paper_size="a5",
            print_layout_preference=legacy_layout,
        )
        self.assertTrue(preview_with_layout["fit_estimate"]["requires_one_page"])
        self.assertTrue(preview_with_layout["fit_estimate"]["can_print"])

        fields = {}

        def collect_fields(blocks):
            for block in blocks:
                if block["kind"] == "field":
                    fields[block["props"]["key"]] = block
                collect_fields(block["children"])

        collect_fields(block_schema["blocks"])
        self.assertEqual(fields["ph"]["props"]["normal_min"], "7.35")
        self.assertEqual(fields["ph"]["props"]["normal_max"], "7.45")
        self.assertEqual(fields["be_ecf"]["props"]["normal_min"], "-2")
        self.assertEqual(fields["be_ecf"]["props"]["normal_max"], "+2")
        self.assertNotIn("reference_text", fields["pco2"]["props"])
        self.assertNotIn("normal_value", fields["pco2"]["props"])
        self.assertEqual(build_print_reference(fields["pco2"]["props"]), "35.0 to 45.0 mmHg")
        self.assertEqual(build_print_reference(fields["be_ecf"]["props"]), "-2 to +2 mmol/L")
        self.assertEqual(evaluate_print_abnormal(fields["ph"]["props"], "7.35"), (False, None))
        self.assertEqual(evaluate_print_abnormal(fields["ph"]["props"], "7.46"), (True, "high"))
        self.assertEqual(evaluate_print_abnormal(fields["be_ecf"]["props"], "-2.1"), (True, "low"))
        legacy_layout["containers"]["root:containers:0"]["spans"][
            "root/form.blood_gas_analysis.blood_gas_values"
        ] = 6
        self.assertFalse(ensure_default_blood_gas_analysis_layout(block_schema))
        self.assertEqual(
            legacy_layout["containers"]["root:containers:0"]["spans"][
                "root/form.blood_gas_analysis.blood_gas_values"
            ],
            6,
        )

    def test_hematology_defaults_use_approved_layout_and_ranges(self) -> None:
        schema = json.loads(
            (ROOT / "artifacts" / "schema" / "naic_medtech_app_schema.json").read_text(encoding="utf-8")
        )
        hematology = next(
            form
            for group in schema["groups"]
            for form in group["forms"]
            if form["key"] == "hematology"
        )
        block_schema = build_block_storage_document_from_legacy_storage(hematology)
        ensure_reference_examination_in_patient_info(block_schema, reference_form_slugs())

        self.assertTrue(ensure_default_hematology_layout(block_schema))
        details = next(
            block
            for block in block_schema["blocks"]
            if block["props"]["key"] == "details"
        )
        self.assertEqual(
            [child["props"]["key"] for child in details["children"]],
            [
                "rbc_count_m",
                "rbc_count_f",
                "wbc_count",
                "hemoglobin_m",
                "hemoglobin_f",
                "hematocrit_m",
                "hematocrit_f",
                "platelet_count",
                "clotting_time",
                "bleeding_time",
                "blood_typing",
                "differential_count",
                "others",
            ],
        )
        differential_count = next(
            child for child in details["children"] if child["props"]["key"] == "differential_count"
        )
        self.assertEqual(
            [child["props"]["key"] for child in differential_count["children"]],
            [
                "segmenters",
                "lymphocytes",
                "monocytes",
                "eosinophils",
                "stab",
                "e_s_r_m",
                "e_s_r_f",
            ],
        )

        fields = {}

        def collect_fields(blocks):
            for block in blocks:
                if block["kind"] == "field":
                    fields[block["props"]["key"]] = block
                collect_fields(block["children"])

        collect_fields(block_schema["blocks"])
        self.assertEqual(fields["rbc_count_m"]["props"]["normal_min"], "4.6")
        self.assertEqual(fields["rbc_count_m"]["props"]["normal_max"], "6.2")
        self.assertEqual(fields["rbc_count_m"]["props"]["unit"], "x10^12/L")
        self.assertEqual(fields["rbc_count_m"]["props"]["unit_hint"], "x10^12/L")
        self.assertNotIn("reference_text", fields["rbc_count_m"]["props"])
        self.assertNotIn("normal_value", fields["rbc_count_m"]["props"])
        self.assertEqual(build_print_reference(fields["rbc_count_m"]["props"]), "4.6 to 6.2 x10^12/L")
        self.assertEqual(fields["wbc_count"]["props"]["unit"], "x10^9/L")
        self.assertEqual(fields["e_s_r_f"]["props"]["normal_max"], "20")
        self.assertEqual(evaluate_print_abnormal(fields["rbc_count_m"]["props"], "4.5"), (True, "low"))
        self.assertEqual(evaluate_print_abnormal(fields["rbc_count_m"]["props"], "6.3"), (True, "high"))
        self.assertEqual(evaluate_print_abnormal(fields["segmenters"]["props"], "0.50"), (False, None))
        self.assertEqual(evaluate_print_abnormal(fields["segmenters"]["props"], "0.49"), (True, "low"))
        self.assertEqual(sample_print_value_for_field(fields["clotting_time"]), "3.5")

    def test_hba1c_defaults_use_approved_range(self) -> None:
        schema = json.loads(
            (ROOT / "artifacts" / "schema" / "naic_medtech_app_schema.json").read_text(encoding="utf-8")
        )
        hba1c = next(
            form
            for group in schema["groups"]
            for form in group["forms"]
            if form["key"] == "hba1c"
        )
        block_schema = build_block_storage_document_from_legacy_storage(hba1c)
        ensure_reference_examination_in_patient_info(block_schema, reference_form_slugs())

        self.assertTrue(ensure_default_hba1c_layout(block_schema))
        legacy_layout = block_schema["meta"]["print_layout_defaults"]["profiles"]["legacy_landscape:a5"]
        self.assertEqual(
            legacy_layout["grids"]["root/form.hba1c.patient_information:0"]["spans"],
            {
                "form.hba1c.patient_information.name": 2,
                "form.hba1c.patient_information.age": 2,
                "form.hba1c.patient_information.sex": 2,
                "form.hba1c.patient_information.date_or_datetime": 2,
                "form.hba1c.examination": 2,
                "form.hba1c.patient_information.requesting_physician": 2,
                "form.hba1c.patient_information.room": 3,
                "form.hba1c.patient_information.case_number": 3,
            },
        )
        details = next(block for block in block_schema["blocks"] if block["props"]["key"] == "details")
        result = next(child for child in details["children"] if child["props"]["key"] == "result")
        self.assertEqual(result["props"]["normal_min"], "4.0")
        self.assertEqual(result["props"]["normal_max"], "5.6")
        self.assertEqual(result["props"]["unit"], "%")
        self.assertEqual(result["props"]["unit_hint"], "%")
        self.assertNotIn("reference_text", result["props"])
        self.assertNotIn("normal_value", result["props"])
        self.assertEqual(build_print_reference(result["props"]), "4.0 to 5.6 %")
        self.assertEqual(evaluate_print_abnormal(result["props"], "4.0"), (False, None))
        self.assertEqual(evaluate_print_abnormal(result["props"], "5.7"), (True, "high"))
        legacy_layout["grids"]["root/form.hba1c.patient_information:0"]["spans"][
            "form.hba1c.patient_information.name"
        ] = 6
        self.assertFalse(ensure_default_hba1c_layout(block_schema))

    def test_blood_chemistry_defaults_use_workbook_ranges(self) -> None:
        schema = json.loads(
            (ROOT / "artifacts" / "schema" / "naic_medtech_app_schema.json").read_text(encoding="utf-8")
        )
        forms = {
            form["key"]: form
            for group in schema["groups"]
            for form in group["forms"]
            if form["key"] in {"male", "female"}
        }
        expected_ranges = {
            "male": {
                "fasting_blood_sugar": ("70.27", "124.32"),
                "random_blood_sugar": ("60", "140"),
                "hgt": ("53", "103"),
                "blood_urea_nitrogen": ("7.9", "20.2"),
                "creatinine": ("0.5", "1.3"),
                "blood_uric_acid": ("3.5", "7.2"),
                "sodium": ("135", "148"),
                "potassium": ("3.5", "5.3"),
                "chloride": ("98", "107"),
                "ionized_calcium": ("1.13", "1.32"),
                "cholesterol": ("0", "200"),
                "triglyceride": ("0", "150"),
                "hdl_cholesterol": ("30", "85"),
                "ldl_cholesterol": ("66", "178"),
                "vldl_cholesterol": ("0", "40"),
                "sgot_ast": ("0", "31"),
                "sgpt_alt": ("0", "34"),
            },
            "female": {
                "fasting_blood_sugar": ("70.27", "124.32"),
                "random_blood_sugar": ("60", "140"),
                "hgt": ("53", "103"),
                "blood_urea_nitrogen": ("7.9", "20.2"),
                "creatinine": ("0.4", "1.2"),
                "blood_uric_acid": ("2.6", "6.0"),
                "sodium": ("135", "148"),
                "potassium": ("3.5", "5.3"),
                "chloride": ("98", "107"),
                "ionized_calcium": ("1.13", "1.32"),
                "cholesterol": ("0", "200"),
                "triglyceride": ("0", "150"),
                "hdl_cholesterol": ("30", "85"),
                "ldl_cholesterol": ("66", "178"),
                "vldl_cholesterol": ("0", "40"),
                "sgot_ast": ("0", "31"),
                "sgpt_alt": ("0", "34"),
            },
        }
        layout_by_key = {
            "male": ensure_default_blood_chemistry_male_layout,
            "female": ensure_default_blood_chemistry_female_layout,
        }

        for form_key, expected in expected_ranges.items():
            block_schema = build_block_storage_document_from_legacy_storage(forms[form_key])
            ensure_reference_examination_in_patient_info(block_schema, reference_form_slugs())
            self.assertTrue(layout_by_key[form_key](block_schema))
            if form_key in {"male", "female"}:
                legacy_layout = block_schema["meta"]["print_layout_defaults"]["profiles"][
                    "legacy_landscape:a5"
                ]
                self.assertEqual(
                    legacy_layout["grids"][f"root/form.{form_key}.details:0"]["spans"],
                    {
                        f"form.{form_key}.fasting_blood_sugar": 2,
                        f"form.{form_key}.random_blood_sugar": 2,
                        f"form.{form_key}.hgt": 2,
                        f"form.{form_key}.blood_urea_nitrogen": 2,
                        f"form.{form_key}.creatinine": 2,
                        f"form.{form_key}.blood_uric_acid": 2,
                        f"form.{form_key}.sodium": 2,
                        f"form.{form_key}.potassium": 2,
                        f"form.{form_key}.chloride": 2,
                        f"form.{form_key}.ionized_calcium": 2,
                        f"form.{form_key}.cholesterol": 2,
                        f"form.{form_key}.triglyceride": 2,
                        f"form.{form_key}.hdl_cholesterol": 2,
                        f"form.{form_key}.ldl_cholesterol": 2,
                        f"form.{form_key}.vldl_cholesterol": 2,
                        f"form.{form_key}.sgot_ast": 3,
                        f"form.{form_key}.sgpt_alt": 3,
                        f"form.{form_key}.others": 6,
                    },
                )
            details = next(block for block in block_schema["blocks"] if block["props"]["key"] == "details")
            fields = {child["props"]["key"]: child for child in details["children"]}
            self.assertIn("others", fields)
            for field_key, (normal_min, normal_max) in expected.items():
                props = fields[field_key]["props"]
                self.assertEqual(props["normal_min"], normal_min, field_key)
                self.assertEqual(props["normal_max"], normal_max, field_key)
                self.assertNotIn("reference_text", props, field_key)
                self.assertNotIn("normal_value", props, field_key)

            creatinine = fields["creatinine"]
            low_value = "0.4" if form_key == "male" else "0.3"
            self.assertEqual(evaluate_print_abnormal(creatinine["props"], low_value), (True, "low"))
            self.assertEqual(
                build_print_reference(fields["fasting_blood_sugar"]["props"]),
                "70.27 to 124.32 mg/dl",
            )

    def test_serology_and_cardiaci_defaults_use_workbook_values(self) -> None:
        schema = json.loads(
            (ROOT / "artifacts" / "schema" / "naic_medtech_app_schema.json").read_text(encoding="utf-8")
        )
        forms = {
            form["key"]: form
            for group in schema["groups"]
            for form in group["forms"]
            if form["key"] in {"serology", "cardiaci"}
        }

        serology_schema = build_block_storage_document_from_legacy_storage(forms["serology"])
        ensure_reference_examination_in_patient_info(serology_schema, reference_form_slugs())
        self.assertTrue(ensure_default_serology_layout(serology_schema))
        serology_fields: dict[str, list[dict]] = {}

        def collect_fields(blocks):
            for block in blocks:
                if block["kind"] == "field":
                    serology_fields.setdefault(block["props"]["key"], []).append(block)
                collect_fields(block.get("children") or [])

        collect_fields(serology_schema["blocks"])
        expected_normal_choices = {
            "igm": "NEGATIVE",
            "igg": "NEGATIVE",
            "ns1ag": "NEGATIVE",
            "anti_plasmodium_falcifarum": "NEGATIVE",
            "anti_plasmodium_vivax": "NEGATIVE",
            "hbsag_screening": "NON-REACTIVE",
            "vdrl": "NEGATIVE",
            "anti_hcv": "NON-REACTIVE",
            "aso_titer": "NEGATIVE <200 IU/ML",
        }
        for field_key, normal_choice in expected_normal_choices.items():
            self.assertGreaterEqual(len(serology_fields[field_key]), 1, field_key)
            for field in serology_fields[field_key]:
                props = field["props"]
                self.assertEqual(
                    [option["name"] for option in props["options"] if option["is_normal"]],
                    [normal_choice],
                    field_key,
                )
                self.assertEqual(evaluate_print_abnormal(props, normal_choice), (False, None))
        self.assertEqual(
            evaluate_print_abnormal(serology_fields["igm"][0]["props"], "POSITIVE"),
            (True, "abnormal"),
        )
        self.assertEqual(
            evaluate_print_abnormal(serology_fields["hbsag_screening"][0]["props"], "REACTIVE"),
            (True, "abnormal"),
        )

        cardiaci_schema = build_block_storage_document_from_legacy_storage(forms["cardiaci"])
        ensure_reference_examination_in_patient_info(cardiaci_schema, reference_form_slugs())
        self.assertTrue(ensure_default_cardiaci_layout(cardiaci_schema))
        cardiaci_layout = cardiaci_schema["meta"]["print_layout_defaults"]["profiles"]["legacy_landscape:a5"]
        self.assertEqual(
            cardiaci_layout["grids"]["root/form.cardiaci.details:0"]["spans"],
            {
                "form.cardiaci.ck_mb": 6,
                "form.cardiaci.troponin_i": 6,
                "form.cardiaci.bnp": 6,
            },
        )
        details = next(block for block in cardiaci_schema["blocks"] if block["props"]["key"] == "details")
        cardiaci_fields = {child["props"]["key"]: child for child in details["children"]}
        expected_ranges = {
            "ck_mb": ("0.0", "4.3"),
            "troponin_i": ("0.0", "0.02"),
            "bnp": ("0.0", "100"),
        }
        for field_key, (normal_min, normal_max) in expected_ranges.items():
            props = cardiaci_fields[field_key]["props"]
            self.assertEqual((props["normal_min"], props["normal_max"]), (normal_min, normal_max))
            self.assertNotIn("reference_text", props)
            self.assertNotIn("normal_value", props)
        self.assertEqual(build_print_reference(cardiaci_fields["ck_mb"]["props"]), "0.0 to 4.3 ng/mL")
        self.assertEqual(evaluate_print_abnormal(cardiaci_fields["troponin_i"]["props"], "0.03"), (True, "high"))

    def test_ogtt_defaults_use_workbook_ranges_and_exclusive_upper_limits(self) -> None:
        schema = json.loads(
            (ROOT / "artifacts" / "schema" / "naic_medtech_app_schema.json").read_text(encoding="utf-8")
        )
        ogtt = next(
            form
            for group in schema["groups"]
            for form in group["forms"]
            if form["key"] == "ogtt"
        )
        block_schema = build_block_storage_document_from_legacy_storage(ogtt)
        ensure_reference_examination_in_patient_info(block_schema, reference_form_slugs())
        self.assertTrue(ensure_default_ogtt_layout(block_schema))
        legacy_layout = block_schema["meta"]["print_layout_defaults"]["profiles"][
            "legacy_landscape:a5"
        ]
        self.assertEqual(
            legacy_layout["containers"]["root:containers:0"]["spans"],
            {
                "root/form.ogtt.patient_information": 6,
                "root/form.ogtt.50g_oral_glucose_tolerance": 3,
                "root/form.ogtt.75g_oral_glucose_tolerance": 3,
                "root/form.ogtt.100g_oral_glucose_tolerance": 3,
                "root/form.ogtt.additional_tests": 3,
            },
        )
        containers = {block["props"]["key"]: block for block in block_schema["blocks"]}

        expected_ranges = {
            "50g_oral_glucose_tolerance": {
                "1st_hour": (None, "200", False),
                "2nd_hour": (None, "140", False),
            },
            "75g_oral_glucose_tolerance": {
                "fasting_blood_sugar": ("70.27", "124.32", True),
                "1st_hour": (None, "200", False),
                "2nd_hour": (None, "140", False),
            },
            "100g_oral_glucose_tolerance": {
                "fasting_blood_sugar": ("70.27", "124.32", True),
                "1st_hour": (None, "180", False),
                "2nd_hour": (None, "155", False),
                "3rd_hour": (None, "140", False),
            },
        }
        for container_key, field_ranges in expected_ranges.items():
            fields = {
                child["props"]["key"]: child
                for child in containers[container_key]["children"]
                if child["kind"] == "field"
            }
            for field_key, (normal_min, normal_max, max_is_inclusive) in field_ranges.items():
                props = fields[field_key]["props"]
                self.assertEqual(props.get("normal_min"), normal_min, field_key)
                self.assertEqual(props.get("normal_max"), normal_max, field_key)
                self.assertEqual(
                    props.get("normal_max_inclusive", True),
                    max_is_inclusive,
                    field_key,
                )
                self.assertNotIn("reference_text", props, field_key)
                self.assertNotIn("normal_value", props, field_key)

        fifty_gram_first_hour = next(
            child
            for child in containers["50g_oral_glucose_tolerance"]["children"]
            if child["props"]["key"] == "1st_hour"
        )
        self.assertEqual(build_print_reference(fifty_gram_first_hour["props"]), "< 200 mg/dl")
        self.assertEqual(evaluate_print_abnormal(fifty_gram_first_hour["props"], "199.99"), (False, None))
        self.assertEqual(evaluate_print_abnormal(fifty_gram_first_hour["props"], "200"), (True, "high"))

        additional_fields = {
            child["props"]["key"]: child
            for child in containers["additional_tests"]["children"]
            if child["kind"] == "field"
        }
        self.assertNotIn("normal_min", additional_fields["2_hours_post_prandial"]["props"])
        self.assertNotIn("normal_max", additional_fields["50_g_oral_glucose_challenge"]["props"])

    def test_fecalysis_defaults_mark_only_explicit_negative_findings_as_normal(self) -> None:
        schema = json.loads(
            (ROOT / "artifacts" / "schema" / "naic_medtech_app_schema.json").read_text(encoding="utf-8")
        )
        fecalysis = next(
            form
            for group in schema["groups"]
            for form in group["forms"]
            if form["key"] == "fecalysis"
        )
        block_schema = build_block_storage_document_from_legacy_storage(fecalysis)
        ensure_reference_examination_in_patient_info(block_schema, reference_form_slugs())
        self.assertTrue(ensure_default_fecalysis_layout(block_schema))
        legacy_layout = block_schema["meta"]["print_layout_defaults"]["profiles"][
            "legacy_landscape:a5"
        ]
        self.assertEqual(
            legacy_layout["containers"]["root:containers:0"]["spans"],
            {
                "root/form.fecalysis.patient_information": 6,
                "root/form.fecalysis.macroscopic_finding": 2,
                "root/form.fecalysis.microscopic_finding": 4,
            },
        )

        fields: dict[str, dict] = {}

        def collect_fields(blocks):
            for block in blocks:
                if block["kind"] == "field":
                    fields[block["props"]["key"]] = block
                collect_fields(block.get("children") or [])

        collect_fields(block_schema["blocks"])
        expected_normal_choices = {
            "fecal_occult_blood": "NEGATIVE",
            "parasites": "NO OVA NOR PARASITES SEEN",
        }
        for field_key, normal_choice in expected_normal_choices.items():
            props = fields[field_key]["props"]
            self.assertEqual(
                [option["name"] for option in props["options"] if option["is_normal"]],
                [normal_choice],
            )
            self.assertEqual(evaluate_print_abnormal(props, normal_choice), (False, None))

        self.assertEqual(
            evaluate_print_abnormal(fields["fecal_occult_blood"]["props"], "POSITIVE"),
            (True, "abnormal"),
        )
        self.assertEqual(
            evaluate_print_abnormal(fields["parasites"]["props"], "ASCARIS LUMBRICOIDES OVA"),
            (True, "abnormal"),
        )
        self.assertNotIn("normal_min", fields["pus"]["props"])
        self.assertNotIn("normal_max", fields["red_blood_cell"]["props"])

    def test_pro_time_aptt_defaults_use_approved_ranges(self) -> None:
        schema = json.loads(
            (ROOT / "artifacts" / "schema" / "naic_medtech_app_schema.json").read_text(encoding="utf-8")
        )
        pro_time_aptt = next(
            form
            for group in schema["groups"]
            for form in group["forms"]
            if form["key"] == "pro_time_aptt"
        )
        block_schema = build_block_storage_document_from_legacy_storage(pro_time_aptt)
        ensure_reference_examination_in_patient_info(block_schema, reference_form_slugs())

        self.assertTrue(ensure_default_pro_time_aptt_layout(block_schema))
        legacy_layout = block_schema["meta"]["print_layout_defaults"]["profiles"]["legacy_landscape:a5"]
        self.assertEqual(
            legacy_layout["containers"]["root:containers:0"]["spans"],
            {
                "root/form.pro_time_aptt.patient_information": 6,
                "root/form.pro_time_aptt.pro_time": 3,
                "root/form.pro_time_aptt.aptt": 3,
            },
        )
        pro_time = next(block for block in block_schema["blocks"] if block["props"]["key"] == "pro_time")
        aptt = next(block for block in block_schema["blocks"] if block["props"]["key"] == "aptt")
        pro_fields = {child["props"]["key"]: child for child in pro_time["children"]}
        aptt_fields = {child["props"]["key"]: child for child in aptt["children"]}
        self.assertEqual(pro_fields["test"]["props"]["normal_min"], "10.0")
        self.assertEqual(pro_fields["test"]["props"]["normal_max"], "13.9")
        self.assertEqual(pro_fields["test"]["props"]["unit"], "seconds")
        self.assertEqual(pro_fields["test"]["props"]["unit_hint"], "seconds")
        self.assertNotIn("reference_text", pro_fields["test"]["props"])
        self.assertNotIn("normal_value", pro_fields["test"]["props"])
        self.assertEqual(build_print_reference(pro_fields["test"]["props"]), "10.0 to 13.9 seconds")
        self.assertEqual(pro_fields["inr"]["props"]["normal_min"], "0.70")
        self.assertEqual(pro_fields["inr"]["props"]["normal_max"], "1.30")
        self.assertNotIn("normal_min", pro_fields["control"]["props"])
        self.assertEqual(pro_fields["control"]["props"]["unit_hint"], "seconds")
        self.assertNotIn("reference_text", pro_fields["control"]["props"])
        self.assertNotIn("normal_value", pro_fields["control"]["props"])
        self.assertEqual(pro_fields["activity"]["props"]["unit"], "%")
        self.assertEqual(aptt_fields["test"]["props"]["normal_min"], "22.2")
        self.assertEqual(aptt_fields["test"]["props"]["normal_max"], "37.9")
        self.assertEqual(aptt_fields["control"]["props"]["unit"], "seconds")
        self.assertEqual(evaluate_print_abnormal(pro_fields["test"]["props"], "14"), (True, "high"))
        self.assertEqual(evaluate_print_abnormal(aptt_fields["test"]["props"], "37.9"), (False, None))
        self.assertEqual(evaluate_print_abnormal(aptt_fields["control"]["props"], "99"), (False, None))

    def test_print_containers_render_as_depth_aware_document_hierarchy(self) -> None:
        blocks = [
            {
                "id": "section",
                "kind": "container",
                "name": "Level 0",
                "props": {"key": "level_0"},
                "children": [
                    {
                        "id": "group_1",
                        "kind": "container",
                        "name": "Level 1",
                        "props": {"key": "level_1"},
                        "children": [
                            {
                                "id": "group_2",
                                "kind": "container",
                                "name": "Level 2",
                                "props": {"key": "level_2"},
                                "children": [
                                    {
                                        "id": "group_3",
                                        "kind": "container",
                                        "name": "Level 3",
                                        "props": {"key": "level_3"},
                                        "children": [
                                            {
                                                "id": "result",
                                                "kind": "field",
                                                "name": "Result",
                                                "props": {"key": "result", "data_type": "text"},
                                                "children": [],
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
        items = build_print_items(
            blocks,
            values={},
            asset_by_field={},
            record_id=1,
            print_config={
                "show_top_level_container_titles": True,
                "show_nested_container_titles": True,
            },
        )
        self.assertEqual(items[0]["container_depth"], 0)
        self.assertEqual(items[0]["items"][0]["container_depth"], 1)
        self.assertEqual(items[0]["items"][0]["items"][0]["container_depth"], 2)
        self.assertEqual(items[0]["items"][0]["items"][0]["items"][0]["container_depth"], 3)

        environment = Environment(loader=FileSystemLoader(str(ROOT / "app" / "naic_builder" / "templates")))
        rendered = environment.get_template("records/_print_document.html").module.render_print_items(items)
        self.assertIn('print-section print-container-depth-0 has-title', rendered)
        self.assertIn('print-group print-container-depth-1 has-title', rendered)
        self.assertIn('print-group print-container-depth-2 has-title', rendered)
        self.assertIn('print-group print-container-depth-3 is-deep has-title', rendered)

        print_css = (ROOT / "app" / "naic_builder" / "static" / "print.css").read_text(encoding="utf-8")
        self.assertNotIn(".print-group.has-title {", print_css)
        self.assertNotIn(".print-group.is-deep.has-title {", print_css)

    def test_blood_bank_seed_uses_approved_container_names(self) -> None:
        schema = json.loads(
            (ROOT / "artifacts" / "schema" / "naic_medtech_app_schema.json").read_text(encoding="utf-8")
        )
        blood_bank = next(
            form
            for group in schema["groups"]
            for form in group["forms"]
            if form["key"] == "blood_bank"
        )

        block_schema = build_block_storage_document_from_legacy_storage(blood_bank)
        containers = [block for block in block_schema["blocks"] if block["kind"] == "container"]
        self.assertEqual(
            [container["name"] for container in containers],
            ["Patient Information", "Blood Bank Details", "Crossmatching Details"],
        )
        patient_info = containers[0]
        patient_fields = {child["props"]["key"]: child for child in patient_info["children"]}
        self.assertEqual(patient_fields["age"]["props"]["data_type"], "number")
        self.assertEqual(patient_fields["date_or_datetime"]["name"], "Date & Time")
        self.assertEqual(patient_fields["date_or_datetime"]["props"]["data_type"], "datetime")
        self.assertEqual(patient_fields["case_number"]["props"]["data_type"], "number")
        self.assertTrue(patient_fields["case_number"]["props"]["required"])
        crossmatching = containers[-1]
        self.assertTrue(ensure_default_blood_bank_layout(block_schema))
        crossmatching_fields = [child["props"]["key"] for child in crossmatching["children"]]
        self.assertIn("release_date_time", crossmatching_fields)
        self.assertEqual(
            crossmatching_fields.index("release_date_time"),
            crossmatching_fields.index("released_to") + 1,
        )
        release_date_time = next(
            child for child in crossmatching["children"] if child["props"]["key"] == "release_date_time"
        )
        self.assertEqual(release_date_time["name"], "Date & Time")
        self.assertEqual(release_date_time["props"]["data_type"], "datetime")
        remarks = next(child for child in crossmatching["children"] if child["props"]["key"] == "remarks")
        self.assertEqual(
            evaluate_print_abnormal(remarks["props"], "COMPATIBLE"),
            (False, None),
        )
        self.assertEqual(
            evaluate_print_abnormal(remarks["props"], "INCOMPATIBLE"),
            (True, "abnormal"),
        )
        self.assertEqual(
            next(child["name"] for child in crossmatching["children"] if child["kind"] == "container"),
            "Vital Signs",
        )
        legacy_layout = block_schema["meta"]["print_layout_defaults"]["profiles"]["legacy_landscape:a5"]
        self.assertEqual(
            legacy_layout["containers"]["root:containers:0"]["spans"],
            {
                "root/form.blood_bank.patient_information": 6,
                "root/form.blood_bank.details": 2,
                "root/form.blood_bank.type_of_crossmatching": 4,
            },
        )
        crossmatching_layout = legacy_layout["blocks"]["root/form.blood_bank.type_of_crossmatching:blocks:0"]
        self.assertLess(
            crossmatching_layout["order"].index(
                "root/form.blood_bank.type_of_crossmatching/form.blood_bank.type_of_crossmatching.vital_signs"
            ),
            crossmatching_layout["order"].index("form.blood_bank.type_of_crossmatching.remarks"),
        )
        legacy_layout["grids"]["root/form.blood_bank.patient_information:0"]["spans"][
            "form.blood_bank.patient_information.name"
        ] = 6
        self.assertFalse(ensure_default_blood_bank_layout(block_schema))
        self.assertEqual(
            legacy_layout["grids"]["root/form.blood_bank.patient_information:0"]["spans"][
                "form.blood_bank.patient_information.name"
            ],
            6,
        )

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
        self.assertEqual(printed[0]["kind"], "block_run")
        self.assertEqual([item["kind"] for item in printed[0]["items"]], ["field", "section"])
        self.assertEqual(
            [item["kind"] for item in printed[0]["default_items"]],
            ["field_run", "section"],
        )
        self.assertEqual(printed[0]["default_items"][0]["items"][0]["kind"], "field")
        self.assertEqual(printed[0]["items"][1]["items"][0]["kind"], "group")

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

    def test_print_header_text_color_applies_one_override_to_the_colored_header(self) -> None:
        automatic = normalize_print_config({"accent_color": "#cc3399"})
        self.assertEqual(automatic["header_text_color"], "auto")
        self.assertEqual(print_header_text_color(automatic), "#ffffff")

        black = normalize_print_config({
            "accent_color": "#cc3399",
            "header_text_color": "black",
        })
        self.assertEqual(black["header_text_color"], "black")
        self.assertEqual(print_header_text_color(black), "#171512")

        white = normalize_print_config({
            "accent_color": "#f4b7d2",
            "header_text_color": "white",
        })
        self.assertEqual(white["header_text_color"], "white")
        self.assertEqual(print_header_text_color(white), "#ffffff")
        self.assertEqual(normalize_print_header_text_color("purple"), "auto")

        builder_source = (ROOT / "app" / "naic_builder" / "static" / "app.js").read_text(encoding="utf-8")
        record_print_source = (ROOT / "app" / "naic_builder" / "templates" / "records" / "print.html").read_text(encoding="utf-8")
        builder_preview_source = (ROOT / "app" / "naic_builder" / "templates" / "forms" / "print_preview.html").read_text(encoding="utf-8")
        stylesheet = (ROOT / "app" / "naic_builder" / "static" / "print.css").read_text(encoding="utf-8")
        self.assertIn('data-bind="print_config.header_text_color"', builder_source)
        self.assertIn('printHeaderTextInk(config)', builder_source)
        self.assertIn('print-header-text-{{ document.print_config.header_text_color', record_print_source)
        self.assertIn('print-header-text-{{ document.print_config.header_text_color', builder_preview_source)
        self.assertIn('color: var(--header-ink);', stylesheet)
        self.assertIn('.print-header-text-black .print-exam-head .print-path', stylesheet)
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
        self.assertEqual(presentation["paper_size"], "a4")

        modern = apply_print_presentation(
            {"density": "compact"},
            template_id="modern_portrait",
            text_size="large",
        )
        self.assertEqual(modern["template_id"], "modern_portrait")
        self.assertEqual(modern["text_size"], "large")
        self.assertEqual(modern["paper_size"], "a4")
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
        self.assertEqual(legacy_profile["paper_size"], "a4")
        modern_landscape = print_presentation_details("modern_landscape")
        self.assertEqual(modern_landscape["style"], "modern")
        self.assertEqual(modern_landscape["orientation_key"], "landscape")
        self.assertEqual(modern_landscape["page_size"], "A4")
        self.assertEqual(modern_landscape["page_width_mm"], 297)
        self.assertEqual(modern_landscape["page_height_mm"], 210)
        self.assertEqual(modern_landscape["field_grid_columns"], 3)
        self.assertEqual(print_presentation_details("modern_portrait")["field_grid_columns"], 2)
        self.assertEqual(normalize_print_paper_size("legal"), "legal")
        self.assertEqual(normalize_print_paper_size("letter"), "letter")
        self.assertEqual(normalize_print_paper_size("a5"), "a5")
        self.assertEqual(normalize_print_paper_size("unknown"), "a4")
        self.assertEqual([option["id"] for option in print_paper_size_options()], ["a4", "legal", "letter", "a5"])
        legal_portrait = print_presentation_details("modern_portrait", paper_size="legal")
        self.assertEqual(legal_portrait["page_size"], "Legal")
        self.assertEqual(legal_portrait["page_width_mm"], 216)
        self.assertEqual(legal_portrait["page_height_mm"], 356)
        legal_landscape = print_presentation_details("legacy_landscape", paper_size="legal")
        self.assertEqual(legal_landscape["page_width_mm"], 356)
        self.assertEqual(legal_landscape["page_height_mm"], 216)
        letter_portrait = print_presentation_details("modern_portrait", paper_size="letter")
        self.assertEqual(letter_portrait["page_size"], "Letter")
        self.assertEqual(letter_portrait["page_width_mm"], 216)
        self.assertEqual(letter_portrait["page_height_mm"], 279)
        letter_landscape = print_presentation_details("legacy_landscape", paper_size="letter")
        self.assertEqual(letter_landscape["page_width_mm"], 279)
        self.assertEqual(letter_landscape["page_height_mm"], 216)
        a5_portrait = print_presentation_details("modern_portrait", paper_size="a5")
        self.assertEqual(a5_portrait["page_size"], "A5")
        self.assertEqual(a5_portrait["page_width_mm"], 148)
        self.assertEqual(a5_portrait["page_height_mm"], 210)
        a5_landscape = print_presentation_details("legacy_landscape", paper_size="a5")
        self.assertEqual(a5_landscape["page_width_mm"], 210)
        self.assertEqual(a5_landscape["page_height_mm"], 148)
        self.assertTrue(a5_landscape["requires_one_page"])
        self.assertEqual([option["id"] for option in a5_landscape["text_size_options"]], ["standard"])
        legacy_a5_profile = normalize_print_profile(
            template_id="legacy_landscape",
            text_size="large",
            paper_size="a5",
        )
        self.assertEqual(legacy_a5_profile["text_size"], "standard")
        legacy_a5_fit = estimate_print_page_fit({
            "print_config": {
                "template_id": "legacy_landscape",
                "text_size": "standard",
                "paper_size": "a5",
            },
            "items": [],
        })
        self.assertTrue(legacy_a5_fit["requires_one_page"])
        self.assertTrue(legacy_a5_fit["can_print"])
        oversized_legacy_a5_fit = estimate_print_page_fit({
            "print_config": {
                "template_id": "legacy_landscape",
                "text_size": "standard",
                "paper_size": "a5",
            },
            "items": [{"kind": "field", "display": {}} for _ in range(40)],
        })
        self.assertEqual(oversized_legacy_a5_fit["status"], "long")
        self.assertTrue(oversized_legacy_a5_fit["can_print"])
        crowded_legacy_a5_fit = estimate_print_page_fit({
            "print_config": {
                "template_id": "legacy_landscape",
                "text_size": "standard",
                "paper_size": "a5",
            },
            "items": [{"kind": "field", "display": {}} for _ in range(20)],
        })
        self.assertEqual(crowded_legacy_a5_fit["status"], "long")
        self.assertGreater(
            print_page_fit_limit_units(normalize_print_profile(template_id="modern_portrait", paper_size="legal")),
            print_page_fit_limit_units(normalize_print_profile(template_id="modern_portrait", paper_size="a4")),
        )
        self.assertLess(
            print_page_fit_limit_units(normalize_print_profile(template_id="modern_portrait", paper_size="a5")),
            print_page_fit_limit_units(normalize_print_profile(template_id="modern_portrait", paper_size="letter")),
        )
        self.assertLess(
            print_page_fit_limit_units(normalize_print_profile(template_id="modern_landscape", paper_size="a5")),
            print_page_fit_limit_units(normalize_print_profile(template_id="modern_landscape", paper_size="a4")),
        )
        self.assertLess(
            print_page_fit_limit_units(normalize_print_profile(template_id="modern_portrait", paper_size="letter")),
            print_page_fit_limit_units(normalize_print_profile(template_id="modern_portrait", paper_size="a4")),
        )
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
            self.assertEqual(user.print_paper_size, "a4")

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
            saved = save_user_print_preferences(
                session,
                user,
                template_id="legacy_landscape",
                text_size="large",
                paper_size="legal",
            )
            self.assertEqual(saved["paper_size"], "legal")
            session.refresh(user)
            self.assertEqual(user.print_template_id, "legacy_landscape")
            self.assertEqual(user.print_text_size, "large")
            self.assertEqual(user.print_paper_size, "legal")

            saved = save_user_print_preferences(
                session,
                user,
                template_id="classic_portrait",
                text_size="standard",
            )
            self.assertEqual(saved["template_id"], "classic_portrait")
            self.assertEqual(saved["text_size"], "standard")
            self.assertEqual(saved["paper_size"], "legal")
            session.refresh(user)
            self.assertEqual(user.print_paper_size, "legal")

            saved = save_user_print_preferences(
                session,
                user,
                template_id="classic_portrait",
                text_size="standard",
                paper_size="letter",
            )
            self.assertEqual(saved["paper_size"], "letter")
            session.refresh(user)
            self.assertEqual(user.print_paper_size, "letter")

            saved = save_user_print_preferences(
                session,
                user,
                template_id="classic_portrait",
                text_size="standard",
                paper_size="a5",
            )
            self.assertEqual(saved["paper_size"], "a5")
            session.refresh(user)
            self.assertEqual(user.print_paper_size, "a5")

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
        self.assertIn("print_paper_size_options", source)
        self.assertIn('name="paper_size"', source)
        self.assertIn('name="set_default"', source)
        self.assertIn("data-print-settings-dialog", source)
        self.assertIn("data-open-print-settings", source)
        self.assertNotIn('name="set_paper_default"', source)
        self.assertIn("presentation.page_css_size", source)
        self.assertIn("presentation.page_width_mm", source)
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
        row_name_at = html.index('<strong>PULSE RATE</strong>')
        row_result_at = html.index('class="print-answer">-2')
        row_reference_at = html.index("Normal values: 60 - 100")
        self.assertLess(row_name_at, row_result_at)
        self.assertLess(row_result_at, row_reference_at)
        grid_result_at = html.index('class="print-answer">4')
        grid_reference_at = html.index("Normal values: 60 - 100", grid_result_at)
        self.assertLess(grid_result_at, grid_reference_at)
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

    def test_print_grid_completes_partial_rows_with_structural_cells(self) -> None:
        environment = Environment(loader=FileSystemLoader(ROOT / "app" / "naic_builder" / "templates"))
        macro = environment.get_template("records/_print_document.html").module.render_print_page
        field = {
            "kind": "field",
            "name": "Field",
            "unit_hint": "",
            "reference_text": "",
            "display": {"kind": "text", "text": "Value"},
            "is_abnormal": False,
        }
        html = macro({
            "items": [{"kind": "field_grid", "items": [field] * 7}],
            "clinic": {},
            "template": {"field_grid_columns": 3},
            "print_config": {
                "show_logo": False,
                "show_clinic_info": False,
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
        self.assertEqual(html.count('class="print-grid-cell print-grid-cell--placeholder"'), 2)
        self.assertEqual(html.count('aria-hidden="true"'), 2)

    def test_print_grid_layout_modes_keep_or_balance_trailing_cells(self) -> None:
        field_ids = [f"field_{index}" for index in range(7)]
        items = [{
            "kind": "field_grid",
            "id": "root/container:0",
            "field_ids": field_ids,
            "items": [],
        }]

        apply_print_layout_preference(items, {}, field_grid_units=6)
        preserved = items[0]["layout"]
        self.assertEqual(preserved["mode"], "preserve")
        self.assertEqual(preserved["spans"]["field_6"], 2)
        self.assertEqual(preserved["placeholder_spans"], [2, 2])

        preference = normalize_print_layout_preference({
            "grids": {
                "root/container:0": {
                    "field_ids": field_ids,
                    "mode": "balance",
                }
            }
        })
        apply_print_layout_preference(items, preference, field_grid_units=6)
        balanced = items[0]["layout"]
        self.assertEqual(balanced["mode"], "balance")
        self.assertEqual(balanced["spans"]["field_6"], 6)
        self.assertEqual(balanced["placeholder_spans"], [])

    def test_manual_print_grid_widths_are_profile_safe(self) -> None:
        field_ids = ["name", "age", "sex", "collected_at", "examination", "requesting"]
        items = [{
            "kind": "field_grid",
            "id": "root/patient_information:0",
            "field_ids": field_ids,
            "items": [],
        }]
        raw_preference = {
            "grids": {
                "root/patient_information:0": {
                    "field_ids": field_ids,
                    "mode": "manual",
                    "spans": {"name": 4, "age": 2, "sex": 2},
                }
            }
        }
        safe_preference = filter_print_layout_preference_for_items(
            raw_preference,
            items,
            field_grid_units=6,
        )
        apply_print_layout_preference(items, safe_preference, field_grid_units=6)
        layout = items[0]["layout"]
        self.assertEqual(layout["mode"], "manual")
        self.assertEqual(layout["spans"]["name"], 4)
        self.assertEqual(layout["spans"]["age"], 2)

        changed_items = [{
            "kind": "field_grid",
            "id": "root/patient_information:0",
            "field_ids": ["name", "age", "sex", "new_field"],
            "items": [],
        }]
        apply_print_layout_preference(changed_items, safe_preference, field_grid_units=6)
        self.assertEqual(changed_items[0]["layout"]["mode"], "preserve")

    def test_short_field_runs_keep_rows_until_a_user_arranges_them_as_a_grid(self) -> None:
        blocks = [
            {
                "kind": "field",
                "id": field_id,
                "name": field_id.replace("_", " ").title(),
                "props": {"data_type": "text"},
            }
            for field_id in ("case_number", "requesting_physician", "room")
        ]
        items = build_print_items(
            blocks,
            {},
            {},
            record_id=1,
            print_config={"result_layout": "rows"},
        )

        self.assertEqual(items[0]["kind"], "field_run")
        self.assertEqual(items[0]["id"], "root:run:0")
        self.assertEqual(items[0]["field_ids"], ["case_number", "requesting_physician", "room"])

        apply_print_layout_preference(items, {}, field_grid_units=6)
        self.assertEqual(items[0]["layout"]["mode"], "rows")
        self.assertEqual(items[0]["layout"]["presentation"], "rows")

        preference = {
            "grids": {
                "root:run:0": {
                    "field_ids": ["case_number", "requesting_physician", "room"],
                    "mode": "manual",
                    "spans": {"case_number": 4, "requesting_physician": 2, "room": 6},
                }
            }
        }
        safe_preference = filter_print_layout_preference_for_items(
            preference,
            items,
            field_grid_units=6,
        )
        apply_print_layout_preference(items, safe_preference, field_grid_units=6)
        self.assertEqual(items[0]["layout"]["mode"], "manual")
        self.assertEqual(items[0]["layout"]["presentation"], "grid")
        self.assertEqual(items[0]["layout"]["spans"]["case_number"], 4)

        changed_items = [{
            "kind": "field_run",
            "id": "root:run:0",
            "field_ids": ["case_number", "requesting_physician", "new_field"],
            "items": [],
        }]
        apply_print_layout_preference(changed_items, safe_preference, field_grid_units=6)
        self.assertEqual(changed_items[0]["layout"]["mode"], "rows")
        self.assertEqual(changed_items[0]["layout"]["presentation"], "rows")

    def test_uploaded_image_field_uses_a_selectable_standalone_field_run(self) -> None:
        blocks = [{
            "kind": "field",
            "id": "result_image",
            "name": "Result Image",
            "props": {"data_type": "image"},
        }]
        items = build_print_items(
            blocks,
            values={"result_image": {"asset_id": 7}},
            asset_by_field={"result_image": {"id": 7, "original_filename": "result.png"}},
            record_id=1,
        )

        self.assertEqual(items[0]["kind"], "field_run")
        self.assertEqual(items[0]["id"], "root:field:result_image")
        self.assertEqual(items[0]["field_ids"], ["result_image"])

        preference = {
            "grids": {
                "root:field:result_image": {
                    "field_ids": ["result_image"],
                    "mode": "manual",
                    "spans": {"result_image": 4},
                }
            }
        }
        apply_print_layout_preference(items, preference, field_grid_units=4)
        self.assertEqual(items[0]["layout"]["presentation"], "grid")
        self.assertEqual(items[0]["layout"]["spans"]["result_image"], 4)

        environment = Environment(loader=FileSystemLoader(ROOT / "app" / "naic_builder" / "templates"))
        rendered = environment.get_template("records/_print_document.html").module.render_print_items(items)
        self.assertIn('data-print-layout-grid', rendered)
        self.assertIn('data-print-grid-cell data-field-id="result_image"', rendered)
        self.assertIn('class="print-result-image"', rendered)
        self.assertIn('class="print-image', rendered)

    def test_record_image_editor_uses_async_auto_upload_controls(self) -> None:
        editor_template = (ROOT / "app" / "naic_builder" / "templates" / "records" / "edit.html").read_text(encoding="utf-8")
        records_source = (ROOT / "app" / "naic_builder" / "static" / "records.js").read_text(encoding="utf-8")

        self.assertIn("data-record-image-upload", editor_template)
        self.assertIn("data-record-image-remove", editor_template)
        self.assertNotIn(">Upload image</button>", editor_template)
        self.assertIn("setupRecordImageUploads", records_source)
        self.assertIn("`/api/records/${recordId}/assets`", records_source)
        self.assertIn('method: "DELETE"', records_source)
        self.assertIn('target.matches("[data-record-image-upload]")', records_source)
        self.assertIn("asset_by_field_id", records_source)

    def test_print_page_keeps_a_live_one_page_fit_check_after_layout_adjustments(self) -> None:
        print_template = (ROOT / "app" / "naic_builder" / "templates" / "records" / "print.html").read_text(encoding="utf-8")

        self.assertIn("data-print-fit-status", print_template)
        self.assertIn("renderPrintFitEstimate", print_template)
        self.assertIn("schedulePrintFitCheck", print_template)
        self.assertIn('likely: "Likely 1 page"', print_template)
        self.assertIn('long: "Likely 2 pages"', print_template)
        self.assertIn('data-print-profile', print_template)
        self.assertIn('print-page-viewport', print_template)
        self.assertNotIn('{{ document.record_key }}', print_template)
        self.assertIn("data-print-action", print_template)
        self.assertIn('data-print-action onclick="window.print()"', print_template)
        self.assertNotIn("data-print-action{% if not fit.can_print %}", print_template)

    def test_field_run_template_preserves_rows_until_grid_presentation_is_selected(self) -> None:
        environment = Environment(loader=FileSystemLoader(ROOT / "app" / "naic_builder" / "templates"))
        macro = environment.get_template("records/_print_document.html").module.render_print_page
        field = {
            "id": "case_number",
            "name": "CASE NUMBER",
            "unit_hint": "",
            "reference_text": "",
            "display": {"kind": "text", "text": "1"},
            "is_abnormal": False,
        }
        document = {
            "items": [{
                "kind": "field_run",
                "id": "root:run:0",
                "items": [field],
                "layout": {
                    "id": "root:run:0",
                    "mode": "rows",
                    "presentation": "rows",
                    "units": 4,
                    "spans": {"case_number": 2},
                },
            }],
            "clinic": {},
            "template": {"field_grid_columns": 2},
            "print_config": {
                "show_logo": False,
                "show_clinic_info": False,
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
        }

        row_html = macro(document)
        self.assertIn('class="print-field-run"', row_html)
        self.assertNotIn('class="print-field-run print-layout-grid"', row_html)
        self.assertIn('data-layout-presentation="rows"', row_html)

        document["items"][0]["layout"].update({
            "mode": "manual",
            "presentation": "grid",
            "placeholder_spans": [2],
        })
        grid_html = macro(document)
        self.assertIn('class="print-field-run print-layout-grid"', grid_html)
        self.assertIn('class="print-row print-field-run-placeholder"', grid_html)

    def test_adjacent_containers_are_a_flow_first_layout_group(self) -> None:
        items = [{
            "kind": "container_run",
            "id": "root:containers:0",
            "container_ids": ["root/patient_information", "root/blood_bank_details"],
            "items": [],
        }]

        apply_print_layout_preference(items, {}, field_grid_units=6)
        self.assertEqual(items[0]["layout"]["mode"], "flow")
        self.assertEqual(items[0]["layout"]["presentation"], "flow")

        preference = {
            "containers": {
                "root:containers:0": {
                    "container_ids": ["root/patient_information", "root/blood_bank_details"],
                    "mode": "manual",
                    "spans": {
                        "root/patient_information": 3,
                        "root/blood_bank_details": 3,
                    },
                }
            }
        }
        safe_preference = filter_print_layout_preference_for_items(
            preference,
            items,
            field_grid_units=6,
        )
        self.assertEqual(safe_preference["containers"]["root:containers:0"]["mode"], "manual")
        apply_print_layout_preference(items, safe_preference, field_grid_units=6)
        self.assertEqual(items[0]["layout"]["presentation"], "grid")
        self.assertEqual(items[0]["layout"]["spans"]["root/patient_information"], 3)

        changed_items = [{
            "kind": "container_run",
            "id": "root:containers:0",
            "container_ids": ["root/patient_information", "root/new_details"],
            "items": [],
        }]
        apply_print_layout_preference(changed_items, safe_preference, field_grid_units=6)
        self.assertEqual(changed_items[0]["layout"]["mode"], "flow")

    def test_print_layout_order_is_saved_without_forcing_a_row_group_into_grid_mode(self) -> None:
        items = [{
            "kind": "field_run",
            "id": "root:run:0",
            "field_ids": ["case_number", "requesting_physician", "room"],
            "items": [
                {"kind": "field", "id": "case_number"},
                {"kind": "field", "id": "requesting_physician"},
                {"kind": "field", "id": "room"},
            ],
        }]
        preference = {
            "grids": {
                "root:run:0": {
                    "field_ids": ["case_number", "requesting_physician", "room"],
                    "mode": "rows",
                    "order": ["room", "case_number", "requesting_physician"],
                }
            }
        }

        safe_preference = filter_print_layout_preference_for_items(
            preference,
            items,
            field_grid_units=4,
        )
        self.assertEqual(
            safe_preference["grids"]["root:run:0"]["order"],
            ["room", "case_number", "requesting_physician"],
        )
        apply_print_layout_preference(items, safe_preference, field_grid_units=4)
        self.assertEqual(items[0]["layout"]["mode"], "rows")
        self.assertEqual(
            [item["id"] for item in items[0]["items"]],
            ["room", "case_number", "requesting_physician"],
        )
        self.assertEqual(
            [item["_print_layout_original_index"] for item in items[0]["items"]],
            [2, 0, 1],
        )

    def test_container_run_template_stacks_by_default_and_supports_grid_presentation(self) -> None:
        environment = Environment(loader=FileSystemLoader(ROOT / "app" / "naic_builder" / "templates"))
        macro = environment.get_template("records/_print_document.html").module.render_print_page
        document = {
            "items": [{
                "kind": "container_run",
                "id": "root:containers:0",
                "items": [
                    {
                        "kind": "section",
                        "id": "root/patient_information",
                        "name": "PATIENT INFORMATION",
                        "container_depth": 0,
                        "show_title": True,
                        "items": [],
                    },
                    {
                        "kind": "section",
                        "id": "root/blood_bank_details",
                        "name": "BLOOD BANK DETAILS",
                        "container_depth": 0,
                        "show_title": True,
                        "items": [],
                    },
                ],
                "layout": {
                    "id": "root:containers:0",
                    "mode": "flow",
                    "presentation": "flow",
                    "units": 4,
                    "spans": {},
                },
            }],
            "clinic": {},
            "template": {"field_grid_columns": 2},
            "print_config": {
                "show_logo": False,
                "show_clinic_info": False,
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
        }

        flow_html = macro(document)
        self.assertIn('class="print-container-run"', flow_html)
        self.assertNotIn('class="print-container-run print-layout-grid"', flow_html)
        self.assertIn('data-layout-presentation="flow"', flow_html)

        document["items"][0]["layout"].update({
            "mode": "manual",
            "presentation": "grid",
            "spans": {
                "root/patient_information": 2,
                "root/blood_bank_details": 2,
            },
        })
        grid_html = macro(document)
        self.assertIn('class="print-container-run print-layout-grid"', grid_html)
        self.assertEqual(grid_html.count('data-container-id="root/'), 2)

        editor_source = (ROOT / "app" / "naic_builder" / "templates" / "records" / "print.html").read_text(encoding="utf-8")
        stylesheet = (ROOT / "app" / "naic_builder" / "static" / "print.css").read_text(encoding="utf-8")
        self.assertIn("cell.dataset.containerId", editor_source)
        self.assertIn("containers[gridId]", editor_source)
        self.assertIn(".print-container-run.print-layout-grid", stylesheet)

    def test_mixed_print_blocks_make_a_nested_container_independently_layoutable(self) -> None:
        def field(field_id: str, name: str) -> dict[str, object]:
            return {
                "kind": "field",
                "id": field_id,
                "name": name,
                "props": {"data_type": "text"},
            }

        items = build_print_items(
            [{
                "kind": "container",
                "id": "crossmatching",
                "name": "Crossmatching Details",
                "children": [
                    field("immediate_spin", "Immediate Spin"),
                    field("albumin", "Albumin"),
                    field("anti_human", "Anti Human Globulin"),
                    field("remarks", "Remarks"),
                    {
                        "kind": "container",
                        "id": "vital_signs",
                        "name": "Vital Signs",
                        "children": [
                            field("blood_pressure", "Blood Pressure"),
                            field("pulse_rate", "Pulse Rate"),
                        ],
                    },
                    field("released_by", "Released By"),
                    field("released_to", "Released To"),
                ],
            }],
            values={},
            asset_by_field={},
            record_id=1,
            print_config={"result_layout": "compact_grid"},
        )

        crossmatching = items[0]
        block_run = crossmatching["items"][0]
        self.assertEqual(crossmatching["kind"], "section")
        self.assertEqual(block_run["kind"], "block_run")
        self.assertEqual(
            [item["kind"] for item in block_run["items"]],
            ["field", "field", "field", "field", "group", "field", "field"],
        )
        self.assertEqual(
            [item["kind"] for item in block_run["default_items"]],
            ["field_grid", "group", "field_run"],
        )
        immediate_spin = block_run["items"][0]
        vital_signs = block_run["items"][4]
        self.assertEqual(vital_signs["name"], "Vital Signs")

        environment = Environment(loader=FileSystemLoader(ROOT / "app" / "naic_builder" / "templates"))
        default_rendered = environment.get_template("records/_print_document.html").module.render_print_items(items)
        self.assertIn('class="print-block-run-default"', default_rendered)
        self.assertIn('class="print-field-grid print-layout-grid"', default_rendered)
        self.assertNotIn('is-layout-run-custom', default_rendered)

        reordered_block_ids = [
            immediate_spin["id"],
            vital_signs["id"],
            *[
                block_id
                for block_id in block_run["block_ids"]
                if block_id not in {immediate_spin["id"], vital_signs["id"]}
            ],
        ]
        preference = {
            "blocks": {
                block_run["id"]: {
                    "block_ids": reordered_block_ids,
                    "mode": "manual",
                    "spans": {
                        immediate_spin["id"]: 4,
                        vital_signs["id"]: 2,
                    },
                    "order": reordered_block_ids,
                }
            }
        }
        safe_preference = filter_print_layout_preference_for_items(
            preference,
            items,
            field_grid_units=4,
        )
        self.assertEqual(safe_preference["blocks"][block_run["id"]]["mode"], "manual")

        apply_print_layout_preference(items, safe_preference, field_grid_units=4)
        layout = block_run["layout"]
        self.assertEqual(layout["presentation"], "grid")
        self.assertEqual(layout["spans"][immediate_spin["id"]], 4)
        self.assertEqual(block_run["items"][0]["id"], immediate_spin["id"])
        self.assertEqual(block_run["items"][1]["id"], vital_signs["id"])

        rendered = environment.get_template("records/_print_document.html").module.render_print_items(items)
        self.assertIn('data-layout-kind="block_run"', rendered)
        self.assertIn('is-layout-run-custom', rendered)
        self.assertIn(f'data-layout-item-id="{immediate_spin["id"]}"', rendered)
        self.assertIn(f'data-block-id="{vital_signs["id"]}"', rendered)
        self.assertIn('class="print-layout-move-handle"', rendered)

    def test_print_layout_editor_uses_explicit_modes_and_scopes_to_direct_children(self) -> None:
        editor_source = (
            ROOT / "app" / "naic_builder" / "templates" / "records" / "print.html"
        ).read_text(encoding="utf-8")

        self.assertIn('data-layout-flow', editor_source)
        self.assertIn('data-layout-grid', editor_source)
        self.assertIn('Reset selection', editor_source)
        self.assertIn('Restore form default', editor_source)
        self.assertIn('Save layout', editor_source)
        self.assertIn('data-layout-restore-form title="Remove this record setup and use the form-version default"{% if not record_has_print_presentation %} hidden{% endif %}', editor_source)
        self.assertIn('restoreFormDefaultButton.hidden = false;', editor_source)
        self.assertIn('const directGridCellFromElement = (grid, element) => {', editor_source)
        self.assertIn('cell.parentElement?.closest("[data-print-grid-cell]") || null;', editor_source)
        self.assertNotIn('data-layout-arrange', editor_source)
        self.assertNotIn('data-layout-balance', editor_source)
        self.assertIn('querySelectorAll(":scope > [data-print-grid-cell]")', editor_source)
        self.assertIn('cell.closest("[data-print-layout-grid]") !== grid', editor_source)
        self.assertIn('defaultGridMode(activeLayoutGrid)', editor_source)
        self.assertIn('const blockIds', editor_source)
        self.assertIn('blocks[gridId]', editor_source)
        self.assertIn('data-layout-move-handle', editor_source)
        self.assertIn('setMoveDropIndicator', editor_source)
        self.assertIn('clearMoveDropIndicator', editor_source)
        self.assertIn('data-layout-undo', editor_source)
        self.assertIn('data-layout-redo', editor_source)
        self.assertIn('recordLayoutHistory', editor_source)
        self.assertIn('restoreLayoutHistorySnapshot', editor_source)
        self.assertIn('layoutHistory.length > 31', editor_source)
        self.assertIn('key === "z"', editor_source)
        self.assertIn('activateBlockRunItem', editor_source)
        self.assertIn('const syncResponsiveFieldRunCell = (cell) => {', editor_source)
        self.assertIn('new ResizeObserver((entries) => {', editor_source)
        self.assertIn('cell.getBoundingClientRect().width < 296', editor_source)
        self.assertIn(
            ".print-container-run.print-layout-grid,\n.print-block-run-grid.print-layout-grid {\n  display: grid;",
            (ROOT / "app" / "naic_builder" / "static" / "print.css").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "body.is-layout-editing .print-container-run.print-layout-grid > .print-container-run-item",
            (ROOT / "app" / "naic_builder" / "static" / "print.css").read_text(encoding="utf-8"),
        )
        self.assertIn(
            ".print-container-run.print-layout-grid {\n  background: var(--paper);",
            (ROOT / "app" / "naic_builder" / "static" / "print.css").read_text(encoding="utf-8"),
        )
        self.assertIn(
            ".print-block-run-grid.print-layout-grid {\n  gap: 0;\n  background: var(--paper);",
            (ROOT / "app" / "naic_builder" / "static" / "print.css").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "outline: 1px solid var(--line-soft);",
            (ROOT / "app" / "naic_builder" / "static" / "print.css").read_text(encoding="utf-8"),
        )
        self.assertIn(
            'is-layout-drop-before-row',
            (ROOT / "app" / "naic_builder" / "static" / "print.css").read_text(encoding="utf-8"),
        )
        self.assertIn(
            'is-layout-drop-after-column',
            (ROOT / "app" / "naic_builder" / "static" / "print.css").read_text(encoding="utf-8"),
        )
        self.assertIn(
            '.print-field-run.print-layout-grid > .print-row.is-layout-cell-compact',
            (ROOT / "app" / "naic_builder" / "static" / "print.css").read_text(encoding="utf-8"),
        )
        self.assertNotIn(
            ".print-font-times-new-roman .print-group-title,",
            (ROOT / "app" / "naic_builder" / "static" / "print.css").read_text(encoding="utf-8"),
        )

    def test_print_command_ui_uses_a_fixed_application_accent(self) -> None:
        print_page = (ROOT / "app" / "naic_builder" / "templates" / "records" / "print.html").read_text(encoding="utf-8")
        stylesheet = (ROOT / "app" / "naic_builder" / "static" / "print.css").read_text(encoding="utf-8")

        self.assertIn('--ui-accent: #252a2f;', stylesheet)
        self.assertIn('.print-button {\n  color: var(--ui-accent-ink);\n  background: var(--ui-accent);', stylesheet)
        self.assertIn('.print-active-profile strong {\n  color: var(--ui-accent);', stylesheet)
        self.assertIn('class="print-command-back" href="{{ back_href }}" aria-label="{{ back_label }}" title="{{ back_label }}"', print_page)
        self.assertIn('<span aria-hidden="true">&larr;</span>', print_page)

    def test_builder_accordions_start_closed_and_keep_their_open_state(self) -> None:
        builder_source = (ROOT / "app" / "naic_builder" / "static" / "app.js").read_text(encoding="utf-8")
        library_source = (ROOT / "app" / "naic_builder" / "templates" / "forms" / "library.html").read_text(encoding="utf-8")
        library_script = (ROOT / "app" / "naic_builder" / "static" / "library.js").read_text(encoding="utf-8")

        self.assertIn("openBuilderDetails: {},", builder_source)
        self.assertIn("function setBuilderDetailsOpen(key, open)", builder_source)
        self.assertIn('data-builder-details-key="${escapeHtml(normalizedKey)}"', builder_source)
        self.assertIn("setBuilderDetailsOpen(builderDetailsToken, details.open);", builder_source)
        self.assertIn('builderDetailsKey("signatory", slot.id)', builder_source)
        self.assertIn('builderDetailsKey("print-default-layout")', builder_source)
        self.assertIn('builderDetailsKey("print-header-style")', builder_source)
        self.assertNotIn('<details class="print-settings-section" open>', builder_source)
        self.assertIn('data-default-open="false"', library_source)
        self.assertNotIn('{% if level == 0 %}open{% endif %}', library_source)
        self.assertIn("related.open = true;", library_script)

    def test_shared_shell_owns_topbar_and_drawer_surface_geometry(self) -> None:
        shell_template = (ROOT / "app" / "naic_builder" / "templates" / "_authenticated_shell.html").read_text(encoding="utf-8")
        shell_stylesheet = (ROOT / "app" / "naic_builder" / "static" / "shell.css").read_text(encoding="utf-8")
        theme_stylesheet = (ROOT / "app" / "naic_builder" / "static" / "theme.css").read_text(encoding="utf-8")
        overview_page = (ROOT / "app" / "naic_builder" / "templates" / "overview.html").read_text(encoding="utf-8")

        self.assertIn("overflow: auto;\n  border-radius: var(--radius-xl);", shell_stylesheet)
        self.assertIn("padding: 8px 12px;\n  border-radius: var(--radius-xl);", shell_stylesheet)
        self.assertIn("*::before,\n*::after {\n  box-sizing: border-box;", theme_stylesheet)
        self.assertIn("body {\n  margin: 0;", theme_stylesheet)
        self.assertIn("theme.css') }}?v=20260801-shared-layout-foundation", shell_template)
        self.assertIn("shell.css') }}?v=20260801-clinic-logo-plain", shell_template)
        self.assertIn("app-drawer__brand-mark--logo", shell_template)
        self.assertIn("app-global-header__brand--logo", shell_template)
        self.assertIn(".app-global-header__brand--logo", shell_stylesheet)
        self.assertNotIn("library.css", overview_page)

    def test_overview_recent_updates_are_creator_attributed_and_timezone_free(self) -> None:
        overview_page = (ROOT / "app" / "naic_builder" / "templates" / "overview.html").read_text(encoding="utf-8")
        overview_stylesheet = (ROOT / "app" / "naic_builder" / "static" / "overview.css").read_text(encoding="utf-8")
        label = format_compact_timestamp_label(datetime(2026, 7, 31, 10, 15, tzinfo=timezone.utc))

        self.assertRegex(label, r"^[A-Z][a-z]{2} \d{2}, \d{2}:\d{2} [AP]M$")
        self.assertIn("Created by {{ record.overview_creator_name }}", overview_page)
        self.assertIn("Updated {{ record.overview_updated_at_label }}", overview_page)
        self.assertNotIn("overview-recent-row__time", overview_page)
        self.assertNotIn("overview-recent-row__dot", overview_page)
        self.assertIn("grid-template-columns: minmax(0, 1fr);", overview_stylesheet)

    def test_overview_is_available_to_authenticated_medtech_users(self) -> None:
        main_source = (ROOT / "app" / "naic_builder" / "main.py").read_text(encoding="utf-8")
        shell_template = (ROOT / "app" / "naic_builder" / "templates" / "_authenticated_shell.html").read_text(encoding="utf-8")
        drawer_nav = shell_template.split('<nav class="app-drawer__nav" aria-label="Primary">', 1)[1].split("</nav>", 1)[0]

        self.assertNotIn('ADMIN_PREFIXES = ("/overview",', main_source)
        self.assertLess(drawer_nav.index('href="/overview"'), drawer_nav.index('{% if request.state.is_admin %}'))

    def test_records_management_filters_use_existing_record_timestamps(self) -> None:
        now = datetime(2026, 7, 31, 10, 15, tzinfo=timezone.utc)
        local_now = now.astimezone()
        start_of_today = local_now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)

        self.assertEqual(normalize_record_date_scope("today"), "today")
        self.assertEqual(normalize_record_date_scope("LAST_7_DAYS"), "last_7_days")
        self.assertEqual(normalize_record_date_scope("invalid"), "")
        self.assertEqual(normalize_overview_period("all"), "")
        self.assertEqual(normalize_overview_period("last_7_days"), "last_7_days")
        self.assertEqual(normalize_overview_period("invalid"), "this_month")
        self.assertEqual(record_date_scope_start("today", now=now), start_of_today)
        self.assertEqual(record_date_scope_start("last_7_days", now=now), start_of_today - timedelta(days=6))
        self.assertEqual(record_date_scope_start("this_month", now=now), start_of_today.replace(day=1))

        history_page = (ROOT / "app" / "naic_builder" / "templates" / "records" / "history.html").read_text(encoding="utf-8")
        work_page = (ROOT / "app" / "naic_builder" / "templates" / "records" / "home.html").read_text(encoding="utf-8")
        history_script = (ROOT / "app" / "naic_builder" / "static" / "records.js").read_text(encoding="utf-8")

        self.assertIn('data-history-filter-details', history_page)
        self.assertIn('name="form"', history_page)
        self.assertIn('name="period"', history_page)
        self.assertIn('class="records-work-completed"', work_page)
        self.assertIn("filterDetails?.removeAttribute(\"open\");", history_script)

    def test_user_print_layout_preference_is_personal_and_profile_scoped(self) -> None:
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        try:
            with Session() as session:
                user = User(
                    email="layout@example.test",
                    login_id="layout_user",
                    full_name="Layout User",
                    role="medtech",
                    status="active",
                )
                session.add(user)
                session.commit()
                preference = save_user_print_layout_preference(
                    session,
                    user,
                    form_id=8,
                    template_id="legacy_landscape",
                    paper_size="a5",
                    preference={
                        "grids": {
                            "root/patient:0": {
                                "field_ids": ["name", "age", "sex", "exam"],
                                "mode": "manual",
                                "spans": {"name": 4, "age": 2, "sex": 2, "exam": 2},
                            }
                        },
                        "blocks": {
                            "root/crossmatching:blocks:0": {
                                "block_ids": [
                                    "root/crossmatching:0",
                                    "root/crossmatching/vital_signs",
                                    "root/crossmatching:run:0",
                                ],
                                "mode": "manual",
                                "spans": {
                                    "root/crossmatching:0": 2,
                                    "root/crossmatching/vital_signs": 4,
                                    "root/crossmatching:run:0": 2,
                                },
                            }
                        },
                    },
                )
                self.assertEqual(preference["grids"]["root/patient:0"]["mode"], "manual")
                self.assertEqual(preference["blocks"]["root/crossmatching:blocks:0"]["mode"], "manual")
                session.refresh(user)
                saved = user_print_layout_preference(
                    user,
                    form_id=8,
                    template_id="legacy_landscape",
                    paper_size="a5",
                )
                self.assertEqual(saved["grids"]["root/patient:0"]["spans"]["name"], 4)
                self.assertEqual(
                    saved["blocks"]["root/crossmatching:blocks:0"]["spans"]["root/crossmatching/vital_signs"],
                    4,
                )
                self.assertEqual(
                    user_print_layout_preference(
                        user,
                        form_id=8,
                        template_id="modern_landscape",
                        paper_size="a5",
                    )["grids"],
                    {},
                )
        finally:
            engine.dispose()

    def test_form_layout_defaults_are_versioned_and_completed_records_are_authoritative(self) -> None:
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        try:
            with Session() as session:
                session.info[SKIP_CHANGE_BACKUP_SESSION_KEY] = True
                ensure_reference_seed(session)
                definition = session.scalars(
                    select(FormDefinition).where(FormDefinition.slug == "blood_bank")
                ).one()
                original_version = current_version(definition)
                self.assertIsNotNone(original_version)

                owner = User(
                    email="record-owner@example.test",
                    login_id="record_owner",
                    full_name="Record Owner",
                    role="medtech",
                    status="active",
                )
                admin = User(
                    email="layout-admin@example.test",
                    login_id="layout_admin",
                    full_name="Layout Admin",
                    role="admin",
                    status="active",
                )
                session.add_all([owner, admin])
                session.commit()

                profile = save_user_print_preferences(
                    session,
                    owner,
                    template_id="modern_portrait",
                    text_size="standard",
                    paper_size="a4",
                )
                default_layout = {
                    "containers": {
                        "root:containers:0": {
                            "container_ids": [
                                "root/form.blood_bank.patient_information",
                                "root/form.blood_bank.details",
                                "root/form.blood_bank.type_of_crossmatching",
                            ],
                            "mode": "manual",
                            "spans": {
                                "root/form.blood_bank.patient_information": 4,
                                "root/form.blood_bank.details": 2,
                                "root/form.blood_bank.type_of_crossmatching": 2,
                            },
                        }
                    }
                }
                save_form_print_layout_default(
                    session,
                    definition.slug,
                    profile=profile,
                    layout=default_layout,
                )
                session.expire_all()
                definition = session.scalars(
                    select(FormDefinition).where(FormDefinition.slug == "blood_bank")
                ).one()
                updated_version = current_version(definition)
                self.assertIsNotNone(updated_version)
                self.assertNotEqual(original_version.id, updated_version.id)
                self.assertEqual(
                    form_version_print_layout_preference(
                        original_version,
                        template_id=profile["template_id"],
                        paper_size=profile["paper_size"],
                    )["containers"],
                    {},
                )
                self.assertEqual(
                    form_version_print_layout_preference(
                        updated_version,
                        template_id=profile["template_id"],
                        paper_size=profile["paper_size"],
                    )["containers"]["root:containers:0"]["spans"]["root/form.blood_bank.patient_information"],
                    4,
                )

                old_record = Record(
                    record_key="OLD-LAYOUT-RECORD",
                    form_id=definition.id,
                    form_version_id=original_version.id,
                    created_by_user_id=owner.id,
                    status="completed",
                )
                new_record = Record(
                    record_key="NEW-LAYOUT-RECORD",
                    form_id=definition.id,
                    form_version_id=updated_version.id,
                    created_by_user_id=owner.id,
                    status="completed",
                )
                session.add_all([old_record, new_record])
                session.commit()
                session.refresh(old_record)
                session.refresh(new_record)

                self.assertEqual(
                    effective_record_print_presentation(
                        old_record,
                        fallback_profile=profile,
                    )["source"],
                    "automatic",
                )
                self.assertEqual(
                    effective_record_print_presentation(
                        new_record,
                        fallback_profile=profile,
                    )["source"],
                    "form_default",
                )

                snapshot_completed_record_print_presentation(
                    session,
                    new_record,
                    user=owner,
                )
                session.commit()
                session.refresh(new_record)
                self.assertEqual(new_record.print_presentation.template_id, "modern_portrait")
                self.assertEqual(
                    json.loads(new_record.print_presentation.layout_json)["containers"]["root:containers:0"]["spans"][
                        "root/form.blood_bank.patient_information"
                    ],
                    4,
                )
                self.assertEqual(
                    effective_record_print_presentation(
                        new_record,
                        fallback_profile=profile,
                    )["source"],
                    "record",
                )

                personal_layout = {
                    "grids": {
                        "root/form.blood_bank.patient_information:0": {
                            "field_ids": ["form.blood_bank.patient_information.name"],
                            "mode": "manual",
                            "spans": {"form.blood_bank.patient_information.name": 4},
                        }
                    }
                }
                save_user_print_layout_preference(
                    session,
                    owner,
                    form_id=definition.id,
                    template_id=profile["template_id"],
                    paper_size=profile["paper_size"],
                    preference=personal_layout,
                )
                personal_record = Record(
                    record_key="PERSONAL-LAYOUT-RECORD",
                    form_id=definition.id,
                    form_version_id=updated_version.id,
                    created_by_user_id=owner.id,
                    status="completed",
                )
                session.add(personal_record)
                session.commit()
                snapshot_completed_record_print_presentation(
                    session,
                    personal_record,
                    user=owner,
                )
                session.commit()
                session.refresh(personal_record)
                self.assertEqual(
                    json.loads(personal_record.print_presentation.layout_json),
                    normalize_print_layout_preference(personal_layout),
                )

                record_layout = {
                    "grids": {
                        "root/form.blood_bank.patient_information:0": {
                            "field_ids": ["form.blood_bank.patient_information.name"],
                            "mode": "manual",
                            "spans": {"form.blood_bank.patient_information.name": 4},
                        }
                    }
                }
                saved = save_record_print_presentation(
                    session,
                    old_record,
                    user=owner,
                    profile=normalize_print_profile(
                        template_id="legacy_landscape",
                        text_size="large",
                        paper_size="a5",
                    ),
                    layout=record_layout,
                )
                self.assertEqual(saved["template_id"], "legacy_landscape")
                self.assertEqual(
                    saved["layout"]["grids"]["root/form.blood_bank.patient_information:0"]["spans"],
                    record_layout["grids"]["root/form.blood_bank.patient_information:0"]["spans"],
                )
                effective = effective_record_print_presentation(
                    old_record,
                    fallback_profile=profile,
                )
                self.assertEqual(effective["source"], "record")
                self.assertEqual(effective["profile"]["template_id"], "legacy_landscape")
                self.assertTrue(user_can_manage_record_print_presentation(old_record, owner))
                self.assertTrue(user_can_manage_record_print_presentation(old_record, admin))
                self.assertFalse(user_can_manage_record_print_presentation(new_record, None))
        finally:
            engine.dispose()

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
