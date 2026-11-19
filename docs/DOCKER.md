# IDEmu in Docker

The image builds everything the emulator needs — the patched QEMU binaries (iDrive 5/6/7/8 boards)
and the `glhost` renderer — and runs the web GUI. QEMU runs under **TCG** (software emulation): no
`/dev/kvm`, no privileged containers. The GUI is served inside the container on port 8765; publish
wherever you like.

## Quick start

```bash
docker compose build                 # first build compiles QEMU (minutes)
docker compose up -d
```

Open <http://127.0.0.1:8765>. The first thing the wizard asks for is the **PSdZData** folder: inside
the container that is the mount point described below (e.g. `/psdzdata`).

## Where to mount PSdZData (SWFL packages)

`docker-compose.yml` mounts `./psdzdata` (a sample folder — see `psdzdata/README.md`) read-only at
`/psdzdata`. Point it at your real package in either way:

* **`.env`** next to `docker-compose.yml`:

  ```
  IDEMU_PSDZ=/your/path/to/psdzdata
  ```

* **`docker-compose.override.yml`** (gitignored — good place for machine-specific paths).
  If your `settings.json` already references the folder by absolute path, mount it at the
  **same absolute path** inside the container and reuse the file, and nothing needs
  reconfiguring:

  ```yaml
  services:
    ideemu:
      ports:
        - "127.0.0.1:8766:8765"      # host IDEmu already owns 8765
      volumes:
        - "/mnt/z/ISTA+/psdzdata:/mnt/z/ISTA+/psdzdata:ro"
        - ./settings.json:/data/settings.json
  ```

The folder needs the ISTA+ layout (`swe/swfl/swfl_*.bin.*`, `mainseries/...`) — the same content you
would pick in the desktop wizard. It is mounted read-only; the container never writes there.

## What lives where

| Path in container | What | How |
|---|---|---|
| `/app/environments` | built disks, snapshots, logs (2–5 GB per environment) | named volume `ideemu-environments` |
| `/data/settings.json` → `/app/settings.json` | PSdZData path, map source, … | named volume `ideemu-settings` or bind-mount your repo `settings.json` |
| `/psdzdata` | your PSdZData/SWFL folder | bind mount, read-only |
| `/app/bin` | the QEMU binaries + glhost baked at image build | part of the image |

Built environments are just files: bind-mount `./environments` instead of the named volume to share
the ones on your host — but then **do not run the host IDEmu server against the same environments at
the same time** (snapshot and image files would be raced).

## Which generations work out of the box

* **iDrive 5/6 (NBT Evo)** — fully: `qemu-system-arm` (omap5-uevm + GL bridge) and `glhost` are in
  the image; the renderer runs under Xvfb with software GL (`LIBGL_ALWAYS_SOFTWARE=1`).
* **iDrive 7** — its QEMU (`idemu-shm` device) is in the image; `bin/glhost7` links against the
  firmware's `libc.so.6`, so build it once (`src/mgu/build.sh`) and bind-mount it in:
  `- ./bin/glhost7:/app/bin/glhost7:ro`.
* **iDrive 8** — QEMU aarch64 is in the image; the ANGLE host renderer (`mgu22/guest/mguhost`) and
  ANGLE libraries (`IDEMU_ANGLE`) are not — same bind-mount trick as iDrive 7.
* **CIC (iDrive 4)** — needs the SH-4 QEMU (`src/cic/build.sh`); mount `bin/qemu-system-sh4`
  likewise.
* The guest shim libraries are committed in the repo, so they are already in the image.

## Options

Every supported `IDEMU_*` variable is listed in `docker-compose.yml` under `environment:`,
pre-filled with its default value — change a value to opt in, leave it alone to keep the default.
The two compose-interpolation vars live in `.env`: `IDEMU_WEB_PORT` (host port) and `IDEMU_PSDZ`
(PSdZData folder). Highlights:
* `IDEMU_SMP=2` (default in compose) — TCG multithread on NBT Evo; drop to `1` on slow hosts.
* `IDEMU_NO_SNAPSHOT=1` — never write snapshots (less volume churn).
* `IDEMU_PSDZ` — host folder for `/psdzdata`.
* `shm_size` — iDrive 7/8 renderers use POSIX shared memory; the compose file reserves 2 GB.
* `../idplugins` — if you keep the plugin project next to the repo, mount it and set
  `IDPLUGINS_HOME=/idplugins` (see that project's README).

## Troubleshooting

* Black screen with `glhost` errors in `docker compose logs` — the renderer needs the Xvfb display
  the entrypoint starts (do not override the container command). Software GL (`LIBGL_ALWAYS_SOFTWARE=1`,
  llvmpipe) is the default; the image deliberately runs `Xvfb` directly because Debian's
  `xvfb-run` wrapper does not behave as a container PID 1.
* Slow first boot — under TCG an NBT Evo cold boot takes minutes; resuming from snapshot is much
  faster.
