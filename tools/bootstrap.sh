#!/bin/sh
# Source-only replay on Linux AArch64, using committed, hashed source imports.
set -eu
cd "$(dirname "$0")/.."
tools/check-build-paths.sh
[ "$(uname -s)/$(uname -m)" = Linux/aarch64 ] || { echo 'omega: requires Linux AArch64' >&2; exit 69; }
[ "$#" = 0 ] || { [ "$#" = 1 ] && [ "$1" = --offline ]; } || exit 64
tools/verify-sources.sh
B=build/bootstrap
mkdir -p "$B"
elf() {
    tools/verify-elf.sh "$1"
    chmod +x "$1"
}
sh seed/rung0/load0.sh seed/rung0/seed0.hex "$B/seed0"
elf "$B/seed0"
"$B/seed0" < seed/rung0/seed0.hex > "$B/seed0.self"
cmp "$B/seed0" "$B/seed0.self"
"$B/seed0" < seed/rung1/hex1.hex > "$B/hex1"
elf "$B/hex1"
"$B/hex1" < seed/rung2/asm2.hex1 > "$B/asm2"
elf "$B/asm2"
cat seed/rung2/table.s2 seed/rung3/table3.s2 seed/rung4/table4.s2 seed/rung4/om4.s > "$B/om4.input"
"$B/asm2" < "$B/om4.input" > "$B/om4"
elf "$B/om4"
[ "$(stat -c %s "$B/om4")" = "$(od -An -tu4 -j96 -N4 "$B/om4" | tr -d ' ')" ]
"$B/om4" < seed/omc/omc.om > "$B/stage1"
elf "$B/stage1"
"$B/stage1" < seed/omc/omc.om > "$B/stage2"
elf "$B/stage2"
cmp "$B/stage1" "$B/stage2"
[ "$(sha256sum "$B/stage2" | cut -d' ' -f1)" = 191b776ef98821597c3e30655da6d680a9b66edbc9ceaca3c39c61ea6df098e9 ]
cp "$B/stage2" "$B/omc"
sha256sum "$B/seed0" "$B/hex1" "$B/asm2" "$B/om4" "$B/omc" > "$B/binaries.sha256"
printf 'PASS source-only seed bootstrap and compiler fixpoint\n'
