/* EXPECT_TRAP is 5 for a genuine trap, 34 for a corrupted callback, and 6
 * for exhaustion of the test runtime's deliberately bounded stack. */
#include "omega_native.h"
#include <stdio.h>
#include <string.h>

extern uint32_t x86_sysv_probe(void *, uint64_t *, uint64_t, uint64_t);

int main(void)
{
    const uint64_t sentinel = UINT64_C(0x5a5a5a5a5a5a5a5a);
    uint64_t result = sentinel;
    if (x86_sysv_probe((void *)omega_trapcall, &result, 0, 0) != EXPECT_TRAP || result != sentinel)
        return 1;
#if EXPECT_TRAP == 6
    uint8_t out[64], original[64];
    memset(out, 0xa5, sizeof out);
    memcpy(original, out, sizeof out);
    if (x86_sysv_probe((void *)omega2_outtrap, &result, (uintptr_t)out, 0) != 6 ||
        result != sentinel || memcmp(out, original, sizeof out) != 0)
        return 3;
#endif
    /* Reenter the same library after recovery. With the small-floor control,
     * the nested unit will still exhaust its budget: a separate scalar unit
     * proves the native stack and TLS active flag were restored. */
    if (x86_sysv_probe((void *)omega_follow, &result, 7, 0) != OMEGA_OK || result != 7)
        return 2;
    puts("PASS trap status, unchanged result, SysV saved registers, subsequent call");
    return 0;
}
