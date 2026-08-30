"""
desktop/gui.py — Lytrize Desktop Launcher
==========================================

PySide6 launcher window that manages the Streamlit backend subprocess and
opens the web UI in an isolated browser window.

FEATURES
--------
- Detects all installed browsers; remembers the user's choice across sessions.
- Opens Chromium-based browsers in true "app mode" (no toolbar, isolated
  profile, maximised window) and Firefox in a new isolated instance.
- System tray with Open / Stop & Quit actions.
- Crash-recovery: if Streamlit exits unexpectedly the launcher shows a
  recoverable error state instead of going blank.

STARTUP BEHAVIOUR
-----------------
There are no accounts, sign-up, or login — the app opens straight into the
single local workspace tied to the current OS user, every launch.

BROWSER MODES
-------------
Chromium-based (Chrome, Brave, Edge, Vivaldi, Opera):
  Launched with --app=<url> which strips the browser chrome (address bar,
  tabs) and opens the page in a standalone maximised window that looks and
  feels like a native desktop app.

Firefox / Gecko-based (Firefox, Firefox ESR, LibreWolf, Zen):
  Launched with --new-instance + -profile (isolated) + --kiosk so the
  Lytrize window opens fullscreen with no address bar, no tabs, and no
  browser chrome — the closest Firefox can achieve to Chromium's --app=
  mode without installing an extension.

xdg-open (fallback):
  Delegates to the system default handler. No isolation is possible; the
  URL simply opens wherever the OS decides.

CONTRIBUTING
------------
Keep all Qt / PySide6 code inside this file.
Pure-data helpers belong in backend/modules/utils/.
Threading model: all subprocess I/O is done in QThread subclasses;
results are communicated back to the main thread exclusively via Qt signals.
Never call Qt widget methods from a non-main thread.
"""
import logging

import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

if os.name != "nt":
    import signal  # process-group termination support (POSIX only)

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSystemTrayIcon, QMenu,
    QFrame, QComboBox, QProgressBar, QSizePolicy,
    QGraphicsDropShadowEffect,
)
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from PySide6.QtCore import Qt, QThread, Signal, QPropertyAnimation, QEasingCurve, QTimer, Property, QEvent



BASE       = Path(__file__).resolve().parent.parent  # repo root (or install base)

# backend/config.py is the single source of truth for host/port -- import it
# rather than duplicating "127.0.0.1" / "8501" literals here. If it can't be
# imported for any reason (e.g. a broken install), fall back to the same
# defaults config.py itself defines so the app can still start.
sys.path.insert(0, str(BASE / "backend"))
try:
    from config import APP_HOST, APP_PORT
except Exception:
    APP_HOST, APP_PORT = "127.0.0.1", 8501

# Cross-platform helpers for data-dir placement.
from modules.utils.paths import data_dir as _paths_data_dir
from modules.utils.paths import is_windows as _is_windows

APP_URL    = f"http://{APP_HOST}:{APP_PORT}"

# Persistent user data lives in %APPDATA%\Lytrize on Windows and
# ~/.local/share/lytrize on Linux. Everything downstream (prefs, DB, browser
# profiles, logs) derives from DATA_DIR so uninstall can remove a single tree.
DATA_DIR   = _paths_data_dir()
PREFS      = DATA_DIR / "launcher_prefs.json"
DB_PATH    = DATA_DIR / "lytrize.db"

# Windows venvs place the interpreter under Scripts\pythonw.exe (no console);
# Linux venvs use bin/python. VENV_PY is used for the Streamlit subprocess.
VENV_DIR   = BASE / "venv"
if _is_windows():
    VENV_PY = VENV_DIR / "Scripts" / "pythonw.exe"
else:
    VENV_PY = VENV_DIR / "bin" / "python"

APP_PY     = BASE / "backend" / "app.py"

_PROFILE_ROOT = DATA_DIR / "browser-profiles"
_CHROMIUM_PROFILE = _PROFILE_ROOT / "chromium"
_FIREFOX_PROFILE  = _PROFILE_ROOT / "firefox"

_POLL_INTERVAL_S = 0.5   # seconds between socket probes
_POLL_MAX_TRIES  = 60    # 60 × 0.5 s = 30 s total timeout


def _find_icon() -> Path:
    """Return the first existing icon file from backend/assets/."""
    assets = BASE / "backend" / "assets"
    for name in ("lytrize.png", "Lytrize.png", "lytrize.ico", "Lytrize.ico"):
        candidate = assets / name
        if candidate.exists():
            return candidate
    return assets / "lytrize.png"   

ICON_PATH = _find_icon()



def _load_prefs() -> dict:
    """
    Load persisted launcher preferences from disk.

    Returns an empty dict on any I/O or parse error so callers never
    have to guard against missing keys or file-not-found situations.
    """
    try:
        return json.loads(PREFS.read_text())
    except Exception:
        return {}


def _save_prefs(data: dict) -> None:
    """Persist launcher preferences atomically to DATA_DIR/launcher_prefs.json."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        DATA_DIR.chmod(0o700)
    except Exception as exc:
        logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
        pass
    tmp = PREFS.with_name(f".{PREFS.name}.tmp")
    tmp.write_text(json.dumps(data, indent=2))
    try:
        tmp.chmod(0o600)
    except Exception as exc:
        logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
        pass
    os.replace(tmp, PREFS)
    try:
        PREFS.chmod(0o600)
    except Exception as exc:
        logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
        pass



# ── Linux candidates ---------------------------------------------------
# Resolved via shutil.which() against the executable name on PATH.
_LINUX_BROWSER_CANDIDATES: list[tuple[str, str, bool]] = [
    ("Google Chrome",  "google-chrome",        True),
    ("Google Chrome",  "google-chrome-stable", True),
    ("Chromium",       "chromium",              True),
    ("Chromium",       "chromium-browser",      True),
    ("Brave",          "brave-browser",         True),
    ("Brave",          "brave-browser-stable",  True),
    ("Microsoft Edge", "microsoft-edge",        True),
    ("Vivaldi",        "vivaldi",               True),
    ("Opera",          "opera",                 True),
    ("Firefox",        "firefox",               False),
    ("Firefox ESR",    "firefox-esr",           False),
    ("Zen Browser",    "zen",                   False),
    ("LibreWolf",      "librewolf",             False),
]

# ── Windows candidates -------------------------------------------------
# Real install paths under the standard Program Files / Program Files (x86)
# roots. `%PF%` is expanded to each root at detection time. These exes are NOT
# on PATH on Windows, so shutil.which() cannot be used for them.
_WINDOWS_BROWSER_CANDIDATES: list[tuple[str, str, bool]] = [
    ("Google Chrome",   r"%PF%\Google\Chrome\Application\chrome.exe",              True),
    ("Microsoft Edge",  r"%PF%\Microsoft\Edge\Application\msedge.exe",              True),
    ("Brave",           r"%PF%\BraveSoftware\Brave-Browser\Application\brave.exe", True),
    ("Vivaldi",         r"%PF%\Vivaldi\Application\vivaldi.exe",                    True),
    ("Opera",           r"%PF%\Opera\launcher.exe",                                True),
    ("Mozilla Firefox", r"%PF%\Mozilla Firefox\firefox.exe",                       False),
    ("LibreWolf",       r"%PF%\LibreWolf\librewolf.exe",                           False),
]

# Sentinel used as the "Default / OS handler" browser binary. On Linux this is
# resolved to real `xdg-open`; on Windows it triggers os.startfile().
_DEFAULT_HANDLER = "xdg-open"


def _detect_browsers() -> list[dict]:
    """
    Return a deduplicated list of installed browser dicts.

    Each dict has keys: ``name`` (str), ``binary`` (str path), ``chromium`` (bool).

    On Linux, candidates are resolved with ``shutil.which()`` so symlinks such as
    ``/usr/bin/chromium → /usr/bin/chromium-browser`` are counted once.

    On Windows, candidates are looked up by their real executable path under the
    Program Files roots (browser exes are not on PATH). If nothing is found on
    either OS, a single OS-default-handler entry is returned.
    """
    seen: set[str] = set()
    found: list[dict] = []

    if _is_windows():
        pf      = os.environ.get("ProgramFiles")        or r"C:\Program Files"
        pf_x86  = os.environ.get("ProgramFiles(x86)")   or r"C:\Program Files (x86)"
        local   = os.environ.get("LOCALAPPDATA")        or ""
        # Per-user installs (e.g. current-user Chrome) live under %LOCALAPPDATA%;
        # system-wide ones under the Program Files roots.
        roots = [pf, pf_x86]
        if local:
            roots.append(local)
        for name, relpath, is_chromium in _WINDOWS_BROWSER_CANDIDATES:
            for root in roots:
                binary = relpath.replace("%PF%", root)
                path = Path(binary)
                if not path.exists():
                    continue
                resolved = str(path.resolve())
                if resolved in seen:
                    continue
                seen.add(resolved)
                found.append({"name": name, "binary": binary, "chromium": is_chromium})
    else:
        for name, binary, is_chromium in _LINUX_BROWSER_CANDIDATES:
            path = shutil.which(binary)
            if not path:
                continue
            resolved = str(Path(path).resolve())
            if resolved in seen:
                continue
            seen.add(resolved)
            found.append({"name": name, "binary": path, "chromium": is_chromium})

    if not found:
        found.append({
            "name": "Default",
            "binary": _DEFAULT_HANDLER,
            "chromium": False,
        })

    return found


def _windows_processes() -> list[dict]:
    """
    Snapshot of running Windows processes as a list of dicts with keys
    ``ProcessId``, ``ParentProcessId``, ``Name`` and ``CommandLine``.

    Implemented via PowerShell's Get-CimInstance (no third-party deps).
    Returns an empty list if the query fails, so callers must fall back to
    PID-based killing.
    """
    ps_cmd = (
        "Get-CimInstance Win32_Process | "
        "Select-Object ProcessId,ParentProcessId,Name,CommandLine | "
        "ConvertTo-Json -Compress"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        data = json.loads(result.stdout or "[]")
    except Exception as exc:
        logging.getLogger(__name__).debug(
            "Suppressed error enumerating processes: %s", exc, exc_info=True
        )
        return []
    if isinstance(data, dict):          # single-result form
        data = [data]
    return data or []


def _port_in_use(host: str, port: int) -> bool:
    """True when something is already accepting connections on host:port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0



def _make_icon() -> QIcon:
    """
    Build the application QIcon.

    Loads the PNG/ICO from assets/; if the file is absent or unreadable,
    falls back to a programmatically drawn indigo rounded-rect with an 'L'.
    """
    if ICON_PATH.exists():
        pixmap = QPixmap(str(ICON_PATH))
        if not pixmap.isNull():
            return QIcon(pixmap)

    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor("#4f6ef7"))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(0, 0, 64, 64, 14, 14)
    painter.setPen(QColor("white"))
    painter.setFont(QFont("Sans", 28, QFont.Bold))
    painter.drawText(pixmap.rect(), Qt.AlignCenter, "L")
    painter.end()
    return QIcon(pixmap)



class _WaitThread(QThread):
    """
    Poll APP_HOST:APP_PORT (from backend/config.py) until Streamlit accepts
    TCP connections.

    Emits:
        ready()   — Streamlit is up and accepting connections.
        timeout() — 30 seconds elapsed without a successful connection.

    Threading note: this thread only emits signals; it never touches Qt
    widgets directly.  Qt auto-queues cross-thread signal delivery.
    """
    ready   = Signal()
    timeout = Signal()

    def run(self) -> None:
        for _ in range(_POLL_MAX_TRIES):
            try:
                with socket.create_connection((APP_HOST, APP_PORT), _POLL_INTERVAL_S):
                    pass
                self.ready.emit()
                return
            except OSError:
                time.sleep(_POLL_INTERVAL_S)
        self.timeout.emit()


class _WatchThread(QThread):
    """
    Monitor the Streamlit subprocess for unexpected exits.

    Emits:
        crashed(exit_code) — subprocess exited with a *non-zero* code
                             AND the thread was not cancelled before it
                             returned (i.e. it was not a deliberate stop).

    The ``cancel()`` method should be called before the process is
    deliberately terminated so that a normal SIGTERM (-15) exit is not
    reported as a crash.
    """
    crashed = Signal(int)

    def __init__(self, proc: subprocess.Popen) -> None:
        super().__init__()
        self._proc       = proc
        self._cancelled  = False   # set to True before intentional stop

    def cancel(self) -> None:
        """
        Signal that the upcoming process exit is intentional.

        Call this BEFORE terminating the process to suppress the crash
        notification that would otherwise appear on SIGTERM (-15) exit.
        """
        self._cancelled = True

    def run(self) -> None:
        code = self._proc.wait()
        if code != 0 and not self._cancelled:
            self.crashed.emit(code)


def _ensure_firefox_profile(profile_dir: Path) -> None:
    """
    Create a minimal Firefox/LibreWolf profile that suppresses all first-run
    dialogs and telemetry prompts so the isolated window opens cleanly.

    Without this, Firefox shows "Set as default?", crash-reporter opt-ins,
    and "What's new in Firefox" tabs — even on --new-instance launches.
    The user.js file in the profile overrides these preferences before
    Firefox reads its own defaults.

    Safe to call on every launch; only writes user.js on first creation.
    """
    profile_dir.mkdir(parents=True, exist_ok=True)
    try:
        profile_dir.chmod(0o700)
    except Exception as exc:
        logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
        pass

    user_js = profile_dir / "user.js"
    if not user_js.exists():
        user_js.write_text(
            "// Lytrize isolated Firefox profile — auto-generated, do not edit\n"
            'user_pref("browser.shell.checkDefaultBrowser",       false);\n'
            'user_pref("browser.startup.homepage_override.mstone","ignore");\n'
            'user_pref("browser.startup.firstrunSkipsHomepage",   true);\n'
            'user_pref("browser.tabs.warnOnClose",                false);\n'
            'user_pref("browser.sessionstore.resume_from_crash",  false);\n'
            'user_pref("datareporting.policy.dataSubmissionEnabled", false);\n'
            'user_pref("datareporting.healthreport.uploadEnabled", false);\n'
            'user_pref("toolkit.telemetry.enabled",               false);\n'
            'user_pref("app.normandy.enabled",                    false);\n'
            'user_pref("extensions.formautofill.addresses.enabled", false);\n'
            'user_pref("browser.newtabpage.activity-stream.feeds.section.highlights", false);\n'
            'user_pref("browser.startup.maximized",               false);\n'
            'user_pref("toolkit.legacyUserProfileCustomizations.stylesheets", true);\n'
            'user_pref("browser.tabs.inTitlebar",                 0);\n'
        )

    chrome_dir = profile_dir / "chrome"
    chrome_dir.mkdir(exist_ok=True)
    user_chrome = chrome_dir / "userChrome.css"
    if not user_chrome.exists():
        user_chrome.write_text(
            "/* Lytrize — webapp-style Firefox window (auto-generated) */\n"
            "@namespace url(\"http://www.mozilla.org/keymaster/gatekeeper/there.is.only.xul\");\n"
            "\n"
            "/* Hide the URL / navigation toolbar */\n"
            "#nav-bar { display: none !important; }\n"
            "\n"
            "/* Hide the tab strip */\n"
            "#TabsToolbar { display: none !important; }\n"
            "\n"
            "/* Hide bookmarks toolbar if the user had it on */\n"
            "#PersonalToolbar { display: none !important; }\n"
            "\n"
            "/* Keep the window titlebar (OS decorations) visible so the user\n"
            "   can resize/minimise/close the window normally */\n"
        )




class _PulseDot(QWidget):
    """
    A small circle that smoothly fades between two opacities to signal
    the app's running state without any text changes.

    The animation is driven entirely by QPropertyAnimation on a custom
    Qt Property so it integrates cleanly with the event loop and stops
    automatically when the dot is hidden.
    """

    def __init__(self, colour: str = "#10b981", size: int = 10, parent=None):
        super().__init__(parent)
        self._colour  = QColor(colour)
        self._size    = size
        self._opacity = 1.0
        self.setFixedSize(size, size)

        self._anim = QPropertyAnimation(self, b"opacity", self)
        self._anim.setDuration(900)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.28)
        self._anim.setEasingCurve(QEasingCurve.InOutSine)
        self._anim.setLoopCount(-1)          # loop forever
        self._anim.finished.connect(self._flip)  # ping-pong


    def _get_opacity(self) -> float:
        return self._opacity

    def _set_opacity(self, v: float) -> None:
        self._opacity = v
        self.update()

    opacity = Property(float, _get_opacity, _set_opacity)


    def _flip(self) -> None:
        """Reverse direction for ping-pong effect."""
        start = self._anim.startValue()
        end   = self._anim.endValue()
        self._anim.setStartValue(end)
        self._anim.setEndValue(start)

    def start(self, colour: str | None = None) -> None:
        if colour:
            self._colour = QColor(colour)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.28)
        self._anim.start()

    def stop(self, colour: str = "#64748b") -> None:
        self._anim.stop()
        self._colour = QColor(colour)
        self._opacity = 1.0
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QColor(self._colour)
        c.setAlphaF(self._opacity)
        p.setBrush(c)
        p.setPen(Qt.NoPen)
        p.drawEllipse(0, 0, self._size, self._size)



class Launcher(QWidget):
    """
    Main launcher window — modernised with smooth animations.

    Responsibilities:
        - Build and style the UI (header, status label, browser picker,
          Start / Open / Stop buttons, system tray).
        - Start and stop the Streamlit backend subprocess.
        - Open the web UI in the selected browser in isolated app mode.
        - Report subprocess crashes to the user without crashing the launcher.
        - Animate startup progress, status transitions, and button states.

    The window stays alive in the system tray while Streamlit is running,
    and closes completely only when the user clicks "Stop & Quit".
    """

    _QSS = """
        /* ── Base ── */
        QWidget {
            background: transparent;
            color: #e2e8f0;
            font-family: 'Segoe UI', 'SF Pro Display', system-ui, sans-serif;
            font-size: 13px;
        }

        /* ── Window card ── */
        QWidget#card {
            background: qlineargradient(
                x1:0, y1:0, x2:0, y2:1,
                stop:0 #111827,
                stop:1 #0d1424
            );
            border: 1px solid rgba(99,102,241,0.20);
            border-radius: 14px;
        }

        /* ── Labels ── */
        QLabel#title {
            font-size: 17px;
            font-weight: 700;
            color: #a5b4fc;
            letter-spacing: 0.5px;
        }
        QLabel#subtitle {
            font-size: 11px;
            color: #475569;
            letter-spacing: 0.3px;
        }
        QLabel#status_text {
            font-size: 11px;
            color: #64748b;
            padding-left: 4px;
        }
        QLabel#blbl {
            font-size: 11px;
            color: #64748b;
        }
        QLabel#hint {
            font-size: 10px;
            color: #334155;
        }

        /* ── Divider ── */
        QFrame#divider {
            background: rgba(99,102,241,0.15);
            border: none;
        }

        /* ── Progress bar ── */
        QProgressBar {
            background: rgba(30,41,59,0.8);
            border: none;
            border-radius: 3px;
            height: 4px;
            text-align: center;
        }
        QProgressBar::chunk {
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:0,
                stop:0 #6366f1, stop:1 #8b5cf6
            );
            border-radius: 3px;
        }

        /* ── Combo box ── */
        QComboBox {
            background: rgba(30,41,59,0.9);
            color: #e2e8f0;
            border: 1px solid rgba(99,102,241,0.25);
            border-radius: 7px;
            padding: 5px 10px;
            font-size: 12px;
        }
        QComboBox:hover { border-color: rgba(99,102,241,0.55); }
        QComboBox::drop-down { border: none; width: 18px; }
        QComboBox QAbstractItemView {
            background: #1e293b;
            color: #e2e8f0;
            border: 1px solid rgba(99,102,241,0.30);
            selection-background-color: #4f46e5;
            outline: none;
        }

        /* ── Buttons — shared base ── */
        QPushButton {
            border-radius: 9px;
            padding: 9px 16px;
            font-weight: 600;
            font-size: 12px;
            border: none;
            letter-spacing: 0.2px;
        }

        /* ── Start button — gradient fill ── */
        QPushButton#btn_start {
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:0,
                stop:0 #4f46e5, stop:1 #7c3aed
            );
            color: white;
        }
        QPushButton#btn_start:hover {
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:0,
                stop:0 #6366f1, stop:1 #8b5cf6
            );
        }
        QPushButton#btn_start:pressed {
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:0,
                stop:0 #4338ca, stop:1 #6d28d9
            );
            padding-top: 10px;
            padding-bottom: 8px;
        }
        QPushButton#btn_start:disabled {
            background: rgba(30,41,59,0.7);
            color: #334155;
        }

        /* ── Open button — outlined ── */
        QPushButton#btn_open {
            background: rgba(79,70,229,0.10);
            color: #818cf8;
            border: 1px solid rgba(99,102,241,0.30);
        }
        QPushButton#btn_open:hover {
            background: rgba(79,70,229,0.20);
            border-color: rgba(99,102,241,0.55);
        }
        QPushButton#btn_open:pressed {
            background: rgba(79,70,229,0.30);
            padding-top: 10px;
            padding-bottom: 8px;
        }
        QPushButton#btn_open:disabled {
            color: #1e293b;
            border-color: rgba(30,41,59,0.8);
            background: transparent;
        }

        /* ── Stop button — danger outlined ── */
        QPushButton#btn_stop {
            background: rgba(239,68,68,0.08);
            color: #f87171;
            border: 1px solid rgba(239,68,68,0.22);
        }
        QPushButton#btn_stop:hover {
            background: rgba(239,68,68,0.16);
            border-color: rgba(239,68,68,0.45);
        }
        QPushButton#btn_stop:pressed {
            background: rgba(239,68,68,0.24);
            padding-top: 10px;
            padding-bottom: 8px;
        }
        QPushButton#btn_stop:disabled {
            color: #1e293b;
            border-color: rgba(30,41,59,0.8);
            background: transparent;
        }

        /* ── Close button (X) ── */
        QPushButton#close_btn {
            background: transparent;
            color: #64748b;
            border: none;
            border-radius: 4px;
            padding: 2px;
            font-size: 14px;
            font-weight: normal;
        }
        QPushButton#close_btn:hover {
            background: rgba(239,68,68,0.2);
            color: #f87171;
        }
        QPushButton#close_btn:pressed {
            background: rgba(239,68,68,0.3);
            color: #ef4444;
        }
    """

    def __init__(self) -> None:
        super().__init__()
        self._proc         : subprocess.Popen | None = None
        self._wait_thread  : _WaitThread | None      = None
        self._watch_thread : _WatchThread | None     = None
        self._browser_procs: set[int] = set()   # PIDs of opened isolated browser windows
        self._browsers     = _detect_browsers()
        self._icon         = _make_icon()
        self._crash_count  = 0

        self._progress_timer = QTimer(self)
        self._progress_timer.setInterval(120)
        self._progress_timer.timeout.connect(self._tick_progress)
        self._progress_value = 0

        self.setWindowTitle("Lytrize")
        self.setWindowIcon(self._icon)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(390, 310)
        self.setStyleSheet(self._QSS)

        self._build_ui()
        self._build_tray()
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()   # show right away so minimizing to tray works pre-start
        self._connect_signals()
        self._apply_window_shadow()

        self._drag_pos = None


    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None


    def _apply_window_shadow(self) -> None:
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(32)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 160))
        self._card.setGraphicsEffect(shadow)


    def _build_ui(self) -> None:
        """Construct and lay out all widgets inside a rounded card."""

        self._card = QWidget(self)
        self._card.setObjectName("card")
        self._card.setGeometry(10, 10, self.width() - 20, self.height() - 20)

        lbl_icon = QLabel()
        lbl_icon.setPixmap(self._icon.pixmap(28, 28))
        lbl_icon.setAlignment(Qt.AlignCenter)

        lbl_title = QLabel("Lytrize")
        lbl_title.setObjectName("title")

        lbl_sub = QLabel("Analytics Desktop")
        lbl_sub.setObjectName("subtitle")

        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        title_col.addWidget(lbl_title)
        title_col.addWidget(lbl_sub)

        self.close_btn = QPushButton("✕")
        self.close_btn.setObjectName("close_btn")
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setFlat(True)
        self.close_btn.clicked.connect(self.close)   # triggers closeEvent

        header = QHBoxLayout()
        header.setSpacing(10)
        header.addStretch()
        header.addWidget(lbl_icon)
        header.addLayout(title_col)
        header.addStretch()
        header.addWidget(self.close_btn)

        self._dot = _PulseDot("#64748b", 9, self._card)
        self._dot.setFixedSize(9, 9)

        self.lbl_status = QLabel("Stopped")
        self.lbl_status.setObjectName("status_text")

        status_row = QHBoxLayout()
        status_row.setSpacing(6)
        status_row.addStretch()
        status_row.addWidget(self._dot, alignment=Qt.AlignVCenter)
        status_row.addWidget(self.lbl_status)
        status_row.addStretch()

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(4)
        self.progress.setVisible(False)

        divider = QFrame()
        divider.setObjectName("divider")
        divider.setFrameShape(QFrame.HLine)
        divider.setFixedHeight(1)

        prefs = _load_prefs()
        # Always show the "Open with:" dropdown so the user can pick a browser
        # even when only one (or only the OS-default fallback) is detected.
        self.combo_browser: QComboBox | None = None
        lbl_b = QLabel("Open with:")
        lbl_b.setObjectName("blbl")
        self.combo_browser = QComboBox()
        saved_binary = prefs.get("browser_binary", "")
        selected_idx = 0
        for i, browser in enumerate(self._browsers):
            self.combo_browser.addItem(browser["name"], userData=browser["binary"])
            if browser["binary"] == saved_binary:
                selected_idx = i
        self.combo_browser.setCurrentIndex(selected_idx)

        self.btn_start = QPushButton("▶  Start")
        self.btn_start.setObjectName("btn_start")
        self.btn_start.setFixedHeight(38)

        self.btn_open = QPushButton("⬡  Open App")
        self.btn_open.setObjectName("btn_open")
        self.btn_open.setFixedHeight(36)

        self.btn_stop = QPushButton("■  Stop && Quit")
        self.btn_stop.setObjectName("btn_stop")
        self.btn_stop.setFixedHeight(36)

        self.btn_open.setEnabled(False)
        self.btn_stop.setEnabled(False)

        hint = QLabel("All data is stored locally on this device.")
        hint.setObjectName("hint")
        hint.setAlignment(Qt.AlignCenter)
        hint.setWordWrap(True)

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(24, 20, 24, 18)
        card_layout.setSpacing(10)

        card_layout.addLayout(header)
        card_layout.addLayout(status_row)
        card_layout.addWidget(self.progress)
        card_layout.addWidget(divider)

        if self.combo_browser is not None:
            brow = QHBoxLayout()
            brow.addWidget(lbl_b)
            brow.addWidget(self.combo_browser, stretch=1)
            card_layout.addLayout(brow)

        card_layout.addWidget(self.btn_start)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addWidget(self.btn_open)
        btn_row.addWidget(self.btn_stop)
        card_layout.addLayout(btn_row)

        card_layout.addWidget(hint)

    def _build_tray(self) -> None:
        """Create the system tray icon and context menu."""
        self.tray = QSystemTrayIcon(self._icon, self)
        self.tray.setToolTip("Lytrize")

        tray_menu = QMenu()
        tray_menu.addAction("Open App",     self._open_app)
        tray_menu.addSeparator()
        tray_menu.addAction("Stop && Quit", self._stop_and_quit)
        self.tray.setContextMenu(tray_menu)

    def _connect_signals(self) -> None:
        """Wire all widget and tray signals to their slots."""
        self.btn_start.clicked.connect(self._start)
        self.btn_open.clicked.connect(self._open_app)
        self.btn_stop.clicked.connect(self._stop_and_quit)
        self.tray.activated.connect(self._tray_activated)

        if self.combo_browser is not None:
            self.combo_browser.currentIndexChanged.connect(self._on_browser_changed)


    def _set_status(self, text: str, dot_colour: str = "#64748b",
                    pulse: bool = False) -> None:
        """Update the status label, dot colour, and optionally start pulsing."""
        self.lbl_status.setText(text)
        if pulse:
            self._dot.start(dot_colour)
        else:
            self._dot.stop(dot_colour)

    def _is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None


    def _selected_browser(self) -> dict:
        if self.combo_browser is not None:
            return self._browsers[self.combo_browser.currentIndex()]
        return self._browsers[0]

    def _on_browser_changed(self, idx: int) -> None:
        if self.combo_browser is None:
            return
        prefs = _load_prefs()
        prefs["browser_binary"] = self.combo_browser.itemData(idx)
        _save_prefs(prefs)


    def _start_progress(self) -> None:
        """Show and animate the startup progress bar."""
        self._progress_value = 0
        self.progress.setValue(0)
        self.progress.setVisible(True)
        self._progress_timer.start()

    def _tick_progress(self) -> None:
        """Advance the progress bar with eased deceleration toward 92 %."""
        target = 92
        gap    = target - self._progress_value
        step   = max(1, int(gap * 0.07))    # eased: fast at start, slow at end
        self._progress_value = min(self._progress_value + step, target)
        self.progress.setValue(self._progress_value)

    def _finish_progress(self) -> None:
        """Snap the progress bar to 100 % then hide after a short delay."""
        self._progress_timer.stop()
        self.progress.setValue(100)
        QTimer.singleShot(500, lambda: self.progress.setVisible(False))


    def _terminate_stale_backend(self) -> None:
        """
        Terminate a leftover Lytrize backend from a previous session that is
        still holding APP_PORT (e.g. after a crash or a forced shutdown).
        Without this, the next launch dies with Streamlit's
        "Port ... is not available" (exit 1). Only processes whose command line
        matches *our* backend (`streamlit run <APP_PY>`) are touched, so other
        applications on the same port are left alone.
        """
        if _is_windows():
            procs = _windows_processes()
            if not procs:
                return
            helper_shells = {"powershell.exe", "pwsh.exe", "cmd.exe", "conhost.exe"}
            needle_app = str(APP_PY)
            for proc in procs:
                cmdline = proc.get("CommandLine")
                name = (proc.get("Name") or "").lower()
                if not isinstance(cmdline, str) or name in helper_shells:
                    continue
                if "streamlit" in cmdline and needle_app in cmdline:
                    try:
                        pid = int(proc.get("ProcessId"))
                    except (TypeError, ValueError):
                        continue
                    if pid == os.getpid():
                        continue
                    logging.getLogger(__name__).warning(
                        "Terminating stale Lytrize backend (pid %s) holding port %s",
                        pid, APP_PORT,
                    )
                    self._kill_process_tree(pid)
        else:
            try:
                subprocess.run(
                    ["pkill", "-f", f"streamlit run {APP_PY}"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10,
                )
            except (FileNotFoundError, subprocess.SubprocessError, OSError) as exc:
                logging.getLogger(__name__).debug(
                    "Suppressed error killing stale backend: %s", exc, exc_info=True
                )


    def _start(self) -> None:
        """
        Launch the Streamlit backend subprocess.

        Reads backend/.env so any custom environment variables (e.g.
        LYTRIZE_DB_PATH) are available to the subprocess without
        modifying the system environment.

        After launching, two threads are started:
            _WaitThread  — polls TCP APP_HOST:APP_PORT until Streamlit accepts connections.
            _WatchThread — blocks on proc.wait() to detect unexpected exits.
        """
        if self._is_running():
            return

        # Self-heal: a stale backend from a previous session may still hold
        # APP_PORT, which would make Streamlit exit(1) with
        # "Port ... is not available". Clear our own leftovers first.
        if _port_in_use(APP_HOST, APP_PORT):
            self._terminate_stale_backend()
            time.sleep(1.0)
            if _port_in_use(APP_HOST, APP_PORT):
                logging.getLogger(__name__).warning(
                    "Port %s is still in use by another application; "
                    "the backend may fail to start (see streamlit.log).",
                    APP_PORT,
                )

        self.btn_start.setEnabled(False)
        self._set_status("Starting…", "#f59e0b", pulse=True)
        self._start_progress()
        self._crash_count = 0
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        try:
            DATA_DIR.chmod(0o700)
        except Exception as exc:
            logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
            pass

        if self._wait_thread is not None:
            try:
                self._wait_thread.ready.disconnect()
                self._wait_thread.timeout.disconnect()
            except Exception as exc:
                logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
                pass
            self._wait_thread.quit()
            self._wait_thread.wait(2000)
            self._wait_thread = None

        if self._watch_thread is not None:
            try:
                self._watch_thread.crashed.disconnect()
            except Exception as exc:
                logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
                pass
            self._watch_thread.cancel()
            self._watch_thread.quit()
            self._watch_thread.wait(2000)
            self._watch_thread = None

        env = os.environ.copy()
        env["LYTRIZE_DB_PATH"] = str(DB_PATH)

        env_file = BASE / "backend" / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.split("#")[0].strip().strip('"').strip("'")
                if key:
                    env[key] = val

        python = str(VENV_PY) if VENV_PY.exists() else ("python" if _is_windows() else "python3")

        # On an installed Linux build the venv may have been re-linked to a
        # different Python minor version, so we explicitly prepend its
        # site-packages. Unnecessary on Windows (pythonw resolves its own venv).
        if not _is_windows():
            import glob as _glob
            _sp = _glob.glob("/opt/lytrize/venv/lib/python*/site-packages")
            if _sp:
                _existing = env.get("PYTHONPATH", "")
                env["PYTHONPATH"] = _sp[0] + (":" + _existing if _existing else "")

        _log_path = DATA_DIR / "streamlit.log"
        try:
            _log_fh = open(_log_path, "w", buffering=1)  # line-buffered
        except Exception:
            _log_fh = open(os.devnull, "w")

        # Spawn Streamlit without any console window: on Windows we use
        # CREATE_NO_WINDOW (so the backend leaves no visible shell) and
        # CREATE_NEW_PROCESS_GROUP (so taskkill /T can target the tree later).
        # On POSIX we use start_new_session to make the subprocess a process
        # group leader, matching the original behaviour.
        popen_kwargs: dict = dict(
            cwd=str(APP_PY.parent),
            env=env,
            stdout=_log_fh,
            stderr=_log_fh,
        )
        if _is_windows():
            popen_kwargs["creationflags"] = (
                getattr(subprocess, "CREATE_NO_WINDOW", 0)
                | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            )
        else:
            popen_kwargs["start_new_session"] = True

        self._proc = subprocess.Popen(
            [
                python, "-m", "streamlit", "run", str(APP_PY),
                "--server.port",                 str(APP_PORT),
                "--server.address",              APP_HOST,
                "--server.headless",             "true",
                "--server.fileWatcherType",      "none",
                "--server.runOnSave",            "false",
                "--server.enableCORS",           "false",
                "--server.enableXsrfProtection", "true",
                "--browser.gatherUsageStats",    "false",
                "--browser.serverAddress",       APP_HOST,
                "--client.toolbarMode",          "minimal",
                "--runner.fastReruns",           "true",
                "--runner.magicEnabled",         "false",
            ],
            **popen_kwargs,
        )
        self.tray.show()

        self._wait_thread = _WaitThread(self)
        self._wait_thread.ready.connect(self._on_ready)
        self._wait_thread.timeout.connect(self._on_timeout)
        self._wait_thread.start()

        self._watch_thread = _WatchThread(self._proc)
        self._watch_thread.crashed.connect(self._on_crashed)
        self._watch_thread.start()

    def _on_ready(self) -> None:
        """Slot: Streamlit is accepting connections — update UI and open browser."""
        self._finish_progress()
        self._set_status("Running", "#10b981", pulse=True)
        self.btn_stop.setEnabled(True)
        self.btn_open.setEnabled(True)
        self.tray.showMessage(
            "Lytrize", "App is ready.",
            QSystemTrayIcon.Information, 2000,
        )
        self._open_app()

    def _on_timeout(self) -> None:
        """Slot: Streamlit did not start within the polling timeout."""
        self._finish_progress()
        self._set_status("Timed out — check terminal for errors", "#ef4444")
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(True)

    def _on_crashed(self, code: int) -> None:
        """Slot: Streamlit subprocess exited unexpectedly."""
        self._progress_timer.stop()
        self.progress.setVisible(False)
        self._crash_count += 1
        crash_msg = f"Crashed (exit {code}) — click Start to retry"
        if _port_in_use(APP_HOST, APP_PORT):
            crash_msg += f" — port {APP_PORT} is in use (see streamlit.log)"
        self._set_status(crash_msg, "#ef4444")
        self.btn_start.setEnabled(True)
        self.btn_open.setEnabled(False)
        self.btn_stop.setEnabled(False)
        if self.tray.isVisible():
            self.tray.showMessage(
                "Lytrize",
                f"Server exited unexpectedly (code {code}). Click Start to restart.",
                QSystemTrayIcon.Warning,
                4000,
            )


    def _open_app(self) -> None:
        """Open the Lytrize web UI in the selected browser and track its PID."""
        browser  = self._selected_browser()
        url      = APP_URL
        proc_kwargs: dict = {}
        if _is_windows():
            # Keep console windows away from browser launches too.
            proc_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        else:
            # Make the browser its own process-group leader so the POSIX
            # killpg() in _kill_process_tree() targets the browser tree only
            # (never this launcher).
            proc_kwargs["start_new_session"] = True

        if browser["chromium"]:
            _CHROMIUM_PROFILE.mkdir(parents=True, exist_ok=True)
            if not _is_windows():
                try:
                    _CHROMIUM_PROFILE.chmod(0o700)
                except Exception as exc:
                    logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
            _devnull = open(os.devnull, "w")
            p = subprocess.Popen(
                [
                    browser["binary"],
                    f"--app={url}",
                    f"--user-data-dir={_CHROMIUM_PROFILE}",
                    "--start-maximized",
                    "--disable-extensions",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-sync",
                ],
                stdout=_devnull,
                stderr=_devnull,
                **proc_kwargs,
            )
            self._browser_procs.add(p.pid)
            _devnull.close()
        elif browser["binary"] == _DEFAULT_HANDLER:
            # Default OS handler: Windows uses the shell's default handler via
            # os.startfile(); Linux delegates to xdg-open.
            if _is_windows():
                os.startfile(url)
            else:
                _devnull = open(os.devnull, "w")
                subprocess.Popen(
                    ["xdg-open", url],
                    stdout=_devnull,
                    stderr=_devnull,
                )
                _devnull.close()
        else:
            _ensure_firefox_profile(_FIREFOX_PROFILE)
            _devnull = open(os.devnull, "w")
            p = subprocess.Popen(
                [
                    browser["binary"],
                    "--new-instance",
                    "--profile", str(_FIREFOX_PROFILE),
                    "--width", "1280",
                    "--height", "900",
                    "--new-window",
                    url,
                ],
                stdout=_devnull,
                stderr=_devnull,
                **proc_kwargs,
            )
            self._browser_procs.add(p.pid)
            _devnull.close()


    def _kill_process_tree(self, pid: int) -> None:
        """Terminate a process and all its descendants on either OS."""
        if pid is None:
            return
        try:
            if _is_windows():
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            else:
                pgid = os.getpgid(pid)
                os.killpg(pgid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError) as exc:
            logging.getLogger(__name__).debug(
                "Suppressed error killing pid %s: %s", pid, exc, exc_info=True
            )


    def _kill_backend(self) -> None:
        """Stop the Streamlit backend and reap its watch thread."""
        if self._proc is not None and self._proc.poll() is None:
            self._kill_process_tree(self._proc.pid)
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                if not _is_windows():
                    try:
                        os.killpg(os.getpgid(self._proc.pid), signal.SIGKILL)
                    except (ProcessLookupError, OSError):
                        pass
                self._proc.wait()
        self._proc = None
        if self._watch_thread is not None:
            try:
                self._watch_thread.quit()
                self._watch_thread.wait(2000)
            except Exception as exc:
                logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
            self._watch_thread = None


    def _kill_by_pattern(self, pattern: str) -> None:
        """
        Windows: terminate every process tree whose command line references
        ``pattern`` (our isolated browser profile directory).

        Chromium/Firefox hand off to a new process on Windows, so the PID we
        originally spawned is usually dead by the time "Stop & Quit" runs while
        the real browser window lives under a different PID. Every browser
        process of our isolated instance carries the profile path in its
        command line (``--user-data-dir=...`` / ``--profile ...``), so matching
        on that path reliably finds the surviving tree. Helper shells are
        excluded so we never kill the PowerShell instance doing the lookup.
        """
        if not pattern:
            return
        procs = _windows_processes()
        if not procs:
            return

        helper_shells = {"powershell.exe", "pwsh.exe", "cmd.exe", "conhost.exe"}
        by_id: dict[int, dict] = {}
        matched: set[int] = set()
        for proc in procs:
            try:
                pid = int(proc.get("ProcessId"))
            except (TypeError, ValueError):
                continue
            cmdline = proc.get("CommandLine")
            name = (proc.get("Name") or "").lower()
            by_id[pid] = proc
            if (
                isinstance(cmdline, str)
                and pattern in cmdline
                and name not in helper_shells
            ):
                matched.add(pid)

        if not matched:
            return

        # Kill only the *roots* of matched subtrees: taskkill /T then takes
        # down every descendant, so children are not killed redundantly.
        roots: list[int] = []
        for pid in matched:
            ancestor_matched = False
            seen: set[int] = set()
            current = by_id.get(pid)
            while current is not None:
                try:
                    parent = int(current.get("ParentProcessId"))
                except (TypeError, ValueError):
                    break
                if parent in seen:          # defensive: cyclic parent chain
                    break
                seen.add(parent)
                if parent in matched:
                    ancestor_matched = True
                    break
                current = by_id.get(parent)
            if not ancestor_matched:
                roots.append(pid)

        for pid in roots:
            self._kill_process_tree(pid)


    def _kill_browsers(self) -> None:
        """
        Close every isolated browser window this launcher opened.

        Primary strategy (Windows): match surviving browser processes on the
        unique isolated profile path, since the originally spawned PID may have
        exited after a single-instance handoff. The tracked PIDs are still
        killed first as a fast path. On Linux the browsers are launched as
        their own session leaders, so a process-group kill reaches the whole
        tree.
        """
        for pid in list(self._browser_procs):
            self._kill_process_tree(pid)

        if not _is_windows():
            # POSIX escalation: SIGTERM is usually enough for a browser, but a
            # hung one must not survive "Stop & Quit". Give it a moment, then
            # SIGKILL any process group that is still alive.
            time.sleep(1.0)
            for pid in list(self._browser_procs):
                try:
                    os.kill(pid, 0)          # liveness probe (no signal sent)
                except (ProcessLookupError, PermissionError, OSError):
                    continue                 # already gone (or unreapable)
                try:
                    os.killpg(os.getpgid(pid), signal.SIGKILL)
                except (ProcessLookupError, PermissionError, OSError) as exc:
                    logging.getLogger(__name__).debug(
                        "Suppressed error SIGKILLing browser group %s: %s",
                        pid, exc, exc_info=True,
                    )

        self._browser_procs.clear()

        if _is_windows():
            # Both profile roots are swept so a mid-session browser switch
            # cannot leave an orphaned window behind.
            self._kill_by_pattern(str(_CHROMIUM_PROFILE))
            self._kill_by_pattern(str(_FIREFOX_PROFILE))


    def _stop_and_quit(self) -> None:
        """
        Terminate the Streamlit backend (and all its children) AND the isolated
        browser windows, then exit. Cross-platform: on Windows we use
        ``taskkill /T /F`` against the process tree; on Linux a process-group
        kill. This ensures no background process or browser window survives
        "Stop & Quit".
        """
        self._progress_timer.stop()

        if self._watch_thread is not None:
            try:
                self._watch_thread.crashed.disconnect()
            except Exception as exc:
                logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
            self._watch_thread.cancel()

        self._kill_backend()
        self._kill_browsers()

        self.tray.hide()
        QApplication.quit()


    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.DoubleClick:
            if self._is_running():
                self._open_app()
            else:
                self.show()
                self.raise_()
                self.activateWindow()


    def changeEvent(self, event) -> None:  # noqa: N802
        """Minimize to the system tray whenever the window is minimized
        (taskbar click or titlebar minimize), instead of staying on the taskbar."""
        if event.type() == QEvent.WindowStateChange and self.isMinimized():
            self.hide()
            if self.tray.isVisible():
                self.tray.showMessage(
                    "Lytrize",
                    "Minimized to the system tray. Right-click the tray icon to restore.",
                    QSystemTrayIcon.Information,
                    2000,
                )
        super().changeEvent(event)


    def closeEvent(self, event) -> None:  # noqa: N802
        if self._is_running():
            event.ignore()
            self.hide()
            self.tray.showMessage(
                "Lytrize",
                "Still running in the system tray. Right-click to quit.",
                QSystemTrayIcon.Information,
                3000,
            )
        else:
            event.accept()



if __name__ == "__main__":
    QApplication.setApplicationName("Lytrize")
    QApplication.setOrganizationName("Lytrize")

    app = QApplication(sys.argv)
    app.setApplicationDisplayName("Lytrize")
    app.setDesktopFileName("lytrize")
    app.setQuitOnLastWindowClosed(False)

    icon = _make_icon()
    app.setWindowIcon(icon)

    window = Launcher()
    window.show()
    sys.exit(app.exec())
