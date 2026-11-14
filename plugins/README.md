# plugins/ — every plugin lives here (drop folder)

One plugin, one folder (or zip), **two optional halves**:

| Half | Runs in | Files | Loader |
|---|---|---|---|
| Browser/server | IDEmu web UI + local server | `plugin.json`, `.js`, `.css`, python | `idemu/plugins.py`, hot-rescan |
| In-car | inside the emulated head unit | `pre.sh`, `boot.sh`, `lib/*.so`, `data/**` | `idemu/guestplugins.py` + boot hooks (built in — no loading code from you) |

A package can be browser-only, in-car-only, or both (e.g. `carplay-nav`: a tab that edits the
route, and a `navd.sh` that drives the guidance inside the QNX itself). Each loader ignores the
half a package doesn't have. Full docs: [browser/server](../docs/PLUGINS.md) ·
[in-car](../docs/GUESTPLUGINS.md).

Drop a plugin here and refresh the IDEmu web UI (or press *Scan* — `POST /api/plugins/rescan`).
A plugin is either

- a **zip** — `meutool.zip` containing `plugin.json` (+ files), or
- a **loose folder** — `meutool/plugin.json` (+ files; `plugin.json` optional for in-car-only
  packages, where the folder name is the id).

The UI lists what loaded in `GET /api/plugins` (in-car entries appear with `guest: true`); broken
packages are reported there with the reason and never stop the IDE. Installed zips are unpacked to
`.installed/<id>/` (regenerated when the zip changes) and their files are served at
`/plugins/<id>/<file>`. The in-car half is baked into `shim.img` for the next cold boot, or pushed
to the running car via `POST /api/guestplugins/install`.

Minimal browser plugin (adds a tab to the Run screen):

```json
{ "name": "My tool", "scripts": ["main.js"] }
```

```js
// main.js
IDE.registerTab({
  id: 'meutool', label: 'My tool', icon: 'wrench',
  mount(host, ctx) {
    host.textContent = ctx.running() ? 'head unit is running' : 'idle';
    return { show() {}, hide() {}, destroy() {}, onStatus(s) { host.textContent = s.state; } };
  },
});
```

Minimal in-car plugin (a daemon inside the head unit, browser closed):

```
plugins/my-tweak/boot.sh        #!/bin/ksh — start daemons with ( ksh helper.sh </dev/null >>/var/plug.log 2>&1 & )
```

Full formats, the python hook and the security rules: [docs/PLUGINS.md](../docs/PLUGINS.md),
[docs/GUESTPLUGINS.md](../docs/GUESTPLUGINS.md).

> Only plugins you trust: a plugin runs with full access to this machine (local files, the API,
> QEMU). A `python` entry in `plugin.json` executes arbitrary code inside the IDEmu server process,
> and `boot.sh` runs as root inside the emulated car.
