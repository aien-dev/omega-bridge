#!/bin/sh
# Build st2gguf next to this script. No dependencies beyond a C compiler.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
: "${CC:=cc}"
"$CC" -std=gnu11 -O2 -Wall -Wextra -o "$here/st2gguf" "$here/st2gguf.c"
echo "built $here/st2gguf"
