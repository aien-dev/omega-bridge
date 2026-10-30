// Native ABI v2 oracle, C++ (tests/native/v2/run.sh): the generated omega_native.h and omega_api.h only.
#include "omega_api.h"
#include <cstdio>
#include <cstring>

static int fails;
static void check(const char *name, bool ok)
{
    std::printf("%s %s\n", ok ? "PASS" : "FAIL", name);
    if (!ok)
        fails++;
}
static const uint64_t R0 = 0x5a5a5a5a5a5a5a5aull;

int main()
{
    uint64_t r;
    check("ident vec", std::strcmp(omega2_ident_vec(), OMEGA2_IDENT_vec) == 0);
    check("ident lay", std::strcmp(omega2_ident_lay(), OMEGA2_IDENT_lay) == 0);
    const uint8_t abc[3] = {'a', 'b', 'c'};
    r = R0;
    check("bsum abc = 294", omega2_bsum(&r, abc, 3) == OMEGA_OK && r == 294);
    r = R0;
    check("bsum (NULL, 0) = 0", omega2_bsum(&r, nullptr, 0) == OMEGA_OK && r == 0);
    r = R0;
    check("bsum (NULL, 1) refused", omega2_bsum(&r, nullptr, 1) == OMEGA_BAD_ARG && r == R0);
    alignas(8) uint8_t raw[16] = {0};
    r = R0;
    check("wsum misaligned refused",
          omega2_wsum(&r, reinterpret_cast<const uint32_t *>(raw + 1), 1) == OMEGA_BAD_ARG && r == R0);
    const uint32_t w4[4] = {1, 2, 3, 0xffffffffu};
    r = R0;
    check("wsum = 4294967301", omega2_wsum(&r, w4, 4) == OMEGA_OK && r == 4294967301ull);
    uint16_t h[8] = {1, 2, 3, 4, 0, 0, 0, 0};
    r = R0;
    check("vcopy edit == view refused", omega2_vcopy(&r, h, 4, h, 4) == OMEGA_BAD_ARG);
    r = R0;
    check("vcopy adjacent accepted", omega2_vcopy(&r, h, 4, h + 4, 4) == OMEGA_OK && r == 4 && h[7] == 4);
    uint8_t d16[16] = {0};
    r = R0;
    check("#748 golden: vpart o 2^64-2 k 4 traps 3", omega2_vpart(&r, d16, 16, UINT64_MAX - 1, 4) == 3 && r == R0);
    uint8_t s8[8] = {1, 2, 3, 4, 5, 6, 7, 8};
    r = R0;
    check("swap8 out == view reversed", omega2_swap8(&r, s8, 8, s8) == OMEGA_OK && s8[0] == 8 && s8[7] == 1);
    uint64_t ho[2] = {11, 22};
    r = R0;
    check("halt traps 9, out untouched", omega2_halt(&r, ho) == 9 && ho[0] == 11 && ho[1] == 22 && r == R0);
    lay_blk c;
    std::memset(&c, 0, sizeof c);
    absorb(&c, abc, 3);
    uint8_t o16[16];
    check("absorb, digest", digest(&c, o16) == 3 && c.a == 294 && o16[8] == 294 % 256 && o16[9] == 1);
    uint64_t f3[3] = {0, 0, 0};
    fillv(f3, 3, 9);
    check("fillv", f3[0] == 9 && f3[2] == 9);
    const int64_t l3[3] = {-5, 7, -9};
    check("lsum = -7", lsum(l3, 3) == -7);
    bool inter = true;
    for (uint64_t k = 0; k < 100; k++) {
        r = R0;
        inter = inter && omega_madd(&r, k, 3, 1) == OMEGA_OK && r == 3 * k + 1;
        r = R0;
        inter = inter && omega2_bsum(&r, abc, 3) == OMEGA_OK && r == 294;
    }
    check("interleaved madd (v1) and bsum (v2)", inter);
    std::printf("%s %d\n", fails ? "CPP-V2 FAIL" : "CPP-V2 PASS", fails);
    return fails != 0;
}
