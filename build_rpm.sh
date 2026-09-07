#!/bin/bash
# build_rpm.sh -- Build Lytrize .rpm package
# Usage: bash build_rpm.sh
#
# Requires: rpm-build  (sudo dnf install rpm-build  /  sudo zypper install rpm-build)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

PKG_DIR=packaging/rpm
SPEC=$PKG_DIR/lytrize.spec

APP=$(      awk '/^Name:/      { print $2 }' "$SPEC")
VERSION=$(  awk '/^Version:/   { print $2 }' "$SPEC")
RELEASE=$(  awk '/^Release:/   { print $2 }' "$SPEC" | sed 's/%{?dist}//')
ARCH=$(     awk '/^BuildArch:/ { print $2 }' "$SPEC")

STAGING="$SCRIPT_DIR/build/rpm_staging"
RPMBUILD_ROOT="$SCRIPT_DIR/build/rpmbuild"
VENV="$STAGING/opt/$APP/venv"
FINAL_RPM="build/${APP}-${VERSION}-${RELEASE}_${ARCH}.rpm"

echo "======================================"
echo "  Lytrize .rpm builder  v${VERSION}"
echo "  Arch    : $ARCH"
echo "  Output  : $SCRIPT_DIR/$FINAL_RPM"
echo "======================================"
echo ""

for tool in python3 rpmbuild; do
    if ! command -v "$tool" &>/dev/null; then
        case "$tool" in
            rpmbuild)
                echo "ERROR: 'rpmbuild' not found."
                echo "  Fedora/RHEL : sudo dnf install rpm-build"
                echo "  openSUSE    : sudo zypper install rpm-build"
                ;;
            *) echo "ERROR: '$tool' not found." ;;
        esac
        exit 1
    fi
done

# ── [1/7] Clean ───────────────────────────────────────────────────────────────
echo "[1/7] Cleaning old build..."
rm -rf build
mkdir -p "$STAGING/opt/$APP" \
         "$STAGING/usr/local/bin" \
         "$STAGING/usr/share/applications" \
         "$RPMBUILD_ROOT/"{BUILD,RPMS,SOURCES,SPECS,SRPMS,BUILDROOT}

# ── [2/7] Copy app files ──────────────────────────────────────────────────────
echo "[2/7] Copying app files..."
cp -r backend  "$STAGING/opt/$APP/"
cp -r desktop  "$STAGING/opt/$APP/"
cp service/lytrize.service "$STAGING/opt/$APP/"

# Copy RPM-specific launcher stub and desktop entry
cp "$PKG_DIR/usr/local/bin/lytrize"             "$STAGING/usr/local/bin/lytrize"
cp "$PKG_DIR/usr/share/applications/lytrize.desktop" \
                                                "$STAGING/usr/share/applications/lytrize.desktop"

find "$STAGING/opt/$APP" -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
find "$STAGING/opt/$APP" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete 2>/dev/null || true
find "$STAGING/opt/$APP" -name "* (copy*).py" -delete 2>/dev/null || true
find "$STAGING/opt/$APP" -name "* (Copy*).py" -delete 2>/dev/null || true

# Bake icon into staging tree
ICON_SRC="backend/assets/lytrize.png"
if [ -f "$ICON_SRC" ]; then
    echo "      Packaging icons..."
    for SIZE in 16 22 24 32 48 64 96 128 256; do
        IDIR="$STAGING/usr/share/icons/hicolor/${SIZE}x${SIZE}/apps"
        mkdir -p "$IDIR"
        if command -v convert >/dev/null 2>&1; then
            convert "$ICON_SRC" -resize "${SIZE}x${SIZE}" "$IDIR/lytrize.png" 2>/dev/null \
                || cp "$ICON_SRC" "$IDIR/lytrize.png"
        else
            cp "$ICON_SRC" "$IDIR/lytrize.png"
        fi
    done
    mkdir -p "$STAGING/usr/share/icons/hicolor/scalable/apps" \
             "$STAGING/usr/share/pixmaps"
    cp "$ICON_SRC" "$STAGING/usr/share/icons/hicolor/scalable/apps/lytrize.png"
    cp "$ICON_SRC" "$STAGING/usr/share/pixmaps/lytrize.png"
else
    echo "      WARNING: backend/assets/lytrize.png not found — package will have no icon."
fi

# ── [3/7] Create virtual environment ─────────────────────────────────────────
echo "[3/7] Creating virtual environment..."
python3 -m venv "$VENV"

# ── [4/7] Install Python dependencies ────────────────────────────────────────
echo "[4/7] Installing Python dependencies..."
"$VENV/bin/pip" install --upgrade pip setuptools wheel --quiet
# Install from requirements.txt (single source of truth for version bounds)
# so build_rpm.sh can't silently drift from what `pip install -r requirements.txt`
# would give a developer.
"$VENV/bin/pip" install -r requirements.txt --quiet
# Pin pyarrow to 24.0.0 for Fedora (Python 3.14) — 18.1.0 has no 3.14 wheels
"$VENV/bin/pip" install "pyarrow>=24.0.0" --quiet --only-binary pyarrow

# ── [5/7] Patch venv shebangs for portability ─────────────────────────────────
echo "[5/7] Patching venv shebangs for portability..."
VENV_ABS="$(realpath "$VENV")"
find "$VENV/bin" -maxdepth 1 -type f | while read -r f; do
    if head -c 2 "$f" 2>/dev/null | grep -q '#!'; then
        sed -i "1s|#!${VENV_ABS}/bin/python[0-9.]*|#!/opt/lytrize/venv/bin/python3|g" "$f"
    fi
done
PYDIR="$(dirname "$(readlink -f "$(which python3)")")"
sed -i "s|^home = .*|home = $PYDIR|" "$VENV/pyvenv.cfg" 2>/dev/null || true

# ── [6/7] Slim venv ────────────────────────────────────────────────────────────
echo "[6/7] Slimming venv..."
find "$VENV" -type d \( -name '__pycache__' -o -name 'tests' -o -name 'test' -o -name 'docs' \) \
    -exec rm -rf {} + 2>/dev/null || true
find "$VENV" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete 2>/dev/null || true
# Remove broken symlinks so rpmbuild/tar doesn't fail
find "$VENV" -type l ! -exec test -e {} \; -delete 2>/dev/null || true

# ── [6b/7] Slim unused PySide6 Qt modules ─────────────────────────────────────
# The launcher only uses QtCore / QtGui / QtWidgets. Everything below is dead
# weight (WebEngine alone is an embedded Chromium) and removing it shrinks the
# package by ~150 MB. Mirrors the slimming build_windows.ps1 already does, and
# is guarded by a PySide6 smoke test so a broken package can never ship.
echo "[6b/7] Slimming unused PySide6 Qt modules..."
PYSIDE6_DIR=$(find "$VENV" -type d -name "PySide6" -path "*/site-packages/*" 2>/dev/null | head -1)
if [ -n "$PYSIDE6_DIR" ]; then
    SIZE_BEFORE=$(du -sh "$PYSIDE6_DIR" 2>/dev/null | cut -f1)
    # Unused Qt6 shared libraries (C++). Keep Core/Gui/Widgets and the few the
    # launcher actually links; drop the rest.
    find "$VENV" -type f \( \
        -name 'libQt6WebEngine*.so*' -o -name 'libQt6Pdf*.so*' -o \
        -name 'libQt6Qml*.so*' -o -name 'libQt6Quick*.so*' -o \
        -name 'libQt6Quick3D*.so*' -o -name 'libQt63D*.so*' -o \
        -name 'libQt6Charts*.so*' -o -name 'libQt6DataVisualization*.so*' -o \
        -name 'libQt6Designer*.so*' -o -name 'libQt6Graphs*.so*' -o \
        -name 'libQt6Multimedia*.so*' -o -name 'libQt6Sensors*.so*' -o \
        -name 'libQt6SerialPort*.so*' -o -name 'libQt6Positioning*.so*' -o \
        -name 'libQt6Location*.so*' -o -name 'libQt6RemoteObjects*.so*' -o \
        -name 'libQt6Scxml*.so*' -o -name 'libQt6WebChannel*.so*' -o \
        -name 'libQt6WebSockets*.so*' -o -name 'libQt6NetworkAuth*.so*' -o \
        -name 'libQt6HttpServer*.so*' -o -name 'libQt6TextToSpeech*.so*' -o \
        -name 'libQt6VirtualKeyboard*.so*' -o -name 'libQt6Help*.so*' -o \
        -name 'libQt6UiTools*.so*' -o -name 'libQt6Test*.so*' -o \
        -name 'libQt6Bluetooth*.so*' -o -name 'libQt6Nfc*.so*' -o \
        -name 'libQt6Labs*.so*' -o -name 'libQt6SpatialAudio*.so*' -o \
        -name 'libQt6WebView*.so*' \
    \) -delete 2>/dev/null || true
    # Unused PySide6 Python extension modules.
    find "$VENV" -type f \( \
        -name 'QtWebEngine*.so' -o -name 'QtPdf*.so' -o \
        -name 'QtQml*.so' -o -name 'QtQuick*.so' -o \
        -name 'QtQuick3D*.so' -o -name 'Qt3D*.so' -o \
        -name 'QtCharts*.so' -o -name 'QtDataVisualization*.so' -o \
        -name 'QtDesigner*.so' -o -name 'QtGraphs*.so' -o \
        -name 'QtMultimedia*.so' -o -name 'QtSensors*.so' -o \
        -name 'QtSerialPort*.so' -o -name 'QtPositioning*.so' -o \
        -name 'QtLocation*.so' -o -name 'QtRemoteObjects*.so' -o \
        -name 'QtScxml*.so' -o -name 'QtWebChannel*.so' -o \
        -name 'QtWebSockets*.so' -o -name 'QtNetworkAuth*.so' -o \
        -name 'QtHttpServer*.so' -o -name 'QtTextToSpeech*.so' -o \
        -name 'QtVirtualKeyboard*.so' -o -name 'QtHelp*.so' -o \
        -name 'QtUiTools*.so' -o -name 'QtTest*.so' -o \
        -name 'QtBluetooth*.so' -o -name 'QtNfc*.so' -o \
        -name 'QtLabs*.so' -o -name 'QtSpatialAudio*.so' -o \
        -name 'QtWebView*.so' \
    \) -delete 2>/dev/null || true
    # QtWebEngineProcess helper + webengine resources.
    find "$VENV" -type f -name 'QtWebEngineProcess*' -delete 2>/dev/null || true
    rm -rf "$PYSIDE6_DIR/resources/qtwebengine"* 2>/dev/null || true
    rm -rf "$PYSIDE6_DIR/translations/qtwebengine_locales" 2>/dev/null || true
    # QML tree + dev-only trees.
    rm -rf "$PYSIDE6_DIR/qml" 2>/dev/null || true
    for _d in doc glue include lib metatypes scripts; do
        rm -rf "$PYSIDE6_DIR/$_d" 2>/dev/null || true
    done
    # Unused plugin subdirectories.
    for _p in webview multimedia position sensors sceneparsers geometryloaders \
             canbus renderers renderplugins geoservices scxmldatamodel \
             texttospeech qmmlint qmltooling designer assetimporters; do
        rm -rf "$PYSIDE6_DIR/plugins/$_p" 2>/dev/null || true
    done
    rm -f "$PYSIDE6_DIR/plugins/imageformats/qpdf"* 2>/dev/null || true
    # Clean up now-broken symlinks left by the removals.
    find "$VENV" -type l ! -exec test -e {} \; -delete 2>/dev/null || true
    SIZE_AFTER=$(du -sh "$PYSIDE6_DIR" 2>/dev/null | cut -f1)
    echo "      PySide6 slimmed: $SIZE_BEFORE -> $SIZE_AFTER"
    # Smoke test — abort the build if PySide6 broke, so a broken package never ships.
    "$VENV/bin/python" -c "from PySide6 import QtCore, QtGui, QtWidgets; print('PySide6 smoke test OK')" \
        || { echo "ERROR: PySide6 smoke test FAILED after slimming — refusing to build."; exit 1; }
else
    echo "      PySide6 not found in venv — skipping Qt slimming."
fi

# Set permissions
find "$STAGING" -type d -exec chmod 755 {} \;
find "$STAGING" -type f -exec chmod 644 {} \;
# Make specific files executable
chmod 755 "$STAGING/usr/local/bin/lytrize"
chmod 755 "$STAGING/usr/share/applications/lytrize.desktop"
chmod 755 "$STAGING/opt/$APP/desktop/gui.py"
chmod 755 "$STAGING/opt/$APP/desktop/launcher.py"
find "$VENV/bin" -type f -exec chmod 755 {} \;

# ── [7/7] Build RPM ────────────────────────────────────────────────────────────
echo "[7/7] Building .rpm package..."
cp "$SPEC" "$RPMBUILD_ROOT/SPECS/lytrize.spec"

# QA_RPATHS bitmask: 0x0001 (standard) | 0x0002 (invalid) | 0x0010 (empty)
# Suppresses the check-rpaths failure caused by manylinux .so files in the
# bundled venv (scipy/numpy OpenBLAS RPATHs from the manylinux build env).
export QA_RPATHS=$(( 0x0001|0x0002|0x0010 ))

rpmbuild -bb \
    --define "_topdir        $RPMBUILD_ROOT" \
    --define "_rpmdir        $RPMBUILD_ROOT/RPMS" \
    --define "staging_dir    $STAGING" \
    --define "__brp_check_rpaths %{nil}" \
    --define "_build_name_fmt %%{NAME}-%%{VERSION}-%%{RELEASE}.%%{ARCH}.rpm" \
    "$RPMBUILD_ROOT/SPECS/lytrize.spec"

BUILT=$(find "$RPMBUILD_ROOT/RPMS" -name "*.rpm" | head -1)
[ -z "$BUILT" ] && { echo "ERROR: rpmbuild produced no .rpm file."; exit 1; }
mv "$BUILT" "$SCRIPT_DIR/$FINAL_RPM"

echo ""
echo "======================================"
echo "  Build complete!"
echo "  Package : $SCRIPT_DIR/$FINAL_RPM"
echo "  Size    : $(du -sh "$FINAL_RPM" | cut -f1)"
echo ""
echo "  Install : sudo rpm -i $FINAL_RPM"
echo "     (or)   sudo dnf install $FINAL_RPM"
echo "  Launch  : lytrize"
echo "  Log     : /tmp/lytrize-launch.log   # if something goes wrong"
echo "======================================"
