#!/bin/bash
# Compila os QEMU próprios do IDEmu (QEMU 11.1.2 oficial + os dispositivos/correções de src/qemu):
#   bin/qemu-system-x86_64  — iDrive 7: dispositivo `idemu-shm` + correção de migração do `sdhci-pci`
#   bin/qemu-system-arm     — iDrive 5/6: placa OMAP5 "omap5-uevm" (src/qemu/omap5-uevm.c + qemu-v11.1.2-idemu.patch)
#   bin/qemu-system-aarch64 — iDrive 8: `virt` com memory-backend-shm (o mais recente; evita depender do qemu do sistema)
#
# Uso: tools/qemu/build.sh <qemu-11.1.2.tar.xz> [python3.10+]
#   * O tarball oficial vem de https://download.qemu.org (o script não baixa nada).
#   * Linux:  apt install build-essential pkg-config ninja-build libglib2.0-dev libpixman-1-dev libfdt-dev flex bison
#     (meson >= 0.63: no Ubuntu 22.04, pip3 install --user meson)
#   * macOS:  brew install ninja pkg-config glib pixman; um Python >= 3.10 (o 3.9 da Apple não serve ao configure)
set -e
TAR=${1:?uso: build.sh <qemu-11.1.2.tar.xz> [python]}
if [ "$(uname)" = Darwin ]; then PY=${2:-$(command -v python3.12 || command -v python3.11 || command -v python3.10 || true)}; [ -n "$PY" ] || { echo "preciso de um Python >= 3.10 (segundo argumento)"; exit 1; }; else PY=${2:-$(command -v python3)}; fi
HERE=$(cd "$(dirname "$0")" && pwd); ROOT=$(dirname "$(dirname "$HERE")"); W=${QEMU_BUILD_DIR:-$HOME/idemu-qemu}
command -v ninja >/dev/null || { echo "falta o ninja (apt install ninja-build / brew install ninja)"; exit 1; }
command -v meson >/dev/null || [ -x "$HOME/.local/bin/meson" ] || { echo "falta o meson >= 0.63 (apt install meson; no Ubuntu 22.04: pip3 install --user meson)"; exit 1; }
[ -x "$HOME/.local/bin/meson" ] && export PATH="$HOME/.local/bin:$PATH"
mkdir -p "$W" && cd "$W" && [ -d qemu-11.1.2 ] || tar xf "$TAR"
SRC=$W/qemu-11.1.2
cp "$ROOT/src/qemu/idemu-shm.c" "$SRC/hw/misc/idemu-shm.c"
cp "$ROOT/src/qemu/sdhci-pci.c" "$SRC/hw/sd/sdhci-pci.c"
grep -q IDEMU_SHM "$SRC/hw/misc/Kconfig" || python3 - "$SRC" <<'PYEOF'
import sys
s = sys.argv[1]
p = s + '/hw/misc/Kconfig'; t = open(p).read(); t = t.replace('config PCI_TESTDEV\n', 'config IDEMU_SHM\n    bool\n    default y if PCI_DEVICES\n    depends on PCI\n\nconfig PCI_TESTDEV\n', 1); open(p, 'w').write(t)
p = s + '/hw/misc/meson.build'; t = open(p).read(); t = t.replace("system_ss.add(when: 'CONFIG_PCI_TESTDEV'", "system_ss.add(when: 'CONFIG_IDEMU_SHM', if_true: files('idemu-shm.c'))\nsystem_ss.add(when: 'CONFIG_PCI_TESTDEV'", 1); open(p, 'w').write(t)
PYEOF
# placa OMAP5 do iDrive 5/6: o patch registra hw/arm/omap5-uevm.c no Kconfig/meson; o arquivo em si vem de src/qemu
cp "$ROOT/src/qemu/omap5-uevm.c" "$SRC/hw/arm/omap5-uevm.c"
grep -q OMAP5_UEVM "$SRC/hw/arm/Kconfig" || patch -d "$SRC" -p1 -i "$ROOT/src/qemu/qemu-v11.1.2-idemu.patch"
mkdir -p "$W/build" && cd "$W/build"
[ -f build.ninja ] || "$SRC/configure" --python="$PY" --target-list=x86_64-softmmu,arm-softmmu,aarch64-softmmu --disable-docs --disable-guest-agent --disable-tools --disable-gtk --disable-sdl --disable-vnc --disable-curses --disable-rust --disable-user --disable-linux-user --disable-bsd-user --without-default-features --enable-tcg
ninja qemu-system-x86_64 qemu-system-arm qemu-system-aarch64
mkdir -p "$ROOT/bin"
# o macOS mata (SIGKILL) um executável sobrescrito no mesmo arquivo: copia para um nome novo e troca (inofensivo no Linux)
for b in qemu-system-x86_64 qemu-system-arm qemu-system-aarch64; do cp "$b" "$ROOT/bin/$b.new" && mv "$ROOT/bin/$b.new" "$ROOT/bin/$b"; done
mkdir -p "$ROOT/bin/qemu-share" && for f in bios-256k.bin vgabios-stdvga.bin linuxboot_dma.bin kvmvapic.bin; do cp "$SRC/pc-bios/$f" "$ROOT/bin/qemu-share/"; done
"$ROOT/bin/qemu-system-x86_64" -device help 2>&1 | grep -q idemu-shm && echo "ok: bin/qemu-system-x86_64 com o dispositivo idemu-shm"
"$ROOT/bin/qemu-system-arm" -machine help 2>&1 | grep -q omap5-uevm && echo "ok: bin/qemu-system-arm com a placa omap5-uevm"
echo "ok: bin/ com qemu-system-x86_64, qemu-system-arm e qemu-system-aarch64"
