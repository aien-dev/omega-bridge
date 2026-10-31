#!/bin/sh
# Replays the DeepInfer coverage verdicts in docs/DEEPINFER.md against built omega-mv adapters.
# OMEGA_MV = an omega-mv checkout whose adapters are built (PR #839 head 656192e0 was measured:
#   build/L627/import/python-import, build/S2/c-i64-import, build/L739/cpp-import).
# Prints one row per input and exits 1 if any exit status differs from the recorded one.
set -u
: "${OMEGA_MV:?set OMEGA_MV to a built omega-mv checkout}"
here=$(cd "$(dirname "$0")" && pwd)
py="$OMEGA_MV/build/L627/import/python-import"
c="$OMEGA_MV/build/S2/c-i64-import"
cpp="$OMEGA_MV/build/L739/cpp-import"
for t in "$py" "$c" "$cpp"; do [ -x "$t" ] || { echo "missing adapter $t" >&2; exit 2; }; done
sha256sum "$py" "$c" "$cpp"
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
bad=0
check() { # adapter expected-status input
  "$1" < "$3" > "$tmp/out" 2> "$tmp/err"; got=$?
  verdict=PASS; [ "$got" = "$2" ] || { verdict=FAIL; bad=1; }
  printf '%-5s %-14s want=%-3s got=%-3s out=%5sB %-40s %s\n' "$verdict" "$(basename "$1")" "$2" "$got" \
    "$(wc -c < "$tmp/out" | tr -d ' ')" "$(head -c 40 "$tmp/err" | tr '\n' ' ')" "${3#"$here"/}"
}
v="$here/py-verbatim"; s="$here/py-stripped"; x="$here/cxx"
check "$py" 66 "$v/000_is_power_of_two.py"
check "$py" 66 "$v/001_ceil_div.py"
check "$py" 66 "$v/002_i64.py"
check "$py" 72 "$v/003_expanded_image_token_len.py"
check "$py" 72 "$v/004__align_to_multiple.py"
check "$py" 71 "$v/005__needs_compress_state.py"
check "$py" 0  "$v/ctrl_pos.py"
check "$py" 68 "$v/ctrl_unmasked.py"
check "$py" 68 "$s/000_is_power_of_two.py"
check "$py" 68 "$s/001_ceil_div.py"
check "$py" 69 "$s/002_i64.py"
check "$py" 68 "$s/003_expanded_image_token_len.py"
check "$py" 68 "$s/004__align_to_multiple.py"
check "$py" 68 "$s/005__needs_compress_state.py"
check "$c" 66 "$x/floor_prefix.hdr-c"
check "$c" 66 "$x/capped_prefix.hdr-c"
check "$c" 66 "$x/pairs.hdr-c"
check "$c" 68 "$x/floor_prefix.c17"
for f in floor_prefix capped_prefix pairs; do
  check "$c" 72 "$x/$f.verbatim"
  check "$cpp" 72 "$x/$f.verbatim"
done
check "$c" 0  "$x/ctrl_pos.c17"
check "$cpp" 69 "$x/floor_prefix.hdr-cpp"
check "$cpp" 69 "$x/capped_prefix.hdr-cpp"
check "$cpp" 69 "$x/pairs.hdr-cpp"
check "$cpp" 0  "$x/ctrl_pos.hdr-cpp"
check "$cpp" 71 "$x/ctrl_name.hdr-cpp"
[ "$bad" = 0 ] && echo "DEEPINFER-COVERAGE REPLAY PASS" || echo "DEEPINFER-COVERAGE REPLAY FAIL"
exit "$bad"
