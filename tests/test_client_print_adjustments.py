from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
TEST_RUNTIME = tempfile.TemporaryDirectory(prefix="ndhi-client-adjustments-")
os.environ["NDHI_LABRECORDS_DATA_DIR"] = TEST_RUNTIME.name

from naic_builder.models import FormVersion, Record
from naic_builder.services import (
    build_signatory_snapshot,
    default_signatory_slots,
    ensure_default_pathologist_stamp,
    list_record_completion_issues,
    normalize_signatory_slot,
    signatory_snapshots_for_print,
)


class ClientPrintAdjustmentTests(unittest.TestCase):
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
