# Jaymod (2.2.0)

Differences to legacy.

## No event autoexecs

Jaymod runs no `autoexec_<map>.cfg`, `autoexec_default.cfg`, team or class file (`docs/autoexec.md`). Consequences:

- No `autoexec_mod.cfg`: nothing in jaymod would ever exec it. Switching *into* jaymod therefore keeps the previous mod's values (class command IDs, weapalt binds, `setTeamSpectator`) until `F1`. Switching *away* from jaymod works normally — `autoexec.cfg` still sets `modLast`, and the other mod's `autoexec_mod.cfg` reads it and re-execs.
- No spawnpoint scripts: `spawnSelectorMap` stays empty, ENTER does nothing.

## Weapon IDs

Jaymod keeps etmain's weapon enum unchanged and appends its own weapons from 50, so the general `scripts/class/cs_classcommands.cfg` values are already correct here and `mod_classcommands.cfg` overrides nothing — it only records what was verified and how.

## 32 bit client only

`jaymod-2.2.0.pk3` ships `cgame`/`ui` for i386 and Windows x86 only, and a 64 bit ET: Legacy client can only join servers whose mod provides 64 bit modules ([Compatible Mods](https://github.com/etlegacy/etlegacy/wiki/Compatible-Mods)). Start jaymod with the 32 bit client (`GAME_BIN_I386` in `settings.conf`, `/usr/bin/etl.i386`).

## Popups

The echo menus use jaymod's `cg_numPopups`, `cg_popupWaitTime`, `cg_popupFadeTime` and `cg_popupTime` (`setPopupsMenu` in `mod_general.cfg`). Jaymod caps the wait time at 4000 ms and the fade time at 5000 ms (jaymod source `src/cgame/cg_popupmessages.cpp`), so a menu fades after 9 s instead of staying until it is closed; its keys stay bound.
