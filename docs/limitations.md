# Limitations

What this profile cannot do or work around, why, and the workarounds: config scripts, the engine, mods and local hosting. Syntax and patterns of config scripts: [Config scripting](scripting.md).

## Scripts cannot read the game state

A cfg script can only run commands and set cvars. It has no conditions and cannot read a cvar, the player state or a server answer (`vstr` only runs the text of a cvar, `src/qcommon/cmd.c` `Cmd_Vstr_f`). Every toggle, cycle and layer therefore keeps its own guess of the state in an alias, and the guess is only right as long as the script is the only thing that changes the state.

### State that goes out of sync

| Script | Guess | Goes wrong when |
|---|---|---|
| Prone toggle (`scripts/movement.cfg` `proneToggle`) | prone or standing, with the FOV and crosshair size of that stance | the game ends prone itself: death, jump, double-tap back, water, mounting an MG (`src/game/bg_pmove.c` `PM_CheckProne`); or it refuses to go prone (no room, within 750 ms after standing up; `proneOFF` blocks the keys for that time). The next press would then prone with the normal FOV; `resetProne` repairs it on the jump key, the kill key and F4 (workaround 5) |
| Weapon binds (`binds_custom.cfg` `weapon<n>`, `weaponSwitch`, `bankPistol`, `bankSMG`) | the weapon in hand, with its FPS, MOUSE1 bind and autoreload; whether pistol or SMG is in hand (their keys: plain command or select with fallback, only differs in mods that override `bankPistolPlain`/`bankSMGPlain`) | the game switches the weapon: out of ammo, pickup, death, a bank the class does not have, weapon switch by mouse wheel. The kill key resets the settings to those of the primary weapon (`resetWeapon`) |
| Class keys (`class/cs_backend.cfg`) | team, class and weapon variant | the server refuses or changes it (team full or locked, class or weapon limit, auto balance; not tested in game), or the class is chosen in the limbo menu |
| Restore aliases (`<cvar>Normal`, e.g. `crosshairSizeNormal`) | the value to return to | another script or the menu changed the cvar without updating the alias, or the server enforces a value |
| Cvar toggles (HUD, voice sounds, demo recording) | on or off | the value was changed in the options menu or by the server; the recording stopped on its own (leaving the server) |

### Workarounds

Ordered from "cannot go wrong" to "repairs afterwards":

1. **Hold instead of toggle** (`+vstr <on> <off>`): the key is the state, so there is nothing to remember. Used by the crouch key, the quick equipment keys and the stats key. Does not help where the game command itself is a toggle (`+prone` switches the stance on every press).
2. **Absolute instead of relative commands**: a step sets its values (`cg_fov 90`), never "the other one". Each press of a cycle then leaves a known state even if the previous one was lost. A real cvar with the engine's `toggle`/`cycle` command keeps the state in the game, so it cannot differ from it; this only fits a single cvar without side effects.
3. **A cycle updates the restore alias it competes with**: the FPS cycle (`scripts/display.cfg`) sets `maxFps` together with `com_maxfps`, and the crosshair size cycle sets `crosshairSizeNormal`, so the weapon binds and crouch/prone return to the chosen value. Every cycle over a cvar that has a `<cvar>Normal` alias needs this.
4. **One reset alias per feature, called from every event the scripts do see** ([Config scripting](scripting.md), "Extension points and shared resets"): `reset<Feature>` puts the guess and the game back to the start state, and `resetToggles` collects them. Events a script sees are its own keys: class and team keys (`classHook`), the kill key, the jump key, `F4`; in legacy also the team and class autoexecs, which run on a respawn after a team or class change ([Autoexec behavior](autoexec.md)). A plain death and respawn is not visible to a script.
5. **Reset on keys that end the state anyway**: jumping ends prone (750 ms after going prone at the earliest and only with headroom, `src/game/bg_pmove.c` `PM_CheckProne`), so the jump key resets the prone guess (`proneStand`, `scripts/movement.cfg`); the kill key ends the life, so it runs `resetTemporary` (`scripts/scripts.cfg`: menu layers, class toggles, prone) and `resetWeapon` (weapon settings of the new life). This repairs the guess exactly where the game changed it behind the script's back.
6. **A manual repair key**: `F4` closes all layers, resets the toggles and releases all `+` commands. Last resort for everything the other points miss.

A new toggle or cycle should name in its comment which of these it relies on.

## Timing depends on the frame rate

`wait n` counts runs of the command buffer (two per client frame), not time, and stops the whole buffer including key presses and releases ([Config scripting](scripting.md), `wait`). A script with waits is tuned for one `com_maxfps` and runs faster or slower at another; while it waits, no other key command is processed.

Workarounds: no wait where a hold key does the job; the timer (`scripts/common.cfg`: `set timerDone vstr <alias>; vstr timer<ms>`) runs an alias after a time through a countdown that re-queues itself with `+vstr`, so key commands keep flowing (grenade auto-throw, dynamite: `class/cs_classcripts.cfg`); keep waits as short as the action allows.

The waits in the scripts are tuned for `com_maxfps 125`, where `wait n` lasts n × 4 ms (n × 500 / FPS in general):

| Wait | At 125 FPS | Used by | Kind |
|---|---|---|---|
| `wait 2`, `wait 3` | 1 to 1.5 frames | quick equipment keys, arty, popups, second wait of the jump | frames: the game needs one frame to take a command, at any FPS |
| `wait 5` | 20 ms | timer tick: grenade auto-throw (145 ticks = 2.9 s, fuse 4 s), dynamite (8 ticks = 160 ms weapon switch before `+attack`, 20 ticks = 400 ms plant, then arm), class report (145 ticks = 2.9 s after the last class key), spawnpoint line after the class line on BACKSPACE (50 ticks = 1 s: the server drops a second chat command within 800 ms) | time |
| `wait 10` | 40 ms | jump (sprint before the jump), voice chat close | time |
| `wait 50` | 200 ms | team join hook | time |

At another FPS the time waits are wrong by the factor 125 / FPS: at 76 FPS the grenade countdown takes 4.8 s (longer than the fuse), at 250 FPS the dynamite `+attack` comes after 80 ms instead of 160 ms. The FPS cycle (END) and `maxFpsLow` (pistols, sniper mode: 71 FPS in nitmod and jaymod) change the frame rate while playing.

### Suggested: wait aliases that follow the FPS (not implemented)

`wait` takes no variable and scripts cannot calculate, so the time waits become aliases that hold a `wait` of the right length for the current FPS, and the scripts chain them:

- Three units cover every time wait in use: `wait20` (timer tick), `wait40`, `wait200` (milliseconds). Frame waits (`wait 2`, `wait 3`) stay literal.

| Now (tuned for 125 FPS) | Time | With the aliases |
|---|---|---|
| `wait 5` | 20 ms | `vstr wait20` |
| `wait 10` | 40 ms | `vstr wait40` |
| `wait 50` | 200 ms | `vstr wait200` |

- One value alias per frame rate sets the FPS and the three waits together, so they cannot differ: `set fpsSet125 "com_maxfps 125; set wait20 wait 5; set wait40 wait 10; set wait200 wait 50"`. The count is ms × FPS / 500, rounded:

| `com_maxfps` | `wait20` | `wait40` | `wait200` |
|---|---|---|---|
| 71 | `wait 3` | `wait 6` | `wait 28` |
| 76 | `wait 3` | `wait 6` | `wait 30` |
| 125 | `wait 5` | `wait 10` | `wait 50` |
| 200 | `wait 8` | `wait 16` | `wait 80` |
| 250 | `wait 10` | `wait 20` | `wait 100` |
| 333 | `wait 13` | `wait 27` | `wait 133` |
| 500 | `wait 20` | `wait 40` | `wait 200` |

- `maxFps` and `maxFpsLow` become `vstr fpsSet<n>`. Everything that changes the frame rate already runs one of the two (weapon binds, sniper mode) or sets `maxFps` (FPS cycle), so the waits follow without further state: `user.cfg` only chooses the default (`set maxFpsNormal "vstr fpsSet125"`), a step of the FPS cycle runs `set maxFps vstr fpsSet250; vstr fpsSet250`.
- Cost: 7 `fpsSet<n>` and 3 wait aliases (cvar limit below).
- Remaining error: rounding (up to 6 % at 71 FPS for `wait20`), and a frame rate below `com_maxfps` (the waits get longer, as they do now).

## Limits of the engine

- 2048 cvars including every alias (`MAX_CVARS`, `src/qcommon/cvar.c`): nitmod with this profile uses about 1900. Pages with many entries bind their keys directly instead of defining aliases (server voice chat pages).
- 1024 characters per command line (`MAX_CMD_LINE`), no nested quotes: an alias cannot contain a quoted string, so an action with several commands needs its own alias.
- `reset <alias>` returns to the first value of the game session, not to the value in the cfg ([Config scripting](scripting.md), `reset`).
- Loaded sounds stay cached by file name across servers until `snd_restart` (`vid_restart` keeps them): vsay packs of different servers share names, so the last server's voices play on the next one. `tools/serverconfig.py` runs `snd_restart` once per server change ([Server configs](serverconfigs.md#sound-restart)); `F2` does it by hand.
- A server can enforce cvar values; a script does not notice it. `F3` restores the definitions afterwards.

## Stock shield hides server sounds and menus on unpure servers

The nitmod stock shield (`tools/stock_shield/README.md`) cannot tell a local game from an unpure server: wherever it is active, every stock file name it carries (menus, the whole stock `sound/` folder) plays the stock version.

| Where | Sounds and menus of the server |
|---|---|
| Pure server (`sv_pure 1`, the default) | work: only pk3s on the server's checksum list are read, the shield is not on it (`src/qcommon/files.c` `FS_PakIsPure`) |
| Unpure server (`sv_pure 0`) | files under new names work (spree sounds, custom vsays); files that replace a stock name are stock, e.g. translated vsay voices, other weapon sounds |
| Local game, main menu | same as unpure: this is what the shield is for; wanted packs in the mod folder lose their stock-name files too |

`/sv_pure` in the console shows the mode of the current server. Workaround on an unpure server with wanted replacements: move the shield pk3 out of `<fs_homepath>/nitmod/` and rebuild it afterwards (`python3 tools/stock_shield/stock_shield.py`). Not tested in game.

## Local hosting: a second map runs out of open files

`/map <map>` while on a local game stops with `Invalid game folder`; the console log shows the cause just before: `Sys_FOpen: open('.../etmain/pak0.pk3', 0) failed: errno 24` (too many open files). Seen in a legacy log on 2026-10-10.

- The local server is pure (`sv_pure 1`, the default). Its gamestate makes the client set `fs_containerMount 1` (`src/client/cl_parse.c` `CL_ParseGamestate`).
- A map load on the local host keeps the client connected (`src/client/cl_main.c` `CL_MapLoading`), so the pure list stays set, and the file system restart of the new map mounts every pk3 in `etmain/dlcache/` (`src/qcommon/files.c` `FS_AddContainerDirectory`). The first local map has no such list: leaving the remote server cleared it (`CL_Disconnect` → `FS_ClearPureServerPacks`).
- Every mounted pk3 keeps a file open. The dlcache pk3s plus the ones in `etmain/` (most of them links of `tools/link_maps.py` to the same dlcache files) came to 990, and the desktop session's soft limit is 1024 open files per process (`systemctl --user show -p DefaultLimitNOFILESoft`).

Workaround: `/disconnect` before `/map`. The LOCALHOST entry of the server menu does that (`disconnect; map goldrush`, `tools/helpers/menupages.py`; not tested in game). Remote pure servers mount the whole dlcache as well, so they can hit the same limit as downloads accumulate.

Long term: `tools/link_maps.py` has to stop linking every downloaded map into `etmain/` and link only a chosen subset (the maps to host locally), so the mounted pk3s stay well below the limit.

## Local hosting in nitmod

### Maps in the host game list that do not start

The host game list shows every `scripts/*.arena` file of the search path, whether or not the map's bsp exists (`src/ui/ui_gameinfo.c` `UI_LoadArenas`). The engine mounts every top-level pk3 of the mod folder; the `dlcache` folder that keeps downloads apart exists only for etmain and legacy (`src/qcommon/files.c` `FS_AddContainerDirectory`, `src/qcommon/download.c` `Com_ContainerizePath`). The packs of nitmod servers therefore stay mounted in `<fs_homepath>/nitmod/`, and the arena files they bring for their map rotation add entries without a map, e.g. `nfl_b2`. Legacy does not list them, its search path does not contain the nitmod folder.

Starting such an entry prints `Can't find map maps/<map>.bsp` and starts no server (`src/server/sv_ccmds.c` `SV_Map_f`; dedicated server test and console log of a start from the menu, 2026-10-02). The menu has set `ui_connecting 1` before (`src/ui/ui_main.c`, `StartServer`) and nothing resets it; what the screen shows then is unverified. No cvar restricts the mounted pk3s, and a copy of the mod folder under another name does not work (self-check below).

### Crash after a mod switch in the menu

nitmod's `G_InitGame` checks `gamename` and `fs_game` = `nitmod`, `mod_version` = `2.3.5` and `mod_url` = `etmods.net` and returns without setting up the level when one differs. The engine runs game frames right after the init (`src/server/sv_init.c` `SV_SpawnServer`), and the first one reads the missing entity array: segmentation fault in `G_RunFrame` → `CheckCvars` → `G_ReassignSkillLevel`, crash log `<fs_homepath>/nitmod/crash_*.log` with an empty `Map:`.

Likely trigger, not reproduced: a legacy game hosted before switching to nitmod in the mods menu. Legacy registers `mod_version` and `mod_url` with its own values, cvars survive the mod switch, and registering an existing cvar keeps its value (`src/qcommon/cvar.c` `Cvar_Get`). The crashes seen so far followed that order. Workaround: start the game in nitmod (`+set fs_game nitmod`) to host there.
