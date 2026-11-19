# PyInstaller spec for FOMOfolio (macOS .app and Windows .exe).
# Build with: pyinstaller --noconfirm FOMOfolio.spec
import os
import platform
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

APP_NAME = "FOMOfolio"
VERSION = os.environ.get("FOMOFOLIO_VERSION", "0.0.0").lstrip("v")

# App modules are imported by app.py at runtime through Streamlit, so the
# analysis cannot see them from launcher.py.
app_modules = ["config"]
for pkg in ("core", "ui", "utils"):
    app_modules += collect_submodules(pkg)

hiddenimports = app_modules + collect_submodules("streamlit") + ["webview"]

datas = [("app.py", ".")]
datas += collect_data_files("streamlit")
for dist in ("streamlit", "pandas", "yfinance", "numpy", "pyarrow", "altair", "pywebview"):
    try:
        datas += copy_metadata(dist)
    except Exception:
        pass

icon_mac = "assets/FOMOfolio.icns" if os.path.exists("assets/FOMOfolio.icns") else None
icon_win = "assets/FOMOfolio.ico" if os.path.exists("assets/FOMOfolio.ico") else None

a = Analysis(
    ["launcher.py"],
    pathex=["."],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "pytest", "IPython", "matplotlib"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    console=False,
    upx=False,
    # Build for the running architecture (python.org builds are universal2).
    target_arch=platform.machine() if sys.platform == "darwin" else None,
    icon=icon_win if sys.platform == "win32" else icon_mac,
)

coll = COLLECT(exe, a.binaries, a.datas, name=APP_NAME, upx=False)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=icon_mac,
        bundle_identifier="com.fomofolio.app",
        version=VERSION,
        info_plist={
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": APP_NAME,
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
        },
    )
