# PyInstaller one-file console build. Keep runtime data explicit so local
# configuration, logs, and other machine-specific files cannot enter releases.
from pathlib import Path

root = Path.cwd()

a = Analysis(
    ["src/main.py"],
    pathex=["src"],
    binaries=[],
    datas=[
        (str(root / "translations"), "translations"),
        (str(root / ".env.example"), "."),
    ],
    hiddenimports=[],
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
    a.binaries,
    a.datas,
    [],
    name="send-minecraft-notifications",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
