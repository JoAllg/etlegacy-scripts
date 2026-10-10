---
paths:
  - "default/cvars.cfg"
  - "default/state.cfg"
  - "default/binds_*.cfg"
  - "default/scripts/*.cfg"
  - "default/scripts/class/**"
  - "default/mods/*/mod_general.cfg"
  - "user.example.cfg"
---

# Cvars and binds

## Does a cvar / command exist?

Check the local dumps first, they are taken from the running game and cost one grep (the folder is local, not in version control; if it is missing, use the docs):
```
grep -i '^cg_fov	' research/dumps/*/cvars.tsv   # name, flags, value, default, side, source
grep -i '^forcetapout	' research/dumps/*/cmds.tsv
```
- Dumped: legacy, nitmod, jaymod. A cvar missing in one mod is listed in `research/dumps/<mod>_<version>/diff_legacy.md`. `value` is the value at dump time (no profile loaded), `default` the code default.
- Meaning and value range: ET: Legacy docs or source (`src/cgame/cg_cvars.c`, `src/client`, `src/renderer`); only then the web. Never read `console.log`.
- A cvar that exists in only some mods: say so in its comment, and put a value that differs per mod into `mods/<mod>/mod_general.cfg`.
- Server-side commands of a mod (handled by qagame) are not in `cmds.tsv`: unverified until tested in game, say so.

## Cvars

- `seta` only for real game cvars, in `cvars.cfg` (state cvars: `state.cfg`); aliases use `set`.
- Every cvar a script changes has its `seta` default in `cvars.cfg` and a `<cvar>Normal` value alias next to it; scripts restore it with `vstr <cvar>Normal`, never with a literal value.
- Personal values (fps, mouse, fov, rates, resolution, name) are redefined in `user.cfg`: a new one also goes into `user.example.cfg`.
- `cvars.cfg` is sectioned `//---[ MOUSE | GAME | VIEW | SYSTEM ]---//` with `//--- <Topic> ---//` subsections: grep the section, don't read the whole file (23 KB).
- `etconfig.cfg` is game-generated: never edit or read it for the profile's values.

## Binds

- Key names: `docs/keybinds.md` (German layout: `ß` = `US_MINUS`, `<` = `<`, ...).
- `binds_default.cfg` lists every default key with a marker: `bind` (default kept), `//bind` (taken over by a script in another cfg), `////bind` (unused). When a script takes over or frees a key, change its marker.
- A feature script binds its own key in its block. A key that a script rebinds at runtime gets a `bind<Key><Script>` alias, and its start bind goes into `state.cfg`.
- Before binding a key, check that it is free: `grep -rn 'bind <KEY> ' default/ --include='*.cfg'` (also inside `bind<Key>...` aliases).
- After bind changes run the keymap skill (new commands need a name in `tools/keymap/labels.json`).
