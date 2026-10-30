#!/bin/sh
# Cross-build every ABI v2 caller, then execute under qemu-x86_64.
# Native x86 hardware is deliberately NOT_RUN; see suite.py for prerequisites.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
exec python3 "$ROOT/tests/native/x86/suite.py" "$@"
