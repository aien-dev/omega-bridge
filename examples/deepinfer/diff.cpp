// Differential test of DeepInfer FlopsEstimator::floor_prefix, capped_prefix and pairs. Three sides:
//   Up: the pinned upstream bytes (csrc/engine/flops_estimator.hpp lines 237-257, extracted verbatim by
//       run.sh into upstream.inc and checked against its sha256), compiled here with GCC UBSan;
//   Om: the Omega unit examples/deepinfer/flops_pairs.om through the generated omega_native.h;
//   an oracle: direct enumeration (sum of min(t / ratio, cap) term by term) for the grid, and for large
//       values a step model in __int128 (does a C++ step leave int64_t?) plus a second closed form,
//       ratio*b*(b-1)/2 + b*(s+1) with n = ratio*b + s (evidence/deepinfer-flops-pairs/wolfram.md).
// Built -std=c++20 -fsanitize=undefined -fno-sanitize-recover=all: a case the step model calls defined
// that is undefined in the upstream code aborts the run. Modes:
//   diff grid            exhaustive n, begin, end in 0..300, ratio 1..40, cap 0..40
//   diff random SEED N   N seeded random large in-domain cases (both overflow classes)
//   diff up FN ARG...    the upstream function alone (run per boundary case: UBSan may abort)
//   diff om FN ARG...    the Omega function alone: "status S value V"
// FN is fp, cp or pairs. Every Omega declaration comes from omega_native.h.
#include <algorithm>
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>

#include "omega_native.h"

struct Up {
#include "upstream.inc"
    static int64_t fp(int64_t n, int64_t r) { return floor_prefix(n, r); }
    static int64_t cp(int64_t n, int64_t r, int64_t c) { return capped_prefix(n, r, c); }
    static int64_t pr(int64_t b, int64_t e, int64_t r, int64_t c) { return pairs(b, e, r, c); }
};

static const uint64_t SENTINEL = 0x5555555555555555u;
struct Om {
    uint32_t st;
    int64_t v;
    bool kept; // result left unchanged on a trap
};
static Om om_fp(int64_t n, int64_t r) {
    uint64_t x = SENTINEL;
    const uint32_t st = omega2_floor_prefix(&x, static_cast<uint64_t>(n), static_cast<uint64_t>(r));
    return {st, static_cast<int64_t>(x), st == 0 || x == SENTINEL};
}
static Om om_cp(int64_t n, int64_t r, int64_t c) {
    uint64_t x = SENTINEL;
    const uint32_t st = omega2_capped_prefix(&x, static_cast<uint64_t>(n), static_cast<uint64_t>(r), static_cast<uint64_t>(c));
    return {st, static_cast<int64_t>(x), st == 0 || x == SENTINEL};
}
static Om om_pr(int64_t b, int64_t e, int64_t r, int64_t c) {
    uint64_t x = SENTINEL;
    const uint32_t st = omega2_pairs(&x, static_cast<uint64_t>(b), static_cast<uint64_t>(e), static_cast<uint64_t>(r),
                                     static_cast<uint64_t>(c));
    return {st, static_cast<int64_t>(x), st == 0 || x == SENTINEL};
}

// Step model: each C++ step of the upstream expression in __int128; ovf when any step leaves int64_t.
using i128 = __int128;
static bool fits(i128 x) { return x >= INT64_MIN && x <= INT64_MAX; }
struct M {
    bool ovf;
    int64_t v;
};
static M m_fp(int64_t n, int64_t r) {
    const i128 b = n / r, n1 = i128(n) + 1;
    if (!fits(n1)) return {true, 0};
    const i128 a = b * n1;
    if (!fits(a)) return {true, 0};
    const i128 rb = i128(r) * b;
    if (!fits(rb)) return {true, 0};
    const i128 b1 = b + 1;
    if (!fits(b1)) return {true, 0};
    const i128 t = rb * b1;
    if (!fits(t)) return {true, 0};
    const i128 v = a - t / 2;
    if (!fits(v)) return {true, 0};
    return {false, int64_t(v)};
}
static M m_cp(int64_t n, int64_t r, int64_t c) {
    const i128 rc = i128(r) * c;
    if (!fits(rc)) return {true, 0};
    const int64_t stop = std::min<int64_t>(n, int64_t(rc));
    const M f = m_fp(stop, r);
    if (f.ovf) return f;
    const i128 d = i128(n) - stop;
    if (!fits(d)) return {true, 0};
    const i128 dc = d * c;
    if (!fits(dc)) return {true, 0};
    const i128 v = f.v + dc;
    if (!fits(v)) return {true, 0};
    return {false, int64_t(v)};
}
static M m_pr(int64_t b, int64_t e, int64_t r, int64_t c) {
    const M x = c == 0 ? m_fp(e, r) : m_cp(e, r, c);
    const M y = c == 0 ? m_fp(b, r) : m_cp(b, r, c);
    if (x.ovf || y.ovf) return {true, 0};
    const i128 v = i128(x.v) - y.v;
    if (!fits(v)) return {true, 0};
    return {false, int64_t(v)};
}
// Second closed form, exact in __int128 for every n, ratio, cap in int64_t's nonnegative range.
static i128 alt_fp(i128 n, i128 r) {
    const i128 b = n / r, s = n - r * b;
    return r * b * (b - 1) / 2 + b * (s + 1);
}
static i128 alt_cp(i128 n, i128 r, i128 c) {
    const i128 s = std::min(n, r * c);
    return alt_fp(s, r) + (n - s) * c;
}

static long fails = 0;
static void bad(const char *what, const char *fn, const int64_t *a, int k) {
    if (++fails <= 20) {
        printf("MISMATCH %s %s", what, fn);
        for (int i = 0; i < k; i++) printf(" %" PRId64, a[i]);
        printf("\n");
    }
}

static int grid() {
    long cases[3] = {0, 0, 0}, mis[3] = {0, 0, 0};
    for (int64_t r = 1; r <= 40; r++) {
        int64_t acc = 0;
        for (int64_t n = 0; n <= 300; n++) {
            if (n > 0) acc += n / r;
            const Om o = om_fp(n, r);
            cases[0]++;
            if (o.st != 0 || o.v != acc || Up::fp(n, r) != acc) {
                mis[0]++;
                const int64_t a[] = {n, r};
                bad("grid", "floor_prefix", a, 2);
            }
        }
        for (int64_t c = 0; c <= 40; c++) {
            acc = 0;
            for (int64_t n = 0; n <= 300; n++) {
                if (n > 0) acc += std::min(n / r, c);
                const Om o = om_cp(n, r, c);
                cases[1]++;
                if (o.st != 0 || o.v != acc || Up::cp(n, r, c) != acc) {
                    mis[1]++;
                    const int64_t a[] = {n, r, c};
                    bad("grid", "capped_prefix", a, 3);
                }
            }
            for (int64_t b = 0; b <= 300; b++) {
                acc = 0; // sum over t = b+1 .. e, term by term (cap 0: uncapped)
                for (int64_t e = b; e <= 300; e++) {
                    if (e > b) acc += c == 0 ? e / r : std::min(e / r, c);
                    const Om o = om_pr(b, e, r, c);
                    cases[2]++;
                    if (o.st != 0 || o.v != acc || Up::pr(b, e, r, c) != acc) {
                        mis[2]++;
                        const int64_t a[] = {b, e, r, c};
                        bad("grid", "pairs", a, 4);
                    }
                }
            }
        }
    }
    const char *nm[] = {"floor_prefix", "capped_prefix", "pairs"};
    for (int i = 0; i < 3; i++) printf("GRID %s cases=%ld mismatches=%ld\n", nm[i], cases[i], mis[i]);
    return mis[0] + mis[1] + mis[2] == 0 ? 0 : 1;
}

// A nonnegative value of random magnitude: bit length uniform in 0..63, so small and large both appear.
static int64_t mag(std::mt19937_64 &g, int lo) {
    const int bits = int(g() % 64);
    int64_t v = bits == 0 ? 0 : int64_t(g() >> (64 - bits));
    return std::max<int64_t>(v, lo);
}

static int random_cases(uint64_t seed, long count) {
    std::mt19937_64 g(seed);
    long defined[3] = {0, 0, 0}, ovf[3] = {0, 0, 0}, mis[3] = {0, 0, 0};
    for (long i = 0; i < count; i++) {
        const int f = int(i % 3);
        int64_t n = mag(g, 0), b = mag(g, 0);
        const int64_t r = mag(g, 1), c = mag(g, 0);
        if (b > n) std::swap(b, n);
        M m;
        Om o;
        i128 alt = 0;
        if (f == 0) {
            m = m_fp(n, r), o = om_fp(n, r), alt = alt_fp(n, r);
        } else if (f == 1) {
            m = m_cp(n, r, c), o = om_cp(n, r, c), alt = alt_cp(n, r, c);
        } else {
            const int64_t cc = (g() & 3) == 0 ? 0 : c; // a quarter uncapped
            m = m_pr(b, n, r, cc), o = om_pr(b, n, r, cc);
            alt = cc == 0 ? alt_fp(n, r) - alt_fp(b, r) : alt_cp(n, r, cc) - alt_cp(b, r, cc);
            const int64_t a[] = {b, n, r, cc};
            if (m.ovf) {
                ovf[2]++;
                if (o.st != 1 || !o.kept) mis[2]++, bad("random-ovf", "pairs", a, 4);
            } else {
                defined[2]++;
                if (o.st != 0 || o.v != m.v || i128(o.v) != alt || Up::pr(b, n, r, cc) != o.v) mis[2]++, bad("random", "pairs", a, 4);
            }
            continue;
        }
        const int64_t a[] = {n, r, c};
        const char *nm = f == 0 ? "floor_prefix" : "capped_prefix";
        if (m.ovf) {
            ovf[f]++;
            if (o.st != 1 || !o.kept) mis[f]++, bad("random-ovf", nm, a, f == 0 ? 2 : 3);
        } else {
            defined[f]++;
            const int64_t up = f == 0 ? Up::fp(n, r) : Up::cp(n, r, c);
            if (o.st != 0 || o.v != m.v || i128(o.v) != alt || up != o.v) mis[f]++, bad("random", nm, a, f == 0 ? 2 : 3);
        }
    }
    const char *nm[] = {"floor_prefix", "capped_prefix", "pairs"};
    for (int i = 0; i < 3; i++)
        printf("RANDOM seed=%" PRIu64 " %s defined=%ld overflow=%ld mismatches=%ld\n", seed, nm[i], defined[i], ovf[i], mis[i]);
    return mis[0] + mis[1] + mis[2] == 0 && defined[0] && defined[1] && defined[2] && ovf[0] && ovf[1] && ovf[2] ? 0 : 1;
}

int main(int argc, char **argv) {
    if (argc >= 2 && !strcmp(argv[1], "grid")) return grid();
    if (argc == 4 && !strcmp(argv[1], "random")) return random_cases(strtoull(argv[2], nullptr, 10), strtol(argv[3], nullptr, 10));
    if (argc >= 4 && (!strcmp(argv[1], "up") || !strcmp(argv[1], "om"))) {
        int64_t a[4] = {0, 0, 0, 0};
        const int k = argc - 3;
        for (int i = 0; i < k && i < 4; i++) a[i] = strtoll(argv[3 + i], nullptr, 10);
        const char *fn = argv[2];
        const bool up = argv[1][0] == 'u';
        if (!strcmp(fn, "fp") && k == 2) {
            if (up) return printf("value %" PRId64 "\n", Up::fp(a[0], a[1])) < 0;
            const Om o = om_fp(a[0], a[1]);
            return printf("status %u value %" PRId64 " kept %d\n", o.st, o.st ? 0 : o.v, o.kept) < 0;
        }
        if (!strcmp(fn, "cp") && k == 3) {
            if (up) return printf("value %" PRId64 "\n", Up::cp(a[0], a[1], a[2])) < 0;
            const Om o = om_cp(a[0], a[1], a[2]);
            return printf("status %u value %" PRId64 " kept %d\n", o.st, o.st ? 0 : o.v, o.kept) < 0;
        }
        if (!strcmp(fn, "pairs") && k == 4) {
            if (up) return printf("value %" PRId64 "\n", Up::pr(a[0], a[1], a[2], a[3])) < 0;
            const Om o = om_pr(a[0], a[1], a[2], a[3]);
            return printf("status %u value %" PRId64 " kept %d\n", o.st, o.st ? 0 : o.v, o.kept) < 0;
        }
    }
    fprintf(stderr, "usage: diff grid | random SEED N | up|om fp|cp|pairs ARG...\n");
    return 2;
}
