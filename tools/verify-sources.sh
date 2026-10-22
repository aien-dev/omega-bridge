#!/bin/sh
# Validate the immutable import lock before consuming any source or path list.
set -eu
cd "$(dirname "$0")/.."
fail() { echo 'omega: source provenance mismatch' >&2; exit 65; }
[ "$(sha256sum provenance/lock.sha256 | cut -d ' ' -f1)" = 4eacace2e6046618ada1b991a99cb4e2ce002bd068f914e1c97fd240608203bf ] || fail
sha256sum --status -c provenance/lock.sha256 || fail
[ "${1-}" = --lock-only ] && exit 0
sha256sum --status -c provenance/sources.sha256 || fail
[ "$(sha256sum src/toc.om | cut -d ' ' -f1)" = "$(awk '$1=="converter-source-sha256" {print $2}' provenance/pins)" ] || fail
# Refuse source overlays and symlinks, even if a file was not consumed previously.
expected=$(cat provenance/seed.files provenance/math.files | grep '^seed/' | LC_ALL=C sort)
actual=$(find seed -type f | LC_ALL=C sort)
[ "$expected" = "$actual" ] || fail
[ -z "$(find seed -type l -print)" ] || fail
