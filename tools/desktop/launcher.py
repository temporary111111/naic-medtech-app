from __future__ import annotations

import argparse
import ctypes
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path


HOST = "127.0.0.1"
LAN_BIND_HOST = "0.0.0.0"
DEFAULT_PORT = 8114
APP_PATH = "/records"
PRODUCT_ID = "ndhi-labrecords"
SESSION_SECRET_FILENAME = "session-secret.txt"
DESKTOP_CONFIG_FILENAME = "desktop.json"
BROWSER_PREFERENCE_ENV = "NDHI_LABRECORDS_BROWSER"
NETWORK_MODE_ENV = "NDHI_LABRECORDS_NETWORK_MODE"
SUPPORTED_BROWSERS = {"auto", "edge", "chrome", "default"}
SUPPORTED_NETWORK_MODES = {"local", "lan"}
DEFAULT_NETWORK_MODE = "lan"
CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008
_PROCESS_STREAMS = []


def default_data_dir() -> Path:
    program_data = os.environ.get("ProgramData") or os.environ.get("PROGRAMDATA")
    if program_data:
        return Path(program_data) / "NDHI" / "LabRecords"
    return Path.home() / "AppData" / "Local" / "NDHI" / "LabRecords"


def data_dir_from_args(raw_path: str) -> Path:
    return Path(raw_path).expanduser().resolve() if raw_path else default_data_dir().resolve()


def prepare_runtime_environment(data_dir: Path) -> None:
    for relative_path in (
        "database",
        "uploads",
        "uploads/clinic",
        "uploads/records",
        "uploads/signatories",
        "uploads/users",
        "backups",
        "logs",
        "config",
    ):
        (data_dir / relative_path).mkdir(parents=True, exist_ok=True)

    secret_path = data_dir / "config" / SESSION_SECRET_FILENAME
    if not secret_path.exists():
        secret_path.write_text(secrets.token_urlsafe(48), encoding="utf-8")

    os.environ["NDHI_LABRECORDS_DATA_DIR"] = str(data_dir)
    os.environ["NDHI_SESSION_SECRET"] = secret_path.read_text(encoding="utf-8").strip()


def desktop_config_path(data_dir: Path) -> Path:
    return data_dir / "config" / DESKTOP_CONFIG_FILENAME


def normalize_browser_preference(value: str | None) -> str:
    preference = (value or "").strip().lower()
    return preference if preference in SUPPORTED_BROWSERS else "auto"


def normalize_network_mode(value: str | None) -> str:
    mode = (value or "").strip().lower()
    return mode if mode in SUPPORTED_NETWORK_MODES else DEFAULT_NETWORK_MODE


def read_desktop_config(data_dir: Path) -> dict[str, str]:
    config_path = desktop_config_path(data_dir)
    if not config_path.exists():
        return {}
    try:
        raw_config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        append_startup_log(data_dir, f"Ignoring unreadable desktop config: {config_path}")
        return {}
    if not isinstance(raw_config, dict):
        append_startup_log(data_dir, f"Ignoring invalid desktop config: {config_path}")
        return {}
    return {str(key): str(value) for key, value in raw_config.items()}


def browser_preference_from_config(data_dir: Path, override: str = "") -> str:
    if override:
        return normalize_browser_preference(override)
    env_preference = normalize_browser_preference(os.environ.get(BROWSER_PREFERENCE_ENV))
    if os.environ.get(BROWSER_PREFERENCE_ENV):
        return env_preference
    return normalize_browser_preference(read_desktop_config(data_dir).get("browser_preference"))


def network_mode_from_config(data_dir: Path, override: str = "") -> str:
    if override:
        return normalize_network_mode(override)
    env_mode = normalize_network_mode(os.environ.get(NETWORK_MODE_ENV))
    if os.environ.get(NETWORK_MODE_ENV):
        return env_mode
    return normalize_network_mode(read_desktop_config(data_dir).get("network_mode"))


def bind_host_for_network_mode(network_mode: str) -> str:
    return LAN_BIND_HOST if normalize_network_mode(network_mode) == "lan" else HOST


def append_startup_log(data_dir: Path, message: str) -> None:
    log_path = data_dir / "logs" / "startup.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(f"[{timestamp}] {message}\n")


def ensure_process_streams(data_dir: Path) -> None:
    for attribute, filename in (("stdout", "launcher.out.log"), ("stderr", "launcher.err.log")):
        if getattr(sys, attribute) is not None:
            continue
        stream = (data_dir / "logs" / filename).open("a", encoding="utf-8", buffering=1)
        setattr(sys, attribute, stream)
        _PROCESS_STREAMS.append(stream)


def app_url(port: int) -> str:
    return f"http://{HOST}:{port}{APP_PATH}"


def health_url(port: int) -> str:
    return f"http://{HOST}:{port}/api/health"


def server_is_healthy(port: int) -> bool:
    try:
        with urllib.request.urlopen(health_url(port), timeout=1.5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return (
            response.status == 200
            and payload.get("status") == "ok"
            and payload.get("product_id") == PRODUCT_ID
        )
    except (OSError, ValueError, urllib.error.URLError):
        return False


def wait_for_server(port: int, *, timeout_seconds: int = 90) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if server_is_healthy(port):
            return True
        time.sleep(0.35)
    return False


def launcher_command(*args: str) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, *args]
    return [sys.executable, str(Path(__file__).resolve()), *args]


def start_server(data_dir: Path, port: int, bind_host: str, network_mode: str) -> None:
    log_dir = data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / "server.out.log"
    stderr_path = log_dir / "server.err.log"
    creationflags = CREATE_NO_WINDOW | DETACHED_PROCESS if os.name == "nt" else 0
    with stdout_path.open("a", encoding="utf-8") as stdout_file, stderr_path.open("a", encoding="utf-8") as stderr_file:
        subprocess.Popen(
            launcher_command(
                "--serve",
                "--data-dir",
                str(data_dir),
                "--port",
                str(port),
                "--host",
                bind_host,
                "--network-mode",
                network_mode,
            ),
            stdin=subprocess.DEVNULL,
            stdout=stdout_file,
            stderr=stderr_file,
            close_fds=True,
            creationflags=creationflags,
        )


def find_edge_executable() -> Path | None:
    candidate_paths = [
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
    ]
    for candidate in candidate_paths:
        if candidate.is_file():
            return candidate
    edge_on_path = shutil.which("msedge")
    return Path(edge_on_path) if edge_on_path else None


def find_chrome_executable() -> Path | None:
    candidate_paths = [
        Path(os.environ.get("ProgramFiles", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
    ]
    for candidate in candidate_paths:
        if candidate.is_file():
            return candidate
    chrome_on_path = shutil.which("chrome")
    return Path(chrome_on_path) if chrome_on_path else None


def open_with_browser(browser: str, url: str) -> bool:
    if browser == "edge":
        browser_path = find_edge_executable()
    elif browser == "chrome":
        browser_path = find_chrome_executable()
    else:
        return False
    if not browser_path:
        return False
    subprocess.Popen([str(browser_path), f"--app={url}", "--start-maximized"], close_fds=True)
    return True


def browser_attempt_order(preference: str) -> list[str]:
    if preference == "edge":
        return ["edge", "chrome"]
    if preference == "chrome":
        return ["chrome", "edge"]
    if preference == "default":
        return []
    return ["edge", "chrome"]


def open_app_window(port: int, data_dir: Path, browser_preference: str) -> None:
    url = app_url(port)
    preference = normalize_browser_preference(browser_preference)
    for browser in browser_attempt_order(preference):
        if open_with_browser(browser, url):
            append_startup_log(data_dir, f"Opened desktop app using {browser}.")
            return
    append_startup_log(data_dir, "Opening desktop app using default browser fallback.")
    webbrowser.open(url, new=1)


def show_error(message: str) -> None:
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(0, message, "NDHI Laboratory Records", 0x10)
        return
    print(message, file=sys.stderr)


def serve(port: int, host: str, network_mode: str) -> int:
    data_dir = data_dir_from_args(os.environ.get("NDHI_LABRECORDS_DATA_DIR", ""))
    os.environ["NDHI_LABRECORDS_BIND_HOST"] = host
    os.environ[NETWORK_MODE_ENV] = normalize_network_mode(network_mode)
    append_startup_log(data_dir, f"Importing Uvicorn for local server on {host}:{port}.")
    import uvicorn

    append_startup_log(data_dir, "Importing FastAPI application.")
    from naic_builder.main import app

    append_startup_log(data_dir, "Starting Uvicorn event loop.")
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=False,
    )
    return 0


def create_backup(reason: str, destination: str) -> int:
    from naic_builder.backup import create_verified_backup, verify_backup_archive

    archive_path = create_verified_backup(
        reason=reason,
        destination_dir=Path(destination).expanduser().resolve() if destination else None,
    )
    print(json.dumps(verify_backup_archive(archive_path), indent=2))
    return 0


def verify_backup(archive: str) -> int:
    from naic_builder.backup import verify_backup_archive

    print(json.dumps(verify_backup_archive(Path(archive)), indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="NDHI Laboratory Records local desktop launcher.")
    parser.add_argument("--data-dir", default=os.environ.get("NDHI_LABRECORDS_DATA_DIR", ""))
    parser.add_argument("--port", type=int, default=int(os.environ.get("NDHI_LABRECORDS_PORT", DEFAULT_PORT)))
    parser.add_argument("--serve", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--host", default="", help=argparse.SUPPRESS)
    parser.add_argument("--network-mode", choices=sorted(SUPPORTED_NETWORK_MODES), default="", help=argparse.SUPPRESS)
    parser.add_argument("--backup-now", action="store_true", help="Create a verified local backup.")
    parser.add_argument("--verify-backup", metavar="ARCHIVE", help="Verify an existing backup archive.")
    parser.add_argument("--browser", choices=sorted(SUPPORTED_BROWSERS), default="")
    parser.add_argument("--reason", default="manual")
    parser.add_argument("--destination", default="")
    args = parser.parse_args()

    data_dir = data_dir_from_args(args.data_dir)
    prepare_runtime_environment(data_dir)
    ensure_process_streams(data_dir)
    browser_preference = browser_preference_from_config(data_dir, args.browser)
    network_mode = network_mode_from_config(data_dir, args.network_mode)
    bind_host = args.host.strip() or bind_host_for_network_mode(network_mode)
    append_startup_log(data_dir, f"Launcher entered mode: {'serve' if args.serve else 'backup' if args.backup_now else 'verify' if args.verify_backup else 'desktop'}.")

    if args.serve:
        return serve(args.port, bind_host, network_mode)
    if args.backup_now:
        return create_backup(args.reason, args.destination)
    if args.verify_backup:
        return verify_backup(args.verify_backup)

    if not server_is_healthy(args.port):
        start_server(data_dir, args.port, bind_host, network_mode)
    if not wait_for_server(args.port):
        show_error(
            "NDHI Laboratory Records could not start.\n\n"
            f"Check the logs under:\n{data_dir / 'logs'}"
        )
        return 1
    open_app_window(args.port, data_dir, browser_preference)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        raw_data_dir = os.environ.get("NDHI_LABRECORDS_DATA_DIR", "")
        if raw_data_dir:
            try:
                data_dir = data_dir_from_args(raw_data_dir)
                append_startup_log(data_dir, "Unhandled launcher error:\n" + traceback.format_exc())
            except OSError:
                pass
        raise
