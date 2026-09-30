---
paths:
  - "default/definitions.cfg"
  - "default/cvars.cfg"
  - "default/state.cfg"
  - "default/binds_*.cfg"
  - "default/scripts/*.cfg"
  - "default/scripts/class/**"
  - "default/scripts/vsays/**"
  - "default/server/**"
  - "default/mods/*/autoexec.cfg"
  - "default/mods/*/mod_general.cfg"
  - "default/mods/*/mod_classcommands.cfg"
  - "user.example.cfg"
---

# Definitions pass vs state values

Two passes, so F3 can re-assert settings without throwing away what the player toggled:
- **Definitions** (`default/definitions.cfg` and everything it execs, including the mod's `mod_general.cfg` / `mod_classcommands.cfg`): aliases, fixed binds, cvars no script changes. Re-exec'd by `F3` (`vstr reloadDefinitions`) and by `autoexec.cfg`.
- **State values** (`default/state.cfg`, and `modState` in `mods/<mod>/mod_general.cfg` for mod specific ones): the start value of anything a script changes at runtime. Exec'd by `mods/<mod>/autoexec.cfg` only, so game start and mod switch reset them, `F3` does not. `F1` forces a full reset.
- `unbindall` lives in `mods/<mod>/autoexec.cfg`, never in the definitions.
- **Personal values** (`user.cfg` at the repo root, template `user.example.cfg`): the player's own name and anything else that must not be in version control. Exec'd after the definitions by `mods/<mod>/autoexec.cfg` (before `state.cfg`) and by `F3` (`reloadDefinitions`), so it overrides the general and the mod files; a missing `user.cfg` only prints `couldn't exec`. `state.cfg` runs after it on purpose: state start values win until the next restart/`F1`. User-specific values (fps, mouse, fov, refresh rate, fullscreen resolution, network rates) have ET: Legacy defaults in the definitions (`cvars.cfg`, `scripts/display.cfg`) that `user.cfg` redefines and `state.cfg` applies. Never set there what a mod's `mod_general.cfg` sets per mod (e.g. `maxFpsLow`, `fovLow`).

Rules for the definitions pass:
- Never set a start value of state there: toggle and cycle pointers, keys a script rebinds, cvars a script changes, armed hooks. Leave a comment naming `state.cfg` instead.
- Whether a feature's state belongs in `state.cfg` is decided per feature: keep it in the definitions when it *should* reset on `F3` (sniper mode, and currently the fps, crosshair, hud, sound and name cycles). In `state.cfg`: the weapon switch cycle (F5), the class vsays toggle (F7), team and class state, the team brightness, the window mode toggle (INS), the network cycle (DEL).
- Never set anything the `autoexec_*.cfg` files set: spawnpoint aliases (`spawnp*`, `echosp*`, `spawnsay*`, `spawnpsr/-psb`), `spawnSelectorMap`, `spawnSelector4`. Don't define them empty either: `vstr` on an undefined alias does nothing, so a general script can call them without a definition. But document the value in a general script that expects the alias to exist.
  Why: the chain runs after the autoexecs. `F3` re-execs it after all of them; on a mod switch it runs from `exec autoexec_mod.cfg` at the start of the map/default autoexec, after an earlier team autoexec.
- Never exec autoexecs or `scripts/spawn/` files from the chain.
