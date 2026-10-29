/* Links omega_bsum (the v1 symbol) from the v1 header; against the v2 library this must fail to link. */
#include "omega_native.h"
int main(void)
{
    uint64_t r;
    unsigned char d[4] = {0};
    return (int)omega_bsum(&r, d, 4);
}
