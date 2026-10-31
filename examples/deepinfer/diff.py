"""Differential test of the Omega unit examples/deepinfer/flops_pairs.om through the generated Python
binding (omega_native.py, ctypes) against Python oracles: term-by-term enumeration of
sum(min(t // ratio, cap)) for the grid, and for large values a step model in Python integers (does a
step of the upstream C++ expression leave int64_t?) plus the second closed form
ratio*b*(b-1)//2 + b*(s+1), n = ratio*b + s. Run by run.sh as
python3 -I diff.py BUILD_DIR BOUNDARY_FILE SEED COUNT; prints one line per section and exits 0 only when
nothing mismatched. The grid is diff.cpp's: n, begin, end in 0..300, ratio 1..40, cap 0..40."""
import ctypes
import random
import sys

sys.path.insert(0, sys.argv[1])
import omega_native as om  # noqa: E402  every Omega declaration comes from the generated binding

LO, HI = -(1 << 63), (1 << 63) - 1
SENTINEL = 0x5555555555555555
FAILS = []


def bits(v):
    return v & 0xFFFFFFFFFFFFFFFF


def signed(u):
    return u - (1 << 64) if u >> 63 else u


def call(fn, *args):
    r = ctypes.c_uint64(SENTINEL)
    st = fn(ctypes.byref(r), *(bits(a) for a in args))
    return st, signed(r.value), st == 0 or r.value == SENTINEL


FN = {"fp": om.omega2_floor_prefix, "cp": om.omega2_capped_prefix, "pairs": om.omega2_pairs}


def trunc_div(a, b):  # C++ / on integers
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


class Ovf(Exception):
    pass


def chk(v):
    if not LO <= v <= HI:
        raise Ovf
    return v


def m_fp(n, r):
    b = trunc_div(n, r)
    a = chk(b * chk(n + 1))
    t = chk(chk(r * b) * chk(b + 1))
    return chk(a - trunc_div(t, 2))


def m_cp(n, r, c):
    stop = min(n, chk(r * c))
    return chk(m_fp(stop, r) + chk(chk(n - stop) * c))


def m_pr(b, e, r, c):
    if c == 0:
        return chk(m_fp(e, r) - m_fp(b, r))
    return chk(m_cp(e, r, c) - m_cp(b, r, c))


def model(fn, a):
    """None when a step leaves int64_t (C++ undefined behaviour), else the value."""
    try:
        return {"fp": m_fp, "cp": m_cp, "pairs": m_pr}[fn](*a)
    except Ovf:
        return None


def alt_fp(n, r):
    b, s = divmod(n, r)
    return r * b * (b - 1) // 2 + b * (s + 1)


def alt_cp(n, r, c):
    s = min(n, r * c)
    return alt_fp(s, r) + (n - s) * c


def alt(fn, a):
    if fn == "fp":
        return alt_fp(*a)
    if fn == "cp":
        return alt_cp(*a)
    b, e, r, c = a
    return alt_fp(e, r) - alt_fp(b, r) if c == 0 else alt_cp(e, r, c) - alt_cp(b, r, c)


def bad(what, fn, a, got):
    FAILS.append((what, fn, a, got))
    if len(FAILS) <= 20:
        print("MISMATCH", what, fn, *a, got)


def grid():
    n_fp = n_cp = n_pr = 0
    m0 = len(FAILS)
    for r in range(1, 41):
        acc = 0
        for n in range(301):
            acc += n // r
            n_fp += 1
            got = call(FN["fp"], n, r)
            if got[:2] != (0, acc):
                bad("grid", "fp", (n, r), got)
        for c in range(41):
            acc = 0
            for n in range(301):
                acc += min(n // r, c)
                n_cp += 1
                got = call(FN["cp"], n, r, c)
                if got[:2] != (0, acc):
                    bad("grid", "cp", (n, r, c), got)
    for r in range(1, 41):
        for c in range(41):
            for b in range(301):
                acc = 0
                for e in range(b, 301):
                    if e > b:
                        acc += e // r if c == 0 else min(e // r, c)
                    n_pr += 1
                    got = call(FN["pairs"], b, e, r, c)
                    if got[:2] != (0, acc):
                        bad("grid", "pairs", (b, e, r, c), got)
    print("PY-GRID floor_prefix n 0..300 ratio 1..40 cases=%d; capped_prefix cap 0..40 cases=%d; "
          "pairs begin<=end 0..300 cases=%d; mismatches=%d" % (n_fp, n_cp, n_pr, len(FAILS) - m0))


def mag(g, lo):
    k = g.randrange(64)
    return max(g.getrandbits(k) if k else 0, lo)


def rand(seed, count):
    g = random.Random(seed)
    m0 = len(FAILS)
    defined = ovf = 0
    for i in range(count):
        n, b, r, c = mag(g, 0), mag(g, 0), mag(g, 1), mag(g, 0)
        b, n = min(b, n), max(b, n)
        fn = ("fp", "cp", "pairs")[i % 3]
        a = {"fp": (n, r), "cp": (n, r, c), "pairs": (b, n, r, c if g.randrange(4) else 0)}[fn]
        want = model(fn, a)
        got = call(FN[fn], *a)
        if want is None:
            ovf += 1
            if got[0] != 1 or not got[2]:
                bad("random-ovf", fn, a, got)
        else:
            defined += 1
            if got[:2] != (0, want) or want != alt(fn, a):
                bad("random", fn, a, got)
    print("PY-RANDOM seed=%d defined=%d overflow=%d mismatches=%d" % (seed, defined, ovf, len(FAILS) - m0))
    if not defined or not ovf:
        FAILS.append(("random", "one class empty", (), ()))


def boundary(path):
    m0 = len(FAILS)
    k = 0
    for line in open(path):
        line = line.split("#")[0].strip()
        if not line:
            continue
        lhs, expect = (s.strip() for s in line.split("|"))
        fn, *args = lhs.split()
        a = tuple(int(x) for x in args)
        got = call(FN[fn], *a)
        k += 1
        if expect == "dom":
            ok = got[0] == 9 and got[2]
        elif expect == "ovf":
            ok = got[0] == 1 and got[2] and model(fn, a) is None
        else:
            ok = got[:2] == (0, int(expect)) and model(fn, a) == int(expect)
        if not ok:
            bad("boundary", fn, a, got)
    print("PY-BOUNDARY cases=%d mismatches=%d" % (k, len(FAILS) - m0))


def main():
    ident = om.omega2_ident_flops_pairs()
    print("PY-IDENT", ident.decode())
    if ident != om.OMEGA2_IDENT_flops_pairs:
        FAILS.append(("ident", ident))
    grid()
    rand(int(sys.argv[3]), int(sys.argv[4]))
    boundary(sys.argv[2])
    print("PY-TOTAL mismatches=%d" % len(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
