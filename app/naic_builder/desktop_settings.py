from __future__ import annotations

import base64
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from .config import CONFIG_DIR, DATA_RUNTIME_DIR


DESKTOP_CONFIG_FILENAME = "desktop.json"
DEFAULT_DESKTOP_PORT = 8114
DEFAULT_NETWORK_MODE = "lan"
DEFAULT_BACKUP_RETENTION_COUNT = 30
MIN_BACKUP_RETENTION_COUNT = 5
MAX_BACKUP_RETENTION_COUNT = 365
FIREWALL_RULE_NAME = "NDHI Laboratory Records LAN"
FIREWALL_PROFILES = ("Private", "Domain", "Public")
SUPPORTED_BROWSER_PREFERENCES = ("auto", "edge", "chrome", "default")
SUPPORTED_NETWORK_MODES = ("local", "lan")
CREATE_NO_WINDOW = 0x08000000
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


def _powershell_command() -> str:
    return shutil.which("powershell.exe") or shutil.which("powershell") or "powershell.exe"


def _hidden_subprocess_creationflags() -> int:
    return CREATE_NO_WINDOW if os.name == "nt" else 0


def _powershell_single_quote(value: Any) -> str:
    return "'" + str(value or "").replace("'", "''") + "'"


def _command_line_quote(value: Any) -> str:
    return '"' + str(value or "").replace('"', '\\"') + '"'


def _encoded_powershell(script: str) -> str:
    return base64.b64encode(script.encode("utf-16le")).decode("ascii")


def _clean_powershell_error(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.startswith("#< CLIXML") or "<Objs " in text or "Preparing modules for first use" in text:
        return ""
    return text[-600:]


def _firewall_profiles_ready(profile_text: Any) -> bool:
    profiles = str(profile_text or "").lower()
    if "any" in profiles:
        return True
    return all(profile.lower() in profiles for profile in FIREWALL_PROFILES)


def _netsh_rule_blocks(output: str) -> list[str]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in str(output or "").splitlines():
        if line.strip().lower().startswith("rule name:") and current:
            blocks.append(current)
            current = []
        current.append(line)
    if current:
        blocks.append(current)
    return ["\n".join(block) for block in blocks if any(line.strip() for line in block)]


def _netsh_value(output: str, label: str) -> str:
    prefix = f"{label}:".lower()
    for line in str(output or "").splitlines():
        stripped = line.strip()
        if stripped.lower().startswith(prefix):
            return stripped.split(":", 1)[1].strip()
    return ""


def _netsh_firewall_rule_status(output: str) -> dict[str, str]:
    if "No rules match" in output:
        return {
            "status": "warning",
            "label": "Needs check",
            "detail": "The installer firewall rule was not detected.",
        }

    fallback_warning = {
        "status": "warning",
        "label": "Needs check",
        "detail": "The firewall rule exists, but Windows profile/local-subnet details could not be fully verified.",
    }

    for block in _netsh_rule_blocks(output):
        enabled = _netsh_value(block, "Enabled").lower()
        direction = _netsh_value(block, "Direction").lower()
        profiles = _netsh_value(block, "Profiles")
        remote_ip = _netsh_value(block, "RemoteIP").lower()
        protocol = _netsh_value(block, "Protocol").lower()
        local_port = _netsh_value(block, "LocalPort").lower()
        action = _netsh_value(block, "Action").lower()

        if enabled and enabled != "yes":
            fallback_warning = {
                "status": "warning",
                "label": "Disabled",
                "detail": "The firewall rule exists but is disabled.",
            }
            continue
        if direction and direction not in {"in", "inbound"}:
            continue
        if action and action != "allow":
            continue
        if protocol and protocol != "tcp":
            fallback_warning = {
                "status": "warning",
                "label": "Needs repair",
                "detail": "The firewall rule exists, but it is not configured for TCP.",
            }
            continue
        if local_port and local_port not in {str(DEFAULT_DESKTOP_PORT), "any"}:
            fallback_warning = {
                "status": "warning",
                "label": "Needs repair",
                "detail": "The firewall rule exists, but it does not match the app port.",
            }
            continue
        if remote_ip and "localsubnet" not in remote_ip:
            fallback_warning = {
                "status": "warning",
                "label": "Needs repair",
                "detail": "The firewall rule is not limited to the local clinic network.",
            }
            continue
        if profiles and not _firewall_profiles_ready(profiles):
            fallback_warning = {
                "status": "warning",
                "label": "Limited",
                "detail": "The firewall rule does not cover every Windows network profile. Repair it if sharing fails.",
            }
            continue
        if enabled == "yes" and remote_ip and protocol == "tcp" and local_port == str(DEFAULT_DESKTOP_PORT):
            return {
                "status": "ready",
                "label": "Ready",
                "detail": "Firewall rule is installed for same-network access.",
            }

    return fallback_warning


def _current_program_path() -> str:
    candidate = Path(sys.executable or "")
    return str(candidate) if candidate.is_file() else ""


def _lan_firewall_repair_script_path() -> Path:
    return CONFIG_DIR / "repair-lan-firewall.ps1"


def _lan_firewall_repair_result_path() -> Path:
    return CONFIG_DIR / "repair-lan-firewall-result.json"


def _runtime_permissions_repair_script_path() -> Path:
    return Path(tempfile.gettempdir()) / "ndhi-repair-runtime-permissions.ps1"


def _runtime_permissions_repair_result_path() -> Path:
    return Path(tempfile.gettempdir()) / "ndhi-repair-runtime-permissions-result.json"


def write_lan_firewall_repair_script() -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    script_path = _lan_firewall_repair_script_path()
    script_path.write_text(
        """[CmdletBinding()]
param(
    [int]$Port = 8114,
    [string]$RuleName = "NDHI Laboratory Records LAN",
    [string]$ProgramPath = "",
    [string]$ResultPath = ""
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function Write-RepairResult {
    param(
        [string]$Status,
        [string]$Message
    )

    if (-not $ResultPath) {
        return
    }

    $payload = [ordered]@{
        status = $Status
        label = if ($Status -eq "ready") { "Ready" } else { "Needs attention" }
        detail = $Message
        rule_name = $RuleName
        port = $Port
        profiles = "Private, Domain, Public"
        remote_address = "LocalSubnet"
        timestamp = (Get-Date).ToString("o")
    }

    $parent = Split-Path -Parent $ResultPath
    if ($parent) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
    $payload | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $ResultPath -Encoding UTF8
}

try {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Windows did not grant administrator permission."
    }

    $existingRule = Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue
    if ($existingRule) {
        $existingRule | Remove-NetFirewallRule
    }

    $rule = @{
        DisplayName = $RuleName
        Direction = "Inbound"
        Action = "Allow"
        Protocol = "TCP"
        LocalPort = $Port
        Profile = "Private", "Domain", "Public"
        RemoteAddress = "LocalSubnet"
        Description = "Allows trusted clinic LAN devices to open NDHI Laboratory Records on TCP port $Port."
    }
    if ($ProgramPath -and (Test-Path -LiteralPath $ProgramPath -PathType Leaf)) {
        $rule.Program = $ProgramPath
    }

    New-NetFirewallRule @rule | Out-Null
    Write-RepairResult -Status "ready" -Message "Same-network Windows Firewall access is repaired for this PC."
    exit 0
} catch {
    Write-RepairResult -Status "error" -Message $_.Exception.Message
    exit 1
}
""",
        encoding="utf-8",
    )
    return script_path


def write_runtime_permissions_repair_script() -> Path:
    script_path = _runtime_permissions_repair_script_path()
    script_path.write_text(
        """[CmdletBinding()]
param(
    [string]$RuntimePath = "",
    [string]$ResultPath = ""
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function Write-RepairResult {
    param(
        [string]$Status,
        [string]$Message
    )

    if (-not $ResultPath) {
        return
    }

    $payload = [ordered]@{
        status = $Status
        label = if ($Status -eq "ready") { "Ready" } else { "Needs attention" }
        detail = $Message
        runtime_path = $RuntimePath
        timestamp = (Get-Date).ToString("o")
    }

    $parent = Split-Path -Parent $ResultPath
    if ($parent) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
    $payload | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $ResultPath -Encoding UTF8
}

try {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Windows did not grant administrator permission."
    }
    if (-not $RuntimePath) {
        throw "Runtime data folder path is missing."
    }

    New-Item -ItemType Directory -Force -Path $RuntimePath | Out-Null
    foreach ($child in @("database", "uploads", "uploads\\clinic", "uploads\\records", "uploads\\signatories", "uploads\\users", "backups", "logs", "config")) {
        New-Item -ItemType Directory -Force -Path (Join-Path $RuntimePath $child) | Out-Null
    }

    $grant = "*S-1-5-32-545:(OI)(CI)M"
    & icacls.exe $RuntimePath /grant $grant /T /C | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Windows could not repair the data folder permissions."
    }

    Write-RepairResult -Status "ready" -Message "Data folder access is repaired for normal app use."
    exit 0
} catch {
    Write-RepairResult -Status "error" -Message $_.Exception.Message
    exit 1
}
""",
        encoding="utf-8",
    )
    return script_path


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
            creationflags=_hidden_subprocess_creationflags(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return {
            "status": "unknown",
            "label": "Not checked",
            "detail": "Windows Firewall status could not be checked.",
        }

    output = f"{result.stdout}\n{result.stderr}"
    if result.returncode != 0:
        return {
            "status": "warning",
            "label": "Needs check",
            "detail": "The installer firewall rule was not detected.",
        }
    return _netsh_firewall_rule_status(output)


def detect_runtime_permissions() -> dict[str, str]:
    runtime_path = DATA_RUNTIME_DIR.expanduser()
    probe_dir: Path | None = None
    try:
        runtime_path.mkdir(parents=True, exist_ok=True)
        probe_dir = runtime_path / f".permission-check-{os.getpid()}-{time.time_ns()}"
        probe_file = probe_dir / "write-delete-check.txt"
        probe_dir.mkdir(parents=True, exist_ok=False)
        probe_file.write_text("ok", encoding="utf-8")
        probe_file.unlink()
        probe_dir.rmdir()
    except PermissionError:
        return {
            "status": "warning",
            "label": "Repair needed",
            "detail": "Windows is blocking normal write/delete access to the app data folder.",
        }
    except OSError as exc:
        return {
            "status": "warning",
            "label": "Needs check",
            "detail": f"Data folder access could not be fully checked: {exc}",
        }
    finally:
        if probe_dir is not None and probe_dir.exists():
            try:
                shutil.rmtree(probe_dir)
            except OSError:
                pass
    return {
        "status": "ready",
        "label": "Ready",
        "detail": "Normal app data, backup, and restore access is available.",
    }


def repair_lan_firewall_rule(*, port: int = DEFAULT_DESKTOP_PORT, program_path: str = "") -> dict[str, str]:
    if os.name != "nt":
        return {
            "status": "unknown",
            "label": "Not available",
            "detail": "LAN firewall repair is only available on Windows.",
        }

    script_path = write_lan_firewall_repair_script()
    result_path = _lan_firewall_repair_result_path()
    if result_path.exists():
        try:
            result_path.unlink()
        except OSError:
            pass

    resolved_program_path = str(program_path or _current_program_path())
    arguments = [
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        "-Port",
        str(port),
        "-RuleName",
        FIREWALL_RULE_NAME,
        "-ProgramPath",
        resolved_program_path,
        "-ResultPath",
        str(result_path),
    ]
    argument_line = " ".join(_command_line_quote(argument) for argument in arguments)
    start_process_script = (
        "$ProgressPreference = 'SilentlyContinue'; "
        f"$argumentLine = {_powershell_single_quote(argument_line)}; "
        "Start-Process -FilePath 'powershell.exe' -ArgumentList $argumentLine -Verb RunAs -Wait -WindowStyle Hidden"
    )

    try:
        result = subprocess.run(
            [
                _powershell_command(),
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-EncodedCommand",
                _encoded_powershell(start_process_script),
            ],
            capture_output=True,
            check=False,
            text=True,
            timeout=180,
            creationflags=_hidden_subprocess_creationflags(),
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "warning",
            "label": "Still waiting",
            "detail": "Windows permission did not finish. Try Repair again and approve the prompt.",
        }
    except OSError:
        return {
            "status": "error",
            "label": "Repair failed",
            "detail": "Windows could not open the LAN repair prompt.",
        }

    time.sleep(0.25)
    if result_path.exists():
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        if isinstance(payload, dict):
            status = str(payload.get("status") or "").lower()
            detail = str(payload.get("detail") or "")
            if status == "ready":
                return {
                    "status": "ready",
                    "label": "Ready",
                    "detail": detail or "Same-network access was repaired.",
                }
            return {
                "status": "error",
                "label": "Repair failed",
                "detail": detail or "Windows did not complete the firewall repair.",
            }

    firewall_status = detect_firewall_rule()
    if firewall_status.get("status") == "ready":
        return {
            "status": "ready",
            "label": "Ready",
            "detail": "Same-network access is ready on this PC.",
        }

    stderr = _clean_powershell_error(result.stderr)
    return {
        "status": "warning",
        "label": "Permission needed",
        "detail": stderr or str(firewall_status.get("detail") or "")
        or "Windows permission was not completed. Try Repair again and approve the prompt.",
    }


def repair_runtime_data_permissions() -> dict[str, str]:
    if os.name != "nt":
        return {
            "status": "unknown",
            "label": "Not available",
            "detail": "Data folder permission repair is only available on Windows.",
        }

    script_path = write_runtime_permissions_repair_script()
    result_path = _runtime_permissions_repair_result_path()
    if result_path.exists():
        try:
            result_path.unlink()
        except OSError:
            pass

    runtime_path = str(DATA_RUNTIME_DIR.expanduser())
    arguments = [
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        "-RuntimePath",
        runtime_path,
        "-ResultPath",
        str(result_path),
    ]
    argument_line = " ".join(_command_line_quote(argument) for argument in arguments)
    start_process_script = (
        "$ProgressPreference = 'SilentlyContinue'; "
        f"$argumentLine = {_powershell_single_quote(argument_line)}; "
        "Start-Process -FilePath 'powershell.exe' -ArgumentList $argumentLine -Verb RunAs -Wait -WindowStyle Hidden"
    )

    try:
        result = subprocess.run(
            [
                _powershell_command(),
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-EncodedCommand",
                _encoded_powershell(start_process_script),
            ],
            capture_output=True,
            check=False,
            text=True,
            timeout=180,
            creationflags=_hidden_subprocess_creationflags(),
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "warning",
            "label": "Still waiting",
            "detail": "Windows permission did not finish. Try Repair again and approve the prompt.",
        }
    except OSError:
        return {
            "status": "error",
            "label": "Repair failed",
            "detail": "Windows could not open the data folder repair prompt.",
        }

    time.sleep(0.25)
    if result_path.exists():
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        if isinstance(payload, dict):
            status = str(payload.get("status") or "").lower()
            detail = str(payload.get("detail") or "")
            if status == "ready":
                return {
                    "status": "ready",
                    "label": "Ready",
                    "detail": detail or "Data folder access was repaired.",
                }
            return {
                "status": "error",
                "label": "Repair failed",
                "detail": detail or "Windows did not complete the data folder repair.",
            }

    permission_status = detect_runtime_permissions()
    if permission_status.get("status") == "ready":
        return {
            "status": "ready",
            "label": "Ready",
            "detail": "Data folder access is ready for normal app use.",
        }

    stderr = _clean_powershell_error(result.stderr)
    return {
        "status": "warning",
        "label": "Permission needed",
        "detail": stderr or str(permission_status.get("detail") or "")
        or "Windows permission was not completed. Try Repair again and approve the prompt.",
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
        "data_folder": detect_runtime_permissions(),
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
