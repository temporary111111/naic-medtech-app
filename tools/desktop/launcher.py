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
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path


HOST = "127.0.0.1"
DEFAULT_PORT = 8114
APP_PATH = "/records"
PRODUCT_ID = "ndhi-labrecords"
SESSION_SECRET_FILENAME = "session-secret.txt"
CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008


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


def start_server(data_dir: Path, port: int) -> None:
    log_dir = data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / "server.out.log"
    stderr_path = log_dir / "server.err.log"
    creationflags = CREATE_NO_WINDOW | DETACHED_PROCESS if os.name == "nt" else 0
    with stdout_path.open("a", encoding="utf-8") as stdout_file, stderr_path.open("a", encoding="utf-8") as stderr_file:
        subprocess.Popen(
            launcher_command("--serve", "--data-dir", str(data_dir), "--port", str(port)),
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


def open_app_window(port: int) -> None:
    url = app_url(port)
    edge_path = find_edge_executable()
    if edge_path:
        subprocess.Popen([str(edge_path), f"--app={url}", "--start-maximized"], close_fds=True)
        return
    webbrowser.open(url, new=1)


def show_error(message: str) -> None:
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(0, message, "NDHI Laboratory Records", 0x10)
        return
    print(message, file=sys.stderr)


def serve(port: int) -> int:
    import uvicorn
    from naic_builder.main import app

    uvicorn.run(
        app,
        host=HOST,
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
    parser.add_argument("--backup-now", action="store_true", help="Create a verified local backup.")
    parser.add_argument("--verify-backup", metavar="ARCHIVE", help="Verify an existing backup archive.")
    parser.add_argument("--reason", default="manual")
    parser.add_argument("--destination", default="")
    args = parser.parse_args()

    data_dir = data_dir_from_args(args.data_dir)
    prepare_runtime_environment(data_dir)

    if args.serve:
        return serve(args.port)
    if args.backup_now:
        return create_backup(args.reason, args.destination)
    if args.verify_backup:
        return verify_backup(args.verify_backup)

    if not server_is_healthy(args.port):
        start_server(data_dir, args.port)
    if not wait_for_server(args.port):
        show_error(
            "NDHI Laboratory Records could not start.\n\n"
            f"Check the logs under:\n{data_dir / 'logs'}"
        )
        return 1
    open_app_window(args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
