#!/bin/sh
# Native call ABI v2 qualification (docs/NATIVE-ABI.md, ABI v2). OMEGA_NATIVE_OMC names the seeded omc
# (pinned by tools/native); OMEGA_NATIVE_OMC2 names the OM-2 compiler that compiles this folder's OM-2
# units (omega-mv om2/compiler-s4 @ f6a6492fd, sha256 49923639...803ec, when this run was recorded; its
# digest is what the identities carry). A missing language toolchain is reported
# NOT_RUN, never PASS. Exit 0 only when every run check passed. `run.sh measure` also runs the cost
# measurement (tests/native/v2/measure.c).
set -eu
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
T=$ROOT/tests/native/v2
O=$ROOT/build/native-v2
PIN=$(sed -n 's/^PIN=//p' "$ROOT/tools/native")
OMC=${OMEGA_NATIVE_OMC:?set OMEGA_NATIVE_OMC to the seeded omc (omega seed/out/omc, sha256 $PIN)}
OMC2=${OMEGA_NATIVE_OMC2:?set OMEGA_NATIVE_OMC2 to the OM-2 compiler (omega-mv om2/compiler-s4 seed/out/omc)}
export OMEGA_NATIVE_OMC OMEGA_NATIVE_OMC2="$OMC2"
got=$(sha256sum < "$OMC" | cut -d' ' -f1)
[ "$got" = "$PIN" ] || { echo "FAIL omc sha256 $got, pinned $PIN"; exit 1; }
rm -rf "$O"; mkdir -p "$O"
fails=0; notrun=""
pass() { echo "PASS $1"; }
fail() { echo "FAIL $1"; fails=$((fails + 1)); }
echo "INFO omc $got; OM-2 compiler $OMC2 sha256 $(sha256sum < "$OMC2" | cut -d' ' -f1)"
V2="vec lay one"
units="$ROOT/tests/native/madd.om"; for u in $V2; do units="$units $T/$u.om"; done
if "$ROOT/tools/native" "$O" $units > "$O/tools-native.log" 2>&1; then pass "tools/native: madd (OM-1) + vec, lay, one (OM-2): library, six bindings, omega_api.h"
else fail "tools/native"; cat "$O/tools-native.log"; exit 1; fi
W=$O/work; GEN=$W/native-gen

# basegen REV NAME: the historical generator, with the current C runtime prelude and only
# private assembly-linkage directives normalized. Public wrappers, signatures, compiler bytes
# and declarations remain byte-compared. REVs are reachable on this branch: 5458684 has the blob
# of pre-rebase 3f05908, 3d79d77 that of 3bb8b8a; 74fcd43 is main before host words (after #26's
# f32 and ushort kinds, which changed the python output and accept fsum and halve).
basegen() {
  PRE=$(grep '^text pre ' "$ROOT/src/native.om"); export PRE
  git -C "$ROOT" show "$1:src/native.om" | awk '/^text pre /{print ENVIRON["PRE"]; next} /^text fr |^text fv /{gsub(/[.]globl ombr_code_/, ".local ombr_code_"); gsub(/[.]globl ombr_entry_/, ".local ombr_entry_"); gsub(/[.]globl ombr2_code_/, ".local ombr2_code_"); gsub(/[.]globl ombr2_entry_/, ".local ombr2_entry_")} {print}' > "$O/native-$2.om"
  "$OMC" < "$O/native-$2.om" > "$O/gen-$2"; chmod +x "$O/gen-$2"
}

# 1. ABI v1 output unchanged: the generator of 74fcd43 (plus the current prelude) and this one, on every
# existing unit alone and on the v1 suite's set, for all six outputs.
basegen 74fcd43 v1
same=0; diff=0; : > "$O/v1set.in"
for u in "$ROOT"/tests/native/*.om "$ROOT"/tests/native/g1/*.om; do
  "$OMC" < "$u" > "$O/one.bin" 2> /dev/null || continue
  { cat "$u"; printf '\0'; printf '%08d' "$(wc -c < "$O/one.bin")"; cat "$O/one.bin"; } > "$O/one.in"
  case "$u" in */g1/*) ;; *) cat "$O/one.in" >> "$O/v1set.in";; esac
  for w in c h python rust zig go; do
    a=0; "$O/gen-v1" $w < "$O/one.in" > "$O/a.out" 2> /dev/null || a=$?
    b=0; "$GEN" $w < "$O/one.in" > "$O/b.out" 2> /dev/null || b=$?
    if [ $a = $b ] && cmp -s "$O/a.out" "$O/b.out"; then same=$((same + 1)); else diff=$((diff + 1)); echo "DIFF $u $w ($a/$b)"; fi
  done
done
for w in c h python rust zig go; do
  "$O/gen-v1" $w < "$O/v1set.in" > "$O/a.out"; "$GEN" $w < "$O/v1set.in" > "$O/b.out"
  if cmp -s "$O/a.out" "$O/b.out"; then same=$((same + 1)); else diff=$((diff + 1)); echo "DIFF set $w"; fi
done
if [ $diff = 0 ]; then pass "ABI v1 bindings byte-identical to 74fcd43's generator (runtime/private linkage normalized): $same unit x output cases (every tests/native and g1 unit, and the set)"
else fail "ABI v1 bindings changed in $diff cases"; fi

# 2. Identity: each v2 unit's embedded source digest equals sha256sum of its file (oracle), the omc digest
# equals sha256 of the OM-2 compiler used, and work/ident.txt records every unit, the OM-1 one included.
ok=1
for u in $V2; do
  want="omega-ident 1 unit=$u abi=2 profile=OM-2 src=$(sha256sum < "$T/$u.om" | cut -d' ' -f1) omc=$(sha256sum < "$OMC2" | cut -d' ' -f1)"
  grep -q -F "\"$want\"" "$O/omega_native.c" || { ok=0; echo "missing: $want"; }
  grep -q -F "OMEGA2_IDENT_$u \"$want\"" "$O/omega_native.h" || ok=0
  grep -q -F "$want path=$T/$u.om" "$W/ident.txt" || ok=0
done
grep -q "unit=madd abi=1 profile=OM-1 src=$(sha256sum < "$ROOT/tests/native/madd.om" | cut -d' ' -f1) omc=$PIN" "$W/ident.txt" || ok=0
if [ $ok = 1 ]; then pass "identities: source sha256 (computed by native.om) == sha256sum, omc digest, profile; ident.txt has the OM-1 unit too"
else fail "identity strings"; fi

# 3. The embedded code is the compiler's bytes, unchanged (read at ombr2_code_<unit> in the library).
emb() {
  s=$(objdump -t "$1" | awk -v n="$2" '$NF==n{print $1}')
  [ -n "$s" ] || return 1
  objdump -h "$1" | awk '$2 ~ /^\./ {print $3, $4, $6}' | while read -r sz vma fo; do
    if [ $((0x$vma)) -le $((0x$s)) ] && [ $((0x$s)) -lt $((0x$vma + 0x$sz)) ]; then echo $((0x$s - 0x$vma + 0x$fo)); break; fi
  done
}
ok=1
for u in $V2; do
  off=$(emb "$O/libomega_native.so" "ombr2_code_$u") || { ok=0; continue; }
  [ -n "$off" ] || { ok=0; continue; }
  dd if="$O/libomega_native.so" bs=1 skip="$off" count="$(wc -c < "$W/$u.bin")" 2> /dev/null > "$O/$u.emb"
  cmp -s "$W/$u.bin" "$O/$u.emb" || ok=0
done
if [ $ok = 1 ]; then pass "embedded code == compiler output, per OM-2 unit"; else fail "embedded code differs"; fi
# The exported symbols: one omega2_ per export, one ident per unit, the OM-1 unit's omega_, nothing else.
nm -D --defined-only "$O/libomega_native.so" | awk '{print $3}' | grep -E '^omega' | sort > "$O/syms.txt"
printf '%s\n' omega2_absorb omega2_bsum omega2_digest omega2_fillv omega2_halt omega2_ident_lay omega2_ident_one \
  omega2_ident_vec omega2_lsum omega2_swap8 omega2_two omega2_vcopy omega2_vlen omega2_vpart omega2_wsum omega_madd | sort > "$O/syms.want"
if cmp -s "$O/syms.txt" "$O/syms.want"; then pass "exported symbols: 15 omega2_ (12 exports, 3 idents) + omega_madd; no psum, no v1 name for a v2 unit"
else fail "exported symbols"; diff "$O/syms.want" "$O/syms.txt" || true; fi
if nm --defined-only "$O/libomega_native.so" | awk '$3 ~ /^ombr2_code_/ {n++; if ($2 != "t") bad=1} END {exit bad || n != 3}'; then
  pass "ABI v2 embedded code labels are private local text symbols"
else fail "ABI v2 private code linkage"; fi
if nm --defined-only "$O/libomega_native.so" | awk '$3 ~ /^ombr/ && $2 !~ /^[a-z]$/ {bad=1} END {exit bad}'; then
  pass "all ABI v1/v2 private runtime, code and entry symbols have local binding"
else fail "nonlocal private runtime symbol"; fi

# 4. No caller declares an Omega function by hand.
if grep -n -E 'uint32_t omega|fn omega|argtypes|CDLL|import "C"' "$T"/caller.* > "$O/hand.log"; then
  fail "a caller declares an Omega function by hand"; cat "$O/hand.log"
else pass "no v2 caller declares an Omega function by hand"; fi

# 5. The six language callers (oracles).
run() { lang=$1; shift; if "$@" > "$O/$lang.log" 2>&1; then pass "$lang caller ($(grep -c '^PASS' "$O/$lang.log") checks)"; else fail "$lang caller"; cat "$O/$lang.log"; fi; }
bld() { lang=$1; shift; if "$@" > "$O/$lang-build.log" 2>&1; then return 0; fi; fail "$lang build"; cat "$O/$lang-build.log"; return 1; }
cp "$T"/caller.* "$O/"
bld c cc -std=gnu11 -O2 -Wall -Wextra -Werror -pthread -I "$O" "$O/caller.c" -L"$O" -lomega_native -Wl,-rpath,"$O" -ldl -o "$O/caller_c" \
  && run c "$O/caller_c"
if OMEGA_NATIVE_CFLAGS="-nostartfiles -mbranch-protection=standard -Wl,-z,force-bti" "$ROOT/tools/native" "$O/bti" $units > "$O/bti-native.log" 2>&1 \
  && cmp -s "$O/bti/omega_native.c" "$O/omega_native.c" \
  && bld c-bti cc -std=gnu11 -O2 -Wall -Wextra -Werror -pthread -I "$O/bti" "$O/caller.c" -L"$O/bti" -lomega_native -Wl,-rpath,"$O/bti" -ldl -o "$O/bti/caller_c"; then
  if readelf -n "$O/bti/libomega_native.so" | grep -q "feature: BTI"; then run c-bti "$O/bti/caller_c"; else fail "c-bti build carries no BTI property"; fi
else fail "c-bti library build"; cat "$O/bti-native.log"; fi
if command -v c++ > /dev/null; then
  bld cpp c++ -std=c++17 -O2 -Wall -Wextra -Werror -I "$O" "$O/caller.cpp" -L"$O" -lomega_native -Wl,-rpath,"$O" -o "$O/caller_cpp" && run cpp "$O/caller_cpp"
else notrun="$notrun c++"; fi
if command -v python3 > /dev/null; then run python python3 -I "$O/caller.py" "$O"; else notrun="$notrun python"; fi
if command -v rustc > /dev/null; then
  bld rust rustc -O --edition 2021 -D warnings "$O/caller.rs" -L "$O" -C link-arg=-Wl,-rpath,"$O" -o "$O/caller_rs" && run rust "$O/caller_rs"
  bld rust-2024 rustc -O --edition 2024 -D warnings "$O/caller.rs" -L "$O" -C link-arg=-Wl,-rpath,"$O" -o "$O/caller_rs24" && run rust-2024 "$O/caller_rs24"
else notrun="$notrun rust"; fi
if command -v zig > /dev/null; then
  bld zig sh -c 'cd "$1" && zig build-exe caller.zig -L. -lomega_native -lc -rpath "$1" -femit-bin=caller_zig' _ "$O" && run zig "$O/caller_zig"
else notrun="$notrun zig"; fi
gopkg() { mkdir -p "$1/omeganative"; cp "$2/omega_native.go" "$2/omega_native.h" "$3/libomega_native.so" "$1/omeganative/"; cp "$4" "$1/"; }
if command -v go > /dev/null; then
  gopkg "$O/go" "$O" "$O" "$O/caller.go"
  bld go sh -c 'cd "$1" && go mod init omegacaller > /dev/null 2>&1 && CGO_LDFLAGS="-Wl,-rpath,$1/omeganative" go build -o caller_go .' _ "$O/go" && run go "$O/go/caller_go"
else notrun="$notrun go"; fi

# 6. Link-time refusal: the v1 bindings of an OM-1 unit named bsum declare omega_bsum; every language's
# caller built from them against the library above (where bsum is the v2 export omega2_bsum) must fail
# to link (Python: fail to import), for that reason.
L=$O/v1use; mkdir -p "$L"; cp "$T"/v1use/use.* "$L/"; cp "$O/libomega_native.so" "$L/"
"$OMC" < "$T/v1use/bsum.om" > "$L/bsum.bin"
{ cat "$T/v1use/bsum.om"; printf '\0'; printf '%08d' "$(wc -c < "$L/bsum.bin")"; cat "$L/bsum.bin"; } > "$L/bsum.in"
for w in h:h python:py rust:rs zig:zig go:go; do "$GEN" ${w%%:*} < "$L/bsum.in" > "$L/omega_native.${w##*:}"; done
refl() {
  lang=$1; pat=$2; shift 2
  if "$@" > "$L/$lang.log" 2>&1; then fail "$lang: a v1 caller of a v2 unit linked"
  elif grep -q -E "$pat" "$L/$lang.log"; then pass "$lang refuses the v1 symbol at link time: $(grep -m1 -o -E "$pat" "$L/$lang.log")"
  else fail "$lang v1 caller failed for another reason"; cat "$L/$lang.log"; fi
}
refl c "undefined reference to .omega_bsum." cc -std=gnu11 -I "$L" "$L/use.c" -L"$L" -lomega_native -o "$L/use_c"
command -v c++ > /dev/null && refl cpp "undefined reference to .omega_bsum." c++ -std=c++17 -I "$L" "$L/use.cpp" -L"$L" -lomega_native -o "$L/use_cpp"
command -v python3 > /dev/null && refl python "undefined symbol: omega_bsum" python3 -I "$L/use.py" "$L"
command -v rustc > /dev/null && refl rust "undefined reference to .omega_bsum.|undefined symbol: omega_bsum" rustc --edition 2021 "$L/use.rs" -L "$L" -o "$L/use_rs"
command -v zig > /dev/null && refl zig "undefined symbol: omega_bsum|undefined reference to .omega_bsum." sh -c 'cd "$1" && zig build-exe use.zig -L. -lomega_native -lc -femit-bin=use_zig' _ "$L"
if command -v go > /dev/null; then
  gopkg "$L/go" "$L" "$L" "$L/use.go"
  refl go "undefined reference to .omega_bsum." sh -c 'cd "$1" && go mod init omegacaller > /dev/null 2>&1 && go build -o use_go .' _ "$L/go"
fi

# 7. Stale identity: bindings generated from vec.om with one note byte changed, against the library of
# the real vec.om. The C check sees two identities; the Python binding refuses to import.
S=$O/stale; mkdir -p "$S"; cp "$O/libomega_native.so" "$S/"
sed '1s/an OM-2 unit/An OM-2 unit/' "$T/vec.om" > "$S/vec.om"
{ cat "$S/vec.om"; printf '\0'; printf '%08d' "$(wc -c < "$W/vec.bin")"; cat "$W/vec.bin"; printf 'omega-unit vec %s\n' "$(sha256sum < "$OMC2" | cut -d' ' -f1)"; } > "$S/vec.in"
"$GEN" h < "$S/vec.in" > "$S/omega_native.h"; "$GEN" python < "$S/vec.in" > "$S/omega_native.py"
cc -std=gnu11 -I "$S" "$T/stale.c" -L"$S" -lomega_native -Wl,-rpath,"$S" -o "$S/stale_c"
rc=0; "$S/stale_c" > "$S/c.log" 2>&1 || rc=$?
if [ $rc = 3 ] && grep -q "src=$(sha256sum < "$S/vec.om" | cut -d' ' -f1)" "$S/c.log"; then pass "stale identity: C header from another vec.om is detected (two src digests)"
else fail "stale identity not detected by C (exit $rc)"; cat "$S/c.log"; fi
cc -std=gnu11 -I "$O" "$T/stale.c" -L"$O" -lomega_native -Wl,-rpath,"$O" -o "$S/fresh_c"
if "$S/fresh_c"; then pass "stale identity control: the matching header passes"; else fail "stale control"; fi
if command -v python3 > /dev/null; then
  if python3 -I -c "import sys; sys.path.insert(0, '$S'); import omega_native" > "$S/py.log" 2>&1; then fail "python imported a stale binding"
  elif grep -q "ImportError: libomega_native.so is not the library" "$S/py.log"; then pass "stale identity: the Python binding refuses to import"
  else fail "python stale import failed for another reason"; cat "$S/py.log"; fi
fi

# 8. Generator refusals for OM-2 input (exit 110, no output) and a control.
code=$W/vec.bin
f2() { printf '%s' "$1"; printf '\0'; printf '%08d' "$(wc -c < "$2")"; cat "$2"; printf '%s' "$3"; }
TR="omega-unit u $(printf '%064d' 0)
"
refuse() {
  rc=0; "$GEN" c < "$O/ref.in" > "$O/ref.out" 2> /dev/null || rc=$?
  if [ "$rc" = 110 ] && [ ! -s "$O/ref.out" ]; then pass "generator refuses $1"; else fail "generator accepted $1 (exit $rc)"; fi
}
B='om2
export fn e1 d view uchar * to ulong
ret 0
end
'
f2 "$B" "$code" "$TR" > "$O/ref.in"; rc=0; "$GEN" c < "$O/ref.in" > "$O/ref.out" 2> /dev/null || rc=$?
if [ $rc = 0 ] && grep -q 'omega2_e1(uint64_t \*result, const uint8_t \*o_d, uint64_t o_d_len)' "$O/ref.out"; then pass "generator accepts the control OM-2 unit"
else fail "generator refused the control (exit $rc)"; fi
f2 "$B" "$code" "" > "$O/ref.in"; refuse "an OM-2 unit without its omega-unit line"
f2 "$B" "$code" "omega-unit u 0123
" > "$O/ref.in"; refuse "a short omc digest"
f2 "$B" "$code" "omega-unit u $(printf '%063dG' 0)
" > "$O/ref.in"; refuse "a non-hex omc digest"
f2 "$B" "$code" "omega-unit a-b $(printf '%064d' 0)
" > "$O/ref.in"; refuse "a unit name that is not a C identifier"
{ f2 "$B" "$code" "$TR"; f2 "$(echo "$B" | sed 's/e1/e2/')
" "$code" "$TR"; } > "$O/ref.in"; refuse "a repeated unit name"
{ f2 "$B" "$code" "$TR"; f2 "$B" "$code" "omega-unit v $(printf '%064d' 0)
"; } > "$O/ref.in"; refuse "an export name repeated across units"
f2 'om2 diag
export fn e1 d view uchar * to ulong
ret 0
end
' "$code" "$TR" > "$O/ref.in"; refuse "an om2 diag unit"
f2 'om2
export fn e1 a view uchar * b view uchar * c view uchar * d view uchar * to ulong
ret 0
end
' "$code" "$TR" > "$O/ref.in"; refuse "eight slots (four unsized views)"
f2 'om2
export fn e1 c edit nolay to void
end
' "$code" "$TR" > "$O/ref.in"; refuse "an undeclared layout"
f2 'om2
export fn e1 o out ulong 8193 to void
end
' "$code" "$TR" > "$O/ref.in"; refuse "out buffers over 65536 bytes"
f2 'om2
export fn e1 x uint to ulong
ret 0
end
' "$code" "$TR" > "$O/ref.in"; refuse "a uint scalar parameter"
f2 'om2
export fn e1 d view uchar * to uint
ret 0
end
' "$code" "$TR" > "$O/ref.in"; refuse "a uint result"
f2 'om2
export fn e1 d_len view uchar * to ulong
ret 0
end
' "$code" "$TR" > "$O/ref.in"; refuse "a parameter name ending in _len"
printf 'x\0\0\0\0' > "$O/w4.bin"
f2 'om2
export fn e1 to void
end
export fn e2 to void
end
' "$O/w4.bin" "$TR" > "$O/ref.in"; refuse "two exports in a 4-byte code"
f2 'note bridge c-type nolay x
om2
export fn e1 to void
end
' "$code" "$TR" > "$O/ref.in"; refuse "a c-type note naming no layout"

# 9. Negative controls: one check of the C prelude removed in a copy of the generator must make the C
# caller fail, on the checks that cover it.
mut() {
  name=$1; ex=$2; pat=$3; M=$O/mut-$name; mkdir -p "$M"
  sed "$ex" "$ROOT/src/native.om" > "$M/native.om"
  n=$(diff "$ROOT/src/native.om" "$M/native.om" | grep -c '^<' || true)
  [ "$n" = 1 ] || { fail "mutant $name changed $n lines"; return 0; }
  "$OMC" < "$M/native.om" > "$M/gen"; chmod +x "$M/gen"
  "$M/gen" c < "$W/units.in" > "$M/omega_native.c"; "$M/gen" h < "$W/units.in" > "$M/omega_native.h"
  cmp -s "$M/omega_native.c" "$O/omega_native.c" && { fail "mutant $name: library unchanged"; return 0; }
  cp "$O/omega_api.h" "$M/"
  cc -std=gnu11 -O2 -fPIC -shared -Wl,-soname,libomega_native.so -include "$M/omega_native.h" -o "$M/libomega_native.so" "$M/omega_native.c"
  cc -std=gnu11 -O2 -pthread -I "$M" "$O/caller.c" -L"$M" -lomega_native -Wl,-rpath,"$M" -ldl -o "$M/caller_c"
  if "$M/caller_c" > "$M/c.log" 2>&1; then fail "mutant $name not caught"
  elif grep -q -E "^FAIL $pat" "$M/c.log"; then pass "mutant $name caught ($(grep -c '^FAIL' "$M/c.log") failing checks, e.g. $(grep -m1 -E "^FAIL $pat" "$M/c.log" | cut -c6-70))"
  else fail "mutant $name failed elsewhere"; grep '^FAIL' "$M/c.log"; fi
}
mut wrap '/^text fv /s/ || n \* es > UINTPTR_MAX - lo)/)/' '#748 golden: vpart len 2\^64-1'
mut overlap '/^text fv /s/if ((sp\[i\].w == 1 || sp\[j\].w == 1 ||/if ((/' 'vcopy edit == view'
mut outcopy '/^text fv /s/memmove(o\[i\].dst, buf\[i\], o\[i\].n);/;/' 'digest: tag'

# 10a. The C API out of line (outputs apih, apic) for freestanding consumers. The inline header
# (output api) stays byte for byte what 74fcd43's generator (main before host words, with the current
# prelude) wrote, as does every other output: a unit without host words is generated as before.
basegen 74fcd43 main
ok=1
for w in c h python rust zig go api apih apic; do
  "$O/gen-main" $w < "$W/units.in" > "$O/a.out"; "$GEN" $w < "$W/units.in" > "$O/b.out"
  cmp -s "$O/a.out" "$O/b.out" || { ok=0; echo "DIFF $w"; }
done
if [ $ok = 1 ]; then pass "outputs c h python rust zig go api apih apic byte-identical to 74fcd43's generator (runtime/private linkage normalized) on the v2 set"
else fail "an existing output changed against 74fcd43"; fi
FS=$O/fs; mkdir -p "$FS"
FSCF="-std=gnu11 -ffreestanding -fno-builtin -O2 -Wall -Wextra -Werror -c"
# fsobj DIR: the freestanding object from DIR's omega_api_decl.h; prints its undefined symbols.
fsobj() { cc $FSCF -I "$1" "$T/fsuse.c" -o "$1/fsuse.o" > "$1/fs-build.log" 2>&1 && nm -u "$1/fsuse.o" | awk '{print $2}' | sort; }
u=$(fsobj "$O" | tr '\n' ' ')
if [ "$u" = "absorb bsum digest swap8 " ]; then pass "freestanding object from omega_api_decl.h: undefined symbols are only absorb bsum digest swap8 (no abort)"
else fail "freestanding object references: $u"; cat "$O/fs-build.log"; fi
cc -std=gnu11 -O2 -Wall -Wextra -Werror -Wmissing-prototypes -I "$O" -c "$O/omega_api_defs.c" -o "$FS/defs.o"
if nm -u "$FS/defs.o" | awk '{print $2}' | grep -qx abort && nm "$FS/defs.o" | grep -q ' T swap8$'; then
  pass "omega_api_defs.o defines the API (swap8 ...) and holds the abort reference"
else fail "omega_api_defs.o"; nm "$FS/defs.o"; fi
sed 's/"omega_api_decl.h"/"omega_api.h"/' "$T/fsuse.c" > "$FS/fsuse_inline.c"
cc $FSCF -I "$O" "$FS/fsuse_inline.c" -o "$FS/fsuse_inline.o"
if nm -u "$FS/fsuse_inline.o" | awk '{print $2}' | grep -qx abort; then pass "control: the same object from the inline omega_api.h references abort (what the freestanding gate refuses)"
else fail "control: the inline object has no abort reference"; fi
cc -std=gnu11 -O2 -I "$O" "$T/fsmain.c" "$O/fsuse.o" "$FS/defs.o" -L"$O" -lomega_native -Wl,-rpath,"$O" -o "$FS/fsmain"
if "$FS/fsmain" > "$FS/run.log" 2>&1 && grep -q '^PASS fs_check 0' "$FS/run.log"; then pass "freestanding object + omega_api_defs.o + library: results correct"
else fail "freestanding run"; cat "$FS/run.log"; fi
rc=0; "$FS/fsmain" refuse > "$FS/refuse.log" 2>&1 || rc=$?
if [ $rc = 134 ]; then pass "out-of-line wrapper aborts on a nonzero status (SIGABRT, exit 134)"; else fail "out-of-line wrapper on a trap: exit $rc"; fi
# Mutants. apih: the prototype-only branch disabled, so apih writes the definitions into the header;
# the freestanding fixture must catch it (abort in the object, or abort undeclared there). api: the
# inline branch disabled, so api loses `static inline`; the byte-identity check must catch it.
amut() {
  name=$1; ex=$2; M=$O/amut-$name; mkdir -p "$M"
  sed "$ex" "$ROOT/src/native.om" > "$M/native.om"
  n=$(diff "$ROOT/src/native.om" "$M/native.om" | grep -c '^<' || true)
  [ "$n" = 1 ] || { fail "mutant $name changed $n lines"; return 1; }
  "$OMC" < "$M/native.om" > "$M/gen"; chmod +x "$M/gen"
  cp "$O/omega_native.h" "$M/"
  for w in api apih apic; do "$M/gen" $w < "$W/units.in" > "$M/$w.out"; done
  cp "$M/api.out" "$M/omega_api.h"; cp "$M/apih.out" "$M/omega_api_decl.h"
}
if amut apih '/^if eq get st 5 8$/s/8$/98/'; then
  u=$(fsobj "$M" | tr '\n' ' ' || true)
  if echo "$u" | grep -qw abort || grep -q "implicit declaration of function .abort." "$M/fs-build.log"; then
    pass "mutant apih (definitions in the header) caught: $(echo "$u" | grep -qw abort && echo "abort undefined in the freestanding object" || grep -m1 -o "implicit declaration of function .abort." "$M/fs-build.log")"
  else fail "mutant apih not caught ($u)"; fi
fi
if amut api '/^if eq get st 5 7$/s/7$/97/'; then
  if cmp -s "$M/api.out" "$O/omega_api.h"; then fail "mutant api not caught: inline header unchanged"
  elif ! grep -q 'static inline' "$M/api.out"; then pass "mutant api (inline wrappers lose static inline) caught by the byte-identity check"
  else fail "mutant api changed something else"; fi
fi

# 11. Host words (docs/NATIVE-ABI.md, "Host words"). An OM-2 function unit may use the nine file and
# identity host words (omega-mv om2 function mode) only when tools/native gets --host; native.om judges
# the source (note lines skipped, blank and parenthesis separators), the shell only sequences.
H=$O/host; mkdir -p "$H"; HU=$T/host/hfile.om
hw="fclose,fopen,fstat,stat,getuid,geteuid,getgid,getegid,lstat"
# tnat NAME WANT ARGS...: tools/native ARGS must exit WANT; a refusal must leave nothing installed (its
# OUTDIR absent, or empty as tools/native leaves it when the generator refuses a unit).
tnat() {
  name=$1; want=$2; shift 2; rc=0
  "$ROOT/tools/native" "$@" > "$H/$name.log" 2>&1 || rc=$?
  if [ $rc != "$want" ]; then fail "tools/native $name: exit $rc, want $want"; cat "$H/$name.log"; return 1; fi
  if [ "$want" != 0 ] && [ -n "$(ls -A "$H/$name" 2> /dev/null)" ]; then fail "tools/native $name refused but installed: $(ls -A "$H/$name")"; return 1; fi
  pass "tools/native $name: exit $want$( [ "$want" = 0 ] || printf ' (%s)' "$(tail -n 1 "$H/$name.log")")"
}
tnat nohost 110 "$H/nohost" "$HU" || true
tnat hostfs 110 --host --freestanding "$H/hostfs" "$HU" || true
tnat hostx86 110 --target x86linux --host "$H/hostx86" "$HU" || true
if tnat hostok 0 --host "$H/hostok" "$ROOT/tests/native/madd.om" "$HU"; then
  want="omega-ident 1 unit=hfile abi=2 profile=OM-2 src=$(sha256sum < "$HU" | cut -d' ' -f1) omc=$(sha256sum < "$OMC2" | cut -d' ' -f1) host=$hw"
  if grep -q -F "OMEGA2_IDENT_hfile \"$want\"" "$H/hostok/omega_native.h" && grep -q -F "\"$want\"" "$H/hostok/omega_native.c" \
    && grep -q -F "$want path=$HU" "$H/hostok/work/ident.txt"; then pass "hfile identity names its host words: host=$hw"
  else fail "hfile identity"; grep hfile "$H/hostok/work/ident.txt" || true; fi
  printf 'abcde' > "$H/five"; ln -sf "$H/five" "$H/link"
  bld host-c cc -std=gnu11 -O2 -Wall -Wextra -Werror -I "$H/hostok" "$T/host/hcall.c" -L"$H/hostok" -lomega_native -Wl,-rpath,"$H/hostok" -o "$H/hcall_c" \
    && run host-c "$H/hcall_c" "$H/five" "$H/missing" "$H/link"
  if command -v rustc > /dev/null; then
    cp "$T/host/hcall.rs" "$H/hostok/omega_native.rs" "$H/"
    bld host-rust rustc -O --edition 2021 -D warnings "$H/hcall.rs" -L "$H/hostok" -C link-arg=-Wl,-rpath,"$H/hostok" -o "$H/hcall_rs" \
      && run host-rust "$H/hcall_rs" "$H/five" "$H/missing" "$H/link"
  else notrun="$notrun host-rust"; fi
fi
# --host changes nothing for units without host words: the v2 set built with --host, every output equal.
if tnat hostset 0 --host "$H/hostset" $units; then
  ok=1
  for f in omega_native.c omega_native.h omega_native.py omega_native.rs omega_native.zig omega_native.go omega_api.h omega_api_decl.h omega_api_defs.c; do
    cmp -s "$O/$f" "$H/hostset/$f" || { ok=0; echo "DIFF $f"; }
  done
  if [ $ok = 1 ]; then pass "--host is inert for the v2 set (no host words): all nine generated files byte-identical"; else fail "--host changed a unit without host words"; fi
fi
# The scanner, fed straight to native-gen: source forms the compiler accepts (OMC2 compiles each), and
# sources framed with a clean unit's code to reach the forms the compilers refuse (OM-1, unlink).
# frame SRC BIN OUT: the tools/native framing, with the omega-unit line when SRC is OM-2.
frame() {
  { cat "$1"; printf '\0'; printf '%08d' "$(wc -c < "$2")"; cat "$2"
    [ "$(sed -n '/^ *note\( \|$\)/d; p; q' "$1")" != om2 ] || printf 'omega-unit hu %s\n' "$(sha256sum < "$OMC2" | cut -d' ' -f1)"
  } > "$3"
}
# gcase NAME SRC BIN NOHOST HOST: native-gen c on the frame, without and with host, must exit NOHOST and
# HOST; with HOST 0, ident must carry exactly the host suffix given in HW (empty: no host= at all).
gcase() {
  frame "$2" "$3" "$H/$1.in"; a=0; b=0
  "$GEN" c < "$H/$1.in" > /dev/null 2>&1 || a=$?
  "$GEN" c host < "$H/$1.in" > /dev/null 2>&1 || b=$?
  id=""; [ "$b" != 0 ] || [ "$(sed -n '/^ *note\( \|$\)/d; p; q' "$2")" != om2 ] || id=$("$GEN" ident host < "$H/$1.in")
  case "$id" in *" host="*) got=${id##* host=};; *) got="";; esac
  if [ $a = "$4" ] && [ $b = "$5" ] && [ "$got" = "$HW" ]; then pass "native-gen $1: exit $a without host, $b with host${HW:+, host=$HW}"
  else fail "native-gen $1: exit $a/$b (want $4/$5), host=$got (want $HW)"; fi
}
printf 'om2\nexport fn a to ulong\nx = ulong 7\nret x\nend\n' > "$H/clean.om"; "$OMC2" < "$H/clean.om" > "$H/clean.bin"
printf 'fn a to ulong\nx = ulong 7\nret x\nend\n' > "$H/clean1.om"; "$OMC" < "$H/clean1.om" > "$H/clean1.bin"
HW="" gcase clean "$H/clean.om" "$H/clean.bin" 0 0
HW="" gcase clean1 "$H/clean1.om" "$H/clean1.bin" 0 0
for c in paren:'x = ulong (geteuid)' tab:"$(printf 'x = ulong\tgeteuid')" cr:"$(printf 'x = ulong geteuid\r')"; do
  printf 'om2\nexport fn a to ulong\n%s\nret x\nend\n' "${c#*:}" > "$H/${c%%:*}.om"
  if "$OMC2" < "$H/${c%%:*}.om" > "$H/${c%%:*}.bin" 2> /dev/null; then HW=geteuid gcase "${c%%:*}" "$H/${c%%:*}.om" "$H/${c%%:*}.bin" 110 0
  else fail "OMC2 refuses the ${c%%:*} form"; fi
done
printf 'om2\nnote uses unlink fopen geteuid only in a note\n  note\tlstat after blanks\nexport fn a to ulong\nx = ulong 7\nret x\nend\n' > "$H/note.om"
"$OMC2" < "$H/note.om" > "$H/note.bin"; HW="" gcase note "$H/note.om" "$H/note.bin" 0 0
printf 'om2\nexport fn a to ulong\nx = ulong 7 (note geteuid\nret x\nend\n' > "$H/pnote.om"; HW=geteuid gcase pnote "$H/pnote.om" "$H/clean.bin" 110 0
printf 'om2\nexport fn a to ulong\nx = unlink 7\nret x\nend\n' > "$H/unlink.om"; HW="" gcase unlink "$H/unlink.om" "$H/clean.bin" 110 110
printf 'fn a to ulong\nx = ulong geteuid\nret x\nend\n' > "$H/om1.om"; HW="" gcase om1 "$H/om1.om" "$H/clean1.bin" 110 110
printf 'om2\nexport fn a to ulong\nx = ulong getuidx\nret x\nend\n' > "$H/near.om"; HW="" gcase near "$H/near.om" "$H/clean.bin" 0 0
# Mutant: the scan disabled in fn unit; the paren case must then pass without host, and be caught.
M=$O/hmut; mkdir -p "$M"
sed '/^hscan p q v$/s/^/note /' "$ROOT/src/native.om" > "$M/native.om"
if [ "$(diff "$ROOT/src/native.om" "$M/native.om" | grep -c '^<' || true)" = 1 ] && "$OMC" < "$M/native.om" > "$M/gen"; then
  chmod +x "$M/gen"; rc=0; "$M/gen" c < "$H/paren.in" > /dev/null 2>&1 || rc=$?
  if [ $rc = 0 ]; then pass "mutant hscan-off caught: paren case exits 0 without host (the check above wants 110)"
  else fail "mutant hscan-off not caught (exit $rc)"; fi
else fail "mutant hscan-off did not apply"; fi

# 10. Cost (HOST): call overhead, stack switch, copies, small and large views.
if [ "${1:-}" = measure ]; then
  cc -std=gnu11 -O2 -Wall -Wextra -Werror -pthread -I "$O" "$T/measure.c" -L"$O" -lomega_native -Wl,-rpath,"$O" -o "$O/measure" \
    && "$O/measure" | tee "$O/measure.log"
  echo "INFO load: $(cat /proc/loadavg)"
fi
for l in $notrun; do echo "NOT_RUN $l caller: toolchain not installed"; done
if [ "$fails" -ne 0 ]; then echo "NATIVE-V2 FAIL $fails"; exit 1; fi
if [ -n "$notrun" ]; then echo "NATIVE-V2 NOT_RUN (not run:$notrun)"; exit 1; fi
echo "NATIVE-V2 PASS (not run:${notrun:- none})"
