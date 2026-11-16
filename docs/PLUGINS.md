# Plugins — moved to the `idplugins` project

The plugin system (the two loaders, the docs and the `plugins/` drop folder) now lives in its own
project: [`../idplugins`](../idplugins). This document's full content is there:
**[idplugins/docs/PLUGINS.md](../idplugins/docs/PLUGINS.md)**.

Inside IDEmu nothing changed for users or code: `idemu/plugins.py` and `idemu/guestplugins.py` are
thin shims that re-export the project's loaders, `idemu/_plugins_home.py` locates it
(`$IDPLUGINS_HOME`, default: the sibling folder `../idplugins`), and the web UI / `/api/plugins*` /
shim-image bake work exactly as before.
