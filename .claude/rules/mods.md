---
paths:
  - "default/mods/**"
---

# default/mods

One folder per mod; `deploy.sh` symlinks its `autoexec*` and `mod_*` files into `<fs_homepath>/<mod>/`, where the engine and `definitions.cfg` find them by bare name through the mod search path. Per-mod differences: `default/mods/<mod>/README.md`.

| File | Role |
|---|---|
| `autoexec.cfg` | entry point: `unbindall`, `definitions.cfg`, `profiles/user.cfg`, `state.cfg`, `vstr serverForce` (server settings), then the mod switch guard. The only file that carries the mod's name (guard aliases) |
| `autoexec_mod.cfg` | exec'd by every map/default autoexec; re-execs `autoexec.cfg` only after a mod switch, then `vstr serverCheck` (server settings after a server change). Omitted for mods that run no event autoexecs (`jaymod/`), where nothing would exec it |
| `mod_general.cfg` | mod differences (alt-fire, FOV, spectator command, popups, ...) plus `modState`, the mod's start binds applied by `default/state.cfg` |
| `mod_classcommands.cfg` | the `//--[ CLASS COMMANDS ]--//` block (weapon IDs) |
| `autoexec_default.cfg` (optional) | only for mods that run it (`docs/autoexec.md`); overrides `default/autoexecs/autoexec_default.cfg` |
| `README.md` (optional) | differences compared to plain legacy |

- Folders: `legacy/`, `nitmod/` (full set, tested), `jaymod/` (no `autoexec_mod.cfg`), `etpub/`, `silent/`, `etjump/` (full set with the general default values, not tested in game; etpub and silEnT add an `autoexec_default.cfg` without spawnpoints), `example/` (template, not live, not linked).
- A change that applies to every mod is made in all folders including `example/`: apart from the mod name and the documented differences the same file is identical everywhere.
- Header description (below the title): identical for the same file in every mod folder (`example/` included, no "Template:"); mod differences go in comments after the header.
- Name new dispatch files `mod_<name>.cfg`, with `mod` as the literal word, and exec them by bare name from `default/definitions.cfg`.
- General code stays in the general files; a mod file only overrides the aliases/values that differ (general default first, e.g. `fovLow` in `cvars.cfg`, `setTeamSpectator` in `classcript.cfg`).

## Mod switch guard

Pattern: `docs/scripting.md` "Change guard"; mechanism: `docs/autoexec.md`.
- `autoexec.cfg` ends with these lines before its load echo:
  ```
  set modLast "vstr modIs_<mod>"  // mod switch guard, see autoexec_mod.cfg
  set modIs_<mod> "exec autoexec.cfg"  // armed, so switching mods before any map autoexec ran still re-execs
  ```
- Every mod with an `autoexec.cfg` has an `autoexec_mod.cfg` using its own name in `modIs_<mod>` — except mods that run no event autoexecs. Their `autoexec.cfg` still sets `modLast`/`modIs_<mod>`, so switching *away* from them works; switching *into* them keeps the previous mod's values until `F1`.

## New mod

Copy `example/` to `<mod>/`, replace every `<mod>` placeholder (incl. `modIs_<mod>`), adapt `mod_general.cfg` and the class command IDs, rerun `deploy.sh` (add the mod to `AUTOEXEC_MODS` there if it runs event autoexecs).

## Class commands

**Class commands must be adapted for every mod.** The `b_*` / `r_*` aliases (`team <r|b> <class> <weapon> <weapon2>`) use weapon IDs, and those numbers differ between mods (compare `legacy/mod_classcommands.cfg` vs `nitmod/mod_classcommands.cfg`). When adding or updating a mod, never copy the numbers from another mod — look up/test the IDs for that mod (legacy: weapon enum in ET: Legacy source `src/game/bg_public.h`, allowed weapons per class in `src/game/bg_classes.c`; other mods: sources on the web or a decompile of the mod binary into `research/<mod>/decompiled/`), and let the user test the numbers you found.
