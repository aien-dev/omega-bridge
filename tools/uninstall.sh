#!/bin/sh
# Preserve user data and unrelated changes. No recursive deletion.
set -eu
LC_ALL=C; export LC_ALL
fail() { printf 'omega: %s\n' "$2" >&2; exit "$1"; }
[ "$#" = 2 ] && [ "$1" = --prefix ] || fail 64 'usage: uninstall.sh --prefix absolute-directory'
case $2 in /*) ;; *) fail 64 'prefix must be absolute';; esac
case $2 in *'
'*) fail 64 'newline in prefix is unsupported';; esac
# Inspect the named path before realpath can hide a link (including link/..).
# Strip trailing slashes before -L; a slash otherwise dereferences the leaf.
check_parents() {
    named=$1
    while [ "$named" != / ]; do
        case $named in */) named=${named%/}; continue;; esac
        [ ! -L "$named" ] || fail 73 'installation parent changed; preserving installation'
        named=$(dirname -- "$named")
    done
}
check_parents "$2"
prefix=$(realpath -ms -- "$2")
[ "$prefix" != / ] || fail 64 'root prefix is unsupported'
payload=$prefix/lib/omega-native
preflight() {
check_parents "$2"
check_parents "$prefix/bin"
check_parents "$payload"
[ -d "$payload" ] && [ ! -L "$payload" ] || fail 73 'installation missing'
for name in omega om omg; do
    [ -L "$prefix/bin/$name" ] && [ "$(readlink -- "$prefix/bin/$name")" = ../lib/omega-native/om ] || fail 73 'alias changed; preserving installation'
done
(cd "$payload" && sha256sum --status -c files.sha256) 2>/dev/null || fail 65 'installed files changed; preserving installation'
for f in omc bridge math om uninstall.sh verify-elf.sh HELP.txt pins LICENSE MATH-CONTRACT.md CAPABILITIES.md created-directories files.sha256; do
    case $f in omc|bridge|math|om|uninstall.sh|verify-elf.sh) mode=700;; *) mode=600;; esac
    [ -f "$payload/$f" ] && [ ! -L "$payload/$f" ] && [ "$(stat -c %a "$payload/$f")" = "$mode" ] || fail 65 'installed file type or mode changed; preserving installation'
done
# Fixed deletion list; never use paths supplied by a mutable manifest for removal.
read -r created_prefix created_bin created_lib < "$payload/created-directories"
case "$created_prefix $created_bin $created_lib" in
    '0 0 0'|'0 0 1'|'0 1 0'|'0 1 1'|'1 1 1') ;;
    *) fail 65 'invalid installation record';;
esac
}
preflight --prefix "$2"
mkdir "$prefix/.omega-install-lock" || fail 73 'installation is locked'
trap 'rmdir "$prefix/.omega-install-lock" 2>/dev/null || :' EXIT
# Recheck both the named parents and owned files after taking the lifecycle lock.
preflight --prefix "$2"
# Preflight completed; only fixed, owned files are removed.
rm -- "$prefix/bin/omega" "$prefix/bin/om" "$prefix/bin/omg"
for f in omc bridge math om uninstall.sh verify-elf.sh HELP.txt pins LICENSE MATH-CONTRACT.md CAPABILITIES.md created-directories files.sha256; do
    rm -- "$payload/$f"
done
rmdir "$payload" 2>/dev/null || :
rmdir "$prefix/.omega-install-lock"
trap - EXIT
[ "$created_bin" = 0 ] || rmdir "$prefix/bin" 2>/dev/null || :
[ "$created_lib" = 0 ] || rmdir "$prefix/lib" 2>/dev/null || :
[ "$created_prefix" = 0 ] || rmdir "$prefix" 2>/dev/null || :
printf 'Removed unchanged Omega commands; unrelated files and user data preserved.\n'
