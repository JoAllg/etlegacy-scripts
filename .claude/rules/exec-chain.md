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
  - "default/serverconfigs/**"
  - "default/mods/*/autoexec.cfg"
  - "default/mods/*/mod_general.cfg"
  - "default/mods/*/mod_classcommands.cfg"
  - "user.example.cfg"
---

# Definitions pass vs state values

Three passes and the server settings, in this order, so F3 can re-assert settings without throwing away what the player toggled:
- **Definitions** (`default/definitions.cfg` and everything it execs, including the mod's `mod_general.cfg` / `mod_classcommands.cfg`): aliases, fixed binds, cvars no script changes. Re-exec'd by `F3` (`vstr reloadDefinitions`) and by `autoexec.cfg`.
- **Personal values** (`user.cfg` at the repo root, not in version control; template `user.example.cfg`): name, fps, mouse, fov, refresh rate, fullscreen resolution, network rates, `omnibot_path`. Exec'd after the definitions by `autoexec.cfg` and by `F3`, so it overrides the general and the mod files; a missing file only prints `couldn't exec`. The definitions (`cvars.cfg`, `scripts/display.cfg`) hold the ET: Legacy defaults of these values. Never set there what a mod's `mod_general.cfg` sets per mod (e.g. `maxFpsLow`, `fovLow`). A new value goes into `user.example.cfg` too (`deploy.sh` appends missing ones to `user.cfg`). Its `HUD VALUES` block is generated (`.claude/rules/hud.md`): never edit it, and it is not part of the template.
- **State values** (`default/state.cfg`, and `modState` in `mods/<mod>/mod_general.cfg` for mod specific ones): the start value of anything a script changes at runtime. Exec'd by `mods/<mod>/autoexec.cfg` only, so game start, mod switch and `F1` reset them, `F3` does not. Runs after `user.cfg` on purpose: it applies aliases `user.cfg` redefines, and state start values win until the next restart/`F1`.
- **Server settings** (`default/serverconfigs/`, `.claude/rules/serverconfigs.md`): applied last by `vstr serverForce`, which ends both `autoexec.cfg` and `reloadDefinitions`, so they override all three passes.
- `unbindall` lives in `mods/<mod>/autoexec.cfg`, never in the definitions.

Rules for the definitions pass:
- Never set a start value of state there: toggle and cycle pointers, keys a script rebinds, cvars a script changes, armed hooks. Leave a comment naming `state.cfg` instead.
- Whether a feature's state belongs in `state.cfg` is decided per feature (ask the user for a new one): keep it in the definitions when it *should* reset on `F3` (sniper mode, and currently the fps, crosshair size, hud, sound and name cycles). In `state.cfg`: the crosshair color (the map autoexecs set it per map, `docs/autoexec.md`; the pointer of its HOME cycle stays in the definitions), the weapon switch cycle (F5), the forms of the pistol and SMG key (`bankPistol`, `bankSMG`), the class vsays toggle (KP_MINUS), the class report toggle (KP_SLASH), the spawn report toggle (KP_STAR), team and class state (spawn selector, join hooks), the team brightness, the window mode toggle (INS), the network cycle (DEL), `popupsClose`, the start binds of keys that scripts rebind.
- `reset <alias>` returns to the alias's first `set` of the game session: after changing a start value in `state.cfg`, the game must be restarted (`F1` keeps the old reset value).
- Never set anything the `autoexec_*.cfg` files set: spawnpoint aliases (`spawnp*`, `echosp*`, `spawnsay*`, `spawnpsr/-psb`), `spawnSelectorMap`, `spawnSelector4`. Don't define them empty either: `vstr` on an undefined alias does nothing, so a general script can call them without a definition. But document the value in a general script that expects the alias to exist. Why: the chain runs after the autoexecs. `F3` re-execs it after all of them; on a mod switch it runs from `exec autoexec_mod.cfg` at the start of the map/default autoexec, after an earlier team autoexec.
- Never exec autoexecs or `scripts/spawn/` files from the chain.
- A new cfg is only live once a file of the chain execs it (`profile/...` path) — add the `exec` and the tree entry in `CLAUDE.md`.
- A file that a key press execs (menu page, page opener, a hook of a key such as `serverCheck`, a bind in a generated page) is exec'd with `execq`: the key prints no `execing <file>` line. Plain `exec` stays in the chain and the event autoexecs (game start, mod switch, `F1`, `F3`), where the `execing` lines are the load check.
