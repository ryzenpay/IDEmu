# plugins/ — host extensions (drop folder)

Drop a plugin here and refresh the IDEmu web UI (or press *Scan* — `POST /api/plugins/rescan`).
A plugin is either

- a **zip** — `meutool.zip` containing `plugin.json` (+ `.js`/`.css`, optionally a python module), or
- a **loose folder** — `meutool/plugin.json` (+ files).

The UI lists what loaded in `GET /api/plugins`; broken packages are reported there with the reason
and never stop the IDE. Installed zips are unpacked to `.installed/<id>/` (regenerated when the zip
changes) and their files are served at `/plugins/<id>/<file>`.

Minimal plugin (adds a tab to the Run screen):

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

Full format, the python hook and the security rules: [docs/PLUGINS.md](../docs/PLUGINS.md).

> Only plugins you trust: a plugin runs with full access to this machine (local files, the API,
> QEMU). A `python` entry in `plugin.json` executes arbitrary code inside the IDEmu server process.
> (Note: this folder is for **host-side** extensions; guest-side QNX plugins live in
> `idemu/plugins/` and are injected into the emulated head unit by the builder.)
