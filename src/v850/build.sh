#!/bin/bash
# Compila o transporte io-ipc virtual (ARMv7, freestanding) -> ../../idemu/shim/lib/ioipc-idemu.so
# Uso: build.sh [python-com-ziglang] [libc.so.3 do firmware] [libsocket.so.3 do firmware]
set -e
cd "$(dirname "$0")"
PY=${1:-$(command -v python3)}
LIBC=${2:-../shim/lib/libc.so.3}
SOCK=${3:-/tmp/mgu/fatsrc2/lib/libsocket.so.3}
OUT=../../idemu/shim/lib; mkdir -p out $OUT
CF=(-target armv7-none-eabi -march=armv7-a -mfloat-abi=soft -ffreestanding -mno-unaligned-access -fPIC -Os -Wno-incompatible-library-redeclaration -Wno-builtin-requires-header)
LD=($PY -m ziglang ld.lld -shared -z max-page-size=4096 -z common-page-size=4096 -z norelro -z noseparate-code --no-rosegment --hash-style=sysv --no-eh-frame-hdr -z nognustack --allow-shlib-undefined)
if ! $PY -m ziglang version >/dev/null 2>&1; then
  LLD=${LLD:-$(command -v ld.lld || true)}
  [ -n "$LLD" ] || LLD=$(ls "$HOME"/.rustup/toolchains/*/lib/rustlib/*/bin/gcc-ld/ld.lld 2>/dev/null | head -1)
  [ -x "$LLD" ] || { echo "preciso do pacote ziglang ($PY -m ziglang) ou de um ld.lld (apt install lld)"; exit 1; }
  LD=($LLD -shared -z max-page-size=4096 -z common-page-size=4096 -z norelro -z noseparate-code --no-rosegment --hash-style=sysv --no-eh-frame-hdr -z nognustack --allow-shlib-undefined)
fi
cp "$SOCK" out/libsocket.so.3
clang "${CF[@]}" -c ioipc_idemu.c -o out/ioipc_idemu.o
$LD -soname ioipc-idemu.so -o out/ioipc-idemu.so out/ioipc_idemu.o -L$(dirname $LIBC) -l:libc.so.3
cp out/ioipc-idemu.so $OUT/
ls -l $OUT/ioipc-idemu.so
