#!/bin/sh
# HAND-WRITTEN, NOT generated. Thin wrapper: all logic lives in conformance.py.
set -e
exec "${PYTHON:-python3}" "$(dirname "$0")/conformance.py" "$@"
