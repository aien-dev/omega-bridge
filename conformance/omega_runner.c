/* SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception */
/* Omega-side conformance runner for the frozen matmul and causal GQA contracts.
 *
 * Generates the same deterministic inputs as conformance/oracle.py (splitmix64,
 * exact multiples of 1/64 for bf16 and 1/1024 for f32), executes through the
 * existing CUDApp API, and writes raw f32 output plus run metadata. It does not
 * call the Python oracle and does not judge itself.
 *
 *   omega_runner matmul --m 4 --k 5 --n 3 --seed 680 --out PREFIX [--device]
 *   omega_runner attention --base 1 --rows 2 --hq 4 --hkv 2 --hd 128 \
 *                          --seed 2810054072 --out PREFIX [--device]
 *
 * Without --device the matmul path uses the CUDApp host oracle only to validate
 * wiring; that is NOT device evidence. Attention has no host path here and
 * exits 4 (NOT_RUN). A --device run requires SPARK_WINDOW. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#include "omega_blackwell_matmul.h"
#include "omega_gpu_attention_api.h"
#include "omega_gpu_matmul_api.h"
#include "sha256.h"

#define MASK64 ((uint64_t)-1)

static uint64_t rng_state;

static uint64_t next_u64(void) {
    rng_state += 0x9E3779B97F4A7C15ull;
    uint64_t z = rng_state;
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ull;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBull;
    return z ^ (z >> 31);
}

static float next_bf16_value(void) {
    return (float)((int64_t)(next_u64() % 511ull) - 255) / 64.0f;
}

static float next_f32_value(void) {
    return (float)((int64_t)(next_u64() % 4097ull) - 2048) / 1024.0f;
}

static double now_s(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec / 1e9;
}

static uint32_t uarg(const char *s) {
    char *e = NULL;
    unsigned long v = strtoul(s, &e, 0);
    return (e && *e == 0) ? (uint32_t)v : 0xffffffffu;
}

static int write_bin(const char *prefix, const float *x, size_t n) {
    char p[1024];
    snprintf(p, sizeof p, "%s.bin", prefix);
    FILE *f = fopen(p, "wb");
    if (!f) return -1;
    size_t wrote = fwrite(x, sizeof(float), n, f);
    return (wrote == n && fclose(f) == 0) ? 0 : -1;
}

static void hex32(const uint8_t d[32], char out[65]) {
    static const char h[] = "0123456789abcdef";
    for (int i = 0; i < 32; i++) { out[2 * i] = h[d[i] >> 4]; out[2 * i + 1] = h[d[i] & 15]; }
    out[64] = 0;
}

static int write_meta(const char *prefix, const char *runner, const char *dev, const char *win,
                      const char *shape, const char *contract, double t, const char *fields, const float *out, size_t n) {
    char p[1024], h[65];
    uint8_t d[32];
    sha256_hash((const uint8_t *)out, n * sizeof(float), d);
    hex32(d, h);
    snprintf(p, sizeof p, "%s.json", prefix);
    FILE *f = fopen(p, "wb");
    if (!f) return -1;
    fprintf(f, "{\n  \"runner\": \"%s\",\n  \"device\": \"%s\",\n  \"shape\": %s,\n"
               "  \"contract_id\": \"%s\",\n"
               "  \"seconds\": %.9f,\n  \"spark_window\": %s%s%s,\n  \"output_sha256\": \"%s\"%s\n}\n",
            runner, dev, shape, contract, t,
            win ? "\"" : "", win ? win : "null", win ? "\"" : "",
            h, fields);
    return fclose(f) == 0 ? 0 : -1;
}

int main(int argc, char **argv) {
    if (argc < 3) {
        fprintf(stderr, "usage: omega_runner matmul|attention ... --out PREFIX [--device]\n");
        return 2;
    }
    const char *op = argv[1];
    const char *out = NULL;
    int device = 0;
    uint32_t m = 0, k = 0, n = 0, base = 0, rows = 0, hq = 0, hkv = 0, hd = 0;
    uint64_t seed = 0;
    for (int i = 2; i < argc; i++) {
        if (strcmp(argv[i], "--out") == 0 && i + 1 < argc) out = argv[++i];
        else if (strcmp(argv[i], "--device") == 0) device = 1;
        else if (strcmp(argv[i], "--m") == 0 && i + 1 < argc) m = uarg(argv[++i]);
        else if (strcmp(argv[i], "--k") == 0 && i + 1 < argc) k = uarg(argv[++i]);
        else if (strcmp(argv[i], "--n") == 0 && i + 1 < argc) n = uarg(argv[++i]);
        else if (strcmp(argv[i], "--base") == 0 && i + 1 < argc) base = uarg(argv[++i]);
        else if (strcmp(argv[i], "--rows") == 0 && i + 1 < argc) rows = uarg(argv[++i]);
        else if (strcmp(argv[i], "--hq") == 0 && i + 1 < argc) hq = uarg(argv[++i]);
        else if (strcmp(argv[i], "--hkv") == 0 && i + 1 < argc) hkv = uarg(argv[++i]);
        else if (strcmp(argv[i], "--hd") == 0 && i + 1 < argc) hd = uarg(argv[++i]);
        else if (strcmp(argv[i], "--seed") == 0 && i + 1 < argc) seed = strtoull(argv[++i], NULL, 10);
        else { fprintf(stderr, "unknown argument %s\n", argv[i]); return 2; }
    }
    if (!out || m == 0xffffffffu || k == 0xffffffffu || n == 0xffffffffu) {
        fprintf(stderr, "missing --out or invalid numeric argument\n");
        return 2;
    }
    const char *win = getenv("SPARK_WINDOW");
    if (device && !win) {
        fprintf(stderr, "device run refused: SPARK_WINDOW is not set (no authorized window)\n");
        return 3;
    }
    if (strcmp(op, "matmul") == 0) {
        if (!m || !k || !n) { fprintf(stderr, "matmul needs --m --k --n\n"); return 2; }
        uint16_t *a = malloc((size_t)m * k * 2), *b = malloc((size_t)k * n * 2);
        float *c = malloc((size_t)m * n * 4);
        if (!a || !b || !c) return 4;
        rng_state = seed;
        for (size_t i = 0; i < (size_t)m * k; i++) a[i] = omega_fp32_to_bf16(next_bf16_value());
        for (size_t i = 0; i < (size_t)k * n; i++) b[i] = omega_fp32_to_bf16(next_bf16_value());
        double t0 = now_s();
        int rc;
        char fields[512] = "";
        if (device) {
            OmegaGpuMatmulInfo info;
            memset(&info, 0, sizeof info);
            rc = omega_gpu_matmul_bf16(m, k, n, a, b, c, &info);
            snprintf(fields, sizeof fields,
                     ",\n  \"omega_rc\": %d,\n  \"target_chip\": \"%s\",\n  \"sm_architecture\": %u,\n"
                     "  \"call_ns\": %llu,\n  \"parity_verified\": %s,\n  \"max_abs_err\": %.9g",
                     rc, info.target_chip, info.sm_architecture,
                     (unsigned long long)info.call_ns, info.parity_verified ? "true" : "false",
                     (double)info.max_abs_err);
            if (rc != OMEGA_GPU_MATMUL_OK) { fprintf(stderr, "matmul rc=%d\n", rc); return 5; }
        } else {
            rc = omega_matmul_cpu_oracle_bf16(a, b, c, m, k, n);
            if (rc != 0) { fprintf(stderr, "host oracle rc=%d\n", rc); return 5; }
            snprintf(fields, sizeof fields, ",\n  \"omega_rc\": %d,\n  \"host_wiring_only\": true", rc);
        }
        double t = now_s() - t0;
        if (write_bin(out, c, (size_t)m * n)) return 4;
        char shape[128];
        snprintf(shape, sizeof shape, "[%u, %u]", m, n);
        if (write_meta(out, "omega-native", device ? "gpu" : "host-wiring", win, shape, "647116fc1ba1e1394982fc8ba181ce565293f160a6b56afc0f02b2128a675704", t, fields, c, (size_t)m * n)) return 4;
        free(a); free(b); free(c);
        return 0;
    } else if (strcmp(op, "attention") == 0) {
        if (!rows || !hq || !hkv || !hd) { fprintf(stderr, "attention needs --rows --hq --hkv --hd\n"); return 2; }
        if (!device) { fprintf(stderr, "attention host path NOT_RUN\n"); return 4; }
        uint32_t t = base + rows;
        float *q = malloc((size_t)rows * hq * hd * 4);
        float *kk = malloc((size_t)t * hkv * hd * 4);
        float *vv = malloc((size_t)t * hkv * hd * 4);
        float *o = malloc((size_t)rows * hq * hd * 4);
        if (!q || !kk || !vv || !o) return 4;
        rng_state = seed;
        for (size_t i = 0; i < (size_t)rows * hq * hd; i++) q[i] = next_f32_value();
        for (size_t i = 0; i < (size_t)t * hkv * hd; i++) kk[i] = next_f32_value();
        for (size_t i = 0; i < (size_t)t * hkv * hd; i++) vv[i] = next_f32_value();
        double t0 = now_s();
        OmegaGpuAttnInfo info;
        memset(&info, 0, sizeof info);
        int rc = omega_gpu_gqa_attention_rows_f32(q, kk, vv, base, rows, hq, hkv, hd, o, &info);
        double secs = now_s() - t0;
        if (rc != OMEGA_GPU_ATTN_OK) { fprintf(stderr, "attention rc=%d\n", rc); return 5; }
        char fields[512];
        snprintf(fields, sizeof fields,
                 ",\n  \"omega_rc\": %d,\n  \"target_chip\": \"%s\",\n  \"sm_architecture\": %u,\n"
                 "  \"call_ns\": %llu,\n  \"gpr_count\": %u,\n  \"insn_count\": %u",
                 rc, info.target_chip, info.sm_architecture, (unsigned long long)info.call_ns,
                 info.gpr_count, info.insn_count);
        if (write_bin(out, o, (size_t)rows * hq * hd)) return 4;
        char shape[128];
        snprintf(shape, sizeof shape, "[%u, %u, %u]", rows, hq, hd);
        if (write_meta(out, "omega-native", "gpu", win, shape, "003696e422bba7274877ba9e01a61076ea0f862f32760cbaa06c60f85a115359", secs, fields, o, (size_t)rows * hq * hd)) return 4;
        free(q); free(kk); free(vv); free(o);
        return 0;
    }
    fprintf(stderr, "unknown op %s\n", op);
    return 2;
}
