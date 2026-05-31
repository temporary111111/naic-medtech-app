# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


DESKTOP_DIR = Path(SPECPATH)
PROJECT_ROOT = DESKTOP_DIR.parents[1]
APP_DIR = PROJECT_ROOT / "app"
APP_PACKAGE_DIR = APP_DIR / "naic_builder"
SCHEMA_DIR = PROJECT_ROOT / "artifacts" / "schema"

hiddenimports = collect_submodules("uvicorn") + collect_submodules("naic_builder")
debug_console = os.environ.get("NDHI_PACKAGE_CONSOLE") == "1"

a = Analysis(
    [str(DESKTOP_DIR / "launcher.py")],
    pathex=[str(APP_DIR)],
    binaries=[],
    datas=[
        (str(APP_PACKAGE_DIR / "static"), "naic_builder/static"),
        (str(APP_PACKAGE_DIR / "templates"), "naic_builder/templates"),
        (str(SCHEMA_DIR / "naic_medtech_app_schema.json"), "artifacts/schema"),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="NDHI-LabRecords",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=debug_console,
    disable_windowed_traceback=False,
    argv_emulation=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="NDHI-LabRecords",
)
