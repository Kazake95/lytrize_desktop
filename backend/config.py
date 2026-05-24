# Runtime constants shared between the launcher and the Streamlit backend.
#
# APP_HOST / APP_PORT are authoritative in desktop/gui.py (passed to
# `streamlit run` via CLI flags) and in backend/.streamlit/config.toml.
# Modules that need these values should read from those sources rather
# than importing here, so there is a single source of truth.
#
# This file is intentionally kept minimal. Add shared constants here only
# when they are genuinely needed by more than one module.

APP_NAME    = "Lytrize"
APP_VERSION = "1.2"
APP_HOST    = "127.0.0.1"
APP_PORT    = 8501
