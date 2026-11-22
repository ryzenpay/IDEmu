# Other iDrive repositories — research and merge notes (2026-11-18)

Survey of published work that runs or decodes BMW head-unit software, and what IDEmu took from each.

## Merged

* **NBT EVO Toolkit** (`vandelayautollc/nbt-evo-toolkit`, MIT) — 1,481 coding-parameter definitions
  (English name, description, per-value labels, confidence, source) for CAFD 00001EF6. Joined to the
  coding editor by BMW token with a field-width guard: **1,292 of the 1,334 editor parameters** now
  show real names/labels instead of humanised German tokens (e.g. `STARTUP_EMBLEM` value 5 =
  "Rolls-Royce Spirit of Ecstasy", firmware-traced). Files: `idemu/data/coding_gloss.json`,
  `tools/build_coding_gloss.py`, `idemu/coding.py` (`load_gloss`/`_gloss_get`/`_gloss_value`),
  `tests/test_coding_gloss.py`, NOTICE attribution. The toolkit's CAFD-only tokens are parked in
  `idemu/data/coding_gloss.caf_only.json`. Its real-car tooling (sign_ncd/write_coding/recover_key,
  FSC certstore patching) is deliberately not integrated: IDEmu never touches a car.
* **bimmulator techniques, reimplemented** (their code is unlicensed → behaviour copied, code written
  for IDEmu):
  - **Headless HTTP/CLI remote** — `idemu/hmihead.py` + `python3 -m idemu remote <id>`: page with
    controller buttons and a refreshing screen for eyeball checks, and `POST /api/v1/press`
    (`{"keys": [...], "delay_ms": N}`), `POST /api/v1/click`, `GET /api/v1/{buttons,state,screen.png}`
    for closed-loop runs (press → screenshot → analyze) without browser or Electron. Their press path
    is a one-byte datagram + QMP `screendump`; here the presses are IDEmu's own controller events
    (`<ctl>/input.sock` via `runtime.key/rotor/touch`, press+release pulses, tilt pulses like the web
    UI) and screenshots come straight from the glhost framebuffer (`runtime.screen_png`) — no QMP.
    Verified live on f30-330i-id5: `press menu` switched the HMI from My Vehicle to the top-level
    menu between two screenshots. Tests: `tests/test_hmihead.py` (fake runtime, real HTTP).
  - **Frame-rate benchmark under repeatable load** — `remote <id> bench [s]`: rotor/button workload
    with per-second frame windows from the framebuffer sequence (their QMP-interval metric, our
    frame-seq source).
  - **CI as release precondition** — `.github/workflows/tests.yml` runs `pytest tests` +
    `tools/i18n_check.py` on every push (their repo added a CI workflow early; ours had none).

## Studied, not merged (and why)

* **bimmulator** (`agent00jackson/bimmulator`, `cookingwithsimon/bimmulatorwindows`) — the closest
  emulator: native F32 ID6 Light HMI in patched QEMU OMAP5430 + 6WB (Bosch BO03, MIPS) cluster/HUD guest,
  pinned to one X20511I profile; ANGLE host bridge with reconstructed ESSL shaders; web page that
  presses the controller and screenshots (the three techniques above came from it). Techniques
  studied and deliberately NOT taken: the **SIPC host bridge** (their topology runs `most` as local
  MOST master fed over a V850 UART and decodes the stock daemon's raw SIPC telegrams — in IDEmu the
  stock `most` is fed through the channel-25 DSI bridge instead and SIPC carries no telegram traffic
  (`v850.log`: the peer connects and stays silent), so a decoder here would be dead code); **SGX540
  register/USSP shader diagnostics** (they host-emulate the GPU, IDEmu intercepts EGL/GLES above it in
  glhost — nothing transfers); **QMP screendump** (superseded by the glhost framebuffer); the V850
  trio, which is a stripped port of our own (UART2 polled by `mmap_device_memory`, no SIPC/DSI
  tunnels, no servicebroker — nothing to backport). Their repo has **no LICENSE file** → no code was
  copied; even the PolyForm-NC-derived V850 files were not touched. Press-and-screenshot + bench + CI
  were written from scratch against IDEmu's own plumbing.
* **rishik250809/bmw-idrive8.5-emulator** (MIT) — runs the real MGU22 HMI8 userland natively in an
  ARM64 container (Lima/krunkit VM on Apple Silicon) with a MoltenVK/virgl host GPU driver: no CPU
  emulation at all. macOS-only, mock vehicle data, firmware via file-share links. The architecture is
  the one to watch for ID7/ID8 speed (our gles shim already does the equivalent trick inside QEMU).
* **DAViS0d/BMW-NBT-Emulator** (PolyForm Strict) — original NBT (QNX 6.5 **x86**) on WHPX, ANGLE
  bridge; stagnant since 2026-11-01 and it committed BMW firmware into the repo (479 MB) — a license
  anti-pattern IDEmu deliberately avoids. Nothing to take.
* **vandelayautollc/nbt-evo-reversing** (real-car FSC/certstore research) — knowledge, no
  emulator-relevant code; keep as a reference for coding semantics behind `coding_gloss.json`.
* App ecosystems (`mgu-store`, `ID6_apps_prerelease`, `idrive7-custom-apps`, `Supra-iDrive6-Android-Auto`,
  `mgu-browser`) — run on real head units, not emulators; IDEmu's own plugin/store work lives in
  `idemu/plugins.py` and the id5apps project.
