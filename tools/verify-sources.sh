#!/bin/sh
# Validate the immutable import lock before consuming any source or path list.
set -eu
cd "$(dirname "$0")/.."
fail() { echo 'omega: source provenance mismatch' >&2; exit 65; }
[ "$(sha256sum provenance/lock.sha256 | cut -d ' ' -f1)" = bdbaa59860847d5c842af705ddc9230b98c70a1a3c8babe25be339af284e7ad7 ] || fail
sha256sum --status -c provenance/lock.sha256 || fail
[ "${1-}" = --lock-only ] && exit 0
sha256sum --status -c provenance/sources.sha256 || fail
# Refuse source overlays and symlinks, even if a file was not consumed previously.
expected=$(cat provenance/seed.files provenance/math.files | grep '^seed/' | LC_ALL=C sort)
actual=$(find seed -type f | LC_ALL=C sort)
[ "$expected" = "$actual" ] || fail
[ -z "$(find seed -type l -print)" ] || fail
