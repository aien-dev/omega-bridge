/* Native ABI v2 caller cost (tests/native/v2/run.sh measure): what a C caller pays per call, split into
 * the argument checks, the entry (callee-saved registers, stack switch, runtime table), the out-buffer
 * copies and the Omega code itself, for a small and a large view. Each figure is the lowest of 7 runs of
 * N calls (ns per call, CLOCK_MONOTONIC). The code is what OMEGA_NATIVE_OMC2 compiled from vec.om, lay.om
 * and madd.om. HOST evidence. */
#define _GNU_SOURCE
#include "omega_native.h"
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

static double now(void)
{
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec * 1e9 + t.tv_nsec;
}

static const uint8_t *g_d;
static uint64_t g_n;
static volatile uint64_t sink;

__attribute__((noinline)) static uint64_t c_sum(const uint8_t *d, uint64_t n)
{
    uint64_t s = 0;
    for (uint64_t i = 0; i < n; i++) {
        s += d[i];
        __asm__ volatile("" : "+r"(s)); /* keep the loop scalar, as the Omega code is */
    }
    return s;
}
__attribute__((noinline)) static uint64_t c_empty(const uint8_t *d, uint64_t n)
{
    __asm__ volatile("" ::"r"(d), "r"(n));
    return n;
}

typedef void (*op)(void);
static uint64_t r;
static uint8_t o8[8];
static const uint8_t d8[8] = {1, 2, 3, 4, 5, 6, 7, 8};
static void m_refuse(void) { sink = omega2_bsum(&r, NULL, 1); }
static void m_empty(void) { sink = omega2_bsum(&r, g_d, 0); }
static void m_vlen(void) { sink = omega2_vlen(&r, (const uint64_t *)(const void *)g_d, 1); }
static void m_v1(void) { sink = omega_madd(&r, 3, 5, 7); }
static void m_bsum(void) { sink = omega2_bsum(&r, g_d, g_n); }
static void m_swap8(void) { sink = omega2_swap8(&r, d8, 8, o8); }
static void m_cempty(void) { sink = c_empty(g_d, g_n); }
static void m_csum(void) { sink = c_sum(g_d, g_n); }

static double best(op f, long n)
{
    double b = 1e300;
    for (int k = 0; k < 7; k++) {
        double t0 = now();
        for (long i = 0; i < n; i++)
            f();
        double t = (now() - t0) / n;
        if (t < b)
            b = t;
    }
    return b;
}

static long rss_kib(void)
{
    long pages = 0, res = 0;
    FILE *f = fopen("/proc/self/statm", "r");
    if (f) {
        if (fscanf(f, "%ld %ld", &pages, &res) != 2)
            res = 0;
        fclose(f);
    }
    return res * (sysconf(_SC_PAGESIZE) / 1024);
}

static double first_ns, second_ns;
static long rss_before, rss_after;
static void *fresh(void *a)
{
    (void)a;
    rss_before = rss_kib();
    double t0 = now();
    omega2_vlen(&r, (const uint64_t *)(const void *)g_d, 1);
    double t1 = now();
    omega2_vlen(&r, (const uint64_t *)(const void *)g_d, 1);
    double t2 = now();
    rss_after = rss_kib();
    first_ns = t1 - t0;
    second_ns = t2 - t1;
    return 0;
}

int main(void)
{
    uint64_t big = 16777216;
    uint8_t *d = malloc(big);
    for (uint64_t i = 0; i < big; i++)
        d[i] = (uint8_t)(i * 2654435761u >> 24);
    g_d = d;
    m_vlen(); /* map this thread's Omega stack before timing */
    printf("MEASURE refused-call (checks only, no entry) %.1f ns\n", best(m_refuse, 2000000));
    printf("MEASURE empty-view-call (checks + entry + stack switch, 0 elements) %.1f ns\n", best(m_empty, 2000000));
    printf("MEASURE vlen-call (one view, code returns its len) %.1f ns\n", best(m_vlen, 2000000));
    printf("MEASURE v1-madd-call (ABI v1 baseline, three scalars) %.1f ns\n", best(m_v1, 2000000));
    printf("MEASURE swap8-call (view + 8-byte out: zero, code, memmove) %.1f ns\n", best(m_swap8, 2000000));
    g_n = 0;
    printf("MEASURE c-direct-call (a plain noinline C call, for scale) %.1f ns\n", best(m_cempty, 2000000));
    g_n = 16;
    double sb = best(m_bsum, 1000000), sc = best(m_csum, 1000000);
    printf("MEASURE small-view bsum 16 B: omega %.1f ns, scalar C loop %.1f ns\n", sb, sc);
    g_n = 4096;
    sb = best(m_bsum, 20000), sc = best(m_csum, 20000);
    printf("MEASURE view bsum 4 KiB: omega %.1f ns (%.3f ns/B), scalar C loop %.1f ns (%.3f ns/B)\n", sb, sb / 4096, sc,
           sc / 4096);
    g_n = big;
    sb = best(m_bsum, 5), sc = best(m_csum, 5);
    printf("MEASURE large-view bsum 16 MiB: omega %.0f ns (%.3f ns/B), scalar C loop %.0f ns (%.3f ns/B)\n", sb, sb / big,
           sc, sc / big);
    pthread_t t;
    pthread_create(&t, 0, fresh, 0);
    pthread_join(t, 0);
    printf("MEASURE first call on a new thread (maps 8 MiB stack + 8 MiB guard) %.0f ns, second %.0f ns\n", first_ns,
           second_ns);
    printf("MEASURE RSS around a new thread's first two calls: %ld KiB -> %ld KiB\n", rss_before, rss_after);
    free(d);
    return 0;
}
