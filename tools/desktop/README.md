# NDHI Laboratory Records Desktop Foundation

This folder contains the repeatable Windows packaging foundation for the local-first desktop edition.

## Daily clinic runtime

The installed shortcut launches `NDHI-LabRecords.exe`. The launcher:

1. creates the persistent runtime folders under `%ProgramData%\NDHI\LabRecords`;
2. generates a machine-local session secret if needed;
3. starts the FastAPI server on `0.0.0.0:8114` in default LAN mode, or `127.0.0.1:8114` in local-only mode, if it is not already healthy;
4. waits for `/api/health`;
5. opens the host PC through `http://127.0.0.1:8114` in the configured browser/app-mode window, with Edge as the safe default.

Browser preference is intentionally a launcher/runtime setting, not an installer-only decision. The installed launcher reads:

```text
%ProgramData%\NDHI\LabRecords\config\desktop.json
```

Supported values:

```json
{ "browser_preference": "auto" }
```

Allowed values are `auto`, `edge`, `chrome`, and `default`. `auto` tries Edge first, then Chrome, then the default browser as a last-resort fallback. Command-line override is also available:

```powershell
NDHI-LabRecords.exe --browser chrome
```

Admins can edit the same local preference from `Settings -> Desktop app`. The setting is per machine, not per user account.

`Settings -> Desktop app` also controls same-network access. Fresh installs default to LAN mode because the clinic priority is no-hassle same-network access:

```json
{ "network_mode": "lan" }
```

Allowed values are `local` and `lan`. `local` binds the server to `127.0.0.1`. `lan` binds the server to `0.0.0.0` so other trusted clinic devices on the same LAN can open the app using the hostname/IP URLs shown in Settings. Settings also provides copy buttons, readiness cards, and a downloadable QR code generated locally with `segno`. Keep the port at `8114` unless there is a specific support reason to change it.

The installer automatically creates a Windows Firewall rule named `NDHI Laboratory Records LAN` for TCP `8114`, limited to Private/Domain network profiles and the local subnet. The helper script is only a support fallback if firewall configuration is removed or damaged:

```powershell
.\tools\desktop\enable-lan-access.ps1
```

Do not expose the port to the internet or configure router port forwarding.

The site also ships a web app manifest so the browser-installable PWA path remains available. The launcher does not depend on browser PWA registration because browser profile state is not a reliable startup contract.

## Developer commands

Check a target Windows PC:

```powershell
.\tools\desktop\check-clinic-pc.ps1
```

Run the app through the local desktop-launcher behavior while keeping the existing development database:

```powershell
.\tools\desktop\run-local-desktop.ps1
```

Create and immediately verify a development backup:

```powershell
.\tools\desktop\backup-now.ps1 -Reason manual
```

Restore a development backup through the launcher contract:

```powershell
.\tools\desktop\restore-backup.ps1 -Archive <archive.zip>
```

Installed executable backup contract:

```powershell
NDHI-LabRecords.exe --backup-now --reason manual
NDHI-LabRecords.exe --verify-backup <archive.zip>
NDHI-LabRecords.exe --restore-backup <archive.zip>
```

Normal clinic backup/restore is exposed to admins in `Settings -> Desktop app`. Restore requires a backup ZIP upload and `RESTORE` confirmation, creates an emergency `pre-restore` backup first, and should be followed by closing and reopening the desktop app.

Build the packaged app and final Inno Setup installer:

```powershell
.\tools\desktop\build-installer.ps1 -Architecture x64
```

Validate PyInstaller packaging before Inno Setup is installed:

```powershell
.\tools\desktop\build-installer.ps1 -Architecture x64 -SkipInstaller
```

## Build prerequisites

- matching Python architecture for the requested build;
- PyInstaller installed in that Python environment:
  ```powershell
  .\tools\desktop\setup-build-tools.ps1
  ```
- Inno Setup 6 for the final setup executable.

PyInstaller generates an architecture-specific package. Generate `x86` only if the actual clinic PC requires it and use an `x86` Python interpreter for that build.

## Upgrade safety

The Inno Setup installer checks `%ProgramData%\NDHI\LabRecords` before replacing binaries. If an existing runtime database is present, Setup runs the currently installed executable with:

```powershell
NDHI-LabRecords.exe --backup-now --data-dir "%ProgramData%\NDHI\LabRecords" --reason pre-update
```

Fresh installs without a runtime database skip the hook. If the backup cannot start or exits nonzero, Setup aborts before changing installed files.

## Release boundary

This is a development-grade installer foundation. Do not label a package as a clinic release until the acceptance checks in `docs/handoff/DESKTOP_INSTALLER_ARCHITECTURE.md` pass on a clean Windows PC and the real clinic printer.
