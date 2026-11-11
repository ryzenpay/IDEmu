#!/bin/bash
# Abre o IDEmu. No macOS, duplo clique no Finder; no Linux (e WSL), ./IDEmu.command na terminal.
# Sem Electron instalado, cai no navegador (servidor Python).
cd "$(dirname "$0")"
export PATH="$HOME/.local/node/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
if [ -x electron/node_modules/.bin/electron ]; then
  exec electron/node_modules/.bin/electron electron
fi
echo "Electron não instalado (rode: cd electron && npm install). Abrindo no navegador."
exec python3 -m idemu gui
