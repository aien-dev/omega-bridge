#!/bin/sh
# Reproduce exact-byte source imports. No binaries or working-tree files imported.
set -eu
cd "$(dirname "$0")/.."
tools/verify-sources.sh --lock-only
offline=0
case ${1-} in --offline) offline=1; shift;; esac
[ "$#" -le 1 ] || { echo 'usage: tools/import-sources.sh [--offline] [clean-cached-git-repo]' >&2; exit 64; }
repo=${1:-build/source-cache}
if [ "$#" = 1 ]; then
    [ -z "$(git -C "$repo" status --porcelain --untracked-files=all)" ] || { echo 'omega: dirty source cache refused' >&2; exit 65; }
else
    mkdir -p "$repo"
    [ -d "$repo/.git" ] || git -C "$repo" init -q
fi
for component in seed math; do
    pin=$(awk -v c="$component" '$1==c {print $2}' provenance/pins)
    if ! git -C "$repo" cat-file -e "$pin^{commit}" 2>/dev/null; then
        [ "$offline" = 0 ] || { echo 'omega: offline source pin missing' >&2; exit 65; }
        git -C "$repo" fetch -q --depth=1 https://github.com/aien-spark/omega.git "$pin"
    fi
    while IFS= read -r p; do
        mkdir -p "$(dirname "$p")"
        git -C "$repo" show "$pin:$p" > "$p"
    done < "provenance/$component.files"
done
git -C "$repo" show "$pin:LICENSE" > provenance/OMEGA-LICENSE
tools/verify-sources.sh
