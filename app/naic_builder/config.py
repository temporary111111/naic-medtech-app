from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
APP_DIR = ROOT_DIR / "app"
PACKAGE_DIR = APP_DIR / "naic_builder"
if getattr(sys, "frozen", False):
    PACKAGE_DIR = Path(__file__).resolve().parent
RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", ROOT_DIR))
TEMPLATES_DIR = PACKAGE_DIR / "templates"
STATIC_DIR = PACKAGE_DIR / "static"
DATA_SOURCE_DIR = RESOURCE_ROOT / "data" / "source"
DATA_RUNTIME_DIR = Path(
    os.environ.get("NDHI_LABRECORDS_DATA_DIR") or ROOT_DIR / "data" / "runtime"
).expanduser()
UPLOADS_DIR = DATA_RUNTIME_DIR / "uploads"
RECORD_UPLOADS_DIR = UPLOADS_DIR / "records"
CLINIC_UPLOADS_DIR = UPLOADS_DIR / "clinic"
USER_UPLOADS_DIR = UPLOADS_DIR / "users"
SIGNATORY_UPLOADS_DIR = UPLOADS_DIR / "signatories"
DEFAULT_PATHOLOGIST_STAMP_FILENAME = "default-pathologist-stamp.png"
DEFAULT_PATHOLOGIST_STAMP_RESOURCE_PATH = (
    RESOURCE_ROOT / "artifacts" / "seed" / "signatories" / "bernardita-mojica-figueroa-stamp.png"
)
DEFAULT_PATHOLOGIST_STAMP_RUNTIME_PATH = SIGNATORY_UPLOADS_DIR / DEFAULT_PATHOLOGIST_STAMP_FILENAME
DEFAULT_PATHOLOGIST_STAMP_URL = f"/signatory-stamps/{DEFAULT_PATHOLOGIST_STAMP_FILENAME}"
BACKUPS_DIR = DATA_RUNTIME_DIR / "backups"
LOGS_DIR = DATA_RUNTIME_DIR / "logs"
CONFIG_DIR = DATA_RUNTIME_DIR / "config"
DATABASE_DIR = DATA_RUNTIME_DIR / "database"
DATABASE_FILENAME = "ndhi_labrecords.db"
LEGACY_DATABASE_FILENAME = "naic_medtech.db"
DB_PATH = (
    DATA_RUNTIME_DIR / LEGACY_DATABASE_FILENAME
    if (DATA_RUNTIME_DIR / LEGACY_DATABASE_FILENAME).exists()
    else DATABASE_DIR / DATABASE_FILENAME
)
REFERENCE_SCHEMA_PATH = RESOURCE_ROOT / "artifacts" / "schema" / "naic_medtech_app_schema.json"

ORGANIZATION_LEGAL_NAME = "Naic Doctors Hospital, Incorporated"
ORGANIZATION_SHORT_NAME = "Naic Doctors Hospital"
PRODUCT_NAME = "Laboratory Records System"
PRODUCT_SHORT_NAME = "NDHI Laboratory Records"
PRODUCT_ID = "ndhi-labrecords"
APP_TITLE = f"{ORGANIZATION_SHORT_NAME} | {PRODUCT_NAME}"
SESSION_SECRET = (
    os.environ.get("NDHI_SESSION_SECRET")
    or os.environ.get("NAIC_SESSION_SECRET")
    or "ndhi-labrecords-dev-session-secret"
)


def ensure_runtime_directories() -> None:
    for directory in (
        DATA_RUNTIME_DIR,
        UPLOADS_DIR,
        RECORD_UPLOADS_DIR,
        CLINIC_UPLOADS_DIR,
        USER_UPLOADS_DIR,
        SIGNATORY_UPLOADS_DIR,
        BACKUPS_DIR,
        LOGS_DIR,
        CONFIG_DIR,
        DATABASE_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)
