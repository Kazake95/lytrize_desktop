#!/bin/bash
# build.sh -- Build Lytrize .deb package
# Usage: bash build.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

PKG_DIR=packaging/deb
APP=lytrize
VERSION=$(grep '^Version:'      "$PKG_DIR/DEBIAN/control" | awk '{print $2}')
ARCH=$(grep    '^Architecture:' "$PKG_DIR/DEBIAN/control" | awk '{print $2}')
BUILD=build/${APP}_${VERSION}_${ARCH}
VENV_TARGET=/opt/$APP/venv
VENV_BUILD=$BUILD$VENV_TARGET

echo "======================================"
echo "  Lytrize .deb builder  v${VERSION}"
echo "  Output: $SCRIPT_DIR/$BUILD.deb"
echo "======================================"
echo ""

# ── Verify build tools ────────────────────────────────────────────────────────
for tool in python3 dpkg-deb; do
    if ! command -v "$tool" &>/dev/null; then
        echo "ERROR: '$tool' not found. Install with: sudo apt install $tool"
        exit 1
    fi
done

# ── [1/7] Clean ───────────────────────────────────────────────────────────────
echo "[1/7] Cleaning old build..."
rm -rf build
mkdir -p "$BUILD/opt/$APP"

# ── [2/7] Copy app files ──────────────────────────────────────────────────────
echo "[2/7] Copying app files..."
cp -r backend  "$BUILD/opt/$APP/"
cp -r desktop  "$BUILD/opt/$APP/"
cp service/lytrize.service "$BUILD/opt/$APP/"

find "$BUILD/opt/$APP" -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
find "$BUILD/opt/$APP" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete 2>/dev/null || true
find "$BUILD/opt/$APP" -name "* (copy*).py" -delete 2>/dev/null || true
find "$BUILD/opt/$APP" -name "* (Copy*).py" -delete 2>/dev/null || true

# ── [3/7] Create virtual environment ─────────────────────────────────────────
echo "[3/7] Creating virtual environment..."
python3 -m venv "$VENV_BUILD"

# ── [4/7] Install Python dependencies ────────────────────────────────────────
echo "[4/7] Installing Python dependencies..."
"$VENV_BUILD/bin/pip" install --upgrade pip --quiet
"$VENV_BUILD/bin/pip" install \
    "streamlit>=1.40.0" \
    "pandas>=2.2.0" \
    "plotly>=5.22.0" \
    "openpyxl>=3.1.0" \
    "statsmodels>=0.14.0" \
    "pycountry>=23.12.11" \
    --quiet
echo "      Installing PySide6 (may take 2-3 minutes)..."
"$VENV_BUILD/bin/pip" install PySide6 --quiet

# ── [5/7] Patch venv shebangs for portability ─────────────────────────────────
echo "[5/7] Patching venv shebangs for portability..."
VENV_BUILD_ABS="$(realpath "$VENV_BUILD")"
find "$VENV_BUILD/bin" -maxdepth 1 -type f | while read -r f; do
    if head -c 2 "$f" 2>/dev/null | grep -q '#!'; then
        sed -i "1s|#!${VENV_BUILD_ABS}/bin/python[0-9.]*|#!/opt/lytrize/venv/bin/python3|g" "$f"
    fi
done
PYDIR="$(dirname "$(readlink -f "$(which python3)")")"
sed -i "s|^home = .*|home = $PYDIR|" "$VENV_BUILD/pyvenv.cfg" 2>/dev/null || true

# ── [6/7] Slim venv ────────────────────────────────────────────────────────────
echo "[6/7] Slimming venv..."
find "$VENV_BUILD" -type d \( -name '__pycache__' -o -name 'tests' -o -name 'test' -o -name 'docs' \) \
    -exec rm -rf {} + 2>/dev/null || true
find "$VENV_BUILD" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete 2>/dev/null || true

# ── [7/7] Assemble and build .deb ─────────────────────────────────────────────
echo "[7/7] Building .deb package..."

# Copy deb-specific packaging files
cp -r "$PKG_DIR/DEBIAN" "$BUILD/"
cp -r "$PKG_DIR/usr"    "$BUILD/"

# Bake icon into the package at all standard sizes
ICON_SRC="backend/assets/lytrize.png"
if [ -f "$ICON_SRC" ]; then
    echo "      Packaging icons..."
    for SIZE in 16 22 24 32 48 64 96 128 256; do
        IDIR="$BUILD/usr/share/icons/hicolor/${SIZE}x${SIZE}/apps"
        mkdir -p "$IDIR"
        if command -v convert >/dev/null 2>&1; then
            convert "$ICON_SRC" -resize "${SIZE}x${SIZE}" "$IDIR/lytrize.png" 2>/dev/null \
                || cp "$ICON_SRC" "$IDIR/lytrize.png"
        else
            cp "$ICON_SRC" "$IDIR/lytrize.png"
        fi
    done
    mkdir -p "$BUILD/usr/share/icons/hicolor/scalable/apps" \
             "$BUILD/usr/share/pixmaps"
    cp "$ICON_SRC" "$BUILD/usr/share/icons/hicolor/scalable/apps/lytrize.png"
    cp "$ICON_SRC" "$BUILD/usr/share/pixmaps/lytrize.png"
else
    echo "      WARNING: backend/assets/lytrize.png not found — package will have no icon."
fi

# Set permissions
find "$BUILD" -type d -exec chmod 755 {} \;
find "$BUILD" -type f -exec chmod 644 {} \;
# Make specific files executable
chmod 755 "$BUILD/usr/local/bin/lytrize"
chmod 755 "$BUILD/DEBIAN/postinst"
chmod 755 "$BUILD/DEBIAN/postrm"
chmod 755 "$BUILD/opt/$APP/desktop/gui.py"
chmod 755 "$BUILD/opt/$APP/desktop/launcher.py"
chmod 755 "$BUILD/usr/share/applications/lytrize.desktop"
find "$VENV_BUILD/bin" -type f -exec chmod 755 {} \;

dpkg-deb --build --root-owner-group "$BUILD"

echo ""
echo "======================================"
echo "  Build complete!"
echo "  Package : $SCRIPT_DIR/$BUILD.deb"
echo "  Size    : $(du -sh "$BUILD.deb" | cut -f1)"
echo ""
echo "  Install : sudo dpkg -i $BUILD.deb"
echo "            sudo apt-get install -f   # only if dpkg reports missing deps"
echo "  Launch  : lytrize"
echo "  Log     : /tmp/lytrize-launch.log   # if something goes wrong"
echo "======================================"
