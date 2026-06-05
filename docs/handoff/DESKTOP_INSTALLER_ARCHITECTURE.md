# NDHI Laboratory Records Desktop Installer Architecture

## Status

The desktop foundation is implemented as a local-first deployment mode. It is not yet a clinic release.

The web application remains the product core. The desktop layer is intentionally thin so future multi-user deployment does not require rewriting the FastAPI application.

The source-level launcher, fresh-runtime smoke path, manifest, and verified backup foundation have been validated. PyInstaller `6.20.0` is installed in the project virtual environment through Python's Windows trust store, without bypassing TLS certificate checks. Inno Setup `6.7.3` is installed too. The normal windowed package now passes the automated local-server and verified-backup smoke checks, and the current development installer is `dist/desktop/installer/NDHI-LabRecords-Setup-0.1.1-dev-x64.exe`.

The first installed `0.1.0-dev` build was manually launched successfully on the development PC. Its running installed edition also created and re-verified a backup archive under `%ProgramData%\NDHI\LabRecords\backups`, proving that the online SQLite backup foundation works against the installed runtime while the local server is active. `0.1.1-dev` fixes misleading success-exit log entries and is the current upgrade-test build.

This is a testable development installer, not a clinic release. Manual installed-app QA, Defender-enabled clean-PC QA, real-printer QA, restore drills, automatic backup scheduling, external backup configuration, upgrade safety, and Authenticode signing are still required.

## Product Identity

| Layer | Value |
| --- | --- |
| Legal organization name | `Naic Doctors Hospital, Incorporated` |
| Visible organization name | `Naic Doctors Hospital` |
| Visible product name | `Laboratory Records System` |
| Desktop shortcut | `NDHI Laboratory Records` |
| Stable internal identity | `NDHI\LabRecords` |

Do not rename Python package identifiers, existing schema filenames, or legacy development files merely for cosmetic consistency. Visible branding and stable installed paths matter; unnecessary internal migrations add risk.

## Runtime Architecture

```text
NDHI Laboratory Records desktop shortcut
  -> NDHI-LabRecords.exe launcher
  -> ensure persistent runtime folders and machine-local session secret
  -> start bundled FastAPI server if /api/health is not already healthy
  -> bind only to 127.0.0.1:8114
  -> open the configured browser in dedicated app mode
  -> default-browser fallback only if app-mode browser launch cannot be satisfied
```

The browser-powered window is the recommended initial desktop shell. It keeps browser printing behavior intact while avoiding an early rewrite into a native UI framework. Edge remains the reliable default because it is normally present on supported Windows machines, but the launcher also supports Chrome and default-browser fallback. A PWA manifest is shipped too, but daily launch does not depend on browser-profile PWA registration.

Browser preference is runtime configuration, not an installer-only decision:

```text
%ProgramData%\NDHI\LabRecords\config\desktop.json
```

```json
{ "browser_preference": "auto" }
```

Allowed values are `auto`, `edge`, `chrome`, and `default`. `auto` tries Edge, then Chrome, then the default browser. The launcher also accepts `--browser auto|edge|chrome|default` for shortcut/testing overrides.

Admins can edit this local machine preference from `Settings -> Desktop app`. Keep it out of the main database because future multi-PC deployments may need different browser preferences per workstation.

The same Settings page now includes LAN access. `network_mode=local` binds the server to `127.0.0.1`; `network_mode=lan` binds it to `0.0.0.0` while still opening the host PC's desktop window through `127.0.0.1`. Settings shows a hostname URL first and local IPv4 fallback URLs for other clinic PCs. The default port remains `8114`; do not switch to port `80` by default because it increases permission, conflict, and firewall risk.

The host PC is the only machine that should own the SQLite database and backup folder. Other LAN devices should connect through the host URL in a normal browser. Never place the SQLite database on a network share and never run multiple installed desktop servers against the same database.

If Windows Firewall blocks LAN access, run this on the host PC as Administrator:

```powershell
.\tools\desktop\enable-lan-access.ps1
```

LAN mode is for trusted clinic networks only. Do not configure router port forwarding or expose the app directly to the internet.

## Installed Paths

Replaceable binaries:

```text
%ProgramFiles%\NDHI\LabRecords\
```

Persistent machine-level clinic data:

```text
%ProgramData%\NDHI\LabRecords\
  database\
  uploads\
  backups\
  logs\
  config\
```

The installer must never package or overwrite the tracked development DB under `data/runtime`. A fresh installed runtime creates its own DB and seeds forms from the bundled reference schema.

Uninstall intentionally preserves `%ProgramData%\NDHI\LabRecords`. Patient data must not disappear because an operator removes or upgrades application binaries.

## Development Compatibility

During normal repo development, the app still defaults to:

```text
data\runtime\
```

The installed launcher sets:

```text
NDHI_LABRECORDS_DATA_DIR=%ProgramData%\NDHI\LabRecords
NDHI_SESSION_SECRET=<machine-local generated secret>
```

The current tracked development DB keeps its legacy filename for compatibility. Fresh installed runtimes use:

```text
database\ndhi_labrecords.db
```

## Backup Foundation

`app/naic_builder/backup.py` now creates verified ZIP archives using SQLite's online backup API rather than copying a live DB file blindly.

Each archive includes:

- consistent SQLite snapshot;
- uploaded clinic logos;
- record images;
- user avatars;
- signatory stamp images;
- non-secret runtime configuration files;
- JSON manifest;
- SHA-256 checksums;
- post-build ZIP CRC and SQLite integrity validation.

Local development command:

```powershell
.\tools\desktop\backup-now.ps1 -Reason manual
```

Installed executable contract:

```powershell
NDHI-LabRecords.exe --backup-now --reason manual
NDHI-LabRecords.exe --verify-backup <archive.zip>
```

### Backup work still required before clinic release

- automatic debounced and daily schedules;
- retention policy;
- external destination configuration;
- settings UI with backup-health status;
- safe restore workflow with emergency pre-restore snapshot;
- pre-update backup triggered by installer upgrade;
- restore drill on a clean PC;
- failure notification when external backup becomes stale.

The local verified archive foundation is real, but it is not equivalent to a complete disaster-recovery system yet.

## Compatibility Policy

The packaging scripts support profiles:

```powershell
.\tools\desktop\build-installer.ps1 -Architecture x64
.\tools\desktop\build-installer.ps1 -Architecture x86
```

PyInstaller packages the active Python runtime, so architecture-specific builds require matching Python interpreters. Prefer `x64`. Generate `x86` only after the actual clinic PC diagnostic confirms it is necessary.

Target policy:

| Target | Policy |
| --- | --- |
| Windows 11 x64 | Primary |
| Windows 10 x64 | Compatibility only |
| Windows 10 x86 | Separate compatibility build if proven necessary |
| Windows 7 or 8 | Unsupported |

Run this on the clinic PC before choosing a build:

```powershell
.\tools\desktop\check-clinic-pc.ps1
```

## Repeatable Build

Build command:

```powershell
.\tools\desktop\setup-build-tools.ps1
.\tools\desktop\build-installer.ps1 -Architecture x64
```

Output:

```text
dist\desktop\installer\NDHI-LabRecords-Setup-<version>-<architecture>.exe
```

The build script:

1. validates version and Python architecture;
2. fails clearly if PyInstaller is unavailable;
3. rebuilds the one-folder application package;
4. launches the packaged FastAPI server against disposable data;
5. verifies `/api/health`;
6. creates and validates a disposable backup;
7. compiles the final setup executable with Inno Setup.

## Clinic Release Gates

Do not distribute an installer until all of these pass:

- manual builder review;
- records flow review;
- light and dark mode review;
- clean-PC install without Python or Node installed;
- clean-PC install and launcher test while Windows Defender is active;
- Authenticode-sign the distributable installer before clinic deployment;
- first-run setup and login;
- restart and repeated launcher use;
- create, save, complete, and view a real sample record;
- print preview and physical-printer test;
- verified local backup;
- configured external backup;
- restore drill;
- update old build to new build with pre-update backup;
- uninstall and reinstall without deleting persistent patient data;
- Windows architecture confirmation from the clinic PC.

Do not treat disabling antivirus protection as the normal installation procedure. During development, a scanner may temporarily inspect or lock newly generated PyInstaller files. The release process should instead produce a repeatable installer, test it with antivirus enabled, and sign the distributable artifact. Microsoft documents Authenticode signing as the Windows mechanism for identifying the publisher and verifying that published software was not modified. SmartScreen reputation is still evaluated per file hash, so signing improves trust and integrity but does not guarantee that every brand-new build immediately avoids a first-download warning.

## Deferred Future Mode

If the clinic later uses multiple computers, deploy the same FastAPI application centrally and move from SQLite to a server database such as PostgreSQL. Do not place the SQLite file on a shared network drive.
