from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
from pathlib import Path
from typing import Any

from .config import CONFIG_DIR


DESKTOP_CONFIG_FILENAME = "desktop.json"
DEFAULT_DESKTOP_PORT = 8114
DEFAULT_NETWORK_MODE = "lan"
DEFAULT_BACKUP_RETENTION_COUNT = 30
MIN_BACKUP_RETENTION_COUNT = 5
MAX_BACKUP_RETENTION_COUNT = 365
FIREWALL_RULE_NAME = "NDHI Laboratory Records LAN"
SUPPORTED_BROWSER_PREFERENCES = ("auto", "edge", "chrome", "default")
SUPPORTED_NETWORK_MODES = ("local", "lan")
BROWSER_PREFERENCE_OPTIONS = [
    {
        "value": "auto",
        "label": "Auto",
        "description": "Try Edge first, then Chrome, then the Windows default browser.",
    },
    {
        "value": "edge",
        "label": "Microsoft Edge",
        "description": "Use Edge app mode when it is installed.",
    },
    {
        "value": "chrome",
        "label": "Google Chrome",
        "description": "Use Chrome app mode when it is installed.",
    },
    {
        "value": "default",
        "label": "Windows default browser",
        "description": "Fallback option. This may open as a normal browser tab.",
    },
]
NETWORK_MODE_OPTIONS = [
    {
        "value": "lan",
        "label": "Same network / LAN",
        "description": "Recommended default. Other clinic PCs on the same Wi-Fi or local network can open the app.",
    },
    {
        "value": "local",
        "label": "This PC only",
        "description": "Only this computer can open the app.",
    },
]


def desktop_config_path() -> Path:
    return CONFIG_DIR / DESKTOP_CONFIG_FILENAME


def normalize_browser_preference(value: Any) -> str:
    preference = str(value or "").strip().lower()
    return preference if preference in SUPPORTED_BROWSER_PREFERENCES else "auto"


def normalize_network_mode(value: Any) -> str:
    mode = str(value or "").strip().lower()
    return mode if mode in SUPPORTED_NETWORK_MODES else DEFAULT_NETWORK_MODE


def normalize_external_backup_dir(value: Any) -> str:
    return str(value or "").strip()


def normalize_backup_retention_count(value: Any) -> int:
    try:
        count = int(value)
    except (TypeError, ValueError):
        count = DEFAULT_BACKUP_RETENTION_COUNT
    return max(MIN_BACKUP_RETENTION_COUNT, min(count, MAX_BACKUP_RETENTION_COUNT))


def default_desktop_settings() -> dict[str, Any]:
    return {
        "browser_preference": "auto",
        "network_mode": DEFAULT_NETWORK_MODE,
        "external_backup_dir": "",
        "backup_retention_count": DEFAULT_BACKUP_RETENTION_COUNT,
    }


def read_desktop_settings() -> dict[str, Any]:
    config_path = desktop_config_path()
    if not config_path.exists():
        return default_desktop_settings()
    try:
        raw_config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default_desktop_settings()
    if not isinstance(raw_config, dict):
        return default_desktop_settings()
    return {
        "browser_preference": normalize_browser_preference(raw_config.get("browser_preference")),
        "network_mode": normalize_network_mode(raw_config.get("network_mode")),
        "external_backup_dir": normalize_external_backup_dir(raw_config.get("external_backup_dir")),
        "backup_retention_count": normalize_backup_retention_count(raw_config.get("backup_retention_count")),
    }


def save_desktop_settings(
    *,
    browser_preference: str,
    network_mode: str,
    external_backup_dir: str = "",
    backup_retention_count: Any = DEFAULT_BACKUP_RETENTION_COUNT,
) -> dict[str, Any]:
    settings = {
        "browser_preference": normalize_browser_preference(browser_preference),
        "network_mode": normalize_network_mode(network_mode),
        "external_backup_dir": normalize_external_backup_dir(external_backup_dir),
        "backup_retention_count": normalize_backup_retention_count(backup_retention_count),
    }
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    desktop_config_path().write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    return settings


def _browser_path(candidates: list[Path], command_name: str) -> str:
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    path = shutil.which(command_name)
    return path or ""


def detect_desktop_browsers() -> dict[str, dict[str, str | bool]]:
    edge_path = _browser_path(
        [
            Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            Path(os.environ.get("ProgramFiles", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        ],
        "msedge",
    )
    chrome_path = _browser_path(
        [
            Path(os.environ.get("ProgramFiles", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
            Path(os.environ.get("ProgramFiles(x86)", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        ],
        "chrome",
    )
    return {
        "edge": {
            "label": "Microsoft Edge",
            "installed": bool(edge_path),
            "path": edge_path,
        },
        "chrome": {
            "label": "Google Chrome",
            "installed": bool(chrome_path),
            "path": chrome_path,
        },
        "default": {
            "label": "Windows default browser",
            "installed": True,
            "path": "Controlled by Windows",
        },
    }


def detect_firewall_rule() -> dict[str, str]:
    if os.name != "nt":
        return {
            "status": "unknown",
            "label": "Not checked",
            "detail": "Firewall status is only checked on Windows.",
        }
    try:
        result = subprocess.run(
            [
                "netsh",
                "advfirewall",
                "firewall",
                "show",
                "rule",
                f"name={FIREWALL_RULE_NAME}",
            ],
            capture_output=True,
            check=False,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {
            "status": "unknown",
            "label": "Not checked",
            "detail": "Windows Firewall status could not be checked.",
        }

    output = f"{result.stdout}\n{result.stderr}"
    if result.returncode != 0 or "No rules match" in output:
        return {
            "status": "warning",
            "label": "Needs check",
            "detail": "The installer firewall rule was not detected.",
        }
    if "Enabled:" in output and "Yes" not in output:
        return {
            "status": "warning",
            "label": "Disabled",
            "detail": "The firewall rule exists but may be disabled.",
        }
    return {
        "status": "ready",
        "label": "Ready",
        "detail": "Firewall rule is installed for same-network access.",
    }


def desktop_runtime_status(settings: dict[str, str] | None = None) -> dict[str, dict[str, str]]:
    resolved_settings = settings or read_desktop_settings()
    network_mode = normalize_network_mode(resolved_settings.get("network_mode"))
    runtime_mode = normalize_network_mode(os.environ.get("NDHI_LABRECORDS_NETWORK_MODE"))
    bind_host = str(os.environ.get("NDHI_LABRECORDS_BIND_HOST") or "")

    if network_mode != "lan":
        network_status = {
            "status": "disabled",
            "label": "This PC only",
            "detail": "Same-network access is off.",
        }
    elif runtime_mode == "lan" and bind_host == "0.0.0.0":
        network_status = {
            "status": "ready",
            "label": "Ready",
            "detail": "This server is accepting same-network connections.",
        }
    else:
        network_status = {
            "status": "warning",
            "label": "Restart needed",
            "detail": "Restart the desktop app/server so LAN mode can take effect.",
        }

    return {
        "network": network_status,
        "firewall": detect_firewall_rule(),
        "host": {
            "status": "ready",
            "label": local_hostname(),
            "detail": "Keep this host PC turned on while other clinic PCs use the app.",
        },
        "port": {
            "status": "ready",
            "label": str(DEFAULT_DESKTOP_PORT),
            "detail": "Default app port. Staff should use the links below instead of typing this manually.",
        },
    }


def local_hostname() -> str:
    return (os.environ.get("COMPUTERNAME") or socket.gethostname() or "this-computer").strip()


def local_lan_ipv4_addresses() -> list[str]:
    addresses: set[str] = set()
    hostnames = {local_hostname(), socket.gethostname()}
    for hostname in hostnames:
        try:
            for result in socket.getaddrinfo(hostname, None, socket.AF_INET):
                address = result[4][0]
                if address and not address.startswith("127."):
                    addresses.add(address)
        except socket.gaierror:
            continue

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("8.8.8.8", 80))
            address = probe.getsockname()[0]
            if address and not address.startswith("127."):
                addresses.add(address)
    except OSError:
        pass

    return sorted(addresses)


def lan_access_details(port: int = DEFAULT_DESKTOP_PORT) -> dict[str, Any]:
    hostname = local_hostname()
    ip_addresses = local_lan_ipv4_addresses()
    ip_urls = [f"http://{address}:{port}" for address in ip_addresses]
    qr_url = ip_urls[0] if ip_urls else f"http://{hostname}:{port}"
    return {
        "hostname": hostname,
        "port": port,
        "hostname_url": f"http://{hostname}:{port}",
        "ip_urls": ip_urls,
        "has_ip_fallback": bool(ip_addresses),
        "qr_url": qr_url,
        "qr_url_label": "IP fallback link" if ip_urls else "Hostname link",
    }
