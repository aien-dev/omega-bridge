#!/bin/sh
# Source-only replay on Linux AArch64. No C compiler, assembler or linker.
set -eu
cd "$(dirname "$0")/.."
[ "$(uname -m)" = aarch64 ] || { echo 'bootstrap requires Linux AArch64' >&2; exit 1; }
pin=29b12760f4c962606411d6bf25032aedef063301
mkdir -p build/bootstrap
if [ -n "${OMEGA_SOURCE:-}" ]; then
    source_repo=$OMEGA_SOURCE
else
    source_repo=build/bootstrap/upstream
    if [ ! -d "$source_repo/.git" ]; then git init -q "$source_repo"; fi
    git -C "$source_repo" fetch -q --depth=1 https://github.com/aien-spark/omega.git "$pin"
fi
# Archive only audited source rungs. Never import an opaque executable.
git -C "$source_repo" archive "$pin" seed/rung0/seed0.hex seed/rung0/load0.sh seed/rung1/hex1.hex seed/rung2/asm2.hex1 seed/rung2/table.s2 seed/rung3/table3.s2 seed/rung4/table4.s2 seed/rung4/om4.s seed/rung4/mk4.sh seed/omc/omc.om > build/bootstrap/source.tar
mkdir -p build/bootstrap/source
tar -xf build/bootstrap/source.tar -C build/bootstrap/source
cd build/bootstrap/source
verify() {
    [ -s "$1" ]
    file "$1" | grep -q 'ELF 64-bit.*ARM aarch64'
    chmod +x "$1"
}
sh seed/rung0/load0.sh seed/rung0/seed0.hex seed/rung0/seed0.bin
verify seed/rung0/seed0.bin
seed/rung0/seed0.bin < seed/rung0/seed0.hex > seed/rung0/self
cmp seed/rung0/seed0.bin seed/rung0/self
seed/rung0/seed0.bin < seed/rung1/hex1.hex > seed/rung1/hex1.bin
verify seed/rung1/hex1.bin
seed/rung1/hex1.bin < seed/rung2/asm2.hex1 > seed/rung2/asm2.bin
verify seed/rung2/asm2.bin
sh seed/rung4/mk4.sh
verify seed/rung4/om4.bin
seed/rung4/om4.bin < seed/omc/omc.om > ../stage1
verify ../stage1
../stage1 < seed/omc/omc.om > ../stage2
verify ../stage2
../stage2 < seed/omc/omc.om > ../stage3
verify ../stage3
cmp ../stage1 ../stage2
cmp ../stage2 ../stage3
[ "$(sha256sum ../stage3 | cut -d' ' -f1)" = 191b776ef98821597c3e30655da6d680a9b66edbc9ceaca3c39c61ea6df098e9 ]
cp ../stage3 ../omc
printf 'source=%s\n' "$pin"
sha256sum seed/omc/omc.om ../omc
printf 'bootstrap fixpoint RC=0\n'
