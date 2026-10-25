/* Test-only adapter to the existing, separately pinned Omega C reference
 * interpreter. No placement policy or expected answers live here. This is
 * not the seeded compiler, native Omega execution, or a production runtime. */
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "osc_interp.h"

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    FILE *f = fopen(argv[1], "rb");
    if (!f) return 2;
    if (fseek(f, 0, SEEK_END)) return 2;
    long size = ftell(f);
    if (size <= 0 || size > 16777216 || fseek(f, 0, SEEK_SET)) return 2;
    unsigned char *bytes = malloc((size_t)size);
    OscUnit *unit = calloc(1, sizeof *unit);
    OscRt *rt = calloc(1, sizeof *rt);
    if (!bytes || !unit || !rt) return 2;
    if (fread(bytes, 1, (size_t)size, f) != (size_t)size || fclose(f)) return 2;
    if (osc_ir_decode(bytes, (size_t)size, unit)) return 2;
    int entry = -1;
    for (unsigned i = 0; i < unit->nfuncs; i++)
        if (!strcmp(unit->funcs[i].name, "main")) entry = (int)i;
    if (entry < 0) return 2;
    osc_rt_init(rt);
    uint64_t result = UINT64_MAX;
    int trap = osc_interp_run(unit, entry, NULL, 0, rt, &result);
    printf("reference trap=%d result=%" PRIu64 "\n", trap, result);
    free(bytes); free(unit); free(rt);
    return trap == 0 && result == 0 ? 0 : 1;
}
