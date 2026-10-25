#!/bin/sh
# Explicit external C reference route only. Never an automatic native fallback.
# OMEGA_REFERENCE_SOURCE is source from omega-mv 697539a577ee7594ba12d905062f2e09cb9cc77c.
# No network, install, opaque executable, seed bootstrap, or GPU command here.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
SRC=${OMEGA_REFERENCE_SOURCE:?set OMEGA_REFERENCE_SOURCE to the pinned Omega reference source}
SRC=$(CDPATH= cd -- "$SRC" && pwd)
OUT=$ROOT/build/ggml-reference
mkdir -p "$OUT"
(cd "$SRC" && sha256sum -c "$ROOT/tests/ggml/reference-source.sha256") > "$OUT/source-check.log"
CC=${CC:-cc}
"$CC" -std=gnu11 -O2 -Wall -Wextra -Werror -D_GNU_SOURCE \
    "$SRC/tools/omegese/omegese.c" -o "$OUT/omegese"
# Freeze the compiler-library list from Omega mk/omega-emit.mk in the manifest.
# Do not compile additional unpinned .c files merely because they are present.
# No generated C/Python translation of the policy is used.
set --
for file in $(sed -n 's/^[0-9a-f]*  \(src\/compiler\/.*\.c\)$/\1/p' "$ROOT/tests/ggml/reference-source.sha256"); do
    set -- "$@" "$SRC/$file"
done
"$CC" -std=gnu11 -O2 -Wall -Wextra -Werror -D_GNU_SOURCE \
    -I"$SRC/src" -I"$SRC/src/compiler" "$SRC/tools/omega_emit/omega_emit.c" \
    "$@" "$SRC/src/sha256.c" -lm -o "$OUT/omega_emit"
"$CC" -std=gnu11 -O2 -Wall -Wextra -Werror -D_GNU_SOURCE \
    -I"$SRC/src" -I"$SRC/src/compiler" "$ROOT/tests/ggml/reference_main.c" \
    "$@" "$SRC/src/sha256.c" -lm -o "$OUT/reference"
cat "$ROOT/adapters/ggml/strict_node.om" "$ROOT/adapters/ggml/strict_snapshot.om" \
    "$ROOT/tests/ggml/placement.om" | sed '/^note /d' > "$OUT/placement.om"
"$OUT/omegese" emit "$OUT/placement.om" "$OUT/placement.json"
"$OUT/omega_emit" emit "$OUT/placement.json" "$OUT/placement.oscir"
"$OUT/reference" "$OUT/placement.oscir"
echo 'PASS GGML placement policy: host reference only'
echo 'NOT_RUN seeded native compilation/execution, GGML callbacks/hook, GPU/model/hardware'
