#!/bin/sh
# Synchronous all-or-rollback installation. No account enrollment or hooks.
set -eu
umask 077
cd "$(dirname "$0")/.."
fail() { printf 'omega: %s\n' "$2" >&2; exit "$1"; }
prefix=${HOME:?}/.local
while [ "$#" -gt 0 ]; do
    case $1 in
        --offline) shift;;
        --prefix) [ "$#" -ge 2 ] || fail 64 'missing prefix'; prefix=$2; shift 2;;
        *) fail 64 'usage: tools/install.sh [--offline] [--prefix absolute-directory]';;
    esac
done
case $prefix in /*) ;; *) fail 64 'prefix must be absolute';; esac
case $prefix in *'
'*) fail 64 'newline in prefix is unsupported';; esac
prefix=$(realpath -m -- "$prefix")
[ "$prefix" != / ] || fail 64 'root prefix is unsupported'
payload=$prefix/lib/omega-native
check() {
    for p in "$prefix/bin/om" "$prefix/bin/omg" "$payload"; do
        [ ! -e "$p" ] && [ ! -L "$p" ] || fail 73 'installation collision; no files replaced'
    done
    for p in "$prefix" "$prefix/bin" "$prefix/lib"; do
        [ ! -L "$p" ] && { [ ! -e "$p" ] || [ -d "$p" ]; } || fail 73 'installation directory collision'
    done
}
check
# Require an existing parent so rollback has a bounded list of created directories.
[ -d "$(dirname "$prefix")" ] || fail 73 'prefix parent must already exist'
tools/bootstrap.sh --offline
tools/build-native.sh
created_prefix=0; created_bin=0; created_lib=0; locked=0
published=0; linked_om=0; linked_omg=0; stage=; success=0
cleanup() {
    rc=$?
    trap - EXIT HUP INT TERM
    if [ "$success" = 0 ]; then
        [ "$linked_omg" = 0 ] || rm -f -- "$prefix/bin/omg"
        [ "$linked_om" = 0 ] || rm -f -- "$prefix/bin/om"
        if [ "$published" = 1 ]; then
            # The payload has a flat, private, fixed file set.
            find "$payload" -maxdepth 1 -type f -delete
            rmdir "$payload"
        fi
    fi
    if [ -n "$stage" ] && [ -d "$stage" ]; then
        find "$stage" -maxdepth 1 -type f -delete
        rmdir "$stage"
    fi
    [ "$locked" = 0 ] || rmdir "$prefix/.omega-install-lock"
    if [ "$success" = 0 ]; then
        [ "$created_bin" = 0 ] || rmdir "$prefix/bin"
        [ "$created_lib" = 0 ] || rmdir "$prefix/lib"
        [ "$created_prefix" = 0 ] || rmdir "$prefix"
    fi
    exit "$rc"
}
trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
if [ ! -d "$prefix" ]; then mkdir "$prefix"; created_prefix=1; fi
mkdir "$prefix/.omega-install-lock" || fail 73 'installation is locked'
locked=1
check
if [ ! -d "$prefix/bin" ]; then mkdir "$prefix/bin"; created_bin=1; fi
if [ ! -d "$prefix/lib" ]; then mkdir "$prefix/lib"; created_lib=1; fi
stage=$(mktemp -d "$prefix/.omega-stage.XXXXXXXX")
cp build/native/omc build/native/bridge build/native/math tools/om tools/uninstall.sh tools/HELP.txt "$stage/"
cp provenance/pins "$stage/pins"
cp provenance/OMEGA-LICENSE "$stage/LICENSE"
cp seed/math/CONTRACT.md "$stage/MATH-CONTRACT.md"
cp docs/CAPABILITIES.md "$stage/CAPABILITIES.md"
printf '%s %s %s\n' "$created_prefix" "$created_bin" "$created_lib" > "$stage/created-directories"
(cd "$stage" && sha256sum omc bridge math om uninstall.sh HELP.txt pins LICENSE MATH-CONTRACT.md CAPABILITIES.md created-directories > files.sha256)
chmod 600 "$stage"/*
chmod 700 "$stage/omc" "$stage/bridge" "$stage/math" "$stage/om" "$stage/uninstall.sh"
# Same-filesystem rename, followed by no-clobber links. Trap reverses any failure.
mv -T -- "$stage" "$payload"
stage=; published=1
ln -s ../lib/omega-native/om "$prefix/bin/om"
linked_om=1
ln -s ../lib/omega-native/om "$prefix/bin/omg"
linked_omg=1
[ "$("$prefix/bin/om" math 'eval 1/3+1/6')" = 'OK 1/2' ] || fail 65 'installed native smoke failed'
[ "$("$prefix/bin/omg" math 'diff x^2')" = 'OK 2*x' ] || fail 65 'installed alias smoke failed'
success=1
printf 'Installed om and omg in %s/bin (PATH unchanged)\n' "$prefix"
