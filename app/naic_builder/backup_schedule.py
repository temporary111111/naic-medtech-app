from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .backup import (
    BackupOperationBusyError,
    backup_operation_lock,
    copy_backup_archive_to_destination,
    create_verified_backup,
    local_backup_status,
    prune_backup_archives,
    timestamp_label,
    utc_timestamp,
)
from .config import CONFIG_DIR
from .desktop_settings import read_desktop_settings


BACKUP_SCHEDULE_STATE_FILENAME = "backup-schedule.json"
DAILY_BACKUP_REASON = "daily-auto"
DEFAULT_STARTUP_DELAY_SECONDS = 12
DEFAULT_CHECK_INTERVAL_SECONDS = 30 * 60


def backup_schedule_state_path() -> Path:
    return CONFIG_DIR / BACKUP_SCHEDULE_STATE_FILENAME


def default_backup_schedule_state() -> dict[str, Any]:
    return {
        "enabled": True,
        "status": "pending",
        "last_checked_at_utc": "",
        "last_success_at_utc": "",
        "last_backup_archive": "",
        "last_external_archive": "",
        "last_external_error": "",
        "last_error_at_utc": "",
        "last_error": "",
        "last_skip_at_utc": "",
        "last_skip_reason": "",
        "deleted_local_archives": 0,
        "deleted_external_archives": 0,
    }


def read_backup_schedule_state() -> dict[str, Any]:
    state_path = backup_schedule_state_path()
    if not state_path.exists():
        return default_backup_schedule_state()
    try:
        raw_state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default_backup_schedule_state()
    if not isinstance(raw_state, dict):
        return default_backup_schedule_state()
    state = default_backup_schedule_state()
    state.update(raw_state)
    state["enabled"] = bool(state.get("enabled", True))
    return state


def write_backup_schedule_state(state: dict[str, Any]) -> dict[str, Any]:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    merged_state = default_backup_schedule_state()
    merged_state.update(state)
    state_path = backup_schedule_state_path()
    partial_path = state_path.with_suffix(".json.partial")
    partial_path.write_text(json.dumps(merged_state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(partial_path, state_path)
    return merged_state


def parse_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def datetime_label(value: Any) -> str:
    parsed = parse_datetime(value)
    return timestamp_label(parsed) if parsed else ""


def latest_backup_datetime(local_status: dict[str, Any] | None = None) -> datetime | None:
    status = local_status if local_status is not None else local_backup_status(limit=1)
    latest = status.get("latest") if isinstance(status, dict) else None
    if not isinstance(latest, dict):
        return None
    return parse_datetime(latest.get("modified_at_utc"))


def daily_backup_due(
    *,
    now: datetime | None = None,
    local_status: dict[str, Any] | None = None,
) -> bool:
    current = now or datetime.now().astimezone()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    latest = latest_backup_datetime(local_status)
    if latest is None:
        return True
    return latest.astimezone().date() != current.astimezone().date()


def run_daily_backup_if_due() -> dict[str, Any]:
    checked_at = utc_timestamp()
    state = read_backup_schedule_state()
    state["last_checked_at_utc"] = checked_at

    if not state.get("enabled", True):
        state["status"] = "disabled"
        return write_backup_schedule_state(state)

    if not daily_backup_due():
        state["status"] = "current"
        return write_backup_schedule_state(state)

    try:
        with backup_operation_lock(blocking=False):
            running_state = dict(state)
            running_state["status"] = "running"
            write_backup_schedule_state(running_state)

            desktop_settings = read_desktop_settings()
            external_backup_dir = str(desktop_settings.get("external_backup_dir") or "")
            backup_retention_count = int(desktop_settings.get("backup_retention_count") or 30)

            backup_path = create_verified_backup(reason=DAILY_BACKUP_REASON)
            deleted_local = prune_backup_archives(keep_count=backup_retention_count)

            external_backup_path: Path | None = None
            external_error = ""
            deleted_external: list[dict[str, Any]] = []
            if external_backup_dir:
                try:
                    external_backup_path = copy_backup_archive_to_destination(backup_path, external_backup_dir)
                    if external_backup_path is not None:
                        deleted_external = prune_backup_archives(
                            keep_count=backup_retention_count,
                            backup_dir=Path(external_backup_dir).expanduser(),
                        )
                except Exception as exc:
                    external_error = str(exc)

            success_at = utc_timestamp()
            state.update(
                {
                    "status": "warning" if external_error else "success",
                    "last_success_at_utc": success_at,
                    "last_backup_archive": str(backup_path),
                    "last_external_archive": str(external_backup_path) if external_backup_path else "",
                    "last_external_error": external_error,
                    "last_error_at_utc": "",
                    "last_error": "",
                    "last_skip_at_utc": "",
                    "last_skip_reason": "",
                    "deleted_local_archives": len(deleted_local),
                    "deleted_external_archives": len(deleted_external),
                }
            )
    except BackupOperationBusyError as exc:
        state.update(
            {
                "status": "skipped",
                "last_skip_at_utc": utc_timestamp(),
                "last_skip_reason": str(exc),
            }
        )
    except Exception as exc:
        state.update(
            {
                "status": "error",
                "last_error_at_utc": utc_timestamp(),
                "last_error": str(exc),
            }
        )
    return write_backup_schedule_state(state)


def backup_schedule_summary(
    *,
    state: dict[str, Any] | None = None,
    local_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    current_state = state or read_backup_schedule_state()
    backup_status = local_status if local_status is not None else local_backup_status(limit=1)
    latest = backup_status.get("latest") if isinstance(backup_status, dict) else None
    due = daily_backup_due(local_status=backup_status)
    status = str(current_state.get("status") or "")

    title = "Automatic daily backup"
    label = "Active"
    chip_status = "active"
    detail = "A verified backup has already been created today."
    summary_status = "ready"

    if isinstance(latest, dict):
        detail = f"Latest verified backup: {latest.get('name')} - {latest.get('modified_label')}"

    if status == "disabled":
        label = "Disabled"
        chip_status = "disabled"
        summary_status = "disabled"
        detail = "Automatic backup is disabled."
    elif status == "error":
        label = "Needs attention"
        chip_status = "disabled"
        summary_status = "error"
        detail = f"Automatic backup failed: {current_state.get('last_error') or 'Unknown error'}"
    elif status == "warning":
        label = "Local saved"
        chip_status = "pending"
        summary_status = "warning"
        detail = "Automatic local backup succeeded, but the external copy needs attention."
    elif status == "skipped":
        label = "Waiting"
        chip_status = "pending"
        summary_status = "warning"
        detail = "Backup or restore is already running. The app will check again automatically."
    elif status == "running":
        label = "Running"
        chip_status = "pending"
        summary_status = "warning"
        detail = "Automatic backup is currently running."
    elif due:
        label = "Due"
        chip_status = "pending"
        summary_status = "warning"
        detail = "No verified backup has been created today. The app will create one while it is open."

    return {
        "status": summary_status,
        "chip_status": chip_status,
        "label": label,
        "title": title,
        "detail": detail,
        "last_checked_label": datetime_label(current_state.get("last_checked_at_utc")),
        "last_success_label": datetime_label(current_state.get("last_success_at_utc")),
        "last_backup_archive_name": Path(str(current_state.get("last_backup_archive") or "")).name,
        "last_external_archive_name": Path(str(current_state.get("last_external_archive") or "")).name,
        "last_external_error": str(current_state.get("last_external_error") or ""),
        "last_error": str(current_state.get("last_error") or ""),
    }


def positive_env_int(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, ""))
    except ValueError:
        return default
    return value if value > 0 else default


async def wait_for_stop(stop_event: asyncio.Event, timeout_seconds: int) -> bool:
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        return False
    return True


async def scheduled_backup_loop(
    stop_event: asyncio.Event,
    *,
    startup_delay_seconds: int | None = None,
    interval_seconds: int | None = None,
) -> None:
    startup_delay = (
        startup_delay_seconds
        if startup_delay_seconds is not None
        else positive_env_int("NDHI_BACKUP_STARTUP_DELAY_SECONDS", DEFAULT_STARTUP_DELAY_SECONDS)
    )
    interval = (
        interval_seconds
        if interval_seconds is not None
        else positive_env_int("NDHI_BACKUP_CHECK_INTERVAL_SECONDS", DEFAULT_CHECK_INTERVAL_SECONDS)
    )

    if await wait_for_stop(stop_event, startup_delay):
        return

    while not stop_event.is_set():
        await asyncio.to_thread(run_daily_backup_if_due)
        if await wait_for_stop(stop_event, interval):
            return
