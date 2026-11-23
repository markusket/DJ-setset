# -*- mode: python ; coding: utf-8 -*-
# PyInstaller-määrittely. Rakenna: pyinstaller --noconfirm --clean setinrakentaja.spec
import sys

block_cipher = None

a = Analysis(
    ["run_setinrakentaja.py"],
    pathex=["."],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore",
        "PySide6.QtMultimedia", "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtCharts",
        "PySide6.QtDataVisualization", "PySide6.QtPdf", "tkinter",
    ],
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Setinrakentaja",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    argv_emulation=False,
)
coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, strip=False, upx=False, name="Setinrakentaja")

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Setinrakentaja.app",
        icon=None,
        bundle_identifier="fi.setinrakentaja.app",
        info_plist={
            "CFBundleName": "Setinrakentaja",
            "CFBundleDisplayName": "Setinrakentaja",
            "CFBundleShortVersionString": "1.0.0",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
        },
    )
