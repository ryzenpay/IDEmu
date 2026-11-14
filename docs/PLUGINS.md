# Plugins (drop folder `plugins/`)

A plugin is **one package in this folder** with up to two halves. The **browser/server half** —
what this document covers — extends the IDEmu machine itself: tabs in the web interface, calls to
the local API, optionally python code inside the server. The **in-car half** (`pre.sh`, `boot.sh`,
`lib/`, `data/`) runs inside the emulated head unit, like a tweak installed over SSH into a real
car; its full contract is [GUESTPLUGINS.md](GUESTPLUGINS.md). One package can be browser-only
(the usual case), in-car-only (e.g. `can-log`), or both (e.g. `carplay-nav`, `sport-displays`).
The loaders ignore whichever half a package does not have, and the same `plugin.json` describes both.

(Firmware test fixtures in `idemu/plugins/` are unrelated internal material the builder bakes to
`/plug/<Name>/*` for HMI development.)

## Installing

Drop a package into the `plugins/` folder at the repository root and rescan
(reload the web UI, or `POST /api/plugins/rescan`). Two shapes are accepted:

```
plugins/
├── meutool.zip              ← zip with plugin.json at the root (or inside one wrapper folder)
└── my-other-tool/           ← loose folder with plugin.json at its root
    ├── plugin.json
    └── main.js
```

Zips are unpacked to `plugins/.installed/<id>/` and re-unpacked when the zip file changes
(mtime+size stamp in `.idemu-src`). Loose folders are used in place — edit and reload. Files are
served read-only at `http://127.0.0.1:8765/plugins/<id>/<file>`.

Anything else in the folder (random zips, files without a `plugin.json`) is ignored. Packages
with problems are skipped, never break the IDE, and are listed with the reason under `problems`
in `GET /api/plugins`.

## `plugin.json`

| Key | Meaning |
|---|---|
| `id` | internal id (`[a-z0-9_-]{1,32}`); defaults to the file/folder name |
| `name` / `version` / `description` | shown by the UI (`GET /api/plugins`) |
| `scripts` | js files to load into the page, in order; default: every `*.js` at the package root, sorted by name |
| `styles` | css files to load; default: every `*.css` at the package root |
| `python` | module (path inside the package) imported by the server — see below |

Scripts load sequentially after the page's own code, so `IDE` (and `IDE.tabDefs`, `IDE.api`, …)
already exist when they run. Labels are author text: put your own translations in the plugin.

## Tab API

```js
IDE.registerTab({
  id: 'meutool',                // same id rules; must be unique
  label: 'My tool',             // tab button text
  icon: 'wrench',               // any icon name from idemu/web/util.js (unknown → wrench)
  mount(host, ctx) {            // called on first show; host is a div filling the tab body
    // build UI into `host`...
    return {
      show() {},                // tab became visible
      hide() {},                // tab hidden (keep your state; you are not destroyed)
      onStatus(status) {},      // optional: same status object as GET /api/run/status, ~4/s while booting
      destroy() {},             // optional: run screen torn down — release anything heavy
    };
  },
});
```

`ctx` is `{ status(), running(), booted() }`. The tab button is always visible (unlike the built-in
CAN/GPS tabs, which hide per generation) — use `ctx.running()` inside your UI. Everything the GUI
uses is available: `IDE.api(url)` / `IDE.post(url, body)` for the local REST API (docs/API.md),
`IDE.t()` for translation, `IDE.on(ev, fn)` events (`plugins:loaded` fires once after scanning).

## Python hook (optional, advanced)

`"python": "server.py"` inside the package: the module is imported by the IDEmu server at scan
time and `register(api)` is called once, with `api.id`, `api.dir` (unpacked folder) and `api.app`
(the server `App` — environments, runtime, threads). It has the same trust level as any script in
`tools/`: **full access to this machine**. Register HTTP routes by importing from `idemu.server`
only for read-only state, or expose your own unix socket; the hook contract stays deliberately thin
for now. A raising `register()` disables just that plugin (`problems` reports `python: …`).

## Security (why some zips are rejected)

Unpacking is guarded because the zip comes from outside: relative member paths only, `..` escapes
and absolute/drive paths rejected, symlink members rejected, at most 4096 files and 256 MB
uncompressed. Served files cannot leave the package folder (`/plugins/../` → 404). The web server
stays bound to 127.0.0.1. None of this limits what an *installed* plugin can do — install plugins
you trust.

## Testing a plugin without restarting

```sh
curl -XPOST http://127.0.0.1:8765/api/plugins/rescan
curl -s       http://127.0.0.1:8765/api/plugins | python3 -m json.tool
```

Reload the browser to re-run the plugin scripts. `tests/test_plugins.py` covers the packaging
rules above.
