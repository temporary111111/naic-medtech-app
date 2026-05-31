# NDHI Laboratory Records Desktop Foundation

This folder contains the repeatable Windows packaging foundation for the local-first desktop edition.

## Daily clinic runtime

The installed shortcut launches `NDHI-LabRecords.exe`. The launcher:

1. creates the persistent runtime folders under `%ProgramData%\NDHI\LabRecords`;
2. generates a machine-local session secret if needed;
3. starts the FastAPI server on `127.0.0.1:8114` if it is not already healthy;
4. waits for `/api/health`;
5. opens Microsoft Edge in dedicated `--app=` mode, with default-browser fallback.

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

## Release boundary

This is a development-grade installer foundation. Do not label a package as a clinic release until the acceptance checks in `docs/handoff/DESKTOP_INSTALLER_ARCHITECTURE.md` pass on a clean Windows PC and the real clinic printer.
