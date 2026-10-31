/* hcall.c: the C oracle for hfile.om through the --host library (tests/native/v2/run.sh, section 11).
 * hcall FILE MISSING LINK: FILE holds 5 bytes, MISSING does not exist, LINK is a symlink to FILE.
 * Each expectation is computed here by libc, independently of the Omega unit. */
#define _GNU_SOURCE
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#include "omega_native.h"

static int bad;
static void check(const char *what, int ok) {
    printf("%s %s\n", ok ? "PASS" : "FAIL", what);
    if (!ok) bad = 1;
}

static int64_t peek(const char *p) {
    uint64_t r = 0;
    if (omega2_peek(&r, (const uint8_t *)p, strlen(p)) != OMEGA_OK) return INT64_MIN;
    return (int64_t)r;
}

int main(int argc, char **argv) {
    if (argc != 4) { fprintf(stderr, "usage: hcall FILE MISSING LINK\n"); return 2; }
    uint64_t r = 0;
    uint64_t want = (uint64_t)getuid() + geteuid() + getgid() + getegid();
    check("ids == getuid+geteuid+getgid+getegid", omega2_ids(&r) == OMEGA_OK && r == want);
    check("peek FILE reads its 5 bytes", peek(argv[1]) == 5);
    check("peek MISSING = -ENOENT", peek(argv[2]) == -ENOENT);
    check("peek LINK = -ELOOP (fopen with O_NOFOLLOW)", peek(argv[3]) == -ELOOP);
    struct stat st;
    check("size FILE == st_size", stat(argv[1], &st) == 0 && omega2_size(&r, (const uint8_t *)argv[1], strlen(argv[1])) == OMEGA_OK
          && (int64_t)r == (int64_t)st.st_size);
    check("ident carries host=", strstr(omega2_ident_hfile(), " host=") != NULL
          && strcmp(omega2_ident_hfile(), OMEGA2_IDENT_hfile) == 0);
    return bad;
}
