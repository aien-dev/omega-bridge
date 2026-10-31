/* A hosted caller of the freestanding ABI v2 binding (outputs freest + fapic) of sha256-om2.om and
 * fsout.om; tests/native/test_freestanding_om2.py builds it and checks what it prints. `fsom2` prints
 * one line per check; `fsom2 trap` calls a C API wrapper on a trapping input and must not return. */
#include "omega_api_decl.h"
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

/* Four threads hash "abc" concurrently, each on its own stack (no shared runtime state). */
static void *spin(void *arg)
{
    static const uint8_t want[4] = {0xba, 0x78, 0x16, 0xbf};
    uint8_t o[32];
    (void)arg;
    for (int i = 0; i < 2000; i++) {
        memset(o, 0, sizeof o);
        sha256_hash((const uint8_t *)"abc", 3, o);
        if (memcmp(o, want, 4) != 0)
            return (void *)1;
    }
    return 0;
}

static void hex(const char *name, const uint8_t *d)
{
    printf("%s ", name);
    for (int i = 0; i < 32; i++)
        printf("%02x", d[i]);
    printf("\n");
}

static void once(const char *name, const char *m)
{
    uint8_t o[32];
    memset(o, 0xa5, sizeof o);
    sha256_hash((const uint8_t *)m, strlen(m), o);
    hex(name, o);
}

static uint8_t million[1000000];

int main(int argc, char **argv)
{
    if (argc > 1 && strcmp(argv[1], "trap") == 0) {
        uint8_t o[16];
        fsout(0, o);
        printf("RETURNED\n");
        return 0;
    }
    once("empty", "");
    once("abc", "abc");
    once("448", "abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq");
    sha256_ctx c;
    uint8_t o[32];
    memset(million, 'a', sizeof million);
    memset(o, 0xa5, sizeof o);
    sha256_init(&c);
    sha256_update(&c, million, 123);
    sha256_update(&c, million + 123, sizeof million - 123);
    sha256_final(&c, o);
    hex("million", o);
    /* A refused argument (a null view of 5 bytes): status 32, the out buffer untouched. */
    uint64_t r = 99;
    memset(o, 0xa5, sizeof o);
    uint32_t s = omega2_sha256_hash(&r, NULL, 5, o);
    int same = 1;
    for (int i = 0; i < 32; i++)
        same &= o[i] == 0xa5;
    printf("badarg %u %d\n", s, same);
    /* Success: the whole out buffer comes back (written byte 7, the rest zero-filled). */
    uint8_t b[16];
    memset(b, 0xaa, sizeof b);
    s = omega2_fsout(&r, 1, b);
    int zero = 1;
    for (int i = 1; i < 16; i++)
        zero &= b[i] == 0;
    printf("outok %u %llu %u %d\n", s, (unsigned long long)r, b[0], zero);
    /* A trap after the out write: nonzero status, the caller's buffer as it was. */
    memset(b, 0xaa, sizeof b);
    s = omega2_fsout(&r, 0, b);
    same = 1;
    for (int i = 0; i < 16; i++)
        same &= b[i] == 0xaa;
    printf("outtrap %u %d\n", s, same);
    pthread_t t[4];
    int bad = 0;
    for (int i = 0; i < 4; i++)
        bad |= pthread_create(&t[i], 0, spin, 0) != 0;
    for (int i = 0; i < 4; i++) {
        void *v = (void *)1;
        bad |= pthread_join(t[i], &v) != 0 || v != 0;
    }
    printf("threads %d\n", !bad);
    return 0;
}
