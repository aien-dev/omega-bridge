/* C caller for the omega-bridge native call ABI v1 test library (libomega_native.so).
 * Expected values come from aien-calc / Wolfram receipts listed in docs/NATIVE-ABI.md, never from Omega. */
#include <inttypes.h>
#include <pthread.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <sys/time.h>

uint32_t omega_madd(uint64_t *result, uint64_t a, uint64_t b, uint64_t c);
uint32_t omega_smadd(uint64_t *result, uint64_t a, uint64_t b, uint64_t c);
uint32_t omega_fill(uint64_t *result, void *buf, uint64_t buf_len, uint64_t k);
uint32_t omega_spin(uint64_t *result, uint64_t n);
uint32_t omega_mix(uint64_t *result, uint64_t a, uint64_t b, const void *c, uint64_t c_len, void *d, uint64_t d_len,
                   const void *e, uint64_t e_len, uint64_t f);
uint32_t omega_big(uint64_t *result, uint64_t n);

#define SENTINEL UINT64_C(6148914691236517205)
static int fails;
static void check(const char *name, int ok)
{
    printf("%s %s\n", ok ? "PASS" : "FAIL", name);
    if (!ok)
        fails++;
}

/* ombr_probe(fn, result, a, b, c): set x19..x28 and d8..d15 to known values, call fn(result, a, b, c),
 * then return the status in the low 32 bits and the number of changed registers in the high 32 bits. */
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

static void *big_thread(void *p)
{
    uint64_t *r = p;
    r[1] = omega_big(&r[0], 7);
    return NULL;
}

static volatile uint32_t inner_status = 99;
static void on_alarm(int sig)
{
    uint64_t r = SENTINEL;
    (void)sig;
    inner_status = omega_madd(&r, 3, 5, 7);
}

int main(void)
{
    uint64_t r;
    r = 0;
    check("madd 3*5+7 = 22", omega_madd(&r, 3, 5, 7) == 0 && r == 22);
    r = 0;
    check("madd wraps: (2^64-1)*2+5 = 3", omega_madd(&r, UINT64_MAX, 2, 5) == 0 && r == 3);
    r = 0;
    check("madd large = 3637949782307626511",
          omega_madd(&r, UINT64_C(1311768467463790320), UINT64_C(18364758544493064720), UINT64_C(1085102592571150095)) == 0 &&
              r == UINT64_C(3637949782307626511));
    r = 0;
    check("madd signed bits: -3*5+2 = -13", omega_madd(&r, (uint64_t)(int64_t)-3, 5, 2) == 0 && (int64_t)r == -13 &&
                                                 r == UINT64_C(18446744073709551603));
    r = 0;
    check("smadd -3*5+2 = -13", omega_smadd(&r, (uint64_t)(int64_t)-3, 5, 2) == 0 && (int64_t)r == -13);
    r = SENTINEL;
    check("smadd 2^62*4 traps 1, result unchanged",
          omega_smadd(&r, UINT64_C(4611686018427387904), 4, 0) == 1 && r == SENTINEL);
    uint64_t buf[5] = {0, 0, 0, 0, 0};
    r = SENTINEL;
    check("fill k=1 traps 3, result unchanged", omega_fill(&r, buf, 4, 1) == 3 && r == SENTINEL);
    check("fill k=1 writes before the trap stay visible", buf[0] == 11 && buf[1] == 22 && buf[2] == 0 && buf[3] == 0);
    memset(buf, 0, sizeof buf);
    r = 0;
    check("fill k=0 returns 3, writes 11 22 33", omega_fill(&r, buf, 4, 0) == 0 && r == 3 && buf[0] == 11 && buf[1] == 22 &&
                                                   buf[2] == 33 && buf[3] == 0 && buf[4] == 0);
    check("null result refused 32", omega_madd(NULL, 3, 5, 7) == 32);
    r = SENTINEL;
    check("null buffer refused 32, result unchanged", omega_fill(&r, NULL, 4, 0) == 32 && r == SENTINEL);
    check("buffer length 3 refused 32", omega_fill(&r, buf, 3, 0) == 32 && r == SENTINEL);
    check("misaligned buffer refused 32", omega_fill(&r, (char *)buf + 1, 4, 0) == 32 && r == SENTINEL);
    memset(buf, 0, sizeof buf);
    check("result inside buffer refused 32, buffer untouched",
          omega_fill(&buf[1], buf, 4, 0) == 32 && buf[0] == 0 && buf[1] == 0 && buf[2] == 0);
    r = 0;
    check("call after traps still works", omega_madd(&r, 3, 5, 7) == 0 && r == 22);


    /* mix: six parameters (ulong, long, view uchar 3, edit uchar 2, view ulong 2, ulong), no result.
     * 5 + 20 + 7 = 32 (calc:08302bc4); 5 + 20 + 300 is 70 over 255 (calc:a6a8bb76), so the conversion traps 5. */
    const unsigned char cb[3] = {1, 2, 3};
    unsigned char db[2] = {0, 0};
    const uint64_t eb[2] = {10, 20};
    r = SENTINEL;
    check("mix six parameters, void result writes 0", omega_mix(&r, 5, 1, cb, 3, db, 2, eb, 2, 7) == 0 && r == 0 &&
                                                         db[0] == 3 && db[1] == 32);
    db[0] = db[1] = 0;
    r = SENTINEL;
    check("mix negative long traps 9 after both writes, result unchanged",
          omega_mix(&r, 5, (uint64_t)(int64_t)-1, cb, 3, db, 2, eb, 2, 7) == 9 && r == SENTINEL && db[0] == 3 && db[1] == 32);
    db[0] = db[1] = 0;
    check("mix uchar conversion 325 traps 5, first write visible",
          omega_mix(&r, 5, 1, cb, 3, db, 2, eb, 2, 300) == 5 && r == SENTINEL && db[0] == 3 && db[1] == 0);
    unsigned char ov[3] = {0, 0, 0};
    check("mix view overlapping the edit array refused 32, nothing written",
          omega_mix(&r, 5, 1, ov, 3, ov + 1, 2, eb, 2, 7) == 32 && ov[1] == 0 && ov[2] == 0);

    /* big: a 4,000,000-byte local array (0.954 of Omega's 4 MiB cap, calc:ffff21b2); (7 + 1) + 7 = 15 (calc:e44bce3f). */
    r = 0;
    check("big local array on the main thread = 15", omega_big(&r, 7) == 0 && r == 15);
    r = SENTINEL;
    check("big traps 3 from a frame holding a local array, result unchanged", omega_big(&r, 0) == 3 && r == SENTINEL);
    uint64_t tr[2] = {0, 99};
    pthread_attr_t at;
    pthread_t th;
    pthread_attr_init(&at);
    pthread_attr_setstacksize(&at, 256 * 1024);
    int made = pthread_create(&th, &at, big_thread, tr) == 0;
    if (made)
        pthread_join(th, NULL);
    check("big on a 256 KiB thread runs on the binding's stack = 15", made && tr[1] == 0 && tr[0] == 15);

    /* The caller's callee-saved registers survive a normal return and a trap. */
    uint64_t pv = ombr_probe((void *)omega_madd, &r, 3, 5, 7);
    check("x19..x28 and d8..d15 kept across a normal return", (uint32_t)pv == 0 && (pv >> 32) == 0 && r == 22);
    r = SENTINEL;
    pv = ombr_probe((void *)omega_smadd, &r, UINT64_C(4611686018427387904), 4, 0);
    check("x19..x28 and d8..d15 kept across a trap", (uint32_t)pv == 1 && (pv >> 32) == 0 && r == SENTINEL);

    struct sigaction sa;
    memset(&sa, 0, sizeof sa);
    sa.sa_handler = on_alarm;
    sigaction(SIGALRM, &sa, NULL);
    struct itimerval it = {{0, 0}, {0, 50}};
    int entered = 0;
    for (int tries = 0; tries < 200 && inner_status != 33; tries++) {
        inner_status = 99;
        setitimer(ITIMER_REAL, &it, NULL);
        r = 0;
        uint32_t s = omega_spin(&r, 1000000);
        struct itimerval off = {{0, 0}, {0, 0}};
        setitimer(ITIMER_REAL, &off, NULL);
        if (s != 0 || r != UINT64_C(499999500000)) {
            check("spin result", 0);
            break;
        }
        entered = 1;
    }
    check("reentry from a signal handler during a call refused 33", entered && inner_status == 33);
    printf("%s %d failure(s)\n", fails ? "FAIL" : "PASS", fails);
    return fails != 0;
}
