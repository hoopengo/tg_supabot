#!/bin/bash
set -eo pipefail
shopt -s nullglob

# Run migrations
cd src
alembic upgrade head
exec python -m bot
