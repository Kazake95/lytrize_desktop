"""
modules/ui/font_manager.py – Central font registry & preview helper.

Provides a single source of truth for all fonts the app can use,
with detection of system-installed fonts and a reusable Streamlit
font-selector that shows a live preview of each font face.
"""

from __future__ import annotations

import base64
import os
import re
from typing import Any

import streamlit as st

FONT_ENTRIES: list[dict[str, str]] = [
    {
        "name": "Inter",
        "stack": "'Inter-Variable', 'Inter', 'Helvetica Neue', Arial, sans-serif",
        "category": "Sans-serif",
    },
    {
        "name": "Source Sans 3",
        "stack": "'Source Sans 3', 'Liberation Sans', Arimo, Arial, sans-serif",
        "category": "Sans-serif",
    },
    {
        "name": "Noto Sans",
        "stack": "'Noto Sans', 'DejaVu Sans', 'Liberation Sans', Arial, sans-serif",
        "category": "Sans-serif",
    },
    {
        "name": "DejaVu Sans",
        "stack": "'DejaVu Sans', 'Liberation Sans', Arial, sans-serif",
        "category": "Sans-serif",
    },
    {
        "name": "Lato",
        "stack": "Lato, 'DejaVu Sans', 'Liberation Sans', Arial, sans-serif",
        "category": "Sans-serif",
    },
    {
        "name": "Ubuntu",
        "stack": "Ubuntu, 'DejaVu Sans', 'Liberation Sans', sans-serif",
        "category": "Sans-serif",
    },
    {
        "name": "Arial",
        "stack": "Arial, 'Liberation Sans', Arimo, 'DejaVu Sans', sans-serif",
        "category": "Sans-serif",
    },
    {
        "name": "Arial Black",
        "stack": "'Arial Black', Impact, 'DejaVu Sans', sans-serif",
        "category": "Sans-serif",
    },
    {
        "name": "Calibri",
        "stack": "Calibri, Carlito, 'Liberation Sans', 'DejaVu Sans', sans-serif",
        "category": "Sans-serif",
    },
    {
        "name": "Verdana",
        "stack": "Verdana, 'DejaVu Sans', Geneva, sans-serif",
        "category": "Sans-serif",
    },
    {
        "name": "Oswald",
        "stack": "Oswald, 'DejaVu Sans', Arial, sans-serif",
        "category": "Display",
    },
    {
        "name": "Barlow Condensed",
        "stack": "'Barlow Condensed', 'DejaVu Sans', Arial, sans-serif",
        "category": "Display",
    },
    {
        "name": "Noto Serif",
        "stack": "'Noto Serif', 'DejaVu Serif', 'Liberation Serif', Times, serif",
        "category": "Serif",
    },
    {
        "name": "DejaVu Serif",
        "stack": "'DejaVu Serif', 'Liberation Serif', Times, serif",
        "category": "Serif",
    },
    {
        "name": "EB Garamond",
        "stack": "'EB Garamond', 'DejaVu Serif', 'Liberation Serif', Georgia, serif",
        "category": "Serif",
    },
    {
        "name": "Georgia",
        "stack": "Georgia, 'DejaVu Serif', 'Liberation Serif', serif",
        "category": "Serif",
    },
    {
        "name": "Times New Roman",
        "stack": "'Times New Roman', 'Liberation Serif', Tinos, 'DejaVu Serif', serif",
        "category": "Serif",
    },
    {
        "name": "Fira Code",
        "stack": "'Fira Code', 'DejaVu Sans Mono', 'Liberation Mono', Consolas, monospace",
        "category": "Monospace",
    },
    {
        "name": "DejaVu Sans Mono",
        "stack": "'DejaVu Sans Mono', 'Liberation Mono', Consolas, monospace",
        "category": "Monospace",
    },
    {
        "name": "JetBrains Mono",
        "stack": "'JetBrains Mono', 'DejaVu Sans Mono', 'Liberation Mono', Consolas, monospace",
        "category": "Monospace",
    },
    {
        "name": "Liberation Mono",
        "stack": "'Liberation Mono', 'DejaVu Sans Mono', Consolas, monospace",
        "category": "Monospace",
    },
    {
        "name": "Courier New",
        "stack": "'Courier New', 'Liberation Mono', 'DejaVu Sans Mono', monospace",
        "category": "Monospace",
    },
    {
        "name": "Andale Mono",
        "stack": "'Andale Mono', 'DejaVu Sans Mono', monospace",
        "category": "Monospace",
    },
    {
        "name": "Comic Sans MS",
        "stack": "'Comic Sans MS', 'Comic Sans', cursive, sans-serif",
        "category": "Display",
    },
    {
        "name": "Impact",
        "stack": "Impact, 'Arial Narrow', 'DejaVu Sans', sans-serif",
        "category": "Display",
    },
    {
        "name": "Trebuchet MS",
        "stack": "'Trebuchet MS', 'Liberation Sans', Ubuntu, sans-serif",
        "category": "Sans-serif",
    },
    {
        "name": "Helvetica",
        "stack": "'Helvetica Neue', Helvetica, Arial, 'Liberation Sans', sans-serif",
        "category": "Sans-serif",
    },
    {
        "name": "Palatino Linotype",
        "stack": "'Palatino Linotype', 'Book Antiqua', Palatino, 'Liberation Serif', serif",
        "category": "Serif",
    },
    {
        "name": "Candara",
        "stack": "'Candara', 'Segoe UI', 'Liberation Sans', Arial, sans-serif",
        "category": "Sans-serif",
    },
    {
        "name": "Corbel",
        "stack": "'Corbel', 'Segoe UI', 'Liberation Sans', Arial, sans-serif",
        "category": "Sans-serif",
    },
    {
        "name": "Constantia",
        "stack": "'Constantia', Georgia, 'DejaVu Serif', 'Liberation Serif', serif",
        "category": "Serif",
    },
    {
        "name": "Lucida Console",
        "stack": "'Lucida Console', 'Lucida Sans Typewriter', 'Liberation Mono', monospace",
        "category": "Monospace",
    },
    {
        "name": "Consolas",
        "stack": "'Consolas', 'Liberation Mono', 'Courier New', monospace",
        "category": "Monospace",
    },
    {
        "name": "Sora",
        "stack": "Sora, 'Sora Medium', 'Sora SemiBold', sans-serif",
        "category": "Sans-serif",
    },
    {
        "name": "Cambria",
        "stack": "'Cambria', Georgia, 'DejaVu Serif', 'Liberation Serif', serif",
        "category": "Serif",
    },
    {
        "name": "Tahoma",
        "stack": "Tahoma, 'DejaVu Sans', Geneva, sans-serif",
        "category": "Sans-serif",
    },
    {
        "name": "Webdings",
        "stack": "'Webdings', cursive, sans-serif",
        "category": "Display",
    },
]

_ALL_FONT_NAMES = [f["name"] for f in FONT_ENTRIES]

# --------------------------------------------------------------------------- #
# Bundled-font helpers                                                        #
# --------------------------------------------------------------------------- #

#: Per-file base64 cache keyed by absolute file path.
_BASE64_CACHE: dict[str, str] = {}

#: Full CSS string cache so we only build once per session.
_ALL_FACES_CSS_CACHE: str | None = None


# Mapping of filename -> (css_family_name, weight, style)
_FONT_FILE_META: dict[str, tuple[str, str, str]] = {
    # Inter variable font
    "Inter-Variable.ttf": ("Inter-Variable", "100 900", "normal"),

    # Andale Mono
    "andalemo.ttf": ("Andale Mono", "400", "normal"),

    # Arial
    "arial.ttf": ("Arial", "400", "normal"),
    "arialbd.ttf": ("Arial", "700", "normal"),
    "arialbi.ttf": ("Arial", "700", "italic"),
    "ariali.ttf": ("Arial", "400", "italic"),
    "ariblk.ttf": ("Arial Black", "900", "normal"),

    # Calibri
    "calibri.ttf": ("Calibri", "400", "normal"),
    "calibrib.ttf": ("Calibri", "700", "normal"),
    "calibrii.ttf": ("Calibri", "400", "italic"),
    "calibriz.ttf": ("Calibri", "700", "italic"),

    # Cambria
    "cambriab.ttf": ("Cambria", "700", "normal"),
    "cambriai.ttf": ("Cambria", "400", "italic"),
    "cambriaz.ttf": ("Cambria", "700", "italic"),

    # Candara
    "candara.ttf": ("Candara", "400", "normal"),
    "candarab.ttf": ("Candara", "700", "normal"),
    "candarai.ttf": ("Candara", "400", "italic"),
    "candaraz.ttf": ("Candara", "700", "italic"),

    # Comic Sans MS
    "comic.ttf": ("Comic Sans MS", "400", "normal"),
    "comicbd.ttf": ("Comic Sans MS", "700", "normal"),

    # Consolas
    "consola.ttf": ("Consolas", "400", "normal"),
    "consolab.ttf": ("Consolas", "700", "normal"),
    "consolai.ttf": ("Consolas", "400", "italic"),
    "consolaz.ttf": ("Consolas", "700", "italic"),

    # Constantia
    "constan.ttf": ("Constantia", "400", "normal"),
    "constanb.ttf": ("Constantia", "700", "normal"),
    "constani.ttf": ("Constantia", "400", "italic"),
    "constanz.ttf": ("Constantia", "700", "italic"),

    # Corbel
    "corbel.ttf": ("Corbel", "400", "normal"),
    "corbelb.ttf": ("Corbel", "700", "normal"),
    "corbeli.ttf": ("Corbel", "400", "italic"),
    "corbelz.ttf": ("Corbel", "700", "italic"),

    # Courier New
    "cour.ttf": ("Courier New", "400", "normal"),
    "courbd.ttf": ("Courier New", "700", "normal"),
    "courbi.ttf": ("Courier New", "700", "italic"),
    "couri.ttf": ("Courier New", "400", "italic"),

    # Georgia
    "georgia.ttf": ("Georgia", "400", "normal"),
    "georgiab.ttf": ("Georgia", "700", "normal"),
    "georgiai.ttf": ("Georgia", "400", "italic"),
    "georgiaz.ttf": ("Georgia", "700", "italic"),

    # Impact
    "impact.ttf": ("Impact", "400", "normal"),

    # Tahoma
    "tahoma.ttf": ("Tahoma", "400", "normal"),

    # Times New Roman
    "times.ttf": ("Times New Roman", "400", "normal"),
    "timesbd.ttf": ("Times New Roman", "700", "normal"),
    "timesbi.ttf": ("Times New Roman", "700", "italic"),
    "timesi.ttf": ("Times New Roman", "400", "italic"),

    # Trebuchet MS
    "trebuc.ttf": ("Trebuchet MS", "400", "normal"),
    "trebucbd.ttf": ("Trebuchet MS", "700", "normal"),
    "trebucbi.ttf": ("Trebuchet MS", "700", "italic"),
    "trebucit.ttf": ("Trebuchet MS", "400", "italic"),

    # Verdana
    "verdana.ttf": ("Verdana", "400", "normal"),
    "verdanab.ttf": ("Verdana", "700", "normal"),
    "verdanai.ttf": ("Verdana", "400", "italic"),
    "verdanaz.ttf": ("Verdana", "700", "italic"),

    # Webdings
    "webdings.ttf": ("Webdings", "400", "normal"),
}


def _fonts_dir() -> str:
    """Return the absolute path to the bundled fonts directory."""
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    font_dir = os.path.join(base, "assets", "fonts")
    return font_dir if os.path.isdir(font_dir) else ""


def _file_data_uri(path: str) -> str | None:
    """Return a base64 data URI for a single font file, with local caching."""
    if path in _BASE64_CACHE:
        return _BASE64_CACHE[path]
    try:
        with open(path, "rb") as f:
            raw = f.read()
        b64 = base64.b64encode(raw).decode("ascii")
        uri = f"data:font/ttf;base64,{b64}"
        _BASE64_CACHE[path] = uri
        return uri
    except Exception:
        return None


def _build_all_faces_css() -> str:
    """Generate @font-face rules for every bundled TTF we can find."""
    font_dir = _fonts_dir()
    if not font_dir:
        return ""

    lines: list[str] = []
    for filename, (family, weight, style) in _FONT_FILE_META.items():
        filepath = os.path.join(font_dir, filename)
        if not os.path.isfile(filepath):
            continue
        uri = _file_data_uri(filepath)
        if not uri:
            continue
        lines.append(
            f"@font-face {{\n"
            f"  font-family: '{family}';\n"
            f"  font-style: {style};\n"
            f"  font-weight: {weight};\n"
            f"  src: url('{uri}');\n"
            f"}}\n"
        )

    # Also inject a generic "Inter" alias pointing to the variable font
    inter_path = os.path.join(font_dir, "Inter-Variable.ttf")
    if os.path.isfile(inter_path):
        inter_uri = _file_data_uri(inter_path)
        if inter_uri:
            lines.append(
                f"@font-face {{\n"
                f"  font-family: 'Inter';\n"
                f"  font-style: normal;\n"
                f"  font-weight: 100 900;\n"
                f"  src: url('{inter_uri}');\n"
                f"}}\n"
            )

    return "\n".join(lines)


def inject_bundled_font_css() -> None:
    """
    Inject @font-face rules so every bundled font is available in the
    browser / WebView rendering context via base64 data URIs.

    All TTF files shipped under backend/assets/fonts/ are embedded
    directly, guaranteeing correct rendering regardless of system font
    installation.  Font stacks from FONT_ENTRIES still include fallback
    (metric-compatible) families for graceful degradation.

    CSS is built once per process and injected once per session to avoid
    re-sending ~17 MB of base64-encoded font data on every Streamlit rerun.
    """
    global _ALL_FACES_CSS_CACHE

    if _ALL_FACES_CSS_CACHE is None:
        _ALL_FACES_CSS_CACHE = _build_all_faces_css()

    # Skip re-injection if already done this session
    if st.session_state.get("_lytrize_bundled_fonts_injected"):
        return

    if _ALL_FACES_CSS_CACHE:
        st.markdown(
            f'<style id="lytrize_bundled_fonts">{_ALL_FACES_CSS_CACHE}</style>',
            unsafe_allow_html=True,
        )
    st.session_state["_lytrize_bundled_fonts_injected"] = True


def get_font_stack(name: str) -> str:
    """Return the CSS font stack for a given display name."""
    for entry in FONT_ENTRIES:
        if entry["name"] == name:
            return entry["stack"]
    return name


def get_all_font_names() -> list[str]:
    """Return all registered font display names."""
    return _ALL_FONT_NAMES.copy()


def _css_class(font_name: str) -> str:
    """Convert a font display name to a valid CSS class string."""
    return "lytrize_font_" + font_name.lower().replace(" ", "_").replace("-", "_")


def inject_font_preview_css() -> None:
    """Inject a <style> block with font-family classes for every registered font."""
    inject_bundled_font_css()

    if st.session_state.get("_lytrize_font_preview_injected"):
        return

    css_rules = ""
    for entry in FONT_ENTRIES:
        cls = _css_class(entry["name"])
        css_rules += f".{cls} {{ font-family: {entry['stack']}; }}\n"
    st.markdown(
        f"""<style id="lytrize_font_preview_css">{css_rules}</style>""",
        unsafe_allow_html=True,
    )
    st.session_state["_lytrize_font_preview_injected"] = True


def font_select(label: str, default: str, key: str) -> str:
    """Render a font-family selector with a live preview line."""
    inject_bundled_font_css()

    options = get_all_font_names()
    if default not in options:
        options = [default] + options

    selected = st.selectbox(label, options, index=_index_of(options, default), key=key)

    preview_class = _css_class(selected)
    st.markdown(
        f"""
        <style>
        .{preview_class} {{ font-family: {get_font_stack(selected)}; }}
        </style>
        <p style="margin:0 0 0.5rem 0; font-size:13px; color:#94a3b8;" class="{preview_class}">
            Preview – 123 <strong>{selected}</strong></p>
        """,
        unsafe_allow_html=True,
    )
    return selected


def _index_of(options: list[str], default: str) -> int:
    try:
        return options.index(default)
    except ValueError:
        return 0
