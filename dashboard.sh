#!/bin/bash
# Launches the visual dashboard for the investigation agent in your browser.
# Usage: ./dashboard.sh
set -e
cd "$(dirname "$0")"
source venv/bin/activate
streamlit run scripts/app.py
