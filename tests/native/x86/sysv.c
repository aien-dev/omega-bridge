/* Generated Omega declarations remain authoritative. The assembly probe is
 * deliberately a separate caller so its preserved-register sentinels cannot
 * be optimized away by a host compiler. */
#include "omega_native.h"
#include <stdio.h>

extern uint32_t x86_sysv_probe(void *, uint64_t *, uint64_t, uint64_t);

int main(void)
{
    uint64_t result = 0;
    const uint8_t abc[] = {'a', 'b', 'c'};
    if (x86_sysv_probe((void *)omega2_bsum, &result, (uintptr_t)abc, sizeof abc) != OMEGA_OK || result != 294)
        return 1;
    if (x86_sysv_probe((void *)omega2_bsum, &result, 0, 1) != OMEGA_BAD_ARG || result != 294)
        return 2;
    puts("PASS SysV AMD64 callee-saved registers on success and refusal");
    return 0;
}
