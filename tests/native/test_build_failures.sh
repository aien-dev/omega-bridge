#!/bin/sh
# Offline qualification controls; the real native runner builds and runs every caller.
set -eu
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
: "${OMEGA_NATIVE_OMC:?set OMEGA_NATIVE_OMC to the pinned seeded compiler}"
ZIG=${ZIG:-$HOME/.local/opt/zig-linux-aarch64-0.13.0/zig}
GO=${GO:-$HOME/.local/opt/go1.27.3/bin/go}
[ -x "$ZIG" ] && [ -x "$GO" ] || { echo 'NOT_RUN: real Zig and Go toolchains required'; exit 1; }
D=$(mktemp -d)
trap 'rm -rf "$D"' EXIT HUP INT TERM
mkdir "$D/zig-fail" "$D/go-fail"
cat > "$D/zig-fail/zig" <<'SH'
#!/bin/sh
printf 'CONTROL: Zig build refused\n' >&2
exit 42
SH
cat > "$D/go-fail/go" <<'SH'
#!/bin/sh
printf 'CONTROL: Go build refused\n' >&2
exit 43
SH
chmod +x "$D/zig-fail/zig" "$D/go-fail/go"
P=$(dirname "$ZIG"):$(dirname "$GO"):$PATH
check() {
  name=$1; path=$2; verdict=$3; signal=$4
  rc=0
  (cd "$ROOT" && PATH="$path" sh tests/native/run.sh) > "$D/$name.log" 2>&1 || rc=$?
  if [ "$rc" -eq 0 ] || ! grep -Fq "$verdict" "$D/$name.log" ||
     ! grep -Fq "$signal" "$D/$name.log" || grep -Fq 'NATIVE-CALL PASS' "$D/$name.log"; then
    cat "$D/$name.log"; echo "FAIL control $name (exit $rc)"; exit 1
  fi
  echo "PASS control $name (exit $rc; $verdict)"
}
check zig-build "$D/zig-fail:$P" 'NATIVE-CALL FAIL' 'CONTROL: Zig build refused'
check go-build "$D/go-fail:$P" 'NATIVE-CALL FAIL' 'CONTROL: Go build refused'
# Missing toolchains are NOT_RUN, not a green qualification. Other system tools stay available.
check missing '/usr/bin:/bin' 'NATIVE-CALL NOT_RUN' 'NOT_RUN zig caller'
(cd "$ROOT" && PATH="$P" sh tests/native/run.sh) > "$D/positive.log" 2>&1 || {
  cat "$D/positive.log"; echo 'FAIL positive native callers'; exit 1;
}
grep -Fq 'PASS zig caller' "$D/positive.log"
grep -Fq 'PASS go caller' "$D/positive.log"
grep -Fq 'NATIVE-CALL PASS (not run: none)' "$D/positive.log"
echo 'PASS native callers: Zig and Go built and executed; no missing languages'
