from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
from pathlib import Path
from datetime import datetime, time, timedelta, timezone
from typing import Any, Callable
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from .config import (
    CLINIC_UPLOADS_DIR,
    DEFAULT_PATHOLOGIST_STAMP_FILENAME,
    DEFAULT_PATHOLOGIST_STAMP_RESOURCE_PATH,
    DEFAULT_PATHOLOGIST_STAMP_RUNTIME_PATH,
    DEFAULT_PATHOLOGIST_STAMP_URL,
    ORGANIZATION_SHORT_NAME,
    RECORD_UPLOADS_DIR,
    REFERENCE_SCHEMA_PATH,
    SIGNATORY_UPLOADS_DIR,
    USER_UPLOADS_DIR,
)
from .database import Base, engine
from .models import (
    ClinicProfile,
    FormDefinition,
    FormVersion,
    LibraryNode,
    Record,
    RecordAsset,
    RecordPrintPresentation,
    User,
    utc_now,
)
from .schemas import (
    AccountRequestPayload,
    ClinicProfilePayload,
    FormSavePayload,
    LoginPayload,
    PasswordChangePayload,
    RecordCreatePayload,
    RecordUpdatePayload,
    SetupAdminPayload,
    UserCreatePayload,
)

CANONICAL_BLOCK_SCHEMA_VERSION = 2
ACTIVE_BLOCK_SCHEMA_SOURCE = "builder_blocks_v2"
LEGACY_CONTAINER_KINDS = {"section", "field_group"}
ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAX_RECORD_IMAGE_BYTES = 10 * 1024 * 1024
MAX_CLINIC_LOGO_BYTES = 5 * 1024 * 1024
MAX_USER_AVATAR_BYTES = 2 * 1024 * 1024
MAX_SIGNATORY_STAMP_BYTES = 5 * 1024 * 1024
EDITABLE_RECORD_STATUSES = {"draft"}
VISIBLE_RECORD_STATUSES = {"draft", "completed", "voided"}
RECORD_DATE_SCOPES = {"today", "last_7_days", "this_month"}
RECORD_STATUS_LABELS = {
    "draft": "Draft",
    "completed": "Completed",
    "voided": "Voided",
    "deleted": "Deleted",
}
DEFAULT_PRINT_ACCENT_COLOR = "#1e5d52"
DEFAULT_PRINT_ACCENT_MIGRATED_META_KEY = "print_accent_default_migrated"
CLIENT_SIGNATORY_DEFAULTS_META_KEY = "client_signatory_defaults_2026_07"
DEFAULT_PRINT_ACCENT_COLORS_BY_FORM_KEY = {
    "abg": "#8064a2",
    "blood_bank": "#cc3399",
    "blood_gas_analysis": "#8064a2",
    "cardiac": "#f79646",
    "cardiaci": "#f79646",
    "coag": "#c0504d",
    "covid_19_antigen_rapid_test": "#f79646",
    "fecalysis": "#4bacc6",
    "female": "#9bbb59",
    "hba1c": "#9bbb59",
    "hba1ci": "#9bbb59",
    "hematology": "#c0504d",
    "hiv_1_and_2_testing": "#f79646",
    "hscrp": "#f79646",
    "male": "#9bbb59",
    "microbiology": "#000000",
    "ogtt": "#9bbb59",
    "pro_time_aptt": "#c0504d",
    "semen": "#00b0f0",
    "serology": "#f79646",
    "serologyi": "#f79646",
    "urinalysis": "#ffff66",
    "urine": "#ffff66",
}
PRINT_SUMMARY_SOURCES = {
    "field",
    "primary_identity",
    "secondary_identity",
    "record_key",
    "issued_at",
    "form_version",
}
PRINT_SIGNATURE_SOURCES = {"blank", "prepared_by", "manual", "field"}
PRINT_FONT_FAMILIES = {
    "arial",
    "arial_narrow",
    "aptos",
    "segoe_ui",
    "cambria_title",
    "georgia_title",
    "times_new_roman",
    "bahnschrift_title",
}
PRINT_TEMPLATE_IDS = {
    "modern_portrait",
    "modern_landscape",
    "classic_portrait",
    "classic_landscape",
    "legacy_landscape",
}
PRINT_TEMPLATE_ORDER = (
    "modern_portrait",
    "classic_portrait",
    "modern_landscape",
    "classic_landscape",
    "legacy_landscape",
)
PRINT_TEMPLATE_BY_STYLE_AND_ORIENTATION = {
    ("modern", "portrait"): "modern_portrait",
    ("classic", "portrait"): "classic_portrait",
    ("modern", "landscape"): "modern_landscape",
    ("classic", "landscape"): "classic_landscape",
    ("legacy", "landscape"): "legacy_landscape",
}
PRINT_TEMPLATE_STYLE_ORDER = ("modern", "classic", "legacy")
PRINT_TEMPLATE_STYLES = set(PRINT_TEMPLATE_STYLE_ORDER)
PRINT_TEMPLATE_ORIENTATIONS = {"portrait", "landscape"}
DEFAULT_PRINT_TEMPLATE_ID = "modern_portrait"
DEFAULT_PRINT_TEXT_SIZE = "standard"
DEFAULT_PRINT_PAPER_SIZE = "a4"
PRINT_PROFILE_VERSION = 2
PRINT_LAYOUT_PREFERENCE_VERSION = 5
FORM_PRINT_LAYOUT_DEFAULTS_VERSION = 1
PRINT_LAYOUT_MODES = {"preserve", "balance", "manual"}
PRINT_CONTAINER_LAYOUT_MODES = {"flow", "balance", "manual"}
PRINT_TEXT_SIZE_DETAILS = {
    "standard": {"id": "standard", "label": "Standard"},
    "large": {"id": "large", "label": "Large"},
}
PRINT_PAPER_SIZE_ORDER = ("a4", "legal", "letter", "a5")
PRINT_PAPER_SIZE_DETAILS = {
    "a4": {
        "id": "a4",
        "label": "A4",
        "css_size": "A4",
        "width_mm": 210,
        "height_mm": 297,
        "dimensions_label": "210 x 297 mm",
        "is_available": True,
    },
    "legal": {
        "id": "legal",
        "label": "Legal",
        "css_size": "legal",
        "width_mm": 216,
        "height_mm": 356,
        "dimensions_label": "216 x 356 mm",
        "is_available": True,
    },
    "letter": {
        "id": "letter",
        "label": "Letter",
        "css_size": "letter",
        "width_mm": 216,
        "height_mm": 279,
        "dimensions_label": "216 x 279 mm",
        "is_available": True,
    },
    "a5": {
        "id": "a5",
        "label": "A5",
        "css_size": "A5",
        "width_mm": 148,
        "height_mm": 210,
        "dimensions_label": "148 x 210 mm",
        "is_available": True,
    },
}
PRINT_AVAILABLE_PAPER_SIZE_IDS = {
    paper_size_id
    for paper_size_id, details in PRINT_PAPER_SIZE_DETAILS.items()
    if details["is_available"]
}
PRINT_TEMPLATE_CAPABILITIES = {
    "modern_portrait": {
        "text_sizes": ("standard", "large"),
        "fit_limit_units": 52.0,
        "large_text_fit_factor": 1.12,
    },
    "classic_portrait": {
        "text_sizes": ("standard", "large"),
        "fit_limit_units": 52.0,
        "large_text_fit_factor": 1.12,
    },
    "modern_landscape": {
        "text_sizes": ("standard", "large"),
        "fit_limit_units": 62.0,
        "large_text_fit_factor": 1.08,
    },
    "classic_landscape": {
        "text_sizes": ("standard", "large"),
        "fit_limit_units": 62.0,
        "large_text_fit_factor": 1.10,
    },
    "legacy_landscape": {
        "text_sizes": ("standard", "large"),
        "fit_limit_units": 62.0,
        "large_text_fit_factor": 1.10,
    },
}
PRINT_TEMPLATE_PAPER_CAPABILITIES = {
    # Legacy A5 is the clinic's historical result-sheet workflow. Its fit
    # estimate is intentionally conservative so a user is not told it will
    # fit when Chrome's real print pagination needs a second sheet.
    ("legacy_landscape", "a5"): {
        "text_sizes": ("standard",),
        "fit_limit_units": 37.0,
        "requires_one_page": True,
    },
}
PRINT_TEMPLATE_DETAILS = {
    "modern_portrait": {
        "id": "modern_portrait",
        "name": "Modern Portrait",
        "description": "A4 portrait result sheet with a colored report header.",
        "orientation": "Portrait",
        "orientation_key": "portrait",
        "style": "modern",
        "style_label": "Modern",
    },
    "classic_portrait": {
        "id": "classic_portrait",
        "name": "Classic Portrait",
        "description": "A4 portrait clinical result sheet with a formal monochrome header.",
        "orientation": "Portrait",
        "orientation_key": "portrait",
        "style": "classic",
        "style_label": "Classic",
    },
    "modern_landscape": {
        "id": "modern_landscape",
        "name": "Modern Landscape",
        "description": "A4 landscape result sheet with a colored report header.",
        "orientation": "Landscape",
        "orientation_key": "landscape",
        "style": "modern",
        "style_label": "Modern",
    },
    "classic_landscape": {
        "id": "classic_landscape",
        "name": "Classic Landscape",
        "description": "A4 landscape layout inspired by the clinic's legacy result sheets.",
        "orientation": "Landscape",
        "orientation_key": "landscape",
        "style": "classic",
        "style_label": "Classic",
    },
    "legacy_landscape": {
        "id": "legacy_landscape",
        "name": "Legacy Landscape",
        "description": "Historical laboratory-header style in a landscape layout.",
        "orientation": "Landscape",
        "orientation_key": "landscape",
        "style": "legacy",
        "style_label": "Legacy",
    },
}
DEFAULT_PRINT_SUMMARY_ITEMS = [
    {"id": "summary_primary", "label": "Record", "source": "primary_identity", "field_id": ""},
    {"id": "summary_secondary", "label": "Detail", "source": "secondary_identity", "field_id": ""},
    {"id": "summary_issued", "label": "Issued", "source": "issued_at", "field_id": ""},
    {"id": "summary_version", "label": "Form version", "source": "form_version", "field_id": ""},
]
DEFAULT_LAB_REQUEST_FIELD_SET_ID = "default_lab_request"
DEFAULT_PATIENT_INFO_MATERIALIZED_META_KEY = "default_patient_info_materialized"
DEFAULT_EXAMINATION_IN_PATIENT_INFO_META_KEY = "default_examination_in_patient_info_v1"
BLOOD_BANK_FORM_KEY = "blood_bank"
DEFAULT_BLOOD_BANK_DEFAULTS_META_KEY = "default_blood_bank_defaults_v1"
# This is a builder-owned starting point for the clinic's historical Blood Bank
# sheet. It deliberately belongs to Legacy Landscape / A5 only: other print
# profiles retain the generic responsive layout until an admin configures them.
BLOOD_BANK_LEGACY_A5_LAYOUT_DEFAULT = {
    "version": PRINT_LAYOUT_PREFERENCE_VERSION,
    "grids": {
        "root/form.blood_bank.patient_information:0": {
            "field_ids": [
                "form.blood_bank.patient_information.name",
                "form.blood_bank.patient_information.age",
                "form.blood_bank.patient_information.sex",
                "form.blood_bank.patient_information.date_or_datetime",
                "form.blood_bank.examination",
                "form.blood_bank.patient_information.requesting_physician",
                "form.blood_bank.patient_information.room",
                "form.blood_bank.patient_information.case_number",
            ],
            "mode": "manual",
            "spans": {
                "form.blood_bank.patient_information.name": 2,
                "form.blood_bank.patient_information.age": 2,
                "form.blood_bank.patient_information.sex": 2,
                "form.blood_bank.patient_information.date_or_datetime": 2,
                "form.blood_bank.examination": 2,
                "form.blood_bank.patient_information.requesting_physician": 2,
                "form.blood_bank.patient_information.room": 2,
                "form.blood_bank.patient_information.case_number": 4,
            },
            "order": [],
        },
        "root/form.blood_bank.details:0": {
            "field_ids": [
                "form.blood_bank.patient_s_blood_type",
                "form.blood_bank.blood_component",
                "form.blood_bank.donor_s_blood_type",
                "form.blood_bank.source_of_blood",
                "form.blood_bank.serial_number",
                "form.blood_bank.date_extracted",
                "form.blood_bank.date_expiry",
            ],
            "mode": "manual",
            "spans": {
                "form.blood_bank.patient_s_blood_type": 3,
                "form.blood_bank.blood_component": 3,
                "form.blood_bank.donor_s_blood_type": 3,
                "form.blood_bank.source_of_blood": 3,
                "form.blood_bank.serial_number": 6,
                "form.blood_bank.date_extracted": 3,
                "form.blood_bank.date_expiry": 3,
            },
            "order": [],
        },
        "root/form.blood_bank.type_of_crossmatching/form.blood_bank.type_of_crossmatching.vital_signs:0": {
            "field_ids": [
                "form.blood_bank.type_of_crossmatching.vital_signs.blood_pressure",
                "form.blood_bank.type_of_crossmatching.vital_signs.pulse_rate",
                "form.blood_bank.type_of_crossmatching.vital_signs.respiratory_rate",
                "form.blood_bank.type_of_crossmatching.vital_signs.temperature",
            ],
            "mode": "manual",
            "spans": {
                "form.blood_bank.type_of_crossmatching.vital_signs.blood_pressure": 3,
                "form.blood_bank.type_of_crossmatching.vital_signs.pulse_rate": 3,
                "form.blood_bank.type_of_crossmatching.vital_signs.respiratory_rate": 3,
                "form.blood_bank.type_of_crossmatching.vital_signs.temperature": 3,
            },
            "order": [],
        },
    },
    "containers": {
        "root:containers:0": {
            "container_ids": [
                "root/form.blood_bank.patient_information",
                "root/form.blood_bank.details",
                "root/form.blood_bank.type_of_crossmatching",
            ],
            "mode": "manual",
            "spans": {
                "root/form.blood_bank.patient_information": 6,
                "root/form.blood_bank.details": 2,
                "root/form.blood_bank.type_of_crossmatching": 4,
            },
            "order": [],
        },
    },
    "blocks": {
        "root/form.blood_bank.type_of_crossmatching:blocks:0": {
            "block_ids": [
                "form.blood_bank.type_of_crossmatching.immediate_spin_saline_phase",
                "form.blood_bank.type_of_crossmatching.albumin_phase_37_deg_c",
                "form.blood_bank.type_of_crossmatching.anti_human_globilin_phase",
                "form.blood_bank.type_of_crossmatching.remarks",
                "root/form.blood_bank.type_of_crossmatching/form.blood_bank.type_of_crossmatching.vital_signs",
                "form.blood_bank.type_of_crossmatching.released_by",
                "form.blood_bank.type_of_crossmatching.released_to",
                "form.blood_bank.type_of_crossmatching.release_date_time",
            ],
            "mode": "manual",
            "spans": {
                "form.blood_bank.type_of_crossmatching.immediate_spin_saline_phase": 2,
                "form.blood_bank.type_of_crossmatching.albumin_phase_37_deg_c": 2,
                "form.blood_bank.type_of_crossmatching.anti_human_globilin_phase": 2,
                "form.blood_bank.type_of_crossmatching.remarks": 3,
                "root/form.blood_bank.type_of_crossmatching/form.blood_bank.type_of_crossmatching.vital_signs": 6,
                "form.blood_bank.type_of_crossmatching.released_by": 3,
                "form.blood_bank.type_of_crossmatching.released_to": 3,
                "form.blood_bank.type_of_crossmatching.release_date_time": 3,
            },
            "order": [
                "form.blood_bank.type_of_crossmatching.immediate_spin_saline_phase",
                "form.blood_bank.type_of_crossmatching.albumin_phase_37_deg_c",
                "form.blood_bank.type_of_crossmatching.anti_human_globilin_phase",
                "root/form.blood_bank.type_of_crossmatching/form.blood_bank.type_of_crossmatching.vital_signs",
                "form.blood_bank.type_of_crossmatching.remarks",
                "form.blood_bank.type_of_crossmatching.released_by",
                "form.blood_bank.type_of_crossmatching.released_to",
                "form.blood_bank.type_of_crossmatching.release_date_time",
            ],
        },
    },
}


def legacy_a5_patient_information_grid(form_key: str) -> dict[str, dict[str, Any]]:
    prefix = f"form.{form_key}"
    return {
        f"root/{prefix}.patient_information:0": {
            "field_ids": [
                f"{prefix}.patient_information.name",
                f"{prefix}.patient_information.age",
                f"{prefix}.patient_information.sex",
                f"{prefix}.patient_information.date_or_datetime",
                f"{prefix}.examination",
                f"{prefix}.patient_information.requesting_physician",
                f"{prefix}.patient_information.room",
                f"{prefix}.patient_information.case_number",
            ],
            "mode": "manual",
            "spans": {
                f"{prefix}.patient_information.name": 2,
                f"{prefix}.patient_information.age": 2,
                f"{prefix}.patient_information.sex": 2,
                f"{prefix}.patient_information.date_or_datetime": 2,
                f"{prefix}.examination": 2,
                f"{prefix}.patient_information.requesting_physician": 2,
                f"{prefix}.patient_information.room": 3,
                f"{prefix}.patient_information.case_number": 3,
            },
            "order": [],
        },
    }


def qualitative_result_legacy_a5_layout(
    form_key: str,
    detail_field_keys: tuple[str, ...],
    *,
    spans: dict[str, int] | None = None,
) -> dict[str, Any]:
    prefix = f"form.{form_key}"
    field_ids = [f"{prefix}.{field_key}" for field_key in detail_field_keys]
    return {
        "version": PRINT_LAYOUT_PREFERENCE_VERSION,
        "grids": {
            **legacy_a5_patient_information_grid(form_key),
            f"root/{prefix}.details:0": {
                "field_ids": field_ids,
                "mode": "manual",
                "spans": spans or {field_id: 6 for field_id in field_ids},
                "order": [],
            },
        },
        "containers": {},
        "blocks": {},
    }
BLOOD_GAS_ANALYSIS_FORM_KEY = "blood_gas_analysis"
DEFAULT_BLOOD_GAS_LAYOUT_META_KEY = "default_blood_gas_layout_v2"
# This preserves the old ABG sheet's important visual relationship without
# turning the dynamic form into a static eight-column Word template.
BLOOD_GAS_LEGACY_A5_LAYOUT_DEFAULT = {
    "version": PRINT_LAYOUT_PREFERENCE_VERSION,
    "grids": {
        "root/form.blood_gas_analysis.patient_information:0": {
            "field_ids": [
                "form.blood_gas_analysis.patient_information.name",
                "form.blood_gas_analysis.patient_information.age",
                "form.blood_gas_analysis.patient_information.sex",
                "form.blood_gas_analysis.patient_information.date_or_datetime",
                "form.blood_gas_analysis.examination",
                "form.blood_gas_analysis.patient_information.requesting_physician",
                "form.blood_gas_analysis.patient_information.room",
                "form.blood_gas_analysis.patient_information.case_number",
            ],
            "mode": "manual",
            "spans": {
                "form.blood_gas_analysis.patient_information.name": 2,
                "form.blood_gas_analysis.patient_information.age": 2,
                "form.blood_gas_analysis.patient_information.sex": 2,
                "form.blood_gas_analysis.patient_information.date_or_datetime": 2,
                "form.blood_gas_analysis.examination": 2,
                "form.blood_gas_analysis.patient_information.requesting_physician": 2,
                "form.blood_gas_analysis.patient_information.room": 3,
                "form.blood_gas_analysis.patient_information.case_number": 3,
            },
            "order": [],
        },
        "root/form.blood_gas_analysis.calculated_values/form.blood_gas_analysis.calculated_values_acid_base_status:0": {
            "field_ids": [
                "form.blood_gas_analysis.calculated_values_acid_base_status.hco3",
                "form.blood_gas_analysis.calculated_values_acid_base_status.be_ecf",
                "form.blood_gas_analysis.calculated_values_acid_base_status.po2_a_a",
                "form.blood_gas_analysis.calculated_values_acid_base_status.tco2",
            ],
            "mode": "manual",
            "spans": {
                "form.blood_gas_analysis.calculated_values_acid_base_status.hco3": 3,
                "form.blood_gas_analysis.calculated_values_acid_base_status.be_ecf": 3,
                "form.blood_gas_analysis.calculated_values_acid_base_status.po2_a_a": 3,
                "form.blood_gas_analysis.calculated_values_acid_base_status.tco2": 3,
            },
            "order": [],
        },
    },
    "containers": {
        "root:containers:0": {
            "container_ids": [
                "root/form.blood_gas_analysis.patient_information",
                "root/form.blood_gas_analysis.blood_gas_values",
                "root/form.blood_gas_analysis.calculated_values",
            ],
            "mode": "manual",
            "spans": {
                "root/form.blood_gas_analysis.patient_information": 6,
                "root/form.blood_gas_analysis.blood_gas_values": 2,
                "root/form.blood_gas_analysis.calculated_values": 4,
            },
            "order": [],
        },
    },
    "blocks": {},
}
BLOOD_GAS_NUMERIC_RANGES = {
    "ph": ("7.35", "7.45"),
    "po2": ("80", "105"),
    "pco2": ("35.0", "45.0"),
    "so2": ("95", "100"),
    "hco3": ("22", "28"),
    "be_ecf": ("-2", "+2"),
    "po2_a_a": ("5", "10"),
    "tco2": ("23", "29"),
}
HEMATOLOGY_FORM_KEY = "hematology"
DEFAULT_HEMATOLOGY_LAYOUT_META_KEY = "default_hematology_layout_v2"


def normal_range_field_defaults(
    normal_min: str,
    normal_max: str,
    *,
    unit: str | None = None,
) -> dict[str, str | None]:
    defaults: dict[str, str | None] = {
        "normal_min": normal_min,
        "normal_max": normal_max,
        # The printed normal value must follow future Form Builder range edits.
        "reference_text": None,
        "normal_value": None,
    }
    if unit:
        defaults["unit"] = unit
        defaults["unit_hint"] = unit
    return defaults


HEMATOLOGY_FIELD_DEFAULTS = {
    "rbc_count_m": normal_range_field_defaults("4.6", "6.2", unit="x10^12/L"),
    "rbc_count_f": normal_range_field_defaults("4.2", "5.4", unit="x10^12/L"),
    "wbc_count": normal_range_field_defaults("5.0", "10.0", unit="x10^9/L"),
    "hemoglobin_m": normal_range_field_defaults("140", "180", unit="g/L"),
    "hemoglobin_f": normal_range_field_defaults("120", "160", unit="g/L"),
    "hematocrit_m": normal_range_field_defaults("0.40", "0.54", unit="/L"),
    "hematocrit_f": normal_range_field_defaults("0.37", "0.42", unit="/L"),
    "platelet_count": normal_range_field_defaults("150", "450", unit="x10^9/L"),
    "clotting_time": normal_range_field_defaults("1", "6", unit="minutes"),
    "bleeding_time": normal_range_field_defaults("1", "6", unit="minutes"),
    "segmenters": normal_range_field_defaults("0.50", "0.70"),
    "lymphocytes": normal_range_field_defaults("0.25", "0.40"),
    "monocytes": normal_range_field_defaults("0.03", "0.08"),
    "eosinophils": normal_range_field_defaults("0.01", "0.04"),
    "stab": normal_range_field_defaults("0", "0.05"),
    "e_s_r_m": normal_range_field_defaults("0", "10", unit="mm/hr"),
    "e_s_r_f": normal_range_field_defaults("0", "20", unit="mm/hr"),
}
HEMATOLOGY_DIFFERENTIAL_FIELD_KEYS = (
    "segmenters",
    "lymphocytes",
    "monocytes",
    "eosinophils",
    "stab",
    "e_s_r_m",
    "e_s_r_f",
)
HEMATOLOGY_DETAIL_FIELD_KEYS = (
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
    *HEMATOLOGY_DIFFERENTIAL_FIELD_KEYS,
    "others",
)
HBA1C_FORM_KEY = "hba1c"
DEFAULT_HBA1C_LAYOUT_META_KEY = "default_hba1c_layout_v2"
HBA1C_FIELD_DEFAULTS = {
    "result": {
        "normal_min": "4.0",
        "normal_max": "5.6",
        "unit": "%",
        "unit_hint": "%",
        "reference_text": None,
        "normal_value": None,
    },
}
HBA1C_LEGACY_A5_LAYOUT_DEFAULT = {
    "version": PRINT_LAYOUT_PREFERENCE_VERSION,
    "grids": {
        "root/form.hba1c.patient_information:0": {
            "field_ids": [
                "form.hba1c.patient_information.name",
                "form.hba1c.patient_information.age",
                "form.hba1c.patient_information.sex",
                "form.hba1c.patient_information.date_or_datetime",
                "form.hba1c.examination",
                "form.hba1c.patient_information.requesting_physician",
                "form.hba1c.patient_information.room",
                "form.hba1c.patient_information.case_number",
            ],
            "mode": "manual",
            "spans": {
                "form.hba1c.patient_information.name": 2,
                "form.hba1c.patient_information.age": 2,
                "form.hba1c.patient_information.sex": 2,
                "form.hba1c.patient_information.date_or_datetime": 2,
                "form.hba1c.examination": 2,
                "form.hba1c.patient_information.requesting_physician": 2,
                "form.hba1c.patient_information.room": 3,
                "form.hba1c.patient_information.case_number": 3,
            },
            "order": [],
        },
    },
    "containers": {},
    "blocks": {},
}
PRO_TIME_APTT_FORM_KEY = "pro_time_aptt"
DEFAULT_PRO_TIME_APTT_DEFAULTS_META_KEY = "default_pro_time_aptt_defaults_v2"
PRO_TIME_APTT_CONTAINER_FIELD_DEFAULTS = {
    "pro_time": {
        "test": {"normal_min": "10.0", "normal_max": "13.9", "unit": "seconds", "unit_hint": "seconds", "reference_text": None, "normal_value": None},
        "control": {"unit": "seconds", "unit_hint": "seconds", "reference_text": None, "normal_value": None},
        "inr": {"normal_min": "0.70", "normal_max": "1.30", "reference_text": None, "normal_value": None},
        "activity": {"unit": "%", "unit_hint": "%", "reference_text": None, "normal_value": None},
    },
    "aptt": {
        "test": {"normal_min": "22.2", "normal_max": "37.9", "unit": "seconds", "unit_hint": "seconds", "reference_text": None, "normal_value": None},
        "control": {"unit": "seconds", "unit_hint": "seconds", "reference_text": None, "normal_value": None},
    },
}
PRO_TIME_APTT_LEGACY_A5_LAYOUT_DEFAULT = {
    "version": PRINT_LAYOUT_PREFERENCE_VERSION,
    "grids": {
        **legacy_a5_patient_information_grid(PRO_TIME_APTT_FORM_KEY),
        "root/form.pro_time_aptt.pro_time:0": {
            "field_ids": [
                "form.pro_time_aptt.pro_time.test",
                "form.pro_time_aptt.pro_time.control",
                "form.pro_time_aptt.pro_time.inr",
                "form.pro_time_aptt.pro_time.activity",
            ],
            "mode": "manual",
            "spans": {
                "form.pro_time_aptt.pro_time.test": 6,
                "form.pro_time_aptt.pro_time.control": 6,
                "form.pro_time_aptt.pro_time.inr": 6,
                "form.pro_time_aptt.pro_time.activity": 6,
            },
            "order": [],
        },
    },
    "containers": {
        "root:containers:0": {
            "container_ids": [
                "root/form.pro_time_aptt.patient_information",
                "root/form.pro_time_aptt.pro_time",
                "root/form.pro_time_aptt.aptt",
            ],
            "mode": "manual",
            "spans": {
                "root/form.pro_time_aptt.patient_information": 6,
                "root/form.pro_time_aptt.pro_time": 3,
                "root/form.pro_time_aptt.aptt": 3,
            },
            "order": [],
        },
    },
    "blocks": {},
}
HIV_1_AND_2_TESTING_FORM_KEY = "hiv_1_and_2_testing"
DEFAULT_HIV_1_AND_2_TESTING_DEFAULTS_META_KEY = "default_hiv_1_and_2_testing_defaults_v1"
HIV_1_AND_2_TESTING_LEGACY_A5_LAYOUT_DEFAULT = qualitative_result_legacy_a5_layout(
    HIV_1_AND_2_TESTING_FORM_KEY,
    ("lot_number", "test_result"),
    spans={
        "form.hiv_1_and_2_testing.lot_number": 3,
        "form.hiv_1_and_2_testing.test_result": 3,
    },
)
COVID_19_ANTIGEN_RAPID_TEST_FORM_KEY = "covid_19_antigen_rapid_test"
DEFAULT_COVID_19_ANTIGEN_RAPID_TEST_DEFAULTS_META_KEY = "default_covid_19_antigen_rapid_test_defaults_v2"
COVID_19_ANTIGEN_RAPID_TEST_LEGACY_A5_LAYOUT_DEFAULT = qualitative_result_legacy_a5_layout(
    COVID_19_ANTIGEN_RAPID_TEST_FORM_KEY,
    ("test_result", "result_image"),
)
MICROBIOLOGY_FORM_KEY = "microbiology"
DEFAULT_MICROBIOLOGY_DEFAULTS_META_KEY = "default_microbiology_defaults_v1"
MICROBIOLOGY_LEGACY_A5_LAYOUT_DEFAULT = qualitative_result_legacy_a5_layout(
    MICROBIOLOGY_FORM_KEY,
    ("result",),
)
CARDIACI_FORM_KEY = "cardiaci"
DEFAULT_CARDIACI_DEFAULTS_META_KEY = "default_cardiaci_defaults_v1"
CARDIACI_FIELD_DEFAULTS = {
    "ck_mb": {"normal_min": "0.0", "normal_max": "4.3", "reference_text": None, "normal_value": None},
    "troponin_i": {"normal_min": "0.0", "normal_max": "0.02", "reference_text": None, "normal_value": None},
    "bnp": {"normal_min": "0.0", "normal_max": "100", "reference_text": None, "normal_value": None},
}
CARDIACI_LEGACY_A5_LAYOUT_DEFAULT = {
    "version": PRINT_LAYOUT_PREFERENCE_VERSION,
    "grids": {
        **legacy_a5_patient_information_grid(CARDIACI_FORM_KEY),
        "root/form.cardiaci.details:0": {
            "field_ids": [
                "form.cardiaci.ck_mb",
                "form.cardiaci.troponin_i",
                "form.cardiaci.bnp",
            ],
            "mode": "manual",
            "spans": {
                "form.cardiaci.ck_mb": 6,
                "form.cardiaci.troponin_i": 6,
                "form.cardiaci.bnp": 6,
            },
            "order": [],
        },
    },
    "containers": {},
    "blocks": {},
}
OGTT_FORM_KEY = "ogtt"
DEFAULT_OGTT_DEFAULTS_META_KEY = "default_ogtt_defaults_v1"
OGTT_LEGACY_A5_LAYOUT_DEFAULT = {
    "version": PRINT_LAYOUT_PREFERENCE_VERSION,
    "grids": legacy_a5_patient_information_grid(OGTT_FORM_KEY),
    "containers": {
        "root:containers:0": {
            "container_ids": [
                "root/form.ogtt.patient_information",
                "root/form.ogtt.50g_oral_glucose_tolerance",
                "root/form.ogtt.75g_oral_glucose_tolerance",
                "root/form.ogtt.100g_oral_glucose_tolerance",
                "root/form.ogtt.additional_tests",
            ],
            "mode": "manual",
            "spans": {
                "root/form.ogtt.patient_information": 6,
                "root/form.ogtt.50g_oral_glucose_tolerance": 3,
                "root/form.ogtt.75g_oral_glucose_tolerance": 3,
                "root/form.ogtt.100g_oral_glucose_tolerance": 3,
                "root/form.ogtt.additional_tests": 3,
            },
            "order": [],
        },
    },
    "blocks": {},
}
OGTT_CONTAINER_FIELD_DEFAULTS = {
    "50g_oral_glucose_tolerance": {
        "1st_hour": {
            "normal_max": "200",
            "normal_max_inclusive": False,
            "reference_text": None,
            "normal_value": None,
        },
        "2nd_hour": {
            "normal_max": "140",
            "normal_max_inclusive": False,
            "reference_text": None,
            "normal_value": None,
        },
    },
    "75g_oral_glucose_tolerance": {
        "fasting_blood_sugar": {
            "normal_min": "70.27",
            "normal_max": "124.32",
            "reference_text": None,
            "normal_value": None,
        },
        "1st_hour": {
            "normal_max": "200",
            "normal_max_inclusive": False,
            "reference_text": None,
            "normal_value": None,
        },
        "2nd_hour": {
            "normal_max": "140",
            "normal_max_inclusive": False,
            "reference_text": None,
            "normal_value": None,
        },
    },
    "100g_oral_glucose_tolerance": {
        "fasting_blood_sugar": {
            "normal_min": "70.27",
            "normal_max": "124.32",
            "reference_text": None,
            "normal_value": None,
        },
        "1st_hour": {
            "normal_max": "180",
            "normal_max_inclusive": False,
            "reference_text": None,
            "normal_value": None,
        },
        "2nd_hour": {
            "normal_max": "155",
            "normal_max_inclusive": False,
            "reference_text": None,
            "normal_value": None,
        },
        "3rd_hour": {
            "normal_max": "140",
            "normal_max_inclusive": False,
            "reference_text": None,
            "normal_value": None,
        },
    },
}
FECALYSIS_FORM_KEY = "fecalysis"
DEFAULT_FECALYSIS_DEFAULTS_META_KEY = "default_fecalysis_defaults_v1"
FECALYSIS_LEGACY_A5_LAYOUT_DEFAULT = {
    "version": PRINT_LAYOUT_PREFERENCE_VERSION,
    "grids": legacy_a5_patient_information_grid(FECALYSIS_FORM_KEY),
    "containers": {
        "root:containers:0": {
            "container_ids": [
                "root/form.fecalysis.patient_information",
                "root/form.fecalysis.macroscopic_finding",
                "root/form.fecalysis.microscopic_finding",
            ],
            "mode": "manual",
            "spans": {
                "root/form.fecalysis.patient_information": 6,
                "root/form.fecalysis.macroscopic_finding": 2,
                "root/form.fecalysis.microscopic_finding": 4,
            },
            "order": [],
        },
    },
    "blocks": {},
}
FECALYSIS_NORMAL_CHOICE_OPTIONS = {
    "fecal_occult_blood": ("NEGATIVE",),
    "parasites": ("NO OVA NOR PARASITES SEEN",),
}
SEROLOGY_FORM_KEY = "serology"
DEFAULT_SEROLOGY_DEFAULTS_META_KEY = "default_serology_defaults_v1"
SEROLOGY_LEGACY_A5_LAYOUT_DEFAULT = {
    "version": PRINT_LAYOUT_PREFERENCE_VERSION,
    "grids": legacy_a5_patient_information_grid(SEROLOGY_FORM_KEY),
    "containers": {
        "root:containers:0": {
            "container_ids": [
                "root/form.serology.patient_information",
                "root/form.serology.typhidot",
                "root/form.serology.dengue_test",
                "root/form.serology.malarial_test",
                "root/form.serology.other_serology_tests",
            ],
            "mode": "manual",
            "spans": {
                "root/form.serology.patient_information": 6,
                "root/form.serology.typhidot": 2,
                "root/form.serology.dengue_test": 2,
                "root/form.serology.malarial_test": 2,
                "root/form.serology.other_serology_tests": 6,
            },
            "order": [],
        },
    },
    "blocks": {},
}
SEROLOGY_NORMAL_CHOICE_OPTIONS = {
    "igm": ("NEGATIVE",),
    "igg": ("NEGATIVE",),
    "ns1ag": ("NEGATIVE",),
    "anti_plasmodium_falcifarum": ("NEGATIVE",),
    "anti_plasmodium_vivax": ("NEGATIVE",),
    "hbsag_screening": ("NON-REACTIVE",),
    "vdrl": ("NEGATIVE",),
    "anti_hcv": ("NON-REACTIVE",),
    "aso_titer": ("NEGATIVE <200 IU/ML",),
}
BLOOD_CHEMISTRY_MALE_FORM_KEY = "male"
DEFAULT_BLOOD_CHEMISTRY_MALE_DEFAULTS_META_KEY = "default_blood_chemistry_male_defaults_v1"
BLOOD_CHEMISTRY_FEMALE_FORM_KEY = "female"
DEFAULT_BLOOD_CHEMISTRY_FEMALE_DEFAULTS_META_KEY = "default_blood_chemistry_female_defaults_v1"
BLOOD_CHEMISTRY_RESULT_FIELD_KEYS = (
    "fasting_blood_sugar",
    "random_blood_sugar",
    "hgt",
    "blood_urea_nitrogen",
    "creatinine",
    "blood_uric_acid",
    "sodium",
    "potassium",
    "chloride",
    "ionized_calcium",
    "cholesterol",
    "triglyceride",
    "hdl_cholesterol",
    "ldl_cholesterol",
    "vldl_cholesterol",
    "sgot_ast",
    "sgpt_alt",
)


def blood_chemistry_legacy_a5_layout(form_key: str) -> dict[str, Any]:
    """Keep the long chemistry panel compact without fixing it to a Word table."""
    prefix = f"form.{form_key}"
    field_ids = [
        *(f"{prefix}.{field_key}" for field_key in BLOOD_CHEMISTRY_RESULT_FIELD_KEYS),
        f"{prefix}.others",
    ]
    spans = {field_id: 2 for field_id in field_ids}
    spans[f"{prefix}.sgot_ast"] = 3
    spans[f"{prefix}.sgpt_alt"] = 3
    spans[f"{prefix}.others"] = 6
    return {
        "version": PRINT_LAYOUT_PREFERENCE_VERSION,
        "grids": {
            **legacy_a5_patient_information_grid(form_key),
            f"root/{prefix}.details:0": {
                "field_ids": field_ids,
                "mode": "manual",
                "spans": spans,
                "order": [],
            },
        },
        "containers": {},
        "blocks": {},
    }


BLOOD_CHEMISTRY_RANGES_BY_FORM_KEY = {
    BLOOD_CHEMISTRY_MALE_FORM_KEY: {
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
    BLOOD_CHEMISTRY_FEMALE_FORM_KEY: {
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
PATIENT_INFO_GROUP_KEY = "patient_information"
PATIENT_INFO_GROUP_NAME = "Patient Information"
PATIENT_INFO_PRIMARY_KEY = "name"
PATIENT_INFO_SECONDARY_KEY = "case_number"
PATIENT_INFO_REQUIRED_KEYS = {PATIENT_INFO_PRIMARY_KEY, PATIENT_INFO_SECONDARY_KEY}
SIGNATORY_FIELD_KEYS = {"medical_technologist", "pathologist"}
SIGNATORY_INPUT_TYPES = {"person_dropdown", "manual", "fixed", "blank", "stamp_image"}
DEFAULT_MEDTECH_SIGNATORY_PEOPLE = [
    {"id": "imelda_a_elemia", "name": "Imelda A. Elemia, RMT", "license": "0036643"},
    {"id": "crystel_c_tesoro", "name": "Crystel C. Tesoro, RMT", "license": "0103760"},
    {"id": "ma_jesusa_b_vite", "name": "Ma. Jesusa B. Vite, RMT", "license": "0118710"},
    {"id": "andrea_coleen_a_avellones", "name": "Andrea Coleen A. Avellones, RMT", "license": "0119501"},
    {"id": "julie_kyle_a_ronato", "name": "Julie Kyle A. Ronato, RMT", "license": "0119616"},
    {"id": "shiela_mae_d_libradilla", "name": "Shiela Mae D. Libradilla, RMT", "license": "0135995"},
]
DEFAULT_PATHOLOGIST_SIGNATORY_PEOPLE = [
    {
        "id": "bernardita_mojica_figueroa",
        "name": "Bernardita Mojica Figueroa, MD, DPSP",
        "license": "068053",
    },
]


def load_reference_schema() -> dict[str, Any]:
    return json.loads(REFERENCE_SCHEMA_PATH.read_text(encoding="utf-8"))




def slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return normalized or "item"


def compact_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def format_print_temporal_value(data_type: Any, value: Any) -> str:
    text = compact_text(value)
    kind = compact_text(data_type).lower()
    if not text or kind not in {"date", "time", "datetime"}:
        return text
    try:
        if kind == "date":
            parsed_date = datetime.fromisoformat(text).date()
            return parsed_date.strftime("%m/%d/%Y")
        if kind == "time":
            parsed_time = time.fromisoformat(text)
            return parsed_time.strftime("%I:%M %p")
        parsed_datetime = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed_datetime.strftime("%m/%d/%Y %I:%M %p")
    except ValueError:
        return text


def normalize_email(value: Any) -> str:
    return compact_text(value).lower()


def normalize_login_id(value: Any) -> str:
    return slugify(compact_text(value))


def validate_email_format(email: str) -> bool:
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email))


def validate_role(value: Any) -> str:
    role = compact_text(value).lower()
    return role if role in {"admin", "medtech"} else "medtech"


def validate_user_status(value: Any) -> str:
    status = compact_text(value).lower()
    return status if status in {"pending", "active", "disabled"} else "pending"


def normalize_print_accent_color(value: Any) -> str:
    text = compact_text(value)
    return text.lower() if re.fullmatch(r"#[0-9a-fA-F]{6}", text) else DEFAULT_PRINT_ACCENT_COLOR


def normalize_print_header_text_color(value: Any) -> str:
    color = compact_text(value).lower()
    return color if color in {"black", "white"} else "auto"

def form_key_from_meta(meta: dict[str, Any]) -> str:
    raw_key = compact_text(meta.get("form_key")) or compact_text(meta.get("form_id"))
    if raw_key.startswith("form."):
        raw_key = raw_key[5:]
    return slugify(raw_key)


def default_print_accent_color_for_form_key(form_key: Any) -> str:
    return DEFAULT_PRINT_ACCENT_COLORS_BY_FORM_KEY.get(slugify(compact_text(form_key)), DEFAULT_PRINT_ACCENT_COLOR)


def print_accent_text_color(value: Any) -> str:
    color = normalize_print_accent_color(value).lstrip("#")
    red = int(color[0:2], 16)
    green = int(color[2:4], 16)
    blue = int(color[4:6], 16)

    def linear_channel(channel: int) -> float:
        value = channel / 255
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4

    luminance = (
        0.2126 * linear_channel(red)
        + 0.7152 * linear_channel(green)
        + 0.0722 * linear_channel(blue)
    )
    contrast_with_dark = (luminance + 0.05) / 0.05
    contrast_with_light = 1.05 / (luminance + 0.05)
    return "#171512" if contrast_with_dark >= contrast_with_light else "#ffffff"


def print_header_text_color(print_config: dict[str, Any] | None) -> str:
    config = print_config if isinstance(print_config, dict) else {}
    color = normalize_print_header_text_color(config.get("header_text_color"))
    if color == "black":
        return "#171512"
    if color == "white":
        return "#ffffff"
    return print_accent_text_color(config.get("accent_color"))

def ensure_form_default_print_accent(meta: dict[str, Any]) -> bool:
    form_key = form_key_from_meta(meta)
    default_accent = default_print_accent_color_for_form_key(form_key)
    if default_accent == DEFAULT_PRINT_ACCENT_COLOR:
        return False

    raw_config = meta.get("print_config") if isinstance(meta.get("print_config"), dict) else {}
    print_config = normalize_print_config(raw_config)
    changed = print_config != raw_config
    already_migrated = bool(meta.get(DEFAULT_PRINT_ACCENT_MIGRATED_META_KEY))

    if not already_migrated and print_config.get("accent_color") == DEFAULT_PRINT_ACCENT_COLOR:
        print_config["accent_color"] = default_accent
        meta[DEFAULT_PRINT_ACCENT_MIGRATED_META_KEY] = True
        changed = True
    elif not already_migrated and print_config.get("accent_color") != DEFAULT_PRINT_ACCENT_COLOR:
        meta[DEFAULT_PRINT_ACCENT_MIGRATED_META_KEY] = True
        changed = True

    if changed:
        meta["print_config"] = print_config
    return changed


def normalize_print_density(value: Any) -> str:
    density = compact_text(value).lower()
    return density if density in {"compact", "comfortable"} else "compact"


def normalize_print_image_size(value: Any) -> str:
    size = compact_text(value).lower()
    return size if size in {"small", "medium", "large"} else "medium"


def normalize_print_table_density(value: Any) -> str:
    density = compact_text(value).lower()
    return density if density in {"compact", "comfortable"} else "compact"


def normalize_print_result_layout(value: Any) -> str:
    layout = compact_text(value).lower()
    return layout if layout in {"rows", "compact_grid"} else "compact_grid"


def normalize_print_font_family(value: Any) -> str:
    font_family = compact_text(value).lower().replace("-", "_").replace(" ", "_")
    return font_family if font_family in PRINT_FONT_FAMILIES else "arial_narrow"


def normalize_print_template_id(value: Any) -> str:
    template_id = compact_text(value).lower().replace("-", "_").replace(" ", "_")
    return template_id if template_id in PRINT_TEMPLATE_IDS else DEFAULT_PRINT_TEMPLATE_ID


def normalize_print_template_style(value: Any) -> str:
    style = compact_text(value).lower()
    return style if style in PRINT_TEMPLATE_STYLES else "modern"


def normalize_print_template_orientation(value: Any) -> str:
    orientation = compact_text(value).lower()
    return orientation if orientation in PRINT_TEMPLATE_ORIENTATIONS else "portrait"


def print_template_ids_for_style(style: Any) -> tuple[str, ...]:
    selected_style = normalize_print_template_style(style)
    return tuple(
        template_id
        for template_id in PRINT_TEMPLATE_ORDER
        if PRINT_TEMPLATE_DETAILS[template_id]["style"] == selected_style
    )


def print_style_options() -> list[dict[str, str]]:
    options: list[dict[str, str]] = []
    for style in PRINT_TEMPLATE_STYLE_ORDER:
        template_ids = print_template_ids_for_style(style)
        if not template_ids:
            continue
        options.append(
            {
                "id": style,
                "label": PRINT_TEMPLATE_DETAILS[template_ids[0]]["style_label"],
            }
        )
    return options


def print_orientation_options() -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    for orientation in ("portrait", "landscape"):
        supported_styles = [
            style
            for style in PRINT_TEMPLATE_STYLE_ORDER
            if (style, orientation) in PRINT_TEMPLATE_BY_STYLE_AND_ORIENTATION
        ]
        options.append(
            {
                "id": orientation,
                "label": orientation.title(),
                "supported_styles": supported_styles,
            }
        )
    return options


def print_template_id_for(
    style: Any,
    orientation: Any,
    *,
    fallback_template_id: Any = "",
) -> str:
    selected_style = normalize_print_template_style(style)
    selected_orientation = normalize_print_template_orientation(orientation)
    resolved_template_id = PRINT_TEMPLATE_BY_STYLE_AND_ORIENTATION.get(
        (selected_style, selected_orientation)
    )
    if resolved_template_id:
        return resolved_template_id

    fallback = normalize_print_template_id(fallback_template_id)
    if PRINT_TEMPLATE_DETAILS[fallback]["style"] == selected_style:
        return fallback

    available_templates = print_template_ids_for_style(selected_style)
    return available_templates[0] if available_templates else DEFAULT_PRINT_TEMPLATE_ID


def print_template_parts(template_id: Any) -> dict[str, str]:
    selected_template_id = normalize_print_template_id(template_id)
    details = PRINT_TEMPLATE_DETAILS[selected_template_id]
    return {
        "style": details["style"],
        "orientation": details["orientation_key"],
    }


def print_template_paper_capabilities(template_id: Any, paper_size: Any = "") -> dict[str, Any]:
    selected_template_id = normalize_print_template_id(template_id)
    selected_paper_size = normalize_print_paper_size(paper_size)
    capabilities = dict(PRINT_TEMPLATE_CAPABILITIES[selected_template_id])
    capabilities.update(
        PRINT_TEMPLATE_PAPER_CAPABILITIES.get((selected_template_id, selected_paper_size), {})
    )
    return capabilities


def print_text_size_options(template_id: Any, *, paper_size: Any = "") -> list[dict[str, str]]:
    selected_template_id = normalize_print_template_id(template_id)
    allowed_sizes = print_template_paper_capabilities(selected_template_id, paper_size)["text_sizes"]
    return [dict(PRINT_TEXT_SIZE_DETAILS[size]) for size in allowed_sizes]


def normalize_print_text_size(
    value: Any,
    *,
    template_id: Any = "",
    paper_size: Any = "",
) -> str:
    normalized_template_id = normalize_print_template_id(template_id)
    text_size = compact_text(value).lower()
    allowed_sizes = print_template_paper_capabilities(normalized_template_id, paper_size)["text_sizes"]
    return text_size if text_size in allowed_sizes else allowed_sizes[0]


def normalize_print_paper_size(value: Any) -> str:
    paper_size = compact_text(value).lower().replace("-", "_").replace(" ", "_")
    return paper_size if paper_size in PRINT_AVAILABLE_PAPER_SIZE_IDS else DEFAULT_PRINT_PAPER_SIZE


def print_paper_size_options() -> list[dict[str, Any]]:
    return [
        dict(PRINT_PAPER_SIZE_DETAILS[paper_size_id])
        for paper_size_id in PRINT_PAPER_SIZE_ORDER
        if paper_size_id in PRINT_AVAILABLE_PAPER_SIZE_IDS
    ]


def normalize_print_profile(
    *,
    template_id: Any = "",
    style: Any = "",
    orientation: Any = "",
    text_size: Any = "",
    paper_size: Any = "",
) -> dict[str, Any]:
    selected_template_id = normalize_print_template_id(template_id)
    fallback_parts = print_template_parts(selected_template_id)
    selected_style = (
        normalize_print_template_style(style)
        if compact_text(style)
        else fallback_parts["style"]
    )
    selected_orientation = (
        normalize_print_template_orientation(orientation)
        if compact_text(orientation)
        else fallback_parts["orientation"]
    )
    selected_template_id = print_template_id_for(
        selected_style,
        selected_orientation,
        fallback_template_id=selected_template_id,
    )
    selected_parts = print_template_parts(selected_template_id)
    selected_style = selected_parts["style"]
    selected_orientation = selected_parts["orientation"]
    selected_paper_size = normalize_print_paper_size(paper_size)
    selected_text_size = normalize_print_text_size(
        text_size,
        template_id=selected_template_id,
        paper_size=selected_paper_size,
    )
    return {
        "version": PRINT_PROFILE_VERSION,
        "template_id": selected_template_id,
        "style": selected_style,
        "orientation": selected_orientation,
        "text_size": selected_text_size,
        "paper_size": selected_paper_size,
    }


def apply_print_presentation(
    print_config: dict[str, Any] | None,
    *,
    template_id: Any = "",
    style: Any = "",
    orientation: Any = "",
    text_size: Any = "",
    paper_size: Any = "",
) -> dict[str, Any]:
    config = dict(print_config) if isinstance(print_config, dict) else {}
    profile = normalize_print_profile(
        template_id=template_id,
        style=style,
        orientation=orientation,
        text_size=text_size,
        paper_size=paper_size,
    )
    config.update(profile)
    return config


def print_presentation_details(
    template_id: Any,
    text_size: Any = "",
    *,
    style: Any = "",
    orientation: Any = "",
    paper_size: Any = "",
) -> dict[str, Any]:
    profile = normalize_print_profile(
        template_id=template_id,
        style=style,
        orientation=orientation,
        text_size=text_size,
        paper_size=paper_size,
    )
    details = dict(PRINT_TEMPLATE_DETAILS[profile["template_id"]])
    details.update(profile)
    paper_size_details = PRINT_PAPER_SIZE_DETAILS[profile["paper_size"]]
    is_landscape = profile["orientation"] == "landscape"
    page_width_mm = paper_size_details["height_mm"] if is_landscape else paper_size_details["width_mm"]
    page_height_mm = paper_size_details["width_mm"] if is_landscape else paper_size_details["height_mm"]
    field_grid_columns = 3 if is_landscape else 2
    details.update(
        {
            "paper_size_label": paper_size_details["label"],
            "page_size": paper_size_details["label"],
            "page_css_size": paper_size_details["css_size"],
            "page_dimensions_label": paper_size_details["dimensions_label"],
            "page_width_mm": page_width_mm,
            "page_height_mm": page_height_mm,
            "field_grid_columns": field_grid_columns,
            "field_grid_units": field_grid_columns * 2,
        }
    )
    details["text_size_label"] = PRINT_TEXT_SIZE_DETAILS[profile["text_size"]]["label"]
    capabilities = print_template_paper_capabilities(
        profile["template_id"],
        profile["paper_size"],
    )
    details["text_size_options"] = print_text_size_options(
        profile["template_id"],
        paper_size=profile["paper_size"],
    )
    details["requires_one_page"] = bool(capabilities.get("requires_one_page"))
    details["orientation_options"] = print_orientation_options()
    return details


def print_page_fit_limit_units(profile: dict[str, Any]) -> float:
    template_id = normalize_print_template_id(profile.get("template_id"))
    paper_size = normalize_print_paper_size(profile.get("paper_size"))
    orientation = normalize_print_template_orientation(profile.get("orientation"))
    selected_paper = PRINT_PAPER_SIZE_DETAILS[paper_size]
    a4_paper = PRINT_PAPER_SIZE_DETAILS[DEFAULT_PRINT_PAPER_SIZE]
    is_landscape = orientation == "landscape"
    page_width_mm = selected_paper["height_mm"] if is_landscape else selected_paper["width_mm"]
    page_height_mm = selected_paper["width_mm"] if is_landscape else selected_paper["height_mm"]
    a4_page_width_mm = a4_paper["height_mm"] if is_landscape else a4_paper["width_mm"]
    a4_page_height_mm = a4_paper["width_mm"] if is_landscape else a4_paper["height_mm"]
    vertical_margins_mm = 12 if is_landscape else 8
    usable_height_factor = (page_height_mm - vertical_margins_mm) / (
        a4_page_height_mm - vertical_margins_mm
    )
    narrow_width_factor = min(1.0, page_width_mm / a4_page_width_mm)
    capabilities = print_template_paper_capabilities(template_id, paper_size)
    if "fit_limit_units" in PRINT_TEMPLATE_PAPER_CAPABILITIES.get((template_id, paper_size), {}):
        return float(capabilities["fit_limit_units"])
    return (
        capabilities["fit_limit_units"]
        * usable_height_factor
        * narrow_width_factor
    )


def normalize_print_signature_source(value: Any, *, default: str = "blank") -> str:
    source = compact_text(value).lower()
    fallback = default if default in PRINT_SIGNATURE_SOURCES else "blank"
    return source if source in PRINT_SIGNATURE_SOURCES else fallback


def normalize_boolean_setting(value: Any, *, default: bool = True) -> bool:
    if value in (None, ""):
        return default
    if isinstance(value, str):
        return compact_text(value).lower() not in {"0", "false", "no", "off"}
    return bool(value)


def default_print_summary_label(source: str) -> str:
    return {
        "primary_identity": "Record",
        "secondary_identity": "Detail",
        "record_key": "Record key",
        "issued_at": "Issued",
        "form_version": "Form version",
        "field": "Field",
    }.get(source, "Field")


def normalize_print_summary_item(item: Any, index: int) -> dict[str, str]:
    raw_item = item if isinstance(item, dict) else {}
    source = compact_text(raw_item.get("source")).lower()
    if source not in PRINT_SUMMARY_SOURCES:
        source = "field"
    field_id = compact_text(raw_item.get("field_id")) if source == "field" else ""
    label = compact_text(raw_item.get("label")) or default_print_summary_label(source)
    return {
        "id": compact_text(raw_item.get("id")) or f"summary_{index + 1}",
        "label": label,
        "source": source,
        "field_id": field_id,
    }


def normalize_print_config(raw_config: Any) -> dict[str, Any]:
    config = raw_config if isinstance(raw_config, dict) else {}
    summary_items = [
        normalize_print_summary_item(item, index)
        for index, item in enumerate(normalize_items(config.get("summary_items")))
    ]
    if not summary_items:
        summary_items = [dict(item) for item in DEFAULT_PRINT_SUMMARY_ITEMS]

    return {
        "report_title": compact_text(config.get("report_title")),
        "accent_color": normalize_print_accent_color(config.get("accent_color")),
        "header_text_color": normalize_print_header_text_color(config.get("header_text_color")),
        "density": normalize_print_density(config.get("density")),
        "font_family": normalize_print_font_family(config.get("font_family")),
        "show_logo": normalize_boolean_setting(config.get("show_logo"), default=True),
        "show_clinic_info": normalize_boolean_setting(config.get("show_clinic_info"), default=True),
        "show_status": normalize_boolean_setting(config.get("show_status"), default=True),
        "show_summary": normalize_boolean_setting(config.get("show_summary"), default=False),
        "show_signatures": normalize_boolean_setting(config.get("show_signatures"), default=True),
        "hide_empty_fields": normalize_boolean_setting(config.get("hide_empty_fields"), default=False),
        "show_top_level_container_titles": normalize_boolean_setting(
            config.get("show_top_level_container_titles", config.get("show_section_titles")),
            default=True,
        ),
        "show_nested_container_titles": normalize_boolean_setting(
            config.get("show_nested_container_titles", config.get("show_group_titles")),
            default=True,
        ),
        "image_size": normalize_print_image_size(config.get("image_size")),
        "table_density": normalize_print_table_density(config.get("table_density")),
        "result_layout": normalize_print_result_layout(config.get("result_layout")),
        "signature_left_label": compact_text(config.get("signature_left_label")) or "Medical Technologist",
        "signature_left_source": normalize_print_signature_source(config.get("signature_left_source"), default="prepared_by"),
        "signature_left_name": compact_text(config.get("signature_left_name")),
        "signature_left_field_id": compact_text(config.get("signature_left_field_id")),
        "signature_right_label": compact_text(config.get("signature_right_label")) or "Pathologist",
        "signature_right_source": normalize_print_signature_source(config.get("signature_right_source"), default="blank"),
        "signature_right_name": compact_text(config.get("signature_right_name")),
        "signature_right_field_id": compact_text(config.get("signature_right_field_id")),
        "summary_items": summary_items,
    }


def default_print_report_title(form_name: Any, form_path_label: Any = "") -> str:
    fallback = compact_text(form_name) or "Untitled Form"
    path_label = compact_text(form_path_label)
    if not path_label or path_label == fallback or path_label == "Top level":
        return fallback
    root_label = compact_text(path_label.split("/", 1)[0])
    return root_label or fallback


def resolve_print_report_title(
    print_config: dict[str, Any] | None,
    *,
    form_name: Any,
    form_path_label: Any = "",
) -> str:
    config = print_config if isinstance(print_config, dict) else {}
    return compact_text(config.get("report_title")) or default_print_report_title(form_name, form_path_label)


def password_hash_value(password: str) -> str:
    salt = secrets.token_bytes(16)
    iterations = 120_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256${iterations}${salt}${digest}".format(
        iterations=iterations,
        salt=base64.b64encode(salt).decode("ascii"),
        digest=base64.b64encode(digest).decode("ascii"),
    )


def verify_password_hash(password_hash: str | None, password: str) -> bool:
    stored = compact_text(password_hash)
    if not stored:
        return False
    try:
        algorithm, iterations_text, salt_text, digest_text = stored.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_text)
        salt = base64.b64decode(salt_text.encode("ascii"))
        expected = base64.b64decode(digest_text.encode("ascii"))
    except (TypeError, ValueError, base64.binascii.Error):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def validate_password_strength(password: str) -> None:
    if len(password or "") < 8:
        raise ValueError("Use at least 8 characters for the password.")


def derive_login_id(*, full_name: str, email: str, requested_login_id: str = "") -> str:
    requested = normalize_login_id(requested_login_id)
    if requested:
        return requested
    email_local = normalize_email(email).split("@", 1)[0]
    email_candidate = normalize_login_id(email_local)
    if email_candidate:
        return email_candidate
    return normalize_login_id(full_name) or "user"


def next_available_login_id(session: Session, base_login_id: str) -> str:
    base = normalize_login_id(base_login_id) or "user"
    candidate = base
    suffix = 2
    while session.scalar(select(User.id).where(User.login_id == candidate)) is not None:
        candidate = f"{base}{suffix}"
        suffix += 1
    return candidate


def has_any_users(session: Session) -> bool:
    return session.scalar(select(User.id).limit(1)) is not None


def has_any_admin_users(session: Session) -> bool:
    return session.scalar(
        select(User.id).where(User.role == "admin", User.status == "active").limit(1)
    ) is not None


def count_active_admin_users(session: Session) -> int:
    return int(
        session.scalar(
            select(func.count(User.id)).where(User.role == "admin", User.status == "active")
        )
        or 0
    )


def get_user_or_none(session: Session, user_id: int) -> User | None:
    return session.scalar(select(User).where(User.id == user_id))


def get_user_by_identifier(session: Session, identifier: str) -> User | None:
    normalized = compact_text(identifier).lower()
    if not normalized:
        return None
    return session.scalar(
        select(User).where(
            or_(
                func.lower(User.login_id) == normalized,
                func.lower(User.email) == normalized,
            )
        )
    )


def serialize_user(user: User) -> dict[str, Any]:
    print_preference = user_print_preferences(user)
    return {
        "id": user.id,
        "email": user.email,
        "login_id": user.login_id,
        "full_name": user.full_name,
        "role": user.role,
        "status": user.status,
        "must_change_password": bool(user.must_change_password),
        "avatar_path": user.avatar_path,
        "avatar_original_filename": compact_text(user.avatar_original_filename),
        "avatar_mime_type": compact_text(user.avatar_mime_type),
        "has_avatar": bool(compact_text(user.avatar_path)),
        "print_template_id": print_preference["template_id"],
        "print_style": print_preference["style"],
        "print_orientation": print_preference["orientation"],
        "print_text_size": print_preference["text_size"],
        "print_paper_size": print_preference["paper_size"],
        "created_at": user.created_at.astimezone(timezone.utc).isoformat(),
        "updated_at": user.updated_at.astimezone(timezone.utc).isoformat(),
    }


def user_print_preferences(user: User | None) -> dict[str, Any]:
    return normalize_print_profile(
        template_id=user.print_template_id if user is not None else "",
        text_size=user.print_text_size if user is not None else "",
        paper_size=user.print_paper_size if user is not None else "",
    )


def save_user_print_preferences(
    session: Session,
    user: User,
    *,
    template_id: Any = "",
    style: Any = "",
    orientation: Any = "",
    text_size: Any = "",
    paper_size: Any = "",
) -> dict[str, Any]:
    profile = normalize_print_profile(
        template_id=template_id,
        style=style,
        orientation=orientation,
        text_size=text_size,
        paper_size=paper_size if compact_text(paper_size) else user.print_paper_size,
    )
    user.print_template_id = profile["template_id"]
    user.print_text_size = profile["text_size"]
    user.print_paper_size = profile["paper_size"]
    save_user(session, user)
    return user_print_preferences(user)


def print_layout_profile_key(form_id: int, template_id: Any, paper_size: Any) -> str:
    return ":".join(
        [
            str(max(0, int(form_id or 0))),
            normalize_print_template_id(template_id),
            normalize_print_paper_size(paper_size),
        ]
    )


def normalize_print_layout_mode(value: Any) -> str:
    mode = compact_text(value).lower()
    return mode if mode in PRINT_LAYOUT_MODES else "preserve"


def normalize_print_container_layout_mode(value: Any) -> str:
    mode = compact_text(value).lower()
    return mode if mode in PRINT_CONTAINER_LAYOUT_MODES else "flow"


def normalize_print_layout_order(value: Any) -> list[str]:
    order: list[str] = []
    for raw_item_id in normalize_items(value):
        item_id = compact_text(raw_item_id)
        if item_id and item_id not in order and len(order) < 200:
            order.append(item_id)
    return order


def normalize_print_layout_preference(value: Any) -> dict[str, Any]:
    raw_preference = value if isinstance(value, dict) else {}
    raw_grids = raw_preference.get("grids") if isinstance(raw_preference.get("grids"), dict) else {}
    grids: dict[str, dict[str, Any]] = {}

    for raw_grid_id, raw_grid in raw_grids.items():
        grid_id = compact_text(raw_grid_id)
        if not grid_id or len(grid_id) > 480 or not isinstance(raw_grid, dict):
            continue
        field_ids: list[str] = []
        for raw_field_id in normalize_items(raw_grid.get("field_ids")):
            field_id = compact_text(raw_field_id)
            if field_id and field_id not in field_ids:
                field_ids.append(field_id)
        if not field_ids:
            continue

        raw_spans = raw_grid.get("spans") if isinstance(raw_grid.get("spans"), dict) else {}
        spans: dict[str, int] = {}
        for field_id in field_ids:
            try:
                span = int(raw_spans.get(field_id) or 0)
            except (TypeError, ValueError):
                span = 0
            if 1 <= span <= 12:
                spans[field_id] = span

        grids[grid_id] = {
            "field_ids": field_ids,
            "mode": normalize_print_layout_mode(raw_grid.get("mode")),
            "spans": spans,
            "order": normalize_print_layout_order(raw_grid.get("order")),
        }

    raw_containers = (
        raw_preference.get("containers")
        if isinstance(raw_preference.get("containers"), dict)
        else {}
    )
    containers: dict[str, dict[str, Any]] = {}
    for raw_run_id, raw_run in raw_containers.items():
        run_id = compact_text(raw_run_id)
        if not run_id or len(run_id) > 480 or not isinstance(raw_run, dict):
            continue
        container_ids: list[str] = []
        for raw_container_id in normalize_items(raw_run.get("container_ids")):
            container_id = compact_text(raw_container_id)
            if container_id and container_id not in container_ids:
                container_ids.append(container_id)
        if len(container_ids) < 2:
            continue

        raw_spans = raw_run.get("spans") if isinstance(raw_run.get("spans"), dict) else {}
        spans: dict[str, int] = {}
        for container_id in container_ids:
            try:
                span = int(raw_spans.get(container_id) or 0)
            except (TypeError, ValueError):
                span = 0
            if 1 <= span <= 12:
                spans[container_id] = span

        containers[run_id] = {
            "container_ids": container_ids,
            "mode": normalize_print_container_layout_mode(raw_run.get("mode")),
            "spans": spans,
            "order": normalize_print_layout_order(raw_run.get("order")),
        }

    raw_blocks = raw_preference.get("blocks") if isinstance(raw_preference.get("blocks"), dict) else {}
    blocks: dict[str, dict[str, Any]] = {}
    for raw_run_id, raw_run in raw_blocks.items():
        run_id = compact_text(raw_run_id)
        if not run_id or len(run_id) > 480 or not isinstance(raw_run, dict):
            continue
        block_ids: list[str] = []
        for raw_block_id in normalize_items(raw_run.get("block_ids")):
            block_id = compact_text(raw_block_id)
            if block_id and block_id not in block_ids:
                block_ids.append(block_id)
        if len(block_ids) < 2:
            continue

        raw_spans = raw_run.get("spans") if isinstance(raw_run.get("spans"), dict) else {}
        spans: dict[str, int] = {}
        for block_id in block_ids:
            try:
                span = int(raw_spans.get(block_id) or 0)
            except (TypeError, ValueError):
                span = 0
            if 1 <= span <= 12:
                spans[block_id] = span

        blocks[run_id] = {
            "block_ids": block_ids,
            "mode": normalize_print_container_layout_mode(raw_run.get("mode")),
            "spans": spans,
            "order": normalize_print_layout_order(raw_run.get("order")),
        }

    return {
        "version": PRINT_LAYOUT_PREFERENCE_VERSION,
        "grids": grids,
        "containers": containers,
        "blocks": blocks,
    }


def user_print_layout_preferences(user: User | None) -> dict[str, dict[str, Any]]:
    raw_preferences = (
        load_json_object(user.print_layout_preferences_json)
        if user is not None
        else {}
    )
    raw_profiles = raw_preferences.get("profiles") if isinstance(raw_preferences.get("profiles"), dict) else {}
    profiles: dict[str, dict[str, Any]] = {}
    for raw_key, raw_preference in raw_profiles.items():
        profile_key = compact_text(raw_key)
        preference = normalize_print_layout_preference(raw_preference)
        if profile_key and (preference["grids"] or preference["containers"] or preference["blocks"]):
            profiles[profile_key] = preference
    return profiles


def user_print_layout_preference(
    user: User | None,
    *,
    form_id: int,
    template_id: Any,
    paper_size: Any,
) -> dict[str, Any]:
    profile_key = print_layout_profile_key(form_id, template_id, paper_size)
    return user_print_layout_preferences(user).get(
        profile_key,
        normalize_print_layout_preference({}),
    )


def save_user_print_layout_preference(
    session: Session,
    user: User,
    *,
    form_id: int,
    template_id: Any,
    paper_size: Any,
    preference: Any,
    commit: bool = True,
) -> dict[str, Any]:
    profile_key = print_layout_profile_key(form_id, template_id, paper_size)
    profiles = user_print_layout_preferences(user)
    normalized_preference = normalize_print_layout_preference(preference)
    if normalized_preference["grids"] or normalized_preference["containers"] or normalized_preference["blocks"]:
        profiles[profile_key] = normalized_preference
    else:
        profiles.pop(profile_key, None)
    user.print_layout_preferences_json = json.dumps(
        {
            "version": PRINT_LAYOUT_PREFERENCE_VERSION,
            "profiles": profiles,
        },
        ensure_ascii=False,
    )
    if commit:
        save_user(session, user)
    else:
        session.add(user)
    return normalized_preference


def print_layout_default_profile_key(template_id: Any, paper_size: Any) -> str:
    return ":".join(
        [
            normalize_print_template_id(template_id),
            normalize_print_paper_size(paper_size),
        ]
    )


def normalize_form_print_layout_defaults(value: Any) -> dict[str, Any]:
    raw_defaults = value if isinstance(value, dict) else {}
    raw_profiles = raw_defaults.get("profiles") if isinstance(raw_defaults.get("profiles"), dict) else {}
    profiles: dict[str, dict[str, Any]] = {}

    for raw_key, raw_layout in raw_profiles.items():
        key = compact_text(raw_key)
        parts = key.split(":", 1)
        if len(parts) != 2:
            continue
        profile_key = print_layout_default_profile_key(parts[0], parts[1])
        preference = normalize_print_layout_preference(raw_layout)
        if preference["grids"] or preference["containers"] or preference["blocks"]:
            profiles[profile_key] = preference

    return {
        "version": FORM_PRINT_LAYOUT_DEFAULTS_VERSION,
        "profiles": profiles,
    }


def form_version_print_layout_defaults(form_version: FormVersion) -> dict[str, Any]:
    block_schema, _ = load_block_storage_document(form_version)
    meta = block_schema.get("meta") if isinstance(block_schema.get("meta"), dict) else {}
    return normalize_form_print_layout_defaults(meta.get("print_layout_defaults"))


def form_version_print_layout_preference(
    form_version: FormVersion,
    *,
    template_id: Any,
    paper_size: Any,
) -> dict[str, Any]:
    profile_key = print_layout_default_profile_key(template_id, paper_size)
    return form_version_print_layout_defaults(form_version)["profiles"].get(
        profile_key,
        normalize_print_layout_preference({}),
    )


def record_print_presentation_for_record(record: Record) -> RecordPrintPresentation | None:
    return record.print_presentation


def record_print_presentation_profile(
    presentation: RecordPrintPresentation,
) -> dict[str, Any]:
    return normalize_print_profile(
        template_id=presentation.template_id,
        text_size=presentation.text_size,
        paper_size=presentation.paper_size,
    )


def serialize_record_print_presentation(
    presentation: RecordPrintPresentation | None,
) -> dict[str, Any] | None:
    if presentation is None:
        return None
    profile = record_print_presentation_profile(presentation)
    saved_by = presentation.saved_by_user
    return {
        "id": presentation.id,
        "record_id": presentation.record_id,
        "form_version_id": presentation.form_version_id,
        "template_id": profile["template_id"],
        "style": profile["style"],
        "orientation": profile["orientation"],
        "text_size": profile["text_size"],
        "paper_size": profile["paper_size"],
        "layout": normalize_print_layout_preference(load_json_object(presentation.layout_json)),
        "saved_by": {
            "id": saved_by.id,
            "full_name": saved_by.full_name,
        } if saved_by is not None else None,
        "saved_at": presentation.updated_at.astimezone(timezone.utc).isoformat(),
    }


def user_can_manage_record_print_presentation(record: Record, user: User | None) -> bool:
    if user is None:
        return False
    return user.role == "admin" or record.created_by_user_id == user.id


def apply_record_print_presentation(
    session: Session,
    record: Record,
    *,
    user: User | None,
    profile: dict[str, Any],
    layout: Any,
) -> RecordPrintPresentation:
    presentation = record_print_presentation_for_record(record)
    if presentation is None:
        presentation = RecordPrintPresentation(
            record_id=record.id,
            form_version_id=record.form_version_id,
            template_id=profile["template_id"],
            text_size=profile["text_size"],
            paper_size=profile["paper_size"],
            layout_json="{}",
            saved_by_user_id=user.id if user is not None else None,
        )
    else:
        presentation.form_version_id = record.form_version_id
        presentation.template_id = profile["template_id"]
        presentation.text_size = profile["text_size"]
        presentation.paper_size = profile["paper_size"]
        presentation.saved_by_user_id = user.id if user is not None else None

    presentation.layout_json = json.dumps(
        normalize_print_layout_preference(layout),
        ensure_ascii=False,
    )
    session.add(presentation)
    return presentation


def snapshot_completed_record_print_presentation(
    session: Session,
    record: Record,
    *,
    user: User | None,
) -> RecordPrintPresentation:
    profile = user_print_preferences(user)
    form_layout = form_version_print_layout_preference(
        record.form_version,
        template_id=profile["template_id"],
        paper_size=profile["paper_size"],
    )
    personal_layout = user_print_layout_preference(
        user,
        form_id=record.form_id,
        template_id=profile["template_id"],
        paper_size=profile["paper_size"],
    )
    layout = personal_layout if any(personal_layout[key] for key in ("grids", "containers", "blocks")) else form_layout
    return apply_record_print_presentation(
        session,
        record,
        user=user,
        profile=profile,
        layout=layout,
    )


def save_record_print_presentation(
    session: Session,
    record: Record,
    *,
    user: User,
    profile: dict[str, Any],
    layout: Any,
) -> dict[str, Any]:
    presentation = apply_record_print_presentation(
        session,
        record,
        user=user,
        profile=profile,
        layout=layout,
    )
    session.commit()
    session.refresh(presentation)
    return serialize_record_print_presentation(presentation) or {}


def clear_record_print_presentation(session: Session, record: Record) -> bool:
    presentation = record_print_presentation_for_record(record)
    if presentation is None:
        return False
    session.delete(presentation)
    session.commit()
    return True


def effective_record_print_presentation(
    record: Record,
    *,
    fallback_profile: dict[str, Any],
    use_record_presentation: bool = True,
) -> dict[str, Any]:
    presentation = record_print_presentation_for_record(record)
    if presentation is not None and use_record_presentation:
        return {
            "profile": record_print_presentation_profile(presentation),
            "layout": normalize_print_layout_preference(load_json_object(presentation.layout_json)),
            "source": "record",
            "presentation": serialize_record_print_presentation(presentation),
        }

    layout = form_version_print_layout_preference(
        record.form_version,
        template_id=fallback_profile["template_id"],
        paper_size=fallback_profile["paper_size"],
    )
    has_default = bool(layout["grids"] or layout["containers"] or layout["blocks"])
    return {
        "profile": fallback_profile,
        "layout": layout,
        "source": "form_default" if has_default else "automatic",
        "presentation": None,
    }


def get_or_create_clinic_profile(session: Session) -> ClinicProfile:
    profile = session.scalar(select(ClinicProfile).limit(1))
    if profile is not None:
        return profile
    profile = ClinicProfile(clinic_name="")
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def serialize_clinic_profile(profile: ClinicProfile) -> dict[str, Any]:
    return {
        "id": profile.id,
        "clinic_name": compact_text(profile.clinic_name),
        "address": compact_text(profile.address),
        "contact_number": compact_text(profile.contact_number),
        "contact_email": compact_text(profile.contact_email),
        "doh_license_number": compact_text(profile.doh_license_number),
        "logo_path": profile.logo_path,
        "logo_original_filename": compact_text(profile.logo_original_filename),
        "logo_mime_type": compact_text(profile.logo_mime_type),
        "has_logo": bool(compact_text(profile.logo_path)),
        "created_at": profile.created_at.astimezone(timezone.utc).isoformat(),
        "updated_at": profile.updated_at.astimezone(timezone.utc).isoformat(),
    }


def get_clinic_profile(session: Session) -> dict[str, Any]:
    return serialize_clinic_profile(get_or_create_clinic_profile(session))


def list_users(session: Session, *, status: str | None = None) -> list[dict[str, Any]]:
    query = select(User).order_by(User.created_at.desc(), User.id.desc())
    normalized_status = validate_user_status(status) if compact_text(status) else ""
    if normalized_status:
        query = query.where(User.status == normalized_status)
    users = session.scalars(query).all()
    return [serialize_user(user) for user in users]


def count_users(session: Session, *, status: str | None = None) -> int:
    query = select(func.count(User.id))
    normalized_status = validate_user_status(status) if compact_text(status) else ""
    if normalized_status:
        query = query.where(User.status == normalized_status)
    return int(session.scalar(query) or 0)


def save_user(session: Session, user: User) -> User:
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ValueError("This email or login ID is already in use.") from exc
    session.refresh(user)
    return user


def request_account(session: Session, payload: AccountRequestPayload) -> dict[str, Any]:
    full_name = compact_text(payload.full_name)
    email = normalize_email(payload.email)
    validate_password_strength(payload.password)
    if not full_name:
        raise ValueError("Enter the staff member's full name.")
    if not validate_email_format(email):
        raise ValueError("Enter a valid email address.")
    login_id = next_available_login_id(
        session,
        derive_login_id(full_name=full_name, email=email, requested_login_id=payload.login_id or ""),
    )
    user = User(
        email=email,
        login_id=login_id,
        full_name=full_name,
        role="medtech",
        status="pending",
        password_hash=password_hash_value(payload.password),
        must_change_password=False,
    )
    return serialize_user(save_user(session, user))


def create_initial_admin(session: Session, payload: SetupAdminPayload) -> dict[str, Any]:
    if has_any_users(session):
        raise ValueError("Initial setup is already complete.")
    full_name = compact_text(payload.full_name)
    email = normalize_email(payload.email)
    validate_password_strength(payload.password)
    if not full_name:
        raise ValueError("Enter the admin's full name.")
    if not validate_email_format(email):
        raise ValueError("Enter a valid email address.")
    login_id = next_available_login_id(
        session,
        derive_login_id(full_name=full_name, email=email, requested_login_id=payload.login_id or ""),
    )
    user = User(
        email=email,
        login_id=login_id,
        full_name=full_name,
        role="admin",
        status="active",
        password_hash=password_hash_value(payload.password),
        must_change_password=False,
    )
    return serialize_user(save_user(session, user))


def create_user_account(session: Session, payload: UserCreatePayload) -> dict[str, Any]:
    full_name = compact_text(payload.full_name)
    email = normalize_email(payload.email)
    validate_password_strength(payload.password)
    if not full_name:
        raise ValueError("Enter the staff member's full name.")
    if not validate_email_format(email):
        raise ValueError("Enter a valid email address.")
    login_id = next_available_login_id(
        session,
        derive_login_id(full_name=full_name, email=email, requested_login_id=payload.login_id or ""),
    )
    user = User(
        email=email,
        login_id=login_id,
        full_name=full_name,
        role=validate_role(payload.role),
        status="active",
        password_hash=password_hash_value(payload.password),
        must_change_password=True,
    )
    return serialize_user(save_user(session, user))


def approve_user_account(session: Session, user_id: int, *, role: str) -> dict[str, Any]:
    user = get_user_or_none(session, user_id)
    if user is None:
        raise KeyError(user_id)
    user.role = validate_role(role)
    user.status = "active"
    return serialize_user(save_user(session, user))


def update_user_status(session: Session, user_id: int, *, status: str) -> dict[str, Any]:
    user = get_user_or_none(session, user_id)
    if user is None:
        raise KeyError(user_id)
    next_status = validate_user_status(status)
    if next_status == "disabled" and user.role == "admin" and user.status == "active" and count_active_admin_users(session) <= 1:
        raise ValueError("Keep at least one active admin account.")
    user.status = next_status
    return serialize_user(save_user(session, user))


def update_user_admin_details(
    session: Session,
    user_id: int,
    *,
    full_name: str,
    role: str,
) -> dict[str, Any]:
    user = get_user_or_none(session, user_id)
    if user is None:
        raise KeyError(user_id)
    resolved_name = compact_text(full_name)
    if not resolved_name:
        raise ValueError("Enter the staff member's full name.")
    next_role = validate_role(role)
    if (
        user.role == "admin"
        and user.status == "active"
        and next_role != "admin"
        and count_active_admin_users(session) <= 1
    ):
        raise ValueError("Keep at least one active admin account.")
    user.full_name = resolved_name
    user.role = next_role
    return serialize_user(save_user(session, user))


def reset_user_password_by_admin(
    session: Session,
    user_id: int,
    *,
    temporary_password: str,
) -> dict[str, Any]:
    user = get_user_or_none(session, user_id)
    if user is None:
        raise KeyError(user_id)
    validate_password_strength(temporary_password)
    user.password_hash = password_hash_value(temporary_password)
    user.must_change_password = True
    return serialize_user(save_user(session, user))


def authenticate_user(session: Session, payload: LoginPayload) -> dict[str, Any]:
    user = get_user_by_identifier(session, payload.identifier)
    if user is None:
        raise ValueError("The email or login ID and password do not match.")
    if not verify_password_hash(user.password_hash, payload.password):
        raise ValueError("The email or login ID and password do not match.")
    if user.status == "pending":
        raise ValueError("This account is still waiting for admin approval.")
    if user.status == "disabled":
        raise ValueError("This account is currently disabled. Ask an admin for access.")
    if user.status != "active":
        raise ValueError("This account is not active yet.")
    return serialize_user(user)


def change_user_password(
    session: Session,
    user_id: int,
    payload: PasswordChangePayload,
    *,
    require_current_password: bool = True,
) -> dict[str, Any]:
    user = get_user_or_none(session, user_id)
    if user is None:
        raise KeyError(user_id)
    if require_current_password and not verify_password_hash(user.password_hash, payload.current_password):
        raise ValueError("The current password is incorrect.")
    validate_password_strength(payload.new_password)
    user.password_hash = password_hash_value(payload.new_password)
    user.must_change_password = False
    return serialize_user(save_user(session, user))


def normalize_items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def normalize_notes(raw_notes: Any) -> list[str]:
    notes: list[str] = []
    for note in raw_notes or []:
        text = compact_text(note)
        if text and text not in notes:
            notes.append(text)
    return notes


def unique_key(base: str, used: set[str]) -> str:
    key = slugify(base)
    candidate = key
    suffix = 2
    while candidate in used:
        candidate = f"{key}_{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def normalize_options(raw_options: Any, field_id: str) -> list[dict[str, Any]]:
    options = raw_options or []
    normalized: list[dict[str, Any]] = []
    used: set[str] = set()

    for index, option in enumerate(options, start=1):
        if isinstance(option, dict):
            name = compact_text(option.get("name"))
            key_source = compact_text(option.get("key")) or name
        else:
            name = compact_text(option)
            key_source = name
        if not name:
            continue
        key = unique_key(key_source, used)
        normalized.append(
            {
                "id": f"{field_id}.{key}",
                "key": key,
                "name": name,
                "order": index,
                "is_normal": bool(option.get("is_normal")) if isinstance(option, dict) else False,
            }
        )

    return normalized


def normalize_field(field: dict[str, Any], parent_id: str, order: int, used_keys: set[str]) -> dict[str, Any]:
    name = compact_text(field.get("name")) or f"Untitled Field {order}"
    key = unique_key(compact_text(field.get("key")) or name, used_keys)
    field_id = f"{parent_id}.{key}"
    kind = "field_group" if compact_text(field.get("kind")) == "field_group" else "field"

    normalized: dict[str, Any] = {
        "id": field_id,
        "key": key,
        "name": name,
        "kind": kind,
        "order": order,
    }

    notes = normalize_notes(field.get("notes"))
    if notes:
        normalized["notes"] = notes

    source = field.get("source")
    if isinstance(source, dict) and source:
        normalized["source"] = source

    if kind == "field_group":
        child_used: set[str] = set()
        normalized["fields"] = [
            normalize_field(child, field_id, child_order, child_used)
            for child_order, child in enumerate(field.get("fields") or [], start=1)
            if isinstance(child, dict)
        ]
        return normalized

    options = normalize_options(field.get("options"), field_id)
    control = compact_text(field.get("control")) or ("select" if options else "input")
    data_type = compact_text(field.get("data_type")) or ("enum" if control == "select" else "text")

    normalized["control"] = control
    normalized["data_type"] = data_type
    if bool(field.get("required")):
        normalized["required"] = True

    default_value_mode = normalize_temporal_default_mode(field.get("default_value_mode"), data_type)
    if default_value_mode:
        normalized["default_value_mode"] = default_value_mode

    unit_hint = compact_text(field.get("unit_hint"))
    if unit_hint:
        normalized["unit_hint"] = unit_hint

    reference_text = compact_text(field.get("reference_text") or field.get("normal_value"))
    if reference_text:
        normalized["reference_text"] = reference_text
        normalized["normal_value"] = reference_text

    normal_min = compact_text(field.get("normal_min"))
    if normal_min:
        normalized["normal_min"] = normal_min

    normal_max = compact_text(field.get("normal_max"))
    if normal_max:
        normalized["normal_max"] = normal_max
    if normal_min and not normalize_boolean_setting(field.get("normal_min_inclusive"), default=True):
        normalized["normal_min_inclusive"] = False
    if normal_max and not normalize_boolean_setting(field.get("normal_max_inclusive"), default=True):
        normalized["normal_max_inclusive"] = False

    if options:
        normalized["options"] = options

    return normalized


def normalize_section(section: dict[str, Any], form_id: str, order: int, used_keys: set[str]) -> dict[str, Any]:
    name = compact_text(section.get("name")) or f"Untitled Section {order}"
    key = unique_key(compact_text(section.get("key")) or name, used_keys)
    section_id = f"{form_id}.{key}"
    field_used: set[str] = set()

    normalized: dict[str, Any] = {
        "id": section_id,
        "key": key,
        "name": name,
        "order": order,
        "fields": [
            normalize_field(field, section_id, field_order, field_used)
            for field_order, field in enumerate(section.get("fields") or [], start=1)
            if isinstance(field, dict)
        ],
    }

    notes = normalize_notes(section.get("notes"))
    if notes:
        normalized["notes"] = notes

    source = section.get("source")
    if isinstance(source, dict) and source:
        normalized["source"] = source

    return normalized


def normalize_signatory_option(raw_option: Any, index: int, slot_id: str) -> dict[str, Any] | None:
    option = raw_option if isinstance(raw_option, dict) else {"name": raw_option}
    name = compact_text(option.get("name"))
    if not name:
        return None
    key = slugify(compact_text(option.get("key")) or compact_text(option.get("id")) or name)
    option_id = compact_text(option.get("id")) or f"{slot_id}.{key}"
    license_text = compact_text(option.get("license") or option.get("license_no") or option.get("license_number"))
    if license_text.lower().startswith("lic. no:"):
        license_text = compact_text(license_text.split(":", 1)[1])
    return {
        "id": option_id,
        "key": key,
        "name": name,
        "title": compact_text(option.get("title")),
        "license": license_text,
        "order": int(option.get("order") or index),
    }


def default_signatory_options(slot_id: str, people: list[dict[str, str]]) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    for index, person in enumerate(people, start=1):
        option = normalize_signatory_option(person, index, slot_id)
        if option is not None:
            options.append(option)
    return options


def default_signatory_slots() -> list[dict[str, Any]]:
    medtech_1_options = default_signatory_options("medical_technologist_1", DEFAULT_MEDTECH_SIGNATORY_PEOPLE)
    medtech_2_options = default_signatory_options("medical_technologist_2", DEFAULT_MEDTECH_SIGNATORY_PEOPLE)
    return [
        {
            "id": "medical_technologist_1",
            "label": "Analyzed by:",
            "designation": "Medical Technologist (RMT)",
            "input_type": "person_dropdown",
            "required": True,
            "show_on_print": True,
            "show_license": True,
            "signature_line": True,
            "default_option_id": "",
            "options": medtech_1_options,
        },
        {
            "id": "medical_technologist_2",
            "label": "Verified by:",
            "designation": "Medical Technologist (RMT)",
            "input_type": "person_dropdown",
            "required": True,
            "show_on_print": True,
            "show_license": True,
            "signature_line": True,
            "default_option_id": "",
            "options": medtech_2_options,
        },
        {
            "id": "pathologist",
            "label": "Noted by:",
            "designation": "Pathologist",
            "input_type": "stamp_image",
            "required": False,
            "show_on_print": True,
            "show_license": False,
            "signature_line": True,
            "default_option_id": "",
            "stamp_image_url": DEFAULT_PATHOLOGIST_STAMP_URL,
            "stamp_image_filename": DEFAULT_PATHOLOGIST_STAMP_FILENAME,
            "stamp_image_mime_type": "image/png",
            "options": [],
        },
    ]


def normalize_signatory_slot(raw_slot: Any, index: int) -> dict[str, Any] | None:
    slot = raw_slot if isinstance(raw_slot, dict) else {}
    label = compact_text(slot.get("label")) or f"Signatory {index}"
    slot_id = slugify(compact_text(slot.get("id")) or compact_text(slot.get("key")) or label)
    input_type = compact_text(slot.get("input_type")).lower()
    if input_type not in SIGNATORY_INPUT_TYPES:
        input_type = "person_dropdown"
    options = [
        option
        for option in (
            normalize_signatory_option(option, option_index, slot_id)
            for option_index, option in enumerate(normalize_items(slot.get("options")), start=1)
        )
        if option is not None
    ]
    default_option_id = compact_text(slot.get("default_option_id"))
    if default_option_id and all(compact_text(option.get("id")) != default_option_id for option in options):
        default_option_id = ""
    if input_type == "fixed" and not default_option_id and options:
        default_option_id = compact_text(options[0].get("id"))
    return {
        "id": slot_id,
        "label": label,
        "designation": compact_text(slot.get("designation")) or compact_text(slot.get("title")),
        "input_type": input_type,
        "required": normalize_boolean_setting(slot.get("required"), default=False),
        "show_on_print": normalize_boolean_setting(slot.get("show_on_print"), default=True),
        "show_license": normalize_boolean_setting(slot.get("show_license"), default=True),
        "signature_line": normalize_boolean_setting(slot.get("signature_line"), default=True),
        "default_option_id": default_option_id,
        "manual_name": compact_text(slot.get("manual_name")),
        "manual_title": compact_text(slot.get("manual_title")),
        "manual_license": compact_text(slot.get("manual_license")),
        "stamp_image_url": compact_text(slot.get("stamp_image_url")),
        "stamp_image_filename": compact_text(slot.get("stamp_image_filename")),
        "stamp_image_mime_type": compact_text(slot.get("stamp_image_mime_type")),
        "options": options,
    }


def normalize_signatory_slots(raw_slots: Any, *, use_defaults: bool = False) -> list[dict[str, Any]]:
    if not isinstance(raw_slots, list):
        return default_signatory_slots() if use_defaults else []
    slots = [
        slot
        for slot in (
            normalize_signatory_slot(slot, index)
            for index, slot in enumerate(raw_slots, start=1)
        )
        if slot is not None
    ]
    return slots


def merge_client_signatory_defaults(raw_slots: Any) -> list[dict[str, Any]]:
    defaults = default_signatory_slots()
    existing = normalize_signatory_slots(raw_slots, use_defaults=False)
    by_id = {compact_text(slot.get("id")): slot for slot in existing}
    merged: list[dict[str, Any]] = []
    for default in defaults:
        current = by_id.pop(default["id"], None)
        if current is None:
            merged.append(default)
            continue
        preserved_stamp = {
            key: current.get(key)
            for key in ("stamp_image_url", "stamp_image_filename", "stamp_image_mime_type")
            if compact_text(current.get(key))
        }
        next_slot = {**current, **default}
        if default["id"] == "pathologist" and preserved_stamp:
            next_slot.update(preserved_stamp)
        merged.append(normalize_signatory_slot(next_slot, len(merged) + 1))
    merged.extend(by_id.values())
    return merged


def signatory_option_by_id(slot: dict[str, Any], option_id: str) -> dict[str, Any] | None:
    target_id = compact_text(option_id)
    for option in normalize_items(slot.get("options")):
        if isinstance(option, dict) and compact_text(option.get("id")) == target_id:
            return option
    return None


def build_signatory_snapshot(slot: dict[str, Any], raw_value: Any = None) -> dict[str, Any]:
    value = raw_value if isinstance(raw_value, dict) else {}
    input_type = compact_text(slot.get("input_type")).lower()
    option_id = compact_text(value.get("option_id"))
    if not option_id and input_type == "fixed":
        option_id = compact_text(slot.get("default_option_id"))
    option = signatory_option_by_id(slot, option_id) if option_id else None

    name = compact_text(value.get("name"))
    title = compact_text(value.get("title"))
    license_text = compact_text(value.get("license"))
    if option is not None:
        name = compact_text(option.get("name"))
        title = compact_text(option.get("title"))
        license_text = compact_text(option.get("license"))
        option_id = compact_text(option.get("id"))
    elif input_type in {"fixed", "manual"}:
        name = compact_text(slot.get("manual_name"))
        title = compact_text(slot.get("manual_title"))
        license_text = compact_text(slot.get("manual_license"))

    return {
        "slot_id": compact_text(slot.get("id")),
        "label": compact_text(slot.get("label")) or "Signatory",
        "designation": compact_text(slot.get("designation")) or compact_text(slot.get("title")),
        "input_type": input_type if input_type in SIGNATORY_INPUT_TYPES else "person_dropdown",
        "option_id": option_id,
        "name": name,
        "title": title,
        "license": license_text,
        "required": normalize_boolean_setting(slot.get("required"), default=False),
        "show_on_print": normalize_boolean_setting(slot.get("show_on_print"), default=True),
        "show_license": normalize_boolean_setting(slot.get("show_license"), default=True),
        "signature_line": normalize_boolean_setting(slot.get("signature_line"), default=True),
        "stamp_image_url": compact_text(slot.get("stamp_image_url")),
        "stamp_image_filename": compact_text(slot.get("stamp_image_filename")),
        "stamp_image_mime_type": compact_text(slot.get("stamp_image_mime_type")),
    }


def normalize_record_signatory_snapshots(raw_signatories: Any, slots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    raw_map: dict[str, Any] = {}
    if isinstance(raw_signatories, dict):
        raw_map = raw_signatories
    elif isinstance(raw_signatories, list):
        raw_map = {
            compact_text(item.get("slot_id")): item
            for item in raw_signatories
            if isinstance(item, dict) and compact_text(item.get("slot_id"))
        }

    snapshots: list[dict[str, Any]] = []
    for slot in slots:
        slot_id = compact_text(slot.get("id"))
        if not slot_id:
            continue
        snapshots.append(build_signatory_snapshot(slot, raw_map.get(slot_id)))
    return snapshots


def signatory_snapshots_for_print(snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    printable: list[dict[str, Any]] = []
    for snapshot in snapshots:
        if not isinstance(snapshot, dict):
            continue
        if not normalize_boolean_setting(snapshot.get("show_on_print"), default=True):
            continue
        input_type = compact_text(snapshot.get("input_type")).lower()
        required = normalize_boolean_setting(snapshot.get("required"), default=False)
        designation = compact_text(snapshot.get("designation")) or compact_text(snapshot.get("title"))
        name = compact_text(snapshot.get("name"))
        license_text = compact_text(snapshot.get("license"))
        stamp_image_url = compact_text(snapshot.get("stamp_image_url"))
        if input_type == "stamp_image":
            if not stamp_image_url:
                continue
            printable.append(
                {
                    "label": compact_text(snapshot.get("label")) or "Signatory",
                    "designation": designation,
                    "name": "",
                    "title": "",
                    "license": "",
                    "signature_line": normalize_boolean_setting(snapshot.get("signature_line"), default=True),
                    "image_url": stamp_image_url,
                    "image_alt": compact_text(snapshot.get("stamp_image_filename"))
                    or compact_text(snapshot.get("label"))
                    or "Signatory stamp",
                }
            )
            continue
        if not name and not normalize_boolean_setting(snapshot.get("signature_line"), default=True):
            continue
        if not name and not license_text and input_type != "blank" and not required:
            continue
        printable.append(
            {
                "label": compact_text(snapshot.get("label")) or "Signatory",
                "designation": designation,
                "name": name,
                "title": compact_text(snapshot.get("title")),
                "license": license_text if normalize_boolean_setting(snapshot.get("show_license"), default=True) else "",
                "signature_line": normalize_boolean_setting(snapshot.get("signature_line"), default=True),
                "image_url": "",
                "image_alt": "",
            }
        )
    return printable


def reference_common_field_set(field_set_id: str) -> dict[str, Any]:
    target_id = compact_text(field_set_id)
    for field_set in normalize_items(load_reference_schema().get("common_field_sets")):
        if isinstance(field_set, dict) and compact_text(field_set.get("id")) == target_id:
            return field_set
    return {}


def default_patient_info_legacy_group() -> dict[str, Any]:
    field_set = reference_common_field_set(DEFAULT_LAB_REQUEST_FIELD_SET_ID)
    fields: list[dict[str, Any]] = []

    for raw_field in normalize_items(field_set.get("fields")):
        if not isinstance(raw_field, dict):
            continue
        key = compact_text(raw_field.get("key"))
        name = compact_text(raw_field.get("name"))
        if not key or not name:
            continue
        if key in SIGNATORY_FIELD_KEYS:
            continue

        data_type = compact_text(raw_field.get("data_type")) or "text"
        if key == "date_or_datetime":
            data_type = "datetime"

        field: dict[str, Any] = {
            "key": key,
            "name": name,
            "kind": "field",
            "control": compact_text(raw_field.get("control")) or "input",
            "data_type": data_type,
            "source": {
                "common_field_set_id": DEFAULT_LAB_REQUEST_FIELD_SET_ID,
                "common_field_id": compact_text(raw_field.get("id")),
            },
        }
        options = normalize_options(raw_field.get("options"), f"{PATIENT_INFO_GROUP_KEY}.{key}")
        if options:
            field["options"] = options
        if key in PATIENT_INFO_REQUIRED_KEYS:
            field["required"] = True
        fields.append(field)

    return {
        "key": PATIENT_INFO_GROUP_KEY,
        "name": PATIENT_INFO_GROUP_NAME,
        "kind": "field_group",
        "source": {"common_field_set_id": DEFAULT_LAB_REQUEST_FIELD_SET_ID},
        "fields": fields,
    }


def legacy_schema_has_default_patient_info(raw_schema: dict[str, Any]) -> bool:
    for field in normalize_items(raw_schema.get("fields")):
        if not isinstance(field, dict):
            continue
        if compact_text(field.get("key")) == PATIENT_INFO_GROUP_KEY:
            return True
        if compact_text(field.get("name")).lower() == PATIENT_INFO_GROUP_NAME.lower():
            return True
    return False


def materialize_default_patient_info_fields(raw_schema: dict[str, Any]) -> dict[str, Any]:
    schema = raw_schema if isinstance(raw_schema, dict) else {}
    if compact_text(schema.get("common_field_set_id")) != DEFAULT_LAB_REQUEST_FIELD_SET_ID:
        return schema
    if legacy_schema_has_default_patient_info(schema):
        return schema

    materialized = json.loads(json.dumps(schema))
    materialized["fields"] = [
        default_patient_info_legacy_group(),
        *normalize_items(materialized.get("fields")),
    ]
    return materialized


def legacy_field_to_block(field: dict[str, Any]) -> dict[str, Any]:
    field_id = compact_text(field.get("id")) or f"blk_{slugify(field.get('name') or 'field')}"
    kind = "container" if compact_text(field.get("kind")) == "field_group" else "field"
    props: dict[str, Any] = {
        "key": compact_text(field.get("key")) or slugify(field.get("name") or field_id),
        "order": int(field.get("order") or 1),
    }

    notes = normalize_notes(field.get("notes"))
    if notes:
        props["notes"] = notes

    source = field.get("source")
    if isinstance(source, dict) and source:
        props["source"] = source

    if kind == "container":
        return {
            "id": field_id,
            "kind": "container",
            "name": compact_text(field.get("name")) or "Untitled Container",
            "props": props,
            "children": [
                legacy_field_to_block(child)
                for child in normalize_items(field.get("fields"))
                if isinstance(child, dict)
            ],
        }

    props["control"] = compact_text(field.get("control")) or "input"
    props["data_type"] = compact_text(field.get("data_type")) or "text"
    props["required"] = bool(field.get("required") or False)

    default_value_mode = normalize_temporal_default_mode(field.get("default_value_mode"), props["data_type"])
    if default_value_mode:
        props["default_value_mode"] = default_value_mode

    unit_hint = compact_text(field.get("unit_hint"))
    if unit_hint:
        props["unit_hint"] = unit_hint

    reference_text = compact_text(field.get("reference_text") or field.get("normal_value"))
    if reference_text:
        props["reference_text"] = reference_text

    normal_min = compact_text(field.get("normal_min"))
    if normal_min:
        props["normal_min"] = normal_min

    normal_max = compact_text(field.get("normal_max"))
    if normal_max:
        props["normal_max"] = normal_max
    if normal_min and not normalize_boolean_setting(field.get("normal_min_inclusive"), default=True):
        props["normal_min_inclusive"] = False
    if normal_max and not normalize_boolean_setting(field.get("normal_max_inclusive"), default=True):
        props["normal_max_inclusive"] = False

    options = []
    for option in normalize_items(field.get("options")):
        if not isinstance(option, dict):
            continue
        name = compact_text(option.get("name"))
        if not name:
            continue
        options.append(
            {
                "id": compact_text(option.get("id")) or f"{field_id}.{slugify(name)}",
                "key": compact_text(option.get("key")) or slugify(name),
                "name": name,
                "order": int(option.get("order") or len(options) + 1),
                "is_normal": bool(option.get("is_normal")),
            }
        )
    if options:
        props["options"] = options

    return {
        "id": field_id,
        "kind": "field",
        "name": compact_text(field.get("name")) or "Untitled Field",
        "props": props,
        "children": [],
    }


def legacy_section_to_block(section: dict[str, Any]) -> dict[str, Any]:
    section_id = compact_text(section.get("id")) or f"blk_{slugify(section.get('name') or 'section')}"
    props: dict[str, Any] = {
        "key": compact_text(section.get("key")) or slugify(section.get("name") or section_id),
        "order": int(section.get("order") or 1),
    }

    notes = normalize_notes(section.get("notes"))
    if notes:
        props["notes"] = notes

    source = section.get("source")
    if isinstance(source, dict) and source:
        props["source"] = source

    return {
        "id": section_id,
        "kind": "container",
        "name": compact_text(section.get("name")) or "Untitled Container",
        "props": props,
        "children": [
            legacy_field_to_block(field)
            for field in normalize_items(section.get("fields"))
            if isinstance(field, dict)
        ],
    }


def build_block_schema_from_legacy_storage(raw_schema: dict[str, Any]) -> dict[str, Any]:
    raw_schema = materialize_default_patient_info_fields(raw_schema)
    meta: dict[str, Any] = {
        "form_id": compact_text(raw_schema.get("id")),
        "form_key": compact_text(raw_schema.get("key")),
        "form_order": int(raw_schema.get("order") or 1),
    }

    notes = normalize_notes(raw_schema.get("notes"))
    if notes:
        meta["notes"] = notes

    source = raw_schema.get("source")
    if isinstance(source, dict) and source:
        meta["source"] = source

    blocks = [
        *[
            legacy_field_to_block(field)
            for field in normalize_items(raw_schema.get("fields"))
            if isinstance(field, dict)
        ],
        *[
            legacy_section_to_block(section)
            for section in normalize_items(raw_schema.get("sections"))
            if isinstance(section, dict)
        ],
    ]

    block_schema = {
        "schema_version": CANONICAL_BLOCK_SCHEMA_VERSION,
        "source_kind": ACTIVE_BLOCK_SCHEMA_SOURCE,
        "meta": meta,
        "blocks": blocks,
    }
    if block_schema_has_default_patient_info(block_schema):
        meta[DEFAULT_PATIENT_INFO_MATERIALIZED_META_KEY] = True
        block_schema["meta"] = meta
    ensure_default_patient_info_identity(block_schema)
    return block_schema


def default_patient_info_field_id(form_id: str, field_key: str) -> str:
    return f"{compact_text(form_id)}.{PATIENT_INFO_GROUP_KEY}.{field_key}"


def block_schema_has_default_patient_info(block_schema: dict[str, Any]) -> bool:
    for block in normalize_items(block_schema.get("blocks")):
        if not isinstance(block, dict):
            continue
        props = block.get("props") if isinstance(block.get("props"), dict) else {}
        if compact_text(props.get("key")) == PATIENT_INFO_GROUP_KEY:
            return True
        if compact_text(block.get("name")).lower() == PATIENT_INFO_GROUP_NAME.lower():
            return True
    return False


def build_default_patient_info_block(form_id: str) -> dict[str, Any]:
    field_group = normalize_field(default_patient_info_legacy_group(), form_id, 1, set())
    return legacy_field_to_block(field_group)


def resequence_top_level_block_orders(blocks: list[dict[str, Any]]) -> None:
    for index, block in enumerate(blocks, start=1):
        if not isinstance(block, dict):
            continue
        props = block.get("props") if isinstance(block.get("props"), dict) else {}
        props["order"] = index
        block["props"] = props


def resequence_block_orders(blocks: list[Any]) -> None:
    for index, block in enumerate(blocks, start=1):
        if not isinstance(block, dict):
            continue
        props = block.get("props") if isinstance(block.get("props"), dict) else {}
        props["order"] = index
        block["props"] = props


def reference_form_slugs() -> set[str]:
    return {
        compact_text(form.get("key"))
        for group in normalize_items(load_reference_schema().get("groups"))
        if isinstance(group, dict)
        for form in normalize_items(group.get("forms"))
        if isinstance(form, dict) and compact_text(form.get("key"))
    }


def find_default_patient_info_block(block_schema: dict[str, Any]) -> dict[str, Any] | None:
    for block in normalize_items(block_schema.get("blocks")):
        if not isinstance(block, dict):
            continue
        props = block.get("props") if isinstance(block.get("props"), dict) else {}
        if compact_text(props.get("key")) == PATIENT_INFO_GROUP_KEY:
            return block
        if compact_text(block.get("name")).lower() == PATIENT_INFO_GROUP_NAME.lower():
            return block
    return None


def find_field_with_parent(
    blocks: list[Any],
    field_key: str,
) -> tuple[list[Any], dict[str, Any]] | None:
    for block in blocks:
        if not isinstance(block, dict):
            continue
        props = block.get("props") if isinstance(block.get("props"), dict) else {}
        if compact_text(block.get("kind")) == "field" and compact_text(props.get("key")) == field_key:
            return blocks, block

        children = block.get("children")
        if isinstance(children, list):
            match = find_field_with_parent(children, field_key)
            if match is not None:
                return match
    return None


def find_fields_by_key(blocks: list[Any], field_key: str) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        props = block.get("props") if isinstance(block.get("props"), dict) else {}
        if compact_text(block.get("kind")) == "field" and compact_text(props.get("key")) == field_key:
            fields.append(block)
        fields.extend(find_fields_by_key(normalize_items(block.get("children")), field_key))
    return fields


def patient_info_examination_insert_index(children: list[Any]) -> int:
    for index, child in enumerate(children):
        if not isinstance(child, dict):
            continue
        props = child.get("props") if isinstance(child.get("props"), dict) else {}
        if compact_text(props.get("key")) == "date_or_datetime":
            return index + 1
    return len(children)


def remove_empty_reference_details_container(
    block_schema: dict[str, Any],
    reference_slugs: set[str],
) -> bool:
    meta = block_schema.get("meta") if isinstance(block_schema.get("meta"), dict) else {}
    form_key = compact_text(meta.get("form_key"))
    form_id = compact_text(meta.get("form_id"))
    if form_key not in reference_slugs or not form_id:
        return False

    expected_id = f"{form_id}.details"
    blocks = normalize_items(block_schema.get("blocks"))
    for index, block in enumerate(blocks):
        if not isinstance(block, dict):
            continue
        props = block.get("props") if isinstance(block.get("props"), dict) else {}
        if (
            compact_text(block.get("kind")) == "container"
            and compact_text(block.get("id")) == expected_id
            and compact_text(props.get("key")) == "details"
            and not normalize_items(block.get("children"))
        ):
            blocks.pop(index)
            resequence_top_level_block_orders(blocks)
            return True
    return False


def ensure_reference_examination_in_patient_info(
    block_schema: dict[str, Any],
    reference_slugs: set[str],
) -> bool:
    if not isinstance(block_schema, dict):
        return False

    meta = block_schema.get("meta") if isinstance(block_schema.get("meta"), dict) else {}
    if compact_text(meta.get("form_key")) not in reference_slugs:
        return False

    details_container_removed = remove_empty_reference_details_container(
        block_schema,
        reference_slugs,
    )
    if meta.get(DEFAULT_EXAMINATION_IN_PATIENT_INFO_META_KEY) is True:
        return details_container_removed

    patient_info = find_default_patient_info_block(block_schema)
    if patient_info is None:
        return False

    patient_children = patient_info.get("children")
    if not isinstance(patient_children, list):
        patient_children = []
        patient_info["children"] = patient_children

    match = find_field_with_parent(normalize_items(block_schema.get("blocks")), "examination")
    if match is None:
        return False

    parent_children, examination = match
    if parent_children is not patient_children:
        parent_children.remove(examination)
        patient_children.insert(patient_info_examination_insert_index(patient_children), examination)
        resequence_block_orders(patient_children)

    remove_empty_reference_details_container(block_schema, reference_slugs)

    meta[DEFAULT_EXAMINATION_IN_PATIENT_INFO_META_KEY] = True
    block_schema["meta"] = meta
    return True


def find_top_level_block_by_key(blocks: list[Any], block_key: str) -> dict[str, Any] | None:
    for block in blocks:
        if not isinstance(block, dict):
            continue
        props = block.get("props") if isinstance(block.get("props"), dict) else {}
        if compact_text(props.get("key")) == block_key:
            return block
    return None


def configure_blood_gas_numeric_ranges(block_schema: dict[str, Any]) -> bool:
    changed = False
    for field_key, (normal_min, normal_max) in BLOOD_GAS_NUMERIC_RANGES.items():
        match = find_field_with_parent(normalize_items(block_schema.get("blocks")), field_key)
        if match is None:
            continue
        _, field = match
        props = field.get("props") if isinstance(field.get("props"), dict) else {}
        if compact_text(props.get("normal_min")) != normal_min:
            props["normal_min"] = normal_min
            changed = True
        if compact_text(props.get("normal_max")) != normal_max:
            props["normal_max"] = normal_max
            changed = True
        for property_name in ("reference_text", "normal_value"):
            if property_name in props:
                props.pop(property_name)
                changed = True
        field["props"] = props
    return changed


def configure_default_field_properties(
    block_schema: dict[str, Any],
    field_defaults: dict[str, dict[str, Any]],
) -> bool:
    changed = False
    for field_key, defaults in field_defaults.items():
        match = find_field_with_parent(normalize_items(block_schema.get("blocks")), field_key)
        if match is None:
            continue
        _, field = match
        props = field.get("props") if isinstance(field.get("props"), dict) else {}
        for property_name, expected_value in defaults.items():
            if expected_value is None:
                if property_name in props:
                    props.pop(property_name)
                    changed = True
                continue
            if isinstance(expected_value, bool):
                if normalize_boolean_setting(props.get(property_name), default=True) == expected_value:
                    continue
                props[property_name] = expected_value
                changed = True
                continue
            if compact_text(props.get(property_name)) == expected_value:
                continue
            props[property_name] = expected_value
            changed = True
        field["props"] = props
    return changed


def configure_container_field_properties(
    block_schema: dict[str, Any],
    container_field_defaults: dict[str, dict[str, dict[str, Any]]],
) -> bool:
    changed = False
    blocks = normalize_items(block_schema.get("blocks"))
    for container_key, field_defaults in container_field_defaults.items():
        container = find_top_level_block_by_key(blocks, container_key)
        if container is None:
            continue
        fields_by_key = {
            compact_text((child.get("props") or {}).get("key")): child
            for child in container.get("children") or []
            if isinstance(child, dict) and child.get("kind") == "field"
        }
        for field_key, defaults in field_defaults.items():
            field = fields_by_key.get(field_key)
            if field is None:
                continue
            props = field.get("props") if isinstance(field.get("props"), dict) else {}
            for property_name, expected_value in defaults.items():
                if expected_value is None:
                    if property_name in props:
                        props.pop(property_name)
                        changed = True
                    continue
                if isinstance(expected_value, bool):
                    if normalize_boolean_setting(props.get(property_name), default=True) == expected_value:
                        continue
                    props[property_name] = expected_value
                    changed = True
                    continue
                if compact_text(props.get(property_name)) == expected_value:
                    continue
                props[property_name] = expected_value
                changed = True
            field["props"] = props
    return changed


def configure_choice_field_normal_options(
    block_schema: dict[str, Any],
    choice_field_defaults: dict[str, tuple[str, ...]],
) -> bool | None:
    fields: list[tuple[dict[str, Any], set[str]]] = []
    for field_key, normal_names in choice_field_defaults.items():
        matching_fields = find_fields_by_key(normalize_items(block_schema.get("blocks")), field_key)
        if not matching_fields:
            return None
        wanted_names = {compact_text(name) for name in normal_names if compact_text(name)}
        for field in matching_fields:
            props = field.get("props") if isinstance(field.get("props"), dict) else {}
            options = normalize_items(props.get("options"))
            option_names = {
                compact_text(option.get("name"))
                for option in options
                if isinstance(option, dict) and compact_text(option.get("name"))
            }
            if not wanted_names or not wanted_names.issubset(option_names):
                return None
            fields.append((field, wanted_names))

    changed = False
    for field, wanted_names in fields:
        props = field.get("props") if isinstance(field.get("props"), dict) else {}
        for option in normalize_items(props.get("options")):
            if not isinstance(option, dict):
                continue
            expected = compact_text(option.get("name")) in wanted_names
            if bool(option.get("is_normal")) != expected:
                option["is_normal"] = expected
                changed = True
        field["props"] = props
    return changed


def ensure_default_image_field(
    block_schema: dict[str, Any],
    *,
    container: dict[str, Any],
    key: str,
    name: str,
    required: bool,
) -> bool:
    children = container.get("children") if isinstance(container.get("children"), list) else []
    if not isinstance(container.get("children"), list):
        container["children"] = children

    existing = next(
        (
            child
            for child in children
            if isinstance(child, dict)
            and child.get("kind") == "field"
            and compact_text((child.get("props") or {}).get("key")) == key
        ),
        None,
    )
    changed = False
    if existing is None:
        meta = block_schema.get("meta") if isinstance(block_schema.get("meta"), dict) else {}
        form_id = compact_text(meta.get("form_id"))
        if not form_id:
            return False
        existing = {
            "id": f"{form_id}.{compact_text((container.get('props') or {}).get('key'))}.{key}",
            "kind": "field",
            "name": name,
            "props": {
                "key": key,
                "order": len(children) + 1,
                "control": "input",
                "data_type": "image",
                "required": required,
                "source": {"normalized_from": "approved_default_result_image"},
            },
            "children": [],
        }
        children.append(existing)
        return True

    props = existing.get("props") if isinstance(existing.get("props"), dict) else {}
    defaults: dict[str, Any] = {
        "key": key,
        "control": "input",
        "data_type": "image",
        "required": required,
    }
    for property_name, expected_value in defaults.items():
        if props.get(property_name) != expected_value:
            props[property_name] = expected_value
            changed = True
    if compact_text(existing.get("name")) != name:
        existing["name"] = name
        changed = True
    existing["props"] = props
    return changed


def ensure_default_release_datetime_field(
    block_schema: dict[str, Any],
    *,
    container: dict[str, Any],
) -> bool:
    children = container.get("children") if isinstance(container.get("children"), list) else []
    if not isinstance(container.get("children"), list):
        container["children"] = children

    existing = next(
        (
            child
            for child in children
            if isinstance(child, dict)
            and child.get("kind") == "field"
            and compact_text((child.get("props") or {}).get("key")) == "release_date_time"
        ),
        None,
    )
    changed = False
    if existing is None:
        meta = block_schema.get("meta") if isinstance(block_schema.get("meta"), dict) else {}
        form_id = compact_text(meta.get("form_id"))
        container_key = compact_text((container.get("props") or {}).get("key"))
        if not form_id or not container_key:
            return False
        existing = {
            "id": f"{form_id}.{container_key}.release_date_time",
            "kind": "field",
            "name": "Date & Time",
            "props": {
                "key": "release_date_time",
                "order": len(children) + 1,
                "control": "input",
                "data_type": "datetime",
                "default_value_mode": "smart",
                "source": {"normalized_from": "approved_default_release_date_time"},
            },
            "children": [],
        }
        released_to_index = next(
            (
                index
                for index, child in enumerate(children)
                if isinstance(child, dict)
                and compact_text((child.get("props") or {}).get("key")) == "released_to"
            ),
            len(children) - 1,
        )
        children.insert(released_to_index + 1, existing)
        resequence_block_orders(children)
        return True

    props = existing.get("props") if isinstance(existing.get("props"), dict) else {}
    defaults = {
        "key": "release_date_time",
        "control": "input",
        "data_type": "datetime",
        "default_value_mode": "smart",
    }
    for property_name, expected_value in defaults.items():
        if props.get(property_name) != expected_value:
            props[property_name] = expected_value
            changed = True
    if compact_text(existing.get("name")) != "Date & Time":
        existing["name"] = "Date & Time"
        changed = True
    existing["props"] = props
    return changed


def ensure_default_top_level_container(
    block_schema: dict[str, Any],
    *,
    key: str,
    name: str,
    field_keys: tuple[str, ...],
) -> tuple[dict[str, Any] | None, bool]:
    blocks = normalize_items(block_schema.get("blocks"))
    existing = find_top_level_block_by_key(blocks, key)
    if existing is not None:
        return existing, False

    fields_by_key = {
        compact_text((block.get("props") or {}).get("key")): block
        for block in blocks
        if isinstance(block, dict) and block.get("kind") == "field"
    }
    if any(field_key not in fields_by_key for field_key in field_keys):
        return None, False

    meta = block_schema.get("meta") if isinstance(block_schema.get("meta"), dict) else {}
    form_id = compact_text(meta.get("form_id"))
    if not form_id:
        return None, False
    first_field_index = min(blocks.index(fields_by_key[field_key]) for field_key in field_keys)
    container = {
        "id": f"{form_id}.{key}",
        "kind": "container",
        "name": name,
        "props": {
            "key": key,
            "order": first_field_index + 1,
            "source": {"normalized_from": "approved_default_container_layout"},
        },
        "children": [fields_by_key[field_key] for field_key in field_keys],
    }
    field_ids = {id(field) for field in container["children"]}
    blocks = [block for block in blocks if id(block) not in field_ids]
    blocks.insert(first_field_index, container)
    block_schema["blocks"] = blocks
    resequence_block_orders(container["children"])
    resequence_top_level_block_orders(blocks)
    return container, True


def ensure_default_hematology_layout(block_schema: dict[str, Any]) -> bool:
    if not isinstance(block_schema, dict):
        return False

    meta = block_schema.get("meta") if isinstance(block_schema.get("meta"), dict) else {}
    if compact_text(meta.get("form_key")) != HEMATOLOGY_FORM_KEY:
        return False
    if meta.get(DEFAULT_HEMATOLOGY_LAYOUT_META_KEY) is True:
        return False

    changed = configure_default_field_properties(block_schema, HEMATOLOGY_FIELD_DEFAULTS)
    details, details_created = ensure_default_top_level_container(
        block_schema,
        key="details",
        name="Hematology Details",
        field_keys=HEMATOLOGY_DETAIL_FIELD_KEYS,
    )
    if details is None:
        return changed
    changed = changed or details_created
    detail_children = details.get("children") if isinstance(details.get("children"), list) else []
    differential_count = next(
        (
            child
            for child in detail_children
            if isinstance(child, dict)
            and compact_text((child.get("props") or {}).get("key")) == "differential_count"
        ),
        None,
    )
    if differential_count is None:
        field_by_key = {
            compact_text((child.get("props") or {}).get("key")): child
            for child in detail_children
            if isinstance(child, dict) and child.get("kind") == "field"
        }
        if any(field_key not in field_by_key for field_key in HEMATOLOGY_DIFFERENTIAL_FIELD_KEYS):
            return changed

        first_differential_index = min(
            detail_children.index(field_by_key[field_key])
            for field_key in HEMATOLOGY_DIFFERENTIAL_FIELD_KEYS
        )
        differential_count = {
            "id": f"{meta['form_id']}.differential_count",
            "kind": "container",
            "name": "Differential Count",
            "props": {
                "key": "differential_count",
                "order": first_differential_index + 1,
                "source": {"normalized_from": "approved_default_container_layout"},
            },
            "children": [field_by_key[field_key] for field_key in HEMATOLOGY_DIFFERENTIAL_FIELD_KEYS],
        }
        differential_field_ids = {id(field) for field in differential_count["children"]}
        new_children: list[dict[str, Any]] = []
        for child in detail_children:
            if id(child) in differential_field_ids:
                if len(new_children) == first_differential_index:
                    new_children.append(differential_count)
                continue
            new_children.append(child)
        detail_children = new_children
        details["children"] = detail_children
        resequence_block_orders(differential_count["children"])
        resequence_block_orders(detail_children)
        changed = True

    meta[DEFAULT_HEMATOLOGY_LAYOUT_META_KEY] = True
    block_schema["meta"] = meta
    return True


def ensure_default_hba1c_layout(block_schema: dict[str, Any]) -> bool:
    if not isinstance(block_schema, dict):
        return False

    meta = block_schema.get("meta") if isinstance(block_schema.get("meta"), dict) else {}
    if compact_text(meta.get("form_key")) != HBA1C_FORM_KEY:
        return False
    if meta.get(DEFAULT_HBA1C_LAYOUT_META_KEY) is True:
        if not ensure_form_print_layout_default(
            meta,
            template_id="legacy_landscape",
            paper_size="a5",
            layout=HBA1C_LEGACY_A5_LAYOUT_DEFAULT,
        ):
            return False
        block_schema["meta"] = meta
        return True

    details, _ = ensure_default_top_level_container(
        block_schema,
        key="details",
        name="HBA1C Details",
        field_keys=("result",),
    )
    if details is None:
        return False
    configure_container_field_properties(
        block_schema,
        {"details": HBA1C_FIELD_DEFAULTS},
    )
    meta[DEFAULT_HBA1C_LAYOUT_META_KEY] = True
    ensure_form_print_layout_default(
        meta,
        template_id="legacy_landscape",
        paper_size="a5",
        layout=HBA1C_LEGACY_A5_LAYOUT_DEFAULT,
    )
    block_schema["meta"] = meta
    return True


def ensure_default_blood_bank_layout(block_schema: dict[str, Any]) -> bool:
    if not isinstance(block_schema, dict):
        return False

    meta = block_schema.get("meta") if isinstance(block_schema.get("meta"), dict) else {}
    if compact_text(meta.get("form_key")) != BLOOD_BANK_FORM_KEY:
        return False

    crossmatching = find_top_level_block_by_key(
        normalize_items(block_schema.get("blocks")),
        "type_of_crossmatching",
    )
    if crossmatching is None:
        return False

    changed = False
    if meta.get(DEFAULT_BLOOD_BANK_DEFAULTS_META_KEY) is not True:
        ensure_default_release_datetime_field(block_schema, container=crossmatching)
        resequence_block_orders(normalize_items(crossmatching.get("children")))
        meta[DEFAULT_BLOOD_BANK_DEFAULTS_META_KEY] = True
        changed = True

    defaults = normalize_form_print_layout_defaults(meta.get("print_layout_defaults"))
    profile_key = print_layout_default_profile_key("legacy_landscape", "a5")
    if profile_key not in defaults["profiles"]:
        defaults["profiles"][profile_key] = normalize_print_layout_preference(
            BLOOD_BANK_LEGACY_A5_LAYOUT_DEFAULT
        )
        meta["print_layout_defaults"] = defaults
        changed = True

    if not changed:
        return False
    block_schema["meta"] = meta
    return True


def ensure_default_pro_time_aptt_layout(block_schema: dict[str, Any]) -> bool:
    if not isinstance(block_schema, dict):
        return False

    meta = block_schema.get("meta") if isinstance(block_schema.get("meta"), dict) else {}
    if compact_text(meta.get("form_key")) != PRO_TIME_APTT_FORM_KEY:
        return False
    if meta.get(DEFAULT_PRO_TIME_APTT_DEFAULTS_META_KEY) is True:
        if not ensure_form_print_layout_default(
            meta,
            template_id="legacy_landscape",
            paper_size="a5",
            layout=PRO_TIME_APTT_LEGACY_A5_LAYOUT_DEFAULT,
        ):
            return False
        block_schema["meta"] = meta
        return True

    blocks = normalize_items(block_schema.get("blocks"))
    if (
        find_top_level_block_by_key(blocks, "pro_time") is None
        or find_top_level_block_by_key(blocks, "aptt") is None
    ):
        return False
    configure_container_field_properties(block_schema, PRO_TIME_APTT_CONTAINER_FIELD_DEFAULTS)
    meta[DEFAULT_PRO_TIME_APTT_DEFAULTS_META_KEY] = True
    ensure_form_print_layout_default(
        meta,
        template_id="legacy_landscape",
        paper_size="a5",
        layout=PRO_TIME_APTT_LEGACY_A5_LAYOUT_DEFAULT,
    )
    block_schema["meta"] = meta
    return True


def ensure_default_qualitative_result_layout(
    block_schema: dict[str, Any],
    *,
    form_key: str,
    meta_key: str,
    details_name: str,
    detail_field_keys: tuple[str, ...],
    normal_choice_options: dict[str, tuple[str, ...]],
    result_image: dict[str, Any] | None = None,
    print_layout: dict[str, Any] | None = None,
) -> bool:
    if not isinstance(block_schema, dict):
        return False

    meta = block_schema.get("meta") if isinstance(block_schema.get("meta"), dict) else {}
    if compact_text(meta.get("form_key")) != form_key:
        return False
    if meta.get(meta_key) is True:
        if print_layout is None or not ensure_form_print_layout_default(
            meta,
            template_id="legacy_landscape",
            paper_size="a5",
            layout=print_layout,
        ):
            return False
        block_schema["meta"] = meta
        return True

    details, _ = ensure_default_top_level_container(
        block_schema,
        key="details",
        name=details_name,
        field_keys=detail_field_keys,
    )
    if details is None:
        return False
    choice_options_changed = configure_choice_field_normal_options(
        block_schema,
        normal_choice_options,
    )
    if choice_options_changed is None:
        return False

    if isinstance(result_image, dict):
        image_key = compact_text(result_image.get("key"))
        image_name = compact_text(result_image.get("name"))
        if not image_key or not image_name:
            return False
        ensure_default_image_field(
            block_schema,
            container=details,
            key=image_key,
            name=image_name,
            required=bool(result_image.get("required")),
        )
        resequence_block_orders(normalize_items(details.get("children")))

    meta[meta_key] = True
    if print_layout is not None:
        ensure_form_print_layout_default(
            meta,
            template_id="legacy_landscape",
            paper_size="a5",
            layout=print_layout,
        )
    block_schema["meta"] = meta
    return True


def ensure_default_hiv_1_and_2_testing_layout(block_schema: dict[str, Any]) -> bool:
    return ensure_default_qualitative_result_layout(
        block_schema,
        form_key=HIV_1_AND_2_TESTING_FORM_KEY,
        meta_key=DEFAULT_HIV_1_AND_2_TESTING_DEFAULTS_META_KEY,
        details_name="HIV 1&2 Testing Details",
        detail_field_keys=("lot_number", "test_result"),
        normal_choice_options={"test_result": ("NON-REACTIVE",)},
        print_layout=HIV_1_AND_2_TESTING_LEGACY_A5_LAYOUT_DEFAULT,
    )


def ensure_default_covid_19_antigen_rapid_test_layout(block_schema: dict[str, Any]) -> bool:
    return ensure_default_qualitative_result_layout(
        block_schema,
        form_key=COVID_19_ANTIGEN_RAPID_TEST_FORM_KEY,
        meta_key=DEFAULT_COVID_19_ANTIGEN_RAPID_TEST_DEFAULTS_META_KEY,
        details_name="COVID 19 Antigen (Rapid Test) Details",
        detail_field_keys=("test_result",),
        normal_choice_options={"test_result": ("NEGATIVE",)},
        result_image={"key": "result_image", "name": "Result Image", "required": False},
        print_layout=COVID_19_ANTIGEN_RAPID_TEST_LEGACY_A5_LAYOUT_DEFAULT,
    )


def ensure_default_microbiology_layout(block_schema: dict[str, Any]) -> bool:
    return ensure_default_qualitative_result_layout(
        block_schema,
        form_key=MICROBIOLOGY_FORM_KEY,
        meta_key=DEFAULT_MICROBIOLOGY_DEFAULTS_META_KEY,
        details_name="Microbiology Details",
        detail_field_keys=("result",),
        normal_choice_options={"result": ("NO FUNGAL ELEMENTS SEEN",)},
        print_layout=MICROBIOLOGY_LEGACY_A5_LAYOUT_DEFAULT,
    )


def ensure_default_blood_chemistry_layout(
    block_schema: dict[str, Any],
    *,
    form_key: str,
    meta_key: str,
    details_name: str,
    print_layout: dict[str, Any] | None = None,
) -> bool:
    if not isinstance(block_schema, dict):
        return False

    meta = block_schema.get("meta") if isinstance(block_schema.get("meta"), dict) else {}
    if compact_text(meta.get("form_key")) != form_key:
        return False
    if meta.get(meta_key) is True:
        if print_layout is None or not ensure_form_print_layout_default(
            meta,
            template_id="legacy_landscape",
            paper_size="a5",
            layout=print_layout,
        ):
            return False
        block_schema["meta"] = meta
        return True

    details, _ = ensure_default_top_level_container(
        block_schema,
        key="details",
        name=details_name,
        field_keys=BLOOD_CHEMISTRY_RESULT_FIELD_KEYS + ("others",),
    )
    if details is None:
        return False

    ranges = BLOOD_CHEMISTRY_RANGES_BY_FORM_KEY[form_key]
    configure_container_field_properties(
        block_schema,
        {
            "details": {
                field_key: {
                    "normal_min": normal_min,
                    "normal_max": normal_max,
                    "reference_text": None,
                    "normal_value": None,
                }
                for field_key, (normal_min, normal_max) in ranges.items()
            }
        },
    )
    meta[meta_key] = True
    if print_layout is not None:
        ensure_form_print_layout_default(
            meta,
            template_id="legacy_landscape",
            paper_size="a5",
            layout=print_layout,
        )
    block_schema["meta"] = meta
    return True


def ensure_default_blood_chemistry_male_layout(block_schema: dict[str, Any]) -> bool:
    return ensure_default_blood_chemistry_layout(
        block_schema,
        form_key=BLOOD_CHEMISTRY_MALE_FORM_KEY,
        meta_key=DEFAULT_BLOOD_CHEMISTRY_MALE_DEFAULTS_META_KEY,
        details_name="Male Details",
        print_layout=blood_chemistry_legacy_a5_layout(BLOOD_CHEMISTRY_MALE_FORM_KEY),
    )


def ensure_default_blood_chemistry_female_layout(block_schema: dict[str, Any]) -> bool:
    return ensure_default_blood_chemistry_layout(
        block_schema,
        form_key=BLOOD_CHEMISTRY_FEMALE_FORM_KEY,
        meta_key=DEFAULT_BLOOD_CHEMISTRY_FEMALE_DEFAULTS_META_KEY,
        details_name="Female Details",
        print_layout=blood_chemistry_legacy_a5_layout(BLOOD_CHEMISTRY_FEMALE_FORM_KEY),
    )


def ensure_default_serology_layout(block_schema: dict[str, Any]) -> bool:
    if not isinstance(block_schema, dict):
        return False

    meta = block_schema.get("meta") if isinstance(block_schema.get("meta"), dict) else {}
    if compact_text(meta.get("form_key")) != SEROLOGY_FORM_KEY:
        return False
    if meta.get(DEFAULT_SEROLOGY_DEFAULTS_META_KEY) is True:
        if not ensure_form_print_layout_default(
            meta,
            template_id="legacy_landscape",
            paper_size="a5",
            layout=SEROLOGY_LEGACY_A5_LAYOUT_DEFAULT,
        ):
            return False
        block_schema["meta"] = meta
        return True
    if configure_choice_field_normal_options(block_schema, SEROLOGY_NORMAL_CHOICE_OPTIONS) is None:
        return False

    meta[DEFAULT_SEROLOGY_DEFAULTS_META_KEY] = True
    ensure_form_print_layout_default(
        meta,
        template_id="legacy_landscape",
        paper_size="a5",
        layout=SEROLOGY_LEGACY_A5_LAYOUT_DEFAULT,
    )
    block_schema["meta"] = meta
    return True


def ensure_default_fecalysis_layout(block_schema: dict[str, Any]) -> bool:
    if not isinstance(block_schema, dict):
        return False

    meta = block_schema.get("meta") if isinstance(block_schema.get("meta"), dict) else {}
    if compact_text(meta.get("form_key")) != FECALYSIS_FORM_KEY:
        return False
    if meta.get(DEFAULT_FECALYSIS_DEFAULTS_META_KEY) is True:
        if not ensure_form_print_layout_default(
            meta,
            template_id="legacy_landscape",
            paper_size="a5",
            layout=FECALYSIS_LEGACY_A5_LAYOUT_DEFAULT,
        ):
            return False
        block_schema["meta"] = meta
        return True
    if configure_choice_field_normal_options(block_schema, FECALYSIS_NORMAL_CHOICE_OPTIONS) is None:
        return False

    meta[DEFAULT_FECALYSIS_DEFAULTS_META_KEY] = True
    ensure_form_print_layout_default(
        meta,
        template_id="legacy_landscape",
        paper_size="a5",
        layout=FECALYSIS_LEGACY_A5_LAYOUT_DEFAULT,
    )
    block_schema["meta"] = meta
    return True


def ensure_default_cardiaci_layout(block_schema: dict[str, Any]) -> bool:
    if not isinstance(block_schema, dict):
        return False

    meta = block_schema.get("meta") if isinstance(block_schema.get("meta"), dict) else {}
    if compact_text(meta.get("form_key")) != CARDIACI_FORM_KEY:
        return False
    if meta.get(DEFAULT_CARDIACI_DEFAULTS_META_KEY) is True:
        if not ensure_form_print_layout_default(
            meta,
            template_id="legacy_landscape",
            paper_size="a5",
            layout=CARDIACI_LEGACY_A5_LAYOUT_DEFAULT,
        ):
            return False
        block_schema["meta"] = meta
        return True

    details, _ = ensure_default_top_level_container(
        block_schema,
        key="details",
        name="Cardiaci Details",
        field_keys=("ck_mb", "troponin_i", "bnp"),
    )
    if details is None:
        return False
    configure_container_field_properties(block_schema, {"details": CARDIACI_FIELD_DEFAULTS})
    meta[DEFAULT_CARDIACI_DEFAULTS_META_KEY] = True
    ensure_form_print_layout_default(
        meta,
        template_id="legacy_landscape",
        paper_size="a5",
        layout=CARDIACI_LEGACY_A5_LAYOUT_DEFAULT,
    )
    block_schema["meta"] = meta
    return True


def ensure_default_ogtt_layout(block_schema: dict[str, Any]) -> bool:
    if not isinstance(block_schema, dict):
        return False

    meta = block_schema.get("meta") if isinstance(block_schema.get("meta"), dict) else {}
    if compact_text(meta.get("form_key")) != OGTT_FORM_KEY:
        return False
    if meta.get(DEFAULT_OGTT_DEFAULTS_META_KEY) is True:
        if not ensure_form_print_layout_default(
            meta,
            template_id="legacy_landscape",
            paper_size="a5",
            layout=OGTT_LEGACY_A5_LAYOUT_DEFAULT,
        ):
            return False
        block_schema["meta"] = meta
        return True

    blocks = normalize_items(block_schema.get("blocks"))
    if any(
        find_top_level_block_by_key(blocks, container_key) is None
        for container_key in OGTT_CONTAINER_FIELD_DEFAULTS
    ):
        return False
    configure_container_field_properties(block_schema, OGTT_CONTAINER_FIELD_DEFAULTS)
    meta[DEFAULT_OGTT_DEFAULTS_META_KEY] = True
    ensure_form_print_layout_default(
        meta,
        template_id="legacy_landscape",
        paper_size="a5",
        layout=OGTT_LEGACY_A5_LAYOUT_DEFAULT,
    )
    block_schema["meta"] = meta
    return True


def set_default_blood_gas_container(
    block: dict[str, Any],
    *,
    key: str,
    name: str,
    order: int,
) -> None:
    block["name"] = name
    props = block.get("props") if isinstance(block.get("props"), dict) else {}
    props["key"] = key
    props["order"] = order
    block["props"] = props


def ensure_default_blood_gas_print_layout(meta: dict[str, Any]) -> bool:
    return ensure_form_print_layout_default(
        meta,
        template_id="legacy_landscape",
        paper_size="a5",
        layout=BLOOD_GAS_LEGACY_A5_LAYOUT_DEFAULT,
    )


def ensure_form_print_layout_default(
    meta: dict[str, Any],
    *,
    template_id: str,
    paper_size: str,
    layout: dict[str, Any],
) -> bool:
    defaults = normalize_form_print_layout_defaults(meta.get("print_layout_defaults"))
    profile_key = print_layout_default_profile_key(template_id, paper_size)
    if profile_key in defaults["profiles"]:
        return False
    defaults["profiles"][profile_key] = normalize_print_layout_preference(layout)
    meta["print_layout_defaults"] = defaults
    return True


def ensure_default_blood_gas_analysis_layout(block_schema: dict[str, Any]) -> bool:
    if not isinstance(block_schema, dict):
        return False

    meta = block_schema.get("meta") if isinstance(block_schema.get("meta"), dict) else {}
    if compact_text(meta.get("form_key")) != BLOOD_GAS_ANALYSIS_FORM_KEY:
        return False
    if meta.get(DEFAULT_BLOOD_GAS_LAYOUT_META_KEY) is True:
        if not ensure_default_blood_gas_print_layout(meta):
            return False
        block_schema["meta"] = meta
        return True

    changed = configure_blood_gas_numeric_ranges(block_schema)
    blocks = normalize_items(block_schema.get("blocks"))
    blood_gas_values = find_top_level_block_by_key(blocks, "blood_gas_values")
    calculated_values = find_top_level_block_by_key(blocks, "calculated_values")

    if blood_gas_values is None or calculated_values is None:
        abg = find_top_level_block_by_key(blocks, "blood_gas_value_abg")
        oximetry = find_top_level_block_by_key(blocks, "calculated_values_oximetry")
        acid_base_status = find_top_level_block_by_key(blocks, "calculated_values_acid_base_status")
        if abg is None or oximetry is None or acid_base_status is None:
            return changed

        abg_children = abg.get("children") if isinstance(abg.get("children"), list) else []
        acid_base_children = (
            acid_base_status.get("children") if isinstance(acid_base_status.get("children"), list) else []
        )
        note_match = find_field_with_parent(acid_base_children, "note")
        note = None
        if note_match is not None:
            note_parent, note = note_match
            note_parent.remove(note)

        set_default_blood_gas_container(abg, key="abg", name="ABG", order=1)
        set_default_blood_gas_container(oximetry, key="oximetry", name="Oximetry", order=1)
        set_default_blood_gas_container(
            acid_base_status,
            key="acid_base_status",
            name="Acid-Base Status",
            order=2,
        )
        if note is not None:
            note_props = note.get("props") if isinstance(note.get("props"), dict) else {}
            note_props["order"] = 2
            note["props"] = note_props

        first_index = min(blocks.index(abg), blocks.index(oximetry), blocks.index(acid_base_status))
        for block in (abg, oximetry, acid_base_status):
            blocks.remove(block)
        blood_gas_values = {
            "id": f"{meta['form_id']}.blood_gas_values",
            "kind": "container",
            "name": "Blood Gas Values",
            "props": {
                "key": "blood_gas_values",
                "order": first_index + 1,
                "source": {"normalized_from": "approved_default_container_layout"},
            },
            "children": [abg, *([note] if note is not None else [])],
        }
        calculated_values = {
            "id": f"{meta['form_id']}.calculated_values",
            "kind": "container",
            "name": "Calculated Values",
            "props": {
                "key": "calculated_values",
                "order": first_index + 2,
                "source": {"normalized_from": "approved_default_container_layout"},
            },
            "children": [oximetry, acid_base_status],
        }
        blocks.insert(first_index, blood_gas_values)
        blocks.insert(first_index + 1, calculated_values)
        resequence_block_orders(blood_gas_values["children"])
        resequence_block_orders(calculated_values["children"])
        resequence_block_orders(acid_base_status["children"])
        resequence_top_level_block_orders(blocks)
        changed = True

    meta[DEFAULT_BLOOD_GAS_LAYOUT_META_KEY] = True
    ensure_default_blood_gas_print_layout(meta)
    block_schema["meta"] = meta
    return True


def ensure_default_patient_info_identity(block_schema: dict[str, Any]) -> bool:
    meta = block_schema.get("meta") if isinstance(block_schema.get("meta"), dict) else {}
    form_id = compact_text(meta.get("form_id"))
    if not form_id or not block_schema_has_default_patient_info(block_schema):
        return False

    name_field_id = default_patient_info_field_id(form_id, PATIENT_INFO_PRIMARY_KEY)
    case_field_id = default_patient_info_field_id(form_id, PATIENT_INFO_SECONDARY_KEY)
    identity = normalize_record_identity_config(meta.get("record_identity"))
    changed = False

    if not identity["primary_field_id"]:
        identity["primary_field_id"] = name_field_id
        changed = True
    if not identity["secondary_field_id"]:
        identity["secondary_field_id"] = case_field_id
        changed = True

    searchable_ids = list(identity["searchable_field_ids"])
    for field_id in [name_field_id, case_field_id]:
        if field_id and field_id not in searchable_ids:
            searchable_ids.append(field_id)
            changed = True
    if searchable_ids != identity["searchable_field_ids"]:
        identity["searchable_field_ids"] = searchable_ids
        changed = True

    if changed or meta.get("record_identity") != identity:
        meta["record_identity"] = identity
        block_schema["meta"] = meta
        return True
    return False


def ensure_default_patient_info_block_schema(block_schema: dict[str, Any]) -> bool:
    if not isinstance(block_schema, dict):
        return False

    meta = block_schema.get("meta") if isinstance(block_schema.get("meta"), dict) else {}
    form_id = compact_text(meta.get("form_id"))
    if not form_id:
        return False

    changed = False
    blocks = normalize_items(block_schema.get("blocks"))
    has_patient_info = block_schema_has_default_patient_info(block_schema)
    was_materialized = bool(meta.get(DEFAULT_PATIENT_INFO_MATERIALIZED_META_KEY))

    if not has_patient_info and was_materialized:
        return False

    if not has_patient_info:
        blocks = [build_default_patient_info_block(form_id), *blocks]
        block_schema["blocks"] = blocks
        has_patient_info = True
        changed = True

    if has_patient_info and meta.get(DEFAULT_PATIENT_INFO_MATERIALIZED_META_KEY) is not True:
        meta[DEFAULT_PATIENT_INFO_MATERIALIZED_META_KEY] = True
        block_schema["meta"] = meta
        changed = True

    if has_patient_info:
        resequence_top_level_block_orders(blocks)
        changed = ensure_default_patient_info_identity(block_schema) or changed
    return changed


def normalize_block_option_props(raw_options: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []

    for index, option in enumerate(normalize_items(raw_options), start=1):
        if isinstance(option, dict):
            normalized_option = dict(option)
            name = compact_text(normalized_option.get("name") or normalized_option.get("label"))
            if not name:
                continue
            normalized_option["name"] = name
            normalized_option.pop("label", None)
            normalized_option["key"] = compact_text(normalized_option.get("key")) or slugify(name) or f"option_{index}"
            normalized_option["order"] = int(normalized_option.get("order") or index)
            normalized_option["is_normal"] = bool(normalized_option.get("is_normal"))
            normalized.append(normalized_option)
            continue

        name = compact_text(option)
        if not name:
            continue
        normalized.append(
            {
                "name": name,
                "key": slugify(name) or f"option_{index}",
                "order": index,
                "is_normal": False,
            }
        )

    return normalized


TEMPORAL_FIELD_TYPES = {"date", "time", "datetime"}
TEMPORAL_DEFAULT_MODES = {"smart", "blank", "today", "now", "current_datetime"}


def normalize_temporal_default_mode(value: Any, data_type: Any) -> str:
    field_type = compact_text(data_type)
    if field_type not in TEMPORAL_FIELD_TYPES:
        return ""

    mode = compact_text(value) or "smart"
    if mode not in TEMPORAL_DEFAULT_MODES:
        mode = "smart"
    if field_type == "date" and mode == "now":
        return "today"
    if field_type == "time" and mode in {"today", "current_datetime"}:
        return "now"
    if field_type == "datetime" and mode in {"today", "now"}:
        return "current_datetime"
    return mode


def normalize_active_block_storage_node(node: dict[str, Any]) -> bool:
    if not isinstance(node, dict):
        return False

    changed = False
    if compact_text(node.get("kind")) in LEGACY_CONTAINER_KINDS:
        node["kind"] = "container"
        changed = True
    props = node.get("props") if isinstance(node.get("props"), dict) else None
    if isinstance(props, dict):
        if "field_type" in props:
            props.pop("field_type", None)
            changed = True

        if compact_text(node.get("kind")) == "field":
            required = bool(props.get("required"))
            if required:
                if props.get("required") is not True:
                    props["required"] = True
                    changed = True
            elif "required" in props:
                props.pop("required", None)
                changed = True

            default_value_mode = normalize_temporal_default_mode(
                props.get("default_value_mode"),
                props.get("data_type"),
            )
            if default_value_mode:
                if props.get("default_value_mode") != default_value_mode:
                    props["default_value_mode"] = default_value_mode
                    changed = True
            elif "default_value_mode" in props:
                props.pop("default_value_mode", None)
                changed = True

        reference_text = compact_text(props.get("reference_text") or props.get("normal_value"))
        if reference_text:
            if props.get("reference_text") != reference_text:
                props["reference_text"] = reference_text
                changed = True
        elif "reference_text" in props:
            props.pop("reference_text", None)
            changed = True

        if "normal_value" in props:
            props.pop("normal_value", None)
            changed = True

        normal_min = compact_text(props.get("normal_min"))
        if normal_min:
            if props.get("normal_min") != normal_min:
                props["normal_min"] = normal_min
                changed = True
        elif "normal_min" in props:
            props.pop("normal_min", None)
            changed = True

        normal_max = compact_text(props.get("normal_max"))
        if normal_max:
            if props.get("normal_max") != normal_max:
                props["normal_max"] = normal_max
                changed = True
        elif "normal_max" in props:
            props.pop("normal_max", None)
            changed = True

        for property_name, has_bound in (
            ("normal_min_inclusive", bool(normal_min)),
            ("normal_max_inclusive", bool(normal_max)),
        ):
            is_inclusive = normalize_boolean_setting(props.get(property_name), default=True)
            if has_bound and not is_inclusive:
                if props.get(property_name) is not False:
                    props[property_name] = False
                    changed = True
            elif property_name in props:
                props.pop(property_name, None)
                changed = True

        if "options" in props:
            normalized_options = normalize_block_option_props(props.get("options"))
            if normalized_options:
                if normalized_options != props.get("options"):
                    props["options"] = normalized_options
                    changed = True
            else:
                props.pop("options", None)
                changed = True

    for child in normalize_items(node.get("children")):
        if normalize_active_block_storage_node(child):
            changed = True

    return changed


def normalize_active_block_storage_schema(block_schema: dict[str, Any]) -> bool:
    if not isinstance(block_schema, dict):
        return False

    changed = False
    if int(block_schema.get("schema_version") or 0) != CANONICAL_BLOCK_SCHEMA_VERSION:
        block_schema["schema_version"] = CANONICAL_BLOCK_SCHEMA_VERSION
        changed = True
    if compact_text(block_schema.get("source_kind")) != ACTIVE_BLOCK_SCHEMA_SOURCE:
        block_schema["source_kind"] = ACTIVE_BLOCK_SCHEMA_SOURCE
        changed = True
    blocks = normalize_items(block_schema.get("blocks"))
    if block_schema.get("blocks") != blocks:
        block_schema["blocks"] = blocks
        changed = True

    meta = block_schema.get("meta") if isinstance(block_schema.get("meta"), dict) else {}
    had_signatories = "signatories" in meta
    normalized_identity = normalize_record_identity_config(meta.get("record_identity"))
    if any(
        [
            normalized_identity["primary_field_id"],
            normalized_identity["secondary_field_id"],
            normalized_identity["searchable_field_ids"],
        ]
    ):
        if meta.get("record_identity") != normalized_identity:
            meta["record_identity"] = normalized_identity
            block_schema["meta"] = meta
            changed = True
    elif "record_identity" in meta:
        meta.pop("record_identity", None)
        block_schema["meta"] = meta
        changed = True

    normalized_print_config = normalize_print_config(meta.get("print_config"))
    if meta.get("print_config") != normalized_print_config:
        meta["print_config"] = normalized_print_config
        block_schema["meta"] = meta
        changed = True
    if ensure_form_default_print_accent(meta):
        block_schema["meta"] = meta
        changed = True

    normalized_signatories = normalize_signatory_slots(
        meta.get("signatories"),
        use_defaults=not had_signatories,
    )
    if meta.get("signatories") != normalized_signatories:
        meta["signatories"] = normalized_signatories
        block_schema["meta"] = meta
        changed = True
    if not had_signatories and meta.get(CLIENT_SIGNATORY_DEFAULTS_META_KEY) is not True:
        meta[CLIENT_SIGNATORY_DEFAULTS_META_KEY] = True
        block_schema["meta"] = meta
        changed = True

    for block in blocks:
        if normalize_active_block_storage_node(block):
            changed = True

    return changed


def build_block_storage_payload(
    raw_schema: dict[str, Any],
    *,
    slug: str,
    name: str,
    form_order: int,
) -> dict[str, Any]:
    if isinstance(raw_schema, dict) and "blocks" in raw_schema and "fields" not in raw_schema and "sections" not in raw_schema:
        block_schema = json.loads(json.dumps(raw_schema))
    else:
        block_schema = build_block_schema_from_legacy_storage(raw_schema)

    block_schema["schema_version"] = CANONICAL_BLOCK_SCHEMA_VERSION
    block_schema["source_kind"] = ACTIVE_BLOCK_SCHEMA_SOURCE
    block_schema["blocks"] = normalize_items(block_schema.get("blocks"))

    meta = block_schema.get("meta") if isinstance(block_schema.get("meta"), dict) else {}
    meta.pop("common_field_set_id", None)
    meta["form_id"] = stable_form_schema_id(slug)
    meta["form_key"] = compact_text(slug)
    meta["form_name"] = compact_text(name) or "Untitled Form"
    meta["form_order"] = int(form_order or 1)
    meta.pop("legacy_form_id", None)
    meta.pop("legacy_form_key", None)
    meta.pop("legacy_order", None)

    if not (isinstance(raw_schema, dict) and "blocks" in raw_schema):
        notes = normalize_notes(raw_schema.get("notes"))
        if notes:
            meta["notes"] = notes
        else:
            meta.pop("notes", None)

        source = raw_schema.get("source")
        if isinstance(source, dict) and source:
            meta["source"] = source
        else:
            meta.pop("source", None)

    ensure_form_default_print_accent(meta)
    block_schema["meta"] = meta
    normalize_active_block_storage_schema(block_schema)
    return block_schema


def build_block_storage_document_from_legacy_storage(
    legacy_storage_schema: dict[str, Any],
) -> dict[str, Any]:
    return build_block_storage_payload(
        legacy_storage_schema,
        slug=compact_text(legacy_storage_schema.get("key")) or "compat",
        name=compact_text(legacy_storage_schema.get("name")) or "Untitled Form",
        form_order=int(legacy_storage_schema.get("order") or 1),
    )


def block_payload_form_key(raw_block_schema: dict[str, Any]) -> str:
    if not isinstance(raw_block_schema, dict):
        return ""
    meta = raw_block_schema.get("meta") if isinstance(raw_block_schema.get("meta"), dict) else {}
    return compact_text(meta.get("form_key"))


def stable_form_schema_id(slug: str) -> str:
    return f"form.{slugify(slug or 'compat')}"


def build_legacy_storage_payload(
    raw_schema: dict[str, Any],
    *,
    slug: str,
    name: str,
    form_order: int,
) -> dict[str, Any]:
    raw_schema = materialize_default_patient_info_fields(raw_schema if isinstance(raw_schema, dict) else {})
    form_id = stable_form_schema_id(slug)
    field_used: set[str] = set()
    section_used: set[str] = set()

    normalized: dict[str, Any] = {
        "id": form_id,
        "key": slug,
        "name": compact_text(name) or "Untitled Form",
        "order": form_order,
        "fields": [
            normalize_field(field, form_id, field_order, field_used)
            for field_order, field in enumerate(raw_schema.get("fields") or [], start=1)
            if isinstance(field, dict)
        ],
        "sections": [
            normalize_section(section, form_id, section_order, section_used)
            for section_order, section in enumerate(raw_schema.get("sections") or [], start=1)
            if isinstance(section, dict)
        ],
    }

    notes = normalize_notes(raw_schema.get("notes"))
    if notes:
        normalized["notes"] = notes

    source = raw_schema.get("source")
    if isinstance(source, dict) and source:
        normalized["source"] = source

    return normalized


def build_form_version_record(
    *,
    form_id: int,
    version_number: int,
    summary: str,
    block_storage_schema: dict[str, Any],
    source: str,
    is_current: bool,
) -> FormVersion:
    return FormVersion(
        form_id=form_id,
        version_number=version_number,
        summary=summary,
        block_schema_json=json.dumps(block_storage_schema, ensure_ascii=False),
        legacy_schema_json=None,
        source=source,
        is_current=is_current,
    )


def current_version(definition: FormDefinition) -> FormVersion | None:
    for version in definition.versions:
        if version.is_current:
            return version
    return definition.versions[-1] if definition.versions else None


def load_legacy_storage_document(version: FormVersion) -> dict[str, Any]:
    raw_schema = compact_text(version.legacy_schema_json)
    if not raw_schema:
        return {}
    try:
        parsed = json.loads(raw_schema)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def load_block_storage_document(
    version: FormVersion,
    *,
    legacy_storage_schema: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], bool]:
    raw_block_storage = compact_text(version.block_schema_json)
    if raw_block_storage:
        try:
            parsed = json.loads(raw_block_storage)
            if isinstance(parsed, dict):
                return parsed, normalize_active_block_storage_schema(parsed)
        except json.JSONDecodeError:
            pass
    fallback_legacy_storage = legacy_storage_schema if isinstance(legacy_storage_schema, dict) else load_legacy_storage_document(version)
    return build_block_storage_document_from_legacy_storage(fallback_legacy_storage), True


def load_json_object(raw_value: str | None) -> dict[str, Any]:
    payload = compact_text(raw_value)
    if not payload:
        return {}
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def normalize_record_values(raw_values: Any) -> dict[str, Any]:
    if not isinstance(raw_values, dict):
        return {}

    normalized: dict[str, Any] = {}
    for raw_key, raw_value in raw_values.items():
        field_id = compact_text(raw_key)
        if not field_id:
            continue

        if isinstance(raw_value, dict):
            asset_payload: dict[str, Any] = {}
            asset_id = raw_value.get("asset_id")
            if asset_id not in (None, ""):
                try:
                    asset_payload["asset_id"] = int(asset_id)
                except (TypeError, ValueError):
                    pass
            kind = compact_text(raw_value.get("kind"))
            if kind:
                asset_payload["kind"] = kind
            if asset_payload:
                normalized[field_id] = asset_payload
            continue

        if isinstance(raw_value, bool):
            normalized[field_id] = raw_value
            continue

        if isinstance(raw_value, (int, float)):
            normalized[field_id] = raw_value
            continue

        text_value = compact_text(raw_value)
        if text_value:
            normalized[field_id] = text_value

    return normalized


def normalize_record_indexed_meta(
    raw_meta: Any,
    *,
    patient_name: str | None,
    patient_age: str | None,
    patient_sex: str | None,
    case_number: str | None,
) -> dict[str, Any]:
    normalized = dict(raw_meta) if isinstance(raw_meta, dict) else {}

    if patient_name is not None and compact_text(patient_name):
        normalized["patient_name"] = compact_text(patient_name)
    elif patient_name is not None:
        normalized.pop("patient_name", None)

    if patient_age is not None and compact_text(patient_age):
        normalized["patient_age"] = compact_text(patient_age)
    elif patient_age is not None:
        normalized.pop("patient_age", None)

    if patient_sex is not None and compact_text(patient_sex):
        normalized["patient_sex"] = compact_text(patient_sex)
    elif patient_sex is not None:
        normalized.pop("patient_sex", None)

    if case_number is not None and compact_text(case_number):
        normalized["case_number"] = compact_text(case_number)
    elif case_number is not None:
        normalized.pop("case_number", None)

    return normalized


def remove_file_if_present(path_value: str | None) -> None:
    file_path = Path(path_value or "")
    if not file_path.exists() or not file_path.is_file():
        return
    try:
        file_path.unlink()
    except OSError:
        return

    parent = file_path.parent
    stop_dir = RECORD_UPLOADS_DIR.resolve()
    while parent.exists():
        try:
            if parent.resolve() == stop_dir:
                break
        except OSError:
            break
        try:
            parent.rmdir()
        except OSError:
            break
        parent = parent.parent


def remove_file_if_present_under(path_value: str | None, *, stop_dir: Path) -> None:
    file_path = Path(path_value or "")
    if not file_path.exists() or not file_path.is_file():
        return
    try:
        file_path.unlink()
    except OSError:
        return

    parent = file_path.parent
    safe_stop_dir = stop_dir.resolve()
    while parent.exists():
        try:
            if parent.resolve() == safe_stop_dir:
                break
        except OSError:
            break
        try:
            parent.rmdir()
        except OSError:
            break
        parent = parent.parent


def remove_record_asset(
    session: Session,
    asset: RecordAsset,
) -> None:
    remove_file_if_present(asset.storage_path)
    session.delete(asset)


def save_user_avatar(
    session: Session,
    user_id: int,
    *,
    avatar_filename: str = "",
    avatar_content_type: str | None = None,
    avatar_bytes: bytes | None = None,
) -> dict[str, Any]:
    user = get_user_or_none(session, user_id)
    if user is None:
        raise KeyError(user_id)

    mime_type = compact_text(avatar_content_type)
    extension = ALLOWED_IMAGE_CONTENT_TYPES.get(mime_type)
    if extension is None:
        raise ValueError("Only JPG, PNG, and WebP avatars are allowed.")
    if not avatar_bytes:
        raise ValueError("Choose an image before uploading.")
    if len(avatar_bytes) > MAX_USER_AVATAR_BYTES:
        raise ValueError("Avatar image must be 2 MB or smaller.")

    old_avatar_path = user.avatar_path
    old_avatar_name = user.avatar_original_filename
    old_avatar_type = user.avatar_mime_type
    USER_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    new_avatar_path = USER_UPLOADS_DIR / f"user_{user.id}_avatar_{uuid4().hex}{extension}"
    new_avatar_path.write_bytes(avatar_bytes)

    user.avatar_path = str(new_avatar_path)
    user.avatar_original_filename = compact_text(avatar_filename) or new_avatar_path.name
    user.avatar_mime_type = mime_type or None

    try:
        session.add(user)
        session.commit()
    except Exception:
        session.rollback()
        remove_file_if_present_under(str(new_avatar_path), stop_dir=USER_UPLOADS_DIR)
        user.avatar_path = old_avatar_path
        user.avatar_original_filename = old_avatar_name
        user.avatar_mime_type = old_avatar_type
        raise

    if old_avatar_path and old_avatar_path != str(new_avatar_path):
        remove_file_if_present_under(old_avatar_path, stop_dir=USER_UPLOADS_DIR)

    session.refresh(user)
    return serialize_user(user)


def remove_user_avatar(session: Session, user_id: int) -> dict[str, Any]:
    user = get_user_or_none(session, user_id)
    if user is None:
        raise KeyError(user_id)

    old_avatar_path = user.avatar_path
    user.avatar_path = None
    user.avatar_original_filename = None
    user.avatar_mime_type = None
    session.add(user)
    session.commit()
    if old_avatar_path:
        remove_file_if_present_under(old_avatar_path, stop_dir=USER_UPLOADS_DIR)
    session.refresh(user)
    return serialize_user(user)


def save_clinic_profile(
    session: Session,
    payload: ClinicProfilePayload,
    *,
    logo_filename: str = "",
    logo_content_type: str | None = None,
    logo_bytes: bytes | None = None,
) -> dict[str, Any]:
    profile = get_or_create_clinic_profile(session)

    clinic_name = compact_text(payload.clinic_name)
    address = compact_text(payload.address)
    contact_number = compact_text(payload.contact_number)
    contact_email = normalize_email(payload.contact_email) if compact_text(payload.contact_email) else ""
    doh_license_number = compact_text(payload.doh_license_number)

    if not clinic_name:
        raise ValueError("Enter the clinic name.")
    if contact_email and not validate_email_format(contact_email):
        raise ValueError("Enter a valid contact email address.")

    old_logo_path = profile.logo_path
    old_logo_name = profile.logo_original_filename
    old_logo_type = profile.logo_mime_type
    old_doh_license_number = profile.doh_license_number
    new_logo_path: Path | None = None

    if logo_bytes is not None:
        mime_type = compact_text(logo_content_type)
        extension = ALLOWED_IMAGE_CONTENT_TYPES.get(mime_type)
        if extension is None:
            raise ValueError("Only JPG, PNG, and WebP logos are allowed.")
        if not logo_bytes:
            raise ValueError("Choose an image before uploading.")
        if len(logo_bytes) > MAX_CLINIC_LOGO_BYTES:
            raise ValueError("Logo image must be 5 MB or smaller.")
        CLINIC_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        new_logo_path = CLINIC_UPLOADS_DIR / f"logo_{uuid4().hex}{extension}"
        new_logo_path.write_bytes(logo_bytes)
        profile.logo_path = str(new_logo_path)
        profile.logo_original_filename = compact_text(logo_filename) or new_logo_path.name
        profile.logo_mime_type = mime_type or None

    profile.clinic_name = clinic_name
    profile.address = address or None
    profile.contact_number = contact_number or None
    profile.contact_email = contact_email or None
    profile.doh_license_number = doh_license_number or None

    try:
        session.add(profile)
        session.commit()
    except Exception:
        session.rollback()
        if new_logo_path is not None:
            remove_file_if_present_under(str(new_logo_path), stop_dir=CLINIC_UPLOADS_DIR)
        profile.logo_path = old_logo_path
        profile.logo_original_filename = old_logo_name
        profile.logo_mime_type = old_logo_type
        profile.doh_license_number = old_doh_license_number
        raise

    if new_logo_path is not None and old_logo_path and old_logo_path != str(new_logo_path):
        remove_file_if_present_under(old_logo_path, stop_dir=CLINIC_UPLOADS_DIR)

    session.refresh(profile)
    return serialize_clinic_profile(profile)


def save_signatory_stamp_image(
    *,
    stamp_filename: str = "",
    stamp_content_type: str | None = None,
    stamp_bytes: bytes | None = None,
) -> dict[str, Any]:
    mime_type = compact_text(stamp_content_type)
    extension = ALLOWED_IMAGE_CONTENT_TYPES.get(mime_type)
    if extension is None:
        raise ValueError("Only JPG, PNG, and WebP stamp images are allowed.")
    if not stamp_bytes:
        raise ValueError("Choose a stamp image before uploading.")
    if len(stamp_bytes) > MAX_SIGNATORY_STAMP_BYTES:
        raise ValueError("Stamp image must be 5 MB or smaller.")

    SIGNATORY_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    stamp_path = SIGNATORY_UPLOADS_DIR / f"stamp_{uuid4().hex}{extension}"
    stamp_path.write_bytes(stamp_bytes)
    return {
        "url": f"/signatory-stamps/{stamp_path.name}",
        "original_filename": compact_text(stamp_filename) or stamp_path.name,
        "mime_type": mime_type,
        "size_bytes": len(stamp_bytes),
    }


def ensure_default_pathologist_stamp(
    *,
    source_path: Path | None = None,
    destination_path: Path | None = None,
) -> Path:
    source = source_path or DEFAULT_PATHOLOGIST_STAMP_RESOURCE_PATH
    destination = destination_path or DEFAULT_PATHOLOGIST_STAMP_RUNTIME_PATH
    if destination.is_file():
        return destination
    if not source.is_file():
        raise FileNotFoundError(f"Default Pathologist stamp was not bundled: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".partial")
    shutil.copyfile(source, partial)
    os.replace(partial, destination)
    return destination


def remove_clinic_logo(session: Session) -> dict[str, Any]:
    profile = get_or_create_clinic_profile(session)
    old_logo_path = profile.logo_path
    profile.logo_path = None
    profile.logo_original_filename = None
    profile.logo_mime_type = None
    session.add(profile)
    session.commit()
    if old_logo_path:
        remove_file_if_present_under(old_logo_path, stop_dir=CLINIC_UPLOADS_DIR)
    session.refresh(profile)
    return serialize_clinic_profile(profile)


def preserve_existing_asset_values(
    existing_values: dict[str, Any],
    incoming_values: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(incoming_values)
    for field_id, value in existing_values.items():
        if field_id in merged:
            continue
        if isinstance(value, dict) and value.get("kind") == "image" and value.get("asset_id"):
            merged[field_id] = value
    return merged


def find_block_by_id(blocks: list[dict[str, Any]], block_id: str) -> dict[str, Any] | None:
    target_id = compact_text(block_id)
    for block in blocks:
        if not isinstance(block, dict):
            continue
        if compact_text(block.get("id")) == target_id:
            return block
        children = normalize_items(block.get("children"))
        if children:
            found = find_block_by_id(children, target_id)
            if found is not None:
                return found
    return None


def resolve_record_image_field(record: Record, field_block_id: str) -> dict[str, Any]:
    block_schema, _ = load_block_storage_document(record.form_version)
    field_block = find_block_by_id(normalize_items(block_schema.get("blocks")), field_block_id)
    if field_block is None or compact_text(field_block.get("kind")) != "field":
        raise ValueError("Image field not found.")
    props = field_block.get("props") if isinstance(field_block.get("props"), dict) else {}
    if compact_text(props.get("data_type")) != "image":
        raise ValueError("This field does not accept image uploads.")
    return field_block


def current_record_values(record: Record) -> dict[str, Any]:
    return normalize_record_values(load_json_object(record.values_json))


def iter_record_field_blocks(
    blocks: list[dict[str, Any]],
    *,
    parents: list[str] | None = None,
):
    parent_names = parents or []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        kind = compact_text(block.get("kind"))
        block_name = compact_text(block.get("name"))
        if kind == "container":
            next_parent_names = [*parent_names, block_name] if block_name else parent_names
            yield from iter_record_field_blocks(
                normalize_items(block.get("children")),
                parents=next_parent_names,
            )
            continue
        if kind == "field":
            block_id = compact_text(block.get("id"))
            if not block_id:
                continue
            yield {
                "id": block_id,
                "name": block_name or "Untitled field",
                "path_label": " / ".join([*parent_names, block_name]) if parent_names else block_name,
                "block": block,
            }


def record_field_lookup(block_schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        field["id"]: field
        for field in iter_record_field_blocks(normalize_items(block_schema.get("blocks")))
    }


def normalize_record_identity_config(raw_config: Any) -> dict[str, Any]:
    config = raw_config if isinstance(raw_config, dict) else {}
    primary_field_id = compact_text(config.get("primary_field_id"))
    secondary_field_id = compact_text(config.get("secondary_field_id"))
    searchable_field_ids = []
    for field_id in normalize_items(config.get("searchable_field_ids")):
        normalized = compact_text(field_id)
        if normalized and normalized not in searchable_field_ids:
            searchable_field_ids.append(normalized)

    return {
        "primary_field_id": primary_field_id,
        "secondary_field_id": secondary_field_id,
        "searchable_field_ids": searchable_field_ids,
    }


def record_value_display_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        if value.get("kind") == "image" and value.get("asset_id"):
            return "Image uploaded"
        return " ".join(
            part
            for part in (record_value_display_text(item) for item in value.values())
            if part
        )
    if isinstance(value, list):
        return " ".join(
            part
            for part in (record_value_display_text(item) for item in value)
            if part
        )
    return compact_text(value)


def resolve_record_identity(
    block_schema: dict[str, Any],
    values: dict[str, Any],
    *,
    fallback_primary: str = "",
    fallback_secondary: str = "",
) -> dict[str, Any]:
    meta = block_schema.get("meta") if isinstance(block_schema.get("meta"), dict) else {}
    config = normalize_record_identity_config(meta.get("record_identity"))
    fields = record_field_lookup(block_schema)

    primary_field = fields.get(config["primary_field_id"])
    secondary_field = fields.get(config["secondary_field_id"])
    primary_value = record_value_display_text(values.get(config["primary_field_id"]))
    secondary_value = record_value_display_text(values.get(config["secondary_field_id"]))

    searchable_items: list[dict[str, str]] = []
    search_field_ids = list(config["searchable_field_ids"])
    for field_id in [config["primary_field_id"], config["secondary_field_id"]]:
        if field_id and field_id not in search_field_ids:
            search_field_ids.append(field_id)

    for field_id in search_field_ids:
        field = fields.get(field_id)
        value = record_value_display_text(values.get(field_id))
        if not field or not value:
            continue
        searchable_items.append(
            {
                "field_id": field_id,
                "label": compact_text(field.get("name")) or "Field",
                "value": value,
            }
        )

    fallback_primary_value = compact_text(fallback_primary)
    fallback_secondary_value = compact_text(fallback_secondary)
    search_parts: list[str] = []
    for part in [primary_value, secondary_value, *[item["value"] for item in searchable_items]]:
        text = compact_text(part)
        if text and text not in search_parts:
            search_parts.append(text)

    return {
        "primary_field_id": config["primary_field_id"],
        "primary_label": compact_text(primary_field.get("name")) if primary_field else "",
        "primary_value": primary_value or fallback_primary_value,
        "secondary_field_id": config["secondary_field_id"],
        "secondary_label": compact_text(secondary_field.get("name")) if secondary_field else "",
        "secondary_value": secondary_value or fallback_secondary_value,
        "searchable_fields": searchable_items,
        "search_text": " ".join(search_parts),
    }


def build_record_indexed_meta(
    raw_meta: Any,
    form_version: FormVersion,
    values: dict[str, Any],
    *,
    patient_name: str | None,
    patient_age: str | None,
    patient_sex: str | None,
    case_number: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    block_schema, _ = load_block_storage_document(form_version)
    normalized = normalize_record_indexed_meta(
        raw_meta,
        patient_name=patient_name,
        patient_age=patient_age,
        patient_sex=patient_sex,
        case_number=case_number,
    )
    identity = resolve_record_identity(
        block_schema,
        values,
        fallback_primary=compact_text(patient_name) or compact_text(normalized.get("patient_name")),
        fallback_secondary=compact_text(case_number) or compact_text(normalized.get("case_number")),
    )
    normalized["record_identity"] = identity
    normalized["record_search_text"] = identity["search_text"]
    meta = block_schema.get("meta") if isinstance(block_schema.get("meta"), dict) else {}
    signatory_slots = normalize_signatory_slots(meta.get("signatories"), use_defaults=False)
    signatory_snapshots = normalize_record_signatory_snapshots(
        normalized.get("signatories"),
        signatory_slots,
    )
    normalized["signatories"] = signatory_snapshots
    signatory_search = " ".join(
        compact_text(snapshot.get("name"))
        for snapshot in signatory_snapshots
        if isinstance(snapshot, dict) and compact_text(snapshot.get("name"))
    )
    if signatory_search:
        normalized["record_search_text"] = compact_text(f"{normalized['record_search_text']} {signatory_search}")
    return normalized, identity


def next_record_key(session: Session, form_slug: str) -> str:
    base = f"rec_{slugify(form_slug or 'record')}"
    while True:
        candidate = f"{base}_{uuid4().hex[:8]}"
        exists = session.scalar(select(Record.id).where(Record.record_key == candidate))
        if exists is None:
            return candidate


def form_path_label_for_record(record: Record) -> str:
    location = serialize_form_location(record.form)
    if location["location_kind"] == "top_level":
        return compact_text(record.form.name) or "Untitled Form"
    return f"{location['location_path_label']} / {compact_text(record.form.name) or 'Untitled Form'}"


def serialize_record_asset(asset: RecordAsset) -> dict[str, Any]:
    return {
        "id": asset.id,
        "field_block_id": asset.field_block_id,
        "field_key": asset.field_key,
        "kind": asset.kind,
        "storage_path": asset.storage_path,
        "original_filename": asset.original_filename,
        "mime_type": asset.mime_type,
        "size_bytes": asset.size_bytes,
        "image_width": asset.image_width,
        "image_height": asset.image_height,
        "created_at": asset.created_at.astimezone(timezone.utc).isoformat(),
    }


def format_timestamp_label(value: Any) -> str:
    if value is None:
        return ""
    try:
        local_value = value.astimezone()
    except Exception:
        return ""
    tz_name = compact_text(local_value.tzname()) or "local"
    return f"{local_value.strftime('%b %d, %Y %I:%M %p')} {tz_name}"


def format_compact_timestamp_label(value: Any) -> str:
    if value is None:
        return ""
    try:
        local_value = value.astimezone()
    except Exception:
        return ""
    return local_value.strftime("%b %d, %I:%M %p")


def serialize_record_actor(user: User | None) -> dict[str, Any] | None:
    if user is None:
        return None
    return {
        "id": user.id,
        "full_name": compact_text(user.full_name),
        "email": compact_text(user.email),
        "login_id": compact_text(user.login_id),
        "role": compact_text(user.role),
    }


def serialize_record_actor_snapshot(session: Session, actor_user_id: int | None) -> dict[str, Any] | None:
    if actor_user_id is None:
        return None
    return serialize_record_actor(session.get(User, actor_user_id))


def lifecycle_event_payload(
    session: Session,
    *,
    actor_user_id: int | None,
    reason: str = "",
) -> dict[str, Any]:
    event_time = utc_now()
    return {
        "at_utc": event_time.astimezone(timezone.utc).isoformat(),
        "at_label": format_timestamp_label(event_time),
        "reason": compact_text(reason),
        "by_user_id": actor_user_id,
        "by_user": serialize_record_actor_snapshot(session, actor_user_id),
    }


def record_lifecycle_meta(indexed_meta: dict[str, Any]) -> dict[str, Any]:
    lifecycle = indexed_meta.get("lifecycle")
    return lifecycle if isinstance(lifecycle, dict) else {}


class RecordCompletionValidationError(ValueError):
    def __init__(self, issues: list[str]):
        self.issues = issues
        super().__init__("Complete this record after filling the missing required details.")


def has_meaningful_record_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, dict):
        if value.get("kind") == "image" and value.get("asset_id"):
            return True
        return any(has_meaningful_record_value(item) for item in value.values())
    if isinstance(value, list):
        return any(has_meaningful_record_value(item) for item in value)
    return bool(compact_text(value))


def collect_required_record_field_issues(
    blocks: list[dict[str, Any]],
    values: dict[str, Any],
) -> list[str]:
    issues: list[str] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        kind = compact_text(block.get("kind"))
        if kind == "container":
            issues.extend(
                collect_required_record_field_issues(
                    normalize_items(block.get("children")),
                    values,
                )
            )
            continue
        if kind != "field":
            continue
        props = block.get("props") if isinstance(block.get("props"), dict) else {}
        if not bool(props.get("required")):
            continue
        block_id = compact_text(block.get("id"))
        field_name = compact_text(block.get("name")) or "Untitled field"
        if not has_meaningful_record_value(values.get(block_id)):
            issues.append(f"Fill in required field: {field_name}.")
    return issues


def list_record_completion_issues(
    record: Record,
    *,
    values: dict[str, Any],
    indexed_meta: dict[str, Any] | None = None,
) -> list[str]:
    issues: list[str] = []
    block_schema, _ = load_block_storage_document(record.form_version)
    issues.extend(
        collect_required_record_field_issues(
            normalize_items(block_schema.get("blocks")),
            values,
        )
    )
    meta = block_schema.get("meta") if isinstance(block_schema.get("meta"), dict) else {}
    signatory_slots = normalize_signatory_slots(meta.get("signatories"), use_defaults=False)
    resolved_meta = indexed_meta if isinstance(indexed_meta, dict) else load_json_object(record.indexed_meta_json)
    signatory_snapshots = normalize_record_signatory_snapshots(
        resolved_meta.get("signatories"),
        signatory_slots,
    )
    for slot, snapshot in zip(signatory_slots, signatory_snapshots):
        if not normalize_boolean_setting(slot.get("required"), default=False):
            continue
        slot_input_type = compact_text(slot.get("input_type")).lower()
        if slot_input_type in {"person_dropdown", "manual"} and not compact_text(snapshot.get("name")):
            label = compact_text(slot.get("label")).rstrip(":") or "Signatory"
            issues.append(f"Choose required signatory: {label}.")
    return issues


def validate_record_completion(
    record: Record,
    *,
    values: dict[str, Any],
    indexed_meta: dict[str, Any] | None = None,
) -> None:
    issues = list_record_completion_issues(
        record,
        values=values,
        indexed_meta=indexed_meta,
    )
    if issues:
        raise RecordCompletionValidationError(issues)


def parse_numeric_answer(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = compact_text(value)
    if not text:
        return None
    text = text.replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def build_print_reference(props: dict[str, Any]) -> str:
    reference_text = compact_text(props.get("reference_text"))
    if reference_text:
        return reference_text

    normal_min = compact_text(props.get("normal_min"))
    normal_max = compact_text(props.get("normal_max"))
    unit_hint = compact_text(props.get("unit_hint") or props.get("unit"))
    unit_suffix = f" {unit_hint}" if unit_hint else ""
    normal_min_operator = ">=" if normalize_boolean_setting(props.get("normal_min_inclusive"), default=True) else ">"
    normal_max_operator = "<=" if normalize_boolean_setting(props.get("normal_max_inclusive"), default=True) else "<"
    if normal_min and normal_max:
        if normal_min_operator != ">=" or normal_max_operator != "<=":
            return f"{normal_min_operator} {normal_min} to {normal_max_operator} {normal_max}{unit_suffix}"
        return f"{normal_min} to {normal_max}{unit_suffix}"
    if normal_min:
        return f"{normal_min_operator} {normal_min}{unit_suffix}"
    if normal_max:
        return f"{normal_max_operator} {normal_max}{unit_suffix}"
    return ""


def evaluate_numeric_abnormal(props: dict[str, Any], value: Any) -> tuple[bool, str | None]:
    numeric_value = parse_numeric_answer(value)
    if numeric_value is None:
        return False, None

    normal_min = parse_numeric_answer(props.get("normal_min"))
    normal_max = parse_numeric_answer(props.get("normal_max"))
    if normal_min is not None:
        min_is_inclusive = normalize_boolean_setting(props.get("normal_min_inclusive"), default=True)
        if numeric_value < normal_min or (not min_is_inclusive and numeric_value <= normal_min):
            return True, "low"
    if normal_max is not None:
        max_is_inclusive = normalize_boolean_setting(props.get("normal_max_inclusive"), default=True)
        if numeric_value > normal_max or (not max_is_inclusive and numeric_value >= normal_max):
            return True, "high"
    return False, None


def evaluate_choice_abnormal(props: dict[str, Any], value: Any) -> tuple[bool, str | None]:
    selected = compact_text(value)
    if not selected:
        return False, None

    options = normalize_items(props.get("options"))
    normal_names = {
        compact_text(option.get("name"))
        for option in options
        if isinstance(option, dict) and bool(option.get("is_normal")) and compact_text(option.get("name"))
    }
    if not normal_names:
        return False, None
    if selected in normal_names:
        return False, None
    return True, "abnormal"


def evaluate_print_abnormal(props: dict[str, Any], value: Any) -> tuple[bool, str | None]:
    data_type = compact_text(props.get("data_type"))
    control = compact_text(props.get("control"))

    if data_type == "image":
        return False, None
    if control == "select":
        return evaluate_choice_abnormal(props, value)
    return evaluate_numeric_abnormal(props, value)


def build_print_display_value(
    props: dict[str, Any],
    value: Any,
    image_asset: dict[str, Any] | None,
    *,
    record_id: int,
) -> dict[str, Any]:
    data_type = compact_text(props.get("data_type"))
    if data_type == "image":
        if image_asset is None:
            return {
                "kind": "image",
                "text": "",
                "image_url": None,
                "filename": "",
                "is_empty": True,
            }
        return {
            "kind": "image",
            "text": "",
            "image_url": f"/records/{record_id}/assets/{image_asset['id']}/file",
            "filename": compact_text(image_asset.get("original_filename")),
            "is_empty": False,
        }

    text_value = format_print_temporal_value(data_type, value)
    return {
        "kind": "text",
        "text": text_value,
        "image_url": None,
        "filename": "",
        "is_empty": not text_value,
    }


def build_print_utility_content(props: dict[str, Any]) -> str:
    return compact_text(props.get("content")) or ""


def build_print_table_columns(props: dict[str, Any]) -> list[str]:
    columns = [
        compact_text(column)
        for column in normalize_items(props.get("columns"))
        if compact_text(column)
    ]
    return columns or ["Column 1", "Column 2"]


def build_print_table_sample_rows(props: dict[str, Any]) -> int:
    try:
        sample_rows = int(props.get("sample_rows") or 0)
    except (TypeError, ValueError):
        sample_rows = 0
    return max(1, min(sample_rows or 3, 6))


def build_print_clinic_profile(
    clinic_profile: dict[str, Any] | None,
    *,
    logo_url: str = "",
) -> dict[str, Any]:
    profile = clinic_profile if isinstance(clinic_profile, dict) else {}
    name = compact_text(profile.get("clinic_name")) or ORGANIZATION_SHORT_NAME
    address = compact_text(profile.get("address"))
    contact_number = compact_text(profile.get("contact_number"))
    contact_email = compact_text(profile.get("contact_email"))
    doh_license_number = compact_text(profile.get("doh_license_number"))
    contact_parts = [part for part in [contact_number, contact_email] if part]

    return {
        "name": name,
        "address": address,
        "contact_number": contact_number,
        "contact_email": contact_email,
        "doh_license_number": doh_license_number,
        "contact_line": " | ".join(contact_parts),
        "logo_url": compact_text(logo_url) if bool(profile.get("has_logo")) else "",
    }


def build_print_field_item(
    block: dict[str, Any],
    values: dict[str, Any],
    asset_by_field: dict[str, dict[str, Any]],
    *,
    record_id: int,
    print_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    props = block.get("props") if isinstance(block.get("props"), dict) else {}
    config = print_config if isinstance(print_config, dict) else normalize_print_config({})
    block_id = compact_text(block.get("id"))
    raw_value = values.get(block_id)
    image_asset = asset_by_field.get(block_id)
    display = build_print_display_value(props, raw_value, image_asset, record_id=record_id)
    is_abnormal, abnormal_reason = evaluate_print_abnormal(props, raw_value)

    return {
        "kind": "field",
        "id": block_id,
        "name": compact_text(block.get("name")) or "Untitled Field",
        "unit_hint": compact_text(props.get("unit_hint")),
        "reference_text": build_print_reference(props),
        "display": display,
        "image_size": normalize_print_image_size(config.get("image_size")),
        "is_abnormal": is_abnormal,
        "abnormal_reason": abnormal_reason,
    }


def is_compact_grid_field_item(item: dict[str, Any]) -> bool:
    if compact_text(item.get("kind")) != "field":
        return False
    display = item.get("display") if isinstance(item.get("display"), dict) else {}
    return compact_text(display.get("kind")) != "image"


def print_layout_grid_id(layout_path: str, grid_index: int) -> str:
    return f"{compact_text(layout_path) or 'root'}:{max(0, grid_index)}"


def print_layout_field_run_id(layout_path: str, run_index: int) -> str:
    return f"{compact_text(layout_path) or 'root'}:run:{max(0, run_index)}"


def print_layout_standalone_field_run_id(layout_path: str, field_id: str) -> str:
    path = compact_text(layout_path) or "root"
    identifier = compact_text(field_id) or "field"
    return f"{path}:field:{identifier}"


def print_layout_container_id(layout_path: str, container_id: str) -> str:
    path = compact_text(layout_path) or "root"
    identifier = compact_text(container_id) or "container"
    return f"{path}/{identifier}"


def print_layout_container_run_id(layout_path: str, run_index: int) -> str:
    return f"{compact_text(layout_path) or 'root'}:containers:{max(0, run_index)}"


def print_layout_block_run_id(layout_path: str, run_index: int) -> str:
    return f"{compact_text(layout_path) or 'root'}:blocks:{max(0, run_index)}"


def compact_print_field_runs(
    items: list[dict[str, Any]],
    print_config: dict[str, Any],
    *,
    layout_path: str = "root",
) -> list[dict[str, Any]]:
    compacted: list[dict[str, Any]] = []
    run: list[dict[str, Any]] = []
    grid_index = 0
    run_index = 0
    use_compact_grid = normalize_print_result_layout(print_config.get("result_layout")) == "compact_grid"

    def flush_run() -> None:
        nonlocal run, grid_index, run_index
        if not run:
            return
        if use_compact_grid and len(run) >= 4:
            compacted.append(
                {
                    "kind": "field_grid",
                    "id": print_layout_grid_id(layout_path, grid_index),
                    "field_ids": [compact_text(item.get("id")) for item in run],
                    "items": run,
                }
            )
            grid_index += 1
        else:
            compacted.append(
                {
                    # Keep short/default field sequences visually as rows. The wrapper only
                    # gives the print editor a stable, independently configurable layout group.
                    "kind": "field_run",
                    "id": print_layout_field_run_id(layout_path, run_index),
                    "field_ids": [compact_text(item.get("id")) for item in run],
                    "items": run,
                }
            )
            run_index += 1
        run = []

    for item in items:
        if is_compact_grid_field_item(item):
            run.append(item)
            continue
        flush_run()
        if compact_text(item.get("kind")) == "field":
            # Images are intentionally excluded from compact result grids to
            # preserve their full-size print treatment. Keep each one in a
            # one-field run so it remains selectable in Adjust layout.
            field_id = compact_text(item.get("id"))
            compacted.append(
                {
                    "kind": "field_run",
                    "id": print_layout_standalone_field_run_id(layout_path, field_id),
                    "field_ids": [field_id] if field_id else [],
                    "items": [item],
                }
            )
            continue
        compacted.append(item)
    flush_run()
    return compacted


def is_print_container_item(item: dict[str, Any]) -> bool:
    return compact_text(item.get("kind")) in {"section", "group"} and bool(compact_text(item.get("id")))


def compact_print_container_runs(
    items: list[dict[str, Any]],
    *,
    layout_path: str = "root",
) -> list[dict[str, Any]]:
    """Group only adjacent sibling containers for optional print reflow.

    The default is a normal document flow. The wrapper therefore has no visual
    effect until a user explicitly arranges that sibling set in print preview.
    """
    compacted: list[dict[str, Any]] = []
    run: list[dict[str, Any]] = []
    run_index = 0

    def flush_run() -> None:
        nonlocal run, run_index
        if len(run) >= 2:
            compacted.append(
                {
                    "kind": "container_run",
                    "id": print_layout_container_run_id(layout_path, run_index),
                    "container_ids": [compact_text(item.get("id")) for item in run],
                    "items": run,
                }
            )
            run_index += 1
        else:
            compacted.extend(run)
        run = []

    for item in items:
        if is_print_container_item(item):
            run.append(item)
            continue
        flush_run()
        compacted.append(item)
    flush_run()
    return compacted


def is_print_layout_block_item(item: dict[str, Any]) -> bool:
    return (
        compact_text(item.get("kind")) in {"section", "group", "field_grid", "field_run", "container_run"}
        and bool(compact_text(item.get("id")))
    )


def compact_print_block_runs(
    items: list[dict[str, Any]],
    *,
    layout_path: str = "root",
) -> list[dict[str, Any]]:
    """Add an optional direct-sibling layout layer without changing default print.

    Field compaction is useful for the normal report, but it must not become a
    hidden constraint in the layout editor. A mixed run therefore keeps both its
    compact default representation and the original direct sibling items. The
    latter is used only after the user explicitly customizes that print area.
    """
    compacted: list[dict[str, Any]] = []
    run: list[dict[str, Any]] = []
    run_index = 0

    def direct_items(run_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        direct: list[dict[str, Any]] = []
        for run_item in run_items:
            kind = compact_text(run_item.get("kind"))
            if kind in {"field_grid", "field_run", "container_run"}:
                direct.extend(
                    child
                    for child in normalize_items(run_item.get("items"))
                    if isinstance(child, dict)
                )
            else:
                direct.append(run_item)
        return direct

    def flush_run() -> None:
        nonlocal run, run_index
        direct = direct_items(run)
        block_ids = [compact_text(item.get("id")) for item in direct]
        if (
            len(run) >= 2
            and len(direct) >= 2
            and all(block_ids)
            and len(set(block_ids)) == len(block_ids)
        ):
            compacted.append(
                {
                    "kind": "block_run",
                    "id": print_layout_block_run_id(layout_path, run_index),
                    "block_ids": block_ids,
                    "items": direct,
                    "default_items": run,
                }
            )
            run_index += 1
        else:
            compacted.extend(run)
        run = []

    for item in items:
        if is_print_layout_block_item(item):
            run.append(item)
            continue
        flush_run()
        compacted.append(item)
    flush_run()
    return compacted


def build_print_items(
    blocks: list[dict[str, Any]],
    values: dict[str, Any],
    asset_by_field: dict[str, dict[str, Any]],
    *,
    record_id: int,
    print_config: dict[str, Any] | None = None,
    container_depth: int = 0,
    layout_path: str = "root",
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    config = print_config if isinstance(print_config, dict) else normalize_print_config({})
    hide_empty_fields = normalize_boolean_setting(config.get("hide_empty_fields"), default=False)

    for block_index, block in enumerate(blocks):
        if not isinstance(block, dict):
            continue
        kind = compact_text(block.get("kind"))
        props = block.get("props") if isinstance(block.get("props"), dict) else {}

        if kind == "container":
            block_id = compact_text(block.get("id")) or f"container_{block_index}"
            child_items = build_print_items(
                normalize_items(block.get("children")),
                values,
                asset_by_field,
                record_id=record_id,
                print_config=config,
                container_depth=container_depth + 1,
                layout_path=f"{layout_path}/{block_id}",
            )
            if hide_empty_fields and not child_items:
                continue
            items.append(
                {
                    "kind": "section" if container_depth == 0 else "group",
                    "id": print_layout_container_id(layout_path, block_id),
                    "name": compact_text(block.get("name")) or "Untitled Container",
                    "container_depth": container_depth,
                    "show_title": normalize_boolean_setting(
                        config.get(
                            "show_top_level_container_titles"
                            if container_depth == 0
                            else "show_nested_container_titles"
                        ),
                        default=True,
                    ),
                    "items": child_items,
                }
            )
            continue

        if kind == "field":
            item = build_print_field_item(
                block,
                values,
                asset_by_field,
                record_id=record_id,
                print_config=config,
            )
            display = item.get("display") if isinstance(item.get("display"), dict) else {}
            optional_empty_image = (
                compact_text(props.get("data_type")) == "image"
                and not normalize_boolean_setting(props.get("required"), default=False)
                and bool(display.get("is_empty"))
            )
            if optional_empty_image or (hide_empty_fields and bool(display.get("is_empty"))):
                continue
            items.append(item)
            continue

        if kind == "note":
            items.append(
                {
                    "kind": "note",
                    "name": compact_text(block.get("name")) or "",
                    "content": build_print_utility_content(props),
                }
            )
            continue

        if kind == "divider":
            items.append(
                {
                    "kind": "divider",
                    "name": compact_text(block.get("name")) or "",
                    "content": build_print_utility_content(props),
                }
            )
            continue

        if kind == "table":
            items.append(
                {
                    "kind": "table",
                    "name": compact_text(block.get("name")) or "Table",
                    "columns": build_print_table_columns(props),
                    "sample_rows": build_print_table_sample_rows(props),
                    "table_density": normalize_print_table_density(config.get("table_density")),
                }
            )
            continue

    return compact_print_block_runs(
        compact_print_container_runs(
            compact_print_field_runs(items, config, layout_path=layout_path),
            layout_path=layout_path,
        ),
        layout_path=layout_path,
    )


def print_layout_allowed_spans(field_grid_units: int) -> set[int]:
    units = max(2, int(field_grid_units or 0))
    if units <= 4:
        return {2, units}
    return {2, units // 2, max(2, units - 2), units}


def balanced_print_grid_spans(field_ids: list[str], field_grid_units: int) -> dict[str, int]:
    units = max(2, int(field_grid_units or 0))
    base_span = 2
    spans = {field_id: base_span for field_id in field_ids}
    current_row: list[str] = []
    used_units = 0

    for field_id in field_ids:
        if used_units + base_span > units:
            current_row = []
            used_units = 0
        current_row.append(field_id)
        used_units += base_span

    if len(current_row) == 1:
        spans[current_row[0]] = units
    elif len(current_row) == 2 and used_units < units and units % 2 == 0:
        for field_id in current_row:
            spans[field_id] = units // 2
    return spans


def print_grid_placeholder_spans(
    field_ids: list[str],
    spans: dict[str, int],
    *,
    field_grid_units: int,
    preserve_grid_cells: bool,
) -> list[int]:
    units = max(2, int(field_grid_units or 0))
    used_units = 0
    for field_id in field_ids:
        span = int(spans.get(field_id) or 2)
        if used_units + span > units:
            used_units = 0
        used_units += span
        if used_units == units:
            used_units = 0
    if not used_units:
        return []

    remaining_units = units - used_units
    if preserve_grid_cells and remaining_units % 2 == 0:
        return [2] * (remaining_units // 2)
    return [remaining_units]


def matching_print_layout_order(raw_order: Any, item_ids: list[str]) -> list[str]:
    order = normalize_print_layout_order(raw_order)
    return order if len(order) == len(item_ids) and set(order) == set(item_ids) else list(item_ids)


def print_layout_item_ids_match(
    configured_item_ids: list[str],
    canonical_item_ids: list[str],
) -> bool:
    """Accept the same direct children regardless of their saved visual order."""
    return (
        bool(canonical_item_ids)
        and len(configured_item_ids) == len(canonical_item_ids)
        and set(configured_item_ids) == set(canonical_item_ids)
    )


def apply_print_layout_item_order(
    item: dict[str, Any],
    layout: dict[str, Any],
    *,
    item_ids_key: str,
) -> None:
    child_items = item.get("items")
    if not isinstance(child_items, list):
        return
    for index, child in enumerate(child_items):
        if isinstance(child, dict):
            child["_print_layout_original_index"] = index
    item_ids = [compact_text(value) for value in normalize_items(layout.get(item_ids_key))]
    order = matching_print_layout_order(layout.get("order"), item_ids)
    child_by_id = {
        compact_text(child.get("id")): child
        for child in child_items
        if isinstance(child, dict) and compact_text(child.get("id"))
    }
    if len(child_by_id) == len(item_ids) and all(item_id in child_by_id for item_id in order):
        item["items"] = [child_by_id[item_id] for item_id in order]


def normalized_print_grid_layout(
    grid_item: dict[str, Any],
    preference: dict[str, Any],
    *,
    field_grid_units: int,
) -> dict[str, Any]:
    field_ids = [compact_text(field_id) for field_id in normalize_items(grid_item.get("field_ids"))]
    field_ids = [field_id for field_id in field_ids if field_id]
    grid_id = compact_text(grid_item.get("id"))
    raw_grids = preference.get("grids") if isinstance(preference.get("grids"), dict) else {}
    raw_layout = raw_grids.get(grid_id) if isinstance(raw_grids.get(grid_id), dict) else {}
    raw_field_ids = [compact_text(field_id) for field_id in normalize_items(raw_layout.get("field_ids"))]
    is_matching_grid = bool(
        grid_id and print_layout_item_ids_match(raw_field_ids, field_ids)
    )
    mode = normalize_print_layout_mode(raw_layout.get("mode")) if is_matching_grid else "preserve"
    order = matching_print_layout_order(raw_layout.get("order"), field_ids) if is_matching_grid else field_ids
    allowed_spans = print_layout_allowed_spans(field_grid_units)
    spans = {field_id: 2 for field_id in field_ids}

    if mode == "balance":
        spans = balanced_print_grid_spans(field_ids, field_grid_units)
    elif mode == "manual":
        raw_spans = raw_layout.get("spans") if isinstance(raw_layout.get("spans"), dict) else {}
        for field_id in field_ids:
            try:
                span = int(raw_spans.get(field_id) or 2)
            except (TypeError, ValueError):
                span = 2
            spans[field_id] = span if span in allowed_spans else 2

    return {
        "id": grid_id,
        "field_ids": field_ids,
        "mode": mode,
        "order": order,
        "spans": spans,
        "units": field_grid_units,
        "allowed_spans": sorted(allowed_spans),
        "placeholder_spans": print_grid_placeholder_spans(
            field_ids,
            spans,
            field_grid_units=field_grid_units,
            preserve_grid_cells=mode == "preserve",
        ),
    }


def normalized_print_field_run_layout(
    run_item: dict[str, Any],
    preference: dict[str, Any],
    *,
    field_grid_units: int,
) -> dict[str, Any]:
    """Return a row-first layout for a short/default field run.

    A field run must retain its original row presentation until the user explicitly
    selects it and changes it to a grid from print preview.
    """
    field_ids = [compact_text(field_id) for field_id in normalize_items(run_item.get("field_ids"))]
    field_ids = [field_id for field_id in field_ids if field_id]
    run_id = compact_text(run_item.get("id"))
    raw_grids = preference.get("grids") if isinstance(preference.get("grids"), dict) else {}
    raw_layout = raw_grids.get(run_id) if isinstance(raw_grids.get(run_id), dict) else {}
    raw_field_ids = [compact_text(field_id) for field_id in normalize_items(raw_layout.get("field_ids"))]
    is_matching_run = bool(
        run_id and print_layout_item_ids_match(raw_field_ids, field_ids)
    )
    configured_mode = normalize_print_layout_mode(raw_layout.get("mode")) if is_matching_run else "preserve"
    mode = configured_mode if configured_mode in {"balance", "manual"} else "rows"
    order = matching_print_layout_order(raw_layout.get("order"), field_ids) if is_matching_run else field_ids
    allowed_spans = print_layout_allowed_spans(field_grid_units)
    spans = {field_id: 2 for field_id in field_ids}

    if mode == "balance":
        spans = balanced_print_grid_spans(field_ids, field_grid_units)
    elif mode == "manual":
        raw_spans = raw_layout.get("spans") if isinstance(raw_layout.get("spans"), dict) else {}
        for field_id in field_ids:
            try:
                span = int(raw_spans.get(field_id) or 2)
            except (TypeError, ValueError):
                span = 2
            spans[field_id] = span if span in allowed_spans else 2

    return {
        "id": run_id,
        "field_ids": field_ids,
        "mode": mode,
        "presentation": "grid" if mode in {"balance", "manual"} else "rows",
        "order": order,
        "spans": spans,
        "units": field_grid_units,
        "allowed_spans": sorted(allowed_spans),
        "placeholder_spans": (
            print_grid_placeholder_spans(
                field_ids,
                spans,
                field_grid_units=field_grid_units,
                preserve_grid_cells=False,
            )
            if mode in {"balance", "manual"}
            else []
        ),
    }


def normalized_print_container_run_layout(
    run_item: dict[str, Any],
    preference: dict[str, Any],
    *,
    field_grid_units: int,
) -> dict[str, Any]:
    container_ids = [
        compact_text(container_id)
        for container_id in normalize_items(run_item.get("container_ids"))
    ]
    container_ids = [container_id for container_id in container_ids if container_id]
    run_id = compact_text(run_item.get("id"))
    raw_containers = preference.get("containers") if isinstance(preference.get("containers"), dict) else {}
    raw_layout = raw_containers.get(run_id) if isinstance(raw_containers.get(run_id), dict) else {}
    raw_container_ids = [
        compact_text(container_id)
        for container_id in normalize_items(raw_layout.get("container_ids"))
    ]
    is_matching_run = bool(
        run_id
        and len(container_ids) >= 2
        and print_layout_item_ids_match(raw_container_ids, container_ids)
    )
    mode = normalize_print_container_layout_mode(raw_layout.get("mode")) if is_matching_run else "flow"
    order = (
        matching_print_layout_order(raw_layout.get("order"), container_ids)
        if is_matching_run
        else container_ids
    )
    allowed_spans = print_layout_allowed_spans(field_grid_units)
    spans = {container_id: 2 for container_id in container_ids}

    if mode == "balance":
        spans = balanced_print_grid_spans(container_ids, field_grid_units)
    elif mode == "manual":
        raw_spans = raw_layout.get("spans") if isinstance(raw_layout.get("spans"), dict) else {}
        for container_id in container_ids:
            try:
                span = int(raw_spans.get(container_id) or 2)
            except (TypeError, ValueError):
                span = 2
            spans[container_id] = span if span in allowed_spans else 2

    return {
        "id": run_id,
        "container_ids": container_ids,
        "mode": mode,
        "presentation": "grid" if mode in {"balance", "manual"} else "flow",
        "order": order,
        "spans": spans,
        "units": field_grid_units,
        "allowed_spans": sorted(allowed_spans),
        "placeholder_spans": [],
    }


def normalized_print_block_run_layout(
    run_item: dict[str, Any],
    preference: dict[str, Any],
    *,
    field_grid_units: int,
) -> dict[str, Any]:
    block_ids = [compact_text(block_id) for block_id in normalize_items(run_item.get("block_ids"))]
    block_ids = [block_id for block_id in block_ids if block_id]
    run_id = compact_text(run_item.get("id"))
    raw_blocks = preference.get("blocks") if isinstance(preference.get("blocks"), dict) else {}
    raw_layout = raw_blocks.get(run_id) if isinstance(raw_blocks.get(run_id), dict) else {}
    raw_block_ids = [compact_text(block_id) for block_id in normalize_items(raw_layout.get("block_ids"))]
    is_matching_run = bool(
        run_id
        and len(block_ids) >= 2
        and print_layout_item_ids_match(raw_block_ids, block_ids)
    )
    mode = normalize_print_container_layout_mode(raw_layout.get("mode")) if is_matching_run else "flow"
    order = (
        matching_print_layout_order(raw_layout.get("order"), block_ids)
        if is_matching_run
        else block_ids
    )
    allowed_spans = print_layout_allowed_spans(field_grid_units)
    spans = {block_id: 2 for block_id in block_ids}

    if mode == "balance":
        spans = balanced_print_grid_spans(block_ids, field_grid_units)
    elif mode == "manual":
        raw_spans = raw_layout.get("spans") if isinstance(raw_layout.get("spans"), dict) else {}
        for block_id in block_ids:
            try:
                span = int(raw_spans.get(block_id) or 2)
            except (TypeError, ValueError):
                span = 2
            spans[block_id] = span if span in allowed_spans else 2

    return {
        "id": run_id,
        "block_ids": block_ids,
        "mode": mode,
        "presentation": "grid" if mode in {"balance", "manual"} else "flow",
        "order": order,
        "spans": spans,
        "units": field_grid_units,
        "allowed_spans": sorted(allowed_spans),
        "placeholder_spans": [],
    }


def apply_print_layout_preference(
    items: list[dict[str, Any]],
    preference: dict[str, Any] | None,
    *,
    field_grid_units: int,
) -> list[dict[str, Any]]:
    normalized_preference = normalize_print_layout_preference(preference)
    for item in items:
        if not isinstance(item, dict):
            continue
        kind = compact_text(item.get("kind"))
        if kind == "field_grid":
            item["layout"] = normalized_print_grid_layout(
                item,
                normalized_preference,
                field_grid_units=field_grid_units,
            )
            apply_print_layout_item_order(
                item,
                item["layout"],
                item_ids_key="field_ids",
            )
            continue
        if kind == "field_run":
            item["layout"] = normalized_print_field_run_layout(
                item,
                normalized_preference,
                field_grid_units=field_grid_units,
            )
            apply_print_layout_item_order(
                item,
                item["layout"],
                item_ids_key="field_ids",
            )
            continue
        if kind == "container_run":
            item["layout"] = normalized_print_container_run_layout(
                item,
                normalized_preference,
                field_grid_units=field_grid_units,
            )
            apply_print_layout_item_order(
                item,
                item["layout"],
                item_ids_key="container_ids",
            )
        if kind == "block_run":
            # The compact default items own the nested field/container layouts.
            # Apply those first, then apply the direct-sibling order and spans to
            # the custom layout layer itself.
            default_items = item.get("default_items")
            if isinstance(default_items, list):
                apply_print_layout_preference(
                    default_items,
                    normalized_preference,
                    field_grid_units=field_grid_units,
                )
            item["layout"] = normalized_print_block_run_layout(
                item,
                normalized_preference,
                field_grid_units=field_grid_units,
            )
            apply_print_layout_item_order(
                item,
                item["layout"],
                item_ids_key="block_ids",
            )
            continue
        child_items = item.get("items")
        if isinstance(child_items, list):
            apply_print_layout_preference(
                child_items,
                normalized_preference,
                field_grid_units=field_grid_units,
            )
    return items


def filter_print_layout_preference_for_items(
    preference: Any,
    items: list[dict[str, Any]],
    *,
    field_grid_units: int,
) -> dict[str, Any]:
    normalized_preference = normalize_print_layout_preference(preference)
    valid_grids: dict[str, dict[str, Any]] = {}
    valid_containers: dict[str, dict[str, Any]] = {}
    valid_blocks: dict[str, dict[str, Any]] = {}

    def collect(item_list: list[dict[str, Any]]) -> None:
        for item in item_list:
            if not isinstance(item, dict):
                continue
            kind = compact_text(item.get("kind"))
            if kind == "field_grid":
                layout = normalized_print_grid_layout(
                    item,
                    normalized_preference,
                    field_grid_units=field_grid_units,
                )
                has_custom_order = layout["order"] != layout["field_ids"]
                if layout["mode"] != "preserve" or has_custom_order:
                    valid_grids[layout["id"]] = {
                        "field_ids": layout["field_ids"],
                        "mode": layout["mode"],
                        "spans": layout["spans"] if layout["mode"] == "manual" else {},
                        "order": layout["order"] if has_custom_order else [],
                    }
                continue
            if kind == "field_run":
                layout = normalized_print_field_run_layout(
                    item,
                    normalized_preference,
                    field_grid_units=field_grid_units,
                )
                has_custom_order = layout["order"] != layout["field_ids"]
                if layout["mode"] != "rows" or has_custom_order:
                    valid_grids[layout["id"]] = {
                        "field_ids": layout["field_ids"],
                        "mode": layout["mode"],
                        "spans": layout["spans"] if layout["mode"] == "manual" else {},
                        "order": layout["order"] if has_custom_order else [],
                    }
                continue
            if kind == "container_run":
                layout = normalized_print_container_run_layout(
                    item,
                    normalized_preference,
                    field_grid_units=field_grid_units,
                )
                has_custom_order = layout["order"] != layout["container_ids"]
                if layout["mode"] != "flow" or has_custom_order:
                    valid_containers[layout["id"]] = {
                        "container_ids": layout["container_ids"],
                        "mode": layout["mode"],
                        "spans": layout["spans"] if layout["mode"] == "manual" else {},
                        "order": layout["order"] if has_custom_order else [],
                    }
                child_items = item.get("items")
                if isinstance(child_items, list):
                    collect(child_items)
                continue
            if kind == "block_run":
                layout = normalized_print_block_run_layout(
                    item,
                    normalized_preference,
                    field_grid_units=field_grid_units,
                )
                has_custom_order = layout["order"] != layout["block_ids"]
                if layout["mode"] != "flow" or has_custom_order:
                    valid_blocks[layout["id"]] = {
                        "block_ids": layout["block_ids"],
                        "mode": layout["mode"],
                        "spans": layout["spans"] if layout["mode"] == "manual" else {},
                        "order": layout["order"] if has_custom_order else [],
                    }
                default_items = item.get("default_items")
                if isinstance(default_items, list):
                    collect(default_items)
                continue
            child_items = item.get("items")
            if isinstance(child_items, list):
                collect(child_items)

    collect(items)
    return {
        "version": PRINT_LAYOUT_PREFERENCE_VERSION,
        "grids": valid_grids,
        "containers": valid_containers,
        "blocks": valid_blocks,
    }


def build_print_summary_items(
    print_config: dict[str, Any],
    serialized: dict[str, Any],
    values: dict[str, Any],
    *,
    issued_at_label: str,
) -> list[dict[str, str]]:
    if not normalize_boolean_setting(print_config.get("show_summary"), default=False):
        return []

    entry_schema = serialized.get("entry_schema") if isinstance(serialized.get("entry_schema"), dict) else {}
    identity = serialized.get("record_identity") if isinstance(serialized.get("record_identity"), dict) else {}
    fields = record_field_lookup(entry_schema)
    summary_items: list[dict[str, str]] = []

    for item in normalize_items(print_config.get("summary_items")):
        if not isinstance(item, dict):
            continue
        source = compact_text(item.get("source")).lower()
        label = compact_text(item.get("label")) or default_print_summary_label(source)
        value = ""

        if source == "field":
            field_id = compact_text(item.get("field_id"))
            field = fields.get(field_id)
            if not compact_text(item.get("label")) and field:
                label = compact_text(field.get("name")) or "Field"
            field_block = field.get("block") if isinstance(field, dict) and isinstance(field.get("block"), dict) else {}
            field_props = field_block.get("props") if isinstance(field_block.get("props"), dict) else {}
            field_data_type = compact_text(field_props.get("data_type"))
            if field_data_type in {"date", "time", "datetime"}:
                value = format_print_temporal_value(field_data_type, values.get(field_id))
            else:
                value = record_value_display_text(values.get(field_id))
        elif source == "primary_identity":
            label = compact_text(item.get("label")) or compact_text(identity.get("primary_label")) or "Record"
            value = compact_text(identity.get("primary_value"))
        elif source == "secondary_identity":
            label = compact_text(item.get("label")) or compact_text(identity.get("secondary_label")) or "Detail"
            value = compact_text(identity.get("secondary_value"))
        elif source == "record_key":
            value = compact_text(serialized.get("record_key"))
        elif source == "issued_at":
            value = issued_at_label
        elif source == "form_version":
            value = compact_text(serialized.get("form_version_label")) or f"v{serialized['form_version_number']}"

        if source in {"primary_identity", "secondary_identity"} and not value:
            continue
        summary_items.append({"label": label, "value": value or "Not set yet"})

    if not summary_items:
        summary_items.append({"label": "Record", "value": compact_text(serialized.get("record_key"))})
    return summary_items


def resolve_print_signature_name(
    source: str,
    *,
    field_id: str,
    manual_name: str,
    prepared_by_name: str,
    values: dict[str, Any],
) -> str:
    normalized_source = normalize_print_signature_source(source)
    if normalized_source == "prepared_by":
        return compact_text(prepared_by_name)
    if normalized_source == "manual":
        return compact_text(manual_name)
    if normalized_source == "field":
        return record_value_display_text(values.get(field_id))
    return ""


def build_print_signature_items(
    print_config: dict[str, Any],
    values: dict[str, Any],
    *,
    prepared_by_name: str,
    signatories: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if signatories is not None:
        signature_items = signatory_snapshots_for_print(signatories)
        if signature_items:
            return signature_items

    signatures: list[dict[str, Any]] = []
    for side, fallback_label in (("left", "Medical Technologist"), ("right", "Pathologist")):
        label = compact_text(print_config.get(f"signature_{side}_label")) or fallback_label
        source = normalize_print_signature_source(print_config.get(f"signature_{side}_source"))
        manual_name = compact_text(print_config.get(f"signature_{side}_name"))
        field_id = compact_text(print_config.get(f"signature_{side}_field_id"))
        signatures.append(
            {
                "label": label,
                "name": resolve_print_signature_name(
                    source,
                    field_id=field_id,
                    manual_name=manual_name,
                    prepared_by_name=prepared_by_name,
                    values=values,
                ),
                "source": source,
                "field_id": field_id if source == "field" else "",
                "signature_line": True,
            }
        )
    return signatures


def sample_print_value_for_field(block: dict[str, Any]) -> Any:
    props = block.get("props") if isinstance(block.get("props"), dict) else {}
    key = compact_text(props.get("key")).lower()
    name = compact_text(block.get("name")).lower()
    label = f"{key} {name}"
    data_type = compact_text(props.get("data_type")).lower()
    control = compact_text(props.get("control")).lower()

    if data_type == "image":
        return ""
    if "case" in label and "number" in label:
        return "NAIC-2026-0001"
    if key == "name" or name == "name" or "patient name" in label:
        return "Juan Dela Cruz"
    if "age" in label:
        return "34"
    if "sex" in label or "gender" in label:
        return "Male"
    if data_type == "datetime":
        return "2026-04-29 09:30"
    if data_type == "date":
        return "2026-04-29"
    if data_type == "time":
        return "09:30"
    if data_type not in {"number", "enum"} and "date" in label and "time" in label:
        return "2026-04-29 09:30"
    if data_type not in {"number", "enum"} and "date" in label:
        return "2026-04-29"
    if data_type not in {"number", "enum"} and "time" in label:
        return "09:30"
    if "requesting" in label and "physician" in label:
        return "Dr. Reyes"
    if "room" in label:
        return "OPD"
    if "medical technologist" in label or "medtech" in label:
        return "Sample Medtech"
    if "pathologist" in label:
        return "Sample Pathologist"

    if control == "select":
        options = [
            option
            for option in normalize_items(props.get("options"))
            if isinstance(option, dict) and compact_text(option.get("name"))
        ]
        normal_option = next((option for option in options if bool(option.get("is_normal"))), None)
        selected_option = normal_option or (options[0] if options else None)
        return compact_text(selected_option.get("name")) if selected_option else "Sample option"

    if data_type == "number":
        normal_min = compact_text(props.get("normal_min"))
        normal_max = compact_text(props.get("normal_max"))
        if normal_min and normal_max:
            min_value = parse_numeric_answer(normal_min)
            max_value = parse_numeric_answer(normal_max)
            if min_value is not None and max_value is not None:
                return f"{((min_value + max_value) / 2):g}"
        return normal_min or normal_max or "1.0"

    return "Sample value"


def build_sample_print_values(blocks: list[dict[str, Any]]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for block in blocks:
        if not isinstance(block, dict):
            continue
        kind = compact_text(block.get("kind"))
        if kind == "field":
            block_id = compact_text(block.get("id"))
            if block_id:
                values[block_id] = sample_print_value_for_field(block)
            continue
        values.update(build_sample_print_values(normalize_items(block.get("children"))))
    return values


def print_layout_row_count(item: dict[str, Any]) -> int:
    fields = normalize_items(item.get("items"))
    field_ids = [compact_text(field.get("id")) for field in fields if isinstance(field, dict)]
    layout = item.get("layout") if isinstance(item.get("layout"), dict) else {}
    try:
        units = max(2, int(layout.get("units") or 4))
    except (TypeError, ValueError):
        units = 4
    spans = layout.get("spans") if isinstance(layout.get("spans"), dict) else {}
    used_units = 0
    row_count = 0

    for field_id in field_ids:
        try:
            span = int(spans.get(field_id) or 2)
        except (TypeError, ValueError):
            span = 2
        if span not in print_layout_allowed_spans(units):
            span = 2
        if used_units + span > units:
            row_count += 1
            used_units = 0
        used_units += span
        if used_units == units:
            row_count += 1
            used_units = 0
    return max(1, row_count + (1 if used_units else 0))


def print_container_run_fit_units(item: dict[str, Any]) -> float:
    layout = item.get("layout") if isinstance(item.get("layout"), dict) else {}
    child_items = [child for child in normalize_items(item.get("items")) if isinstance(child, dict)]
    if compact_text(layout.get("presentation")) != "grid":
        return print_item_fit_units(child_items)
    try:
        units = max(2, int(layout.get("units") or 4))
    except (TypeError, ValueError):
        units = 4
    allowed_spans = print_layout_allowed_spans(units)
    spans = layout.get("spans") if isinstance(layout.get("spans"), dict) else {}
    current_width = 0
    current_height = 0.0
    total_height = 0.0

    for child in child_items:
        container_id = compact_text(child.get("id"))
        try:
            span = int(spans.get(container_id) or 2)
        except (TypeError, ValueError):
            span = 2
        if span not in allowed_spans:
            span = 2
        if current_width and current_width + span > units:
            total_height += current_height
            current_width = 0
            current_height = 0.0
        current_width += span
        current_height = max(current_height, print_item_fit_units([child]))
        if current_width == units:
            total_height += current_height
            current_width = 0
            current_height = 0.0
    return total_height + current_height


def print_block_run_fit_units(item: dict[str, Any]) -> float:
    layout = item.get("layout") if isinstance(item.get("layout"), dict) else {}
    child_items = [child for child in normalize_items(item.get("items")) if isinstance(child, dict)]
    if compact_text(layout.get("presentation")) != "grid":
        default_items = [
            child
            for child in normalize_items(item.get("default_items"))
            if isinstance(child, dict)
        ]
        return print_item_fit_units(default_items or child_items)
    try:
        units = max(2, int(layout.get("units") or 4))
    except (TypeError, ValueError):
        units = 4
    allowed_spans = print_layout_allowed_spans(units)
    spans = layout.get("spans") if isinstance(layout.get("spans"), dict) else {}
    current_width = 0
    current_height = 0.0
    total_height = 0.0

    for child in child_items:
        block_id = compact_text(child.get("id"))
        try:
            span = int(spans.get(block_id) or 2)
        except (TypeError, ValueError):
            span = 2
        if span not in allowed_spans:
            span = 2
        if current_width and current_width + span > units:
            total_height += current_height
            current_width = 0
            current_height = 0.0
        current_width += span
        current_height = max(current_height, print_item_fit_units([child]))
        if current_width == units:
            total_height += current_height
            current_width = 0
            current_height = 0.0
    return total_height + current_height


def print_item_fit_units(items: list[dict[str, Any]]) -> float:
    units = 0.0
    for item in normalize_items(items):
        if not isinstance(item, dict):
            continue
        kind = compact_text(item.get("kind"))
        if kind == "section":
            units += 1.7 + print_item_fit_units(normalize_items(item.get("items")))
        elif kind == "group":
            units += 1.25 + print_item_fit_units(normalize_items(item.get("items")))
        elif kind == "field":
            display = item.get("display") if isinstance(item.get("display"), dict) else {}
            units += 1.15
            if compact_text(item.get("reference_text")):
                units += 0.25
            if display.get("kind") == "image" and not display.get("is_empty"):
                units += 5.0
        elif kind == "field_grid":
            fields = normalize_items(item.get("items"))
            row_count = print_layout_row_count(item)
            reference_count = sum(
                1
                for field in fields
                if isinstance(field, dict) and compact_text(field.get("reference_text"))
            )
            units += 0.45 + (row_count * 0.95) + (reference_count * 0.15)
        elif kind == "field_run":
            layout = item.get("layout") if isinstance(item.get("layout"), dict) else {}
            fields = normalize_items(item.get("items"))
            if compact_text(layout.get("presentation")) != "grid":
                units += print_item_fit_units(fields)
                continue
            row_count = print_layout_row_count(item)
            reference_count = sum(
                1
                for field in fields
                if isinstance(field, dict) and compact_text(field.get("reference_text"))
            )
            units += 0.45 + (row_count * 0.95) + (reference_count * 0.15)
        elif kind == "container_run":
            units += print_container_run_fit_units(item)
        elif kind == "block_run":
            units += print_block_run_fit_units(item)
        elif kind == "table":
            try:
                sample_rows = int(item.get("sample_rows") or 3)
            except (TypeError, ValueError):
                sample_rows = 3
            units += 1.4 + (max(1, min(sample_rows, 6)) * 0.65)
        elif kind in {"note", "divider"}:
            units += 0.8
    return units


def estimate_print_page_fit(document: dict[str, Any]) -> dict[str, Any]:
    print_config = document.get("print_config") if isinstance(document.get("print_config"), dict) else {}
    density = normalize_print_density(print_config.get("density"))
    profile = normalize_print_profile(
        template_id=print_config.get("template_id"),
        style=print_config.get("style"),
        orientation=print_config.get("orientation"),
        text_size=print_config.get("text_size"),
        paper_size=print_config.get("paper_size"),
    )
    template_id = profile["template_id"]
    text_size = profile["text_size"]
    show_summary = normalize_boolean_setting(print_config.get("show_summary"), default=False)
    summary_count = len(normalize_items(document.get("summary_items"))) if show_summary else 0
    base_units = 8.5
    if normalize_boolean_setting(print_config.get("show_logo"), default=True):
        base_units += 1.2
    if normalize_boolean_setting(print_config.get("show_clinic_info"), default=True):
        base_units += 1.0
    if normalize_boolean_setting(print_config.get("show_signatures"), default=True):
        base_units += 4.2
    if show_summary and summary_count:
        base_units += max(1, (summary_count + 2) // 3) * 2.2

    density_factor = 1.14 if density == "comfortable" else 1.0
    capabilities = print_template_paper_capabilities(template_id, profile["paper_size"])
    if text_size == "large":
        density_factor *= capabilities["large_text_fit_factor"]
    estimated_units = (base_units + print_item_fit_units(normalize_items(document.get("items")))) * density_factor
    limit_units = print_page_fit_limit_units(profile)
    paper_size = profile["paper_size"]
    page_size_label = PRINT_PAPER_SIZE_DETAILS[paper_size]["label"]
    requires_one_page = bool(capabilities.get("requires_one_page"))
    likely_fit_ratio = 0.90 if requires_one_page else 0.82
    if estimated_units <= limit_units * likely_fit_ratio:
        status = "likely"
        label = "Likely 1 page"
        detail = (
            "Legacy A5 is configured to print this record on one page."
            if requires_one_page
            else f"The current sample looks safely within the {page_size_label} target."
        )
    elif estimated_units <= limit_units:
        status = "tight"
        label = "Check print preview"
        detail = (
            "A5 has limited vertical space. Check browser print preview before release."
            if paper_size == "a5"
            else "This should be checked in browser print preview before release."
        )
    else:
        status = "long"
        label = "Likely 2 pages"
        detail = (
            "This A5 layout will likely continue on another page. You can still print it, "
            "or use a larger paper size."
            if paper_size == "a5"
            else "Consider compact density, fewer summary rows, or hiding optional output later."
        )

    return {
        "status": status,
        "label": label,
        "detail": detail,
        "estimated_units": round(estimated_units, 1),
        "limit_units": limit_units,
        "requires_one_page": requires_one_page,
        # Fit feedback is advisory. Browser and printer settings must never
        # block a record from being printed, including a multi-page result.
        "can_print": True,
    }


def build_form_print_preview_document(
    *,
    form_name: str,
    form_path_label: str = "",
    block_schema: dict[str, Any],
    clinic_profile: dict[str, Any] | None = None,
    clinic_logo_url: str = "",
    template_id: Any = "",
    style: Any = "",
    orientation: Any = "",
    text_size: Any = "",
    paper_size: Any = "",
    print_layout_preference: dict[str, Any] | None = None,
) -> dict[str, Any]:
    entry_schema = json.loads(json.dumps(block_schema if isinstance(block_schema, dict) else {}))
    if not entry_schema:
        entry_schema = {
            "schema_version": 1,
            "source_kind": ACTIVE_BLOCK_SCHEMA_SOURCE,
            "meta": {},
            "blocks": [],
        }
    normalize_active_block_storage_schema(entry_schema)

    values = build_sample_print_values(normalize_items(entry_schema.get("blocks")))
    identity = resolve_record_identity(
        entry_schema,
        values,
        fallback_primary="Juan Dela Cruz",
        fallback_secondary="NAIC-2026-0001",
    )
    meta = entry_schema.get("meta") if isinstance(entry_schema.get("meta"), dict) else {}
    print_config = apply_print_presentation(
        normalize_print_config(meta.get("print_config")),
        template_id=template_id,
        style=style,
        orientation=orientation,
        text_size=text_size,
        paper_size=paper_size,
    )
    signatory_slots = normalize_signatory_slots(meta.get("signatories"), use_defaults=False)
    signatory_samples = normalize_record_signatory_snapshots({}, signatory_slots)
    print_accent_ink = print_accent_text_color(print_config.get("accent_color"))
    print_header_ink = print_header_text_color(print_config)
    normalized_form_name = compact_text(form_name) or "Untitled Form"
    normalized_path = compact_text(form_path_label) or "Builder preview"
    report_title = resolve_print_report_title(
        print_config,
        form_name=normalized_form_name,
        form_path_label=normalized_path,
    )
    serialized = {
        "id": 0,
        "record_key": "PREVIEW-0001",
        "entry_schema": entry_schema,
        "values": values,
        "asset_by_field_id": {},
        "record_identity": identity,
        "status": "draft",
        "form_name": normalized_form_name,
        "form_path_label": normalized_path,
        "form_version_number": "draft",
        "form_version_label": "Draft preview",
        "created_at_label": "Preview sample",
        "updated_at_label": "Preview sample",
        "completed_at_label": "",
    }
    summary_items = build_print_summary_items(
        print_config,
        serialized,
        values,
        issued_at_label="Preview sample",
    )
    presentation = print_presentation_details(
        print_config.get("template_id"),
        print_config.get("text_size"),
        paper_size=print_config.get("paper_size"),
    )
    print_items = build_print_items(
        normalize_items(entry_schema.get("blocks")),
        values,
        {},
        record_id=0,
        print_config=print_config,
    )
    apply_print_layout_preference(
        print_items,
        print_layout_preference,
        field_grid_units=int(presentation["field_grid_units"]),
    )
    prepared_by_name = "Sample Medtech"
    document = {
        "record": serialized,
        "clinic": build_print_clinic_profile(clinic_profile, logo_url=clinic_logo_url),
        "print_config": print_config,
        "print_accent_ink": print_accent_ink,
        "print_header_ink": print_header_ink,
        "template": presentation,
        "title": report_title,
        "status": "draft",
        "display_title": compact_text(identity.get("primary_value")) or normalized_form_name,
        "display_subtitle": compact_text(identity.get("secondary_value")),
        "display_subtitle_label": compact_text(identity.get("secondary_label")),
        "summary_items": summary_items,
        "patient_name": compact_text(identity.get("primary_value")),
        "patient_age": "",
        "patient_sex": "",
        "case_number": compact_text(identity.get("secondary_value")),
        "form_name": normalized_form_name,
        "report_title": report_title,
        "form_path_label": normalized_path,
        "form_version_number": "draft",
        "record_key": "PREVIEW-0001",
        "created_at": "",
        "updated_at": "",
        "created_at_label": "Preview sample",
        "updated_at_label": "Preview sample",
        "completed_at_label": "",
        "issued_at_label": "Preview sample",
        "prepared_by_name": prepared_by_name,
        "signatures": build_print_signature_items(
            print_config,
            values,
            prepared_by_name=prepared_by_name,
            signatories=signatory_samples,
        ),
        "items": print_items,
    }
    document["fit_estimate"] = estimate_print_page_fit(document)
    return document


def build_record_print_document(
    record: Record,
    *,
    clinic_profile: dict[str, Any] | None = None,
    clinic_logo_url: str = "",
    template_id: Any = "",
    style: Any = "",
    orientation: Any = "",
    text_size: Any = "",
    paper_size: Any = "",
    print_layout_preference: dict[str, Any] | None = None,
) -> dict[str, Any]:
    serialized = serialize_record(record, include_entry_schema=True)
    entry_schema = serialized.get("entry_schema") or {}
    values = serialized.get("values") or {}
    asset_by_field = serialized.get("asset_by_field_id") or {}
    updated_by = serialized.get("updated_by") or serialized.get("created_by") or {}
    issued_at_label = (
        serialized.get("completed_at_label")
        or serialized.get("updated_at_label")
        or serialized.get("created_at_label")
        or ""
    )
    meta = entry_schema.get("meta") if isinstance(entry_schema.get("meta"), dict) else {}
    print_config = apply_print_presentation(
        normalize_print_config(meta.get("print_config")),
        template_id=template_id,
        style=style,
        orientation=orientation,
        text_size=text_size,
        paper_size=paper_size,
    )
    print_accent_ink = print_accent_text_color(print_config.get("accent_color"))
    print_header_ink = print_header_text_color(print_config)
    report_title = resolve_print_report_title(
        print_config,
        form_name=serialized["form_name"],
        form_path_label=serialized["form_path_label"],
    )
    summary_items = build_print_summary_items(
        print_config,
        serialized,
        values,
        issued_at_label=issued_at_label or "Not set yet",
    )
    prepared_by_name = compact_text(updated_by.get("full_name")) or ""

    presentation = print_presentation_details(
        print_config.get("template_id"),
        print_config.get("text_size"),
        paper_size=print_config.get("paper_size"),
    )
    print_items = build_print_items(
        normalize_items(entry_schema.get("blocks")),
        values,
        asset_by_field,
        record_id=serialized["id"],
        print_config=print_config,
    )
    apply_print_layout_preference(
        print_items,
        print_layout_preference,
        field_grid_units=int(presentation["field_grid_units"]),
    )

    document = {
        "record": serialized,
        "clinic": build_print_clinic_profile(clinic_profile, logo_url=clinic_logo_url),
        "print_config": print_config,
        "print_accent_ink": print_accent_ink,
        "print_header_ink": print_header_ink,
        "template": presentation,
        "title": report_title,
        "status": serialized["status"],
        "display_title": serialized["display_title"],
        "display_subtitle": serialized["display_subtitle"],
        "display_subtitle_label": serialized["display_subtitle_label"],
        "summary_items": summary_items,
        "patient_name": serialized["patient_name"] or "",
        "patient_age": serialized["patient_age"] or "",
        "patient_sex": serialized["patient_sex"] or "",
        "case_number": serialized["case_number"] or "",
        "form_name": serialized["form_name"],
        "report_title": report_title,
        "form_path_label": serialized["form_path_label"],
        "form_version_number": serialized["form_version_number"],
        "record_key": serialized["record_key"],
        "created_at": serialized["created_at"],
        "updated_at": serialized["updated_at"],
        "created_at_label": serialized.get("created_at_label") or "",
        "updated_at_label": serialized.get("updated_at_label") or "",
        "completed_at_label": serialized.get("completed_at_label") or "",
        "issued_at_label": issued_at_label,
        "prepared_by_name": prepared_by_name,
        "signatures": build_print_signature_items(
            print_config,
            values,
            prepared_by_name=prepared_by_name,
            signatories=normalize_items(serialized.get("signatories")),
        ),
        "items": print_items,
    }
    document["fit_estimate"] = estimate_print_page_fit(document)
    return document


def serialize_record(
    record: Record,
    *,
    include_values: bool = True,
    include_entry_schema: bool = False,
) -> dict[str, Any]:
    location = serialize_form_location(record.form)
    indexed_meta = load_json_object(record.indexed_meta_json)
    stored_values = normalize_record_values(load_json_object(record.values_json))
    block_schema_for_signatories, _ = load_block_storage_document(record.form_version)
    block_meta_for_signatories = (
        block_schema_for_signatories.get("meta")
        if isinstance(block_schema_for_signatories.get("meta"), dict)
        else {}
    )
    signatory_slots = normalize_signatory_slots(block_meta_for_signatories.get("signatories"), use_defaults=False)
    signatory_snapshots = normalize_record_signatory_snapshots(
        indexed_meta.get("signatories"),
        signatory_slots,
    )
    lifecycle = record_lifecycle_meta(indexed_meta)
    stored_identity = indexed_meta.get("record_identity") if isinstance(indexed_meta.get("record_identity"), dict) else {}
    if stored_identity:
        identity = resolve_record_identity(
            {"meta": {"record_identity": stored_identity}, "blocks": []},
            stored_values,
            fallback_primary=compact_text(stored_identity.get("primary_value")) or compact_text(record.patient_name),
            fallback_secondary=compact_text(stored_identity.get("secondary_value")) or compact_text(record.case_number),
        )
        identity.update(
            {
                "primary_label": compact_text(stored_identity.get("primary_label")),
                "primary_value": compact_text(stored_identity.get("primary_value")) or compact_text(record.patient_name),
                "secondary_label": compact_text(stored_identity.get("secondary_label")),
                "secondary_value": compact_text(stored_identity.get("secondary_value")) or compact_text(record.case_number),
                "searchable_fields": normalize_items(stored_identity.get("searchable_fields")),
                "search_text": compact_text(stored_identity.get("search_text")),
            }
        )
    else:
        block_schema_for_identity, _ = load_block_storage_document(record.form_version)
        identity = resolve_record_identity(
            block_schema_for_identity,
            stored_values,
            fallback_primary=compact_text(record.patient_name),
            fallback_secondary=compact_text(record.case_number),
        )

    display_title = compact_text(identity.get("primary_value")) or compact_text(record.patient_name) or compact_text(record.form.name) or "Untitled record"
    display_subtitle = compact_text(identity.get("secondary_value")) or compact_text(record.case_number) or record.record_key
    display_subtitle_label = compact_text(identity.get("secondary_label")) or ("Record" if display_subtitle == record.record_key else "Secondary")
    asset_by_field_id = {
        compact_text(asset.field_block_id): serialize_record_asset(asset)
        for asset in record.assets
        if compact_text(asset.field_block_id)
    }
    payload = {
        "id": record.id,
        "record_key": record.record_key,
        "status": record.status,
        "status_label": RECORD_STATUS_LABELS.get(record.status, record.status.title()),
        "patient_name": record.patient_name,
        "patient_age": compact_text(indexed_meta.get("patient_age")) or None,
        "patient_sex": compact_text(indexed_meta.get("patient_sex")) or None,
        "case_number": record.case_number,
        "display_title": display_title,
        "display_subtitle": display_subtitle,
        "display_subtitle_label": display_subtitle_label,
        "record_identity": identity,
        "form_slug": record.form.slug,
        "form_name": record.form.name,
        "form_path_label": form_path_label_for_record(record),
        "location_name": location["location_name"],
        "location_path_label": location["location_path_label"],
        "location_node_key": location["location_node_key"],
        "form_version_id": record.form_version_id,
        "form_version_number": record.form_version.version_number,
        "assets": [serialize_record_asset(asset) for asset in record.assets],
        "asset_by_field_id": asset_by_field_id,
        "created_at": record.created_at.astimezone(timezone.utc).isoformat(),
        "updated_at": record.updated_at.astimezone(timezone.utc).isoformat(),
        "completed_at": record.completed_at.astimezone(timezone.utc).isoformat() if record.completed_at else None,
        "created_at_label": format_timestamp_label(record.created_at),
        "updated_at_label": format_timestamp_label(record.updated_at),
        "created_at_compact_label": format_compact_timestamp_label(record.created_at),
        "updated_at_compact_label": format_compact_timestamp_label(record.updated_at),
        "completed_at_label": format_timestamp_label(record.completed_at) if record.completed_at else "",
        "created_by": serialize_record_actor(record.created_by_user),
        "updated_by": serialize_record_actor(record.updated_by_user),
        "indexed_meta": indexed_meta,
        "lifecycle": lifecycle,
        "voided_event": lifecycle.get("voided") if isinstance(lifecycle.get("voided"), dict) else None,
        "deleted_event": lifecycle.get("deleted") if isinstance(lifecycle.get("deleted"), dict) else None,
        "signatories": signatory_snapshots,
    }
    if include_values:
        payload["values"] = stored_values
    if include_entry_schema:
        payload["entry_schema"] = block_schema_for_signatories
    return payload


def get_record_or_none(session: Session, record_id: int) -> Record | None:
    return session.scalar(
        select(Record)
        .where(Record.id == record_id)
        .options(
            selectinload(Record.form).selectinload(FormDefinition.library_node).selectinload(LibraryNode.parent),
            selectinload(Record.form_version),
            selectinload(Record.assets),
            selectinload(Record.created_by_user),
            selectinload(Record.updated_by_user),
        )
    )


def record_query_with_relationships():
    return select(Record).options(
        selectinload(Record.form).selectinload(FormDefinition.library_node).selectinload(LibraryNode.parent),
        selectinload(Record.form_version),
        selectinload(Record.assets),
        selectinload(Record.created_by_user),
        selectinload(Record.updated_by_user),
    )


def apply_record_filters(
    query,
    *,
    status: str | None = None,
    search: str | None = None,
    form_slug: str | None = None,
    date_scope: str | None = None,
):
    normalized_status = compact_text(status)
    if normalized_status:
        query = query.where(Record.status == normalized_status)
    else:
        query = query.where(Record.status.in_(VISIBLE_RECORD_STATUSES))

    normalized_form_slug = compact_text(form_slug)
    if normalized_form_slug:
        query = query.where(Record.form.has(FormDefinition.slug == normalized_form_slug))

    start_at = record_date_scope_start(date_scope)
    if start_at is not None:
        query = query.where(Record.updated_at >= start_at)

    search_text = compact_text(search)
    if search_text:
        search_pattern = f"%{search_text}%"
        query = query.join(FormDefinition, Record.form_id == FormDefinition.id).where(
            or_(
                Record.patient_name.ilike(search_pattern),
                Record.case_number.ilike(search_pattern),
                Record.record_key.ilike(search_pattern),
                Record.indexed_meta_json.ilike(search_pattern),
                Record.values_json.ilike(search_pattern),
                FormDefinition.name.ilike(search_pattern),
            )
        )

    return query


def normalize_record_date_scope(value: Any) -> str:
    scope = compact_text(value).lower()
    return scope if scope in RECORD_DATE_SCOPES else ""


def record_date_scope_start(value: Any, *, now: datetime | None = None) -> datetime | None:
    scope = normalize_record_date_scope(value)
    if not scope:
        return None

    local_now = (now or utc_now()).astimezone()
    start_of_today = datetime.combine(local_now.date(), time.min, tzinfo=local_now.tzinfo)
    if scope == "today":
        return start_of_today.astimezone(timezone.utc)
    if scope == "last_7_days":
        return (start_of_today - timedelta(days=6)).astimezone(timezone.utc)
    return start_of_today.replace(day=1).astimezone(timezone.utc)


def count_records(
    session: Session,
    *,
    status: str | None = None,
    search: str | None = None,
    form_slug: str | None = None,
    date_scope: str | None = None,
) -> int:
    query = select(func.count(Record.id))
    query = apply_record_filters(
        query,
        status=status,
        search=search,
        form_slug=form_slug,
        date_scope=date_scope,
    )
    return int(session.scalar(query) or 0)


def list_records(
    session: Session,
    *,
    status: str | None = None,
    search: str | None = None,
    form_slug: str | None = None,
    date_scope: str | None = None,
    limit: int = 24,
    offset: int = 0,
) -> list[dict[str, Any]]:
    query = record_query_with_relationships()
    query = apply_record_filters(
        query,
        status=status,
        search=search,
        form_slug=form_slug,
        date_scope=date_scope,
    )
    query = query.order_by(Record.updated_at.desc(), Record.id.desc()).offset(max(0, int(offset or 0))).limit(limit)
    records = session.scalars(query).all()
    return [serialize_record(record, include_values=False) for record in records]


def list_completed_record_activity_by_form(
    session: Session,
    *,
    date_scope: str | None = None,
) -> list[dict[str, Any]]:
    """Return every active library form with completed-record totals for the selected History scope."""
    record_conditions = [
        Record.form_id == FormDefinition.id,
        Record.status == "completed",
    ]
    start_at = record_date_scope_start(date_scope)
    if start_at is not None:
        record_conditions.append(Record.updated_at >= start_at)
    query = (
        select(
            FormDefinition.slug,
            FormDefinition.name,
            func.count(Record.id).label("record_count"),
        )
        .select_from(FormDefinition)
        .join(LibraryNode, LibraryNode.form_definition_id == FormDefinition.id)
        .outerjoin(Record, and_(*record_conditions))
        .where(
            LibraryNode.kind == "form",
            LibraryNode.archived.is_(False),
        )
    )
    query = query.group_by(FormDefinition.id, FormDefinition.slug, FormDefinition.name).order_by(
        func.count(Record.id).desc(),
        FormDefinition.name.asc(),
    )
    rows = session.execute(query).all()
    counts = [int(row.record_count or 0) for row in rows]
    maximum = max(counts, default=0)
    return [
        {
            "slug": str(row.slug),
            "name": str(row.name),
            "count": int(row.record_count or 0),
            "percent": round((int(row.record_count or 0) / maximum) * 100) if maximum else 0,
        }
        for row in rows
    ]


def create_record(
    session: Session,
    payload: RecordCreatePayload,
    *,
    actor_user_id: int | None = None,
) -> dict[str, Any]:
    form_slug = compact_text(payload.form_slug)
    if not form_slug:
        raise ValueError("Choose a form before you continue.")

    definition = get_form_or_none(session, form_slug)
    if definition is None:
        raise ValueError("Form not found.")

    version = current_version(definition)
    if version is None:
        raise ValueError("This form has no current version yet.")

    patient_name = compact_text(payload.patient_name)
    patient_age = compact_text(payload.patient_age)
    patient_sex = compact_text(payload.patient_sex)
    case_number = compact_text(payload.case_number)
    normalized_values = normalize_record_values(payload.values)
    indexed_meta, identity = build_record_indexed_meta(
        payload.indexed_meta,
        version,
        normalized_values,
        patient_name=patient_name,
        patient_age=patient_age,
        patient_sex=patient_sex,
        case_number=case_number,
    )

    record = Record(
        record_key=next_record_key(session, definition.slug),
        form_id=definition.id,
        form_version_id=version.id,
        status="draft",
        patient_name=identity["primary_value"] or patient_name or None,
        case_number=identity["secondary_value"] or case_number or None,
        values_json=json.dumps(normalized_values, ensure_ascii=False),
        indexed_meta_json=json.dumps(indexed_meta, ensure_ascii=False),
        created_by_user_id=actor_user_id,
        updated_by_user_id=actor_user_id,
    )
    session.add(record)
    session.commit()
    session.expire_all()

    created = get_record_or_none(session, record.id)
    if created is None:
        raise ValueError("Record could not be loaded.")
    return serialize_record(created, include_entry_schema=True)


def update_record(
    session: Session,
    record_id: int,
    payload: RecordUpdatePayload,
    *,
    preserve_asset_fields: bool = False,
    actor_user_id: int | None = None,
) -> dict[str, Any]:
    record = get_record_or_none(session, record_id)
    if record is None:
        raise KeyError(record_id)
    if record.status not in EDITABLE_RECORD_STATUSES:
        raise ValueError("Only draft records can be edited.")

    existing_meta = load_json_object(record.indexed_meta_json)
    patient_name = compact_text(payload.patient_name) if payload.patient_name is not None else compact_text(record.patient_name)
    patient_age = compact_text(payload.patient_age) if payload.patient_age is not None else compact_text(existing_meta.get("patient_age"))
    patient_sex = compact_text(payload.patient_sex) if payload.patient_sex is not None else compact_text(existing_meta.get("patient_sex"))
    case_number = compact_text(payload.case_number) if payload.case_number is not None else compact_text(record.case_number)
    normalized_values = normalize_record_values(payload.values)
    if preserve_asset_fields:
        normalized_values = preserve_existing_asset_values(current_record_values(record), normalized_values)
    indexed_meta, identity = build_record_indexed_meta(
        {
            **existing_meta,
            **(payload.indexed_meta if isinstance(payload.indexed_meta, dict) else {}),
        },
        record.form_version,
        normalized_values,
        patient_name=patient_name,
        patient_age=patient_age,
        patient_sex=patient_sex,
        case_number=case_number,
    )

    record.patient_name = identity["primary_value"] or patient_name or None
    record.case_number = identity["secondary_value"] or case_number or None
    record.values_json = json.dumps(normalized_values, ensure_ascii=False)
    record.indexed_meta_json = json.dumps(indexed_meta, ensure_ascii=False)
    record.updated_by_user_id = actor_user_id
    session.commit()
    session.expire_all()

    updated = get_record_or_none(session, record_id)
    if updated is None:
        raise KeyError(record_id)
    return serialize_record(updated, include_entry_schema=True)


def complete_record(
    session: Session,
    record_id: int,
    payload: RecordUpdatePayload,
    *,
    preserve_asset_fields: bool = False,
    actor_user_id: int | None = None,
) -> dict[str, Any]:
    record = get_record_or_none(session, record_id)
    if record is None:
        raise KeyError(record_id)
    if record.status != "draft":
        raise ValueError("Only draft records can be completed.")

    existing_meta = load_json_object(record.indexed_meta_json)
    patient_name = compact_text(payload.patient_name) if payload.patient_name is not None else compact_text(record.patient_name)
    patient_age = compact_text(payload.patient_age) if payload.patient_age is not None else compact_text(existing_meta.get("patient_age"))
    patient_sex = compact_text(payload.patient_sex) if payload.patient_sex is not None else compact_text(existing_meta.get("patient_sex"))
    case_number = compact_text(payload.case_number) if payload.case_number is not None else compact_text(record.case_number)
    normalized_values = normalize_record_values(payload.values)
    if preserve_asset_fields:
        normalized_values = preserve_existing_asset_values(current_record_values(record), normalized_values)
    indexed_meta, identity = build_record_indexed_meta(
        {
            **existing_meta,
            **(payload.indexed_meta if isinstance(payload.indexed_meta, dict) else {}),
        },
        record.form_version,
        normalized_values,
        patient_name=patient_name,
        patient_age=patient_age,
        patient_sex=patient_sex,
        case_number=case_number,
    )

    validate_record_completion(
        record,
        values=normalized_values,
        indexed_meta=indexed_meta,
    )

    record.patient_name = identity["primary_value"] or patient_name or None
    record.case_number = identity["secondary_value"] or case_number or None
    record.values_json = json.dumps(normalized_values, ensure_ascii=False)
    record.indexed_meta_json = json.dumps(indexed_meta, ensure_ascii=False)
    record.status = "completed"
    record.completed_at = utc_now()
    record.updated_by_user_id = actor_user_id
    presentation_user = record.created_by_user
    if presentation_user is None and actor_user_id is not None:
        presentation_user = session.get(User, actor_user_id)
    snapshot_completed_record_print_presentation(
        session,
        record,
        user=presentation_user,
    )
    session.commit()
    session.expire_all()

    completed = get_record_or_none(session, record_id)
    if completed is None:
        raise KeyError(record_id)
    return serialize_record(completed, include_entry_schema=True)


def delete_draft_record(
    session: Session,
    record_id: int,
    *,
    actor_user_id: int | None = None,
) -> dict[str, Any]:
    record = get_record_or_none(session, record_id)
    if record is None:
        raise KeyError(record_id)
    if record.status != "draft":
        raise ValueError("Only draft records can be deleted. Completed records should be voided instead.")

    indexed_meta = load_json_object(record.indexed_meta_json)
    lifecycle = record_lifecycle_meta(indexed_meta)
    lifecycle["deleted"] = lifecycle_event_payload(session, actor_user_id=actor_user_id)
    indexed_meta["lifecycle"] = lifecycle

    record.status = "deleted"
    record.indexed_meta_json = json.dumps(indexed_meta, ensure_ascii=False)
    record.updated_by_user_id = actor_user_id
    session.commit()
    session.expire_all()

    deleted = get_record_or_none(session, record_id)
    if deleted is None:
        raise KeyError(record_id)
    return serialize_record(deleted, include_entry_schema=False)


def void_completed_record(
    session: Session,
    record_id: int,
    *,
    reason: str,
    actor_user_id: int | None = None,
) -> dict[str, Any]:
    record = get_record_or_none(session, record_id)
    if record is None:
        raise KeyError(record_id)
    if record.status != "completed":
        raise ValueError("Only completed records can be voided.")

    reason_text = compact_text(reason)
    if not reason_text:
        raise ValueError("Add a short reason before voiding this record.")

    indexed_meta = load_json_object(record.indexed_meta_json)
    lifecycle = record_lifecycle_meta(indexed_meta)
    lifecycle["voided"] = lifecycle_event_payload(session, actor_user_id=actor_user_id, reason=reason_text)
    indexed_meta["lifecycle"] = lifecycle

    record.status = "voided"
    record.indexed_meta_json = json.dumps(indexed_meta, ensure_ascii=False)
    record.updated_by_user_id = actor_user_id
    session.commit()
    session.expire_all()

    voided = get_record_or_none(session, record_id)
    if voided is None:
        raise KeyError(record_id)
    return serialize_record(voided, include_entry_schema=True)


def store_record_image_asset(
    session: Session,
    *,
    record_id: int,
    field_block_id: str,
    original_filename: str,
    content_type: str | None,
    file_bytes: bytes,
) -> dict[str, Any]:
    record = get_record_or_none(session, record_id)
    if record is None:
        raise KeyError(record_id)
    if record.status not in EDITABLE_RECORD_STATUSES:
        raise ValueError("Only draft records can be edited.")

    field_block = resolve_record_image_field(record, field_block_id)
    mime_type = compact_text(content_type)
    extension = ALLOWED_IMAGE_CONTENT_TYPES.get(mime_type)
    if extension is None:
        raise ValueError("Only JPG, PNG, and WebP images are allowed.")
    if not file_bytes:
        raise ValueError("Choose an image before uploading.")
    if len(file_bytes) > MAX_RECORD_IMAGE_BYTES:
        raise ValueError("Image must be 10 MB or smaller.")

    props = field_block.get("props") if isinstance(field_block.get("props"), dict) else {}
    field_key = compact_text(props.get("key")) or None
    safe_field = slugify(field_key or field_block_id)
    destination_dir = RECORD_UPLOADS_DIR / record.record_key / safe_field
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination_path = destination_dir / f"{uuid4().hex}{extension}"
    destination_path.write_bytes(file_bytes)

    current_values = current_record_values(record)
    existing_ref = current_values.get(field_block_id)
    if isinstance(existing_ref, dict) and existing_ref.get("asset_id"):
        existing_asset = session.scalar(
            select(RecordAsset).where(
                RecordAsset.id == int(existing_ref["asset_id"]),
                RecordAsset.record_id == record.id,
            )
        )
        if existing_asset is not None:
            remove_record_asset(session, existing_asset)

    asset = RecordAsset(
        record_id=record.id,
        field_block_id=compact_text(field_block_id),
        field_key=field_key,
        kind="image",
        storage_path=str(destination_path),
        original_filename=compact_text(original_filename) or destination_path.name,
        mime_type=mime_type or None,
        size_bytes=len(file_bytes),
        image_width=None,
        image_height=None,
    )
    session.add(asset)
    session.flush()

    current_values[compact_text(field_block_id)] = {
        "asset_id": asset.id,
        "kind": "image",
    }
    record.values_json = json.dumps(current_values, ensure_ascii=False)
    session.commit()
    session.expire_all()

    updated = get_record_or_none(session, record_id)
    if updated is None:
        raise KeyError(record_id)
    return serialize_record(updated, include_entry_schema=True)


def delete_record_asset(session: Session, record_id: int, asset_id: int) -> dict[str, Any]:
    record = get_record_or_none(session, record_id)
    if record is None:
        raise KeyError(record_id)
    if record.status not in EDITABLE_RECORD_STATUSES:
        raise ValueError("Only draft records can be edited.")

    asset = session.scalar(
        select(RecordAsset).where(
            RecordAsset.id == asset_id,
            RecordAsset.record_id == record.id,
        )
    )
    if asset is None:
        raise KeyError(asset_id)

    current_values = current_record_values(record)
    field_id = compact_text(asset.field_block_id)
    current_ref = current_values.get(field_id)
    if isinstance(current_ref, dict) and current_ref.get("asset_id") == asset.id:
        current_values.pop(field_id, None)
        record.values_json = json.dumps(current_values, ensure_ascii=False)

    remove_record_asset(session, asset)
    session.commit()
    session.expire_all()

    updated = get_record_or_none(session, record_id)
    if updated is None:
        raise KeyError(record_id)
    return serialize_record(updated, include_entry_schema=True)


def serialize_form_location(definition: FormDefinition) -> dict[str, Any]:
    form_node = definition.library_node
    parent_node = form_node.parent if form_node is not None else None

    if parent_node is None:
        return {
            "location_name": "Top level",
            "location_path_label": "Top level",
            "location_node_key": None,
            "location_kind": "top_level",
        }

    path: list[str] = []
    cursor = parent_node
    while cursor is not None:
        path.append(compact_text(cursor.name) or "Untitled Folder")
        cursor = cursor.parent
    path.reverse()

    location_name = path[-1] if path else compact_text(parent_node.name) or "Untitled Folder"
    location_path_label = " / ".join(path) if path else location_name
    return {
        "location_name": location_name,
        "location_path_label": location_path_label,
        "location_node_key": compact_text(parent_node.node_key) or None,
        "location_kind": "folder",
    }


def serialize_form(definition: FormDefinition) -> dict[str, Any]:
    version = current_version(definition)
    if version is None:
        raise ValueError(f"Form '{definition.slug}' has no versions.")

    block_schema, _ = load_block_storage_document(version)

    location = serialize_form_location(definition)
    return {
        "slug": definition.slug,
        "name": definition.name,
        "location_name": location["location_name"],
        "location_path_label": location["location_path_label"],
        "location_node_key": location["location_node_key"],
        "location_kind": location["location_kind"],
        "library_parent_node_key": definition.library_parent_node_key,
        "current_version_number": version.version_number,
        "summary": version.summary,
        "updated_at": definition.updated_at.astimezone(timezone.utc).isoformat(),
        "block_schema": block_schema,
    }


def get_form_or_none(session: Session, slug: str) -> FormDefinition | None:
    return session.scalar(
        select(FormDefinition)
        .where(FormDefinition.slug == slug)
        .options(
            selectinload(FormDefinition.versions),
            selectinload(FormDefinition.library_node).selectinload(LibraryNode.parent),
        )
    )


def list_container_choices(session: Session) -> list[dict[str, Any]]:
    tree = list_library_tree(session)
    choices: list[dict[str, Any]] = []

    def walk(nodes: list[dict[str, Any]], path: list[str]) -> None:
        for node in nodes:
            if compact_text(node.get("kind")) != "container" or node.get("archived"):
                continue
            current_path = [*path, compact_text(node.get("name")) or "Untitled Folder"]
            children = node.get("children", [])
            next_form_order = max((int(child.get("order") or 0) for child in children), default=0) + 1
            choices.append(
                {
                    "node_key": compact_text(node.get("id")),
                    "name": compact_text(node.get("name")) or "Untitled Folder",
                    "folder_path_label": " / ".join(current_path),
                    "depth": len(path),
                    "order": int(node.get("order") or 999),
                    "next_form_order": next_form_order,
                }
            )
            walk(children, current_path)

    walk(tree, [])
    return choices


def list_form_choices(session: Session) -> list[dict[str, Any]]:
    tree = list_library_tree(session)
    choices: list[dict[str, Any]] = []

    def walk(nodes: list[dict[str, Any]], path: list[str]) -> None:
        for node in nodes:
            if node.get("archived"):
                continue
            kind = compact_text(node.get("kind"))
            if kind == "container":
                current_path = [*path, compact_text(node.get("name")) or "Untitled Folder"]
                walk(node.get("children", []), current_path)
                continue
            if kind != "form":
                continue
            form = node.get("form") or {}
            form_name = compact_text(form.get("name")) or compact_text(node.get("name")) or "Untitled Form"
            current_path = [*path, form_name]
            choices.append(
                {
                    "slug": compact_text(form.get("slug")),
                    "name": form_name,
                    "location_name": path[-1] if path else "Top level",
                    "location_path_label": " / ".join(path) or "Top level",
                    "form_path_label": " / ".join(current_path),
                    "depth": len(path),
                    "order": int(node.get("order") or 1),
                    "current_version_number": int(form.get("current_version_number") or 1),
                }
            )

    walk(tree, [])
    return choices


def next_available_container_node_key(session: Session, preferred: str) -> str:
    base = f"container:{slugify(preferred or 'folder')}"
    key = base
    suffix = 2
    while session.scalar(select(LibraryNode.id).where(LibraryNode.node_key == key)) is not None:
        key = f"{base}_{suffix}"
        suffix += 1
    return key


def ensure_container_node(
    session: Session,
    name: str,
    parent_node_key: str | None = None,
) -> LibraryNode:
    container_name = compact_text(name) or "Untitled Folder"
    parent_key = compact_text(parent_node_key)
    parent_id: int | None = None

    if parent_key:
        parent = session.scalar(select(LibraryNode).where(LibraryNode.node_key == parent_key))
        if parent is not None and parent.kind == "container":
            parent_id = parent.id
            if parent.archived:
                parent.archived = False

    query = select(LibraryNode).where(
        LibraryNode.kind == "container",
        LibraryNode.name == container_name,
    )
    if parent_id is None:
        query = query.where(LibraryNode.parent_id.is_(None))
    else:
        query = query.where(LibraryNode.parent_id == parent_id)

    existing = session.scalar(query.order_by(LibraryNode.id))
    if existing is not None:
        if existing.archived:
            existing.archived = False
        return existing

    sibling_query = select(LibraryNode).where(LibraryNode.parent_id == parent_id) if parent_id is not None else select(LibraryNode).where(LibraryNode.parent_id.is_(None))
    next_order = max((node.node_order for node in session.scalars(sibling_query).all()), default=0) + 1
    container = LibraryNode(
        node_key=next_available_container_node_key(session, container_name),
        kind="container",
        name=container_name,
        parent_id=parent_id,
        node_order=next_order,
        archived=False,
    )
    session.add(container)
    session.flush()
    return container


def create_container(
    session: Session,
    name: str,
    parent_node_key: str | None = None,
) -> LibraryNode:
    container_name = compact_text(name)
    if not container_name:
        raise ValueError("Name the folder before you continue.")

    parent_key = compact_text(parent_node_key)
    parent_id: int | None = None
    if parent_key:
        parent = session.scalar(select(LibraryNode).where(LibraryNode.node_key == parent_key))
        if parent is None or parent.kind != "container":
            raise ValueError("Parent folder not found.")
        parent_id = parent.id

    existing_query = select(LibraryNode).where(
        LibraryNode.kind == "container",
        LibraryNode.name == container_name,
    )
    if parent_id is None:
        existing_query = existing_query.where(LibraryNode.parent_id.is_(None))
    else:
        existing_query = existing_query.where(LibraryNode.parent_id == parent_id)

    existing = session.scalar(existing_query.limit(1))
    if existing is not None:
        raise ValueError("A folder with this name already exists here.")

    container = ensure_container_node(session, container_name, parent_key or None)
    session.commit()
    return container


def get_container_or_none(session: Session, node_key: str) -> LibraryNode | None:
    key = compact_text(node_key)
    if not key:
        return None
    node = session.scalar(select(LibraryNode).where(LibraryNode.node_key == key))
    if node is None or node.kind != "container":
        return None
    return node


def next_node_order(session: Session, parent_id: int | None, *, exclude_node_id: int | None = None) -> int:
    query = (
        select(LibraryNode).where(LibraryNode.parent_id == parent_id)
        if parent_id is not None
        else select(LibraryNode).where(LibraryNode.parent_id.is_(None))
    )
    siblings = session.scalars(query).all()
    return max(
        (
            node.node_order
            for node in siblings
            if exclude_node_id is None or node.id != exclude_node_id
        ),
        default=0,
    ) + 1


def resolve_target_container(session: Session, parent_node_key: str | None) -> LibraryNode | None:
    target_key = compact_text(parent_node_key)
    if not target_key:
        return None
    target = get_container_or_none(session, target_key)
    if target is None:
        raise ValueError("Folder not found.")
    if target.archived:
        target.archived = False
    return target


def upsert_form_node_location(
    session: Session,
    definition: FormDefinition,
    *,
    parent_node_key: str | None,
    node_order: int | None = None,
) -> LibraryNode:
    target_parent = resolve_target_container(session, parent_node_key)
    target_parent_id = target_parent.id if target_parent is not None else None
    desired_order = int(node_order or 1)
    node_key = form_node_key(definition.slug)

    form_node = definition.library_node or session.scalar(
        select(LibraryNode).where(LibraryNode.form_definition_id == definition.id)
    )
    if form_node is None:
        form_node = session.scalar(select(LibraryNode).where(LibraryNode.node_key == node_key))

    if form_node is None:
        form_node = LibraryNode(
            node_key=node_key,
            kind="form",
            name=definition.name,
            parent_id=target_parent_id,
            node_order=desired_order,
            archived=False,
            form_definition_id=definition.id,
        )
        session.add(form_node)
        session.flush()
    else:
        form_node.kind = "form"
        form_node.name = definition.name
        form_node.parent_id = target_parent_id
        form_node.node_order = desired_order
        form_node.archived = False
        form_node.form_definition_id = definition.id

    definition.library_parent_node_key = target_parent.node_key if target_parent is not None else None
    return form_node


def create_form_definition_record(
    *,
    slug: str,
    name: str,
    parent_node_key: str | None = None,
) -> FormDefinition:
    return FormDefinition(
        slug=slug,
        name=name,
        library_parent_node_key=parent_node_key,
    )


def sync_definition_parent_node_key(
    session: Session,
    definition: FormDefinition,
    *,
    form_node: LibraryNode | None = None,
) -> bool:
    node = form_node or definition.library_node or session.scalar(
        select(LibraryNode).where(LibraryNode.form_definition_id == definition.id)
    )
    if node is None:
        return False

    parent_container = None
    if node.parent_id is not None:
        parent_container = session.scalar(select(LibraryNode).where(LibraryNode.id == node.parent_id))

    derived_parent_key = parent_container.node_key if parent_container is not None and parent_container.kind == "container" else None
    changed = False
    if compact_text(definition.library_parent_node_key) != compact_text(derived_parent_key):
        definition.library_parent_node_key = derived_parent_key
        changed = True
    return changed


def definition_schema_order_hint(definition: FormDefinition) -> int:
    version = current_version(definition)
    if version is not None:
        schema, _ = load_block_storage_document(version)
        meta = schema.get("meta") if isinstance(schema.get("meta"), dict) else {}
        return int(meta.get("form_order") or 1)
    return 1


def container_is_inside(session: Session, candidate: LibraryNode | None, ancestor_id: int) -> bool:
    current = candidate
    while current is not None:
        if current.id == ancestor_id:
            return True
        if current.parent_id is None:
            return False
        current = session.scalar(select(LibraryNode).where(LibraryNode.id == current.parent_id))
    return False


def descendant_container_keys(session: Session, node_key: str) -> set[str]:
    container = get_container_or_none(session, node_key)
    if container is None:
        return set()

    nodes = session.scalars(
        select(LibraryNode).where(LibraryNode.kind == "container")
    ).all()
    children_by_parent: dict[int | None, list[LibraryNode]] = {}
    for node in nodes:
        children_by_parent.setdefault(node.parent_id, []).append(node)

    descendants: set[str] = set()

    def walk(parent_id: int) -> None:
        for child in children_by_parent.get(parent_id, []):
            descendants.add(child.node_key)
            walk(child.id)

    walk(container.id)
    return descendants


def list_move_target_choices(
    session: Session,
    *,
    exclude_node_key: str | None = None,
) -> list[dict[str, Any]]:
    excluded = {compact_text(exclude_node_key)} if compact_text(exclude_node_key) else set()
    if exclude_node_key:
        excluded.update(descendant_container_keys(session, exclude_node_key))
    return [
        option
        for option in list_container_choices(session)
        if option["node_key"] not in excluded
    ]


def move_container(
    session: Session,
    node_key: str,
    parent_node_key: str | None,
) -> LibraryNode:
    ensure_library_tree(session)
    container = get_container_or_none(session, node_key)
    if container is None:
        raise ValueError("Folder not found.")

    target_parent = resolve_target_container(session, parent_node_key)
    target_parent_id = target_parent.id if target_parent is not None else None

    if target_parent is not None:
        if target_parent.id == container.id:
            raise ValueError("A folder cannot be moved inside itself.")
        if container_is_inside(session, target_parent, container.id):
            raise ValueError("A folder cannot be moved inside one of its own child folders.")

    duplicate_query = select(LibraryNode).where(
        LibraryNode.kind == "container",
        LibraryNode.name == container.name,
        LibraryNode.id != container.id,
    )
    if target_parent_id is None:
        duplicate_query = duplicate_query.where(LibraryNode.parent_id.is_(None))
    else:
        duplicate_query = duplicate_query.where(LibraryNode.parent_id == target_parent_id)

    duplicate = session.scalar(duplicate_query.limit(1))
    if duplicate is not None:
        raise ValueError("A folder with this name already exists there.")

    if container.parent_id != target_parent_id:
        container.parent_id = target_parent_id
        container.node_order = next_node_order(session, target_parent_id, exclude_node_id=container.id)

    if container.archived:
        container.archived = False

    session.commit()
    ensure_library_tree(session)
    session.expire_all()
    moved = get_container_or_none(session, node_key)
    if moved is None:
        raise ValueError("Folder not found.")
    return moved


def move_form(
    session: Session,
    slug: str,
    parent_node_key: str | None,
) -> FormDefinition:
    ensure_library_tree(session)
    definition = session.scalar(
        select(FormDefinition)
        .where(FormDefinition.slug == slug)
        .options(selectinload(FormDefinition.versions), selectinload(FormDefinition.library_node))
    )
    if definition is None:
        raise ValueError("Form not found.")

    target_parent = resolve_target_container(session, parent_node_key)
    target_parent_id = target_parent.id if target_parent is not None else None
    form_node = definition.library_node or session.scalar(
        select(LibraryNode).where(LibraryNode.form_definition_id == definition.id)
    )
    if form_node is None:
        raise ValueError("Form node not found.")

    desired_order = (
        int(form_node.node_order or 1)
        if form_node.parent_id == target_parent_id
        else next_node_order(session, target_parent_id, exclude_node_id=form_node.id)
    )
    upsert_form_node_location(
        session,
        definition,
        parent_node_key=target_parent.node_key if target_parent is not None else None,
        node_order=desired_order,
    )
    sync_definition_parent_node_key(session, definition, form_node=form_node)

    session.commit()
    ensure_library_tree(session)
    session.expire_all()
    moved = get_form_or_none(session, slug)
    if moved is None:
        raise ValueError("Form not found.")
    return moved


def rename_container(
    session: Session,
    node_key: str,
    name: str,
) -> LibraryNode:
    container = get_container_or_none(session, node_key)
    if container is None:
        raise ValueError("Folder not found.")

    container_name = compact_text(name)
    if not container_name:
        raise ValueError("Name the folder before you continue.")

    existing_query = select(LibraryNode).where(
        LibraryNode.kind == "container",
        LibraryNode.name == container_name,
        LibraryNode.id != container.id,
    )
    if container.parent_id is None:
        existing_query = existing_query.where(LibraryNode.parent_id.is_(None))
    else:
        existing_query = existing_query.where(LibraryNode.parent_id == container.parent_id)

    existing = session.scalar(existing_query.limit(1))
    if existing is not None:
        raise ValueError("A folder with this name already exists here.")

    container.name = container_name
    if container.archived:
        container.archived = False
    session.commit()
    return container


def delete_container(session: Session, node_key: str) -> None:
    container = get_container_or_none(session, node_key)
    if container is None:
        raise ValueError("Folder not found.")

    child_node = session.scalar(select(LibraryNode.id).where(LibraryNode.parent_id == container.id).limit(1))
    if child_node is not None:
        raise ValueError("This folder is not empty yet. Move or remove the items inside it first.")

    session.delete(container)
    session.commit()


def normalize_location_name_input(value: str | None) -> str:
    normalized = compact_text(value)
    return "Top level" if normalized == "Unassigned" else normalized


def resolve_form_location_metadata(
    session: Session,
    *,
    form_name: str,
    location_name: str,
    library_parent_node_key: str | None,
    library_new_container_name: str | None,
    existing_definition: FormDefinition | None = None,
) -> dict[str, Any]:
    resolved_parent_key = compact_text(library_parent_node_key) or None
    pending_container_name = compact_text(library_new_container_name) or None
    explicit_location_name = normalize_location_name_input(location_name)

    if pending_container_name:
        if resolved_parent_key:
            resolved_parent_key = resolve_target_container(session, resolved_parent_key).node_key
        resolved_parent_key = ensure_container_node(session, pending_container_name, resolved_parent_key).node_key
    elif (
        not resolved_parent_key
        and explicit_location_name
        and explicit_location_name != "Top level"
    ):
        raise ValueError("Select an existing folder from the library.")

    target_parent = resolve_target_container(session, resolved_parent_key)
    existing_node = existing_definition.library_node if existing_definition is not None else None

    if target_parent is not None:
        if existing_node is not None and existing_node.parent_id == target_parent.id:
            resolved_form_order = int(existing_node.node_order or 1)
        else:
            resolved_form_order = next_node_order(
                session,
                target_parent.id,
                exclude_node_id=existing_node.id if existing_node is not None else None,
            )

        return {
            "resolved_parent_key": target_parent.node_key,
            "resolved_form_order": resolved_form_order,
        }

    if existing_node is not None and existing_node.parent_id is None:
        resolved_form_order = int(existing_node.node_order or 1)
    else:
        resolved_form_order = next_node_order(
            session,
            None,
            exclude_node_id=existing_node.id if existing_node is not None else None,
        )

    return {
        "resolved_parent_key": None,
        "resolved_form_order": resolved_form_order,
    }


def container_node_key(name: str) -> str:
    return f"container:{slugify(name or 'unassigned')}"


def form_node_key(slug: str) -> str:
    return f"form:{slug}"


def ensure_library_tree(session: Session) -> None:
    Base.metadata.create_all(bind=engine)
    definitions = session.scalars(
        select(FormDefinition)
        .options(selectinload(FormDefinition.versions), selectinload(FormDefinition.library_node))
        .order_by(FormDefinition.name, FormDefinition.id)
    ).all()

    nodes = session.scalars(select(LibraryNode)).all()
    nodes_by_key = {node.node_key: node for node in nodes}
    changed = False

    for definition in definitions:
        node_key = form_node_key(definition.slug)
        form_node = nodes_by_key.get(node_key)
        fallback_form_order = definition_schema_order_hint(definition)
        parent_id = None
        parent_node_key: str | None = None
        explicit_parent_key = compact_text(definition.library_parent_node_key)
        desired_form_order = (
            int(form_node.node_order or fallback_form_order)
            if form_node is not None
            else int(fallback_form_order)
        )

        if explicit_parent_key:
            explicit_parent = nodes_by_key.get(explicit_parent_key)
            if explicit_parent is not None and explicit_parent.kind == "container":
                if explicit_parent.archived:
                    explicit_parent.archived = False
                    changed = True
                parent_id = explicit_parent.id
                parent_node_key = explicit_parent.node_key
        elif form_node is not None:
            parent_id = form_node.parent_id
            if form_node.parent_id is not None:
                parent = session.scalar(select(LibraryNode).where(LibraryNode.id == form_node.parent_id))
                if parent is not None and parent.kind == "container":
                    parent_node_key = parent.node_key

        if form_node is None:
            form_node = upsert_form_node_location(
                session,
                definition,
                parent_node_key=parent_node_key,
                node_order=desired_form_order,
            )
            nodes_by_key[node_key] = form_node
            changed = True
        else:
            original_state = (
                form_node.kind,
                form_node.name,
                form_node.parent_id,
                int(form_node.node_order or 1),
                bool(form_node.archived),
                form_node.form_definition_id,
            )
            upsert_form_node_location(
                session,
                definition,
                parent_node_key=parent_node_key,
                node_order=desired_form_order,
            )
            current_state = (
                form_node.kind,
                form_node.name,
                form_node.parent_id,
                int(form_node.node_order or 1),
                bool(form_node.archived),
                form_node.form_definition_id,
            )
            if current_state != original_state:
                changed = True

        if sync_definition_parent_node_key(session, definition, form_node=form_node):
            changed = True

    if changed:
        session.commit()


def list_library_tree(session: Session) -> list[dict[str, Any]]:
    ensure_library_tree(session)
    nodes = session.scalars(
        select(LibraryNode)
        .options(selectinload(LibraryNode.form_definition).selectinload(FormDefinition.versions))
        .order_by(LibraryNode.parent_id, LibraryNode.node_order, LibraryNode.name)
    ).all()

    children_by_parent: dict[int | None, list[LibraryNode]] = {}
    for node in nodes:
        children_by_parent.setdefault(node.parent_id, []).append(node)

    def serialize_node(node: LibraryNode) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": node.node_key,
            "kind": node.kind,
            "name": node.name,
            "order": node.node_order,
            "archived": node.archived,
            "children": [serialize_node(child) for child in children_by_parent.get(node.id, [])],
        }
        if node.kind == "form" and node.form_definition is not None:
            version = current_version(node.form_definition)
            payload["form"] = {
                "slug": node.form_definition.slug,
                "name": node.form_definition.name,
                "current_version_number": version.version_number if version else 0,
            }
        return payload

    return [serialize_node(node) for node in children_by_parent.get(None, [])]


def next_available_slug(session: Session, preferred: str) -> str:
    base = slugify(preferred)
    slug = base
    suffix = 2
    while session.scalar(select(FormDefinition.id).where(FormDefinition.slug == slug)) is not None:
        slug = f"{base}_{suffix}"
        suffix += 1
    return slug


def ensure_reference_seed(session: Session) -> None:
    existing = session.scalar(select(FormDefinition.id).limit(1))
    if existing is not None:
        return

    reference = load_reference_schema()
    try:
        for group in reference.get("groups", []):
            group_name = compact_text(group.get("name"))
            group_kind = compact_text(group.get("kind")) or "category"
            group_order = int(group.get("order") or 999)
            parent_container: LibraryNode | None = None
            parent_node_key: str | None = None

            if group_kind != "standalone_form":
                parent_container = ensure_container_node(session, group_name)
                if parent_container.node_order != group_order:
                    parent_container.node_order = group_order
                parent_node_key = parent_container.node_key

            for form in group.get("forms", []):
                slug = compact_text(form.get("key")) or slugify(form.get("name"))
                name = compact_text(form.get("name")) or "Untitled Form"
                form_order = int(form.get("order") or 1)
                legacy_storage_schema = build_legacy_storage_payload(
                    form,
                    slug=slug,
                    name=name,
                    form_order=form_order,
                )
                block_storage_schema = build_block_storage_document_from_legacy_storage(
                    legacy_storage_schema,
                )

                definition = create_form_definition_record(
                    slug=slug,
                    name=name,
                    parent_node_key=parent_node_key,
                )
                session.add(definition)
                session.flush()
                upsert_form_node_location(
                    session,
                    definition,
                    parent_node_key=parent_node_key,
                    node_order=form_order,
                )
                sync_definition_parent_node_key(session, definition)

                version = build_form_version_record(
                    form_id=definition.id,
                    version_number=1,
                    summary="Seeded from current reference schema.",
                    block_storage_schema=block_storage_schema,
                    source="seed",
                    is_current=True,
                )
                session.add(version)

        session.commit()
        ensure_library_tree(session)
    except IntegrityError:
        session.rollback()
        if session.scalar(select(FormDefinition.id).limit(1)) is None:
            raise


def ensure_default_patient_info_fields(session: Session) -> int:
    definitions = session.scalars(
        select(FormDefinition)
        .options(
            selectinload(FormDefinition.versions),
            selectinload(FormDefinition.library_node),
        )
    ).all()
    migrated_count = 0
    reference_slugs = reference_form_slugs()

    for definition in definitions:
        version = current_version(definition)
        if version is None:
            continue

        block_schema, _ = load_block_storage_document(version)
        patient_info_changed = ensure_default_patient_info_block_schema(block_schema)
        examination_changed = ensure_reference_examination_in_patient_info(
            block_schema,
            reference_slugs,
        )
        if not patient_info_changed and not examination_changed:
            continue

        meta = block_schema.get("meta") if isinstance(block_schema.get("meta"), dict) else {}
        form_order = int(
            meta.get("form_order")
            or (definition.library_node.node_order if definition.library_node is not None else 1)
            or 1
        )
        stored_block_schema = build_block_storage_payload(
            block_schema,
            slug=definition.slug,
            name=definition.name,
            form_order=form_order,
        )

        for existing_version in definition.versions:
            existing_version.is_current = False

        next_version = max((existing_version.version_number for existing_version in definition.versions), default=0) + 1
        session.add(
            build_form_version_record(
                form_id=definition.id,
                version_number=next_version,
                summary="Applied default patient information layout.",
                block_storage_schema=stored_block_schema,
                source="system",
                is_current=True,
            )
        )
        definition.updated_at = utc_now()
        migrated_count += 1

    if migrated_count:
        session.commit()
    return migrated_count


def ensure_blood_gas_analysis_defaults(session: Session) -> int:
    definition = session.scalar(
        select(FormDefinition)
        .where(FormDefinition.slug == BLOOD_GAS_ANALYSIS_FORM_KEY)
        .options(
            selectinload(FormDefinition.versions),
            selectinload(FormDefinition.library_node),
        )
    )
    if definition is None:
        return 0

    version = current_version(definition)
    if version is None:
        return 0

    block_schema, _ = load_block_storage_document(version)
    if not ensure_default_blood_gas_analysis_layout(block_schema):
        return 0

    meta = block_schema.get("meta") if isinstance(block_schema.get("meta"), dict) else {}
    form_order = int(
        meta.get("form_order")
        or (definition.library_node.node_order if definition.library_node is not None else 1)
        or 1
    )
    stored_block_schema = build_block_storage_payload(
        block_schema,
        slug=definition.slug,
        name=definition.name,
        form_order=form_order,
    )
    for existing_version in definition.versions:
        existing_version.is_current = False

    next_version = max((existing_version.version_number for existing_version in definition.versions), default=0) + 1
    session.add(
        build_form_version_record(
            form_id=definition.id,
            version_number=next_version,
            summary="Applied approved Blood Gas Analysis defaults.",
            block_storage_schema=stored_block_schema,
            source="system",
            is_current=True,
        )
    )
    definition.updated_at = utc_now()
    session.commit()
    return 1


def ensure_hematology_defaults(session: Session) -> int:
    definition = session.scalar(
        select(FormDefinition)
        .where(FormDefinition.slug == HEMATOLOGY_FORM_KEY)
        .options(
            selectinload(FormDefinition.versions),
            selectinload(FormDefinition.library_node),
        )
    )
    if definition is None:
        return 0

    version = current_version(definition)
    if version is None:
        return 0

    block_schema, _ = load_block_storage_document(version)
    if not ensure_default_hematology_layout(block_schema):
        return 0

    meta = block_schema.get("meta") if isinstance(block_schema.get("meta"), dict) else {}
    form_order = int(
        meta.get("form_order")
        or (definition.library_node.node_order if definition.library_node is not None else 1)
        or 1
    )
    stored_block_schema = build_block_storage_payload(
        block_schema,
        slug=definition.slug,
        name=definition.name,
        form_order=form_order,
    )
    for existing_version in definition.versions:
        existing_version.is_current = False

    next_version = max((existing_version.version_number for existing_version in definition.versions), default=0) + 1
    session.add(
        build_form_version_record(
            form_id=definition.id,
            version_number=next_version,
            summary="Applied approved Hematology defaults.",
            block_storage_schema=stored_block_schema,
            source="system",
            is_current=True,
        )
    )
    definition.updated_at = utc_now()
    session.commit()
    return 1


def apply_default_form_version(
    session: Session,
    definition: FormDefinition,
    block_schema: dict[str, Any],
    *,
    summary: str,
) -> int:
    meta = block_schema.get("meta") if isinstance(block_schema.get("meta"), dict) else {}
    form_order = int(
        meta.get("form_order")
        or (definition.library_node.node_order if definition.library_node is not None else 1)
        or 1
    )
    stored_block_schema = build_block_storage_payload(
        block_schema,
        slug=definition.slug,
        name=definition.name,
        form_order=form_order,
    )
    for existing_version in definition.versions:
        existing_version.is_current = False

    next_version = max((existing_version.version_number for existing_version in definition.versions), default=0) + 1
    session.add(
        build_form_version_record(
            form_id=definition.id,
            version_number=next_version,
            summary=summary,
            block_storage_schema=stored_block_schema,
            source="system",
            is_current=True,
        )
    )
    definition.updated_at = utc_now()
    session.commit()
    return 1


def ensure_hba1c_defaults(session: Session) -> int:
    definition = session.scalar(
        select(FormDefinition)
        .where(FormDefinition.slug == HBA1C_FORM_KEY)
        .options(
            selectinload(FormDefinition.versions),
            selectinload(FormDefinition.library_node),
        )
    )
    if definition is None:
        return 0

    version = current_version(definition)
    if version is None:
        return 0

    block_schema, _ = load_block_storage_document(version)
    if not ensure_default_hba1c_layout(block_schema):
        return 0
    return apply_default_form_version(
        session,
        definition,
        block_schema,
        summary="Applied approved HBA1C defaults.",
    )


def ensure_pro_time_aptt_defaults(session: Session) -> int:
    definition = session.scalar(
        select(FormDefinition)
        .where(FormDefinition.slug == PRO_TIME_APTT_FORM_KEY)
        .options(
            selectinload(FormDefinition.versions),
            selectinload(FormDefinition.library_node),
        )
    )
    if definition is None:
        return 0

    version = current_version(definition)
    if version is None:
        return 0

    block_schema, _ = load_block_storage_document(version)
    if not ensure_default_pro_time_aptt_layout(block_schema):
        return 0
    return apply_default_form_version(
        session,
        definition,
        block_schema,
        summary="Applied approved Pro-Time, APTT defaults.",
    )


def ensure_qualitative_result_form_defaults(
    session: Session,
    *,
    form_key: str,
    layout: Callable[[dict[str, Any]], bool],
    summary: str,
) -> int:
    definition = session.scalar(
        select(FormDefinition)
        .where(FormDefinition.slug == form_key)
        .options(
            selectinload(FormDefinition.versions),
            selectinload(FormDefinition.library_node),
        )
    )
    if definition is None:
        return 0

    version = current_version(definition)
    if version is None:
        return 0

    block_schema, _ = load_block_storage_document(version)
    if not layout(block_schema):
        return 0
    return apply_default_form_version(
        session,
        definition,
        block_schema,
        summary=summary,
    )


def ensure_blood_bank_defaults(session: Session) -> int:
    return ensure_qualitative_result_form_defaults(
        session,
        form_key=BLOOD_BANK_FORM_KEY,
        layout=ensure_default_blood_bank_layout,
        summary="Applied approved Blood Bank defaults.",
    )


def ensure_hiv_1_and_2_testing_defaults(session: Session) -> int:
    return ensure_qualitative_result_form_defaults(
        session,
        form_key=HIV_1_AND_2_TESTING_FORM_KEY,
        layout=ensure_default_hiv_1_and_2_testing_layout,
        summary="Applied approved HIV 1&2 Testing defaults.",
    )


def ensure_covid_19_antigen_rapid_test_defaults(session: Session) -> int:
    return ensure_qualitative_result_form_defaults(
        session,
        form_key=COVID_19_ANTIGEN_RAPID_TEST_FORM_KEY,
        layout=ensure_default_covid_19_antigen_rapid_test_layout,
        summary="Applied approved COVID 19 Antigen (Rapid Test) defaults.",
    )


def ensure_microbiology_defaults(session: Session) -> int:
    return ensure_qualitative_result_form_defaults(
        session,
        form_key=MICROBIOLOGY_FORM_KEY,
        layout=ensure_default_microbiology_layout,
        summary="Applied approved Microbiology defaults.",
    )


def ensure_blood_chemistry_male_defaults(session: Session) -> int:
    return ensure_qualitative_result_form_defaults(
        session,
        form_key=BLOOD_CHEMISTRY_MALE_FORM_KEY,
        layout=ensure_default_blood_chemistry_male_layout,
        summary="Applied approved Blood Chemistry Male defaults.",
    )


def ensure_blood_chemistry_female_defaults(session: Session) -> int:
    return ensure_qualitative_result_form_defaults(
        session,
        form_key=BLOOD_CHEMISTRY_FEMALE_FORM_KEY,
        layout=ensure_default_blood_chemistry_female_layout,
        summary="Applied approved Blood Chemistry Female defaults.",
    )


def ensure_serology_defaults(session: Session) -> int:
    return ensure_qualitative_result_form_defaults(
        session,
        form_key=SEROLOGY_FORM_KEY,
        layout=ensure_default_serology_layout,
        summary="Applied approved Serology defaults.",
    )


def ensure_fecalysis_defaults(session: Session) -> int:
    return ensure_qualitative_result_form_defaults(
        session,
        form_key=FECALYSIS_FORM_KEY,
        layout=ensure_default_fecalysis_layout,
        summary="Applied approved Fecalysis defaults.",
    )


def ensure_cardiaci_defaults(session: Session) -> int:
    return ensure_qualitative_result_form_defaults(
        session,
        form_key=CARDIACI_FORM_KEY,
        layout=ensure_default_cardiaci_layout,
        summary="Applied approved Cardiaci defaults.",
    )


def ensure_ogtt_defaults(session: Session) -> int:
    return ensure_qualitative_result_form_defaults(
        session,
        form_key=OGTT_FORM_KEY,
        layout=ensure_default_ogtt_layout,
        summary="Applied approved OGTT defaults.",
    )


def ensure_client_signatory_defaults(session: Session) -> int:
    definitions = session.scalars(
        select(FormDefinition)
        .options(
            selectinload(FormDefinition.versions),
            selectinload(FormDefinition.library_node),
        )
    ).all()
    migrated_count = 0

    try:
        for definition in definitions:
            version = current_version(definition)
            if version is None:
                continue

            block_schema, _ = load_block_storage_document(version)
            meta = block_schema.get("meta") if isinstance(block_schema.get("meta"), dict) else {}
            if normalize_boolean_setting(meta.get(CLIENT_SIGNATORY_DEFAULTS_META_KEY), default=False):
                continue

            meta["signatories"] = merge_client_signatory_defaults(meta.get("signatories"))
            meta[CLIENT_SIGNATORY_DEFAULTS_META_KEY] = True
            block_schema["meta"] = meta

            form_order = int(
                meta.get("form_order")
                or (definition.library_node.node_order if definition.library_node is not None else 1)
                or 1
            )
            stored_block_schema = build_block_storage_payload(
                block_schema,
                slug=definition.slug,
                name=definition.name,
                form_order=form_order,
            )

            for existing_version in definition.versions:
                existing_version.is_current = False
            next_version = max(
                (existing_version.version_number for existing_version in definition.versions),
                default=0,
            ) + 1
            session.add(
                build_form_version_record(
                    form_id=definition.id,
                    version_number=next_version,
                    summary="Applied approved client signatory defaults.",
                    block_storage_schema=stored_block_schema,
                    source="system",
                    is_current=True,
                )
            )
            definition.updated_at = utc_now()
            migrated_count += 1

        if migrated_count:
            session.commit()
    except Exception:
        session.rollback()
        raise
    return migrated_count


def ensure_form_version_storage_documents(session: Session) -> None:
    """Upgrade stored versions in place to the canonical container schema."""
    versions = session.scalars(select(FormVersion).options(selectinload(FormVersion.form))).all()
    changed = False

    for version in versions:
        legacy_storage_schema = load_legacy_storage_document(version)
        definition_slug = (
            version.form.slug
            if version.form is not None
            else compact_text(legacy_storage_schema.get("key")) or "compat"
        )
        stable_schema_id = stable_form_schema_id(definition_slug)
        block_schema, block_changed = load_block_storage_document(
            version,
            legacy_storage_schema=legacy_storage_schema,
        )

        meta = block_schema.get("meta") if isinstance(block_schema.get("meta"), dict) else {}
        if "common_field_set_id" in meta:
            meta.pop("common_field_set_id", None)
            block_changed = True
        if compact_text(meta.get("form_id")) != stable_schema_id:
            meta["form_id"] = stable_schema_id
            block_changed = True
        if compact_text(meta.get("legacy_form_id")):
            meta.pop("legacy_form_id", None)
            block_changed = True
        stable_form_key = compact_text(
            version.form.slug if version.form is not None else legacy_storage_schema.get("key")
        )
        if compact_text(meta.get("form_key")) != stable_form_key:
            meta["form_key"] = stable_form_key
            block_changed = True
        if compact_text(meta.get("legacy_form_key")):
            meta.pop("legacy_form_key", None)
            block_changed = True
        stable_form_name = compact_text(
            version.form.name if version.form is not None else legacy_storage_schema.get("name")
        ) or "Untitled Form"
        if compact_text(meta.get("form_name")) != stable_form_name:
            meta["form_name"] = stable_form_name
            block_changed = True
        default_container_id = f"{stable_schema_id}.details"
        for block in normalize_items(block_schema.get("blocks")):
            if not isinstance(block, dict) or compact_text(block.get("kind")) != "container":
                continue
            if compact_text(block.get("id")) != default_container_id:
                continue
            if compact_text(block.get("name")) == "Form Details":
                block["name"] = f"{stable_form_name} Details"
                block_changed = True
        stable_form_order = int(legacy_storage_schema.get("order") or 1)
        if int(meta.get("form_order") or 1) != stable_form_order:
            meta["form_order"] = stable_form_order
            block_changed = True
        if compact_text(meta.get("legacy_order")):
            meta.pop("legacy_order", None)
            block_changed = True

        block_schema["meta"] = meta
        if normalize_active_block_storage_schema(block_schema):
            block_changed = True
        if block_changed:
            version.block_schema_json = json.dumps(block_schema, ensure_ascii=False)
            changed = True

    if changed:
        session.commit()


def create_form(session: Session, payload: FormSavePayload) -> dict[str, Any]:
    raw_block_schema = payload.form_schema if isinstance(payload.form_schema, dict) else {}
    slug = next_available_slug(
        session,
        payload.slug or block_payload_form_key(raw_block_schema) or payload.name or "untitled_form",
    )
    name = compact_text(payload.name) or "Untitled Form"
    location_meta = resolve_form_location_metadata(
        session,
        form_name=name,
        location_name=compact_text(payload.location_name),
        library_parent_node_key=payload.library_parent_node_key,
        library_new_container_name=payload.library_new_container_name,
    )
    stored_block_schema = build_block_storage_payload(
        raw_block_schema,
        slug=slug,
        name=name,
        form_order=location_meta["resolved_form_order"],
    )

    definition = create_form_definition_record(
        slug=slug,
        name=name,
        parent_node_key=location_meta["resolved_parent_key"],
    )
    session.add(definition)
    session.flush()
    upsert_form_node_location(
        session,
        definition,
        parent_node_key=location_meta["resolved_parent_key"],
        node_order=location_meta["resolved_form_order"],
    )
    sync_definition_parent_node_key(session, definition)

    version = build_form_version_record(
        form_id=definition.id,
        version_number=1,
        summary=compact_text(payload.summary) or "Initial builder version.",
        block_storage_schema=stored_block_schema,
        source="builder",
        is_current=True,
    )
    session.add(version)
    session.commit()
    ensure_library_tree(session)
    session.expire_all()
    return serialize_form(get_form_or_none(session, slug))


def update_form(session: Session, slug: str, payload: FormSavePayload) -> dict[str, Any]:
    definition = get_form_or_none(session, slug)
    if definition is None:
        raise KeyError(slug)

    raw_block_schema = payload.form_schema if isinstance(payload.form_schema, dict) else {}
    name = compact_text(payload.name) or definition.name
    location_meta = resolve_form_location_metadata(
        session,
        form_name=name,
        location_name=compact_text(payload.location_name),
        library_parent_node_key=payload.library_parent_node_key,
        library_new_container_name=payload.library_new_container_name,
        existing_definition=definition,
    )
    stored_block_schema = build_block_storage_payload(
        raw_block_schema,
        slug=definition.slug,
        name=name,
        form_order=location_meta["resolved_form_order"],
    )

    next_version = (current_version(definition).version_number if current_version(definition) else 0) + 1
    for version in definition.versions:
        version.is_current = False

    definition.name = name
    upsert_form_node_location(
        session,
        definition,
        parent_node_key=location_meta["resolved_parent_key"],
        node_order=location_meta["resolved_form_order"],
    )
    sync_definition_parent_node_key(session, definition)

    version = build_form_version_record(
        form_id=definition.id,
        version_number=next_version,
        summary=compact_text(payload.summary) or f"Builder update v{next_version}.",
        block_storage_schema=stored_block_schema,
        source="builder",
        is_current=True,
    )
    session.add(version)
    session.commit()
    ensure_library_tree(session)
    session.expire_all()
    return serialize_form(get_form_or_none(session, slug))


def save_form_print_layout_default(
    session: Session,
    slug: str,
    *,
    profile: dict[str, Any],
    layout: Any,
) -> dict[str, Any]:
    definition = get_form_or_none(session, slug)
    if definition is None:
        raise KeyError(slug)

    version = current_version(definition)
    if version is None:
        raise ValueError("The form has no current version.")

    block_schema, _ = load_block_storage_document(version)
    preview_document = build_form_print_preview_document(
        form_name=definition.name,
        form_path_label=serialize_form_location(definition)["location_path_label"],
        block_schema=block_schema,
        template_id=profile["template_id"],
        text_size=profile["text_size"],
        paper_size=profile["paper_size"],
    )
    preference = filter_print_layout_preference_for_items(
        layout,
        preview_document["items"],
        field_grid_units=int(preview_document["template"]["field_grid_units"]),
    )
    defaults = form_version_print_layout_defaults(version)
    profile_key = print_layout_default_profile_key(profile["template_id"], profile["paper_size"])
    if preference["grids"] or preference["containers"] or preference["blocks"]:
        defaults["profiles"][profile_key] = preference
    else:
        defaults["profiles"].pop(profile_key, None)

    meta = block_schema.get("meta") if isinstance(block_schema.get("meta"), dict) else {}
    if defaults["profiles"]:
        meta["print_layout_defaults"] = defaults
    else:
        meta.pop("print_layout_defaults", None)
    block_schema["meta"] = meta

    serialized = serialize_form(definition)
    return update_form(
        session,
        slug,
        FormSavePayload(
            name=definition.name,
            location_name=serialized["location_name"],
            library_parent_node_key=definition.library_parent_node_key,
            summary=(
                f"Updated default print layout for "
                f"{profile['template_id']} / {profile['paper_size']}."
            ),
            form_schema=block_schema,
        ),
    )


def clear_form_print_layout_default(
    session: Session,
    slug: str,
    *,
    profile: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    definition = get_form_or_none(session, slug)
    if definition is None:
        raise KeyError(slug)
    version = current_version(definition)
    if version is None:
        raise ValueError("The form has no current version.")

    defaults = form_version_print_layout_defaults(version)
    profile_key = print_layout_default_profile_key(profile["template_id"], profile["paper_size"])
    if profile_key not in defaults["profiles"]:
        return serialize_form(definition), False

    return (
        save_form_print_layout_default(
            session,
            slug,
            profile=profile,
            layout={},
        ),
        True,
    )
