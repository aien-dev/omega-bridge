// C++ caller for examples/deepinfer/flops_pairs.om. Every Omega declaration comes from the generated
// omega_native.h; nothing is typed by hand here. Expected values: evidence/deepinfer-flops-pairs/wolfram.md.
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

#include "omega_native.h"

namespace {
int fails = 0;
void check(const std::string &name, bool ok) {
    std::printf("%s %s\n", ok ? "PASS" : "FAIL", name.c_str());
    if (!ok) fails++;
}
struct V {
    const char *fn;
    std::vector<int64_t> a;
    uint32_t status;
    int64_t want;
};
uint32_t call(const V &x, uint64_t *r) {
    std::vector<uint64_t> u;
    for (int64_t v : x.a) u.push_back(static_cast<uint64_t>(v));
    if (!std::strcmp(x.fn, "floor_prefix")) return omega2_floor_prefix(r, u[0], u[1]);
    if (!std::strcmp(x.fn, "capped_prefix")) return omega2_capped_prefix(r, u[0], u[1], u[2]);
    return omega2_pairs(r, u[0], u[1], u[2], u[3]);
}
} // namespace

int main() {
    const std::vector<V> vs = {
        {"floor_prefix", {9, 2}, 0, 20},
        {"capped_prefix", {9, 2, 3}, 0, 18},
        {"pairs", {3, 9, 2, 3}, 0, 16},
        {"pairs", {3, 9, 2, 0}, 0, 18},
        {"pairs", {0, 4096, 1, 512}, 0, 1966336},
        {"floor_prefix", {3037000499, 1}, 0, 4611686016981624750},
        {"capped_prefix", {4611686018427387904, 1, 2}, 0, 9223372036854775807},
        {"floor_prefix", {3037000500, 1}, 1, 0},
        {"capped_prefix", {4611686018427387905, 1, 2}, 1, 0},
        {"capped_prefix", {0, 4294967296, 2147483648}, 1, 0},
        {"floor_prefix", {-1, 1}, 9, 0},
        {"floor_prefix", {5, 0}, 9, 0},
        {"pairs", {5, 3, 1, 0}, 9, 0},
        {"pairs", {0, 3, 1, -1}, 9, 0},
    };
    const uint64_t sentinel = 0x5a5a5a5a5a5a5a5aull;
    check("ident: library == header", std::strcmp(omega2_ident_flops_pairs(), OMEGA2_IDENT_flops_pairs) == 0);
    for (const V &x : vs) {
        uint64_t r = sentinel;
        const uint32_t st = call(x, &r);
        std::string name = x.fn;
        for (int64_t v : x.a) name += " " + std::to_string(v);
        name += " -> status " + std::to_string(st);
        check(name, st == x.status && (st == OMEGA_OK ? static_cast<int64_t>(r) == x.want : r == sentinel));
    }
    check("null result refused 32", omega2_pairs(nullptr, 0, 3, 1, 0) == OMEGA_BAD_ARG);
    return fails ? 1 : 0;
}
