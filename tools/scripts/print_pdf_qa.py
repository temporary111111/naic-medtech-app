from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from print_record_qa import (  # noqa: E402
    DEFAULT_QA_SLUGS,
    create_completed_print_qa_record,
    first_active_user_id,
    restore_runtime_db,
    signed_session_cookie_value,
    snapshot_runtime_db,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate browser PDFs for temporary actual records and verify page count.",
    )
    parser.add_argument("slugs", nargs="*", help="Form slugs to test.")
    parser.add_argument("--all", action="store_true", help="Test all current forms.")
    parser.add_argument("--max-pages", type=int, default=1, help="Maximum acceptable PDF page count.")
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "output" / "print-qa"),
        help="Directory for generated PDFs and report JSON.",
    )
    parser.add_argument(
        "--keep-output",
        action="store_true",
        help="Keep previous PDFs/logs in the output directory instead of cleaning generated QA files first.",
    )
    parser.add_argument(
        "--keep-records",
        action="store_true",
        help="Do not restore the runtime DB after the run.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Temporary local server host.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="Temporary local server port. Defaults to a free port.",
    )
    return parser.parse_args()


def load_slugs(use_all: bool, requested_slugs: list[str]) -> list[str]:
    if not use_all:
        return requested_slugs or DEFAULT_QA_SLUGS

    from naic_builder.database import SessionLocal
    from naic_builder.models import FormDefinition

    with SessionLocal() as session:
        return [
            slug
            for slug in session.scalars(select(FormDefinition.slug).order_by(FormDefinition.name)).all()
        ]


def find_free_port(host: str) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def wait_for_server(base_url: str, process: subprocess.Popen, timeout_seconds: float = 25.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    health_url = f"{base_url}/api/health"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Temporary server exited early with code {process.returncode}.")
        try:
            with urlopen(health_url, timeout=1.0) as response:
                if response.status == 200:
                    return
        except URLError:
            time.sleep(0.25)
    raise TimeoutError(f"Temporary server did not become ready: {health_url}")


def start_server(host: str, port: int, output_dir: Path) -> tuple[subprocess.Popen, str]:
    actual_port = port or find_free_port(host)
    base_url = f"http://{host}:{actual_port}"
    stdout_path = output_dir / "uvicorn.out.log"
    stderr_path = output_dir / "uvicorn.err.log"
    stdout_file = stdout_path.open("w", encoding="utf-8")
    stderr_file = stderr_path.open("w", encoding="utf-8")
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "naic_builder.main:app",
        "--app-dir",
        str(ROOT / "app"),
        "--host",
        host,
        "--port",
        str(actual_port),
        "--log-level",
        "warning",
    ]
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        stdout=stdout_file,
        stderr=stderr_file,
    )
    process._naic_log_files = (stdout_file, stderr_file)  # type: ignore[attr-defined]
    wait_for_server(base_url, process)
    return process, base_url


def stop_server(process: subprocess.Popen | None) -> None:
    if process is None:
        return
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=8)
    for log_file in getattr(process, "_naic_log_files", ()):
        log_file.close()


def write_storage_state(path: Path, base_url: str, user_id: int) -> None:
    host = urlparse(base_url).hostname or "127.0.0.1"
    state = {
        "cookies": [
            {
                "name": "session",
                "value": signed_session_cookie_value(user_id),
                "domain": host,
                "path": "/",
                "expires": -1,
                "httpOnly": False,
                "secure": False,
                "sameSite": "Lax",
            }
        ],
        "origins": [],
    }
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def count_pdf_pages(path: Path) -> int:
    data = path.read_bytes()
    return len(re.findall(rb"/Type\s*/Page\b", data))


def playwright_executable() -> str:
    executable = shutil.which("npx.cmd") if os.name == "nt" else shutil.which("npx")
    executable = executable or shutil.which("npx")
    if not executable:
        raise RuntimeError("npx was not found. Install Node.js/npm before running browser PDF QA.")
    return executable


def generate_pdf(
    *,
    npx: str,
    url: str,
    output_path: Path,
    storage_state_path: Path,
) -> subprocess.CompletedProcess[str]:
    command = [
        npx,
        "--yes",
        "playwright",
        "pdf",
        "--paper-format",
        "A4",
        "--wait-for-selector",
        ".print-page",
        "--wait-for-timeout",
        "250",
        "--timeout",
        "30000",
        "--load-storage",
        str(storage_state_path),
        url,
        str(output_path),
    ]
    return subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=60,
    )


def safe_filename(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", value).strip("_") or "record"


def clean_output_dir(output_dir: Path) -> None:
    for pattern in ("*.pdf", "report.json", "uvicorn.out.log", "uvicorn.err.log", ".storage-state.json"):
        for path in output_dir.glob(pattern):
            if path.is_file():
                path.unlink()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    if not args.keep_output:
        clean_output_dir(output_dir)

    snapshot = None if args.keep_records else snapshot_runtime_db()
    server: subprocess.Popen | None = None
    storage_state_path = output_dir / ".storage-state.json"
    records: list[dict[str, Any]] = []
    report: dict[str, Any] = {
        "max_pages": args.max_pages,
        "results": [],
        "failures": [],
    }

    try:
        actor_user_id = first_active_user_id()
        if actor_user_id is None:
            raise RuntimeError("No active user found. Create or activate an account before PDF QA.")

        slugs = load_slugs(args.all, args.slugs)
        records = [
            create_completed_print_qa_record(slug, actor_user_id=actor_user_id)
            for slug in slugs
        ]

        server, base_url = start_server(args.host, args.port, output_dir)
        write_storage_state(storage_state_path, base_url, actor_user_id)
        npx = playwright_executable()

        for record in records:
            slug = str(record["slug"])
            record_id = int(record["record_id"])
            pdf_path = output_dir / f"{safe_filename(slug)}-{record_id}.pdf"
            url = f"{base_url}/records/{record_id}/print"
            completed = generate_pdf(
                npx=npx,
                url=url,
                output_path=pdf_path,
                storage_state_path=storage_state_path,
            )
            if completed.returncode != 0:
                message = (completed.stderr or completed.stdout or "Playwright PDF failed.").strip()
                report["failures"].append({"slug": slug, "error": message})
                print(f"{slug}\tERROR\t{message}", file=sys.stderr)
                continue

            pages = count_pdf_pages(pdf_path)
            result = {
                "slug": slug,
                "record_id": record_id,
                "record_key": record.get("record_key"),
                "fit": record.get("fit"),
                "fit_label": record.get("fit_label"),
                "pages": pages,
                "pdf": str(pdf_path),
            }
            report["results"].append(result)
            print(
                "\t".join(
                    [
                        slug,
                        str(record_id),
                        str(record.get("record_key")),
                        str(record.get("fit")),
                        f"pages={pages}",
                        str(pdf_path),
                    ]
                )
            )
            if pages > args.max_pages:
                report["failures"].append(
                    {
                        "slug": slug,
                        "pages": pages,
                        "max_pages": args.max_pages,
                    }
                )

        report["summary"] = {
            "tested": len(records),
            "passed": len(records) - len(report["failures"]),
            "failed": len(report["failures"]),
        }
        (output_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        return 1 if report["failures"] else 0
    finally:
        stop_server(server)
        if storage_state_path.exists():
            storage_state_path.unlink()
        if snapshot is not None:
            restore_runtime_db(snapshot)


if __name__ == "__main__":
    raise SystemExit(main())
