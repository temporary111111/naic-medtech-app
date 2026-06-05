from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
import html
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app"))

from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from sqlalchemy import select

from naic_builder.config import DB_PATH, SESSION_SECRET

DEFAULT_QA_SLUGS = [
    "ogtt",
    "semen",
    "serology",
    "hematology",
    "male",
    "female",
    "blood_bank",
]

STRESS_VALUES = {
    "name": "Maria Christina Dela Cruz-Santos Villanueva",
    "case": "NAIC-2026-0001-RECHECK-LONG",
    "physician": "Dr. Antonio Miguel Reyes III, Internal Medicine",
    "room": "Outpatient Department / Follow-up Bay 2",
    "medical technologist": "Maria Lourdes Santos, RMT",
    "medtech": "Maria Lourdes Santos, RMT",
    "pathologist": "Dr. Rafael Alfonso Cruz, FPSP",
    "remarks": "Slightly hemolyzed specimen; correlate clinically and repeat if clinically indicated.",
    "others": "Occasional epithelial cells; correlate clinically if symptoms persist.",
    "released by": "Maria Lourdes Santos, RMT",
    "released to": "Juan Miguel Dela Cruz, authorized representative",
}


@dataclass(frozen=True)
class RuntimeDbSnapshot:
    db_path: Path
    backup_path: Path | None
    existed: bool


def sqlite_sidecar_paths(db_path: Path) -> list[Path]:
    return [
        Path(f"{db_path}-wal"),
        Path(f"{db_path}-shm"),
        Path(f"{db_path}-journal"),
    ]


def remove_sqlite_sidecars(db_path: Path) -> None:
    for path in sqlite_sidecar_paths(db_path):
        if path.exists():
            path.unlink()


def snapshot_runtime_db() -> RuntimeDbSnapshot:
    db_path = DB_PATH.resolve()
    if not db_path.exists():
        return RuntimeDbSnapshot(db_path=db_path, backup_path=None, existed=False)

    with tempfile.NamedTemporaryFile(
        prefix="naic-print-record-qa-",
        suffix=".db",
        delete=False,
    ) as backup_file:
        backup_path = Path(backup_file.name)
    shutil.copy2(db_path, backup_path)
    return RuntimeDbSnapshot(db_path=db_path, backup_path=backup_path, existed=True)


def dispose_database_engine_if_loaded() -> None:
    if "naic_builder.database" not in sys.modules:
        return

    from naic_builder.database import engine

    engine.dispose()


def restore_runtime_db(snapshot: RuntimeDbSnapshot) -> None:
    dispose_database_engine_if_loaded()
    remove_sqlite_sidecars(snapshot.db_path)

    if snapshot.existed and snapshot.backup_path is not None:
        snapshot.db_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(snapshot.backup_path, snapshot.db_path)
        snapshot.backup_path.unlink(missing_ok=True)
        return

    if snapshot.db_path.exists():
        snapshot.db_path.unlink()


def compact_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def apply_stress_values(
    blocks: list[dict[str, Any]],
    values: dict[str, Any],
    normalize_items_func: Any,
) -> None:
    for block in normalize_items_func(blocks):
        if not isinstance(block, dict):
            continue
        kind = compact_text(block.get("kind"))
        block_id = compact_text(block.get("id"))
        props = block.get("props") if isinstance(block.get("props"), dict) else {}
        label = f"{props.get('key') or ''} {block.get('name') or ''}".lower()
        if kind == "field" and block_id:
            for key, value in STRESS_VALUES.items():
                if key in label:
                    values[block_id] = value
                    break
        apply_stress_values(block.get("children"), values, normalize_items_func)


def build_required_signatory_meta(block_schema: dict[str, Any]) -> dict[str, Any]:
    meta = block_schema.get("meta") if isinstance(block_schema.get("meta"), dict) else {}
    slots = meta.get("signatories") if isinstance(meta.get("signatories"), list) else []
    signatories: dict[str, dict[str, str]] = {}

    for slot in slots:
        if not isinstance(slot, dict) or not slot.get("required"):
            continue
        slot_id = compact_text(slot.get("id"))
        input_type = compact_text(slot.get("input_type")).lower()
        if not slot_id:
            continue

        if input_type == "person_dropdown":
            options = slot.get("options") if isinstance(slot.get("options"), list) else []
            option_id = ""
            for option in options:
                if isinstance(option, dict) and compact_text(option.get("id")):
                    option_id = compact_text(option.get("id"))
                    break
            if option_id:
                signatories[slot_id] = {"option_id": option_id}
        elif input_type == "manual":
            signatories[slot_id] = {
                "name": "Print QA Signatory",
                "license": "000000",
            }

    return {"signatories": signatories} if signatories else {}


def first_active_user_id() -> int | None:
    from naic_builder.database import SessionLocal
    from naic_builder.models import User

    with SessionLocal() as session:
        user = session.scalars(
            select(User)
            .where(User.status == "active")
            .order_by(User.id)
        ).first()
        return user.id if user else None


def signed_client(user_id: int | None) -> TestClient:
    from naic_builder.main import app

    client = TestClient(app)
    if user_id is not None:
        client.cookies.set("session", signed_session_cookie_value(user_id))
    return client


def signed_session_cookie_value(user_id: int) -> str:
    raw = base64.b64encode(json.dumps({"user_id": user_id}).encode("utf-8"))
    return TimestampSigner(str(SESSION_SECRET)).sign(raw).decode("utf-8")


def create_completed_print_qa_record(slug: str, *, actor_user_id: int | None) -> dict[str, Any]:
    from naic_builder.database import SessionLocal
    from naic_builder.models import FormDefinition
    from naic_builder.schemas import RecordCreatePayload, RecordUpdatePayload
    from naic_builder.services import (
        build_record_print_document,
        build_sample_print_values,
        complete_record,
        create_record,
        current_version,
        get_clinic_profile,
        get_record_or_none,
        load_block_storage_document,
        normalize_items,
    )

    created_record_id: int | None = None
    with SessionLocal() as session:
        definition = session.scalars(select(FormDefinition).where(FormDefinition.slug == slug)).first()
        if definition is None:
            raise ValueError(f"Form not found: {slug}")
        version = current_version(definition)
        if version is None:
            raise ValueError(f"Form has no current version: {slug}")

        block_schema, _ = load_block_storage_document(version)
        values = build_sample_print_values(normalize_items(block_schema.get("blocks")))
        apply_stress_values(block_schema.get("blocks"), values, normalize_items)
        indexed_meta = build_required_signatory_meta(block_schema)

        created = create_record(
            session,
            RecordCreatePayload(form_slug=slug, values=values, indexed_meta=indexed_meta),
            actor_user_id=actor_user_id,
        )
        created_record_id = int(created["id"])
        completed = complete_record(
            session,
            created_record_id,
            RecordUpdatePayload(values=values, indexed_meta=indexed_meta),
            actor_user_id=actor_user_id,
        )
        record = get_record_or_none(session, created_record_id)
        if record is None:
            raise ValueError(f"Created record could not be loaded: {slug}")

        clinic_profile = get_clinic_profile(session)
        document = build_record_print_document(
            record,
            clinic_profile=clinic_profile,
            clinic_logo_url="/settings/clinic/logo" if clinic_profile.get("has_logo") else "",
        )
        fit = document.get("fit_estimate") if isinstance(document.get("fit_estimate"), dict) else {}

    return {
        "slug": slug,
        "record_id": created_record_id,
        "record_key": document.get("record_key"),
        "form_name": document.get("form_name"),
        "status": completed.get("status"),
        "fit": fit.get("status") or "",
        "fit_label": fit.get("label") or "",
    }


def delete_record(record_id: int) -> None:
    from naic_builder.database import SessionLocal
    from naic_builder.models import Record

    with SessionLocal() as cleanup_session:
        record = cleanup_session.get(Record, record_id)
        if record is not None:
            cleanup_session.delete(record)
            cleanup_session.commit()


def qa_record_print(slug: str, *, actor_user_id: int | None, keep_records: bool) -> dict[str, Any]:
    result = create_completed_print_qa_record(slug, actor_user_id=actor_user_id)
    created_record_id = int(result["record_id"])

    client = signed_client(actor_user_id)
    response = client.get(f"/records/{created_record_id}/print")
    if response.status_code != 200:
        raise ValueError(f"Print route failed for {slug}: HTTP {response.status_code}")
    html_text = html.unescape(response.text)
    missing = [
        token
        for token in [
            "print-page",
            "print-fit-badge",
            compact_text(result.get("record_key")),
            compact_text(result.get("form_name")),
            "Medical Technologist",
        ]
        if token and token not in html_text
    ]

    if not keep_records:
        delete_record(created_record_id)

    return {
        **result,
        "missing": missing,
        "kept": keep_records,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create temporary actual records and smoke-test /records/{id}/print.",
    )
    parser.add_argument("slugs", nargs="*", help="Form slugs to test.")
    parser.add_argument("--all", action="store_true", help="Test all current forms.")
    parser.add_argument(
        "--keep-records",
        action="store_true",
        help="Do not restore the runtime DB or delete QA records after the run.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    snapshot = None if args.keep_records else snapshot_runtime_db()

    try:
        from naic_builder.database import SessionLocal
        from naic_builder.models import FormDefinition

        actor_user_id = first_active_user_id()
        with SessionLocal() as session:
            if args.all:
                slugs = [
                    slug
                    for slug in session.scalars(select(FormDefinition.slug).order_by(FormDefinition.name)).all()
                ]
            else:
                slugs = args.slugs or DEFAULT_QA_SLUGS

        failures: list[str] = []
        for slug in slugs:
            result = qa_record_print(slug, actor_user_id=actor_user_id, keep_records=args.keep_records)
            missing = ", ".join(result["missing"]) if result["missing"] else "none"
            print(
                "\t".join(
                    [
                        result["slug"],
                        str(result["record_id"]),
                        str(result["record_key"]),
                        str(result["status"]),
                        str(result["fit"]),
                        str(result["fit_label"]),
                        f"missing={missing}",
                        f"kept={result['kept']}",
                    ]
                )
            )
            if result["missing"] or result["fit"] == "long":
                failures.append(slug)

        if failures:
            print(f"FAILED: {', '.join(failures)}", file=sys.stderr)
            return 1
        return 0
    finally:
        if snapshot is not None:
            restore_runtime_db(snapshot)


if __name__ == "__main__":
    raise SystemExit(main())
