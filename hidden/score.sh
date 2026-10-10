#!/usr/bin/env bash
# Usage: hidden/score.sh <build-dir>; prints passed/total and failing test names for the hidden suite run against that build.
set -u
BUILD=$(realpath "$1")
HERE=$(cd "$(dirname "$0")" && pwd)
cd "$BUILD" || exit 1
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$BUILD:$HERE" /home/lance/.local/bin/mise exec -- python -m pytest -c /dev/null --rootdir "$BUILD" -p no:cacheprovider --import-mode=importlib -q --tb=no -rf "$HERE/test_hidden.py" 2>&1 | rg -v '^$' | tail -n 120
