# The in-car half of a plugin — running inside the head unit

A plugin in IDEmu is **one package in `plugins/`** with up to two halves: the browser/server half
(tabs, local API, python — [PLUGINS.md](PLUGINS.md)) and the **in-car half** documented here, which
runs *inside the emulated iDrive*, the way a tweak installed over SSH into a real head unit would.
It is not a browser tab: whatever it changes shows up on the head unit's own screen and in the
signals the HMI sends, exactly like factory behaviour. A plugin can be only one half, or both.

| Half | Where code runs | Part of the package | Loader |
|---|---|---|---|
| Browser/server | IDEmu web UI / local server | `plugin.json` + `.js`/`.css`/python | `idemu/plugins.py`, hot-rescan |
| **In-car** (this doc) | inside the QNX head unit (iDrive 5/6) | `pre.sh` / `boot.sh` / `lib/` / `data/` | `idemu/guestplugins.py` + `boot.sh` hooks (built-in — you do not write any loading code) |

(Firmware test fixtures in `idemu/plugins/` are a separate, internal thing: `builder.py` bakes them
to `/plug/` for HMI development. Not user plugins.)

## Package layout (the whole contract)

```
plugins/
└── my-tweak/
    ├── plugin.json        optional — {"description": "..."}; the id is the folder name (slug)
    ├── pre.sh             optional — sourced at boot BEFORE the HMI starts (may export variables)
    ├── boot.sh            optional — run at boot just before the HMI starts (ksh; heavy setup, daemons)
    ├── lib/*.so           optional — joined the library path before the firmware's own libs
    ├── data/**            optional — read-only files for your scripts (or for the HMI to read)
    ├── main.js, hook.py … browser/server half of the SAME plugin — never sent to the guest
```

A package without `pre.sh`/`boot.sh`/`lib/` is simply browser/server-only: the in-car loader
ignores it (no error, nothing to bake).

**Inside the guest your package lives at fixed paths:**

| Host path (in `plugins/<id>/`) | Guest path | Notes |
|---|---|---|
| any file | `/fs/shim/u/<id>/` | RAM disk; scripts run from here |
| `lib/x.so` | `/fs/shim/ulib/x.so` | already in `LD_LIBRARY_PATH` (front) when the HMI starts |
| `data/x` | `/fs/shim/udata/<id>/x` | read-only input |
| — | `$IDEMU_UDATA/<id>` = `/var/idemu/plug/<id>` | **writable** state dir (RAM, per plugin) |

Environment every script gets: `IDEMU_UPLUGINS` (space-separated ids loaded this boot),
`IDEMU_UDATA`, plus all firmware env from `/fs/shim/env.sh` (`IDEMU_VIN`, `HMI_BRAND`, …).
Boot logs go to `/var/plug.log` (the `boot.sh` line and everything your scripts print).

## How the loading works (already built — you never touch it)

1. **Next boot (persistent path).** `builder.build_shim()` packs every `plugins/<id>/` into the
   shim RAM disk (`/u/<id>/`, `/ulib/`, `/udata/`). `idemu/guest/boot.sh` then, in order: sources
   every `pre.sh`, exports the env above, runs every `boot.sh` right before launching `HmiMain3D`.
   Saving a plugin automatically invalidates the fast-boot snapshot (`shim.img` feeds
   `snapshot_key`), so the next start is a cold boot where these hooks really run.
2. **Live (running guest).** `idemu/guestplugins.install()` pushes the package through the guest
   console (`shell.sock`, the same channel the SSH tab uses) into `/fs/shim/u/<id>/` and can run the
   scripts immediately; `hmi_restart()` (`slay HmiMain3D`) lets boot.sh's restart loop relaunch the
   HMI in ~3 s. Live pushes live in RAM only — they vanish at the next start unless the folder is
   also in `plugins/` (which is the supported way to keep them).

HTTP API (server): `GET /api/guestplugins` (host packages + what's installed in the guest now),
`POST /api/guestplugins/install|uninstall|run|hmi_restart` with `{"id": "<id>"}` (+ `"run": true`,
`"script": "boot.sh"`). CLI-equivalent via the SSH tab: see recipes below.

## Guest ground rules (learn them once, save hours)

* The console shell is **root ksh**, one persistent session, serialized by a file lock — long
  foreground commands block the SSH tab; **detach every daemon** with a double-subshell:
  `( ksh helper.sh </dev/null >>/var/plug.log 2>&1 & )` — the QNX image has **no `nohup`, no
  `setsid`**, and anything still sharing the tty keeps the console session waiting (timeouts,
  Ctrl-C kills). `/dev/shmem` is also **flat**: `mkdir /dev/shmem/sub` fails — writable trees go
  under `/var` (`$IDEMU_UDATA` = `/var/idemu/plug`). ksh heredocs need a writable `TMPDIR`
  (`/tmp` does not exist): boot.sh exports `TMPDIR=/dev/shmem`, plain SSH sessions do not.
* **No `printf`, `base64`, `od`, `cksum`, `awk`, `head`, `no /dev/fd`, no process substitution** in
  the stock QNX image (ksh's builtin `echo` expands `\ooo` only inside `$()`; `print -rn` does not
  expand escapes to a redirect — all verified the hard way). `sed/cut/grep/date/sleep/cat/dd/
  slay/on/bsdtar/gzip/sqlite3/vi` do exist. `guestplugins.install()` handles text transfer for you
  (verified heredoc); binaries only via the baked path.
* CAN/GPS state arrives as files written by the guest agent: last frame per id in
  `/var/idemu/can/<ID>` (bare uppercase hex, e.g. `AA` = engine RPM — **no `0x` prefix** in the
  name), NMEA sentences in `/var/idemu/gps/<TYPE>` (e.g. `GPRMC`).
* `slay -f most` wedges the shell — never kill the MOST daemon. Restarting the HMI is just
  `slay HmiMain3D`.
* Everything is RAM: `/fs/shim/*`, `/var`, `/dev/shmem` are rewound by the fast-boot snapshot on
  stop→start. Persist = keep the folder in `plugins/`.

## SSH recipes (the "drop files into the car" workflow)

```sh
# from the IDEmu host machine (or the SSH tab, which is the same console)
ssh -F environments/<env>/ssh/ssh_config idemu 'cat /var/plug.log'
ssh … idemu 'ls /fs/shim/u'                       # what is installed live right now
ssh … 'slay HmiMain3D'                            # relaunch HMI (3 s) so a pushed tweak takes effect
```

Live-push one file without any host tooling:

```sh
python3 -m idemu ssh            # interactive console, paste files with your editor
# or scripted, from python:
python3 -c "from idemu import guestfs; guestfs.push('<run-dir>/shell.sock', 'boot.sh', '/fs/shim/u/my-tweak/boot.sh')"
```

## Live transport caveat (v1)

`install()` pushes **text** files (scripts, configs) through the console with a verified heredoc.
Binary payloads (`.so`) cannot ride that channel yet (the QNX image has no `printf`/`base64`, and
the tty rewrites CR); until a byte-exact helper ships, keep `lib/` out of live pushes — bake the
`.so` via `plugins/` (it reaches the guest inside `shim.img`, no console involved) and use the
live path for iterating on scripts.

## Writing (or rewriting) the in-car half — checklist

1. `mkdir plugins/<id>` with a `boot.sh` (and `pre.sh` only if you must export env for the HMI).
2. Write state **only** under `$IDEMU_UDATA/<id>`; read your inputs from `/fs/shim/u/<id>` or `/udata`.
3. Iterate live: `POST /api/guestplugins/install {"id":"<id>","run":true}`, then
   `POST /api/guestplugins/hmi_restart`; watch `cat /var/plug.log` over SSH.
4. When it works, the folder *is* the installer: it ships on every cold boot from then on.
5. Want a tab for it (config, live view)? Add `main.js`/`hook.py` to the **same folder** — one
   plugin, two halves (host tabs can drive the guest through `/api/guestplugins*` or the CAN signal
   bank). The in-car half must still work on its own, with the browser closed.

### Capability matrix (what the in-car half can actually change)

| Want | Mechanism | Status |
|---|---|---|
| Files/scripts/daemons inside the head unit | `boot.sh` (this doc) | supported today |
| Interpose a library the HMI loads | `lib/x.so` + `LD_LIBRARY_PATH` front (only if the HMI loads that lib by name; core libs like `libscreen` are symlinked by boot.sh *before* plugins run — override them from `pre.sh` with your own symlink) | supported, expert |
| Export env/variants to the HMI process | `pre.sh` exports; `/fs/shim/variants.bin` semantics | supported, expert |
| Change what the **cluster/HUD shows** | the cluster content the HMI receives comes over the virtual MOST from the host (`MostCar.publish`, `POST /api/v850/publish`, FBlock `0xE0`); the browser-side panel is host-drawn | host-side seam today — talk to us before building on it |
| Inject an overlay into the head unit's **own screen** | host compositor seam (`src/glhost/map.c` style layer, CarPlay precedent) | host-side seam today |
| Custom CAN signals visible inside the HMI | add frames/signals to `idemu/data/can_signals.json` (ids 0x410–0x4FF are reserved for user signals) | supported today |
