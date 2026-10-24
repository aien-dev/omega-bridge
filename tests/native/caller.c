/* C caller for the omega-bridge native call ABI v1 test library (libomega_native.so).
 * Expected values come from aien-calc / Wolfram receipts listed in docs/NATIVE-ABI.md, never from Omega. */
#include <inttypes.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <sys/time.h>

uint32_t omega_madd(uint64_t *result, uint64_t a, uint64_t b, uint64_t c);
uint32_t omega_smadd(uint64_t *result, uint64_t a, uint64_t b, uint64_t c);
uint32_t omega_fill(uint64_t *result, void *buf, uint64_t buf_len, uint64_t k);
uint32_t omega_spin(uint64_t *result, uint64_t n);

#define SENTINEL UINT64_C(6148914691236517205)
static int fails;
static void check(const char *name, int ok)
{
    printf("%s %s\n", ok ? "PASS" : "FAIL", name);
    if (!ok)
        fails++;
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
