#!/bin/bash
# Compila as peças do iDrive 7: as bibliotecas do guest x86-64 (clang + ld.lld, ligadas à libc-2.27 do firmware) e o renderizador do host (glhost7).
# Uso: ./build.sh <libc-2.27.so do MGU>
set -e; cd "$(dirname "$0")"; mkdir -p out/lib
LIBC=${1:-/tmp/mgu/rse/root/lib/libc-2.27.so}; cp "$LIBC" out/lib/libc.so.6
LLD=${LLD:-$(command -v ld.lld || true)}
[ -n "$LLD" ] || LLD=$(ls "$HOME"/.rustup/toolchains/*/lib/rustlib/*/bin/gcc-ld/ld.lld 2>/dev/null | head -1)
CF=(-target x86_64-linux-gnu -ffreestanding -fPIC -O1 -fno-stack-protector -Wno-incompatible-library-redeclaration -Wno-builtin-requires-header -Wno-implicit-function-declaration -Wno-empty-body)
for f in "$@"; do :; done
clang $CF -c wlstub.c -o out/wlstub.o
$LLD -pie -o out/idemu-wl --dynamic-linker /lib/ld-linux-x86-64.so.2 -e _start out/wlstub.o -Lout/lib -l:libc.so.6
clang $CF -c idemu_run.c -o out/idemu_run.o
$LLD -pie -o out/idemu-run --dynamic-linker /lib/ld-linux-x86-64.so.2 -e _start out/idemu_run.o -Lout/lib -l:libc.so.6
clang $CF -c lifecycle.c -o out/lifecycle.o
$LLD -pie -o out/idemu-lifecycle --dynamic-linker /lib/ld-linux-x86-64.so.2 -e _start out/lifecycle.o -Lout/lib -l:libc.so.6
ls -l out/idemu-wl
cp "$(dirname "$LIBC")/libdl-2.27.so" out/lib/libdl.so.2
python3 gen_gl.py >/dev/null
clang $CF -c gles_guest.c -o out/gles_guest.o
$LLD -shared -soname libGLESv2.so.2 -o out/libGLESv2.so.2 out/gles_guest.o -Lout/lib -l:libc.so.6 -l:libdl.so.2
echo 'int idemu_egl_stub;' > out/egl_stub.c; clang $CF -c out/egl_stub.c -o out/egl_stub.o
$LLD -shared -soname libEGL.so.1 -o out/libEGL.so.1 out/egl_stub.o --no-as-needed -Lout -l:libGLESv2.so.2
ls -l out/libGLESv2.so.2 out/libEGL.so.1
clang $CF -c fakeipc.c -o out/fakeipc.o
$LLD -shared -soname libipc.so.1 -o out/libipc.so.1 out/fakeipc.o -Lout/lib -l:libc.so.6
ls -l out/libipc.so.1
clang $CF -c fakesvc.c -o out/fakesvc.o
$LLD -pie -o out/idemu-fakesvc --dynamic-linker /lib/ld-linux-x86-64.so.2 -e _start out/fakesvc.o -Lout/lib -l:libc.so.6
ls -l out/idemu-fakesvc
clang $CF -c fastclock.c -o out/fastclock.o
$LLD -shared -soname libfastclock.so -o out/libfastclock.so out/fastclock.o
ls -l out/libfastclock.so
# o renderizador do host (bin/glhost7): OpenGL 4.1 core fora da tela (CGL no Mac, EGL no Linux)
mkdir -p ../../bin
if [ "$(uname)" = Darwin ]; then
  clang -O2 -Wno-everything glhost7.c -o out/glhost7 -framework OpenGL
else
  # apt install libglew-dev libegl1-mesa-dev libgl1-mesa-dev
  cc -O2 -Wno-everything glhost7.c -o out/glhost7 -lGLEW -lEGL -lGL -lm
fi
cp out/glhost7 ../../bin/glhost7.new && mv ../../bin/glhost7.new ../../bin/glhost7
ls -l ../../bin/glhost7
