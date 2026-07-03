"""
modules/ui/css.py — Global CSS injection
=========================================

Hides all Streamlit chrome, keeps the purple brand palette, and provides
all shared component styles used across every page.

---------------------
1. Nav button squeeze (Profile "Pro file" wrapping)
       root cause: align-items: left is not a valid flex value → browser
                   ignores it and collapses the container; button shrinks.
       fix: align-items: center  +  white-space: nowrap on each button.

2. KPI card inconsistent height/width
       root cause: row-direction flex with variable-length labels caused
                   taller cards when labels wrapped to two lines.
       fix: column-direction flex + min-height + white-space: nowrap on label.

3. Analysis cards unstyled
       root cause: .ag-card / .ag-icon / .ag-name / .ag-desc classes were
                   referenced in analysis.py but never defined in this file.
       fix: full definition matching the KPI card visual language.
"""

from __future__ import annotations

import base64
import os
from functools import lru_cache
from pathlib import Path

import streamlit as st

from config import APP_NAME, APP_VERSION


LOGO_PATH   = Path(__file__).resolve().parents[2] / "assets" / "lytrize.ico"
THEME_MODES = ("dark", "light")



def get_theme_mode() -> str:
    try:
        import streamlit as _st
        return str(_st.session_state.get("theme", "dark"))
    except Exception:
        return "dark"


def set_theme_mode(mode: str) -> None:
    try:
        import streamlit as _st
        _st.session_state["theme"] = mode if mode in THEME_MODES else "dark"
        _css_block.cache_clear()
    except Exception:
        pass



@lru_cache(maxsize=1)
def logo_data_uri() -> str:
    try:
        data = base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
        return f"data:image/x-icon;base64,{data}"
    except Exception:
        return ""



@lru_cache(maxsize=1)
def _font_link() -> str:
    return (
        "<link rel='stylesheet'"
        " href='https://fonts.googleapis.com/css2?"
        "family=Inter:wght@300;400;500;600;700;800"
        "&family=Sora:wght@600;700;800"
        "&family=JetBrains+Mono:wght@400;500&display=swap'"
        " media='print'"
        " onload=\"this.media='all'\">"
        "<noscript><link rel='stylesheet'"
        " href='https://fonts.googleapis.com/css2?"
        "family=Inter:wght@300;400;500;600;700;800"
        "&family=Sora:wght@600;700;800"
        "&family=JetBrains+Mono:wght@400;500&display=swap'></noscript>"
    )



def inject_css() -> None:
    """Inject fonts + full stylesheet into the Streamlit page."""
    st.markdown(_font_link(), unsafe_allow_html=True)
    st.markdown(_css_block(get_theme_mode()), unsafe_allow_html=True)


@lru_cache(maxsize=3)
def _css_block(theme_mode: str | None = None) -> str:
    return _build_css(theme_mode or get_theme_mode())


def _light_overrides() -> str:
    """Extra CSS injected only in light mode. Never touches nav/button structure."""
    return """
/* ── LIGHT MODE OVERRIDES ──────────────────────────────────────────────────── */

/* Page & app background */
.stApp, [data-testid="stAppViewContainer"] {
    background: linear-gradient(180deg, #f0f3ff 0%, #f8faff 100%) !important;
    color: #1e1b4b !important;
}

/* Topbar & footer */
.lytrize-topbar {
    background: color-mix(in srgb, #f8faff 92%, transparent) !important;
    border-bottom: 1px solid rgba(99,102,241,0.15) !important;
}
.lytrize-footer {
    background: color-mix(in srgb, #f8faff 94%, transparent) !important;
    border-top: 1px solid rgba(99,102,241,0.15) !important;
}

/* Brand keeps purple gradient */
.brand {
    background: linear-gradient(170deg, #4338ca 37%, #7c3aed 95%, #4338ca 100%) !important;
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
}

/* Global text — but NOT inside gradient buttons */
body { color: #1e1b4b !important; }
p, span, label, li, small, strong, b, code, pre { color: #1e1b4b !important; }
h1, h2, h3, h4, h5, h6 { color: #1e1b4b !important; }
a { color: #4f46e5 !important; }
input, textarea { color: #1e1b4b !important; }

/* Button text */
.stButton > button,
.stButton > button p,
.stButton > button span,
.stButton > button small,
.stButton > button label,
.stButton > button * {
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
}

[data-testid="stBaseButton-secondary"],
[data-testid="stBaseButton-secondary"] *,
[data-testid="stBaseButton-secondaryFormSubmit"],
[data-testid="stBaseButton-secondaryFormSubmit"] *,
[data-testid="stBaseButton-primaryFormSubmit"],
[data-testid="stBaseButton-primaryFormSubmit"] *,
.stButton > button *,
[data-testid="stButton"] button *,
[data-testid="stButton"] button * ,
[data-testid="stFormSubmitButton"] button,
[data-testid="stFormSubmitButton"] button *,
button[kind="primary"],
button[kind="primary"] *,
[data-testid="stDownloadButton"] > a,
[data-testid="stDownloadButton"] > a * {
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
}
.stDownloadButton > button,
.stDownloadButton > button *,
[data-testid="stDownloadButton"] > a,
[data-testid="stDownloadButton"] > a * {
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
}

/* Surfaces */
.kpi-card, .sess-card, .ag-card {
    background: linear-gradient(160deg, rgba(255,255,255,0.98), rgba(245,247,255,0.98)) !important;
    border-color: rgba(99,102,241,0.18) !important;
    box-shadow: 0 2px 8px rgba(99,102,241,0.07) !important;
}
.kpi-lbl, .ag-desc { color: #4b5563 !important; }
.ag-name           { color: #1e1b4b !important; }

/* KPI value — dark purple gradient on light bg */
.kpi-val {
    background: linear-gradient(135deg, #4338ca, #7c3aed) !important;
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
}

/* Welcome banner keeps dark gradient — text stays white */
.welcome-banner {
    background: linear-gradient(170deg, #4338ca 80%, #7c3aed 99%, #4338ca 100%) !important;
}
.welcome-banner, .welcome-banner * {
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
}

/* Alerts */
[data-testid="stAlert"],
[data-testid="stNotification"],
div[data-baseweb="notification"] {
    background: rgba(241,245,255,0.98) !important;
    border: 1px solid rgba(99,102,241,0.18) !important;
    border-radius: 10px !important;
}

[data-testid="stAlert"] *,
[data-testid="stNotification"] *,
div[data-baseweb="notification"] * {
    color: #1e1b4b !important;
    -webkit-text-fill-color: #1e1b4b !important;
}

div[data-baseweb="notification"],
[data-testid="stAlert"] [data-baseweb="notification"],
[data-testid="stNotification"] [data-baseweb="notification"] {
    background: rgba(241,245,255,0.98) !important;
}

/* Info tint */
[data-testid="stAlert"][data-baseweb="notification"] {
    background: rgba(239,246,255,0.98) !important;
}

/* Success tint */
[data-testid="stAlert"][kind="success"],
.stSuccess { background: rgba(236,253,245,0.98) !important; }


/* Toast pop-ups */
[data-testid="stToast"] {
    background: rgba(255,255,255,0.98) !important;
    border: 1px solid rgba(99,102,241,0.18) !important;
    box-shadow: 0 4px 16px rgba(15,23,42,0.14) !important;
}
/* Keep toast body transparent */
[data-testid="stToast"] [data-baseweb="notification"],
[data-testid="stToast"] [data-baseweb="toast"],
[data-testid="stToast"] > div {
    background: transparent !important;
}
[data-testid="stToast"] * {
    color: #1e1b4b !important;
    -webkit-text-fill-color: #1e1b4b !important;
}

[data-testid="stToast"] svg {
    color: #4338ca !important;
    fill: #4338ca !important;
}
[data-testid="stToastViewButton"] {
    color: #4338ca !important;
    -webkit-text-fill-color: #4338ca !important;
}

/* Inputs */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stNumberInput"] input,
[data-testid="stDateInput"] input {
    background: rgba(255,255,255,0.98) !important;
    color: #1e1b4b !important;
    -webkit-text-fill-color: #1e1b4b !important;
    border: 1px solid rgba(99,102,241,0.22) !important;
}
[data-testid="stTextInput"] input::placeholder,
[data-testid="stTextArea"] textarea::placeholder {
    color: #9ca3af !important;
    -webkit-text-fill-color: #9ca3af !important;
}

/* Selectbox and multiselect */
[data-testid="stSelectbox"] [data-baseweb="select"],
[data-testid="stSelectbox"] > div,
[data-testid="stMultiSelect"] [data-baseweb="select"],
[data-testid="stMultiSelect"] > div {
    background: rgba(255,255,255,0.98) !important;
    color: #1e1b4b !important;
    -webkit-text-fill-color: #1e1b4b !important;
    border-color: rgba(99,102,241,0.22) !important;
}

[data-testid="stSelectbox"] [data-baseweb="select"] div,
[data-testid="stMultiSelect"] [data-baseweb="select"] div {
    background: transparent !important;
}
/* Multiselect chips */
[data-testid="stMultiSelect"] [data-baseweb="tag"],
[data-testid="stMultiSelect"] span[data-baseweb="tag"] {
    background: rgba(99,102,241,0.12) !important;
    border: 1px solid rgba(99,102,241,0.25) !important;
    color: #4338ca !important;
    -webkit-text-fill-color: #4338ca !important;
}
[data-testid="stMultiSelect"] [data-baseweb="tag"] span,
[data-testid="stMultiSelect"] [data-baseweb="tag"] svg {
    color: #4338ca !important;
    -webkit-text-fill-color: #4338ca !important;
    fill: #4338ca !important;
}

[data-testid="stMultiSelect"] [data-baseweb="tag"],
[data-testid="stMultiSelect"] [data-baseweb="tag"] *,
[data-testid="stMultiSelect"] [data-baseweb="tag"] [data-baseweb="tag-label"],
[data-testid="stMultiSelect"] [data-baseweb="tag"] [data-baseweb="tag-close-icon"],
[data-testid="stMultiSelect"] [data-baseweb="tag"] [role="button"] {
    overflow: visible !important;
    text-overflow: clip !important;
    max-width: none !important;
    white-space: nowrap !important;
    flex-shrink: 0 !important;
    min-width: 0 !important;
    width: auto !important;
}

[data-testid="stMultiSelect"] [data-baseweb="tag"] {
    margin-left: 6px !important;
}
[data-testid="stMultiSelect"] [data-baseweb="select"],
[data-testid="stMultiSelect"] [data-baseweb="select"] > div,
[data-testid="stMultiSelect"] [data-baseweb="select"] div {
    overflow: visible !important;
    height: auto !important;
}

[data-testid="stMultiSelect"] input,
[data-testid="stMultiSelect"] [data-baseweb="select"] input {
    color: #1e1b4b !important;
    -webkit-text-fill-color: #1e1b4b !important;
    background: transparent !important;
}

/* Dropdown menu */
[data-baseweb="popover"],
[data-baseweb="popover"] > div,
[data-baseweb="menu"],
[data-baseweb="menu"] > div,
[data-baseweb="select"] [role="listbox"],
[data-baseweb="select"] [role="listbox"] > div,
[data-testid="stSelectboxVirtualDropdown"],
[data-testid="stSelectboxVirtualDropdown"] > div {
    background: rgba(255, 255, 255, 0.99) !important;
    background-color: rgba(255, 255, 255, 0.99) !important;
    border: 1px solid rgba(99, 102, 241, 0.22) !important;
    border-radius: 10px !important;
    box-shadow: 0 8px 24px rgba(99, 102, 241, 0.12) !important;
}


[data-baseweb="menu"] div:not([data-baseweb="option"]),
[data-baseweb="select"] [role="listbox"] div:not([data-baseweb="option"]),
[data-testid="stSelectboxVirtualDropdown"] div:not([data-baseweb="option"]),
[data-baseweb="menu"] ul,
[role="listbox"] ul {
    background: transparent !important;
    background-color: transparent !important;
    color: #1e1b4b !important;
    -webkit-text-fill-color: #1e1b4b !important;
}

[data-baseweb="option"],
[data-baseweb="select"] [role="option"] {
    background: rgba(255, 255, 255, 0.99) !important;
    color: #1e1b4b !important;
    -webkit-text-fill-color: #1e1b4b !important;
}
[data-baseweb="option"]:hover {
    background: rgba(99, 102, 241, 0.09) !important;
}
[aria-selected="true"][data-baseweb="option"] {
    background: rgba(99, 102, 241, 0.13) !important;
    color: #4338ca !important;
    -webkit-text-fill-color: #4338ca !important;
}
/* Ensure text and symbols inside selected options inherit the proper active theme color */
[aria-selected="true"][data-baseweb="option"] * {
    color: #4338ca !important;
    -webkit-text-fill-color: #4338ca !important;
}

/* Expanders */
[data-testid="stExpander"] {
    background: rgba(255,255,255,0.98) !important;
    border: 1px solid rgba(99,102,241,0.18) !important;
}
[data-testid="stExpander"] summary {
    background: rgba(245,247,255,0.98) !important;
    color: #1e1b4b !important;
    -webkit-text-fill-color: #1e1b4b !important;
}
[data-testid="stExpander"] summary * {
    color: #1e1b4b !important;
    -webkit-text-fill-color: #1e1b4b !important;
}
[data-testid="stExpander"] summary:hover { background: rgba(99,102,241,0.07) !important; }

/* Metrics */
[data-testid="stMetric"] { background: rgba(255,255,255,0.98) !important; }

/* Scrollbar */
::-webkit-scrollbar-track { background: #f0f3ff; }
::-webkit-scrollbar-thumb { background: rgba(99,102,241,0.25); }
::-webkit-scrollbar-thumb:hover { background: rgba(99,102,241,0.45); }

/* Tooltips */
[data-baseweb="tooltip"] {
    background: rgba(255,255,255,0.98) !important;
    border: 1px solid rgba(99,102,241,0.22) !important;
    border-radius: 8px !important;
    box-shadow: 0 4px 16px rgba(99,102,241,0.12) !important;
}
[data-baseweb="tooltip"] div,
[data-baseweb="tooltip"] span {
    background: transparent !important;
    color: #1e1b4b !important;
}
/* The tooltip ARROW (triangle) — hide the dark border artifact */
[data-baseweb="tooltip"] [data-popper-arrow],
[data-baseweb="tooltip"] [data-popper-arrow]::before {
    border-color: rgba(99,102,241,0.22) !important;
    background: rgba(255,255,255,0.98) !important;
}

/* File uploader */
[data-testid="stFileUploader"] { background: transparent !important; border: none !important; }
[data-testid="stFileUploaderDropzone"] {
    background: rgba(255,255,255,0.98) !important;
    border: 1.5px dashed rgba(99,102,241,0.35) !important;
    border-radius: 10px !important;
}
/* Upload button */
[data-testid="stFileUploaderDropzone"] button,
[data-testid="stFileUploader"] button {
    background: linear-gradient(170deg, #4313a6 80%, #8658e6 99%, #4313a6 100%) !important;
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
    border: none !important;
    border-radius: 8px !important;
}
[data-testid="stFileUploaderDropzoneInstructions"] span,
[data-testid="stFileUploaderDropzoneInstructions"] p,
[data-testid="stFileUploaderDropzoneInstructions"] div {
    color: #4b5563 !important;
    -webkit-text-fill-color: #4b5563 !important;
}

/* Gradient buttons */
[data-testid="stBaseButton-primary"],
[data-testid="stBaseButton-primary"] p,
[data-testid="stBaseButton-primary"] span,
[data-testid="stBaseButton-primary"] *,
[data-testid="stBaseButton-secondary"],
[data-testid="stBaseButton-secondary"] p,
[data-testid="stBaseButton-secondary"] span,
[data-testid="stBaseButton-secondary"] *,
[data-testid="stBaseButton-primaryFormSubmit"],
[data-testid="stBaseButton-primaryFormSubmit"] p,
[data-testid="stBaseButton-primaryFormSubmit"] span,
[data-testid="stBaseButton-primaryFormSubmit"] *,
[data-testid="stBaseButton-secondaryFormSubmit"],
[data-testid="stBaseButton-secondaryFormSubmit"] p,
[data-testid="stBaseButton-secondaryFormSubmit"] span,
[data-testid="stBaseButton-secondaryFormSubmit"] {
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
}


/* Inline code labels */
[data-testid="stTextInput"] label code,
[data-testid="stTextInput"] label [data-testid="stMarkdownContainer"] code,
[data-baseweb="form-control"] label code {
    background: rgba(99,102,241,0.1) !important;
    color: #4338ca !important;
    -webkit-text-fill-color: #4338ca !important;
    border: 1px solid rgba(99,102,241,0.2) !important;
    border-radius: 4px !important;
    padding: 0.1rem 0.35rem !important;
}

/* Code blocks */
[data-testid="stCode"],
[data-testid="stCode"] pre,
[data-testid="stCode"] code,
.stCode, .stCode pre, .stCode code {
    background: rgba(241,245,255,0.98) !important;
    color: #1e1b4b !important;
    -webkit-text-fill-color: #1e1b4b !important;
    border: 1px solid rgba(99,102,241,0.18) !important;
    border-radius: 6px !important;
}


[data-testid="stMultiSelect"] [data-baseweb="tooltip"],
[data-testid="stMultiSelect"] [data-baseweb="popover"],
[data-testid="stMultiSelect"] [role="tooltip"],
[data-testid="stMultiSelect"] [data-baseweb="input"] ~ [data-baseweb="popover"],
[data-testid="stMultiSelect"] [data-baseweb="select"] ~ [data-baseweb="popover"],
[data-testid="stMultiSelect"] div[data-baseweb="popover"],
[data-testid="stMultiSelect"] div[data-baseweb="tooltip"] {
    background: rgba(255,255,255,0.99) !important;
    border: 1px solid rgba(99,102,241,0.22) !important;
    color: #1e1b4b !important;
    -webkit-text-fill-color: #1e1b4b !important;
    box-shadow: 0 4px 16px rgba(15,23,42,0.14) !important;
}
[data-testid="stMultiSelect"] [data-baseweb="tooltip"] *,
[data-testid="stMultiSelect"] [data-baseweb="popover"] *,
[data-testid="stMultiSelect"] [role="tooltip"] *,
[data-testid="stMultiSelect"] div[data-baseweb="popover"] *,
[data-testid="stMultiSelect"] div[data-baseweb="tooltip"] * {
    color: #1e1b4b !important;
    -webkit-text-fill-color: #1e1b4b !important;
    background: transparent !important;
}


[data-testid="stMultiSelect"] div[data-baseweb="popover"] ul,
[data-testid="stMultiSelect"] div[data-baseweb="popover"] li {
    background: transparent !important;
    color: #1e1b4b !important;
}


/* Multiselect chip layout */
[data-testid="stMultiSelect"] [data-baseweb="tag"] {
    max-width: none !important;
    overflow: visible !important;
    white-space: nowrap !important;
    flex-shrink: 0 !important;
    margin-left: 6px !important;
}
[data-testid="stMultiSelect"] [data-baseweb="tag"] * {
    overflow: visible !important;
    text-overflow: clip !important;
    max-width: none !important;
    white-space: nowrap !important;
    flex-shrink: 0 !important;
}

[data-testid="stMultiSelect"] [data-baseweb="select"],
[data-testid="stMultiSelect"] [data-baseweb="select"] > div,
[data-testid="stMultiSelect"] [data-baseweb="select"] div {
    overflow: visible !important;
    height: auto !important;
}

/* Color picker popup — light mode fix
   Streamlit renders st.color_picker in a baseweb popover that contains
   a <canvas> (saturation/brightness picker) and <input> (hex field).
   The popover inherits Streamlit's base dark theme even in light mode.
   We target the popover that :has(canvas) to scope these rules strictly
   to the color picker (avoids touching dropdown menus or tooltips). */

/* Popup container */
div[data-baseweb="popover"]:has(canvas) {
    background: #ffffff !important;
    background-color: #ffffff !important;
    border: 1px solid rgba(99,102,241,0.22) !important;
    border-radius: 10px !important;
    box-shadow: 0 8px 24px rgba(99,102,241,0.14) !important;
}

/* All child divs inside the popup (strip dark bg inherited from base theme) */
div[data-baseweb="popover"]:has(canvas) > div,
div[data-baseweb="popover"]:has(canvas) > div > div {
    background: #ffffff !important;
    background-color: #ffffff !important;
    border-radius: 10px !important;
}

/* The saturation/brightness canvas box wrapper */
div[data-baseweb="popover"]:has(canvas) div:has(> canvas) {
    background: transparent !important;
    border-radius: 6px !important;
    overflow: hidden !important;
}

/* Hue & opacity slider tracks */
div[data-baseweb="popover"]:has(canvas) [class*="slider"],
div[data-baseweb="popover"]:has(canvas) [class*="track"] {
    background: transparent !important;
}

/* Hex input field */
div[data-baseweb="popover"]:has(canvas) input[type="text"],
div[data-baseweb="popover"]:has(canvas) input {
    background: rgba(241,245,255,0.98) !important;
    background-color: rgba(241,245,255,0.98) !important;
    color: #1e1b4b !important;
    -webkit-text-fill-color: #1e1b4b !important;
    border: 1px solid rgba(99,102,241,0.28) !important;
    border-radius: 6px !important;
}

/* "HEX" label below the input */
div[data-baseweb="popover"]:has(canvas) p,
div[data-baseweb="popover"]:has(canvas) span:not([style*="background"]) {
    color: #4b5563 !important;
    -webkit-text-fill-color: #4b5563 !important;
    background: transparent !important;
}

/* Number increment/decrement arrows beside the hex input */
div[data-baseweb="popover"]:has(canvas) button,
div[data-baseweb="popover"]:has(canvas) [role="button"] {
    background: rgba(241,245,255,0.98) !important;
    color: #1e1b4b !important;
    -webkit-text-fill-color: #1e1b4b !important;
    border-color: rgba(99,102,241,0.2) !important;
}
div[data-baseweb="popover"]:has(canvas) button svg,
div[data-baseweb="popover"]:has(canvas) [role="button"] svg {
    fill: #1e1b4b !important;
    color: #1e1b4b !important;
}

/* Sliders */
[data-testid="stSlider"] label,
[data-testid="stSlider"] p,
[data-testid="stSlider"] span {
    color: #1e1b4b !important;
    -webkit-text-fill-color: #1e1b4b !important;
}

/* Checkboxes */
[data-testid="stCheckbox"] label,
[data-testid="stCheckbox"] p,
[data-testid="stCheckbox"] span {
    color: #1e1b4b !important;
    -webkit-text-fill-color: #1e1b4b !important;
}

/* Markdown in expanders */
[data-testid="stExpander"] [data-testid="stMarkdownContainer"] p,
[data-testid="stExpander"] [data-testid="stMarkdownContainer"] span,
[data-testid="stExpander"] label {
    color: #1e1b4b !important;
    -webkit-text-fill-color: #1e1b4b !important;
}

[data-testid="stExpander"] .stButton > button,
[data-testid="stExpander"] .stButton > button *,
[data-testid="stExpander"] [data-testid="stBaseButton-primary"] *,
[data-testid="stExpander"] [data-testid="stBaseButton-secondary"] *,
[data-testid="stExpander"] [data-testid="stDownloadButton"] > a,
[data-testid="stExpander"] [data-testid="stDownloadButton"] > a * {
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
}

/* Number input */
[data-testid="stNumberInput"] button {
    background: rgba(245,247,255,0.98) !important;
    color: #1e1b4b !important;
    -webkit-text-fill-color: #1e1b4b !important;
    border: 1px solid rgba(99,102,241,0.22) !important;
}

/* Tabs */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
    background: rgba(241,245,255,0.98) !important;
    border-bottom: 1px solid rgba(99,102,241,0.18) !important;
}
[data-testid="stTabs"] [data-baseweb="tab"] {
    color: #4b5563 !important;
    -webkit-text-fill-color: #4b5563 !important;
    background: transparent !important;
}
[data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] {
    color: #4338ca !important;
    -webkit-text-fill-color: #4338ca !important;
    border-bottom: 2px solid #4338ca !important;
}

/* Captions */
[data-testid="stCaptionContainer"] p,
[data-testid="stCaptionContainer"] span {
    color: #6b7280 !important;
    -webkit-text-fill-color: #6b7280 !important;
}

/* File chips */
[data-testid="stFileChips"], [data-testid="stFileChip"] {
    background: rgba(241,245,255,0.98) !important;
    border: 1px solid rgba(99,102,241,0.22) !important;
    border-radius: 8px !important;
    color: #1e1b4b !important;
    -webkit-text-fill-color: #1e1b4b !important;
}
[data-testid="stFileChipName"],
[data-testid="stFileChip"] span,
[data-testid="stFileChip"] small {
    color: #1e1b4b !important;
    -webkit-text-fill-color: #1e1b4b !important;
}


/* ── DATAFRAME COLUMN MENU EXEMPTION ─────────────────────────────────────── */
/* Protects the dataframe column menu popover from inheriting white backgrounds & white text in light theme.
   This guarantees it remains in its original dark, clear and default styling layout.
   The :not(:has(canvas):has(input)) clause EXCLUDES color picker popovers (which contain a canvas
   element for the saturation/hue picker) so they get the normal light-mode styling and work correctly. */
div[data-baseweb="popover"]:not(:has([role="option"])):not(:has([role="tooltip"])):not(:has(canvas):has(input)) {
    background: #12182d !important;
    background-color: #12182d !important;
    border: 1px solid rgba(255, 255, 255, 0.15) !important;
    border-radius: 8px !important;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5) !important;
}

div[data-baseweb="popover"]:not(:has([role="option"])):not(:has([role="tooltip"])) *,
div[data-baseweb="popover"]:not(:has([role="option"])):not(:has([role="tooltip"])) span,
div[data-baseweb="popover"]:not(:has([role="option"])):not(:has([role="tooltip"])) p,
div[data-baseweb="popover"]:not(:has([role="option"])):not(:has([role="tooltip"])) button,
div[data-baseweb="popover"]:not(:has([role="option"])):not(:has([role="tooltip"])) svg {
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
    fill: #ffffff !important;
    background: transparent !important;
    background-color: transparent !important;
}

div[data-baseweb="popover"]:not(:has([role="option"])):not(:has([role="tooltip"])) button:hover,
div[data-baseweb="popover"]:not(:has([role="option"])):not(:has([role="tooltip"])) [role="button"]:hover,
div[data-baseweb="popover"]:not(:has([role="option"])):not(:has([role="tooltip"])) div[class*="item"]:hover {
    background-color: rgba(255, 255, 255, 0.08) !important;
}

/* ── DATAFRAME ELEMENT TOOLBAR EXEMPTION ─────────────────────────────────── */
/* Protects the floating toolbar (search, download, fullscreen) from inheriting light background and dark text styles.
   This ensures it matches default dark theme styling perfectly and remains fully legible. */
[data-testid="stElementToolbar"] {
    background: rgba(14, 20, 38, 0.85) !important;
    background-color: rgba(14, 20, 38, 0.85) !important;
    border: 1px solid rgba(255, 255, 255, 0.15) !important;
    border-radius: 8px !important;
    padding: 2px 4px !important;
}

[data-testid="stElementToolbar"] button,
[data-testid="stElementToolbar"] svg {
    color: #ffffff !important;
    background: transparent !important;
    background-color: transparent !important;
}

[data-testid="stElementToolbar"] button:hover {
    background-color: rgba(255, 255, 255, 0.12) !important;
}
"""



def _theme_vars(_mode: str) -> str:
    """CSS custom-property block — dark or light palette."""
    if _mode == "light":
        return """
:root {
    --bg-primary:        #f8faff;
    --bg-secondary:      rgba(241, 245, 255, 0.96);
    --surface-1:         rgba(255, 255, 255, 0.98);
    --surface-2:         rgba(245, 247, 255, 0.98);
    --surface-3:         rgba(237, 241, 255, 0.98);
    --surface-muted:     rgba(99, 102, 241, 0.07);
    --border-subtle:     rgba(99, 102, 241, 0.18);
    --border-strong:     rgba(99, 102, 241, 0.35);
    --text-primary:      #1e1b4b;
    --text-secondary:    #4b5563;
    --muted-link:        #4f46e5;
    --chip-bg:           rgba(99, 102, 241, 0.12);
    --input-bg:          rgba(255, 255, 255, 0.95);
    --input-text:        #1e1b4b;
    --input-placeholder: #9ca3af;
    --page-bg:           linear-gradient(180deg, #f0f3ff 0%, #f8faff 100%);
}
"""
    return """
:root {
    --bg-primary:      #0e1428;
    --bg-secondary:    rgba(18, 26, 48, 0.92);
    --surface-1:       rgba(20, 28, 53, 0.95);
    --surface-2:       rgba(25, 35, 64, 0.96);
    --surface-3:       rgba(14, 20, 38, 0.96);
    --surface-muted:   rgba(255,255,255,0.06);
    --border-subtle:   rgba(137, 154, 255, 0.20);
    --border-strong:   rgba(137, 154, 255, 0.35);
    --text-primary:    #eef2ff;
    --text-secondary:  #a7b3d1;
    --muted-link:      #95a2ff;
    --chip-bg:         rgba(111,99,255,0.20);
    --input-bg:        rgba(12, 18, 36, 0.95);
    --input-text:      #eef2ff;
    --input-placeholder: #7f8db0;
    --page-bg:         linear-gradient(180deg, #0e1428 0%, #10182e 100%);
}
"""



def _build_css(theme_mode: str) -> str:
    vars_css = _theme_vars(theme_mode)
    extra    = _light_overrides() if theme_mode == "light" else ""
    return f"""
<style>

/* Hide Streamlit chrome */
.stDeployButton, .stAppDeployButton,
.stStatusWidget, .stActionButton,
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
button[aria-label="More options"],
button[aria-label="Record a screencast"],
button[aria-label="Settings"],
iframe[title="streamlit-menu"] {{
    display:    none       !important;
    visibility: hidden     !important;
}}
header,
[data-testid="stHeader"],
[data-testid="stDecoration"],
[data-testid="stToolbar"] {{
    height:     0          !important;
    min-height: 0          !important;
    max-height: 0          !important;
    padding:    0          !important;
    margin:     0          !important;
    overflow:   hidden     !important;
}}


/* Theme tokens */
:root {{
    --accent-purple:        #6c56e8;
    --accent-purple-strong: #5a49ff;
    --accent-cyan:          #62c8ff;
    --accent-gradient:      linear-gradient(170deg, #4313a6 80%, #8658e6 99%, #4313a6 100%);
    --button-text:          #ffffff;
    --shadow-soft:          0 10px 28px rgba(56, 65, 99, 0.10);
    --shadow-strong:        0 16px 34px rgba(56, 65, 99, 0.16);
}}
{vars_css}


/* Page layout */
.stApp,
[data-testid="stAppViewContainer"] {{
    background: var(--page-bg) !important;
    color:      var(--text-primary) !important;
}}
.main .block-container {{
    padding-top:    3.2rem  !important;
    padding-bottom: 3.2rem  !important;
    max-width: 1480px;
}}

/* Global text */
body, p, span, label, li, a, small, strong, b, code, pre, input, textarea {{
    color: var(--text-primary) !important;
}}
h1, h2, h3, h4, h5, h6,
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3 {{
    color: var(--text-primary) !important;
}}
a {{
    color:           var(--muted-link) !important;
    text-decoration: none;
}}


/* Top bar */
.lytrize-topbar {{
    position:        fixed;
    top:             0;
    left:            0;
    right:           0;
    z-index:         110;
    display:         flex;
    justify-content: center;
    align-items:     center;
    gap:             0.5rem;
    min-height:      44px;
    padding:         0.35rem 1rem;
    background:      color-mix(in srgb, var(--bg-primary) 88%, transparent);
    backdrop-filter: blur(12px);
    /* contain: layout style isolates the fixed bar repaint from page scrolls */
    contain:         layout style;
}}
.lytrize-topbar-brand {{
    position:        absolute;
    left:            50%;
    transform:       translateX(-50%);
    display:         inline-flex;
    align-items:     center;
    gap:             6px;
    pointer-events:  none;
}}
.brand {{
    background: linear-gradient(170deg, #5c1ee6 37%, #b08eff 95%, #5c1ee6 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}}


/* Navigation buttons */
div[data-testid="stVerticalBlock"]:has(#nav-target):not(:has(div[data-testid="stVerticalBlock"])) {{
    position:        fixed          !important;
    top:             6px            !important;
    right:           24px           !important;
    z-index:         120            !important;
    display:         flex           !important;
    flex-direction:  row            !important;
    gap:             0.50rem        !important;
    align-items:     center         !important;
    width:           auto           !important;
}}


/* All nav buttons — gradient style */
div[data-testid="stVerticalBlock"]:has(#nav-target) [data-testid="stButton"] button {{
    background:       var(--accent-gradient) !important;
    color:            #fff                   !important;
    border:           none                   !important;
    border-radius:    8px                    !important;
    padding:          0.28rem 0.9rem         !important;
    font-weight:      600                    !important;
    font-family:      'Inter', sans-serif    !important;
    font-size:        0.82rem                !important;
    line-height:      1.4                    !important;
    cursor:           pointer                !important;
    min-height:       auto                   !important;
    height:           auto                   !important;


    white-space:      nowrap                 !important;
    min-width:        max-content            !important;

    box-shadow:       0 4px 12px rgba(111, 99, 255, 0.25) !important;
    transition:       transform 0.15s ease, box-shadow 0.15s ease !important;
}}

div[data-testid="stVerticalBlock"]:has(#nav-target) [data-testid="stButton"] button:hover {{
    transform:  translateY(-1px)                      !important;
    box-shadow: 0 6px 16px rgba(111, 99, 255, 0.35)  !important;
}}

/* Secondary nav buttons (e.g. sign-out icon) — ghost style */
div[data-testid="stVerticalBlock"]:has(#nav-target) [data-testid="baseButton-secondary"] button {{
    background: rgba(255,255,255,0.10)  !important;
    box-shadow: none                    !important;
}}


/* Welcome banner */
.welcome-banner {{
    margin-top:    0.2rem   !important;
    margin-bottom: 1rem     !important;
    padding:       1rem 1.35rem !important;
    border-radius: 18px     !important;
    text-align:    center   !important;
    overflow:      hidden;
    background:    linear-gradient(170deg, #4313a6 80%, #8658e6 99%, #4313a6 100%) !important;
    box-shadow: var(--shadow-strong);
}}
.welcome-banner,
.welcome-banner * {{
    color:                  #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
}}


/* Section label */
.sec-label {{
    font-size:   0.88rem;
    font-weight: 700;
    color:       var(--text-secondary);
    margin:      0.3rem 0 0.6rem;
}}


/* Global buttons */
.stButton > button,
.stDownloadButton > button,
.stDownloadButton > a,
[data-testid="stDownloadButton"] > a,
[data-testid="stFormSubmitButton"] button,
button[kind="primary"],
[data-testid="baseButton-primary"] {{
    background:    var(--accent-gradient)              !important;
    color:         var(--button-text)                  !important;
    border:        0                                   !important;
    border-radius: 12px                                !important;
    box-shadow:    0 8px 20px rgba(111, 99, 255, 0.22) !important;
    font-weight:   700                                 !important;
    min-height:    2.6rem                              !important;
    transition:    opacity 0.15s ease, transform 0.15s ease !important;
    text-decoration: none !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
}}
.stButton > button:hover,
.stDownloadButton > button:hover,
.stDownloadButton > a:hover,
[data-testid="stDownloadButton"] > a:hover,
[data-testid="stFormSubmitButton"] button:hover,
[data-testid="baseButton-primary"]:hover {{
    opacity: 0.92 !important;
    transform: translateY(-1px) !important;
}}
.stButton > button:active,
.stDownloadButton > button:active,
.stDownloadButton > a:active,
[data-testid="stDownloadButton"] > a:active,
[data-testid="stFormSubmitButton"] button:active,
[data-testid="baseButton-primary"]:active {{
    opacity: 0.85 !important;
    transform: translateY(0) !important;
}}


/* KPI cards */
.kpi-card {{
    background:      linear-gradient(160deg, var(--surface-1), var(--surface-2)) !important;
    border:          1px solid var(--border-subtle) !important;
    border-radius:   16px                           !important;


    display:         flex;
    flex-direction:  column;
    align-items:     center;
    justify-content: center;
    text-align:      center;
    gap:             0.2rem;


    min-height:      90px;
    width:           100%;        /* Fill the Streamlit column fully */
    padding:         1rem 0.85rem !important;
    box-sizing:      border-box;

    /* Explicit base state prevents first-hover layout shift */
    transform:       translateY(0);
    will-change:     transform;
    backface-visibility: hidden;

    transition: border-color 0.18s, box-shadow 0.18s, transform 0.12s ease;
}}
.kpi-card:hover {{
    border-color: var(--border-strong)                       !important;
    box-shadow:   0 6px 18px rgba(111, 99, 255, 0.12)       !important;
    transform:    translateY(-1px);
}}
.kpi-icon {{
    font-size:   1.45rem;
    line-height: 1;
    flex-shrink: 0;
}}
.kpi-val {{
    /* Bright vivid purple — readable against dark card backgrounds */
    background:              linear-gradient(135deg, #a78bfa 0%, #c084fc 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-size:               1.75rem;
    font-weight:             800;
    line-height:             1.1;
}}
.kpi-lbl {{
    font-size:   0.76rem;
    font-weight: 500;
    color:       var(--text-secondary) !important;
    line-height: 1.3;


    white-space: nowrap;
}}
.kpi-body {{
    display:         flex;
    flex-direction:  column;
    align-items:     center;
    gap:             0.1rem;
}}


/* Session cards */
.sess-card {{
    background:    linear-gradient(160deg, var(--surface-1), var(--surface-2)) !important;
    border:        1px solid var(--border-subtle)  !important;
    border-radius: 12px                            !important;
    padding:       0.6rem 0.9rem                   !important;
    margin-bottom: 0.1rem;
    transition:    border-color 0.18s;
}}
.sess-card:hover {{
    border-color: var(--border-strong) !important;
}}


/* Analysis cards */
.ag-card {{
    background:    linear-gradient(160deg, var(--surface-1), var(--surface-2)) !important;
    border:        1px solid var(--border-subtle) !important;
    border-radius: 14px                           !important;
    padding:       0.9rem 0.8rem 0.65rem          !important;

    display:        flex;
    flex-direction: column;
    align-items:    flex-start;
    gap:            0.2rem;
    min-height:     108px;
    box-sizing:     border-box;


    margin-bottom:  0.1rem;


    transform:       translateY(0);
    will-change:     transform;
    backface-visibility: hidden;

    transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.12s ease;
}}
.ag-card:hover {{
    border-color: var(--border-strong)                  !important;
    box-shadow:   0 6px 18px rgba(111, 99, 255, 0.14)  !important;
    transform:    translateY(-1px);
}}


.ag-icon {{
    font-size:     1.5rem;
    line-height:   1;
    margin-bottom: 0.1rem;
    flex-shrink:   0;
}}
.brand_theme_vars {{
    display: none;
}}
.ag-name {{
    font-size:   0.88rem;
    font-weight: 700;
    color:       var(--text-primary)   !important;
    line-height: 1.25;
}}
.ag-desc {{
    font-size:  0.73rem;
    color:      var(--text-secondary)  !important;
    line-height: 1.35;
    opacity:    0.88;
    /* Clamp to two lines maximum — prevents layout shifts */
    display:            -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow:           hidden;
}}

/* Make the Select button directly below each ag-card full-width and
   flush to the card so they read as a single unit */
[data-testid="stVerticalBlock"] > div > [data-testid="stVerticalBlock"] [data-testid="stMarkdownContainer"]:has(.ag-card) + div [data-testid="stBaseButton-secondary"] > button,
[data-testid="column"] [data-testid="stMarkdownContainer"]:has(.ag-card) + div [data-testid="stBaseButton-secondary"] > button {{
    border-radius:  0 0 12px 12px  !important;
    margin-top:    -2px            !important;
    width:          100%           !important;
    min-height:     2rem           !important;
    font-size:      0.78rem        !important;
    padding:        0.25rem 0.5rem !important;
}}


/* Form inputs */
[data-testid="stTextInput"] input,
[data-testid="stSelectbox"] > div,
[data-testid="stMultiSelect"] > div,
[data-testid="stNumberInput"] input,
[data-testid="stTextArea"] textarea {{
    background:    var(--input-bg)   !important;
    color:         var(--input-text) !important;
    border:        1px solid var(--border-subtle) !important;
    border-radius: 8px               !important;
}}
[data-testid="stTextInput"] input::placeholder,
[data-testid="stTextArea"] textarea::placeholder {{
    color: var(--input-placeholder) !important;
}}
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {{
    border-color: var(--accent-purple) !important;
    box-shadow:   0 0 0 2px rgba(111, 99, 255, 0.20) !important;
}}


/* Tabs */
[data-testid="stTabs"] [data-baseweb="tab"] {{
    color:       var(--text-secondary) !important;
    font-weight: 500;
    border-bottom: 2px solid transparent;
    transition:  color 0.15s, border-color 0.15s;
}}
[data-testid="stTabs"] [aria-selected="true"] {{
    color:        var(--accent-purple) !important;
    border-color: var(--accent-purple) !important;
    font-weight:  700;
}}


/* Expanders */
[data-testid="stExpander"] {{
    background:    var(--surface-1) !important;
    border:        1px solid var(--border-subtle) !important;
    border-radius: 10px !important;
    overflow:      hidden;
}}
[data-testid="stExpander"] summary {{
    color:       var(--text-primary)  !important;
    font-weight: 600;
    padding:     0.55rem 0.9rem;
}}
[data-testid="stExpander"] summary:hover {{
    background: var(--surface-muted) !important;
}}


/* Metrics */
[data-testid="stMetric"] {{
    background:    var(--surface-1) !important;
    border:        1px solid var(--border-subtle) !important;
    border-radius: 12px             !important;
    padding:       0.75rem 1rem     !important;
}}
[data-testid="stMetricLabel"] {{
    color: var(--text-secondary) !important;
}}
[data-testid="stMetricValue"] {{
    color:       var(--text-primary) !important;
    font-weight: 800 !important;
}}
[data-testid="stMetricDelta"] {{
    font-weight: 600 !important;
}}


/* Divider */
hr {{
    border-color: var(--border-subtle) !important;
    margin: 1rem 0 !important;
}}


/* Footer */
.lytrize-footer {{
    position:        fixed;
    left:            0;
    right:           0;
    bottom:          0;
    z-index:         100;
    display:         flex;
    justify-content: center;
    align-items:     center;
    gap:             0.8rem;
    padding:         0.6rem 1rem;
    font-size:       0.74rem;
    color:           var(--text-secondary);
    background:      color-mix(in srgb, var(--bg-primary) 92%, transparent);
    backdrop-filter: blur(12px);
    border-top:      1px solid var(--border-subtle);
    contain:         layout style;
}}


/* Scrollbar */
::-webkit-scrollbar       {{ width: 6px; height: 6px; }}
::-webkit-scrollbar-track {{ background: var(--bg-primary); }}
::-webkit-scrollbar-thumb {{ background: var(--border-subtle); border-radius: 3px; }}
::-webkit-scrollbar-thumb:hover {{ background: var(--border-strong); }}

/* Hide scrollbars on chart containers (Plotly tables, etc.) */
.js-plotly-plot .plotly .main-svg,
.js-plotly-plot .plotly .draglayer,
.js-plotly-plot .plotly .subplot {{
    overflow: hidden !important;
}}

/* Hide scrollbar on Streamlit chart containers */
[data-testid="stPlotlyChart"] > div,
[data-testid="stPlotlyChart"] .js-plotly-plot {{
    overflow: hidden !important;
    scrollbar-width: none !important;
    -ms-overflow-style: none !important;
}}
[data-testid="stPlotlyChart"] > div::-webkit-scrollbar,
[data-testid="stPlotlyChart"] .js-plotly-plot::-webkit-scrollbar {{
    display: none !important;
    width: 0 !important;
    height: 0 !important;
}}

/* Also target the specific wrapper that contains the matrix table */
.stPlotlyChart > div,
.stPlotlyChart > div > div {{
    overflow: hidden !important;
    scrollbar-width: none !important;
    -ms-overflow-style: none !important;
}}
.stPlotlyChart > div::-webkit-scrollbar,
.stPlotlyChart > div > div::-webkit-scrollbar {{
    display: none !important;
}}


/* Tooltips */
[data-baseweb="tooltip"] {{
    background:    var(--surface-2) !important;
    border:        1px solid var(--border-subtle) !important;
    border-radius: 8px              !important;
}}


/* Responsive */
@media (max-width: 800px) {{
    .main .block-container {{
        padding-left:  1rem !important;
        padding-right: 1rem !important;
    }}

    div[data-testid="stVerticalBlock"]:has(#nav-target):not(:has(div[data-testid="stVerticalBlock"])) {{
        top:   4px  !important;
        right: 8px  !important;
        gap:   0.3rem !important;
    }}
    .kpi-lbl {{
        white-space: normal;
        font-size:   0.7rem;
    }}
    .ag-card {{ min-height: 90px; }}
}}

/* Hide file uploader hint */
[data-testid="stFileUploaderDropzoneInstructions"] > div > small {{
    display: none !important;
}}

{extra}

</style>
"""



def render_logo() -> None:
    """
    Render the fixed top bar + right-side nav buttons.
    Button order: ☀️/🌙 Theme | Sessions ⚙️ | ⏻ Sign Out
    """
    logo_src  = logo_data_uri()
    icon_html = (
        f'<img src="{logo_src}" alt="{APP_NAME}"'
        f' style="width:1.15rem;height:1.15rem;vertical-align:middle;">'
        if logo_src else '<span style="font-size:.5rem">📊</span>'
    )

    st.markdown(
        '<div style="height:0;overflow:visible;margin:0;padding:0;">'
        f'<div class="lytrize-topbar">'
        f'  <span class="lytrize-topbar-brand"'
        f'        style="display:inline-flex;align-items:center;gap:6px;">'
        f'    {icon_html}'
        f'    <span class="brand"'
        f'          style="font-family:\'Sora\',sans-serif;font-size:1.1rem;'
        f'                 font-weight:800;letter-spacing:0.02em;">'
        f'      {APP_NAME}'
        f'    </span>'
        f'  </span>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    is_guest   = st.session_state.get("is_guest", False)
    theme_mode = st.session_state.get("theme", "dark")

    with st.container():
        st.markdown('<div id="nav-target"></div>', unsafe_allow_html=True)

        # ── DISABLED: Theme toggle (☀️/🌙) — locked to dark for production ──
        # _icon = "☀️" if theme_mode == "dark" else "🌙"
        # _help = "Switch to light mode" if theme_mode == "dark" else "Switch to dark mode"
        # if st.button(_icon, key="global_nav_theme", help=_help):
        #     set_theme_mode("light" if theme_mode == "dark" else "dark")
        #     st.rerun()
        # ── ── ── ──

        st.markdown(
            "<span style='color:rgba(148,163,184,0.45);font-size:1rem;"
            "line-height:1;pointer-events:none;user-select:none;margin:0 0.3rem;'>│</span>",
            unsafe_allow_html=True,
        )

        if st.button(" Sessions ⚙️", key="global_nav_profile", help="Backup-Restore"):
            st.session_state.page = "profile"
            st.rerun()

        if not is_guest:
            st.markdown(
                "<span style='color:rgba(148,163,184,0.45);font-size:1rem;"
                "line-height:1;pointer-events:none;user-select:none;'>│</span>",
                unsafe_allow_html=True,
            )
            if st.button("⏻ Sign Out", key="global_nav_logout",
                         help="Sign out of your account"):
                _do_logout()


def _do_logout() -> None:
    """Revoke the session token, clear state, and redirect to the profile page."""
    from modules.database import revoke_token, log_activity

    try:
        base     = Path(__file__).resolve().parents[2]
        tok_path = base / ".local" / "share" / "lytrize" / "session.token"
        token    = tok_path.read_text().strip() if tok_path.exists() else ""
        if token:
            revoke_token(token)
        for fname in ("session.token", "session.user"):
            p = base / ".local" / "share" / "lytrize" / fname
            if p.exists():
                p.write_text("")
    except Exception:
        pass

    try:
        log_activity(st.session_state.get("user_id", 0), "logout")
    except Exception:
        pass

    st.query_params.clear()
    st.session_state.clear()
    st.session_state.page = "profile"
    st.rerun()



def inject_footer() -> None:
    """Render the fixed bottom footer bar."""
    st.markdown(
        f'<div class="lytrize-footer">'
        f'  <span>{APP_NAME} v{APP_VERSION}</span>'
        f'  <span>|</span>'
        f'  <span style="color:var(--text-secondary);">Light-weight &amp; Offline</span>'
        f'  <span>|</span>'
        f'  <a href="https://github.com/VidalNat/Lytrize/discussions/categories/q-a" style="color:var(--text-secondary); text-decoration: none;">Feedback 🗒️</a>'
        f'</div>',
        unsafe_allow_html=True,
    )
