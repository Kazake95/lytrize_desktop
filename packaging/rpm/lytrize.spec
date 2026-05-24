Name:           lytrize
Version:        1.1
Release:        1%{?dist}
Summary:        Offline desktop analytics — CSV and Excel to interactive dashboards
BuildArch:      x86_64

License:        See /opt/lytrize/LICENSE
URL:            https://github.com/lytrize/lytrize-desktop

# Runtime dependencies (Fedora / RHEL / openSUSE equivalents of the Debian deps)
Requires:       python3 >= 3.11
Requires:       mesa-libGL
Requires:       glib2
Requires:       xcb-util-cursor
Recommends:     chromium-browser
Recommends:     firefox

%description
Lytrize is a local-first Linux desktop analytics app.

Analyse CSV and Excel files locally with interactive Plotly charts,
saved dashboards, KPI cards, and export to PDF/image.

Features: distribution analysis, time series, correlation, outlier
detection, categorical charts, map plots, and more.

Fully offline — no internet connection, no cloud account, and no
telemetry. All data stays on this device.


# ── Build ─────────────────────────────────────────────────────────────────────
# No source compilation — the venv and app files are pre-built by build_rpm.sh
# and passed in via the staging_dir macro.

%install
# staging_dir is passed by build_rpm.sh: --define "staging_dir /path/to/staging"
# It mirrors the target filesystem layout (contains opt/, usr/).
cp -rp %{staging_dir}/. %{buildroot}/

# Ensure all venv executables are marked executable
find %{buildroot}/opt/lytrize/venv/bin -type f -exec chmod 755 {} \;
chmod 755 %{buildroot}/opt/lytrize/desktop/gui.py
chmod 755 %{buildroot}/opt/lytrize/desktop/launcher.py
chmod 755 %{buildroot}/usr/local/bin/lytrize


# ── Files ─────────────────────────────────────────────────────────────────────
%files
%defattr(-,root,root,-)

# Launcher stub
%attr(755,root,root) /usr/local/bin/lytrize

# Desktop entry
/usr/share/applications/lytrize.desktop

# Main application tree
%dir /opt/lytrize
/opt/lytrize/backend
/opt/lytrize/desktop
/opt/lytrize/venv
/opt/lytrize/lytrize.service


# ── Post-install ──────────────────────────────────────────────────────────────
# Runs after files are laid down on the target machine.
# $1 == 1  → fresh install
# $1 >= 2  → upgrade
%post
set -e

VENV=/opt/lytrize/venv
ASSETS=/opt/lytrize/backend/assets

# Wipe stale bytecode so Python recompiles from the newly installed .py files
find /opt/lytrize/backend -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
find /opt/lytrize/backend -name '*.pyc' -o -name '*.pyo' | xargs rm -f 2>/dev/null || true

# Re-link the bundled venv to this machine's python3.
# This is a symlink-only operation — it requires no network access.
echo "Linking Lytrize to system Python..."
python3 -m venv --upgrade "$VENV" 2>/dev/null || true

# Create the per-user data directory for the installing user.
# Under rpm install SUDO_USER holds the real user; fall back to USER.
TARGET_USER="${SUDO_USER:-$USER}"
if [ -n "$TARGET_USER" ] && [ "$TARGET_USER" != "root" ]; then
    USER_HOME=$(getent passwd "$TARGET_USER" | cut -d: -f6 2>/dev/null || echo "")
    if [ -n "$USER_HOME" ]; then
        mkdir -p "$USER_HOME/.local/share/lytrize"
        chown "$TARGET_USER" "$USER_HOME/.local/share/lytrize" 2>/dev/null || true
    fi
fi

# Install icon at every standard hicolor size
ICON_SRC=""
for candidate in "$ASSETS/lytrize.png" "$ASSETS/Lytrize.png" "$ASSETS/icon.png"; do
    if [ -f "$candidate" ]; then
        ICON_SRC="$candidate"
        break
    fi
done

if [ -n "$ICON_SRC" ]; then
    for SIZE in 16 22 24 32 48 64 96 128 256; do
        DIR="/usr/share/icons/hicolor/${SIZE}x${SIZE}/apps"
        mkdir -p "$DIR"
        if command -v convert >/dev/null 2>&1; then
            convert "$ICON_SRC" -resize "${SIZE}x${SIZE}" "$DIR/lytrize.png" 2>/dev/null \
                || cp "$ICON_SRC" "$DIR/lytrize.png"
        else
            cp "$ICON_SRC" "$DIR/lytrize.png"
        fi
    done
    mkdir -p /usr/share/icons/hicolor/scalable/apps /usr/share/pixmaps
    cp "$ICON_SRC" /usr/share/icons/hicolor/scalable/apps/lytrize.png
    cp "$ICON_SRC" /usr/share/pixmaps/lytrize.png
fi

# Refresh desktop and icon caches
gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
update-desktop-database /usr/share/applications      2>/dev/null || true
xdg-desktop-menu forceupdate                         2>/dev/null || true

echo "Lytrize installed successfully."
echo "Launch from your application menu or run: lytrize"


# ── Pre-uninstall ─────────────────────────────────────────────────────────────
# Runs before files are removed.
# $1 == 0  → full uninstall
# $1 == 1  → upgrade (leave everything in place)
%preun
if [ "$1" -eq 0 ]; then
    # Stop and disable the systemd user service if it is running
    TARGET_USER="${SUDO_USER:-$USER}"
    if [ -n "$TARGET_USER" ] && [ "$TARGET_USER" != "root" ]; then
        _UID=$(id -u "$TARGET_USER" 2>/dev/null || echo "")
        _RUNTIME="/run/user/${_UID}"
        _SVC_FILE="/home/${TARGET_USER}/.config/systemd/user/lytrize.service"

        if [ -n "$_UID" ] && [ -d "$_RUNTIME" ]; then
            su "$TARGET_USER" -c "
                export XDG_RUNTIME_DIR='${_RUNTIME}'
                export DBUS_SESSION_BUS_ADDRESS='unix:path=${_RUNTIME}/bus'
                systemctl --user stop    lytrize 2>/dev/null || true
                systemctl --user disable lytrize 2>/dev/null || true
                systemctl --user daemon-reload   2>/dev/null || true
            " 2>/dev/null || true
        fi
        rm -f "$_SVC_FILE" 2>/dev/null || true
    fi
fi


# ── Post-uninstall ────────────────────────────────────────────────────────────
# Runs after files are removed.
# $1 == 0  → full uninstall    (clean up everything)
# $1 == 1  → upgrade           (leave data and icons; next %post will refresh them)
%postun
if [ "$1" -eq 0 ]; then

    # Remove icons from the hicolor theme
    for SIZE in 16 22 24 32 48 64 96 128 256; do
        rm -f "/usr/share/icons/hicolor/${SIZE}x${SIZE}/apps/lytrize.png" 2>/dev/null || true
    done
    rm -f /usr/share/icons/hicolor/scalable/apps/lytrize.png 2>/dev/null || true
    rm -f /usr/share/pixmaps/lytrize.png                     2>/dev/null || true

    # Force-remove the entire /opt/lytrize tree.
    # RPM removes only files it installed; the venv writes hundreds of extra
    # __pycache__ dirs and .pyc files at runtime that RPM never tracked.
    rm -rf /opt/lytrize 2>/dev/null || true

    # User data — ask interactively, preserve silently in non-interactive mode
    TARGET_USER="${SUDO_USER:-$USER}"
    USER_DATA_DIR=""
    if [ -n "$TARGET_USER" ] && [ "$TARGET_USER" != "root" ]; then
        USER_HOME=$(getent passwd "$TARGET_USER" | cut -d: -f6 2>/dev/null || echo "")
        if [ -n "$USER_HOME" ]; then
            USER_DATA_DIR="$USER_HOME/.local/share/lytrize"
        fi
    fi

    if [ -n "$USER_DATA_DIR" ] && [ -d "$USER_DATA_DIR" ]; then
        if [ -t 0 ]; then
            echo ""
            echo "Lytrize user data found at: $USER_DATA_DIR"
            echo "This contains your saved analysis sessions and account data."
            echo ""
            printf "Remove user data? This cannot be undone. [y/N] "
            read -r _ANSWER </dev/tty || _ANSWER="n"
            case "$_ANSWER" in
                [Yy]*)
                    rm -rf "$USER_DATA_DIR"
                    echo "User data removed."
                    ;;
                *)
                    echo "User data kept at: $USER_DATA_DIR"
                    echo "To remove manually: rm -rf $USER_DATA_DIR"
                    ;;
            esac
        else
            echo "Non-interactive mode: user data preserved at: $USER_DATA_DIR"
            echo "To remove manually: rm -rf $USER_DATA_DIR"
        fi
    fi

    # Refresh caches after icon removal
    gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
    update-desktop-database /usr/share/applications      2>/dev/null || true

    echo "Lytrize fully removed."
fi


# ── Changelog ─────────────────────────────────────────────────────────────────
%changelog
* Fri May 24 2026 Lytrize <vnat8638@gmail.com> - 1.1-1
- Removed Playwright dependency; HTML-to-PNG export now uses the system browser
- Fixed stale runners.py compat shim import in pages/analysis.py
- Removed dead backend/utils/ directory (never imported)
- Removed empty matrix_performance_patch.py

* Wed May 21 2026 Lytrize <vnat8638@gmail.com> - 1.0-1
- Initial release
