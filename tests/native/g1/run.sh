#!/bin/sh
# G1 sample (omega-mv #624, translation-v1 section 5 form): calc(i0, i1) = (i0 + i1) * (i0 - i1) modulo
# 2^64 as a function-mode .om unit with a "new ulong" SSA array, compiled by the pinned omc, bound by
# tools/native, and called from C, C++, Python, Rust, Zig and Go. Every caller's output on the boundary
# vectors must equal the Python bigint reference line for line. Writes build/g1/manifest.json.
# OMEGA_G1_UNIT names the unit (default tests/native/g1/calc.om, hand-written; calc.lowered.om is the one
# the omega-mv pipeline generated). The bound function's name and arity come from the unit's last fn
# line; the callers and the reference implement calc with two inputs, so any other is a FAIL. A first
# line "note omega.universal.lower.v1 semantic <64 hex>" is recorded as the semantic identity, apart from
# the source identity (sha256 of the unit's bytes).
# A missing toolchain is NOT_RUN, never PASS. Exit 0 only when every caller that ran passed.
set -eu
PIN=734f0a39319fbfa930bcc62cb30dbf06d47d78e126372b74f5baf478e6126b61
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
T=$ROOT/tests/native/g1
O=$ROOT/build/g1
OMC=${OMEGA_NATIVE_OMC:?set OMEGA_NATIVE_OMC to the seeded omc (omega seed/out/omc, sha256 $PIN)}
got=$(sha256sum < "$OMC" | cut -d' ' -f1)
[ "$got" = "$PIN" ] || { echo "FAIL omc sha256 $got, pinned $PIN"; exit 1; }
command -v python3 > /dev/null || { echo "FAIL python3 (the reference) is not installed"; exit 1; }
rm -rf "$O"; mkdir -p "$O/mut" "$O/unit"
fails=0
pass() { echo "PASS $1"; }
fail() { echo "FAIL $1"; fails=$((fails + 1)); }
UNIT=${OMEGA_G1_UNIT:-$T/calc.om}
[ -f "$UNIT" ] || { echo "FAIL unit $UNIT not found"; exit 1; }
FNL=$(grep '^fn ' "$UNIT" | tail -n 1)
NAME=$(printf '%s\n' "$FNL" | awk '{ print $2 }')
ARITY=$(printf '%s\n' "$FNL" | awk '{ n = 0; for (i = 3; i < NF; i += 2) { if ($i == "to") break; n++ } print n }')
SEM=$(head -n 1 "$UNIT" | awk '$1 == "note" && $2 == "omega.universal.lower.v1" && $3 == "semantic" { print $4 }')
if head -n 1 "$UNIT" | grep -q '^note omega.universal.lower.v1 '; then
  if printf '%s\n' "$SEM" | grep -qx '[0-9a-f]\{64\}'; then pass "unit carries semantic identity $SEM"
  else fail "unit's lower.v1 note line has no 64-hex semantic identity"; SEM=; fi
fi
if [ "$NAME" = calc ] && [ "$ARITY" = 2 ]; then pass "bound function $NAME, $ARITY inputs ($FNL)"
else echo "FAIL bound function '$FNL': the callers and the reference implement calc with 2 inputs"; exit 1; fi
# tools/native names a unit's code after its file, so the unit is bound from a copy named after its function.
cp "$UNIT" "$O/unit/$NAME.om"
OMEGA_NATIVE_OMC="$OMC" "$ROOT/tools/native" "$O" "$O/unit/$NAME.om" > "$O/tools-native.log" 2>&1 \
  || { echo "FAIL tools/native"; cat "$O/tools-native.log"; exit 1; }
"$OMC" < "$UNIT" > "$O/calc.bin"
if cmp -s "$O/calc.bin" "$O/work/calc.bin"; then pass "calc compiled ($(wc -c < "$O/calc.bin") bytes of code)"
else fail "tools/native compiled calc differently from omc"; fi
# The embedded code must be omc's bytes: read at ombr_code_calc, mapped to its file offset.
s=$(objdump -t "$O/libomega_native.so" | awk '$NF=="ombr_code_calc"{print $1}')
off=$(objdump -h "$O/libomega_native.so" | awk '$2 ~ /^\./ {print $3, $4, $6}' | while read -r sz vma fo; do
  if [ $((0x$vma)) -le $((0x$s)) ] && [ $((0x$s)) -lt $((0x$vma + 0x$sz)) ]; then echo $((0x$s - 0x$vma + 0x$fo)); break; fi
done)
dd if="$O/libomega_native.so" bs=1 skip="${off:-0}" count="$(wc -c < "$O/calc.bin")" 2> /dev/null > "$O/calc.emb"
if [ -n "$off" ] && cmp -s "$O/calc.bin" "$O/calc.emb"; then pass "embedded code == omc output"
else fail "embedded code differs from omc output"; fi
python3 -I "$T/reference.py" vectors > "$O/vectors.txt"
python3 -I "$T/reference.py" expect < "$O/vectors.txt" > "$O/expect.txt"
N=$(wc -l < "$O/vectors.txt")
cp "$T"/caller.* "$O/"
: > "$O/status.txt"
# rec LANG STATUS MATCHED TOOLCHAIN: one line per language for the manifest.
rec() { printf '%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" >> "$O/status.txt"; }
cmpout() {
  lang=$1; tc=$2
  m=$(awk 'NR==FNR { e[FNR] = $0; next } e[FNR] == $0 { n++ } END { print n + 0 }' "$O/expect.txt" "$O/$lang.out")
  if cmp -s "$O/expect.txt" "$O/$lang.out"; then pass "$lang caller ($m/$N vectors)"; rec "$lang" PASS "$m" "$tc"
  else fail "$lang caller ($m/$N vectors)"; rec "$lang" FAIL "$m" "$tc"; fi
}
try() {
  lang=$1; tc=$2; shift 2
  if "$@" > "$O/$lang-build.log" 2>&1; then return 0; fi
  fail "$lang build"; cat "$O/$lang-build.log"; rec "$lang" FAIL 0 "$tc"; return 1
}
notrun() { echo "NOT_RUN $1 caller: $2 not installed"; rec "$1" NOT_RUN 0 "-"; }
# ver TOOL ARGS: the tool's resolved path, then the first line of its version output.
ver() { printf '%s: ' "$(command -v "$1")"; "$@" 2>&1 | head -n 1; }
if command -v cc > /dev/null; then
  tc=$(ver cc --version)
  try c "$tc" cc -std=c17 -O2 -Wall -Wextra -Werror "$O/caller.c" -L"$O" -lomega_native -Wl,-rpath,"$O" -o "$O/caller_c" \
    && { "$O/caller_c" < "$O/vectors.txt" > "$O/c.out" 2> "$O/c.err" || true; cmpout c "$tc"; }
else notrun c cc; fi
if command -v c++ > /dev/null; then
  tc=$(ver c++ --version)
  try cpp "$tc" c++ -std=c++17 -O2 -Wall -Wextra -Werror "$O/caller.cpp" -L"$O" -lomega_native -Wl,-rpath,"$O" -o "$O/caller_cpp" \
    && { "$O/caller_cpp" < "$O/vectors.txt" > "$O/cpp.out" 2> "$O/cpp.err" || true; cmpout cpp "$tc"; }
else notrun cpp c++; fi
tc=$(ver python3 --version)
python3 -I "$O/caller.py" < "$O/vectors.txt" > "$O/python.out" 2> "$O/python.err" || true; cmpout python "$tc"
if command -v rustc > /dev/null; then
  tc=$(ver rustc --version)
  try rust "$tc" rustc -O --edition 2021 "$O/caller.rs" -L "$O" -C link-arg=-Wl,-rpath,"$O" -o "$O/caller_rs" \
    && { "$O/caller_rs" < "$O/vectors.txt" > "$O/rust.out" 2> "$O/rust.err" || true; cmpout rust "$tc"; }
else notrun rust rustc; fi
if command -v zig > /dev/null; then
  tc=$(ver zig version)
  try zig "$tc" sh -c 'cd "$1" && zig build-exe caller.zig -L. -lomega_native -lc -rpath "$1" -femit-bin=caller_zig' _ "$O" \
    && { "$O/caller_zig" < "$O/vectors.txt" > "$O/zig.out" 2> "$O/zig.err" || true; cmpout zig "$tc"; }
else notrun zig zig; fi
if command -v go > /dev/null; then
  tc=$(ver go version)
  mkdir -p "$O/go/omeganative"; cp "$O/omega_native.go" "$O/omega_native.h" "$O/libomega_native.so" "$O/go/omeganative/"
  cp "$O/caller.go" "$O/go/"
  try go "$tc" sh -c 'cd "$1" && go mod init omegacaller > /dev/null 2>&1 && CGO_LDFLAGS="-Wl,-rpath,$1/omeganative" go build -o caller_go .' _ "$O/go" \
    && { "$O/go/caller_go" < "$O/vectors.txt" > "$O/go.out" 2> "$O/go.err" || true; cmpout go "$tc"; }
else notrun go go; fi
# Negative control: the same unit with its (first) sub turned into add, bound and called from C, must
# disagree with the reference on these vectors.
sed '0,/^\(put v [0-9]* \)sub /s//\1add /' "$UNIT" > "$O/mut/calc.om"
if cmp -s "$O/mut/calc.om" "$UNIT"; then fail "mutant calc (sub -> add) did not change the unit"
elif OMEGA_NATIVE_OMC="$OMC" "$ROOT/tools/native" "$O/mut" "$O/mut/calc.om" > "$O/mut/tools-native.log" 2>&1 \
    && cc -std=c17 -O2 "$O/caller.c" -I"$O/mut" -L"$O/mut" -lomega_native -Wl,-rpath,"$O/mut" -o "$O/mut/caller_c" \
    && "$O/mut/caller_c" < "$O/vectors.txt" > "$O/mut/c.out"; then
  m=$(awk 'NR==FNR { e[FNR] = $0; next } e[FNR] == $0 { n++ } END { print n + 0 }' "$O/expect.txt" "$O/mut/c.out")
  if cmp -s "$O/expect.txt" "$O/mut/c.out"; then fail "mutant calc (sub -> add) not caught"
  else pass "mutant calc (sub -> add) caught ($((N - m))/$N vectors differ)"; fi
else fail "mutant calc (sub -> add) did not build"; fi
# The manifest: identities of the inputs and the artifact, the ELF header, and each caller's status.
readelf -h "$O/libomega_native.so" > "$O/readelf-h.txt"
python3 -I - "$O" "$ROOT" "$N" "$got" "$UNIT" "$NAME" "$ARITY" "$SEM" > "$O/manifest.json" << 'EOF'
import hashlib, json, os, subprocess, sys
O, ROOT, N, OMC_SHA, UNIT, NAME, ARITY, SEM = sys.argv[1:9]
N, ARITY = int(N), int(ARITY)
def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()
elf = {}
for line in open(O + "/readelf-h.txt"):
    k, _, v = line.partition(":")
    if k.strip() in ("Class", "Machine", "OS/ABI", "Type"):
        elf[k.strip().lower().replace("/", "_")] = v.strip()
git = lambda *a: subprocess.run(["git", "-C", ROOT] + list(a), capture_output=True, text=True).stdout.strip()
callers = {}
for line in open(O + "/status.txt"):
    lang, status, matched, tc = line.rstrip("\n").split("\t")
    callers[lang] = {"status": status, "vectors": N if status != "NOT_RUN" else 0,
                     "matched": int(matched), "toolchain": tc}
uname = subprocess.run(["uname", "-s", "-m"], capture_output=True, text=True).stdout.split()
unit = os.path.realpath(UNIT)
m = {
    "schema": "omega-bridge.native-artifact-manifest.v1",
    "unit": {"file": os.path.relpath(unit, ROOT) if unit.startswith(ROOT + "/") else unit,
             "function": NAME, "inputs": ARITY},
    "source_identity": {"algorithm": "sha256", "of": "the unit's .om bytes", "value": sha(unit)},
    "semantic_identity": ({"value": SEM, "from": "the unit's first line: note omega.universal.lower.v1 semantic",
                           "definition": "spec/universal/translation-v1.md section 4 (omega-mv)"}
                          if SEM else None),
    "omc_sha256": OMC_SHA,
    "native_om_sha256": sha(ROOT + "/src/native.om"),
    "tools_native_sha256": sha(ROOT + "/tools/native"),
    "code_sha256": sha(O + "/calc.bin"),
    "artifact": {"file": "libomega_native.so", "sha256": sha(O + "/libomega_native.so"),
                 "binding_sha256": {f: sha(O + "/omega_native." + f) for f in ("c", "h", "py", "rs", "zig", "go")}},
    "isa": "aarch64",
    "elf": elf,
    "abi": "omega-native-v1",
    "os": "Linux",
    "host": {"uname_s": uname[0], "uname_m": uname[1]},
    "bridge_commit": git("rev-parse", "HEAD"),
    "bridge_tree_dirty": bool(git("status", "--porcelain", "--", "src", "tools", "tests")),
    "vectors": {"count": N, "sha256": sha(O + "/vectors.txt"), "expect_sha256": sha(O + "/expect.txt"),
                "reference": "tests/native/g1/reference.py (Python bigint, reduced mod 2^64)"},
    "callers": callers,
}
print(json.dumps(m, indent=2, sort_keys=True))
EOF
echo "manifest $O/manifest.json"
nr=$(awk -F'\t' '$2 == "NOT_RUN" { printf " %s", $1 }' "$O/status.txt")
if [ "$fails" -ne 0 ]; then echo "G1-CALC FAIL $fails"; exit 1; fi
echo "G1-CALC PASS (not run:${nr:- none})"
