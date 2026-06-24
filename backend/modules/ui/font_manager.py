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

# ── Font catalogue ──────────────────────────────────────────────────────────
FONT_ENTRIES: list[dict[str, str]] = [
    {
        "name": "Inter",
        "stack": "'Inter-Variable', 'Inter', 'Helvetica Neue', Arial, sans-serif",
        "category": "Sans-serif",
    },
    {
        "name": "Arial",
        "stack": "'Arial', 'Liberation Sans', Arimo, 'Helvetica Neue', Helvetica, sans-serif",
        "category": "Sans-serif",
    },
    {
        "name": "Liberation Sans",
        "stack": "'Liberation Sans', Arial, Arimo, sans-serif",
        "category": "Sans-serif",
    },
    {
        "name": "Calibri",
        "stack": "'Calibri', Carlito, 'Liberation Sans', Arial, sans-serif",
        "category": "Sans-serif",
    },
    {
        "name": "Carlito",
        "stack": "Carlito, Calibri, 'Liberation Sans', Arial, sans-serif",
        "category": "Sans-serif",
    },
    {
        "name": "Verdana",
        "stack": "'Verdana', Geneva, DejaVu Sans, sans-serif",
        "category": "Sans-serif",
    },
    {
        "name": "Tahoma",
        "stack": "'Tahoma', Geneva, DejaVu Sans, sans-serif",
        "category": "Sans-serif",
    },
    {
        "name": "Cambria",
        "stack": "'Cambria', Georgia, 'DejaVu Serif', 'Liberation Serif', serif",
        "category": "Serif",
    },
    {
        "name": "Trebuchet MS",
        "stack": "'Trebuchet MS', 'Liberation Sans', Ubuntu, sans-serif",
        "category": "Sans-serif",
    },
    {
        "name": "Ubuntu",
        "stack": "Ubuntu, 'DejaVu Sans', 'Liberation Sans', sans-serif",
        "category": "Sans-serif",
    },
    {
        "name": "Helvetica",
        "stack": "'Helvetica Neue', Helvetica, Arial, 'Liberation Sans', sans-serif",
        "category": "Sans-serif",
    },
    {
        "name": "Times New Roman",
        "stack": "'Times New Roman', 'Liberation Serif', Tinos, Times, serif",
        "category": "Serif",
    },
    {
        "name": "Liberation Serif",
        "stack": "'Liberation Serif', 'Times New Roman', Tinos, Times, serif",
        "category": "Serif",
    },
    {
        "name": "Georgia",
        "stack": "'Georgia', 'DejaVu Serif', 'Liberation Serif', serif",
        "category": "Serif",
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
        "name": "JetBrains Mono",
        "stack": "'JetBrains Mono', 'Liberation Mono', 'Courier New', Consolas, monospace",
        "category": "Monospace",
    },
    {
        "name": "Courier New",
        "stack": "'Courier New', 'Liberation Mono', Cousine, 'Lucida Console', monospace",
        "category": "Monospace",
    },
    {
        "name": "Liberation Mono",
        "stack": "'Liberation Mono', 'Courier New', Cousine, Consolas, monospace",
        "category": "Monospace",
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
        "name": "Impact",
        "stack": "'Impact', Haettenschweiler, 'Arial Narrow Bold', sans-serif",
        "category": "Display",
    },
    {
        "name": "Comic Sans MS",
        "stack": "'Comic Sans MS', 'Comic Sans', 'Chalkboard SE', cursive, sans-serif",
        "category": "Display",
    },
]

_ALL_FONT_NAMES = [f["name"] for f in FONT_ENTRIES]

# Cache for the Inter-Variable base64 data URI so we only encode once
_INTER_BASE64_CACHE: str | None = None


def _fonts_dir() -> str:
    """Return the absolute path to the bundled fonts directory."""
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    font_dir = os.path.join(base, "assets", "fonts")
    return font_dir if os.path.isdir(font_dir) else ""


def _inter_data_uri() -> str | None:
    """
    Read Inter-Variable.ttf from the bundled fonts dir and return
    a base64 data URI.  This is cached so we only encode once per session.
    """
    global _INTER_BASE64_CACHE
    if _INTER_BASE64_CACHE is not None:
        return _INTER_BASE64_CACHE

    font_dir = _fonts_dir()
    if not font_dir:
        return None

    inter_path = os.path.join(font_dir, "Inter-Variable.ttf")
    if not os.path.isfile(inter_path):
        return None

    try:
        with open(inter_path, "rb") as f:
            raw = f.read()
        b64 = base64.b64encode(raw).decode("ascii")
        _INTER_BASE64_CACHE = f"data:font/ttf;base64,{b64}"
        return _INTER_BASE64_CACHE
    except Exception:
        return None


def inject_bundled_font_css() -> None:
    """
    Inject @font-face rules so the app's bundled Inter font is available in
    the browser/WebView rendering context via a base64 data URI.

    Inter is the default chart font and is embedded directly so it always
    renders correctly regardless of system font installation.
    Other fonts (Arial, Calibri, etc.) are referenced by family name in the
    CSS font stacks — they will use the system-installed version if available
    (e.g. via ttf-mscorefonts-installer / mscore-fonts), or fall back to
    metric-compatible Liberation/Carlito fonts shipped by every Linux distro.
    """
    inter_data = _inter_data_uri()
    if not inter_data:
        return

    css = (
        "@font-face {\n"
        "  font-family: 'Inter-Variable';\n"
        "  font-style: normal;\n"
        "  font-weight: 100 900;\n"
        f"  src: url('{inter_data}');\n"
        "}\n"
        "@font-face {\n"
        "  font-family: 'Inter';\n"
        "  font-style: normal;\n"
        "  font-weight: 100 900;\n"
        f"  src: url('{inter_data}');\n"
        "}\n"
    )
    st.markdown(
        f"<style id=\"lytrize_bundled_fonts\">{css}</style>",
        unsafe_allow_html=True,
    )


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
    # First inject @font-face rules so bundled fonts are loadable
    inject_bundled_font_css()

    css_rules = ""
    for entry in FONT_ENTRIES:
        cls = _css_class(entry["name"])
        css_rules += f".{cls} {{ font-family: {entry['stack']}; }}\n"
    st.markdown(
        f"""<style id="lytrize_font_preview_css">{css_rules}</style>""",
        unsafe_allow_html=True,
    )


def font_select(label: str, default: str, key: str) -> str:
    """Render a font-family selector with a live preview line."""
    inject_bundled_font_css()

    options = get_all_font_names()
    if default not in options:
        options = [default] + options

    selected = st.selectbox(label, options, index=_index_of(options, default), key=key)

    # Show a preview line rendered in the selected font
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