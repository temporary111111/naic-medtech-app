from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP_DIR = ROOT / "app"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from naic_builder.config import DB_PATH
from naic_builder.database import SessionLocal, ensure_runtime_schema
from naic_builder.services import (
    ensure_blood_gas_analysis_defaults,
    ensure_covid_19_antigen_rapid_test_defaults,
    ensure_default_patient_info_fields,
    ensure_hematology_defaults,
    ensure_hba1c_defaults,
    ensure_hiv_1_and_2_testing_defaults,
    ensure_microbiology_defaults,
    ensure_form_version_storage_documents,
    ensure_library_tree,
    ensure_pro_time_aptt_defaults,
    ensure_reference_seed,
)


def main() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()

    ensure_runtime_schema()
    with SessionLocal() as session:
        ensure_reference_seed(session)
        ensure_form_version_storage_documents(session)
        ensure_default_patient_info_fields(session)
        ensure_blood_gas_analysis_defaults(session)
        ensure_hematology_defaults(session)
        ensure_hba1c_defaults(session)
        ensure_pro_time_aptt_defaults(session)
        ensure_hiv_1_and_2_testing_defaults(session)
        ensure_covid_19_antigen_rapid_test_defaults(session)
        ensure_microbiology_defaults(session)
        ensure_library_tree(session)

    print(f"Reset runtime DB at: {DB_PATH}")


if __name__ == "__main__":
    main()
