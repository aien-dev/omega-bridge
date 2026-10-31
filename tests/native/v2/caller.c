/* Native ABI v2 oracle (tests/native/v2/run.sh): calls the OM-2 test units vec, lay, one and hoist, and the
 * OM-1 unit madd, through the generated declarations only (omega_native.h, omega_api.h). Expected
 * values are computed here independently of Omega. Prints one PASS or FAIL line per check; exit 0
 * only when all pass. */
#define _GNU_SOURCE
#include "omega_api.h"
#include <dlfcn.h>
#include <pthread.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/time.h>

static int fails;
static void check(const char *name, int ok)
{
    printf("%s %s\n", ok ? "PASS" : "FAIL", name);
    if (!ok)
        fails++;
}

#define R0 0x5a5a5a5a5a5a5a5aull

static uint64_t refsum(const uint8_t *d, uint64_t n)
{
    uint64_t s = 0;
    for (uint64_t i = 0; i < n; i++)
        s += d[i];
    return s;
}

static uint64_t rng = 0x9e3779b97f4a7c15ull;
static uint64_t next(void)
{
    rng ^= rng << 13;
    rng ^= rng >> 7;
    rng ^= rng << 17;
    return rng;
}

static volatile uint32_t sig_status = 99;
static volatile int sig_fired;
static void on_alarm(int s)
{
    (void)s;
    uint64_t r = 0, d[1] = {1};
    sig_status = omega2_vlen(&r, d, 1);
    sig_fired = 1;
}

static void *swap_thread(void *arg)
{
    uint8_t *ok = arg, d[8], o[8];
    *ok = 1;
    for (int k = 0; k < 20000; k++) {
        for (int i = 0; i < 8; i++)
            d[i] = (uint8_t)(k + i);
        uint64_t r = R0;
        if (omega2_swap8(&r, d, 8, o) != OMEGA_OK || r != 8)
            *ok = 0;
        for (int i = 0; i < 8; i++)
            if (o[i] != (uint8_t)(k + 7 - i))
                *ok = 0;
    }
    return 0;
}

/* hoist_thread: 5000 calls of the hoisting unit on this thread's own Omega stack; every fifth call traps
 * in inner, after the loop wrote this thread's array. */
static void *hoist_thread(void *arg)
{
    uint8_t *ok = arg;
    uint64_t d[64] = {0};
    *ok = 1;
    for (int k = 0; k < 5000; k++) {
        uint64_t r = R0, t = (uint64_t)(k % 5 == 4);
        uint32_t s = omega2_hadd(&r, d, 64, t);
        if (t ? s != 9 || r != R0 : s != OMEGA_OK || r != 1920569)
            *ok = 0;
        for (int i = 0; i < 64; i++)
            if (d[i] != 70000ull * (uint64_t)(k + 1))
                *ok = 0;
    }
    return 0;
}

/* ombr_probe(fn, result, a, b, c): set x19..x28 and d8..d15 to known values, call fn(result, a, b, c),
 * then return the status in the low 32 bits and the number of changed registers in the high 32 bits
 * (as tests/native/caller.c). */
uint64_t ombr_probe(void *fn, uint64_t *result, uint64_t a, uint64_t b, uint64_t c);
__asm__(".text\n.balign 4\n.globl ombr_probe\n.type ombr_probe,%function\nombr_probe:\nhint #34\n"
        "stp x29,x30,[sp,#-160]!\nmov x29,sp\nstp x19,x20,[sp,#16]\nstp x21,x22,[sp,#32]\nstp x23,x24,[sp,#48]\n"
        "stp x25,x26,[sp,#64]\nstp x27,x28,[sp,#80]\nstp d8,d9,[sp,#96]\nstp d10,d11,[sp,#112]\n"
        "stp d12,d13,[sp,#128]\nstp d14,d15,[sp,#144]\nmov x16,x0\nmov x0,x1\nmov x1,x2\nmov x2,x3\nmov x3,x4\n"
        "mov x19,#119\nmov x20,#120\nmov x21,#121\nmov x22,#122\nmov x23,#123\nmov x24,#124\nmov x25,#125\nmov x26,#126\nmov x27,#127\nmov x28,#128\n"
        "mov x9,#108\nfmov d8,x9\nmov x9,#109\nfmov d9,x9\nmov x9,#110\nfmov d10,x9\nmov x9,#111\nfmov d11,x9\nmov x9,#112\nfmov d12,x9\nmov x9,#113\nfmov d13,x9\nmov x9,#114\nfmov d14,x9\nmov x9,#115\nfmov d15,x9\n"
        "blr x16\nmov w0,w0\nmov x9,#0\n"
        "cmp x19,#119\ncinc x9,x9,ne\ncmp x20,#120\ncinc x9,x9,ne\ncmp x21,#121\ncinc x9,x9,ne\ncmp x22,#122\ncinc x9,x9,ne\ncmp x23,#123\ncinc x9,x9,ne\ncmp x24,#124\ncinc x9,x9,ne\ncmp x25,#125\ncinc x9,x9,ne\ncmp x26,#126\ncinc x9,x9,ne\ncmp x27,#127\ncinc x9,x9,ne\ncmp x28,#128\ncinc x9,x9,ne\n"
        "fmov x10,d8\ncmp x10,#108\ncinc x9,x9,ne\nfmov x10,d9\ncmp x10,#109\ncinc x9,x9,ne\nfmov x10,d10\ncmp x10,#110\ncinc x9,x9,ne\nfmov x10,d11\ncmp x10,#111\ncinc x9,x9,ne\nfmov x10,d12\ncmp x10,#112\ncinc x9,x9,ne\nfmov x10,d13\ncmp x10,#113\ncinc x9,x9,ne\nfmov x10,d14\ncmp x10,#114\ncinc x9,x9,ne\nfmov x10,d15\ncmp x10,#115\ncinc x9,x9,ne\n"
        "orr x0,x0,x9,lsl #32\nldp d14,d15,[sp,#144]\nldp d12,d13,[sp,#128]\nldp d10,d11,[sp,#112]\nldp d8,d9,[sp,#96]\n"
        "ldp x27,x28,[sp,#80]\nldp x25,x26,[sp,#64]\nldp x23,x24,[sp,#48]\nldp x21,x22,[sp,#32]\nldp x19,x20,[sp,#16]\n"
        "ldp x29,x30,[sp],#160\nret\n.size ombr_probe,.-ombr_probe\n");

int main(void)
{
    uint64_t r;
    uint32_t s;
    setvbuf(stdout, 0, _IOLBF, 0); /* each line survives a crash (the negative controls rely on it) */

    /* Identity: the library's string equals the one the generated header carries. */
    check("ident vec: library == header", strcmp(omega2_ident_vec(), OMEGA2_IDENT_vec) == 0);
    check("ident lay: library == header", strcmp(omega2_ident_lay(), OMEGA2_IDENT_lay) == 0);
    check("ident one: library == header", strcmp(omega2_ident_one(), OMEGA2_IDENT_one) == 0);
    printf("IDENT %s\nIDENT %s\nIDENT %s\n", omega2_ident_vec(), omega2_ident_lay(), omega2_ident_one());

    /* Values. */
    const uint8_t abc[3] = {'a', 'b', 'c'};
    r = R0;
    check("bsum abc = 294", omega2_bsum(&r, abc, 3) == OMEGA_OK && r == 294);
    uint32_t w4[4] = {1, 2, 3, 0xffffffffu};
    r = R0;
    check("wsum {1,2,3,2^32-1} = 4294967301", omega2_wsum(&r, w4, 4) == OMEGA_OK && r == 4294967301ull);
    int64_t l3[3] = {-5, 7, -9};
    r = R0;
    check("lsum {-5,7,-9} = -7", omega2_lsum(&r, l3, 3) == OMEGA_OK && (int64_t)r == -7);
    int64_t lo[2] = {INT64_MAX, 1};
    r = R0;
    check("lsum overflow traps 1, result unchanged", omega2_lsum(&r, lo, 2) == 1 && r == R0);

    /* Empty views: len 0 with any pointer, NULL included, is the empty view. */
    r = R0;
    check("bsum (NULL, 0) = 0", omega2_bsum(&r, NULL, 0) == OMEGA_OK && r == 0);
    r = R0;
    check("wsum (misaligned, 0) = 0", omega2_wsum(&r, (const uint32_t *)(abc + 1), 0) == OMEGA_OK && r == 0);
    r = R0;
    check("vlen (NULL, 0) = 0", omega2_vlen(&r, NULL, 0) == OMEGA_OK && r == 0);

    /* Refusals before any Omega code runs: status 32, result unchanged. */
    r = R0;
    check("NULL with len 1 refused", omega2_bsum(&r, NULL, 1) == OMEGA_BAD_ARG && r == R0);
    _Alignas(8) uint8_t raw[64] = {0};
    r = R0;
    check("wsum misaligned by 1 refused", omega2_wsum(&r, (const uint32_t *)(raw + 1), 1) == OMEGA_BAD_ARG && r == R0);
    r = R0;
    check("wsum misaligned by 2 refused", omega2_wsum(&r, (const uint32_t *)(raw + 2), 1) == OMEGA_BAD_ARG && r == R0);
    r = R0;
    check("vlen misaligned by 4 refused", omega2_vlen(&r, (const uint64_t *)(raw + 4), 1) == OMEGA_BAD_ARG && r == R0);
    r = R0;
    check("vcopy edit misaligned by 1 refused",
          omega2_vcopy(&r, (const uint16_t *)raw, 1, (uint16_t *)(raw + 33), 1) == OMEGA_BAD_ARG && r == R0);
    r = R0;
    check("wsum len*4 = 2^64 (len 2^62) refused", omega2_wsum(&r, w4, 1ull << 62) == OMEGA_BAD_ARG && r == R0);
    r = R0;
    check("vlen len*8 overflows (len 2^61) refused", omega2_vlen(&r, (const uint64_t *)raw, 1ull << 61) == OMEGA_BAD_ARG);
    r = R0;
    check("vlen len 2^64-1 refused", omega2_vlen(&r, (const uint64_t *)raw, UINT64_MAX) == OMEGA_BAD_ARG && r == R0);
    /* #748 golden at the bridge boundary: a view of len 2^64-1 bytes cannot be formed, whatever o and k. */
    r = R0;
    check("#748 golden: vpart len 2^64-1, o 2^64-2, k 4 refused (32)",
          omega2_vpart(&r, raw, UINT64_MAX, UINT64_MAX - 1, 4) == OMEGA_BAD_ARG && r == R0);
    r = R0;
    check("bsum len 2^64-1 refused", omega2_bsum(&r, raw, UINT64_MAX) == OMEGA_BAD_ARG && r == R0);
    /* Address wrap: end exactly 2^64 is refused; end 2^64-8 is accepted (vlen reads no element). */
    const uint64_t *top = (const uint64_t *)(uintptr_t)(UINTPTR_MAX - 15u);
    r = R0;
    check("vlen at 2^64-16, len 2 (end 2^64) refused", omega2_vlen(&r, top, 2) == OMEGA_BAD_ARG && r == R0);
    r = R0;
    check("vlen at 2^64-16, len 1 (end 2^64-8) accepted", omega2_vlen(&r, top, 1) == OMEGA_OK && r == 1);
    r = R0;
    check("wsum at 2^64-16, len 2^62-4 (wraps) refused",
          omega2_wsum(&r, (const uint32_t *)top, (1ull << 62) - 4) == OMEGA_BAD_ARG && r == R0);
    /* Huge accepted length: 2^32+5 elements of a PROT_NONE NORESERVE mapping; vlen reads none. */
    uint64_t big = (1ull << 32) + 5;
    void *m = mmap(0, big * 8, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE, -1, 0);
    if (m != MAP_FAILED) {
        r = R0;
        check("vlen len 2^32+5 accepted, len arrives whole", omega2_vlen(&r, m, big) == OMEGA_OK && r == big);
        munmap(m, big * 8);
    } else
        check("mmap 32 GiB NORESERVE for the huge-len check", 0);
    r = R0;
    check("result NULL refused", omega2_bsum(NULL, abc, 3) == OMEGA_BAD_ARG);

    /* #748 golden inside the code: the part checks are o <= len then k <= len - o, never o + k. */
    uint8_t d16[16];
    for (int i = 0; i < 16; i++)
        d16[i] = (uint8_t)(i + 1);
    r = R0;
    check("#748 golden: vpart len 16, o 2^64-2, k 4 traps 3 (wrapped o+k = 2 not used)",
          omega2_vpart(&r, d16, 16, UINT64_MAX - 1, 4) == 3 && r == R0);
    int grid = 1;
    for (uint64_t o = 0; o <= 18; o++)
        for (uint64_t k = 0; k <= 18; k++) {
            r = R0;
            s = omega2_vpart(&r, d16, 16, o, k);
            if (o <= 16 && k <= 16 - o) {
                if (s != OMEGA_OK || r != refsum(d16 + o, k))
                    grid = 0;
            } else if (s != 3 || r != R0)
                grid = 0;
        }
    check("vpart over every o, k in 0..18 of a 16-byte view (sum or trap 3)", grid);
    r = R0;
    check("vpart o = len, k = 0 (empty part at the end) = 0", omega2_vpart(&r, d16, 16, 16, 0) == OMEGA_OK && r == 0);
    r = R0;
    check("vpart o 2^64-1, k 1 traps 3", omega2_vpart(&r, d16, 16, UINT64_MAX, 1) == 3);

    /* Split inputs: every split point of a 64-byte buffer, whole = left + right. */
    uint8_t b64[64];
    for (int i = 0; i < 64; i++)
        b64[i] = (uint8_t)next();
    int split = 1;
    uint64_t whole = 0;
    split &= omega2_bsum(&whole, b64, 64) == OMEGA_OK && whole == refsum(b64, 64);
    for (uint64_t k = 0; k <= 64; k++) {
        uint64_t a = R0, b = R0;
        split &= omega2_bsum(&a, b64, k) == OMEGA_OK && omega2_bsum(&b, b64 + k, 64 - k) == OMEGA_OK && a + b == whole;
    }
    check("bsum split at every point 0..64", split);

    /* Large inputs: 16 MiB of bytes, 16 Mi uint words, summed by the unit in parts of 1000000. */
    uint64_t nb = 16777216;
    uint8_t *lb = malloc(nb);
    uint32_t *lw = malloc(nb * 4);
    if (lb && lw) {
        uint64_t rs = 0, rw = 0;
        for (uint64_t i = 0; i < nb; i++) {
            lb[i] = (uint8_t)next();
            lw[i] = (uint32_t)next();
            rs += lb[i];
            rw += lw[i];
        }
        r = R0;
        check("bsum 16 MiB = reference", omega2_bsum(&r, lb, nb) == OMEGA_OK && r == rs);
        r = R0;
        check("wsum 16 Mi words (64 MiB) = reference", omega2_wsum(&r, lw, nb) == OMEGA_OK && r == rw);
        r = R0;
        check("bsum 16 MiB at an odd address (uchar needs no alignment)",
              omega2_bsum(&r, lb + 1, nb - 1) == OMEGA_OK && r == rs - lb[0]);
    } else
        check("malloc 80 MiB", 0);

    /* Overlap: an edit range against any other array or the result; half-open; empty overlaps nothing. */
    _Alignas(8) uint16_t h[16];
    for (int i = 0; i < 16; i++)
        h[i] = (uint16_t)(100 + i);
    r = R0;
    check("vcopy edit == view refused", omega2_vcopy(&r, h, 4, h, 4) == OMEGA_BAD_ARG && r == R0);
    r = R0;
    check("vcopy edit overlapping the view by one element refused",
          omega2_vcopy(&r, h, 4, h + 3, 4) == OMEGA_BAD_ARG && h[3] == 103 && r == R0);
    r = R0;
    check("vcopy adjacent ranges (half-open) accepted",
          omega2_vcopy(&r, h, 4, h + 4, 4) == OMEGA_OK && r == 4 && h[4] == 100 && h[7] == 103);
    r = R0;
    check("vcopy both empty at one address = 0", omega2_vcopy(&r, h, 0, h, 0) == OMEGA_OK && r == 0);
    r = R0;
    check("vcopy empty edit inside the view passes the bridge (code traps 3)", omega2_vcopy(&r, h, 4, h + 1, 0) == 3);
    r = R0;
    check("vcopy empty view inside the edit = 0", omega2_vcopy(&r, h + 2, 0, h, 8) == OMEGA_OK && r == 0);
    uint64_t *rin = (uint64_t *)(void *)h;
    check("vcopy result inside the edit refused", omega2_vcopy(rin, h + 8, 2, h, 4) == OMEGA_BAD_ARG);
    uint64_t rv[2] = {R0, R0};
    check("bsum result inside the view refused (v1 rule)", omega2_bsum(&rv[0], (const uint8_t *)rv, 16) == OMEGA_BAD_ARG);
    r = R0;
    check("vcopy short edit traps 3 after the writes it made",
          omega2_vcopy(&r, h, 4, h + 8, 2) == 3 && h[8] == 100 && h[9] == 101 && r == R0);

    /* Layout and out parameters (lay), through the generated API header and the raw symbols. */
    lay_blk c;
    memset(&c, 0, sizeof c);
    for (int i = 0; i < 8; i++)
        c.tag[i] = (uint8_t)(0xa0 + i);
    absorb(&c, abc, 3);
    absorb(&c, b64, 64);
    check("absorb twice: a = byte sum, n = 67", c.a == (uint32_t)(294 + refsum(b64, 64)) && c.n == 67);
    uint8_t o16[16];
    memset(o16, 0xee, sizeof o16);
    uint64_t n = digest(&c, o16);
    int dok = n == 67;
    for (int i = 0; i < 8; i++)
        dok &= o16[i] == 0xa0 + i;
    for (int i = 0; i < 4; i++)
        dok &= o16[8 + i] == (uint8_t)(c.a >> (8 * i)) && o16[12 + i] == 0;
    check("digest: tag, a's bytes, zeros; result n", dok);
    r = R0;
    check("absorb NULL layout refused", omega2_absorb(&r, NULL, abc, 3) == OMEGA_BAD_ARG && r == R0);
    r = R0;
    check("absorb layout overlapping the view refused",
          omega2_absorb(&r, (uint8_t *)&c, (const uint8_t *)&c + 20, 4) == OMEGA_BAD_ARG && c.n == 67);
    r = R0;
    check("digest NULL out refused", omega2_digest(&r, (const uint8_t *)&c, NULL) == OMEGA_BAD_ARG && r == R0);
    r = R0;
    check("digest out overlapping the result refused", omega2_digest(&r, (const uint8_t *)&c, (uint8_t *)&r) == OMEGA_BAD_ARG);
    /* An out may overlap a view: written after the code returns, memmove semantics. */
    uint8_t s8[8] = {1, 2, 3, 4, 5, 6, 7, 8};
    r = R0;
    s = omega2_swap8(&r, s8, 8, s8);
    check("swap8 out == view: reversed in place (memmove after return)",
          s == OMEGA_OK && r == 8 && s8[0] == 8 && s8[3] == 5 && s8[4] == 4 && s8[7] == 1);
    uint8_t s12[12] = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12};
    r = R0;
    check("swap8 out overlapping the view by 4 bytes",
          omega2_swap8(&r, s12, 12, s12 + 4) == OMEGA_OK && s12[3] == 4 && s12[4] == 8 && s12[11] == 1 && r == 12);
    lay_blk c2 = c;
    r = R0;
    check("digest out over its own layout view",
          omega2_digest(&r, (const uint8_t *)&c2, (uint8_t *)&c2) == OMEGA_OK && r == 67 && c2.tag[0] == 0xa0
              && ((uint8_t *)&c2)[0] == 0xa0 && ((uint8_t *)&c2)[8] == (uint8_t)c.a);
    /* Nothing reaches the caller's out buffer on a trap. */
    memset(o16, 0xee, sizeof o16);
    r = R0;
    check("swap8 short view traps 3, out untouched, result unchanged",
          omega2_swap8(&r, s8, 7, o16) == 3 && o16[0] == 0xee && o16[7] == 0xee && r == R0);
    uint64_t ho[2] = {11, 22};
    r = R0;
    check("halt traps 9 after writing its out buffer: caller's out untouched",
          omega2_halt(&r, ho) == 9 && ho[0] == 11 && ho[1] == 22 && r == R0);
    r = R0;
    check("halt out misaligned refused", omega2_halt(&r, (uint64_t *)(void *)(raw + 4)) == OMEGA_BAD_ARG);

    /* Two out parameters: adjacent is fine, overlapping is refused (both would be copied to the bytes). */
    uint8_t t8[8] = {0};
    r = R0;
    check("two outs adjacent accepted", omega2_two(&r, t8, t8 + 4) == OMEGA_OK && t8[0] == 1 && t8[4] == 5 && t8[7] == 8);
    memset(t8, 0, sizeof t8);
    r = R0;
    check("two outs overlapping by one byte refused", omega2_two(&r, t8, t8 + 3) == OMEGA_BAD_ARG && t8[0] == 0);
    r = R0;
    check("two outs at one address refused", omega2_two(&r, t8, t8) == OMEGA_BAD_ARG && t8[0] == 0);

    /* A unit without export: its last fn is bound. */
    uint64_t f5[5] = {0};
    fillv(f5, 5, 42);
    check("fillv (OM-2, no export) fills 5 elements", f5[0] == 42 && f5[4] == 42);

    /* Module boundary: three separately compiled OM-2 units and one OM-1 unit in one binary, calls
     * interleaved, each checked against its reference. */
    int inter = 1;
    lay_blk ci;
    memset(&ci, 0, sizeof ci);
    uint64_t f3[3], expa = 0;
    for (uint64_t k = 0; k < 2000; k++) {
        uint8_t d[5];
        for (int i = 0; i < 5; i++)
            d[i] = (uint8_t)next();
        r = R0;
        inter &= omega2_bsum(&r, d, 5) == OMEGA_OK && r == refsum(d, 5);
        absorb(&ci, d, 5);
        expa += refsum(d, 5);
        inter &= omega2_fillv(&r, f3, 3, k) == OMEGA_OK && f3[2] == k;
        r = R0;
        inter &= omega_madd(&r, k, 3, 1) == OMEGA_OK && r == 3 * k + 1;
        inter &= ci.a == (uint32_t)expa && ci.n == 5 * (k + 1);
    }
    check("2000 interleaved rounds: vec, lay, one (OM-2) and madd (OM-1)", inter);

    /* Only exports are symbols: the private helper and v1 names for v2 units do not exist. */
    void *self = dlopen(0, RTLD_NOW);
    check("no symbol for the private helper psum (omega2_psum, omega_psum)",
          !dlsym(self, "omega2_psum") && !dlsym(self, "omega_psum"));
    check("no v1 symbol for a v2 unit (omega_bsum, omega_fillv, omega_vec)",
          !dlsym(self, "omega_bsum") && !dlsym(self, "omega_fillv") && !dlsym(self, "omega_vec"));
    check("no v2 symbol for the v1 unit (omega2_madd)", !dlsym(self, "omega2_madd"));

    /* Reentry: a call from a signal handler during a call returns 33. */
    struct sigaction sa;
    memset(&sa, 0, sizeof sa);
    sa.sa_handler = on_alarm;
    sigaction(SIGALRM, &sa, 0);
    struct itimerval it = {{0, 0}, {0, 2000}};
    setitimer(ITIMER_REAL, &it, 0);
    for (int k = 0; k < 2000 && !sig_fired && lb; k++)
        omega2_bsum(&r, lb, nb);
    check("reentry from a signal handler during a v2 call returns 33", sig_fired && sig_status == OMEGA_REENTRY);

    /* Two threads, each with its own Omega stack and out buffers. */
    pthread_t t1, t2;
    uint8_t ok1 = 0, ok2 = 0;
    pthread_create(&t1, 0, swap_thread, &ok1);
    pthread_create(&t2, 0, swap_thread, &ok2);
    pthread_join(t1, 0);
    pthread_join(t2, 0);
    check("two threads x 20000 swap8 calls", ok1 && ok2);

    /* Callee-saved registers: hoist's code keeps hadd's seven loop constants in x20..x26 and inner's in x20
     * and x21, and inner's conversions write d8..d15 (with a hoisting OM-2 omc; run.sh fails unless the code
     * writes them). The caller's x19..x28 and d8..d15 survive a normal return and a trap 9 raised in inner,
     * the exported function's callee. 1920569 = 64 * 29997 + 761 (inner's result for k = 0). */
    uint64_t hd[64], pv;
    for (int i = 0; i < 64; i++)
        hd[i] = (uint64_t)i;
    r = R0;
    pv = ombr_probe((void *)omega2_hadd, &r, (uint64_t)(uintptr_t)hd, 64, 0);
    int hok = 1;
    for (int i = 0; i < 64; i++)
        hok &= hd[i] == (uint64_t)i + 70000;
    check("hoist: x19..x28 and d8..d15 kept across a normal return", (uint32_t)pv == OMEGA_OK && (pv >> 32) == 0 && r == 1920569 && hok);
    r = R0;
    pv = ombr_probe((void *)omega2_hadd, &r, (uint64_t)(uintptr_t)hd, 64, 1);
    check("hoist: x19..x28 and d8..d15 kept across a trap 9 in a callee", (uint32_t)pv == 9 && (pv >> 32) == 0 && r == R0);
    uint8_t hk1 = 0, hk2 = 0;
    pthread_create(&t1, 0, hoist_thread, &hk1);
    pthread_create(&t2, 0, hoist_thread, &hk2);
    pthread_join(t1, 0);
    pthread_join(t2, 0);
    check("two threads x 5000 hadd calls (every fifth a trap)", hk1 && hk2);

    free(lb);
    free(lw);
    printf("%s %d\n", fails ? "C-V2 FAIL" : "C-V2 PASS", fails);
    return fails != 0;
}
