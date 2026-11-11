#!/bin/bash
# Reconstrução rápida do glhost (passatempo de desenvolvimento) — agora só um atalho para o build.sh, que escolhe o sistema.
exec "$(cd "$(dirname "$0")/../glhost" && pwd)/build.sh"
