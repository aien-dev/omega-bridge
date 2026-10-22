/* SPDX-License-Identifier: AGPL-3.0-only */
/* Unprivileged Linux probe boundary. No writable filesystem grants or sockets.
 * Failure to establish either restriction refuses the probe. */
#include "host.h"
#include <errno.h>
#include <linux/audit.h>
#include <linux/filter.h>
#include <linux/landlock.h>
#include <linux/seccomp.h>
#include <stddef.h>
#include <sys/ioctl.h>
#include <sys/prctl.h>
#include <sys/syscall.h>
#include <unistd.h>
#define DENY_CALL(number)                                                      \
  BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, (number), 0, 1),                         \
      BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | EACCES)
int restrict_probe(void) {
  if (prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0))
    return -1;
  int version = (int)syscall(SYS_landlock_create_ruleset, NULL, 0,
                             LANDLOCK_CREATE_RULESET_VERSION);
  if (version < 3)
    return -1;
  struct landlock_ruleset_attr rules = {
      .handled_access_fs =
          LANDLOCK_ACCESS_FS_WRITE_FILE | LANDLOCK_ACCESS_FS_REMOVE_DIR |
          LANDLOCK_ACCESS_FS_REMOVE_FILE | LANDLOCK_ACCESS_FS_MAKE_CHAR |
          LANDLOCK_ACCESS_FS_MAKE_DIR | LANDLOCK_ACCESS_FS_MAKE_REG |
          LANDLOCK_ACCESS_FS_MAKE_SOCK | LANDLOCK_ACCESS_FS_MAKE_FIFO |
          LANDLOCK_ACCESS_FS_MAKE_BLOCK | LANDLOCK_ACCESS_FS_MAKE_SYM};
  if (version >= 2)
    rules.handled_access_fs |= LANDLOCK_ACCESS_FS_REFER;
#ifdef LANDLOCK_ACCESS_FS_TRUNCATE
  if (version >= 3)
    rules.handled_access_fs |= LANDLOCK_ACCESS_FS_TRUNCATE;
#endif
  int fd = (int)syscall(SYS_landlock_create_ruleset, &rules, sizeof rules, 0);
  if (fd < 0)
    return -1;
  int rc = (int)syscall(SYS_landlock_restrict_self, fd, 0);
  close(fd);
  if (rc)
    return -1;
  const struct sock_filter filter[] = {
      BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, arch)),
#if defined(__aarch64__)
      BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, AUDIT_ARCH_AARCH64, 1, 0),
#elif defined(__x86_64__)
      BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, AUDIT_ARCH_X86_64, 1, 0),
#else
#error Unqualified probe architecture
#endif
      BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_KILL_PROCESS),
      BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, nr)),
      DENY_CALL(SYS_socket), DENY_CALL(SYS_socketpair), DENY_CALL(SYS_connect),
      DENY_CALL(SYS_fchmod), DENY_CALL(SYS_fchmodat), DENY_CALL(SYS_fchown),
      DENY_CALL(SYS_fchownat), DENY_CALL(SYS_utimensat),
      DENY_CALL(SYS_setxattr), DENY_CALL(SYS_lsetxattr),
      DENY_CALL(SYS_fsetxattr), DENY_CALL(SYS_removexattr),
      DENY_CALL(SYS_lremovexattr), DENY_CALL(SYS_fremovexattr),
      DENY_CALL(SYS_mount), DENY_CALL(SYS_umount2), DENY_CALL(SYS_ptrace),
      /* Permit descriptor flag operations needed for ordinary stdio pipes.
         Device-specific requests remain denied. */
      BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, SYS_ioctl, 0, 6),
      BPF_STMT(BPF_LD | BPF_W | BPF_ABS,
               offsetof(struct seccomp_data, args[1])),
      BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, FIONBIO, 3, 0),
      BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, FIOCLEX, 2, 0),
      BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, FIONCLEX, 1, 0),
      BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | EACCES),
      BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW), DENY_CALL(SYS_truncate),
      DENY_CALL(SYS_ftruncate),
#ifdef SYS_fchmodat2
      DENY_CALL(SYS_fchmodat2),
#endif
#ifdef SYS_io_uring_setup
      DENY_CALL(SYS_io_uring_setup), DENY_CALL(SYS_io_uring_enter),
      DENY_CALL(SYS_io_uring_register),
#endif
#ifdef SYS_chmod
      DENY_CALL(SYS_chmod),
#endif
#ifdef SYS_chown
      DENY_CALL(SYS_chown),
#endif
#ifdef SYS_lchown
      DENY_CALL(SYS_lchown),
#endif
#ifdef SYS_utime
      DENY_CALL(SYS_utime),
#endif
#ifdef SYS_utimes
      DENY_CALL(SYS_utimes),
#endif
#ifdef SYS_futimesat
      DENY_CALL(SYS_futimesat),
#endif
      BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW)};
  struct sock_fprog program = {.len = (unsigned short)ARRAY_LEN(filter),
                               .filter = (struct sock_filter *)filter};
  return prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, &program);
}
