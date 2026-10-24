/* ggufcmp: compare two GGUF files key by key and tensor by tensor.
 *
 * Own reader from the published GGUF facts (see st2gguf.c). Used to check a file written by
 * st2gguf against an independently produced reference: every metadata key of A must exist in
 * B with the same type and value (strings and arrays element for element), and every tensor
 * of A must exist in B with the same type, extents and identical bytes. Keys that describe
 * the producer rather than the model are reported but do not fail the comparison.
 *
 * exit 0: identical in everything that matters; 1: a difference; 2: cannot read.
 * usage: ggufcmp <a.gguf> <b.gguf>
 */
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static void die2(const char *what, const char *who) { fprintf(stderr, "ggufcmp: %s: %s\n", what, who); exit(2); }
static void *xmalloc(size_t n) { void *p = malloc(n ? n : 1); if (!p) die2("out of memory", ""); return p; }

enum { GT_U8 = 0, GT_I8, GT_U16, GT_I16, GT_U32, GT_I32, GT_F32, GT_BOOL, GT_STR, GT_ARR, GT_U64, GT_I64, GT_F64 };
static const size_t scalar_size[] = { 1, 1, 2, 2, 4, 4, 4, 1, 0, 0, 8, 8, 8 };

typedef struct {
    char *key;
    uint32_t type;        /* GT_* ; for arrays the element type is in etype */
    uint32_t etype;
    uint64_t n;           /* element count for arrays, 1 otherwise */
    uint8_t *raw;         /* scalars and arrays of scalars: packed bytes; strings: concatenated with u64 lengths */
    size_t rawlen;
} kv;

typedef struct {
    char *name;
    uint32_t ndim;
    uint64_t ne[4];
    uint32_t type;
    uint64_t offset;
} tinfo;

typedef struct {
    const char *path;
    int fd;
    uint8_t *hdr;         /* the whole header, read once */
    size_t hlen, pos;
    uint64_t n_tensors, n_kv;
    kv *kvs;
    tinfo *ts;
    uint32_t alignment;
    uint64_t data_start;
} gfile;

static void need(gfile *g, size_t n) {
    if (g->pos + n > g->hlen) {
        size_t grow = g->hlen ? g->hlen : (1u << 20);
        while (g->pos + n > g->hlen + grow) grow *= 2;
        uint8_t *nh = xmalloc(g->hlen + grow);
        if (g->hdr) memcpy(nh, g->hdr, g->hlen);
        ssize_t got = pread(g->fd, nh + g->hlen, grow, (off_t)g->hlen);
        if (got < 0 || (size_t)got < (g->pos + n - g->hlen)) die2("truncated header", g->path);
        free(g->hdr); g->hdr = nh; g->hlen += (size_t)got;
    }
}
static uint32_t ru32(gfile *g) { need(g, 4); uint32_t v; memcpy(&v, g->hdr + g->pos, 4); g->pos += 4; return v; }
static uint64_t ru64(gfile *g) { need(g, 8); uint64_t v; memcpy(&v, g->hdr + g->pos, 8); g->pos += 8; return v; }
static char *rstr(gfile *g) {
    uint64_t n = ru64(g);
    if (n > (1u << 28)) die2("string too long", g->path);
    need(g, (size_t)n);
    char *s = xmalloc((size_t)n + 1); memcpy(s, g->hdr + g->pos, (size_t)n); s[n] = 0; g->pos += (size_t)n;
    return s;
}

static void read_header(gfile *g) {
    g->fd = open(g->path, O_RDONLY);
    if (g->fd < 0) die2("cannot open", g->path);
    need(g, 4);
    if (memcmp(g->hdr, "GGUF", 4)) die2("not a GGUF file", g->path);
    g->pos = 4;
    uint32_t version = ru32(g);
    if (version != 3) die2("GGUF version is not 3", g->path);
    g->n_tensors = ru64(g);
    g->n_kv = ru64(g);
    g->kvs = xmalloc(g->n_kv * sizeof *g->kvs);
    g->alignment = 32;
    for (uint64_t i = 0; i < g->n_kv; i++) {
        kv *k = &g->kvs[i];
        k->key = rstr(g);
        k->type = ru32(g);
        k->etype = k->type; k->n = 1;
        if (k->type == GT_ARR) { k->etype = ru32(g); k->n = ru64(g); }
        if (k->etype > GT_F64) die2("unknown value type", k->key);
        if (k->etype == GT_STR) {
            size_t start = g->pos;
            for (uint64_t j = 0; j < k->n; j++) { uint64_t n = ru64(g); need(g, (size_t)n); g->pos += (size_t)n; }
            k->rawlen = g->pos - start; k->raw = g->hdr + start; /* fixed up below */
            k->raw = xmalloc(k->rawlen); memcpy(k->raw, g->hdr + start, k->rawlen);
        } else {
            k->rawlen = (size_t)(k->n * scalar_size[k->etype]);
            need(g, k->rawlen);
            k->raw = xmalloc(k->rawlen); memcpy(k->raw, g->hdr + g->pos, k->rawlen); g->pos += k->rawlen;
        }
        if (!strcmp(k->key, "general.alignment") && k->type == GT_U32) memcpy(&g->alignment, k->raw, 4);
    }
    g->ts = xmalloc(g->n_tensors * sizeof *g->ts);
    for (uint64_t i = 0; i < g->n_tensors; i++) {
        tinfo *t = &g->ts[i];
        t->name = rstr(g);
        t->ndim = ru32(g);
        if (t->ndim < 1 || t->ndim > 4) die2("tensor rank", t->name);
        for (uint32_t d = 0; d < 4; d++) t->ne[d] = 1;
        for (uint32_t d = 0; d < t->ndim; d++) t->ne[d] = ru64(g);
        t->type = ru32(g);
        t->offset = ru64(g);
    }
    g->data_start = (g->pos + g->alignment - 1) / g->alignment * g->alignment;
}

static size_t type_size(uint32_t t) {
    switch (t) { case 0: return 4; case 1: return 2; case 30: return 2; default: return 0; }
}
static uint64_t tensor_bytes(const tinfo *t) {
    size_t s = type_size(t->type);
    if (!s) return 0;
    return t->ne[0] * t->ne[1] * t->ne[2] * t->ne[3] * s;
}

static const char *informational[] = { "general.name", "general.basename", "general.size_label", "general.license",
    "general.type", "general.finetune", "general.base_model.count", "general.tags.count", "general.languages.count", NULL };
static int is_informational(const char *k) {
    for (int i = 0; informational[i]; i++) if (!strcmp(k, informational[i])) return 1;
    return !strncmp(k, "general.base_model.", 19) || !strncmp(k, "general.tags", 12) || !strncmp(k, "general.languages", 17);
}
static kv *find_kv(gfile *g, const char *key) {
    for (uint64_t i = 0; i < g->n_kv; i++) if (!strcmp(g->kvs[i].key, key)) return &g->kvs[i];
    return NULL;
}
static tinfo *find_t(gfile *g, const char *name) {
    for (uint64_t i = 0; i < g->n_tensors; i++) if (!strcmp(g->ts[i].name, name)) return &g->ts[i];
    return NULL;
}

int main(int argc, char **argv) {
    if (argc != 3) { fprintf(stderr, "usage: ggufcmp <a.gguf> <b.gguf>\n"); return 2; }
    gfile a = {0}, b = {0};
    a.path = argv[1]; b.path = argv[2];
    read_header(&a); read_header(&b);
    int bad = 0, info = 0, same_kv = 0, same_t = 0;
    for (uint64_t i = 0; i < a.n_kv; i++) {
        kv *x = &a.kvs[i], *y = find_kv(&b, x->key);
        if (!y) { printf("%s: only in A\n", x->key); if (is_informational(x->key)) info++; else bad++; continue; }
        int eq = x->type == y->type && x->etype == y->etype && x->n == y->n && x->rawlen == y->rawlen && !memcmp(x->raw, y->raw, x->rawlen);
        if (eq) { same_kv++; continue; }
        if (is_informational(x->key)) { printf("%s: differs (informational)\n", x->key); info++; continue; }
        if (x->type == GT_ARR && y->type == GT_ARR && x->etype == y->etype && x->n == y->n && x->etype != GT_STR) {
            size_t es = scalar_size[x->etype];
            for (uint64_t j = 0; j < x->n; j++) if (memcmp(x->raw + j * es, y->raw + j * es, es)) { printf("%s: element %llu differs\n", x->key, (unsigned long long)j); break; }
        } else if (x->type == GT_ARR && y->type == GT_ARR && x->etype == GT_STR && y->etype == GT_STR) {
            size_t px = 0, py = 0; uint64_t j;
            for (j = 0; j < x->n && j < y->n; j++) {
                uint64_t lx, ly; memcpy(&lx, x->raw + px, 8); memcpy(&ly, y->raw + py, 8);
                if (lx != ly || memcmp(x->raw + px + 8, y->raw + py + 8, (size_t)lx)) break;
                px += 8 + (size_t)lx; py += 8 + (size_t)ly;
            }
            printf("%s: string arrays differ (A %llu, B %llu items), first difference at %llu\n", x->key,
                   (unsigned long long)x->n, (unsigned long long)y->n, (unsigned long long)j);
        } else printf("%s: differs (type %u/%u, %llu/%llu items)\n", x->key, x->type, y->type, (unsigned long long)x->n, (unsigned long long)y->n);
        bad++;
    }
    for (uint64_t i = 0; i < b.n_kv; i++) if (!find_kv(&a, b.kvs[i].key)) { printf("%s: only in B\n", b.kvs[i].key); if (is_informational(b.kvs[i].key)) info++; else bad++; }

    const size_t BUF = 64u << 20;
    uint8_t *ba = xmalloc(BUF), *bb = xmalloc(BUF);
    uint64_t bytes_compared = 0;
    for (uint64_t i = 0; i < a.n_tensors; i++) {
        tinfo *x = &a.ts[i], *y = find_t(&b, x->name);
        if (!y) { printf("tensor %s: only in A\n", x->name); bad++; continue; }
        if (x->type != y->type || x->ndim != y->ndim || memcmp(x->ne, y->ne, sizeof x->ne)) {
            printf("tensor %s: type/shape differ (A type %u [%llu,%llu], B type %u [%llu,%llu])\n", x->name, x->type,
                   (unsigned long long)x->ne[0], (unsigned long long)x->ne[1], y->type, (unsigned long long)y->ne[0], (unsigned long long)y->ne[1]);
            bad++; continue;
        }
        uint64_t n = tensor_bytes(x);
        if (!n) { printf("tensor %s: unsupported type %u\n", x->name, x->type); bad++; continue; }
        uint64_t oa = a.data_start + x->offset, ob = b.data_start + y->offset, left = n, at = 0; int diff = 0;
        while (left) {
            size_t chunk = left < BUF ? (size_t)left : BUF;
            if (pread(a.fd, ba, chunk, (off_t)(oa + at)) != (ssize_t)chunk) die2("short read", a.path);
            if (pread(b.fd, bb, chunk, (off_t)(ob + at)) != (ssize_t)chunk) die2("short read", b.path);
            if (memcmp(ba, bb, chunk)) {
                size_t j = 0; while (j < chunk && ba[j] == bb[j]) j++;
                printf("tensor %s: bytes differ at %llu of %llu\n", x->name, (unsigned long long)(at + j), (unsigned long long)n);
                diff = 1; break;
            }
            left -= chunk; at += chunk;
        }
        bytes_compared += n - left;
        if (diff) bad++; else same_t++;
    }
    for (uint64_t i = 0; i < b.n_tensors; i++) if (!find_t(&a, b.ts[i].name)) { printf("tensor %s: only in B\n", b.ts[i].name); bad++; }
    printf("ggufcmp: %d keys identical, %d informational differences, %d tensors identical (%llu bytes), %d differences\n",
           same_kv, info, same_t, (unsigned long long)bytes_compared, bad);
    return bad ? 1 : 0;
}
