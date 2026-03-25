#!/bin/bash
# Breathe Agent Quick Start Script
echo "--- Breathe Agent Starting ---"
cd "$(dirname "$0")"
PYTHONUNBUFFERED=1 python3 main.py
