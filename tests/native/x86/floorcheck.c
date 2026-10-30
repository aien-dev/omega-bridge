/* Test-only inclusion gives the oracle access to the actual TLS stack top.
 * The framed six-byte payload returns R15 without modifying the owned stack. */
#include "omega_native.h"
#include "omega_native.c"
#include <stdio.h>

int main(void)
{
    uint64_t result = 0;
    uint8_t out[64];
    if (omega2_floor(&result, out) != OMEGA_OK)
        return 2;
    if (result != (uintptr_t)(ombr_stk - OMBR_STACK)) {
        puts("FAIL stack floor follows carved out-buffer top");
        return 1;
    }
    puts("PASS R15 equals actual usable mapping floor with an out buffer");
    return 0;
}
