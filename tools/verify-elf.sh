#!/bin/sh
# This gate must succeed before a newly built executable is run.
set -eu
[ "$#" = 1 ] && [ -s "$1" ] || exit 65
headers=$(readelf -h -l -d -- "$1") || exit 65
printf '%s\n' "$headers" | grep -q 'Machine:.*AArch64' || exit 65
printf '%s\n' "$headers" | grep -q 'Type:.*EXEC' || exit 65
if printf '%s\n' "$headers" | grep -Eq 'INTERP|DYNAMIC|NEEDED'; then
    echo 'omega: dynamic executable refused' >&2
    exit 65
fi
