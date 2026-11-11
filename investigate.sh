#!/bin/bash
# Investigate one flagged transaction with the AI agent.
# Usage: ./investigate.sh 3429911
set -e
cd "$(dirname "$0")"
source venv/bin/activate
cd scripts
python ai_agent.py "$1"
