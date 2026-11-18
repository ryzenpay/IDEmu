#!/bin/bash
# Boot do container: settings.json persistido no volume /data, GUI sob um Xvfb proprio
# (o glhost usa GLX; o xvfb-run do Debian nao funciona como PID 1 de container).
set -e
mkdir -p /app/environments
# o servidor cria/grava settings.json no repo; ligamos ao volume para sobreviver a rebuilds
if [ ! -e /app/settings.json ] && [ ! -L /app/settings.json ]; then ln -s /data/settings.json /app/settings.json; fi

: "${XVFB_DISPLAY:=99}"
Xvfb ":$XVFB_DISPLAY" -screen 0 1280x1024x24 -nolisten tcp &
XVFB_PID=$!
for _ in $(seq 1 50); do
  [ -e "/tmp/.X11-unix/X${XVFB_DISPLAY}" ] && break
  sleep 0.2
done
[ -e "/tmp/.X11-unix/X${XVFB_DISPLAY}" ] || { echo "Xvfb não subiu" >&2; exit 1; }
export DISPLAY=":$XVFB_DISPLAY"
# sem GPU: renderização por software (llvmpipe) — LIBGL_ALWAYS_SOFTWARE já vem do ambiente
exec python3 /app/docker/serve.py
