#!/bin/sh
# Replay a frozen source distribution in an isolated prefix, no account changes.
set -eu
umask 077
root=$1
case "$root" in /*) ;; *) exit 64;; esac
[ -f "$root/package.tar.gz" ] || exit 66
mkdir "$root/source" "$root/home" "$root/tmp" "$root/project"
export HOME="$root/home" TMPDIR="$root/tmp" LC_ALL=C
unset OMEGA_SEED OMEGA_SOURCE || true
printf 'HOST '; uname -sm
printf 'SOURCE '; sha256sum "$root/package.tar.gz"
tar -xzf "$root/package.tar.gz" -C "$root/source"
cd "$root/source/omega"
./tools/install.sh --offline --prefix "$root/home/prefix"
om="$root/home/prefix/bin/om"
omg="$root/home/prefix/bin/omg"
[ "$(readlink -f "$om")" = "$(readlink -f "$omg")" ]
cd "$root/project"
printf 'text msg "Hello from Omega\\n"\nfn main to int\nw = write 1 msg 0 len msg\nret 0\nend\n' > hello.om
printf 'Hello from Omega\n' > expected.txt
"$om" version
"$om" check hello.om > check.stdout
[ ! -s check.stdout ]
"$om" build hello.om -o hello > build.stdout
[ ! -s build.stdout ]
./hello > built.stdout
"$om" run hello.om > run.stdout
"$omg" run hello.om > alias.stdout
cmp expected.txt built.stdout
cmp expected.txt run.stdout
cmp expected.txt alias.stdout
[ "$("$om" math 'eval 1/3+1/6')" = 'OK 1/2' ]
printf 'fn main to int\nret 23\nend\n' > status.om
set +e
"$om" run status.om
rc=$?
set -e
[ "$rc" -eq 23 ]
printf 'fn main to int\nret unknown\nend\n' > invalid.om
set +e
"$om" check invalid.om > invalid.stdout 2> invalid.stderr
rc=$?
set -e
[ "$rc" -eq 65 ]
[ ! -s invalid.stdout ]
sha256sum "$root/home/prefix/lib/omega-native/omc" "$root/home/prefix/lib/omega-native/bridge" "$root/home/prefix/lib/omega-native/math" > "$root/native.sha256"
sha256sum built.stdout run.stdout alias.stdout
cat "$root/native.sha256"
"$om" uninstall
[ ! -e "$root/home/prefix/bin/om" ]
[ ! -e "$root/home/prefix/bin/omg" ]
[ ! -e "$root/home/prefix/lib/omega-native" ]
printf 'PASS isolated source install, project check/build/run, alias, math, status, invalid-source refusal and uninstall\n'
printf '0\n' > "$root/exit.code"
