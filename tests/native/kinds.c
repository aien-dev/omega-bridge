// kinds.c: f32 and ushort array kinds of native ABI v1 (docs/NATIVE-ABI.md), checked against values computed
// by this C caller (AArch64 _Float16 conversion as the f16 oracle), plus the refusals for those kinds.
#include <stdint.h>
#include <stdio.h>
#include <string.h>
uint32_t omega_fsum(uint64_t *r, const void *a, uint64_t an, const void *h, uint64_t hn, void *d, uint64_t dn);
uint32_t omega_halve(uint64_t *r, void *h, uint64_t hn);
static int fails;
static void check(const char *what, int ok) { printf("%s %s\n", ok ? "PASS" : "FAIL", what); if (!ok) fails++; }
int main(void) {
    float a[4] = { 1.5f, -2.25f, 1e-3f, 65504.0f }, d[4];
    _Float16 hf[4] = { (_Float16) 0.5f, (_Float16) -3.0f, (_Float16) 0.0999755859375f, (_Float16) 2.0f };
    uint16_t h[4]; memcpy(h, hf, sizeof h);
    uint64_t r = 0;
    check("fsum status 0", omega_fsum(&r, a, 4, h, 4, d, 4) == 0);
    int same = 1;
    for (int i = 0; i < 4; i++) { float w = a[i] + (float) hf[i]; same &= memcmp(&w, &d[i], 4) == 0; }
    check("fsum f32 lanes == C oracle", same);
    float s = d[0] + d[3]; uint32_t sb; memcpy(&sb, &s, 4);
    check("fsum result bits == C oracle", r == sb);
    _Float16 g[3] = { (_Float16) 6.0f, (_Float16) -0.75f, (_Float16) 1024.0f }; uint16_t gb[3]; memcpy(gb, g, sizeof gb);
    check("halve status 0", omega_halve(&r, gb, 3) == 0);
    int halved = 1;
    for (int i = 0; i < 3; i++) { _Float16 w = g[i] / 2; uint16_t wb; memcpy(&wb, &w, 2); halved &= wb == gb[i]; }
    check("halve ushort edit == C oracle", halved);
    char raw[64] __attribute__((aligned(8)));
    memcpy(raw + 4, a, 16);
    check("f32 view misaligned (2 bytes) refused", omega_fsum(&r, raw + 2, 4, h, 4, d, 4) == 32);
    check("f32 view at 4-byte alignment accepted", omega_fsum(&r, raw + 4, 4, h, 4, d, 4) == 0);
    check("ushort view misaligned refused", omega_fsum(&r, a, 4, (char *) h + 1, 4, d, 4) == 32);
    check("f32 wrong length refused", omega_fsum(&r, a, 3, h, 4, d, 4) == 32);
    check("f32 edit overlapping f32 view refused", omega_fsum(&r, a, 4, h, 4, a, 4) == 32);
    check("ushort view overlapping f32 edit refused", omega_fsum(&r, a, 4, (uint16_t *) d, 4, d, 4) == 32);
    check("null ushort edit refused", omega_halve(&r, NULL, 3) == 32);
    printf("KINDS %s\n", fails ? "FAIL" : "PASS");
    return fails != 0;
}
