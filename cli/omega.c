/* SPDX-License-Identifier: AGPL-3.0-only */
/* Disclosed Linux host boundary; semantic eligibility stays in Omega. */
#include "host.h"
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/inotify.h>
#include <sys/wait.h>
#include <unistd.h>
static volatile sig_atomic_t stop_requested;
static void on_signal(int signo) {
  (void)signo;
  stop_requested = 1;
}
static void state_path(char *p, const char *name) {
  join(p, PATH_MAX, ctx.state, name);
}
static int enabled(void) {
  char p[PATH_MAX];
  state_path(p, "enabled");
  return exists(p);
}
static int enrolled(void) {
  char p[PATH_MAX];
  state_path(p, "config");
  return exists(p);
}
int watcher_running(long *pid) {
  char p[PATH_MAX];
  state_path(p, "watch.lock");
  int fd = open(p, O_RDWR | O_CLOEXEC | O_NOFOLLOW);
  if (fd < 0)
    return 0;
  int running = flock(fd, LOCK_EX | LOCK_NB) < 0 &&
                (errno == EWOULDBLOCK || errno == EAGAIN);
  close(fd);
  if (pid) {
    *pid = 0;
    if (running) {
      state_path(p, "pid");
      char *b = slurp(p, NULL);
      if (b) {
        *pid = strtol(b, NULL, 10);
        free(b);
      }
    }
  }
  return running;
}
void emit_status(int fresh) {
  long pid = 0;
  int running = watcher_running(&pid);
  fprintf(stdout,
          "{\"schema\":1,\"converter\":\"NOT_AVAILABLE\",\"enrolled\":%s,"
          "\"enabled\":%s,\"watcher\":\"%s\",\"watcher_pid\":%ld,",
          enrolled() ? "true" : "false", enabled() ? "true" : "false",
          running ? "RUNNING" : "STOPPED", pid);
  if (fresh)
    inventory_json(stdout);
  else {
    char p[PATH_MAX];
    state_path(p, "inventory");
    char *b = slurp(p, NULL);
    if (b) {
      fputs(b, stdout);
      free(b);
    } else
      fputs("\"inventory\":[],\"warnings\":[]", stdout);
  }
  fputs("}\n", stdout);
}
static char *desktop_text(size_t *len) {
  char *b = NULL;
  FILE *f = open_memstream(&b, len);
  if (!f)
    die("cannot format desktop entry");
  fputs("[Desktop Entry]\nType=Application\nName=Omega "
        "discovery\nComment=Discover enrolled language environments\nExec=\"",
        f);
  for (const char *p = ctx.self; *p; p++) {
    if (*p == '%')
      fputc('%', f);
    if (*p == '\\')
      fputs("\\\\\\\\", f);
    else {
      if (*p == '"' || *p == '$' || *p == '`')
        fputs("\\\\", f);
      fputc(*p, f);
    }
  }
  fputs("\" watch\nTerminal=false\nX-GNOME-Autostart-enabled=true\n", f);
  fclose(f);
  return b;
}
static void check_desktop(int require_expected) {
  if (!exists(ctx.desktop))
    return;
  char p[PATH_MAX];
  state_path(p, "desktop.expected");
  size_t n = 0, m = 0;
  char *expected = slurp(p, &n), *actual = slurp(ctx.desktop, &m);
  if (!actual || !expected || m != n || memcmp(expected, actual, n)) {
    free(expected);
    free(actual);
    if (require_expected)
      die("existing or modified desktop entry preserved; enrollment refused");
    die("modified desktop entry preserved; uninstall refused");
  }
  free(expected);
  free(actual);
}
static void write_desktop(void) {
  check_desktop(1);
  char dir[PATH_MAX];
  join(dir, sizeof dir, ctx.home, ".config/autostart");
  ensure_dir(dir);
  size_t n;
  char *b = desktop_text(&n);
  /* A different launcher location needs an explicit uninstall/reinstall. */
  char p[PATH_MAX];
  state_path(p, "desktop.expected");
  if (exists(p)) {
    size_t m;
    char *old = slurp(p, &m);
    if (!old || m != n || memcmp(old, b, n)) {
      free(old);
      free(b);
      die("launcher location changed; uninstall prior enrollment first");
    }
    free(old);
  }
  atomic_write(p, b, n, 0600);
  atomic_write(ctx.desktop, b, n, 0600);
  free(b);
}
static int notification_fd(void) {
#ifdef OMEGA_ATTACH_TESTING
  if (getenv("OMEGA_ATTACH_NO_INOTIFY"))
    return -1;
#endif
  int fd = inotify_init1(IN_CLOEXEC | IN_NONBLOCK);
  if (fd < 0)
    return -1;
  for (size_t i = 0; i < inventory.ndirs; i++)
    (void)inotify_add_watch(fd, inventory.dirs[i],
                            IN_CREATE | IN_DELETE | IN_MOVED_FROM |
                                IN_MOVED_TO | IN_CLOSE_WRITE | IN_ATTRIB |
                                IN_DELETE_SELF | IN_MOVE_SELF);
  char p[PATH_MAX];
  state_path(p, "notify");
  (void)inotify_add_watch(
      fd, p, IN_MODIFY | IN_CLOSE_WRITE | IN_DELETE_SELF | IN_MOVE_SELF);
  return fd;
}
static int test_delay(const char *name, int fallback, int minimum) {
#ifdef OMEGA_ATTACH_TESTING
  const char *v = getenv(name);
  if (v) {
    int n = atoi(v);
    if (n >= minimum && n <= 60000)
      return n;
  }
#else
  (void)name;
  (void)minimum;
#endif
  return fallback;
}
static void watcher(int readyfd, int initial_scan) {
  if (ctx.lockfd >= 0) {
    close(ctx.lockfd);
    ctx.lockfd = -1;
  }
  ctx.transaction = 0;
  char p[PATH_MAX];
  state_path(p, "watch.lock");
  int lock = open(p, O_RDWR | O_CLOEXEC | O_NOFOLLOW);
  if (lock < 0 || flock(lock, LOCK_EX | LOCK_NB)) {
    if (readyfd >= 0)
      close(readyfd);
    exit(0);
  }
  signal(SIGTERM, on_signal);
  signal(SIGINT, on_signal);
  signal(SIGHUP, on_signal);
  char pid[32];
  int n = snprintf(pid, sizeof pid, "%ld\n", (long)getpid());
  state_path(p, "pid");
  atomic_write(p, pid, (size_t)n, 0600);
  if (initial_scan) {
    load_config();
    check_policy();
    scan(1);
    write_inventory();
  }
  int fd = notification_fd();
  int interval = test_delay("OMEGA_ATTACH_INTERVAL_MS", 60000, 100),
      debounce = test_delay("OMEGA_ATTACH_DEBOUNCE_MS", 300, 30);
  int minimum_scan_gap = test_delay("OMEGA_ATTACH_MIN_SCAN_MS", 5000, 100);
  int poll_ms = debounce < 1000 ? debounce : 1000;
  char notice_path[PATH_MAX];
  state_path(notice_path, "notify");
  struct stat last_notice = {0};
  (void)stat(notice_path, &last_notice);
  if (readyfd >= 0) {
    ssize_t sent = write(readyfd, "R", 1);
    close(readyfd);
    if (sent != 1)
      exit(1);
  }
  long long next = monotonic_ms() + interval, dirty = 0;
  long long earliest = monotonic_ms() + minimum_scan_gap;
  int force_refresh = 0;
  while (!stop_requested && enabled()) {
    struct pollfd poller = {fd, POLLIN, 0};
    (void)poll(&poller, fd < 0 ? 0 : 1, poll_ms);
    long long now = monotonic_ms();
    struct stat notice;
    if (!stat(notice_path, &notice) &&
        (notice.st_ino != last_notice.st_ino ||
         notice.st_mtim.tv_sec != last_notice.st_mtim.tv_sec ||
         notice.st_mtim.tv_nsec != last_notice.st_mtim.tv_nsec)) {
      last_notice = notice;
      force_refresh = 1;
      if (!dirty)
        dirty = now;
    }
    if (fd >= 0 && (poller.revents & POLLIN)) {
      char events[8192];
      ssize_t got;
      int changed = 0;
      while ((got = read(fd, events, sizeof events)) > 0) {
        for (size_t at = 0; at < (size_t)got;) {
          struct inotify_event *e =
              (struct inotify_event *)(void *)(events + at);
          if (!(e->mask & IN_IGNORED))
            changed = 1;
          at += sizeof(*e) + e->len;
        }
      }
      if (changed && !dirty)
        dirty = now;
    }
    if (((dirty && now - dirty >= debounce) || now >= next) &&
        now >= earliest) {
      if (!enabled())
        break;
      load_config();
      if (force_refresh)
        invalidate_cache();
      scan(1);
      write_inventory();
      if (fd >= 0)
        close(fd);
      fd = notification_fd();
      next = monotonic_ms() + interval;
      earliest = monotonic_ms() + minimum_scan_gap;
      dirty = 0;
      force_refresh = 0;
    }
  }
  if (fd >= 0)
    close(fd);
  close(lock);
  exit(0);
}
static void start_watcher(void) {
  if (watcher_running(NULL))
    return;
#ifdef OMEGA_ATTACH_TESTING
  if (getenv("OMEGA_ATTACH_FAIL") &&
      !strcmp(getenv("OMEGA_ATTACH_FAIL"), "watcher"))
    die("injected watcher startup failure");
#endif
  char pidpath[PATH_MAX];
  state_path(pidpath, "pid");
  remember(pidpath);
  int ready[2];
  if (pipe2(ready, O_CLOEXEC))
    die("cannot create watcher startup channel");
  fflush(NULL);
  pid_t pid = fork();
  if (pid < 0)
    die("cannot start user watcher");
  if (pid == 0) {
    close(ready[0]);
    if (setsid() < 0)
      _exit(1);
    int null = open("/dev/null", O_RDWR);
    if (null < 0)
      _exit(1);
    (void)dup2(null, 0);
    (void)dup2(null, 1);
    (void)dup2(null, 2);
    if (null > 2)
      close(null);
    if (ready[1] > 3)
      (void)close_range(3, (unsigned)ready[1] - 1, 0);
    (void)close_range((unsigned)ready[1] + 1, ~0U, 0);
    ctx.lockfd = -1;
    watcher(ready[1], 0);
  }
  close(ready[1]);
  struct pollfd p = {ready[0], POLLIN, 0};
  char c = 0;
  int ok = poll(&p, 1, 2000) > 0 && read(ready[0], &c, 1) == 1 && c == 'R';
  close(ready[0]);
  if (!ok) {
    (void)waitpid(pid, NULL, WNOHANG);
    die("watcher failed to start; enrollment rolled back");
  }
}
static void stop_watcher(void) {
  char p[PATH_MAX];
  state_path(p, "enabled");
  if (exists(p))
    remove_owned(p);
  long long deadline = monotonic_ms() + 9000;
  while (watcher_running(NULL)) {
    if (monotonic_ms() > deadline)
      die("watcher did not stop within bound; files preserved");
    (void)poll(NULL, 0, 20);
  }
}
static void disable_internal(void) {
  stop_watcher();
  clear_hooks();
  char p[PATH_MAX];
  state_path(p, "inventory");
  /* Revocation must work even when the policy or configuration is damaged.
     Drop cached attachment claims once hooks have been removed. */
  if (exists(p))
    remove_owned(p);
}
static void attach(int use_saved) {
  check_policy();
  begin_transaction();
  if (use_saved) {
    if (!enrolled())
      die("attach once before enable");
    load_config();
  } else
    save_config();
  write_desktop();
  char p[PATH_MAX];
  state_path(p, "hooks");
  ensure_dir(p);
  state_path(p, "watch.lock");
  if (!exists(p))
    atomic_write(p, "", 0, 0600);
  state_path(p, "notify");
  if (!exists(p))
    atomic_write(p, "", 0, 0600);
  state_path(p, "enabled");
  atomic_write(p, "OMEGA_ENROLLED_V1\n", 18, 0600);
  if (!watcher_running(NULL)) {
    scan(1);
    write_inventory();
    start_watcher();
  }
  commit_transaction();
  emit_status(0);
}
static const char *command_names[] = {"om", "omg"};
struct installation {
  char bindir[PATH_MAX], libdir[PATH_MAX], links[2][PATH_MAX];
  char binary[PATH_MAX], policy[PATH_MAX], receipt[PATH_MAX];
};
static void install_paths(struct installation *i) {
  join(i->bindir, sizeof i->bindir, ctx.home, ".local/bin");
  join(i->libdir, sizeof i->libdir, ctx.home, ".local/lib/omega-attach");
  join(i->binary, sizeof i->binary, i->libdir, "om");
  join(i->policy, sizeof i->policy, i->libdir, "attachment-policy");
  join(i->receipt, sizeof i->receipt, i->libdir, "install.receipt");
  for (size_t n = 0; n < ARRAY_LEN(command_names); n++)
    join(i->links[n], PATH_MAX, i->bindir, command_names[n]);
}
static int verify_install(struct installation *i) {
  validate_managed_path(i->receipt);
  if (!exists(i->receipt)) {
    if (exists(i->libdir))
      die("unrecognized installation directory preserved");
    return 0;
  }
  char *b = slurp(i->receipt, NULL);
  unsigned long long h1, h2;
  char tail;
  if (!b ||
      sscanf(b, "OMEGA_INSTALL_V1\n%llx %llx\n%c", &h1, &h2, &tail) != 2 ||
      fingerprint(i->binary) != h1 || fingerprint(i->policy) != h2) {
    free(b);
    die("modified installation preserved; uninstall refused");
  }
  free(b);
  for (size_t n = 0; n < ARRAY_LEN(command_names); n++) {
    validate_managed_path(i->links[n]);
    char target[PATH_MAX];
    ssize_t len = readlink(i->links[n], target, sizeof target - 1);
    if (len < 0)
      die("modified launcher link preserved");
    target[len] = 0;
    if (strcmp(target, i->binary))
      die("modified launcher link preserved");
  }
  return 1;
}
static void bootstrap(void) {
  check_policy();
  struct installation i;
  install_paths(&i);
  if (verify_install(&i)) {
    if (fingerprint(i.binary) != fingerprint(ctx.self) ||
        fingerprint(i.policy) != fingerprint(ctx.policy))
      die("different installed release preserved; uninstall before upgrade");
    fputs("om and omg already installed; shared enrollment preserved\n",
          stdout);
    return;
  }
  for (size_t n = 0; n < ARRAY_LEN(command_names); n++)
    if (exists(i.links[n]))
      die("existing om or omg command preserved");
  char *path = strdup(getenv("PATH") ? getenv("PATH") : "");
  if (!path)
    die("out of memory");
  char *remaining = path, *part;
  while ((part = strsep(&remaining, ":"))) {
    char dir[PATH_MAX];
    if (!realpath(*part ? part : ".", dir))
      continue;
    for (size_t n = 0; n < ARRAY_LEN(command_names); n++) {
      char p[PATH_MAX];
      join(p, sizeof p, dir, command_names[n]);
      if (!access(p, X_OK)) {
        free(path);
        die("existing om or omg has no checked extension; preserved");
      }
    }
  }
  free(path);
  begin_transaction();
  ensure_dir(i.bindir);
  ensure_dir(i.libdir);
  size_t len;
  char *b = slurp(ctx.self, &len);
  if (!b)
    die("cannot read launcher");
  atomic_write(i.binary, b, len, 0755);
  free(b);
  b = slurp(ctx.policy, &len);
  if (!b)
    die("cannot read native Omega policy");
  atomic_write(i.policy, b, len, 0755);
  free(b);
  char hashes[128];
  int n = snprintf(hashes, sizeof hashes, "OMEGA_INSTALL_V1\n%016llx %016llx\n",
                   (unsigned long long)fingerprint(i.binary),
                   (unsigned long long)fingerprint(i.policy));
  atomic_write(i.receipt, hashes, (size_t)n, 0600);
  for (size_t j = 0; j < ARRAY_LEN(command_names); j++) {
    remember(i.links[j]);
    if (symlink(i.binary, i.links[j]))
      die("cannot install om and omg aliases");
  }
#ifdef OMEGA_ATTACH_TESTING
  if (getenv("OMEGA_ATTACH_FAIL") &&
      !strcmp(getenv("OMEGA_ATTACH_FAIL"), "bootstrap"))
    die("injected bootstrap failure");
#endif
  commit_transaction();
  printf("om and omg installed in %s; no enrollment or watcher started\n",
         i.bindir);
  int onpath = 0;
  path = strdup(getenv("PATH") ? getenv("PATH") : "");
  if (!path)
    die("out of memory");
  remaining = path;
  while ((part = strsep(&remaining, ":")))
    if (!strcmp(part, i.bindir))
      onpath = 1;
  free(path);
  if (!onpath)
    fputs(".local/bin is absent from PATH; shell configuration was preserved\n",
          stdout);
}
static void uninstall(void) {
  if (!exists(ctx.state)) {
    fputs("omega enrollment absent\n", stdout);
    return;
  }
  verify_owner();
  load_dirs();
  char p[PATH_MAX];
  state_path(p, "lock");
  ctx.lockfd = open(p, O_RDWR | O_CLOEXEC | O_NOFOLLOW);
  if (ctx.lockfd < 0 || flock(ctx.lockfd, LOCK_EX | LOCK_NB))
    die("cannot lock enrollment for uninstall");
  check_desktop(0);
  struct installation installed_paths;
  install_paths(&installed_paths);
  int installed = verify_install(&installed_paths);
  disable_internal();
  if (exists(ctx.desktop))
    remove_owned(ctx.desktop);
  if (installed) {
    for (size_t n = 0; n < ARRAY_LEN(command_names); n++)
      if (unlink(installed_paths.links[n]))
        die("cannot remove owned launcher link");
    remove_owned(installed_paths.binary);
    remove_owned(installed_paths.policy);
    remove_owned(installed_paths.receipt);
  }
  const char *files[] = {
      "enabled",    "config",           "inventory",    "notify", "pid",
      "watch.lock", "desktop.expected", "created-dirs", "owner",  "lock"};
  for (size_t i = 0; i < ARRAY_LEN(files); i++) {
    state_path(p, files[i]);
    if (exists(p))
      remove_owned(p);
  }
  for (size_t i = ctx.ndirs; i > 0; i--)
    (void)rmdir(ctx.dirs[i - 1]);
  fputs("omega enrollment removed; previous files preserved\n", stdout);
}
int main(int argc, char **argv) {
  signal(SIGPIPE, SIG_IGN);
  init_context();
  if (argc != 2) {
    fputs("usage: om (equivalent alias: omg) "
          "discover|attach|status|enable|disable|notify|watch|bootstrap|"
          "uninstall\n",
          stderr);
    return 2;
  }
  const char *command = argv[1];
  if (!strcmp(command, "discover")) {
    check_policy();
    scan(0);
    emit_status(1);
  } else if (!strcmp(command, "status"))
    emit_status(0);
  else if (!strcmp(command, "attach"))
    attach(0);
  else if (!strcmp(command, "enable"))
    attach(1);
  else if (!strcmp(command, "disable")) {
    if (exists(ctx.state)) {
      begin_transaction();
      disable_internal();
      commit_transaction();
    }
    emit_status(0);
  } else if (!strcmp(command, "notify")) {
    if (!enrolled())
      die("enrollment absent");
    char p[PATH_MAX];
    state_path(p, "notify");
    atomic_write(p, "notify\n", 7, 0600);
    emit_status(0);
  } else if (!strcmp(command, "watch")) {
    if (!enabled())
      return 0;
    load_config();
    check_policy();
    watcher(-1, 1);
  } else if (!strcmp(command, "bootstrap"))
    bootstrap();
  else if (!strcmp(command, "uninstall"))
    uninstall();
  else {
    fputs("unknown omega attachment command\n", stderr);
    return 2;
  }
  return 0;
}
