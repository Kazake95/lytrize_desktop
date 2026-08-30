"""modules/utils/paths.py -- Cross-platform data & cache directory resolution.

Centralises where Lytrize stores persistent data (SQLite DB, launcher prefs,
browser profiles, logs) and transient/per-user caches (parquet snapshots).

Linux (matches the original behaviour):
    data_dir     -> ~/.local/share/lytrize
    cache_dir    -> $XDG_CACHE_HOME/lytrize  (or ~/.cache/lytrize)
    snapshot_dir -> $XDG_RUNTIME_DIR/lytrize when available, else cache_dir.

Windows:
    data_dir     -> %APPDATA%\\Lytrize           (Roaming)
    cache_dir    -> %LOCALAPPDATA%\\Lytrize      (Local)
    snapshot_dir -> cache_dir

Anything may be overridden by LYTRIZE_DB_PATH / LYTRIZE_CACHE_DIR env vars
(for testing and so the launcher can pin the exact DB location it uses).
"""
import os
import pathlib


def is_windows() -> bool:
    """True when running on Microsoft Windows."""
    return os.name == "nt"


def data_dir() -> pathlib.Path:
    """Directory holding persistent user data (DB, prefs, profiles, logs)."""
    override = os.environ.get("LYTRIZE_DB_PATH")
    if override:
        return pathlib.Path(override).parent

    if is_windows():
        base = os.environ.get("APPDATA")
        if not base:
            base = str(pathlib.Path.home() / "AppData" / "Roaming")
        return pathlib.Path(base) / "Lytrize"

    return pathlib.Path.home() / ".local" / "share" / "lytrize"


def cache_dir() -> pathlib.Path:
    """Directory for transient / large caches (parquet snapshots)."""
    override = os.environ.get("LYTRIZE_CACHE_DIR")
    if override:
        return pathlib.Path(override)

    if is_windows():
        base = os.environ.get("LOCALAPPDATA")
        if not base:
            base = str(pathlib.Path.home() / "AppData" / "Local")
        return pathlib.Path(base) / "Lytrize"

    cache_home = os.environ.get("XDG_CACHE_HOME")
    if cache_home:
        return pathlib.Path(cache_home) / "lytrize"
    return pathlib.Path.home() / ".cache" / "lytrize"


def snapshot_dir() -> pathlib.Path:
    """Parent directory for per-user DataFrame parquet snapshots."""
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if runtime:
        return pathlib.Path(runtime) / "lytrize"
    return cache_dir()