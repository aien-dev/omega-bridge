#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
# Invoke with quiet-build tools/test.sh on a shared build host.
tools/build.sh
python3 tests/differential.py
python3 tests/refusals.py
python3 tests/attachments.py
python3 tests/controls.py
python3 tests/robustness.py
printf 'ALL SUITES RC=0\n'
