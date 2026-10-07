#!/bin/sh
export PATH=/usr/local/bin:/usr/bin:/bin
export PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1
cd /service || exit 1
exec python3 /service/app.py
