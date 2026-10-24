/* st2gguf: write a GGUF model file from a bf16 safetensors checkpoint.
 *
 * Own implementation from the published format facts (GGUF: magic "GGUF", version 3,
 * 32-byte data alignment, little-endian fields; safetensors: 8-byte header length,
 * JSON header, raw tensor bytes). Nothing is copied from any outside converter.
 *
 * Scope (bridge-strict-v1 freeze, Bridge #10 / CUDApp #75): dense Qwen3 checkpoints
 * stored entirely in bf16. 2-D weights are copied byte for byte (bf16 -> GGML BF16).
 * 1-D norm vectors are widened exactly to f32 (bf16 is the top half of an f32).
 * Tied embeddings: no output.weight is written; the loader reuses token_embd.
 *
 * This is translation glue (format in, format out), no model computation. It moves to
 * Omega (.om) once the seed's host file words land (omega-mv PR #678).
 *
 * usage: st2gguf <checkpoint dir> <out.gguf>
 */
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static void die(const char *what) { fprintf(stderr, "st2gguf: %s\n", what); exit(2); }
static void die2(const char *what, const char *who) { fprintf(stderr, "st2gguf: %s: %s\n", what, who); exit(2); }
static void *xmalloc(size_t n) { void *p = malloc(n ? n : 1); if (!p) die("out of memory"); return p; }
static void *xrealloc(void *p, size_t n) { p = realloc(p, n ? n : 1); if (!p) die("out of memory"); return p; }

/* ---- whole-file read ---- */
static char *read_file(const char *path, size_t *len) {
    FILE *f = fopen(path, "rb");
    if (!f) die2("cannot open", path);
    if (fseek(f, 0, SEEK_END)) die2("seek", path);
    long n = ftell(f);
    if (n < 0) die2("tell", path);
    rewind(f);
    char *buf = xmalloc((size_t)n + 1);
    if (fread(buf, 1, (size_t)n, f) != (size_t)n) die2("short read", path);
    fclose(f);
    buf[n] = 0;
    if (len) *len = (size_t)n;
    return buf;
}

/* ---- minimal JSON document model ---- */
enum jtype { J_NULL, J_BOOL, J_NUM, J_STR, J_ARR, J_OBJ };
typedef struct jval jval;
struct jval {
    enum jtype t;
    int b;
    double num;
    char *str;            /* J_STR: UTF-8, NUL-terminated (also knows its length) */
    size_t slen;
    jval **items;         /* J_ARR: items; J_OBJ: values */
    char **keys;          /* J_OBJ: keys */
    size_t n;
};

typedef struct { const char *s; const char *end; const char *start; const char *name; } jparser;

static void jfail(jparser *p, const char *msg) {
    fprintf(stderr, "st2gguf: %s: bad JSON at byte %ld: %s\n", p->name, (long)(p->s - p->start), msg);
    exit(2);
}
static void jws(jparser *p) { while (p->s < p->end && (*p->s == ' ' || *p->s == '\n' || *p->s == '\r' || *p->s == '\t')) p->s++; }
static jval *jnew(enum jtype t) { jval *v = xmalloc(sizeof *v); memset(v, 0, sizeof *v); v->t = t; return v; }

static void put_utf8(char **out, size_t *len, size_t *cap, uint32_t cp) {
    if (*len + 4 >= *cap) { *cap = *cap * 2 + 16; *out = xrealloc(*out, *cap); }
    char *o = *out + *len;
    if (cp < 0x80) { o[0] = (char)cp; *len += 1; }
    else if (cp < 0x800) { o[0] = (char)(0xC0 | (cp >> 6)); o[1] = (char)(0x80 | (cp & 0x3F)); *len += 2; }
    else if (cp < 0x10000) { o[0] = (char)(0xE0 | (cp >> 12)); o[1] = (char)(0x80 | ((cp >> 6) & 0x3F)); o[2] = (char)(0x80 | (cp & 0x3F)); *len += 3; }
    else { o[0] = (char)(0xF0 | (cp >> 18)); o[1] = (char)(0x80 | ((cp >> 12) & 0x3F)); o[2] = (char)(0x80 | ((cp >> 6) & 0x3F)); o[3] = (char)(0x80 | (cp & 0x3F)); *len += 4; }
}
static uint32_t hex4(jparser *p) {
    if (p->end - p->s < 4) jfail(p, "short \\u escape");
    uint32_t v = 0;
    for (int i = 0; i < 4; i++) {
        char c = p->s[i]; v <<= 4;
        if (c >= '0' && c <= '9') v |= (uint32_t)(c - '0');
        else if (c >= 'a' && c <= 'f') v |= (uint32_t)(c - 'a' + 10);
        else if (c >= 'A' && c <= 'F') v |= (uint32_t)(c - 'A' + 10);
        else jfail(p, "bad hex in \\u escape");
    }
    p->s += 4;
    return v;
}
static char *jstring(jparser *p, size_t *outlen) {
    if (*p->s != '"') jfail(p, "expected string");
    p->s++;
    size_t len = 0, cap = 32;
    char *out = xmalloc(cap);
    while (p->s < p->end && *p->s != '"') {
        unsigned char c = (unsigned char)*p->s++;
        if (c == '\\') {
            if (p->s >= p->end) jfail(p, "truncated escape");
            char e = *p->s++;
            switch (e) {
            case '"': put_utf8(&out, &len, &cap, '"'); break;
            case '\\': put_utf8(&out, &len, &cap, '\\'); break;
            case '/': put_utf8(&out, &len, &cap, '/'); break;
            case 'b': put_utf8(&out, &len, &cap, '\b'); break;
            case 'f': put_utf8(&out, &len, &cap, '\f'); break;
            case 'n': put_utf8(&out, &len, &cap, '\n'); break;
            case 'r': put_utf8(&out, &len, &cap, '\r'); break;
            case 't': put_utf8(&out, &len, &cap, '\t'); break;
            case 'u': {
                uint32_t cp = hex4(p);
                if (cp >= 0xD800 && cp <= 0xDBFF) {
                    if (p->end - p->s < 6 || p->s[0] != '\\' || p->s[1] != 'u') jfail(p, "lone high surrogate");
                    p->s += 2;
                    uint32_t lo = hex4(p);
                    if (lo < 0xDC00 || lo > 0xDFFF) jfail(p, "bad low surrogate");
                    cp = 0x10000 + ((cp - 0xD800) << 10) + (lo - 0xDC00);
                }
                put_utf8(&out, &len, &cap, cp);
                break;
            }
            default: jfail(p, "unknown escape");
            }
        } else {
            if (len + 1 >= cap) { cap = cap * 2 + 16; out = xrealloc(out, cap); }
            out[len++] = (char)c;
        }
    }
    if (p->s >= p->end) jfail(p, "unterminated string");
    p->s++;
    out = xrealloc(out, len + 1);
    out[len] = 0;
    if (outlen) *outlen = len;
    return out;
}
static jval *jparse(jparser *p);
static jval *jparse(jparser *p) {
    jws(p);
    if (p->s >= p->end) jfail(p, "unexpected end");
    char c = *p->s;
    if (c == '{') {
        jval *v = jnew(J_OBJ); size_t cap = 0;
        p->s++; jws(p);
        if (*p->s == '}') { p->s++; return v; }
        for (;;) {
            jws(p);
            char *k = jstring(p, NULL);
            jws(p);
            if (*p->s != ':') jfail(p, "expected ':'");
            p->s++;
            jval *item = jparse(p);
            if (v->n == cap) { cap = cap * 2 + 8; v->keys = xrealloc(v->keys, cap * sizeof *v->keys); v->items = xrealloc(v->items, cap * sizeof *v->items); }
            v->keys[v->n] = k; v->items[v->n] = item; v->n++;
            jws(p);
            if (*p->s == ',') { p->s++; continue; }
            if (*p->s == '}') { p->s++; return v; }
            jfail(p, "expected ',' or '}'");
        }
    }
    if (c == '[') {
        jval *v = jnew(J_ARR); size_t cap = 0;
        p->s++; jws(p);
        if (*p->s == ']') { p->s++; return v; }
        for (;;) {
            jval *item = jparse(p);
            if (v->n == cap) { cap = cap * 2 + 8; v->items = xrealloc(v->items, cap * sizeof *v->items); }
            v->items[v->n++] = item;
            jws(p);
            if (*p->s == ',') { p->s++; continue; }
            if (*p->s == ']') { p->s++; return v; }
            jfail(p, "expected ',' or ']'");
        }
    }
    if (c == '"') { jval *v = jnew(J_STR); v->str = jstring(p, &v->slen); return v; }
    if (!strncmp(p->s, "true", 4)) { p->s += 4; jval *v = jnew(J_BOOL); v->b = 1; return v; }
    if (!strncmp(p->s, "false", 5)) { p->s += 5; jval *v = jnew(J_BOOL); v->b = 0; return v; }
    if (!strncmp(p->s, "null", 4)) { p->s += 4; return jnew(J_NULL); }
    if (c == '-' || (c >= '0' && c <= '9')) {
        char *endp; double d = strtod(p->s, &endp);
        if (endp == p->s) jfail(p, "bad number");
        p->s = endp; jval *v = jnew(J_NUM); v->num = d; return v;
    }
    jfail(p, "unexpected character");
    return NULL;
}
static jval *jparse_text(const char *text, size_t len, const char *name) {
    jparser p = { text, text + len, text, name };
    jval *v = jparse(&p);
    jws(&p);
    if (p.s != p.end) jfail(&p, "trailing bytes");
    return v;
}
static jval *jget(jval *o, const char *key) {
    if (!o || o->t != J_OBJ) return NULL;
    for (size_t i = 0; i < o->n; i++) if (!strcmp(o->keys[i], key)) return o->items[i];
    return NULL;
}
static double jnum(jval *o, const char *key) {
    jval *v = jget(o, key);
    if (!v || v->t != J_NUM) die2("missing number", key);
    return v->num;
}
static const char *jstr(jval *o, const char *key) {
    jval *v = jget(o, key);
    if (!v || v->t != J_STR) die2("missing string", key);
    return v->str;
}

/* ---- GGUF writer ---- */
enum { GT_U8 = 0, GT_I8, GT_U16, GT_I16, GT_U32, GT_I32, GT_F32, GT_BOOL, GT_STR, GT_ARR, GT_U64, GT_I64, GT_F64 };
enum { GGML_F32 = 0, GGML_BF16 = 30 };
#define ALIGN 32u

typedef struct { FILE *f; uint64_t pos; } gw;
static void wbytes(gw *w, const void *p, size_t n) { if (fwrite(p, 1, n, w->f) != n) die("write failed"); w->pos += n; }
static void wu8(gw *w, uint8_t v) { wbytes(w, &v, 1); }
static void wu32(gw *w, uint32_t v) { wbytes(w, &v, 4); }
static void wi32(gw *w, int32_t v) { wbytes(w, &v, 4); }
static void wu64(gw *w, uint64_t v) { wbytes(w, &v, 8); }
static void wf32(gw *w, float v) { wbytes(w, &v, 4); }
static void wstrn(gw *w, const char *s, size_t n) { wu64(w, n); wbytes(w, s, n); }
static void wstr(gw *w, const char *s) { wstrn(w, s, strlen(s)); }

static void kv_str(gw *w, const char *k, const char *v) { wstr(w, k); wu32(w, GT_STR); wstr(w, v); }
static void kv_u32(gw *w, const char *k, uint32_t v) { wstr(w, k); wu32(w, GT_U32); wu32(w, v); }
static void kv_f32(gw *w, const char *k, float v) { wstr(w, k); wu32(w, GT_F32); wf32(w, v); }
static void kv_bool(gw *w, const char *k, int v) { wstr(w, k); wu32(w, GT_BOOL); wu8(w, v ? 1 : 0); }

/* ---- the tensors ---- */
typedef struct {
    char gname[64];        /* GGUF tensor name */
    const char *hname;     /* checkpoint name */
    int file;              /* which safetensors file */
    uint64_t begin, end;   /* byte range of the bf16 data inside that file's data block */
    uint32_t ndim;
    uint64_t ne[2];        /* ggml order: ne[0] innermost */
    uint32_t type;
    uint64_t nbytes;       /* bytes as written to GGUF */
    uint64_t offset;       /* offset from the data start */
} tensor;

static const struct { const char *hf; const char *gg; } layer_map[] = {
    { "input_layernorm.weight",          "attn_norm.weight" },
    { "self_attn.q_proj.weight",         "attn_q.weight" },
    { "self_attn.k_proj.weight",         "attn_k.weight" },
    { "self_attn.v_proj.weight",         "attn_v.weight" },
    { "self_attn.o_proj.weight",         "attn_output.weight" },
    { "self_attn.q_norm.weight",         "attn_q_norm.weight" },
    { "self_attn.k_norm.weight",         "attn_k_norm.weight" },
    { "post_attention_layernorm.weight", "ffn_norm.weight" },
    { "mlp.gate_proj.weight",            "ffn_gate.weight" },
    { "mlp.up_proj.weight",              "ffn_up.weight" },
    { "mlp.down_proj.weight",            "ffn_down.weight" },
};
#define NLAYER_MAP (sizeof layer_map / sizeof layer_map[0])

/* HF name -> GGUF name; 0 when the tensor is not part of the profile */
static int map_name(const char *h, char *out, size_t outn) {
    if (!strcmp(h, "model.embed_tokens.weight")) { snprintf(out, outn, "token_embd.weight"); return 1; }
    if (!strcmp(h, "model.norm.weight")) { snprintf(out, outn, "output_norm.weight"); return 1; }
    if (!strcmp(h, "lm_head.weight")) { snprintf(out, outn, "output.weight"); return 1; }
    if (strncmp(h, "model.layers.", 13)) return 0;
    const char *p = h + 13; char *endp;
    long il = strtol(p, &endp, 10);
    if (endp == p || *endp != '.' || il < 0) return 0;
    const char *rest = endp + 1;
    for (size_t i = 0; i < NLAYER_MAP; i++)
        if (!strcmp(rest, layer_map[i].hf)) { snprintf(out, outn, "blk.%ld.%s", il, layer_map[i].gg); return 1; }
    return 0;
}

static int cmp_tensor(const void *a, const void *b) {
    const tensor *x = a, *y = b;
    /* token_embd first, output_norm last, layers in numeric order with the map's field order */
    int xk = !strncmp(x->gname, "blk.", 4) ? 1 : (!strcmp(x->gname, "token_embd.weight") ? 0 : 2);
    int yk = !strncmp(y->gname, "blk.", 4) ? 1 : (!strcmp(y->gname, "token_embd.weight") ? 0 : 2);
    if (xk != yk) return xk - yk;
    if (xk != 1) return strcmp(x->gname, y->gname);
    long lx = strtol(x->gname + 4, NULL, 10), ly = strtol(y->gname + 4, NULL, 10);
    if (lx != ly) return lx < ly ? -1 : 1;
    const char *fx = strchr(x->gname + 4, '.') + 1, *fy = strchr(y->gname + 4, '.') + 1;
    size_t ix = NLAYER_MAP, iy = NLAYER_MAP;
    for (size_t i = 0; i < NLAYER_MAP; i++) { if (!strcmp(fx, layer_map[i].gg)) ix = i; if (!strcmp(fy, layer_map[i].gg)) iy = i; }
    return (int)ix - (int)iy;
}

static char *path_join(const char *dir, const char *name) {
    size_t n = strlen(dir) + strlen(name) + 2;
    char *p = xmalloc(n);
    snprintf(p, n, "%s/%s", dir, name);
    return p;
}

int main(int argc, char **argv) {
    if (argc != 3) { fprintf(stderr, "usage: st2gguf <checkpoint dir> <out.gguf>\n"); return 2; }
    const char *dir = argv[1], *outpath = argv[2];

    /* config */
    size_t n;
    char *t = read_file(path_join(dir, "config.json"), &n);
    jval *cfg = jparse_text(t, n, "config.json");
    jval *archs = jget(cfg, "architectures");
    if (!archs || archs->t != J_ARR || archs->n != 1 || strcmp(archs->items[0]->str, "Qwen3ForCausalLM"))
        die("profile covers Qwen3ForCausalLM only");
    uint32_t n_embd = (uint32_t)jnum(cfg, "hidden_size");
    uint32_t n_layer = (uint32_t)jnum(cfg, "num_hidden_layers");
    uint32_t n_head = (uint32_t)jnum(cfg, "num_attention_heads");
    uint32_t n_head_kv = (uint32_t)jnum(cfg, "num_key_value_heads");
    uint32_t head_dim = (uint32_t)jnum(cfg, "head_dim");
    uint32_t n_ff = (uint32_t)jnum(cfg, "intermediate_size");
    uint32_t n_ctx = (uint32_t)jnum(cfg, "max_position_embeddings");
    uint32_t n_vocab = (uint32_t)jnum(cfg, "vocab_size");
    float rms_eps = (float)jnum(cfg, "rms_norm_eps");
    float rope_theta = (float)jnum(cfg, "rope_theta");
    uint32_t bos_id = (uint32_t)jnum(cfg, "bos_token_id");
    uint32_t eos_id = (uint32_t)jnum(cfg, "eos_token_id");
    jval *tie = jget(cfg, "tie_word_embeddings");
    int tied = tie && tie->t == J_BOOL && tie->b;
    jval *abias = jget(cfg, "attention_bias");
    if (abias && abias->t == J_BOOL && abias->b) die("attention_bias true is outside the profile");
    jval *rs = jget(cfg, "rope_scaling");
    if (rs && rs->t != J_NULL) die("rope_scaling is outside the profile");

    /* tokenizer */
    t = read_file(path_join(dir, "tokenizer.json"), &n);
    jval *tok = jparse_text(t, n, "tokenizer.json");
    jval *model = jget(tok, "model");
    if (!model || strcmp(jstr(model, "type"), "BPE")) die("tokenizer model is not BPE");
    jval *vocab = jget(model, "vocab");
    jval *merges = jget(model, "merges");
    jval *added = jget(tok, "added_tokens");
    if (!vocab || vocab->t != J_OBJ || !merges || merges->t != J_ARR || !added || added->t != J_ARR) die("tokenizer.json shape");
    char **tokens = xmalloc(n_vocab * sizeof *tokens);
    size_t *toklen = xmalloc(n_vocab * sizeof *toklen);
    int32_t *toktype = xmalloc(n_vocab * sizeof *toktype);
    for (uint32_t i = 0; i < n_vocab; i++) { tokens[i] = NULL; toklen[i] = 0; toktype[i] = 5; /* UNUSED */ }
    for (size_t i = 0; i < vocab->n; i++) {
        jval *idv = vocab->items[i];
        if (idv->t != J_NUM || idv->num < 0 || idv->num >= n_vocab) die("vocab id out of range");
        uint32_t id = (uint32_t)idv->num;
        if (tokens[id]) die("duplicate vocab id");
        tokens[id] = vocab->keys[i]; toklen[id] = strlen(vocab->keys[i]); toktype[id] = 1; /* NORMAL */
    }
    for (size_t i = 0; i < added->n; i++) {
        jval *a = added->items[i];
        uint32_t id = (uint32_t)jnum(a, "id");
        if (id >= n_vocab) die("added token id out of range");
        jval *sp = jget(a, "special");
        jval *content = jget(a, "content");
        if (!content || content->t != J_STR) die("added token content");
        if (tokens[id] && strcmp(tokens[id], content->str)) die("added token disagrees with vocab");
        tokens[id] = content->str; toklen[id] = content->slen;
        toktype[id] = (sp && sp->t == J_BOOL && sp->b) ? 3 /* CONTROL */ : 4 /* USER_DEFINED */;
    }
    uint32_t n_pad = 0;
    for (uint32_t i = 0; i < n_vocab; i++) if (!tokens[i]) {
        char *s = xmalloc(24); snprintf(s, 24, "[PAD%u]", i); tokens[i] = s; toklen[i] = strlen(s); n_pad++;
    }
    for (size_t i = 0; i < merges->n; i++) {
        jval *m = merges->items[i];
        if (!(m->t == J_STR || (m->t == J_ARR && m->n == 2 && m->items[0]->t == J_STR && m->items[1]->t == J_STR))) die("merge entry shape");
    }
    t = read_file(path_join(dir, "tokenizer_config.json"), &n);
    jval *tcfg = jparse_text(t, n, "tokenizer_config.json");
    const char *chat_template = jstr(tcfg, "chat_template");
    jval *addbos = jget(tcfg, "add_bos_token");
    int add_bos = addbos && addbos->t == J_BOOL && addbos->b;
    jval *padtok = jget(tcfg, "pad_token");
    uint32_t pad_id = bos_id;
    if (padtok && padtok->t == J_STR) {
        int found = 0;
        for (uint32_t i = 0; i < n_vocab && !found; i++) if (toktype[i] >= 3 && !strcmp(tokens[i], padtok->str)) { pad_id = i; found = 1; }
        if (!found) die("pad_token not among added tokens");
    }

    /* safetensors shards */
    t = read_file(path_join(dir, "model.safetensors.index.json"), &n);
    jval *index = jparse_text(t, n, "model.safetensors.index.json");
    jval *wmap = jget(index, "weight_map");
    if (!wmap || wmap->t != J_OBJ) die("weight_map");
    char **files = NULL; size_t nfiles = 0;
    for (size_t i = 0; i < wmap->n; i++) {
        const char *fn = wmap->items[i]->str; size_t k;
        for (k = 0; k < nfiles; k++) if (!strcmp(files[k], fn)) break;
        if (k == nfiles) { files = xrealloc(files, (nfiles + 1) * sizeof *files); files[nfiles++] = (char *)fn; }
    }
    tensor *ts = NULL; size_t nts = 0;
    uint64_t *data_base = xmalloc(nfiles * sizeof *data_base);
    int *fds = xmalloc(nfiles * sizeof *fds);
    for (size_t k = 0; k < nfiles; k++) {
        char *fp = path_join(dir, files[k]);
        fds[k] = open(fp, O_RDONLY);
        if (fds[k] < 0) die2("open shard", fp);
        uint64_t hlen;
        if (pread(fds[k], &hlen, 8, 0) != 8) die2("shard header length", fp);
        if (hlen > (64u << 20)) die2("shard header too large", fp);
        char *h = xmalloc(hlen + 1);
        if (pread(fds[k], h, hlen, 8) != (ssize_t)hlen) die2("shard header", fp);
        h[hlen] = 0;
        data_base[k] = 8 + hlen;
        jval *hdr = jparse_text(h, hlen, files[k]);
        for (size_t i = 0; i < hdr->n; i++) {
            if (!strcmp(hdr->keys[i], "__metadata__")) continue;
            jval *e = hdr->items[i];
            char gname[64];
            if (!map_name(hdr->keys[i], gname, sizeof gname)) die2("unmapped tensor", hdr->keys[i]);
            if (tied && !strcmp(gname, "output.weight")) die("tied embeddings but lm_head.weight present");
            if (strcmp(jstr(e, "dtype"), "BF16")) die2("tensor is not BF16", hdr->keys[i]);
            jval *shape = jget(e, "shape"), *off = jget(e, "data_offsets");
            if (!shape || shape->t != J_ARR || shape->n < 1 || shape->n > 2) die2("tensor rank outside profile", hdr->keys[i]);
            if (!off || off->t != J_ARR || off->n != 2) die2("data_offsets", hdr->keys[i]);
            ts = xrealloc(ts, (nts + 1) * sizeof *ts);
            tensor *x = &ts[nts++];
            memset(x, 0, sizeof *x);
            memcpy(x->gname, gname, sizeof gname);
            x->hname = hdr->keys[i]; x->file = (int)k;
            x->begin = (uint64_t)off->items[0]->num; x->end = (uint64_t)off->items[1]->num;
            x->ndim = (uint32_t)shape->n;
            uint64_t count = 1;
            for (size_t d = 0; d < shape->n; d++) { x->ne[d] = (uint64_t)shape->items[shape->n - 1 - d]->num; count *= x->ne[d]; }
            if (x->end - x->begin != count * 2) die2("byte range does not match a bf16 shape", hdr->keys[i]);
            if (x->ndim == 1) { x->type = GGML_F32; x->nbytes = count * 4; }
            else { x->type = GGML_BF16; x->nbytes = count * 2; }
        }
    }
    uint64_t expect = 2 + (uint64_t)n_layer * NLAYER_MAP + (tied ? 0 : 1);
    if (nts != expect) { fprintf(stderr, "st2gguf: %zu tensors, expected %llu\n", nts, (unsigned long long)expect); return 2; }
    qsort(ts, nts, sizeof *ts, cmp_tensor);
    /* shape checks against the config */
    for (size_t i = 0; i < nts; i++) {
        tensor *x = &ts[i]; const char *g = x->gname; int ok = 1;
        if (!strcmp(g, "token_embd.weight") || !strcmp(g, "output.weight")) ok = x->ndim == 2 && x->ne[0] == n_embd && x->ne[1] == n_vocab;
        else if (!strcmp(g, "output_norm.weight") || strstr(g, ".attn_norm.") || strstr(g, ".ffn_norm.")) ok = x->ndim == 1 && x->ne[0] == n_embd;
        else if (strstr(g, ".attn_q_norm.") || strstr(g, ".attn_k_norm.")) ok = x->ndim == 1 && x->ne[0] == head_dim;
        else if (strstr(g, ".attn_q.")) ok = x->ndim == 2 && x->ne[0] == n_embd && x->ne[1] == (uint64_t)n_head * head_dim;
        else if (strstr(g, ".attn_k.") || strstr(g, ".attn_v.")) ok = x->ndim == 2 && x->ne[0] == n_embd && x->ne[1] == (uint64_t)n_head_kv * head_dim;
        else if (strstr(g, ".attn_output.")) ok = x->ndim == 2 && x->ne[0] == (uint64_t)n_head * head_dim && x->ne[1] == n_embd;
        else if (strstr(g, ".ffn_gate.") || strstr(g, ".ffn_up.")) ok = x->ndim == 2 && x->ne[0] == n_embd && x->ne[1] == n_ff;
        else if (strstr(g, ".ffn_down.")) ok = x->ndim == 2 && x->ne[0] == n_ff && x->ne[1] == n_embd;
        if (!ok) die2("shape disagrees with config.json", g);
    }
    uint64_t off = 0;
    for (size_t i = 0; i < nts; i++) { ts[i].offset = off; off += (ts[i].nbytes + ALIGN - 1) / ALIGN * ALIGN; }

    /* write */
    FILE *of = fopen(outpath, "wb");
    if (!of) die2("cannot create", outpath);
    gw w = { of, 0 };
    wbytes(&w, "GGUF", 4);
    wu32(&w, 3);
    wu64(&w, nts);
    const uint64_t n_kv = 26; /* keep equal to the kv_* and array writes below */
    wu64(&w, n_kv);
    kv_str(&w, "general.architecture", "qwen3");
    kv_u32(&w, "general.quantization_version", 2);
    kv_u32(&w, "general.alignment", ALIGN);
    kv_str(&w, "general.name", jget(cfg, "_name_or_path") && jget(cfg, "_name_or_path")->t == J_STR ? jstr(cfg, "_name_or_path") : "qwen3");
    kv_u32(&w, "general.file_type", 32); /* MOSTLY_BF16 */
    kv_u32(&w, "qwen3.context_length", n_ctx);
    kv_u32(&w, "qwen3.embedding_length", n_embd);
    kv_u32(&w, "qwen3.block_count", n_layer);
    kv_u32(&w, "qwen3.feed_forward_length", n_ff);
    kv_u32(&w, "qwen3.attention.head_count", n_head);
    kv_u32(&w, "qwen3.attention.head_count_kv", n_head_kv);
    kv_u32(&w, "qwen3.attention.key_length", head_dim);
    kv_u32(&w, "qwen3.attention.value_length", head_dim);
    kv_f32(&w, "qwen3.attention.layer_norm_rms_epsilon", rms_eps);
    kv_f32(&w, "qwen3.rope.freq_base", rope_theta);
    kv_u32(&w, "qwen3.rope.dimension_count", head_dim);
    kv_str(&w, "tokenizer.ggml.model", "gpt2");
    kv_str(&w, "tokenizer.ggml.pre", "qwen2");
    wstr(&w, "tokenizer.ggml.tokens"); wu32(&w, GT_ARR); wu32(&w, GT_STR); wu64(&w, n_vocab);
    for (uint32_t i = 0; i < n_vocab; i++) wstrn(&w, tokens[i], toklen[i]);
    wstr(&w, "tokenizer.ggml.token_type"); wu32(&w, GT_ARR); wu32(&w, GT_I32); wu64(&w, n_vocab);
    for (uint32_t i = 0; i < n_vocab; i++) wi32(&w, toktype[i]);
    wstr(&w, "tokenizer.ggml.merges"); wu32(&w, GT_ARR); wu32(&w, GT_STR); wu64(&w, merges->n);
    for (size_t i = 0; i < merges->n; i++) {
        jval *m = merges->items[i];
        if (m->t == J_STR) wstrn(&w, m->str, m->slen);
        else {
            size_t a = m->items[0]->slen, b = m->items[1]->slen;
            wu64(&w, a + 1 + b); wbytes(&w, m->items[0]->str, a); wbytes(&w, " ", 1); wbytes(&w, m->items[1]->str, b);
        }
    }
    kv_u32(&w, "tokenizer.ggml.bos_token_id", bos_id);
    kv_u32(&w, "tokenizer.ggml.eos_token_id", eos_id);
    kv_u32(&w, "tokenizer.ggml.padding_token_id", pad_id);
    kv_bool(&w, "tokenizer.ggml.add_bos_token", add_bos);
    kv_str(&w, "tokenizer.chat_template", chat_template);
    for (size_t i = 0; i < nts; i++) {
        tensor *x = &ts[i];
        wstr(&w, x->gname); wu32(&w, x->ndim);
        for (uint32_t d = 0; d < x->ndim; d++) wu64(&w, x->ne[d]);
        wu32(&w, x->type); wu64(&w, x->offset);
    }
    static const uint8_t zeros[ALIGN];
    while (w.pos % ALIGN) wu8(&w, 0);
    uint64_t data_start = w.pos;

    const size_t BUF = 64u << 20;
    uint8_t *buf = xmalloc(BUF);
    uint8_t *wide = xmalloc(BUF * 2);
    for (size_t i = 0; i < nts; i++) {
        tensor *x = &ts[i];
        if (w.pos - data_start != x->offset) die("data offset drift");
        uint64_t left = x->end - x->begin, src = data_base[x->file] + x->begin;
        while (left) {
            size_t chunk = left < BUF ? (size_t)left : BUF;
            ssize_t got = pread(fds[x->file], buf, chunk, (off_t)src);
            if (got != (ssize_t)chunk) die2("short shard read", x->hname);
            if (x->type == GGML_BF16) wbytes(&w, buf, chunk);
            else {
                const uint16_t *in = (const uint16_t *)buf; uint32_t *out = (uint32_t *)wide;
                for (size_t j = 0; j < chunk / 2; j++) out[j] = (uint32_t)in[j] << 16;
                wbytes(&w, wide, chunk * 2);
            }
            left -= chunk; src += chunk;
        }
        uint64_t padn = (ALIGN - (x->nbytes % ALIGN)) % ALIGN;
        if (padn) wbytes(&w, zeros, padn);
    }
    if (fclose(of)) die("close failed");
    printf("st2gguf: %zu tensors, %u layers, vocab %u (%u padding ids), %zu merges, data %llu bytes, file %llu bytes\n",
           nts, n_layer, n_vocab, n_pad, merges->n, (unsigned long long)(w.pos - data_start), (unsigned long long)w.pos);
    return 0;
}
