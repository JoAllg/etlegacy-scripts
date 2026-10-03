# etps differences (compared to plain legacy mod)

etps is a server mod built on legacy 2.84 (its cgame reports `v2.84.0-552`). Everything not listed here works as in legacy: `team spectator`, minimum FOV 75, map/team autoexecs (`CG_MapAutoexec` in its cgame).

- **Alt-fire:** `+attack2` instead of `weapalt`; its cgame rebinds `weapalt` binds to `+attack2` on start (string `Migrated %i legacy weapalt bind%s to +attack2`), tested in game 2026-10-03
- **Popups:** legacy's `editcomponent popupmessages` plus the cvar `cg_numPopups` (max 8), which caps the lines; `setPopupsMenu` in `mod_general.cfg` sets 8 for the echo menus, `setPopupsNormal` restores `numPopupsNormal` (`cvars.cfg`). Echo menus hold 8 lines, so the server menu uses its pages of 7 servers
- **Chat shortcuts for vsays:** the server expands `[H]`, `[P]`, ... in chat (tested in game 2026-10-03 with `say_team`), so `mod_general.cfg` execs `scripts/vsays/chat_shortcuts.cfg` like nitmod
- **HUD file:** the cgame of 2.84 reads `profiles/<cl_profile>/hud.dat` with HUD JSON version 7, not `huds/hud_v8.dat` (`.claude/rules/hud.md`)
- **Class commands:** legacy weapon IDs up to 55, plus its own weapons 56 Shotgun, 57 Venom, 58 BAR, 59 StG44, 60 Johnson. `mod_classcommands.cfg` appends them as class steps to the cycles and gives the soldier a pistol as second weapon (bank 3 holds two weapons, an SMG would be a third)
