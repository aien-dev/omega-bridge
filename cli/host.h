/* SPDX-License-Identifier: AGPL-3.0-only */
#ifndef OMEGA_ATTACH_HOST_H
#define OMEGA_ATTACH_HOST_H
#include <limits.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/stat.h>
#include <sys/types.h>
#define MAX_ITEMS 128
#define MAX_DIRS 192
#define MAX_ALIAS 16
#define MAX_WARN 24
#define MAX_BYTES (1024 * 1024)
#define ARRAY_LEN(a) (sizeof(a) / sizeof((a)[0]))
struct context {
  char home[PATH_MAX], self[PATH_MAX], policy[PATH_MAX], state[PATH_MAX],
      desktop[PATH_MAX];
  char dirs[64][PATH_MAX];
  size_t ndirs, old_ndirs;
  int lockfd, transaction;
};
struct item {
  char language[32], path[PATH_MAX], environment[PATH_MAX], version[256],
      reason[256];
  char aliases[MAX_ALIAS][PATH_MAX];
  size_t nalias;
  struct stat st;
  unsigned char flags[6];
  char state;
  char hook[64];
};
struct inventory {
  struct item items[MAX_ITEMS];
  size_t n;
  char dirs[MAX_DIRS][PATH_MAX];
  size_t ndirs;
  char warnings[MAX_WARN][256];
  size_t nwarnings;
  size_t visited;
};
extern struct context ctx;
extern struct inventory inventory;
void die(const char *message);
void join(char *out, size_t n, const char *a, const char *b);
void copystr(char *out, size_t n, const char *in);
int exists(const char *p);
char *slurp(const char *p, size_t *n);
void atomic_write(const char *p, const void *data, size_t n, mode_t mode);
void remove_owned(const char *p);
void ensure_dir(const char *p);
void init_context(void);
void begin_transaction(void);
void commit_transaction(void);
void rollback(void);
void remember(const char *p);
void load_dirs(void);
void validate_managed_path(const char *p);
void verify_owner(void);
void save_config(void);
void load_config(void);
uint64_t fingerprint(const char *p);
long long monotonic_ms(void);
int run_process(const char *exe, const char *arg, const void *input,
                size_t inlen, char *output, size_t cap, size_t *outlen,
                int timeout_ms);
int restrict_probe(void);
void check_policy(void);
void scan(int enrolled);
void invalidate_cache(void);
void json_string(FILE *f, const char *s);
void inventory_json(FILE *f);
void clear_hooks(void);
void write_inventory(void);
int watcher_running(long *pid);
void emit_status(int fresh);
#endif
