// Standalone check of flops_estimator-omega.patch without torch. run.sh applies the patch to a copy of
// the pinned header and extracts the same two regions from the original and the patched header:
//   *-types.inc  struct QueryRange and struct PairTerm (whose count() calls pairs);
//   *-fns.inc    floor_prefix, capped_prefix, pairs (and the patch's omega_result) and query_ranges.
// Each pair of regions becomes a struct with the members query_ranges reads; TORCH_CHECK is a stub
// that throws std::runtime_error with the same message parts. Built -std=c++20 with GCC UBSan (the
// original side may not hit undefined behaviour). The patched side calls the Omega library through
// omega_native.h. Prints one line per section; exit 0 only when every compared result is identical.
#include <algorithm>
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>

#include "omega_native.h"

template <typename... A> static std::string torch_msg(const A &...a) {
    std::ostringstream s;
    (s << ... << a);
    return s.str();
}
#define TORCH_CHECK(cond, ...)                                                                                         \
    do {                                                                                                               \
        if (!(cond)) throw std::runtime_error(torch_msg(__VA_ARGS__));                                                 \
    } while (0)

struct Orig {
    bool compact = false;
    int keep_tokens = 0;
    int window_size = 0;
    bool has_truncated_swa = false;
#include "orig-types.inc"
#include "orig-fns.inc"
};
struct Patched {
    bool compact = false;
    int keep_tokens = 0;
    int window_size = 0;
    bool has_truncated_swa = false;
#include "patched-types.inc"
#include "patched-fns.inc"
};

static long fails = 0;
static void bad(const char *what, long a, long b, long c, long d) {
    if (++fails <= 20) printf("MISMATCH %s %ld %ld %ld %ld\n", what, a, b, c, d);
}

// The exception message (or "" when none) and the result of f.
template <typename F> static std::pair<std::string, int64_t> run(F f) {
    try {
        return {"", f()};
    } catch (const std::runtime_error &e) {
        return {e.what(), 0};
    }
}

int main() {
    // 1. PairTerm::count, the path calc_attn_flops uses: shift = ratio * (block - 1), block 1..4.
    long n1 = 0;
    for (int64_t ratio = 1; ratio <= 40; ratio++)
        for (int cap = 0; cap <= 40; cap++)
            for (int64_t block = 1; block <= 4; block++)
                for (int b = 0; b <= 120; b++)
                    for (int e = b + 1; e <= 120; e++) {
                        const Orig::PairTerm ot{ratio, cap, ratio * (block - 1), 0, 0};
                        const Patched::PairTerm pt{ratio, cap, ratio * (block - 1), 0, 0};
                        const Orig::QueryRange oq{b, e, 0};
                        const Patched::QueryRange pq{b, e, 0};
                        n1++;
                        if (ot.count(oq) != pt.count(pq)) bad("PairTerm::count", ratio, cap, b, e);
                    }
    printf("PATCH PairTerm::count cases=%ld mismatches=%ld\n", n1, fails);

    // 2. query_ranges (pairs with ratio 1, cap window_size), including its TORCH_CHECK refusals.
    long n2 = 0, refused = 0;
    const long f1 = fails;
    const int windows[] = {0, 1, 7, 64, 128};
    const int keeps[] = {0, 5, 140};
    for (int w : windows)
        for (int flags = 0; flags < 4; flags++)
            for (int keep : keeps) {
                Orig o;
                Patched p;
                o.window_size = p.window_size = w;
                o.compact = p.compact = flags & 1;
                o.has_truncated_swa = p.has_truncated_swa = flags & 2;
                o.keep_tokens = p.keep_tokens = keep;
                for (int q = 0; q <= 24; q++)
                    for (int k = q; k <= 160; k += 3)
                        for (int prompt = 0; prompt < 2; prompt++)
                            for (int fl : {-1, k, k + 3, k + 200, k - 1})
                                for (int sv = 0; sv <= k - q + 1; sv += 4) {
                                    n2++;
                                    const auto a = run([&] {
                                        const auto [f, c] = o.query_ranges(q, k, prompt, fl, sv);
                                        return f.begin * 1000003LL + f.end * 1009LL + f.swa_pairs * 7919LL + c.begin * 31LL +
                                               c.end * 17LL + c.swa_pairs;
                                    });
                                    const auto b = run([&] {
                                        const auto [f, c] = p.query_ranges(q, k, prompt, fl, sv);
                                        return f.begin * 1000003LL + f.end * 1009LL + f.swa_pairs * 7919LL + c.begin * 31LL +
                                               c.end * 17LL + c.swa_pairs;
                                    });
                                    if (!a.first.empty()) refused++;
                                    if (a != b) bad("query_ranges", q, k, fl, sv);
                                }
            }
    printf("PATCH query_ranges cases=%ld refused-by-TORCH_CHECK=%ld mismatches=%ld\n", n2, refused, fails - f1);

    // 3. Omega traps reach TORCH_CHECK. The original has no refusal: these inputs are outside its
    // domain (ratio 0 divides by zero; 3037000500 overflows a step), so only the patched side runs.
    struct T {
        const char *name;
        std::pair<std::string, int64_t> got;
        const char *want;
    };
    const T traps[] = {
        {"pairs(5, 3, 1, 0)", run([] { return Patched::pairs(5, 3, 1, 0); }), "pairs: Omega trap 9"},
        {"pairs(0, 3, 1, -1)", run([] { return Patched::pairs(0, 3, 1, -1); }), "pairs: Omega trap 9"},
        {"floor_prefix(5, 0)", run([] { return Patched::floor_prefix(5, 0); }), "floor_prefix: Omega trap 9"},
        {"floor_prefix(3037000500, 1)", run([] { return Patched::floor_prefix(3037000500, 1); }), "floor_prefix: Omega trap 1"},
        {"capped_prefix(0, 4294967296, 2147483648)", run([] { return Patched::capped_prefix(0, 4294967296LL, 2147483648LL); }),
         "capped_prefix: Omega trap 1"},
    };
    long n3 = 0;
    const long f2 = fails;
    for (const T &t : traps) {
        n3++;
        printf("PATCH trap %s -> \"%s\"\n", t.name, t.got.first.c_str());
        if (t.got.first != t.want) bad(t.name, 0, 0, 0, 0);
    }
    printf("PATCH traps cases=%ld mismatches=%ld\n", n3, fails - f2);
    printf("PATCH total mismatches=%ld\n", fails);
    return fails == 0 ? 0 : 1;
}
