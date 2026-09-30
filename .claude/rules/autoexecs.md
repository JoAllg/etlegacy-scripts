---
paths:
  - "default/autoexecs/**"
  - "default/mods/*/autoexec_default.cfg"
  - "default/scripts/spawn/**"
---

# Autoexec files (map, default, team)

Background (load order, per-mod support, mod switch guard): `docs/autoexec.md`.

## Map autoexecs (`autoexec_<map>.cfg`)

After the header, in this order:
```
exec autoexec_mod.cfg  // this mod's autoexec.cfg, only after a mod switch (fs_game change doesn't re-exec it)
exec profile/scripts/spawn/generic_spawnpoints.cfg  // generic list first, so the previous map's spawnpoints are gone
set spawnSelectorMap "vstr spawnSelector3"
// spawnp*, echosp*, spawnsay* (spawnpsr/-psb come from generic_spawnpoints.cfg; set them only if the map needs other values)
echo ^5>>> AUTOEXEC_MAP LOADED!
```
- `exec autoexec_mod.cfg` comes first, so a mod switch reloads the chain before the map's values are set.
- `generic_spawnpoints.cfg` comes before the spawnpoints: the aliases survive map and mod changes, so otherwise the previous map's would remain.

## `autoexec_default.cfg`

- Same two exec lines, then the fallback `spawnSelectorMap` (`vstr spawnSelector3`; legacy: `spawnmenu` in `mods/legacy/`), last line `echo ^5>>> AUTOEXEC_DEFAULT LOADED!`.
- Mods that run it after every map file (etpub, silEnT) get an empty `mods/<mod>/autoexec_default.cfg`, because it must not undo the map's settings.

## Team autoexecs

- `autoexec_axis.cfg` / `autoexec_allies.cfg` set `spawnSelector4` (`vstr spawnpsr` / `vstr spawnpsb`).
- `autoexec_spectator.cfg` runs `vstr ta_Spectator` (spectator binds, e.g. SPACE plain jump). Legacy runs team autoexecs from the first snapshot too (`cg_snapshot.c` → `CG_Respawn`), so it also covers server join.

## All autoexecs

- Map and default autoexecs also run on every `vid_restart`: keep them safe to re-run. No mod cfg execs except the guarded `exec autoexec_mod.cfg`, no hook resets.
- Only autoexecs set spawnpoint aliases, `spawnSelectorMap` and `spawnSelector4`.
- `scripts/spawn/` files are exec'd by autoexecs only.
- New autoexec files need a rerun of `deploy.sh` (symlinked into the mod folders).
