from __future__ import annotations

import asyncio
import json
import os
import threading
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
CHANGE_BACKUP_REASON = "after-change-sync"
DEFAULT_STARTUP_DELAY_SECONDS = 12
DEFAULT_CHECK_INTERVAL_SECONDS = 30 * 60
DEFAULT_CHANGE_BACKUP_DEBOUNCE_SECONDS = 2
DEFAULT_CHANGE_BACKUP_RETRY_SECONDS = 30
CHANGE_BACKUP_DISABLED_ENV = "NDHI_AFTER_CHANGE_BACKUP_DISABLED"
_CHANGE_BACKUP_PENDING_EVENT = threading.Event()
_CHANGE_BACKUP_STOP_EVENT = threading.Event()
_CHANGE_BACKUP_THREAD_LOCK = threading.Lock()
_CHANGE_BACKUP_STATE_LOCK = threading.Lock()
_CHANGE_BACKUP_THREAD: threading.Thread | None = None
_CHANGE_BACKUP_HAS_PENDING_WORK = False


def backup_schedule_state_path() -> Path:
    return CONFIG_DIR / BACKUP_SCHEDULE_STATE_FILENAME


def default_backup_schedule_state() -> dict[str, Any]:
    return {
        "enabled": True,
        "status": "pending",
        "last_backup_reason": "",
        "last_requested_at_utc": "",
        "last_started_at_utc": "",
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


def _run_configured_backup(
    *,
    state: dict[str, Any],
    reason: str,
    checked_at: str,
) -> dict[str, Any]:
    backup_reason = str(reason or DAILY_BACKUP_REASON).strip() or DAILY_BACKUP_REASON
    state["last_checked_at_utc"] = checked_at

    if not state.get("enabled", True):
        state["status"] = "disabled"
        return write_backup_schedule_state(state)

    try:
        with backup_operation_lock(blocking=False):
            started_at = utc_timestamp()
            running_state = dict(state)
            running_state.update(
                {
                    "status": "running",
                    "last_backup_reason": backup_reason,
                    "last_started_at_utc": started_at,
                }
            )
            write_backup_schedule_state(running_state)

            desktop_settings = read_desktop_settings()
            external_backup_dir = str(desktop_settings.get("external_backup_dir") or "")
            backup_retention_count = int(desktop_settings.get("backup_retention_count") or 30)

            backup_path = create_verified_backup(reason=backup_reason)
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
                    "last_backup_reason": backup_reason,
                    "last_started_at_utc": started_at,
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
                "last_backup_reason": backup_reason,
                "last_skip_at_utc": utc_timestamp(),
                "last_skip_reason": str(exc),
            }
        )
    except Exception as exc:
        state.update(
            {
                "status": "error",
                "last_backup_reason": backup_reason,
                "last_error_at_utc": utc_timestamp(),
                "last_error": str(exc),
            }
        )
    return write_backup_schedule_state(state)


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

    return _run_configured_backup(
        state=state,
        reason=DAILY_BACKUP_REASON,
        checked_at=checked_at,
    )


def run_after_change_backup() -> dict[str, Any]:
    checked_at = utc_timestamp()
    state = read_backup_schedule_state()
    return _run_configured_backup(
        state=state,
        reason=CHANGE_BACKUP_REASON,
        checked_at=checked_at,
    )


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

    title = "Automatic backup sync"
    label = "Active"
    chip_status = "active"
    detail = "Saved changes are backed up automatically while the app is open."
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
    elif status == "success":
        label = "Synced"
    elif status == "warning":
        label = "Local saved"
        chip_status = "pending"
        summary_status = "warning"
        detail = "Automatic local backup sync succeeded, but the external copy needs attention."
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
        detail = "No verified backup has been created today. The app will sync after the next saved change and still checks periodically while open."

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


def after_change_backups_enabled() -> bool:
    disabled = str(os.environ.get(CHANGE_BACKUP_DISABLED_ENV) or "").strip().lower()
    return disabled not in {"1", "true", "yes", "on"}


def request_change_backup(*, reason: str = CHANGE_BACKUP_REASON) -> bool:
    if not after_change_backups_enabled():
        return False

    global _CHANGE_BACKUP_HAS_PENDING_WORK
    with _CHANGE_BACKUP_STATE_LOCK:
        _CHANGE_BACKUP_HAS_PENDING_WORK = True

    try:
        state = read_backup_schedule_state()
        state.update(
            {
                "last_requested_at_utc": utc_timestamp(),
                "last_backup_reason": str(reason or CHANGE_BACKUP_REASON).strip() or CHANGE_BACKUP_REASON,
            }
        )
        write_backup_schedule_state(state)
    except Exception:
        pass

    try:
        start_change_backup_worker()
        _CHANGE_BACKUP_PENDING_EVENT.set()
    except Exception:
        return False
    return True


def start_change_backup_worker() -> None:
    if not after_change_backups_enabled():
        return

    global _CHANGE_BACKUP_THREAD
    with _CHANGE_BACKUP_THREAD_LOCK:
        if _CHANGE_BACKUP_THREAD is not None and _CHANGE_BACKUP_THREAD.is_alive():
            return
        _CHANGE_BACKUP_STOP_EVENT.clear()
        _CHANGE_BACKUP_THREAD = threading.Thread(
            target=_change_backup_worker,
            name="ndhi-after-change-backup",
            daemon=True,
        )
        _CHANGE_BACKUP_THREAD.start()


def stop_change_backup_worker(*, timeout_seconds: float = 5.0, flush_pending: bool = True) -> None:
    _CHANGE_BACKUP_STOP_EVENT.set()
    _CHANGE_BACKUP_PENDING_EVENT.set()
    with _CHANGE_BACKUP_THREAD_LOCK:
        thread = _CHANGE_BACKUP_THREAD
    if thread is not None and thread.is_alive():
        thread.join(timeout=timeout_seconds)
    if flush_pending and _consume_pending_change_backup():
        try:
            run_after_change_backup()
        except Exception:
            pass


def _consume_pending_change_backup() -> bool:
    global _CHANGE_BACKUP_HAS_PENDING_WORK
    with _CHANGE_BACKUP_STATE_LOCK:
        has_pending_work = _CHANGE_BACKUP_HAS_PENDING_WORK
        _CHANGE_BACKUP_HAS_PENDING_WORK = False
    return has_pending_work


def _wait_for_quiet_change_window() -> bool:
    debounce_seconds = positive_env_int(
        "NDHI_AFTER_CHANGE_BACKUP_DEBOUNCE_SECONDS",
        DEFAULT_CHANGE_BACKUP_DEBOUNCE_SECONDS,
    )
    while not _CHANGE_BACKUP_STOP_EVENT.is_set():
        _CHANGE_BACKUP_PENDING_EVENT.clear()
        if _CHANGE_BACKUP_STOP_EVENT.wait(debounce_seconds):
            return False
        if not _CHANGE_BACKUP_PENDING_EVENT.is_set():
            return True
    return False


def _change_backup_worker() -> None:
    global _CHANGE_BACKUP_HAS_PENDING_WORK

    retry_seconds = positive_env_int(
        "NDHI_AFTER_CHANGE_BACKUP_RETRY_SECONDS",
        DEFAULT_CHANGE_BACKUP_RETRY_SECONDS,
    )

    while not _CHANGE_BACKUP_STOP_EVENT.is_set():
        _CHANGE_BACKUP_PENDING_EVENT.wait()
        if _CHANGE_BACKUP_STOP_EVENT.is_set():
            return
        if not _wait_for_quiet_change_window():
            return

        if not _consume_pending_change_backup():
            continue

        try:
            state = run_after_change_backup()
        except Exception:
            state = {"status": "error"}
        if state.get("status") == "skipped" and not _CHANGE_BACKUP_STOP_EVENT.is_set():
            with _CHANGE_BACKUP_STATE_LOCK:
                _CHANGE_BACKUP_HAS_PENDING_WORK = True
            if _CHANGE_BACKUP_STOP_EVENT.wait(retry_seconds):
                return
            _CHANGE_BACKUP_PENDING_EVENT.set()


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
