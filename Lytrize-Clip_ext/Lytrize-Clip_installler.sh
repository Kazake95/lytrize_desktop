#!/bin/bash
# Lytrize-Clip Installer
# Installs the unpacked extension from the same directory as this script.

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXT_PATH="$SCRIPT_DIR/Lytrize-Clip"
BROWSER="${1:-auto}"
PROFILE="${2:-Default}"

if [ ! -f "$EXT_PATH/manifest.json" ]; then
    echo -e "${RED}Error: Lytrize-Clip/ folder not found next to this script.${NC}"
    echo "Expected: $EXT_PATH"
    exit 1
fi

detect_profile() {
    local name="$1"
    local paths=()
    case "$name" in
        chrome)
            paths=("$HOME/.config/google-chrome/$PROFILE" "$HOME/.config/chromium/$PROFILE")
            ;;
        chromium)
            paths=("$HOME/.config/chromium/$PROFILE" "$HOME/.config/google-chrome/$PROFILE")
            ;;
        edge)
            paths=("$HOME/.config/microsoft-edge/$PROFILE")
            ;;
        brave)
            paths=("$HOME/.config/BraveSoftware/Brave-Browser/$PROFILE")
            ;;
        opera)
            paths=("$HOME/.config/opera")
            ;;
        vivaldi)
            paths=("$HOME/.config/vivaldi/$PROFILE")
            ;;
    esac
    for p in "${paths[@]}"; do
        if [ -d "$p" ]; then
            PROFILE_DIR="$p"
            DETECTED_BROWSER="$name"
            return 0
        fi
    done
    return 1
}

if [ "$BROWSER" = "auto" ]; then
    for b in chrome chromium edge brave opera vivaldi; do
        if detect_profile "$b"; then
            break
        fi
    done
else
    detect_profile "$BROWSER"
fi

if [ -z "$PROFILE_DIR" ]; then
    echo -e "${RED}Error: Could not find browser profile directory.${NC}"
    exit 1
fi

PREFS="$PROFILE_DIR/Preferences"
if [ ! -f "$PREFS" ]; then
    echo -e "${RED}Error: Preferences file not found at $PREFS${NC}"
    exit 1
fi

echo -e "${BLUE}Browser profile:${NC}  $PROFILE_DIR"
echo -e "${BLUE}Extension folder:${NC} $EXT_PATH"

# Check if browser is running
BROWSER_PIDS=""
for proc in chrome chromium brave msedge opera vivaldi; do
    PIDS=$(pgrep -x "$proc" 2>/dev/null || true)
    if [ -n "$PIDS" ]; then
        BROWSER_PIDS="$BROWSER_PIDS $PIDS"
    fi
done

if [ -n "$BROWSER_PIDS" ]; then
    echo ""
    echo -e "${YELLOW}WARNING: A Chromium-based browser is running.${NC}"
    echo -e "${YELLOW}Close it first, or changes may be lost.${NC}"
    echo ""
    read -p "Press Enter to continue, or Ctrl+C to cancel..."
fi

# Backup
BACKUP="$PREFS.lytrize-backup-$(date +%s)"
cp "$PREFS" "$BACKUP"
echo -e "${GREEN}Backup created:${NC} $BACKUP"

python3 - "$EXT_PATH" "$PREFS" << 'PYTHON_EOF'
import sys, json, os, hashlib, time

ext_path = sys.argv[1]
prefs_path = sys.argv[2]

def get_ext_id(path):
    canon = os.path.realpath(path)
    d = hashlib.sha256(canon.encode("utf-8")).digest()[:16]
    return "".join(chr(ord("a") + (b >> 4)) + chr(ord("a") + (b & 0x0F)) for b in d)

with open(prefs_path, "r") as f:
    prefs = json.load(f)

prefs.setdefault("extensions", {})
prefs["extensions"].setdefault("settings", {})
prefs["extensions"].setdefault("ui", {})

prefs["extensions"]["ui"]["developer_mode"] = True

ext_id = get_ext_id(ext_path)

prefs["extensions"]["settings"][ext_id] = {
    "path": os.path.realpath(ext_path),
    "location": 4,
    "state": 1,
    "install_time": str(int(time.time() * 1000000)),
    "was_installed_by_default": False,
    "was_installed_by_oem": False,
    "acknowledged": True
}

with open(prefs_path, "w") as f:
    json.dump(prefs, f, separators=(",", ":"))

print(f"Extension ID: {ext_id}")
PYTHON_EOF

echo ""
echo -e "${GREEN}✓ Lytrize-Clip installed.${NC}"
echo -e "${YELLOW}Restart your browser to activate it.${NC}"
echo ""
echo "Restore backup if needed:"
echo "  cp $BACKUP $PREFS"
