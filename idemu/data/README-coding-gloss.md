# coding_gloss.json — readable names for the coding editor

What each coding parameter means (English name, description, per-value labels, confidence), joined to
`coding_dict.json.z` by the BMW token (e.g. `VIDEO_SPEEDLOCK_CONDITION`) and guarded by the field
width: a token whose width differs between the two tables is left un-glossed (`idemu/coding.py`,
`_gloss_get`).

- Source: **NBT EVO Toolkit**, https://github.com/vandelayautollc/nbt-evo-toolkit,
  `capabilities/coding/definitions/cafd_00001ef6_definitions.json` (CAFD 00001EF6, v006.048.013).
  MIT License, (C) the NBT EVO Toolkit contributors — their own reverse-engineered descriptions
  (firmware syset tokens, value tables and code traces), not BMW data. See `LICENSE-nbt-evo-toolkit.txt`.
- Built by `tools/build_coding_gloss.py <definitions.json>`; regenerates this file and
  `coding_gloss.caf_only.json` (79 CAFD parameters with no token in our dictionary — a lead when
  comparing another SWFL's `libhmicoding`).
- 1321 of the editor's ~1334 parameters join, all with matching width. The toolkit's tables describe
  the NBT EVO (ID5/ID6) CAFD; iDrive 7/8 editors (`coding7.py`, `coding8.py`) do not use this file.
- The definitions describe parameters, not guarantees: a coded feature still needs its fitted
  options/variant on the emulated car, same as on a real one. `gloss` on each parameter is the
  toolkit's confidence (`high`/`med`/`low`), `source` where their text came from
  (`firmware-trace` is traced in the HU binaries).
