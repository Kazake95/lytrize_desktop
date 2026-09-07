"""desktop/launcher.py — CLI entry point for the installed Lytrize launcher.

Cross-platform: on Linux it spawns the venv Python and desktop/gui.py; on
Windows it is primarily a fallback (the installer normally creates a Start
Menu / Desktop shortcut straight to gui.py via pythonw.exe). It still works
correctly from a shell on either OS.
"""


import subprocess
import sys
from pathlib import Path


BASE    = Path(__file__).resolve().parent.parent  # repo root or install base
_is_win = sys.platform.startswith("win")

if _is_win:
    VENV_PY = BASE / "venv" / "Scripts" / "pythonw.exe"
else:
    VENV_PY = BASE / "venv" / "bin" / "python"

GUI      = BASE / "desktop" / "gui.py"


def _resolve_python() -> str:
    """Return the path to the Python interpreter to use."""
    if VENV_PY.exists():
        return str(VENV_PY)
    return "python" if _is_win else "python3"


if __name__ == "__main__":
    python = _resolve_python()
    result = subprocess.run([python, str(GUI)] + sys.argv[1:])
    sys.exit(result.returncode)
