# Wolfram checks for examples/deepinfer

Every identity, bound and expected value used by `examples/deepinfer` (flops_pairs.om, boundary.txt,
the callers) came from the Wolfram Language evaluator (MCP `WolframLanguageEvaluator`), 2026-10-31.
Each line is `query -> result`. Notation: n = ratio*b + s with b = Quotient[n, ratio], 0 <= s < ratio;
m = 2^63 - 1.

## Closed forms (the upstream code is a closed form of a sum)

- Sum of floor(t/r) over t = 1..n, split into whole blocks and the partial block:
  `Simplify[Sum[j r,{j,0,b-1}]+b (s+1) == b (b r+s+1)-r b (b+1)/2]` -> `True`
  (the left sum simplifies to `((-1 + b)*b*r)/2 + b*(1 + s)`, the second closed form diff.cpp and
  diff.py compare against).
- floor_prefix equals the enumeration on the test grid, with fp[n,r] = b (n+1) - r b (b+1)/2:
  `AllTrue[Table[fp[n,r]==Sum[Floor[t/r],{t,1,n}],{n,0,300},{r,1,40}]]` -> `True`
- The `/ 2` is exact: `Resolve[ForAll[b, b∈Integers, Mod[b (b+1),2]==0]]` -> `True`
- capped_prefix: for t >= r*c, floor(t/r) >= c, and for t < r*c, floor(t/r) <= c, so
  sum min(floor(t/r), c) = floor_prefix(min(n, r c), r) + (n - min(n, r c)) c:
  `Simplify[Floor[(r c+d)/r]>=c, r>0&&c>=0&&d>=1&&integers]` -> `True`;
  `Simplify[Floor[(r c-d)/r]<=c, r>0&&c>=0&&d>=0&&integers]` -> `True`;
  the capped form against an `Accumulate` of min(floor(t/r), c) over n 0..300, r 1..40, c 0..40
  (493640 cases) -> `True`.
- pairs(begin, end) = prefix(end) - prefix(begin) is the sum over t = begin+1..end by definition of
  the prefix sum (no query needed).

## Overflow boundaries (where an upstream step leaves int64_t)

- `Floor[(Sqrt[4 m+1]-1)/2]` -> `3037000499` (n0, largest n with n (n+1) <= m);
  `n0 (n0+1) <= m` -> `True`; `(n0+1)(n0+2) > m` -> `True`; `n0 (n0+1)/2` -> `4611686016981624750`.
- `Sum[t,{t,1,3037000500}] <= m` -> `True` and `3037000500*3037000501 > m` -> `True`: the true
  floor_prefix(3037000500, 1) fits in int64_t but the upstream step `blocks * (n + 1)` overflows;
  Omega traps 1 at the same step (boundary `fp 3037000500 1 | ovf`).
- `2^32*2^31 > m` -> `True` (capped_prefix `ratio * cap` overflows at ratio 2^32, cap 2^31);
  `4294967296*2147483648 > 2^63-1` -> `True`; `2^32*2147483647 <= m` -> `True`.
- `2^62` -> `4611686018427387904`; `(2^62-2)*2+3 == m` -> `True`; `(2^62-1)*2 <= m` -> `True`;
  `(2^62-1)*2+3 > m` -> `True`; `Sum[Min[t,2],{t,1,2^62+1}] > m` -> `True`.

## Expected values (boundary.txt and callers)

- `Sum[Floor[t/2],{t,1,9}]` -> `20` (fp 9 2)
- `Sum[Min[Floor[t/2],3],{t,1,9}]` -> `18` (cp 9 2 3)
- `Sum[Min[Floor[t/2],3],{t,4,9}]` -> `16` (pairs 3 9 2 3); `Sum[Min[Floor[t/2],3],{t,1,3}]` -> `2`
- `Sum[Floor[t/2],{t,4,9}]` -> `18`, and `Sum[Floor[t/2],{t,1,9}]-Sum[Floor[t/2],{t,1,3}]` -> `18` (pairs 3 9 2 0)
- `Sum[Min[t,512],{t,1,4096}]` -> `1966336` (pairs 0 4096 1 512: a 512-token SWA window over 4096 queries)
- `Sum[t,{t,1,3037000499}]` -> `4611686016981624750`; `Sum[Floor[t/1],{t,1,3037000499}]` -> `4611686016981624750`
- `Sum[Min[t,2],{t,1,2^62}]` -> `9223372036854775807` (cp 2^62 1 2 = m exactly)
- `Sum[Min[t,1],{t,1,2^63-1}]==2^63-1` -> `True` (cp m 1 1, pairs 0 m 1 1)
- `Sum[Min[Floor[t/2^32],2147483647],{t,1,5}]` -> `0`; `Sum[Min[Floor[t/4294967296],2147483647],{t,1,5}]` -> `0`

## Overflow measurement controls (overflow-measurement.log)

- `Mod[2^63-1,7]` -> `0`; `Mod[2^63-2,7]` -> `6`; `Mod[3037000499*3037000500,7]` -> `2`;
  `3037000500^2 > 2^63-1` -> `True`.
