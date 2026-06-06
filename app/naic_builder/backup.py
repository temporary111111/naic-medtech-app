from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import zipfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from .config import (
    BACKUPS_DIR,
    CONFIG_DIR,
    DB_PATH,
    PRODUCT_ID,
    PRODUCT_SHORT_NAME,
    UPLOADS_DIR,
    DATA_RUNTIME_DIR,
    ensure_runtime_directories,
)


BACKUP_FORMAT_VERSION = 1
SESSION_SECRET_FILENAME = "session-secret.txt"
BACKUP_ARCHIVE_PATTERN = "NDHI-LabRecords-Backup-*.zip"


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def archive_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S%fZ")


def file_size_label(size_bytes: int) -> str:
    units = ("B", "KB", "MB", "GB")
    value = float(size_bytes)
    unit = units[0]
    for unit in units:
        if value < 1024 or unit == units[-1]:
            break
        value /= 1024
    return f"{int(value)} {unit}" if unit == "B" else f"{value:.1f} {unit}"


def timestamp_label(value: datetime) -> str:
    local_value = value.astimezone()
    tz_name = local_value.tzname() or "local"
    return f"{local_value.strftime('%b %d, %Y %I:%M %p')} {tz_name}"


def safe_reason(reason: str) -> str:
    compact = re.sub(r"[^a-z0-9_-]+", "-", str(reason or "").strip().lower()).strip("-")
    return compact or "manual"


def serialize_backup_archive(path: Path) -> dict[str, Any]:
    stat = path.stat()
    modified_at = datetime.fromtimestamp(stat.st_mtime, timezone.utc)
    return {
        "name": path.name,
        "path": str(path.resolve()),
        "size_bytes": stat.st_size,
        "size_label": file_size_label(stat.st_size),
        "modified_at_utc": modified_at.isoformat(),
        "modified_label": timestamp_label(modified_at),
    }


def list_backup_archives(*, limit: int = 5, backup_dir: Path | None = None) -> list[dict[str, Any]]:
    archives = list_backup_archive_paths(backup_dir=backup_dir)
    return [serialize_backup_archive(path) for path in archives[:limit]]


def list_backup_archive_paths(*, backup_dir: Path | None = None) -> list[Path]:
    source_dir = (backup_dir or BACKUPS_DIR).expanduser()
    if not source_dir.is_dir():
        return []
    return sorted(
        (path for path in source_dir.glob(BACKUP_ARCHIVE_PATTERN) if path.is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def prune_backup_archives(*, keep_count: int, backup_dir: Path | None = None) -> list[dict[str, Any]]:
    archives = list_backup_archive_paths(backup_dir=backup_dir)
    resolved_keep_count = max(1, int(keep_count or 1))
    expired_archives = archives[resolved_keep_count:]
    deleted: list[dict[str, Any]] = []
    for archive_path in expired_archives:
        deleted.append(serialize_backup_archive(archive_path))
        archive_path.unlink()
    return deleted


def normalize_backup_destination(value: str | Path | None) -> str:
    return str(value or "").strip()


def local_backup_status(*, limit: int = 5) -> dict[str, Any]:
    archives = list_backup_archives(limit=limit)
    return {
        "backup_dir": str(BACKUPS_DIR.expanduser().resolve()),
        "archives": archives,
        "latest": archives[0] if archives else None,
        "count": len(archives),
    }


def external_backup_status(destination: str | Path | None, *, limit: int = 5) -> dict[str, Any]:
    destination_text = normalize_backup_destination(destination)
    if not destination_text:
        return {
            "configured": False,
            "status": "disabled",
            "label": "Not configured",
            "detail": "Add a folder path to keep a second copy outside this PC.",
            "backup_dir": "",
            "archives": [],
            "latest": None,
            "count": 0,
        }

    backup_dir = Path(destination_text).expanduser()
    if backup_dir.exists() and not backup_dir.is_dir():
        return {
            "configured": True,
            "status": "error",
            "label": "Check path",
            "detail": "The configured external backup path is not a folder.",
            "backup_dir": str(backup_dir),
            "archives": [],
            "latest": None,
            "count": 0,
        }

    archives = list_backup_archives(limit=limit, backup_dir=backup_dir)
    if backup_dir.is_dir():
        status = "ready"
        label = "Ready" if archives else "Empty"
        detail = "External backup folder is available."
    else:
        status = "warning"
        label = "Not found"
        detail = "The folder is not currently available. Connect the external drive or choose another path."

    return {
        "configured": True,
        "status": status,
        "label": label,
        "detail": detail,
        "backup_dir": str(backup_dir),
        "archives": archives,
        "latest": archives[0] if archives else None,
        "count": len(archives),
    }


def backup_health_summary(
    local_status: dict[str, Any],
    external_status: dict[str, Any],
) -> dict[str, str]:
    local_latest = local_status.get("latest") if isinstance(local_status, dict) else None
    external_latest = external_status.get("latest") if isinstance(external_status, dict) else None
    external_configured = bool(external_status.get("configured")) if isinstance(external_status, dict) else False
    external_state = str(external_status.get("status") or "") if isinstance(external_status, dict) else ""

    if not local_latest:
        return {
            "status": "warning",
            "chip_status": "pending",
            "label": "No backup yet",
            "title": "Create the first backup before clinic use",
            "detail": "There is no verified local backup archive yet. Create one before real patient records are entered.",
        }

    if not external_configured:
        return {
            "status": "warning",
            "chip_status": "pending",
            "label": "Local only",
            "title": "Local backup is available",
            "detail": "The latest local backup is verified. Add an external folder to keep a second copy outside this PC.",
        }

    if external_state == "error":
        return {
            "status": "error",
            "chip_status": "disabled",
            "label": "External path issue",
            "title": "Check the external backup path",
            "detail": "Local backup is available, but the configured external backup path is not usable.",
        }

    if external_state == "warning":
        return {
            "status": "warning",
            "chip_status": "pending",
            "label": "External missing",
            "title": "External backup folder is not available",
            "detail": "Local backup is available, but the external drive or folder is not currently reachable.",
        }

    if not external_latest:
        return {
            "status": "warning",
            "chip_status": "pending",
            "label": "External empty",
            "title": "External folder is ready",
            "detail": "Create a backup now to write and verify the first external copy.",
        }

    return {
        "status": "ready",
        "chip_status": "active",
        "label": "Local + external",
        "title": "Backups are ready",
        "detail": "The latest local backup and external copy are both available for verification.",
    }


def verify_latest_backup_archive() -> dict[str, Any]:
    archives = list_backup_archives(limit=1)
    if not archives:
        raise FileNotFoundError("No local backup archive found.")
    return verify_backup_archive(Path(archives[0]["path"]))


def verify_latest_external_backup_archive(destination: str | Path | None) -> dict[str, Any]:
    destination_text = normalize_backup_destination(destination)
    if not destination_text:
        raise FileNotFoundError("No external backup folder is configured.")
    archives = list_backup_archives(limit=1, backup_dir=Path(destination_text).expanduser())
    if not archives:
        raise FileNotFoundError("No external backup archive found.")
    return verify_backup_archive(Path(archives[0]["path"]))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sqlite_integrity_check(db_path: Path) -> None:
    with closing(sqlite3.connect(db_path)) as connection:
        result = connection.execute("PRAGMA integrity_check").fetchone()
    if not result or str(result[0]).lower() != "ok":
        raise RuntimeError(f"SQLite integrity check failed for {db_path.name}.")


def sqlite_sidecar_paths(db_path: Path) -> list[Path]:
    return [
        Path(f"{db_path}-wal"),
        Path(f"{db_path}-shm"),
        Path(f"{db_path}-journal"),
    ]


def remove_sqlite_sidecars(db_path: Path) -> None:
    for path in sqlite_sidecar_paths(db_path):
        path.unlink(missing_ok=True)


def dispose_database_engine_if_loaded() -> None:
    database_module = sys.modules.get("naic_builder.database")
    engine = getattr(database_module, "engine", None) if database_module is not None else None
    if engine is not None:
        engine.dispose()


def snapshot_sqlite_database(source_path: Path, destination_path: Path) -> None:
    if not source_path.is_file():
        raise FileNotFoundError(f"Runtime database not found: {source_path}")
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(source_path)) as source, closing(sqlite3.connect(destination_path)) as destination:
        source.backup(destination)
    sqlite_integrity_check(destination_path)


def iter_runtime_assets() -> Iterable[tuple[Path, Path]]:
    for source_root, archive_root in ((UPLOADS_DIR, Path("uploads")), (CONFIG_DIR, Path("config"))):
        if not source_root.is_dir():
            continue
        for source_path in sorted(source_root.rglob("*")):
            if not source_path.is_file() or source_path.name == SESSION_SECRET_FILENAME:
                continue
            yield source_path, archive_root / source_path.relative_to(source_root)


def write_manifest(stage_dir: Path, *, reason: str) -> dict[str, Any]:
    files = []
    for file_path in sorted(path for path in stage_dir.rglob("*") if path.is_file()):
        relative_path = file_path.relative_to(stage_dir).as_posix()
        if relative_path == "manifest.json":
            continue
        files.append(
            {
                "path": relative_path,
                "bytes": file_path.stat().st_size,
                "sha256": sha256_file(file_path),
            }
        )
    manifest = {
        "format_version": BACKUP_FORMAT_VERSION,
        "product_id": PRODUCT_ID,
        "product_name": PRODUCT_SHORT_NAME,
        "created_at_utc": utc_timestamp(),
        "reason": safe_reason(reason),
        "database": f"database/{DB_PATH.name}",
        "files": files,
    }
    (stage_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def create_verified_backup(*, reason: str = "manual", destination_dir: Path | None = None) -> Path:
    ensure_runtime_directories()
    target_dir = (destination_dir or BACKUPS_DIR).expanduser().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    reason_slug = safe_reason(reason)
    archive_path = target_dir / f"NDHI-LabRecords-Backup-{archive_timestamp()}-{reason_slug}.zip"
    partial_path = archive_path.with_suffix(".zip.partial")

    with tempfile.TemporaryDirectory(prefix="ndhi-backup-stage-") as temp_dir:
        stage_dir = Path(temp_dir)
        snapshot_sqlite_database(DB_PATH, stage_dir / "database" / DB_PATH.name)
        for source_path, relative_path in iter_runtime_assets():
            destination_path = stage_dir / relative_path
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination_path)
        write_manifest(stage_dir, reason=reason_slug)
        with zipfile.ZipFile(partial_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file_path in sorted(path for path in stage_dir.rglob("*") if path.is_file()):
                archive.write(file_path, file_path.relative_to(stage_dir).as_posix())

    os.replace(partial_path, archive_path)
    verify_backup_archive(archive_path)
    return archive_path


def copy_backup_archive_to_destination(source_path: Path, destination: str | Path | None) -> Path | None:
    destination_text = normalize_backup_destination(destination)
    if not destination_text:
        return None

    resolved_source = source_path.expanduser().resolve()
    if not resolved_source.is_file():
        raise FileNotFoundError(f"Backup archive not found: {resolved_source}")

    target_dir = Path(destination_text).expanduser()
    if target_dir.exists() and not target_dir.is_dir():
        raise NotADirectoryError(f"External backup path is not a folder: {target_dir}")
    target_dir.mkdir(parents=True, exist_ok=True)

    target_path = target_dir / resolved_source.name
    partial_path = target_path.with_suffix(".zip.partial")
    shutil.copy2(resolved_source, partial_path)
    os.replace(partial_path, target_path)
    verify_backup_archive(target_path)
    return target_path


def validate_archive_member(member_name: str) -> None:
    member_path = PurePosixPath(member_name)
    if member_path.is_absolute() or ".." in member_path.parts:
        raise RuntimeError(f"Unsafe backup archive member: {member_name}")


def verify_backup_archive(archive_path: Path) -> dict[str, Any]:
    resolved_path = archive_path.expanduser().resolve()
    if not resolved_path.is_file():
        raise FileNotFoundError(f"Backup archive not found: {resolved_path}")

    with zipfile.ZipFile(resolved_path) as archive:
        corrupt_member = archive.testzip()
        if corrupt_member:
            raise RuntimeError(f"Backup archive CRC check failed: {corrupt_member}")
        for member_name in archive.namelist():
            validate_archive_member(member_name)
        manifest = json.loads(archive.read("manifest.json"))
        if not isinstance(manifest, dict):
            raise RuntimeError("Backup manifest is invalid.")
        if manifest.get("product_id") != PRODUCT_ID:
            raise RuntimeError("Backup archive belongs to a different product.")
        if manifest.get("format_version") != BACKUP_FORMAT_VERSION:
            raise RuntimeError("Unsupported backup archive format.")
        expected_files = manifest.get("files")
        if not isinstance(expected_files, list):
            raise RuntimeError("Backup manifest does not list files.")
        for item in expected_files:
            member_name = str(item.get("path") or "")
            validate_archive_member(member_name)
            digest = hashlib.sha256(archive.read(member_name)).hexdigest()
            if digest != item.get("sha256"):
                raise RuntimeError(f"Backup checksum failed: {member_name}")
        database_member = str(manifest.get("database") or "")
        validate_archive_member(database_member)
        with tempfile.TemporaryDirectory(prefix="ndhi-backup-verify-") as temp_dir:
            database_path = Path(temp_dir) / Path(database_member).name
            database_path.write_bytes(archive.read(database_member))
            sqlite_integrity_check(database_path)

    return {
        "archive": str(resolved_path),
        "created_at_utc": manifest.get("created_at_utc"),
        "files": len(expected_files),
        "verified": True,
    }


def extract_verified_backup_archive(archive_path: Path, stage_dir: Path) -> dict[str, Any]:
    verify_backup_archive(archive_path)
    resolved_path = archive_path.expanduser().resolve()
    with zipfile.ZipFile(resolved_path) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        if not isinstance(manifest, dict):
            raise RuntimeError("Backup manifest is invalid.")
        expected_files = manifest.get("files")
        if not isinstance(expected_files, list):
            raise RuntimeError("Backup manifest does not list files.")
        expected_paths = {
            str(item.get("path") or "")
            for item in expected_files
            if isinstance(item, dict)
        }
        expected_paths.add("manifest.json")
        expected_paths.add(str(manifest.get("database") or ""))
        for member in archive.infolist():
            validate_archive_member(member.filename)
            if member.filename not in expected_paths:
                continue
            if member.is_dir():
                continue
            destination = stage_dir / PurePosixPath(member.filename)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, destination.open("wb") as target:
                shutil.copyfileobj(source, target)
    return manifest


def restore_directory_tree(source_dir: Path, target_dir: Path) -> int:
    restored_count = 0
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    if not source_dir.is_dir():
        return restored_count
    for source_path in sorted(path for path in source_dir.rglob("*") if path.is_file()):
        relative_path = source_path.relative_to(source_dir)
        destination_path = target_dir / relative_path
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination_path)
        restored_count += 1
    return restored_count


def restore_config_files(source_config_dir: Path) -> int:
    restored_count = 0
    if not source_config_dir.is_dir():
        return restored_count
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    for source_path in sorted(path for path in source_config_dir.rglob("*") if path.is_file()):
        if source_path.name == SESSION_SECRET_FILENAME:
            continue
        relative_path = source_path.relative_to(source_config_dir)
        destination_path = CONFIG_DIR / relative_path
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination_path)
        restored_count += 1
    return restored_count


def restore_verified_backup(
    archive_path: Path,
    *,
    include_config: bool = False,
    emergency_reason: str = "pre-restore",
) -> dict[str, Any]:
    ensure_runtime_directories()
    resolved_archive = archive_path.expanduser().resolve()
    with tempfile.TemporaryDirectory(prefix="ndhi-backup-restore-") as temp_dir:
        stage_dir = Path(temp_dir)
        manifest = extract_verified_backup_archive(resolved_archive, stage_dir)
        database_member = str(manifest.get("database") or "")
        validate_archive_member(database_member)
        staged_database = stage_dir / PurePosixPath(database_member)
        sqlite_integrity_check(staged_database)

        emergency_backup = create_verified_backup(reason=emergency_reason)
        dispose_database_engine_if_loaded()
        remove_sqlite_sidecars(DB_PATH)

        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        restore_database_path = DB_PATH.parent / f"{DB_PATH.name}.restore"
        shutil.copy2(staged_database, restore_database_path)
        sqlite_integrity_check(restore_database_path)
        os.replace(restore_database_path, DB_PATH)
        remove_sqlite_sidecars(DB_PATH)

        restored_uploads = restore_directory_tree(stage_dir / "uploads", UPLOADS_DIR)
        restored_config = restore_config_files(stage_dir / "config") if include_config else 0
        sqlite_integrity_check(DB_PATH)

    return {
        "archive": str(resolved_archive),
        "emergency_backup": str(emergency_backup),
        "restored_at_utc": utc_timestamp(),
        "database": str(DB_PATH.expanduser().resolve()),
        "runtime_dir": str(DATA_RUNTIME_DIR.expanduser().resolve()),
        "uploads_restored": restored_uploads,
        "config_restored": restored_config,
        "config_included": include_config,
        "verified": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or verify an NDHI Laboratory Records backup.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="Create and verify a backup archive.")
    create_parser.add_argument("--reason", default="manual")
    create_parser.add_argument("--destination", type=Path)

    verify_parser = subparsers.add_parser("verify", help="Verify an existing backup archive.")
    verify_parser.add_argument("archive", type=Path)

    restore_parser = subparsers.add_parser("restore", help="Restore a verified backup archive.")
    restore_parser.add_argument("archive", type=Path)
    restore_parser.add_argument("--include-config", action="store_true")

    args = parser.parse_args()
    if args.command == "create":
        backup_path = create_verified_backup(reason=args.reason, destination_dir=args.destination)
        print(json.dumps(verify_backup_archive(backup_path), indent=2))
        return 0
    if args.command == "restore":
        print(json.dumps(restore_verified_backup(args.archive, include_config=args.include_config), indent=2))
        return 0
    print(json.dumps(verify_backup_archive(args.archive), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
