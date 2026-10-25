#!/bin/sh
# Reference source-provenance controls, including a transitive local header.
# Both must fail at the hash gate, before invoking any C compiler.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
SRC=${OMEGA_REFERENCE_SOURCE:?set OMEGA_REFERENCE_SOURCE to the pinned reference source}
SRC=$(CDPATH= cd -- "$SRC" && pwd)
mkdir -p "$ROOT/build"
OUT=$(mktemp -d "$ROOT/build/ggml-source-controls.XXXXXXXX")
mkdir -p "$OUT/source"
# Include the known transitive header explicitly so this regression also runs
# against the defective 30-entry manifest rather than failing from missing C types.
for file in $(sed 's/^[0-9a-f]*  //' "$ROOT/tests/ggml/reference-source.sha256") src/compiler/model/osc_model.h; do
    mkdir -p "$OUT/source/$(dirname "$file")"
    cp "$SRC/$file" "$OUT/source/$file"
done
cat > "$OUT/deny-cc" <<'SCRIPT'
#!/bin/sh
: > "${GGML_CC_MARKER:?}"
exit 99
SCRIPT
chmod +x "$OUT/deny-cc"
for file in src/compiler/osc_interp.c src/compiler/model/osc_model.h; do
    cp "$SRC/$file" "$OUT/source/$file"
    printf '\n/* deliberate source-provenance control */\n' >> "$OUT/source/$file"
    rm -f "$OUT/compiler-invoked"
    rc=0
    GGML_CC_MARKER="$OUT/compiler-invoked" CC="$OUT/deny-cc" \
        OMEGA_REFERENCE_SOURCE="$OUT/source" sh "$ROOT/tests/ggml/run-reference.sh" \
        > "$OUT/$(basename "$file").log" 2>&1 || rc=$?
    if [ "$rc" != 1 ] || [ -e "$OUT/compiler-invoked" ] || \
        ! grep -Fx "$file: FAILED" "$ROOT/build/ggml-reference/source-check.log" > /dev/null; then
        echo "INVALID/UNCAUGHT tampered $file: rc=$rc (hash refusal before compiler required)" >&2
        exit 1
    fi
    cp "$ROOT/build/ggml-reference/source-check.log" "$OUT/$(basename "$file").hash.log"
    cp "$SRC/$file" "$OUT/source/$file"
    echo "CAUGHT tampered $file: exact hash refusal before compiler"
done
echo 'PASS 2/2 source-provenance controls; no native/hardware qualification'
