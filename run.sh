#!/usr/bin/env bash
# Linux launcher (counterpart of run.bat). Activates .venv if present,
# otherwise relies on whatever python is on PATH.
set -e
cd "$(dirname "$0")"
if [ -x .venv/bin/python ]; then
    exec .venv/bin/python flasher/main.py
else
    exec python3 flasher/main.py
fi
