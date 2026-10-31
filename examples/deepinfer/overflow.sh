#!/bin/sh
# Does a 64-bit long add, sub or mul that leaves the long range trap or wrap? Measured on each compiler
# named on the command line (sh overflow.sh OMC...), in program mode (exit status 101 = trap 1, Omega
# exit_status) for OM-1 and, when the compiler accepts it, OM-2. Also records two facts flops_pairs.om
# depends on: an OM-1 requires clause and an OM-2 requires clause on a violated precondition, and a
# parameter named end. Each probe prints "<compiler> <profile> <probe>: <exit status> (<expected>)".
# The non-overflowing controls exit with the value mod 7 (evidence/deepinfer-flops-pairs/wolfram.md).
set -eu
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
probe() { # omc profile name expected program
  omc=$1; prof=$2; name=$3; want=$4; shift 4
  { [ "$prof" = OM-2 ] && echo om2; printf '%s\n' "$@"; } > "$T/p.om"
  if "$omc" < "$T/p.om" > "$T/p.bin" 2> "$T/p.err"; then
    chmod +x "$T/p.bin"; rc=0; "$T/p.bin" > /dev/null 2>&1 || rc=$?
  else rc="refused: $(head -c 120 "$T/p.err")"; fi
  echo "$(sha256sum < "$omc" | cut -c1-8) $prof $name: $rc ($want)"
}
two() { # omc profile name expected op a b
  probe "$1" "$2" "$3" "$4" "fn main to int" "a = long $6" "b = long $7" "q = $5 a b" "ret int rem q 7" "end"
}
for omc in "$@"; do
  echo "INFO compiler $omc sha256 $(sha256sum < "$omc" | cut -d' ' -f1)"
  for prof in OM-1 OM-2; do
    two "$omc" $prof "add 2^63-1 + 1" "trap: 101" add 9223372036854775807 1
    two "$omc" $prof "sub -(2^63-1) - 2" "trap: 101" sub -9223372036854775807 2
    two "$omc" $prof "mul 2^62 * 2" "trap: 101" mul 4611686018427387904 2
    two "$omc" $prof "mul 3037000500 * 3037000500" "trap: 101" mul 3037000500 3037000500
    two "$omc" $prof "control add 2^63-1 + 0" "0 = Mod[2^63-1,7]" add 9223372036854775807 0
    two "$omc" $prof "control mul (2^62-1) * 2" "6 = Mod[2^63-2,7]" mul 4611686018427387903 2
    two "$omc" $prof "control mul 3037000499 * 3037000500" "2" mul 3037000499 3037000500
    probe "$omc" $prof "mul through a function's parameters 3037000500^2" "trap: 101" \
      "fn f a long b long to long" "ret mul a b" "end" "fn main to int" "ret int rem f 3037000500 3037000500 7" "end"
    probe "$omc" $prof "requires ge x 0 called with -5" "trap 9: 109; a return of -4 is int -4 = 252" \
      "fn step x long to long" "requires ge x 0" "ret add x 1" "end" "fn main to int" "ret int step -5" "end"
    probe "$omc" $prof "parameter named end" "refused" \
      "fn f begin long end long to long" "ret sub end begin" "end" "fn main to int" "ret int f 1 3" "end"
  done
done
