// Carregada no QEMU (no Mac, DYLD_INSERT_LIBRARIES; no Linux, LD_PRELOAD): faz o memory-backend-shm usar o objeto POSIX que run.py criou,
// para o mguhost enxergar a RAM do guest sem passar por arquivo.
#ifndef __APPLE__
#define _GNU_SOURCE           /* RTLD_NEXT (dlfcn) antes de qualquer include */
#endif
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
#ifdef __APPLE__
static int my_shm_open(const char *name, int flags, ...) {
  va_list ap; va_start(ap, flags); int mode = va_arg(ap, int); va_end(ap);
  const char *n = getenv("IDEMU_SHM_NAME");
  if (n) return shm_open(n, O_RDWR);
  return shm_open(name, flags, mode);
}
static int my_shm_unlink(const char *name) { if (getenv("IDEMU_SHM_NAME")) return 0; return shm_unlink(name); }
static int my_ftruncate(int fd, off_t len) {
  int r = ftruncate(fd, len);
  if (r && errno == EINVAL) { struct stat st; if (!fstat(fd, &st) && st.st_size == len) return 0; errno = EINVAL; }
  return r;
}
#define I(a, b) __attribute__((used, section("__DATA,__interpose"))) static struct { const void *n, *o; } in_##b = { a, b };
I(my_shm_open, shm_open) I(my_shm_unlink, shm_unlink) I(my_ftruncate, ftruncate)
#else
// LD_PRELOAD: os mesmos três envoltórios como símbolos exportados; o original é chamado via RTLD_NEXT, com /dev/shm e o syscall por baixo se ele faltar.
#include <dlfcn.h>
#include <sys/syscall.h>
static char *shm_path(const char *name) { static char path[600]; snprintf(path, sizeof path, "/dev/shm/%s", name + (name[0] == '/' ? 1 : 0)); return path; }
int shm_open(const char *name, int flags, ...) {
  va_list ap; va_start(ap, flags); int mode = va_arg(ap, int); va_end(ap);
  const char *n = getenv("IDEMU_SHM_NAME");
  if (n) { name = n; flags = O_RDWR; mode = 0600; }
  static int (*real)(const char *, int, ...);
  if (!real) real = (int (*)(const char *, int, ...)) dlsym(RTLD_NEXT, "shm_open");
  if (real) return real(name, flags, mode);
  return open(shm_path(name), flags | O_CREAT, mode);
}
int shm_unlink(const char *name) {
  if (getenv("IDEMU_SHM_NAME")) return 0;
  static int (*real)(const char *);
  if (!real) real = (int (*)(const char *)) dlsym(RTLD_NEXT, "shm_unlink");
  if (real) return real(name);
  return unlink(shm_path(name));
}
int ftruncate(int fd, off_t len) {
  static int (*real)(int, off_t);
  if (!real) real = (int (*)(int, off_t)) dlsym(RTLD_NEXT, "ftruncate");
  int r = real ? real(fd, len) : (int) syscall(SYS_ftruncate, fd, len);
  if (r && errno == EINVAL) { struct stat st; if (!fstat(fd, &st) && st.st_size == len) return 0; errno = EINVAL; }
  return r;
}
#endif
