/* A freestanding object that uses the C API (tests/native/v2/run.sh): built with -ffreestanding
 * -fno-builtin from omega_api_decl.h, its undefined symbols must be the API functions it calls and
 * nothing else; no abort, no C library function. fsmain.c links it with omega_api_defs.c and runs it. */
#include "omega_api_decl.h"

int fs_check(void)
{
    static const uint8_t abc[3] = {'a', 'b', 'c'};
    lay_blk c = {0};
    uint8_t o[16];
    uint8_t s8[8] = {1, 2, 3, 4, 5, 6, 7, 8};
    int bad = 0;
    if (bsum(abc, 3) != 294)
        bad |= 1;
    absorb(&c, abc, 3);
    if (c.a != 294 || c.n != 3)
        bad |= 2;
    if (digest(&c, o) != 3 || o[8] != 294 % 256 || o[9] != 1)
        bad |= 4;
    if (swap8(s8, 8, s8) != 8 || s8[0] != 8 || s8[7] != 1)
        bad |= 8;
    return bad;
}
