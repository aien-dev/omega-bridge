/* C caller for examples/deepinfer/flops_pairs.om (run.sh builds it plain and with BTI enforced).
 * Every Omega declaration comes from the generated omega_native.h; nothing is typed by hand here.
 * Expected values: evidence/deepinfer-flops-pairs/wolfram.md. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "omega_native.h"

static int fails;
static void check(const char *name, int ok) {
    printf("%s %s\n", ok ? "PASS" : "FAIL", name);
    if (!ok) fails++;
}

enum { FP, CP, PR };
struct v {
    int fn;
    int64_t a[4];
    uint32_t status;
    int64_t want;
};

static const struct v vs[] = {
    {FP, {9, 2}, 0, 20},
    {CP, {9, 2, 3}, 0, 18},
    {PR, {3, 9, 2, 3}, 0, 16},
    {PR, {3, 9, 2, 0}, 0, 18},
    {PR, {0, 4096, 1, 512}, 0, 1966336},
    {FP, {3037000499, 1}, 0, 4611686016981624750},
    {CP, {4611686018427387904, 1, 2}, 0, 9223372036854775807},
    {FP, {3037000500, 1}, 1, 0},
    {CP, {4611686018427387905, 1, 2}, 1, 0},
    {CP, {0, 4294967296, 2147483648}, 1, 0},
    {FP, {-1, 1}, 9, 0},
    {FP, {5, 0}, 9, 0},
    {PR, {5, 3, 1, 0}, 9, 0},
    {PR, {0, 3, 1, -1}, 9, 0},
};

static uint32_t call(const struct v *x, uint64_t *r) {
    const uint64_t *u = (const uint64_t *)x->a;
    if (x->fn == FP) return omega2_floor_prefix(r, u[0], u[1]);
    if (x->fn == CP) return omega2_capped_prefix(r, u[0], u[1], u[2]);
    return omega2_pairs(r, u[0], u[1], u[2], u[3]);
}

int main(void) {
    static const char *names[] = {"floor_prefix", "capped_prefix", "pairs"};
    const uint64_t sentinel = 0x5a5a5a5a5a5a5a5aull;
    check("ident: library == header", strcmp(omega2_ident_flops_pairs(), OMEGA2_IDENT_flops_pairs) == 0);
    for (size_t i = 0; i < sizeof vs / sizeof vs[0]; i++) {
        uint64_t r = sentinel;
        const uint32_t st = call(&vs[i], &r);
        const int ok = st == vs[i].status && (st == 0 ? (int64_t)r == vs[i].want : r == sentinel);
        char name[160];
        snprintf(name, sizeof name, "%s %lld %lld %lld %lld -> status %u", names[vs[i].fn], (long long)vs[i].a[0],
                 (long long)vs[i].a[1], (long long)vs[i].a[2], (long long)vs[i].a[3], st);
        check(name, ok);
    }
    check("null result refused 32", omega2_pairs(NULL, 0, 3, 1, 0) == OMEGA_BAD_ARG);
    return fails ? 1 : 0;
}
