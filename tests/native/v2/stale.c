/* The stale-identity check: compares the library's identity string for vec with the one the generated
 * header carries. Exit 0 when equal, 3 (and the two strings) when the header is from another source. */
#include "omega_native.h"
#include <stdio.h>
#include <string.h>
int main(void)
{
    if (strcmp(omega2_ident_vec(), OMEGA2_IDENT_vec) == 0)
        return 0;
    printf("STALE library: %s\nSTALE header:  %s\n", omega2_ident_vec(), OMEGA2_IDENT_vec);
    return 3;
}
