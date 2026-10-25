# Python bigint reference for the G1 sample calc(i0, i1) = (i0 + i1) * (i0 - i1) modulo 2^64.
# "vectors" prints the boundary vectors, one "i0 i1" line each: every ordered pair of the values below
# (0, 1, 2^63 and 2^64-1 among them). "expect" reads such lines and prints "i0 i1 0 result", the line
# each caller must print for a status-0 call. Arbitrary-precision ints, reduced once at the end.
import sys
M = 2**64
VALUES = [0, 1, 2, 2**32, 2**63 - 1, 2**63, 2**63 + 1, 2**64 - 2, 2**64 - 1]
if sys.argv[1:] == ["vectors"]:
    for a in VALUES:
        for b in VALUES:
            print(a, b)
elif sys.argv[1:] == ["expect"]:
    for line in sys.stdin:
        a, b = map(int, line.split())
        print(a, b, 0, ((a + b) * (a - b)) % M)
else:
    sys.exit("usage: reference.py vectors|expect")
