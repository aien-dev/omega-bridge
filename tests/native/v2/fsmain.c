/* Hosted driver for fsuse.c (tests/native/v2/run.sh): runs fs_check, then a refused call through the
 * out-of-line API, which must abort (SIGABRT) as the inline wrappers do. */
#include "omega_api_decl.h"
#include <stdio.h>
#include <string.h>

int fs_check(void);

int main(int argc, char **argv)
{
    if (argc > 1 && strcmp(argv[1], "refuse") == 0) {
        uint8_t s8[8];
        swap8(s8, 7, s8); /* trap 3: abort */
        printf("not aborted\n");
        return 0;
    }
    int bad = fs_check();
    printf("%s fs_check %d\n", bad ? "FAIL" : "PASS", bad);
    return bad != 0;
}
