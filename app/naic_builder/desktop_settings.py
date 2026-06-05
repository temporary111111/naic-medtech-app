from __future__ import annotations

import json
import os
import shutil
import socket
from pathlib import Path
from typing import Any

from .config import CONFIG_DIR


DESKTOP_CONFIG_FILENAME = "desktop.json"
DEFAULT_DESKTOP_PORT = 8114
DEFAULT_NETWORK_MODE = "lan"
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


def read_desktop_settings() -> dict[str, str]:
    config_path = desktop_config_path()
    if not config_path.exists():
        return {"browser_preference": "auto", "network_mode": DEFAULT_NETWORK_MODE}
    try:
        raw_config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"browser_preference": "auto", "network_mode": DEFAULT_NETWORK_MODE}
    if not isinstance(raw_config, dict):
        return {"browser_preference": "auto", "network_mode": DEFAULT_NETWORK_MODE}
    return {
        "browser_preference": normalize_browser_preference(raw_config.get("browser_preference")),
        "network_mode": normalize_network_mode(raw_config.get("network_mode")),
    }


def save_desktop_settings(*, browser_preference: str, network_mode: str) -> dict[str, str]:
    settings = {
        "browser_preference": normalize_browser_preference(browser_preference),
        "network_mode": normalize_network_mode(network_mode),
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
    return {
        "hostname": hostname,
        "port": port,
        "hostname_url": f"http://{hostname}:{port}",
        "ip_urls": [f"http://{address}:{port}" for address in ip_addresses],
        "has_ip_fallback": bool(ip_addresses),
    }
