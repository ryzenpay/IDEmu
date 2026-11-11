#!/bin/bash
# Compila o renderizador do host (bin/glhost).
set -e
cd "$(dirname "$0")"
mkdir -p ../../bin
cp ../shim/glops.h ../shim/gen_host.inc ../shim/opnames.inc ../shim/gl_hand_names.inc . 2>/dev/null || true
if [ "$(uname)" = Darwin ]; then
  clang -O2 -Wno-everything host.c pngload.c -framework GLUT -framework OpenGL -framework ApplicationServices -framework CoreFoundation -o ../../bin/glhost
else
  # apt install freeglut3-dev libgl1-mesa-dev libglew-dev libx11-dev
  cc -O2 -Wno-everything host.c pngload.c -o ../../bin/glhost -lGLEW -lglut -lGL -lX11 -lm -ldl -lpthread
fi
ls -l ../../bin/glhost
