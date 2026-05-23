"""
modules/playwright_renderer.py — HTML → PNG renderer using the system browser.

Uses the user's already-installed Chromium or Firefox in headless mode.
No extra browser download or playwright dependency required.

Supported browsers (tried in order):
  Chromium-based : google-chrome, google-chrome-stable, chromium, chromium-browser,
                   brave-browser, brave-browser-stable, microsoft-edge
  Firefox        : firefox, firefox-esr

Both support headless screenshot natively:
  Chromium  : --headless=new --screenshot=<file> <url>
  Firefox   : --headless --screenshot <file> <url>
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

# (binary, is_chromium) — tried in preference order
_BROWSER_CANDIDATES: list[tuple[str, bool]] = [
    ("google-chrome",        True),
    ("google-chrome-stable", True),
    ("chromium",             True),
    ("chromium-browser",     True),
    ("brave-browser",        True),
    ("brave-browser-stable", True),
    ("microsoft-edge",       True),
    ("firefox",              False),
    ("firefox-esr",          False),
]


def _find_browser() -> tuple[str, bool] | None:
    """
    Return (binary_path, is_chromium) for the first installed browser, or None.
    """
    for binary, is_chromium in _BROWSER_CANDIDATES:
        path = shutil.which(binary)
        if path:
            return path, is_chromium
    return None


def render_html_to_png(
    html_bytes: bytes,
    viewport_width: int = 1600,
    viewport_height: int = 1200,
) -> bytes:
    """
    Render a self-contained HTML page to PNG using the system browser.

    Writes the HTML to a temp file, launches the browser in headless mode,
    takes a full-page screenshot, reads and returns the PNG bytes.

    Raises RuntimeError if no supported browser is found or the screenshot fails.
    """
    browser = _find_browser()
    if browser is None:
        raise RuntimeError(
            "No supported browser found for PNG export. "
            "Install Chromium, Google Chrome, or Firefox and try again.\n"
            "  sudo apt install chromium-browser\n"
            "  # or: sudo apt install firefox"
        )

    binary, is_chromium = browser

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path  = Path(tmp)
        html_file = tmp_path / "dashboard.html"
        png_file  = tmp_path / "screenshot.png"
        html_file.write_bytes(html_bytes)

        if is_chromium:
            cmd = [
                binary,
                "--headless=new",
                "--disable-gpu",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-software-rasterizer",
                f"--window-size={viewport_width},{viewport_height}",
                f"--screenshot={png_file}",
                html_file.as_uri(),
            ]
        else:
            # Firefox headless screenshot
            cmd = [
                binary,
                "--headless",
                "--screenshot", str(png_file),
                f"--window-size={viewport_width},{viewport_height}",
                html_file.as_uri(),
            ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"Browser timed out while rendering PNG ({binary}). "
                "Try again or use a smaller dashboard."
            )
        except FileNotFoundError:
            raise RuntimeError(
                f"Browser binary not found: {binary}. "
                "Install Chromium or Firefox and try again."
            )

        if not png_file.exists() or png_file.stat().st_size == 0:
            stderr = result.stderr.decode(errors="replace")[:400]
            raise RuntimeError(
                f"Browser screenshot failed (exit {result.returncode}). "
                f"Browser: {binary}\n{stderr}"
            )

        return png_file.read_bytes()
