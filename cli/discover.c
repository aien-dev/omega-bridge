/* SPDX-License-Identifier: AGPL-3.0-only */
#include "host.h"
#include "registry.h"
#include <ctype.h>
#include <dirent.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
struct inventory inventory;
struct cached {
  char path[PATH_MAX], version[256];
  struct stat st;
  int ok;
  long long checked;
};
static struct cached cache[MAX_ITEMS];
static size_t ncache;
void invalidate_cache(void) { ncache = 0; }
static long long probe_deadline;
static void warn_once(const char *s) {
  for (size_t i = 0; i < inventory.nwarnings; i++)
    if (!strcmp(inventory.warnings[i], s))
      return;
  if (inventory.nwarnings < MAX_WARN)
    copystr(inventory.warnings[inventory.nwarnings++], 256, s);
}
static const struct descriptor *descriptor(const char *name) {
  for (size_t i = 0; i < ARRAY_LEN(registry); i++)
    if (!strcmp(name, registry[i].name))
      return &registry[i];
  if (!strncmp(name, "python", 6) && isdigit((unsigned char)name[6])) {
    for (const char *p = name + 6; *p; p++)
      if (!isdigit((unsigned char)*p) && *p != '.')
        return NULL;
    return &registry[0];
  }
  return NULL;
}
static int same_stat(const struct stat *a, const struct stat *b) {
  return a->st_dev == b->st_dev && a->st_ino == b->st_ino &&
         a->st_size == b->st_size && a->st_mtim.tv_sec == b->st_mtim.tv_sec &&
         a->st_mtim.tv_nsec == b->st_mtim.tv_nsec &&
         a->st_ctim.tv_sec == b->st_ctim.tv_sec &&
         a->st_ctim.tv_nsec == b->st_ctim.tv_nsec;
}
static void version(struct item *it, const struct descriptor *d) {
  for (size_t i = 0; i < ncache; i++)
    if (cache[i].ok && monotonic_ms() - cache[i].checked < 60000 &&
        !strcmp(cache[i].path, it->path) && same_stat(&cache[i].st, &it->st)) {
      copystr(it->version, sizeof it->version, cache[i].version);
      it->flags[1] = (unsigned char)cache[i].ok;
      return;
    }
  if (monotonic_ms() > probe_deadline) {
    copystr(it->reason, sizeof it->reason,
            "probe budget exhausted; bounded scan deferred this check");
    return;
  }
  char out[2048];
  size_t n = 0;
  int ok = run_process(it->path, d->version_arg, NULL, 0, out, sizeof out, &n,
                       250) == 0 &&
           n > 0;
  const char *line = out;
  size_t line_len = 0;
  int digit = 0;
  while (*line && !digit) {
    line_len = strcspn(line, "\r\n");
    for (size_t i = 0; i < line_len; i++)
      if (isdigit((unsigned char)line[i]))
        digit = 1;
    if (!digit) {
      line += line_len;
      line += strspn(line, "\r\n");
    }
  }
  ok = ok && digit;
  if (ok) {
    size_t len = line_len;
    if (len >= sizeof it->version)
      len = sizeof it->version - 1;
    memcpy(it->version, line, len);
    it->version[len] = 0;
  }
  it->flags[1] = (unsigned char)ok;
  size_t slot = ncache;
  for (size_t i = 0; i < ncache; i++)
    if (!strcmp(cache[i].path, it->path)) {
      slot = i;
      break;
    }
  if (slot < MAX_ITEMS) {
    if (slot == ncache)
      ncache++;
    copystr(cache[slot].path, PATH_MAX, it->path);
    cache[slot].st = it->st;
    cache[slot].ok = ok;
    cache[slot].checked = monotonic_ms();
    copystr(cache[slot].version, 256, it->version);
  }
}
static uint64_t identity(const struct item *it) {
  uint64_t h = UINT64_C(14695981039346656037);
  const char *s[] = {it->language, it->path, it->environment};
  for (size_t j = 0; j < ARRAY_LEN(s); j++) {
    for (const unsigned char *p = (const unsigned char *)s[j]; *p; p++) {
      h ^= *p;
      h *= UINT64_C(1099511628211);
    }
    h ^= 0;
    h *= UINT64_C(1099511628211);
  }
  return h;
}
static void candidate(const char *p, const char *env,
                      const struct descriptor *d) {
  struct stat st;
  if (stat(p, &st) || !S_ISREG(st.st_mode) || access(p, X_OK))
    return;
  char resolved[PATH_MAX], scope[PATH_MAX];
  if (!realpath(p, resolved))
    return;
  copystr(scope, sizeof scope, env);
  if (!strcmp(d->language, "python")) {
    copystr(scope, sizeof scope, resolved);
    char *end = strrchr(scope, '/');
    if (end)
      *end = 0;
    end = strrchr(scope, '/');
    if (end && !strcmp(end + 1, "bin"))
      *end = 0;
    char prefix[PATH_MAX];
    copystr(prefix, sizeof prefix, p);
    char *slash = strrchr(prefix, '/');
    if (slash)
      *slash = 0;
    slash = strrchr(prefix, '/');
    if (slash && !strcmp(slash + 1, "bin")) {
      *slash = 0;
      char cfg[PATH_MAX];
      join(cfg, sizeof cfg, prefix, "pyvenv.cfg");
      const char *active = getenv("VIRTUAL_ENV");
      if (exists(cfg) || (active && !strcmp(active, prefix)))
        copystr(scope, sizeof scope, prefix);
    }
  }
  for (size_t i = 0; i < inventory.n; i++) {
    struct item *it = &inventory.items[i];
    if (it->st.st_dev == st.st_dev && it->st.st_ino == st.st_ino &&
        !strcmp(it->language, d->language) &&
        (strcmp(d->language, "python") || !strcmp(it->environment, scope))) {
      for (size_t j = 0; j < it->nalias; j++)
        if (!strcmp(it->aliases[j], p))
          return;
      if (it->nalias < MAX_ALIAS)
        copystr(it->aliases[it->nalias++], PATH_MAX, p);
      else
        warn_once("alias limit reached");
      return;
    }
  }
  if (inventory.n == MAX_ITEMS) {
    warn_once("inventory limit reached; discovery is partial");
    return;
  }
  struct item *it = &inventory.items[inventory.n++];
  copystr(it->language, sizeof it->language, d->language);
  if (!realpath(p, it->path)) {
    copystr(it->path, PATH_MAX, p);
  }
  copystr(it->environment, PATH_MAX, scope);
  copystr(it->aliases[it->nalias++], PATH_MAX, p);
  it->st = st;
  it->flags[0] = 1;
  version(it, d);
  copystr(it->reason, sizeof it->reason,
          it->flags[1]
              ? "no verified reversible runtime hook; converter NOT_AVAILABLE"
              : "version probe failed, timed out, exceeded output bound or "
                "supplied no version");
#ifdef OMEGA_ATTACH_TESTING
  if (!strcmp(d->language, "fixture") && it->flags[1]) {
    char out[128];
    size_t n;
    if (!strcmp(it->version, "omega-fixture 1.0") &&
        !run_process(it->path, "--omega-attach-probe-v1", NULL, 0, out,
                     sizeof out, &n, 250) &&
        !strcmp(out, "OMEGA_ATTACH_FIXTURE_V1 native 1\n")) {
      it->flags[2] = 1;
      it->flags[3] = 1;
      copystr(it->reason, sizeof it->reason,
              "fixture-only cooperating runtime registration");
    } else
      copystr(it->reason, sizeof it->reason,
              "fixture version/ABI protocol incompatible; no hook installed");
  }
#endif
  struct stat after;
  if (stat(p, &after) || !same_stat(&st, &after)) {
    it->flags[1] = 0;
    copystr(it->reason, sizeof it->reason,
            "executable changed during capability check; retry next scan");
  }
  snprintf(it->hook, sizeof it->hook, "%016llx.hook",
           (unsigned long long)identity(it));
}
static void watch_dir(const char *p) {
  char buf[PATH_MAX];
  copystr(buf, sizeof buf, p);
  struct stat st;
  while (stat(buf, &st) || !S_ISDIR(st.st_mode)) {
    char *s = strrchr(buf, '/');
    if (!s || s == buf)
      return;
    *s = 0;
  }
  for (size_t i = 0; i < inventory.ndirs; i++)
    if (!strcmp(inventory.dirs[i], buf))
      return;
  if (inventory.ndirs < MAX_DIRS)
    copystr(inventory.dirs[inventory.ndirs++], PATH_MAX, buf);
  else
    warn_once("watch directory limit reached; periodic rescan remains active");
}
static int entry_budget(void) {
  if (++inventory.visited > 16384) {
    warn_once("directory entry budget reached; discovery is partial");
    return 0;
  }
  return 1;
}
static void bin_dir(const char *dir, const char *env) {
  watch_dir(dir);
  DIR *f = opendir(dir);
  if (!f) {
    if (errno != ENOENT && errno != ENOTDIR)
      warn_once("a discovery directory is unreadable");
    return;
  }
  struct dirent *e;
  size_t entries = 0;
  while ((e = readdir(f))) {
    if (!entry_budget() || ++entries > 4096) {
      warn_once("directory entry limit reached; discovery is partial");
      break;
    }
    const struct descriptor *d = descriptor(e->d_name);
    if (!d)
      continue;
    char p[PATH_MAX];
    join(p, sizeof p, dir, e->d_name);
    candidate(p, env, d);
  }
  closedir(f);
}
static void manager(const char *dir, int depth) {
  watch_dir(dir);
  if (depth > 5 || inventory.visited > 16384)
    return;
  DIR *f = opendir(dir);
  if (!f) {
    if (errno != ENOENT && errno != ENOTDIR)
      warn_once("a manager directory is unreadable");
    return;
  }
  const char *base = strrchr(dir, '/');
  base = base ? base + 1 : dir;
  if (!strcmp(base, "bin") || !strcmp(base, "Scripts")) {
    char env[PATH_MAX];
    copystr(env, sizeof env, dir);
    char *s = strrchr(env, '/');
    if (s)
      *s = 0;
    bin_dir(dir, env);
    closedir(f);
    return;
  }
  /* Runtimes such as dotnet reside directly in their manager root. */
  bin_dir(dir, dir);
  struct dirent *e;
  size_t entries = 0;
  while ((e = readdir(f))) {
    if (!entry_budget() || ++entries > 512) {
      warn_once("manager tree limit reached; discovery is partial");
      break;
    }
    if (e->d_name[0] == '.' || !strcmp(e->d_name, "lib") ||
        !strcmp(e->d_name, "include") || !strcmp(e->d_name, "share") ||
        !strcmp(e->d_name, "pkgs") || !strcmp(e->d_name, "node_modules"))
      continue;
    char p[PATH_MAX];
    join(p, sizeof p, dir, e->d_name);
    struct stat st;
    /* Do not follow manager directory symlinks recursively; canonical roots and
       executable aliases are followed. This prevents cycles and huge trees. */
    if (lstat(p, &st) == 0 && S_ISDIR(st.st_mode))
      manager(p, depth + 1);
  }
  closedir(f);
}
static void roots(void) {
  const char *path = getenv("PATH");
  char *b = strdup(path ? path : "");
  if (!b)
    die("out of memory");
  char *part = b;
  for (char *p = b;; p++) {
    if (*p != ':' && *p)
      continue;
    char c = *p;
    *p = 0;
    if (part[0] == '/')
      bin_dir(part, "");
    else
      warn_once(
          "relative PATH components skipped for cwd-independent discovery");
    if (!c)
      break;
    part = p + 1;
  }
  free(b);
  for (size_t i = 0; i < ARRAY_LEN(manager_defaults); i++) {
    char p[PATH_MAX];
    join(p, sizeof p, ctx.home, manager_defaults[i]);
    manager(p, 0);
  }
  for (size_t i = 0; i < ARRAY_LEN(manager_vars); i++) {
    const char *v = getenv(manager_vars[i]);
    if (v && v[0] == '/') {
      char *values = strdup(v);
      if (!values)
        die("out of memory");
      char *save = NULL;
      for (char *s = strtok_r(values, ":", &save); s;
           s = strtok_r(NULL, ":", &save))
        if (s[0] == '/')
          manager(s, 0);
      free(values);
    }
  }
  char p[PATH_MAX];
  join(p, sizeof p, ctx.home, ".conda/environments.txt");
  watch_dir(p);
  char *b2 = slurp(p, NULL);
  if (b2) {
    char *save = NULL;
    for (char *s = strtok_r(b2, "\n", &save); s;
         s = strtok_r(NULL, "\n", &save)) {
      if (s[0] == '/' && strlen(s) < PATH_MAX)
        manager(s, 0);
    }
    free(b2);
  }
}
static int item_cmp(const void *a, const void *b) {
  const struct item *x = a, *y = b;
  int n = strcmp(x->language, y->language);
  if (!n)
    n = strcmp(x->path, y->path);
  if (!n)
    n = strcmp(x->environment, y->environment);
  return n;
}
static int hook_owned(const char *p) {
  char *b = slurp(p, NULL);
  int ok = b && !strncmp(b, "OMEGA_ATTACH_FIXTURE_V1\n", 24);
  free(b);
  return ok;
}
void clear_hooks(void) {
  char dir[PATH_MAX];
  join(dir, sizeof dir, ctx.state, "hooks");
  DIR *f = opendir(dir);
  if (!f)
    return;
  struct dirent *e;
  while ((e = readdir(f))) {
    if (e->d_name[0] == '.')
      continue;
    char p[PATH_MAX];
    join(p, sizeof p, dir, e->d_name);
    if (!hook_owned(p)) {
      closedir(f);
      die("modified or foreign hook preserved");
    }
    remove_owned(p);
  }
  closedir(f);
}
static void reconcile_hooks(int enrolled) {
  char enabled[PATH_MAX];
  join(enabled, sizeof enabled, ctx.state, "enabled");
  for (size_t i = 0; i < inventory.n; i++) {
    struct item *it = &inventory.items[i];
    it->flags[4] = (unsigned char)enrolled;
    if (!enrolled || !it->flags[1] || !it->flags[2] || !it->flags[3])
      continue;
    if (!exists(enabled))
      continue;
    char dir[PATH_MAX], p[PATH_MAX];
    join(dir, sizeof dir, ctx.state, "hooks");
    join(p, sizeof p, dir, it->hook);
    char contents[PATH_MAX + 80];
    int n = snprintf(contents, sizeof contents, "OMEGA_ATTACH_FIXTURE_V1\n%s\n",
                     it->path);
    size_t len;
    char *old = slurp(p, &len);
    if (exists(p) && (!old || len != (size_t)n || memcmp(old, contents, len))) {
      free(old);
      copystr(it->reason, sizeof it->reason,
              "existing hook was modified; preserved and refused");
      it->flags[1] = 0;
      continue;
    }
    free(old);
    atomic_write(p, contents, (size_t)n, 0600);
#ifdef OMEGA_ATTACH_TESTING
    if (getenv("OMEGA_ATTACH_FAIL") &&
        !strcmp(getenv("OMEGA_ATTACH_FAIL"), "hook"))
      die("injected hook transaction failure");
#endif
    char *verified = slurp(p, &len);
    it->flags[5] = (unsigned char)(verified && len == (size_t)n &&
                                   !memcmp(verified, contents, len));
    free(verified);
  }
  if (!enrolled)
    return;
  char dir[PATH_MAX];
  join(dir, sizeof dir, ctx.state, "hooks");
  DIR *f = opendir(dir);
  if (!f)
    return;
  struct dirent *e;
  while ((e = readdir(f))) {
    if (e->d_name[0] == '.')
      continue;
    int keep = 0;
    for (size_t i = 0; i < inventory.n; i++)
      if (inventory.items[i].flags[5] &&
          !strcmp(inventory.items[i].hook, e->d_name))
        keep = 1;
    if (!keep) {
      char p[PATH_MAX];
      join(p, sizeof p, dir, e->d_name);
      if (hook_owned(p))
        remove_owned(p);
      else
        warn_once("modified stale hook preserved; manual review required");
    }
  }
  closedir(f);
}
void scan(int enrolled) {
  memset(&inventory, 0, sizeof inventory);
  probe_deadline = monotonic_ms() + 5000;
  roots();
  qsort(inventory.items, inventory.n, sizeof inventory.items[0], item_cmp);
  reconcile_hooks(enrolled);
  unsigned char records[MAX_ITEMS * 6];
  for (size_t i = 0; i < inventory.n; i++)
    memcpy(records + 6 * i, inventory.items[i].flags, 6);
  char out[MAX_ITEMS + 1];
  size_t n = 0;
  if (run_process(ctx.policy, NULL, records, inventory.n * 6, out, sizeof out,
                  &n, 500) ||
      n != inventory.n)
    die("native Omega eligibility policy failed");
  for (size_t i = 0; i < inventory.n; i++) {
    if (out[i] < '0' || out[i] > '4')
      die("invalid native Omega policy response");
    inventory.items[i].state = out[i];
  }
}
void inventory_json(FILE *f) {
  static const char *states[] = {"DETECTED", "SUPPORTED", "ATTACHED",
                                 "UNSUPPORTED", "ERROR"};
  fputs("\"inventory\":[", f);
  for (size_t i = 0; i < inventory.n; i++) {
    const struct item *it = &inventory.items[i];
    if (i)
      fputc(',', f);
    fputs("{\"language\":", f);
    json_string(f, it->language);
    fputs(",\"path\":", f);
    json_string(f, it->path);
    fputs(",\"environment\":", f);
    json_string(f, it->environment);
    fputs(",\"version\":", f);
    json_string(f, it->version);
    fputs(",\"detection\":\"DETECTED\",\"state\":", f);
    json_string(f, states[it->state - '0']);
    fputs(",\"reason\":", f);
    json_string(f, it->reason);
    fputs(",\"aliases\":[", f);
    for (size_t j = 0; j < it->nalias; j++) {
      if (j)
        fputc(',', f);
      json_string(f, it->aliases[j]);
    }
    fputs("]}", f);
  }
  fputs("],\"warnings\":[", f);
  for (size_t i = 0; i < inventory.nwarnings; i++) {
    if (i)
      fputc(',', f);
    json_string(f, inventory.warnings[i]);
  }
  fputs("]", f);
}
void write_inventory(void) {
  char *b = NULL;
  size_t n = 0;
  FILE *f = open_memstream(&b, &n);
  if (!f)
    die("cannot format inventory");
  inventory_json(f);
  fclose(f);
  char p[PATH_MAX];
  join(p, sizeof p, ctx.state, "inventory");
  atomic_write(p, b, n, 0600);
  free(b);
}
