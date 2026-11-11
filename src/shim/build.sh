#!/bin/bash
# Compila as bibliotecas de tradução do guest (ARMv7, freestanding) com clang + ld.lld (do rustup, do PATH ou do pacote ziglang).
# Uso: ./build.sh <libc.so.3 do firmware> [python-com-ziglang]   -> saída em ../../idemu/shim/lib
set -e
cd "$(dirname "$0")"
LIBC=${1:-$HOME/id6-extract/boot1_root/boot/lib/libc.so.3}
PY=${2:-$(command -v python3)}
OUT=../../idemu/shim/lib; mkdir -p lib out $OUT
[ -f "$LIBC" ] || { echo "falta o libc.so.3 do firmware (primeiro argumento): este build só é preciso para refazer os shims; os committed estão em idemu/shim/lib"; exit 1; }
python3 gen.py >/dev/null
cp "$LIBC" lib/libc.so.3
CF=(-target armv7-none-eabi -march=armv7-a -mfloat-abi=soft -ffreestanding -fPIC -Os -mno-unaligned-access -Wno-incompatible-library-redeclaration -Wno-builtin-requires-header -Wno-int-conversion -Wno-pointer-sign ${EXTRA_CF:-})
# ld.lld: o do ambiente, o do PATH, o do rustup (mac ou linux); senão o do pacote ziglang
LLD=${LLD:-$(command -v ld.lld || true)}
[ -n "$LLD" ] || LLD=$(ls "$HOME"/.rustup/toolchains/*/lib/rustlib/*/bin/gcc-ld/ld.lld 2>/dev/null | head -1)
if [ -x "$LLD" ]; then LDBIN=($LLD); else LDBIN=($PY -m ziglang ld.lld); fi
LD=($LDBIN -shared -z max-page-size=4096 -z common-page-size=4096 -z norelro -z noseparate-code --no-rosegment --hash-style=sysv --no-eh-frame-hdr -z nognustack)
for f in bridge gles egl dbg hook; do clang "${CF[@]}" -c $f.c -o out/$f.o; done
$LD -soname libscreen.so.1 -o out/libscreen.so.1 out/bridge.o out/gles.o out/egl.o out/dbg.o out/hook.o -Llib -l:libc.so.3
echo 'int dummy_sym;' > out/empty.c; clang "${CF[@]}" -c out/empty.c -o out/empty.o
$LD -soname libEGL.so.1 -o out/libEGL.so.1 out/empty.o -Llib -l:libc.so.3 -Lout -l:libscreen.so.1
$LD -soname libGLESv2.so.1 -o out/libGLESv2.so.1 out/empty.o -Llib -l:libc.so.3 -Lout -l:libscreen.so.1
clang "${CF[@]}" -c otf.c -o out/otf.o
$LD -soname libBMWOTFapi.so.3 -o out/libBMWOTFapi.so.3 out/otf.o -Llib -l:libc.so.3 -Lout -l:libscreen.so.1
clang "${CF[@]}" -c ilm.c -o out/ilm.o
$LD -soname libilmClient.gpp.so.1 -o out/libilmClient.gpp.so.1 out/ilm.o -Llib -l:libc.so.3 -Lout -l:libscreen.so.1
cp out/lib*.so* $OUT/
ls -l $OUT
