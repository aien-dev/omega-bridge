/* SPDX-License-Identifier: AGPL-3.0-only */
#include "host.h"
#include "registry.h"
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/resource.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
struct context ctx;
struct saved {
  char path[PATH_MAX];
  char *data;
  size_t len;
  mode_t mode;
  int existed;
};
static struct saved saved[192];
static size_t nsaved;
static int rolling_back;
void copystr(char *out, size_t n, const char *in) {
  if (strlen(in) >= n)
    die("path or field exceeds bound");
  memcpy(out, in, strlen(in) + 1);
}
void join(char *out, size_t n, const char *a, const char *b) {
  if (snprintf(out, n, "%s/%s", a, b) < 0 || strlen(a) + strlen(b) + 2 > n)
    die("path exceeds bound");
}
int exists(const char *p) {
  struct stat s;
  return lstat(p, &s) == 0;
}
char *slurp(const char *p, size_t *n) {
  int fd = open(p, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
  if (fd < 0)
    return NULL;
  struct stat s;
  if (fstat(fd, &s) || !S_ISREG(s.st_mode) || s.st_size < 0 ||
      s.st_size > MAX_BYTES) {
    close(fd);
    return NULL;
  }
  size_t len = (size_t)s.st_size;
  char *b = calloc(len + 1, 1);
  if (!b) {
    close(fd);
    die("out of memory");
  }
  size_t at = 0;
  while (at < len) {
    ssize_t r = read(fd, b + at, len - at);
    if (r <= 0) {
      free(b);
      close(fd);
      return NULL;
    }
    at += (size_t)r;
  }
  close(fd);
  if (n)
    *n = len;
  return b;
}
void remember(const char *p) {
  if (!ctx.transaction || rolling_back)
    return;
  for (size_t i = 0; i < nsaved; i++)
    if (!strcmp(saved[i].path, p))
      return;
  if (nsaved == ARRAY_LEN(saved))
    die("transaction exceeds bound");
  struct saved *s = &saved[nsaved];
  copystr(s->path, sizeof s->path, p);
  struct stat st;
  if (lstat(p, &st) == 0) {
    if (!S_ISREG(st.st_mode) || st.st_uid != getuid())
      die("refusing non-owned or non-regular managed file");
    s->existed = 1;
    s->mode = st.st_mode & 0777;
    s->data = slurp(p, &s->len);
    if (!s->data)
      die("cannot read managed file");
  } else if (errno != ENOENT)
    die("cannot inspect managed file");
  nsaved++;
}
static void write_raw(const char *p, const void *data, size_t n, mode_t mode) {
  char tmp[PATH_MAX];
  if (snprintf(tmp, sizeof tmp, "%s.tmp.XXXXXX", p) >= (int)sizeof tmp)
    die("temporary path exceeds bound");
  int fd = mkostemp(tmp, O_CLOEXEC);
  if (fd < 0)
    die("cannot stage managed file");
  if (fchmod(fd, mode)) {
    close(fd);
    unlink(tmp);
    die("cannot set managed file mode");
  }
  size_t at = 0;
  while (at < n) {
    ssize_t w = write(fd, (const char *)data + at, n - at);
    if (w <= 0) {
      close(fd);
      unlink(tmp);
      die("cannot write managed file");
    }
    at += (size_t)w;
  }
  if (fsync(fd) || close(fd) || rename(tmp, p)) {
    unlink(tmp);
    die("cannot commit managed file");
  }
  char parent[PATH_MAX];
  copystr(parent, sizeof parent, p);
  char *slash = strrchr(parent, '/');
  if (slash) {
    *slash = 0;
    int d = open(parent, O_DIRECTORY | O_CLOEXEC);
    if (d >= 0) {
      (void)fsync(d);
      close(d);
    }
  }
}
void atomic_write(const char *p, const void *data, size_t n, mode_t mode) {
  validate_managed_path(p);
  struct stat st;
  if (lstat(p, &st) == 0 && (!S_ISREG(st.st_mode) || st.st_uid != getuid()))
    die("refusing non-owned or non-regular managed file");
  remember(p);
  write_raw(p, data, n, mode);
}
void remove_owned(const char *p) {
  validate_managed_path(p);
  remember(p);
  if (unlink(p) && errno != ENOENT)
    die("cannot remove managed file");
}
void validate_managed_path(const char *p) {
  size_t hlen = strlen(ctx.home);
  if (strlen(p) <= hlen || strncmp(p, ctx.home, hlen) || p[hlen] != '/' ||
      strstr(p, "/../") || strstr(p, "/./"))
    die("managed path outside HOME");
  char part[PATH_MAX];
  copystr(part, sizeof part, p);
  for (char *q = part + hlen + 1; *q; q++)
    if (*q == '/') {
      *q = 0;
      struct stat st;
      int rc = lstat(part, &st);
      *q = '/';
      if (rc < 0) {
        if (errno == ENOENT)
          return;
        die("cannot inspect managed parent");
      }
      if (!S_ISDIR(st.st_mode) || st.st_uid != getuid())
        die("managed parent is symlink, foreign-owned or not a directory");
    }
}
void verify_owner(void) {
  char p[PATH_MAX];
  join(p, sizeof p, ctx.state, "owner");
  validate_managed_path(p);
  size_t n = 0;
  char *b = slurp(p, &n);
  int ok = b && n == 19 && !memcmp(b, "OMEGA_ATTACH_OWNER1\n", 19);
  free(b);
  if (!ok)
    die("existing unrecognized enrollment preserved");
}
void rollback(void) {
  if (!ctx.transaction || rolling_back)
    return;
  rolling_back = 1;
  while (nsaved) {
    struct saved *s = &saved[--nsaved];
    if (s->existed)
      write_raw(s->path, s->data, s->len, s->mode);
    else
      (void)unlink(s->path);
    free(s->data);
    memset(s, 0, sizeof *s);
  }
  for (size_t i = ctx.ndirs; i > ctx.old_ndirs; i--)
    (void)rmdir(ctx.dirs[i - 1]);
  ctx.ndirs = ctx.old_ndirs;
  ctx.transaction = 0;
  rolling_back = 0;
}
void die(const char *message) {
  fprintf(stderr, "om: %s (%s)\n", message, strerror(errno));
  rollback();
  exit(1);
}
void ensure_dir(const char *p) {
  size_t hlen = strlen(ctx.home);
  if (strncmp(p, ctx.home, hlen) || p[hlen] != '/' || strstr(p, "/../") ||
      strstr(p, "/./") || strchr(p, '\n'))
    die("managed directory outside HOME");
  char part[PATH_MAX];
  copystr(part, sizeof part, p);
  for (char *q = part + hlen + 1;; q++) {
    if (*q != '/' && *q)
      continue;
    char c = *q;
    *q = 0;
    struct stat st;
    if (lstat(part, &st) == 0) {
      if (!S_ISDIR(st.st_mode) || st.st_uid != getuid())
        die("managed parent is symlink, foreign-owned or not a directory");
    } else {
      if (errno != ENOENT || ctx.ndirs == ARRAY_LEN(ctx.dirs) ||
          mkdir(part, 0700))
        die("cannot create managed directory");
      copystr(ctx.dirs[ctx.ndirs++], PATH_MAX, part);
    }
    *q = c;
    if (!c)
      break;
  }
}
void init_context(void) {
  memset(&ctx, 0, sizeof ctx);
  ctx.lockfd = -1;
  const char *home = getenv("HOME");
  if (!home || home[0] != '/' || !realpath(home, ctx.home))
    die("HOME must be an existing absolute directory");
  ssize_t n = readlink("/proc/self/exe", ctx.self, sizeof ctx.self - 1);
  if (n <= 0 || n >= (ssize_t)sizeof(ctx.self) - 1)
    die("cannot locate native launcher");
  ctx.self[n] = 0;
  copystr(ctx.policy, sizeof ctx.policy, ctx.self);
  char *s = strrchr(ctx.policy, '/');
  if (!s)
    die("invalid executable location");
  *s = 0;
  char base[PATH_MAX];
  copystr(base, sizeof base, ctx.policy);
  join(ctx.policy, sizeof ctx.policy, base, "attachment-policy");
  join(ctx.state, sizeof ctx.state, ctx.home, ".local/state/omega-attach");
  join(ctx.desktop, sizeof ctx.desktop, ctx.home,
       ".config/autostart/omega-attach.desktop");
}
void load_dirs(void) {
  char p[PATH_MAX];
  join(p, sizeof p, ctx.state, "created-dirs");
  char *b = slurp(p, NULL);
  if (!b) {
    if (exists(p))
      die("invalid directory receipt");
    return;
  }
  char *save = NULL;
  for (char *s = strtok_r(b, "\n", &save); s; s = strtok_r(NULL, "\n", &save)) {
    if (ctx.ndirs == ARRAY_LEN(ctx.dirs) ||
        strncmp(s, ctx.home, strlen(ctx.home)) || s[strlen(ctx.home)] != '/' ||
        strstr(s, ".."))
      die("invalid directory receipt");
    copystr(ctx.dirs[ctx.ndirs++], PATH_MAX, s);
  }
  free(b);
}
void begin_transaction(void) {
  int present = exists(ctx.state);
  if (present) {
    verify_owner();
    load_dirs();
  }
  ctx.old_ndirs = ctx.ndirs;
  ctx.transaction = 1;
  ensure_dir(ctx.state);
  char p[PATH_MAX];
  join(p, sizeof p, ctx.state, "lock");
  if (!present)
    remember(p);
  ctx.lockfd = open(
      p, O_RDWR | O_CLOEXEC | O_NOFOLLOW | (present ? 0 : O_CREAT | O_EXCL),
      0600);
  if (ctx.lockfd < 0 || flock(ctx.lockfd, LOCK_EX | LOCK_NB))
    die("another enrollment command is active");
  if (!present) {
    join(p, sizeof p, ctx.state, "owner");
    atomic_write(p, "OMEGA_ATTACH_OWNER1\n", 19, 0600);
  }
}
void commit_transaction(void) {
  char p[PATH_MAX];
  join(p, sizeof p, ctx.state, "created-dirs");
  char *b = NULL;
  size_t n = 0;
  FILE *f = open_memstream(&b, &n);
  if (!f)
    die("cannot write directory receipt");
  for (size_t i = 0; i < ctx.ndirs; i++)
    fprintf(f, "%s\n", ctx.dirs[i]);
  fclose(f);
  atomic_write(p, b, n, 0600);
  free(b);
  for (size_t i = 0; i < nsaved; i++)
    free(saved[i].data);
  memset(saved, 0, sizeof saved);
  nsaved = 0;
  ctx.transaction = 0;
}
struct config {
  char magic[16], path[8192], values[ARRAY_LEN(manager_vars)][PATH_MAX];
};
void save_config(void) {
  struct config *c = calloc(1, sizeof *c);
  if (!c)
    die("out of memory");
  copystr(c->magic, sizeof c->magic, "OMEGA_ATTACH_V1");
  copystr(c->path, sizeof c->path, getenv("PATH") ? getenv("PATH") : "");
  for (size_t i = 0; i < ARRAY_LEN(manager_vars); i++) {
    const char *v = getenv(manager_vars[i]);
    if (v && v[0] == '/')
      copystr(c->values[i], PATH_MAX, v);
  }
  char p[PATH_MAX];
  join(p, sizeof p, ctx.state, "config");
  atomic_write(p, c, sizeof *c, 0600);
  free(c);
}
void load_config(void) {
  char p[PATH_MAX];
  join(p, sizeof p, ctx.state, "config");
  size_t n;
  char *b = slurp(p, &n);
  if (!b || n != sizeof(struct config))
    die("missing or invalid enrollment configuration");
  struct config *c = (struct config *)b;
  if (memcmp(c->magic, "OMEGA_ATTACH_V1\0", 16) ||
      !memchr(c->path, 0, sizeof c->path))
    die("unsupported enrollment configuration");
  setenv("PATH", c->path, 1);
  for (size_t i = 0; i < ARRAY_LEN(manager_vars); i++) {
    if (!memchr(c->values[i], 0, PATH_MAX))
      die("invalid manager root");
    if (c->values[i][0])
      setenv(manager_vars[i], c->values[i], 1);
    else
      unsetenv(manager_vars[i]);
  }
  free(b);
}
uint64_t fingerprint(const char *p) {
  int fd = open(p, O_RDONLY | O_NOFOLLOW | O_CLOEXEC);
  if (fd < 0)
    die("cannot fingerprint managed file");
  uint64_t h = UINT64_C(14695981039346656037);
  char b[8192];
  ssize_t n;
  while ((n = read(fd, b, sizeof b)) > 0) {
    for (ssize_t i = 0; i < n; i++) {
      h ^= (unsigned char)b[i];
      h *= UINT64_C(1099511628211);
    }
  }
  close(fd);
  if (n < 0)
    die("cannot fingerprint managed file");
  return h;
}
long long monotonic_ms(void) {
  struct timespec t;
  if (clock_gettime(CLOCK_MONOTONIC, &t))
    die("cannot read monotonic clock");
  return (long long)t.tv_sec * 1000 + t.tv_nsec / 1000000;
}
int run_process(const char *exe, const char *arg, const void *input,
                size_t inlen, char *output, size_t cap, size_t *outlen,
                int timeout_ms) {
  int in[2], out[2];
  if (pipe2(in, O_CLOEXEC) || pipe2(out, O_CLOEXEC))
    die("cannot open boundary pipes");
  pid_t pid = fork();
  if (pid < 0)
    die("cannot spawn boundary");
  if (pid == 0) {
    (void)setpgid(0, 0);
    if (dup2(in[0], 0) < 0 || dup2(out[1], 1) < 0 || dup2(out[1], 2) < 0)
      _exit(126);
    close(in[0]);
    close(in[1]);
    close(out[0]);
    close(out[1]);
    (void)close_range(3, ~0U, 0);
    struct rlimit lim = {2, 2};
    (void)setrlimit(RLIMIT_CPU, &lim);
    lim.rlim_cur = lim.rlim_max = 0;
    (void)setrlimit(RLIMIT_CORE, &lim);
    /* Only pinned discovery environment crosses the executable boundary. */
    char *vals[ARRAY_LEN(manager_vars)];
    for (size_t i = 0; i < ARRAY_LEN(manager_vars); i++) {
      const char *v = getenv(manager_vars[i]);
      vals[i] = v ? strdup(v) : NULL;
    }
    char *path = strdup(getenv("PATH") ? getenv("PATH") : "");
    clearenv();
    setenv("HOME", ctx.home, 1);
    setenv("PATH", path ? path : "", 1);
    setenv("LC_ALL", "C", 1);
    for (size_t i = 0; i < ARRAY_LEN(manager_vars); i++)
      if (vals[i])
        setenv(manager_vars[i], vals[i], 1);
    if (restrict_probe())
      _exit(125);
    execl(exe, exe, arg, (char *)NULL);
    _exit(127);
  }
  (void)setpgid(pid, pid);
  close(in[0]);
  close(out[1]);
  /* Input is at most 768 bytes, below Linux PIPE_BUF, before the reader runs.
   */
  if (inlen) {
    ssize_t n = write(in[1], input, inlen);
    if (n != (ssize_t)inlen) {
      close(in[1]);
      close(out[0]);
      kill(-pid, SIGKILL);
      waitpid(pid, NULL, 0);
      return -1;
    }
  }
  close(in[1]);
  fcntl(out[0], F_SETFL, O_NONBLOCK);
  size_t at = 0;
  int status = 0, exited = 0, failed = 0, eof = 0;
  long long end = monotonic_ms() + timeout_ms;
  while (!exited || !eof) {
    char b[512];
    ssize_t n;
    while ((n = read(out[0], b, sizeof b)) > 0) {
      if (at + (size_t)n >= cap) {
        failed = 1;
        break;
      }
      memcpy(output + at, b, (size_t)n);
      at += (size_t)n;
    }
    if (n == 0)
      eof = 1;
    if (failed || monotonic_ms() >= end) {
      failed = 1;
      break;
    }
    if (!exited) {
      pid_t r = waitpid(pid, &status, WNOHANG);
      if (r == pid)
        exited = 1;
      else if (r < 0) {
        failed = 1;
        break;
      }
    }
    if (!exited || !eof) {
      struct pollfd p = {out[0], POLLIN, 0};
      (void)poll(&p, 1, 10);
    }
  }
  /* Also reap/terminate descendants holding pipes after the leader exits. */
  (void)kill(-pid, SIGKILL);
  if (!exited)
    while (waitpid(pid, &status, 0) < 0 && errno == EINTR) {
    }
  close(out[0]);
  output[at] = 0;
  if (outlen)
    *outlen = at;
  return failed || !WIFEXITED(status) || WEXITSTATUS(status) != 0 ? -1 : 0;
}
void check_policy(void) {
  unsigned char input[6] = {1, 1, 0, 0, 0, 0};
  char out[8];
  size_t n;
  if (run_process(ctx.policy, NULL, input, sizeof input, out, sizeof out, &n,
                  500) ||
      n != 1 || out[0] != '3')
    die("native Omega policy unavailable or incompatible");
}
void json_string(FILE *f, const char *s) {
  fputc('"', f);
  for (const unsigned char *p = (const unsigned char *)s; *p; p++) {
    if (*p == '"' || *p == '\\')
      fprintf(f, "\\%c", *p);
    else if (*p < 32)
      fprintf(f, "\\u%04x", *p);
    else
      fputc(*p, f);
  }
  fputc('"', f);
}
