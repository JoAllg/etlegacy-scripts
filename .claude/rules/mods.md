---
paths:
  - "default/mods/**"
---

# default/mods

One folder per mod; its `autoexec*` and `mod_*` files are symlinked into `<fs_homepath>/<mod>/`, where the engine and `definitions.cfg` find them by bare name through the mod search path:
- `autoexec.cfg`: entry point; `unbindall`, `definitions.cfg`, `profiles/user.cfg`, `state.cfg`, then the mod switch guard. The only file that carries the mod's name (guard aliases), everything else is identical in every mod folder
- `autoexec_mod.cfg`: exec'd by every map/default autoexec; re-execs `autoexec.cfg` only after a mod switch. Omit it for mods that run no event autoexecs (`docs/autoexec.md`), where nothing would ever exec it — `jaymod/` has none
- `mod_general.cfg`: mod differences (alt-fire, FOV, spectator command, ...) plus `modState`, the mod's start binds applied by `default/state.cfg`
- `mod_classcommands.cfg`: the `//--[ CLASS COMMANDS ]--//` block

`mod_general.cfg` and `mod_classcommands.cfg` are exec'd by bare name from `default/definitions.cfg`, so the mod search path resolves them to the current mod (`deploy.sh` links `autoexec*` and `mod_*` into `~/.etlegacy/<mod>/`). Name new dispatch files `mod_<name>.cfg`, with `mod` as the literal word — they are the same file in every mod folder.
- `autoexec_default.cfg` (optional): only for mods that run it (see `docs/autoexec.md`); overrides `default/autoexecs/autoexec_default.cfg` (`etpub/` and `silent/` hold only an empty one)
- `README.md` (optional): differences compared to plain legacy

Header description (below the title): identical for the same file in every mod folder (`example/` included, no "Template:"); mod differences go in comments after the header.

`example/` is the template for a new mod (copied from `legacy/`, with `<mod>` placeholders).

## Mod switch guard

Pattern: `docs/scripting.md` "Change guard"; mechanism: `docs/autoexec.md`.
- `autoexec.cfg` ends with these lines before its load echo:
  ```
  set modLast "vstr modIs_<mod>"  // mod switch guard, see autoexec_mod.cfg
  set modIs_<mod> "exec autoexec.cfg"  // armed, so switching mods before any map autoexec ran still re-execs
  ```
- Every mod with an `autoexec.cfg` has an `autoexec_mod.cfg` using its own name in `modIs_<mod>` — except mods that run no event autoexecs, which never exec it. Their `autoexec.cfg` still sets `modLast`/`modIs_<mod>`, so switching *away* from them works; switching *into* them keeps the previous mod's values until `F1`.

## New mod

Copy `example/` to `<mod>/`, replace every `<mod>` placeholder (incl. `modIs_<mod>`), adapt `mod_general.cfg` and the class command IDs, rerun `deploy.sh`.

## Class commands

**Class commands must be adapted for every mod.** The `b_*` / `r_*` aliases (`team <r|b> <class> <weapon> <weapon2>`) use weapon IDs, and those numbers differ between mods (compare `legacy/mod_classcommands.cfg` vs `nitmod/mod_classcommands.cfg`). When adding or updating a mod, never copy the numbers from another mod — look up/test the IDs for that mod (for legacy: weapon enum in ET: Legacy source `src/game/bg_public.h`; for other mods attempt to find sources in the web or decompile their mod pk3 file, let the user test the numbers you have found).
