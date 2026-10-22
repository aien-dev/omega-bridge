#!/bin/sh
# Guard the entire shared output tree before any default build writes.
# Single-user preflight, not a defence against hostile concurrent mutations.
set -eu
cd "$(dirname "$0")/.."
fail() { echo 'omega: unsafe build output tree; preserve it and use a clean build directory' >&2; exit 73; }
[ ! -L build ] || fail
[ -e build ] || exit 0
[ -d build ] || fail
# Never follow links. Hardlinked files can alias unrelated writable user files.
# Refuse special files as well, including FIFOs/devices that redirection opens.
unsafe=$(find build \( -type l -o -type f -links +1 -o ! -type d ! -type f \) -print) || fail
[ -z "$unsafe" ] || fail
