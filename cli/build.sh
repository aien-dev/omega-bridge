#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-only
set -eu
cd "$(dirname "$0")/.."
seed=${1:?usage: sh cli/build.sh /absolute/path/to/qualified/omc}
expected=191b776ef98821597c3e30655da6d680a9b66edbc9ceaca3c39c61ea6df098e9
actual=$(sha256sum "$seed"); actual=${actual%% *}
[ "$actual" = "$expected" ] || { echo 'unqualified Omega seed' >&2; exit 1; }
[ "$(uname -sm)" = 'Linux aarch64' ] || { echo 'native policy build requires qualified Linux aarch64 seed' >&2; exit 1; }
mkdir -p build/attach build/attach-test
"$seed" < cli/attachment-policy.om > build/attach/attachment-policy
chmod 755 build/attach/attachment-policy
cp build/attach/attachment-policy build/attach-test/attachment-policy
"${CC:-cc}" -std=c11 -D_GNU_SOURCE -O2 -Wall -Wextra -Werror -Wformat=2 -Wshadow -o build/attach/om cli/omega.c cli/discover.c cli/host.c cli/sandbox.c
"${CC:-cc}" -std=c11 -D_GNU_SOURCE -DOMEGA_ATTACH_TESTING -O2 -Wall -Wextra -Werror -Wformat=2 -Wshadow -o build/attach-test/om cli/omega.c cli/discover.c cli/host.c cli/sandbox.c
ln -sf om build/attach/omg
ln -sf om build/attach-test/omg
