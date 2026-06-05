from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
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
    source_dir = (backup_dir or BACKUPS_DIR).expanduser()
    if not source_dir.is_dir():
        return []
    archives = sorted(
        (path for path in source_dir.glob(BACKUP_ARCHIVE_PATTERN) if path.is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return [serialize_backup_archive(path) for path in archives[:limit]]


def local_backup_status(*, limit: int = 5) -> dict[str, Any]:
    archives = list_backup_archives(limit=limit)
    return {
        "backup_dir": str(BACKUPS_DIR.expanduser().resolve()),
        "archives": archives,
        "latest": archives[0] if archives else None,
        "count": len(archives),
    }


def verify_latest_backup_archive() -> dict[str, Any]:
    archives = list_backup_archives(limit=1)
    if not archives:
        raise FileNotFoundError("No local backup archive found.")
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or verify an NDHI Laboratory Records backup.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="Create and verify a backup archive.")
    create_parser.add_argument("--reason", default="manual")
    create_parser.add_argument("--destination", type=Path)

    verify_parser = subparsers.add_parser("verify", help="Verify an existing backup archive.")
    verify_parser.add_argument("archive", type=Path)

    args = parser.parse_args()
    if args.command == "create":
        backup_path = create_verified_backup(reason=args.reason, destination_dir=args.destination)
        print(json.dumps(verify_backup_archive(backup_path), indent=2))
        return 0
    print(json.dumps(verify_backup_archive(args.archive), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
