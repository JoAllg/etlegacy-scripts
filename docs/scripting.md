# ET config scripting

General knowledge about client-side config scripting. Verified against the ET: Legacy source at `<ET: Legacy source checkout>` (engine: `src/qcommon/cmd.c`, `src/qcommon/cvar.c`, `src/client/cl_keys.c`; legacy mod: `src/cgame/cg_consolecmds.c`). Mods other than legacy may differ — check `/cmdlist` there.

## Command buffer and syntax

- Commands are split at `;` and newlines, but not inside `"..."`.
- `//` and `/* */` are comments.
- **No escaping, no nested quotes.** A quoted value can't contain other quotes, so longer scripts are built from several aliases (cvars) called with `vstr`.
- In the console, commands are prefixed with `/`; in `.cfg` files without it.
- Limits: 1024 chars per command line (`MAX_CMD_LINE`), 256 tokens per line, 128 KB command buffer (`MAX_CMD_BUFFER`). `exec` itself has no file size cap; the old "cfg must be < 16 KB" rule is vanilla-era.

## Variables (aliases)

| Command | Effect |
|---|---|
| `set <cvar> <value>` | set/create cvar (a user-created cvar works as an alias) |
| `seta <cvar> <value>` | same + archive flag: value is written to `etconfig.cfg` |
| `sets` / `setu` | same + serverinfo / userinfo flag |
| `reset <cvar>` | back to the default value |
| `unset <cvar>` | delete a user-created cvar |
| `vstr <cvar>` | executes the cvar's value as commands; the text is inserted at the front of the buffer, so it runs before whatever follows |

Prefer `set` for aliases: `seta` persists them into `etconfig.cfg`, where they can outlive the script that defined them.

## Binds

- `bind <key> "<commands>"`, `unbind <key>`, `unbindall`, `bindlist`.
- **Key release:** only if the bind text *starts* with `+`, the engine sends `-<rest of the bind> <key> <time>` on release. With several `+commands` in one bind only the first is released correctly (`"+attack; +speed"` releases as `-attack; +speed ...`). For hold actions with several commands use `+vstr`.
- **`ESCAPE`:** the engine handles the press itself (in-game menu, closing the console) and never runs its bind; the release is not intercepted (`src/client/cl_keys.c` `CL_KeyEvent`). So only a `+` bind does anything on `ESCAPE`, and only its release part: `bind ESCAPE "+vstr null resetLayers"` (`scripts/scripts.cfg`) closes the echo menus when the key is let go.
- **No scripted view movement up/down:** the legacy and nitmod cgames remove `+lookup`/`+lookdown` "to avoid abuse" (legacy `src/cgame/cg_consolecmds.c`, nitmod 2.3.5 `trap_RemoveCommand` in its `cgame.mp.x86_64.so`), so they print `Unknown command`. No other command turns the view by a relative amount (`m_pitch` only scales real mouse input), so an anti-recoil script is impossible.

## Built-in helpers

**`toggle <cvar>`:** 0 ↔ 1 (any non-zero becomes 0). **`toggle <cvar> <v1> <v2> ...`:** sets the value that follows the current one, or `v1` if there is no match.

**`cycle <cvar> <start> <end> [step]`:** integers only (floats like `r_gamma 1 3 0.5` don't work), wraps around at the ends. No side effects possible — use the manual cycle pattern for that.

**`+vstr <downCvar> <upCvar>`:** cgame (mod) command, not engine (legacy, nitmod and jaymod have it); both arguments are *cvar names*, not commands. Only works from a bind (it needs the key/time arguments the engine appends).

**`wait [n]`:** delays the *rest of the buffer* by `n` buffer runs (default 1). The client runs the buffer twice per frame (`src/qcommon/common.c` `Com_Frame`), so `wait n` ≈ n/2 frames; real time depends on FPS (`com_maxfps`). Everything queued after it is delayed too, including key presses (single buffer).

**`reset <alias>`:** for a user-created cvar this restores the value it was **first** set to in this game session. A later `set` doesn't change that stored default — after editing a cfg, `reset` still returns the old value until the game restarts.

**`exec <file>`:** runs a cfg (`.cfg` added if missing), path relative to the mod search path (`profile/...`). Console shows `execing <file>` or `couldn't exec <file>`.

**`echo`:** prints text; when connected it shows as a notification (`cpm`). ET: Legacy extension: `echo "FOV: " vstr cg_fov` inserts a cvar value. Color codes `^0`–`^9` and letters (e.g. `^5` cyan).

## Script patterns

Taken from the live scripts in `default/`. Most rely on one idea: a *pointer alias* whose value is `vstr <otherAlias>`, re-pointed with `set` at runtime.

### Toggle (alias switching)
Two states that re-point the toggle alias. Unlike `toggle`, each state can run any side effects (sound, echo, several cvars, binds).
```
bind F8 "vstr soundToggle"
set soundToggle "vstr soundOFF"
set soundOFF "cg_voiceChats 0; set soundToggle vstr soundON; echo ^8Chat sounds ^1OFF; vstr playSelect"
set soundON  "cg_voiceChats 1; set soundToggle vstr soundOFF; echo ^8Chat sounds ^2ON; vstr playCancel"
```
Examples: `scripts/scripts.cfg` (sound, demo), `scripts/movement.cfg` (crouch, prone), `scripts/display.cfg` (HUD), `class/cs_classcripts.cfg` (sniper, map toggle).

### Manual cycle (alias switching)
Like a toggle with N states; the last state points back to the first. Advantages over `cycle`: floats and non-numeric values, several cvars per step, arbitrary step order, and side effects per step (sound, echo, related cvars).
```
bind HOME "vstr cycleCrosshairColor"
set cycleCrosshairColor "vstr crosshairColorCyan"
set crosshairColorCyan "cg_crosshaircolor cyan; cg_crosshaircoloralt cyan; set cycleCrosshairColor vstr crosshairColorRed; vstr playSelect; echo ^8CROSSHAIR COLOR ^2cyan"
set crosshairColorRed "cg_crosshaircolor red;  cg_crosshaircoloralt red;  set cycleCrosshairColor vstr crosshairColorWhite; vstr playSelect; echo ^8CROSSHAIR COLOR ^2red"
set crosshairColorWhite "cg_crosshaircolor white; cg_crosshaircoloralt white; set cycleCrosshairColor vstr crosshairColorCyan; vstr playSelect; echo ^8CROSSHAIR COLOR ^2white"
```
Examples: `scripts/display.cfg` crosshair color, gamma (floats), FPS (sets `com_maxfps` + `cl_maxpackets` + the `maxFpsNormal` alias per step), name cycle; the class selector (`class/cs_backend.cfg`, `cycleAlliesSoldier` → `b_so1..4`) is a manual cycle whose steps run class commands.

Pitfall: a cycle step must point to the *next* step. Check the pointer alias name in every step (a step that sets a different alias than the one bound breaks the cycle).

### Bidirectional cycle
Two pointer aliases (up/down); every step re-points both to its neighbors.
```
bind + "vstr cycleCrosshairSizeUp"
bind - "vstr cycleCrosshairSizeDown"
set cycleCrosshairSizeUp "vstr crosshairSize15"
set cycleCrosshairSizeDown "vstr crosshairSize25"
set crosshairSize15 "cg_crosshairsize 15; set cycleCrosshairSizeDown vstr crosshairSize25; set cycleCrosshairSizeUp vstr crosshairSize20"
set crosshairSize20 "cg_crosshairsize 20; set cycleCrosshairSizeDown vstr crosshairSize15; set cycleCrosshairSizeUp vstr crosshairSize25"
set crosshairSize25 "cg_crosshairsize 25; set cycleCrosshairSizeDown vstr crosshairSize20; set cycleCrosshairSizeUp vstr crosshairSize15"
```
Example: `scripts/display.cfg` crosshair size.

### Resettable cycle
A cycle whose pointer is restored with `reset` (to its first definition, see `reset` above), e.g. so the next key press starts at step 1 again. `class/cs_backend.cfg`: the first press of a class key (`b_so`) resets that class's cycle and re-points the key to `b_soAgain`, so repeated presses keep cycling its weapons; choosing another class (`classKeysAllies`) points all class keys back to their first press.

### Hold with side effects
`+vstr` runs one alias on press and one on release; use it for anything that must be undone when the key is released.
```
bind c "+vstr crouchON crouchOFF"
set crouchON  "+movedown; vstr fovLow; vstr crosshairSizeLow"
set crouchOFF "-movedown; vstr fovNormal; vstr crosshairSizeNormal"
```
Examples: crouch/lean/autosprint in `scripts/movement.cfg`, stats in `scripts/scripts.cfg`; quick equipment in `class/cs_classcripts.cfg`, where a short `wait` lets the weapon switch finish before `+attack`, and release switches back:
```
set weapon6Satchel_ON  "wait 2; vstr weapon6; wait 2; +attack"
set weapon6Satchel_OFF "-attack; vstr weapon3"
```

### Value aliases (Normal/Low)
Store a full `cvar value` command in an alias instead of hardcoding values in scripts. Scripts apply `vstr fovLow` / restore `vstr fovNormal`; changing a default or a mod-specific value (`mods/<mod>/mod_general.cfg` sets `fovLow`) needs one line, not an edit in every script.
```
set fovLow "cg_fov 75"
```

### Bind aliases (runtime key remapping)
Store a whole `bind` command in an alias named `bind<Key><Script>`, then `vstr` it to switch what a key does (per weapon, class, team or mode).
```
set bindMouse1Attack "bind MOUSE1 +attack"
set bindMouse1Sprint "bind MOUSE1 +vstr autosprintON autosprintOFF"
set weapon3 "weaponbank 3; weaponbank 2; vstr bindMouse1Sprint"
```
Examples: weapon binds in `binds_custom.cfg`, class bindings (`cs_*` aliases) in `scripts/classcript.cfg`, mod-specific alt-fire binds in `mods/<mod>/mod_general.cfg`.

### Temporary key layer (modal menu)
One key opens a mode that rebinds a group of keys (e.g. number row) and prints the options; selecting an option or pressing the opener again restores the normal binds. The opener re-points itself to its OFF state while the mode is open.
```
bind ENTER "vstr spawnSelector"
set spawnSelector3      "vstr echospr; vstr bindNumbersSpawnpsr; set spawnSelector3 vstr spawnSelector3OFF"
set spawnSelector3OFF "vstr resetSpawnSelector; vstr playCancel"
set resetSpawnSelector "vstr reBindNumbers; reset spawnSelector3"
set spawnp1r "setspawnpt 1; vstr resetSpawnSelector"
```
Examples: `scripts/spawnscript.cfg`, `scripts/voicechat.cfg`. The restore alias (`reBindNumbers`, `binds_custom.cfg`, shared by all layers) must rebind every key a layer uses. Every exit path (opener, option, `DEL`) closes the layer through one `reset<Layer>` alias; `resetLayers` runs all of them and every opener runs it first, so only one layer is open at a time.

A layer with many pages can bind its keys in exec'd page files instead of aliases (`vsays/servers/<clan>/*.cfg`), which costs no cvars (`MAX_CVARS` 2048, nitmod already uses ~1900).

### Override chain
A key calls level 1, which by default forwards to level 2, and so on. Other cfgs replace a single level (mod cfg, map autoexec, team state) without knowing the rest.
```
set spawnSelector  "vstr spawnSelector2"   // replaced by "no team" / "no class" guards until a class is chosen
set spawnSelector2 "vstr spawnSelectorMap" // spawnSelectorMap is set only by autoexecs: "vstr spawnSelector3" or legacy's "spawnmenu"
set spawnSelector3 "vstr spawnSelector4"   // mode open/close
// spawnSelector4: team list, set only by autoexec_axis/allies.cfg ("vstr spawnpsr" / "vstr spawnpsb"), undefined before
```
Map autoexecs set `spawnSelectorMap "vstr spawnSelector3"`, `autoexec_default.cfg` sets the fallback (legacy: `spawnmenu`). Only autoexecs set it (same for `spawnSelector4`, set by `autoexec_axis/allies.cfg`), because `F3` and a mod switch re-exec the cfg chain after the autoexecs: a value from the cfgs would overwrite the current map's menu. Same for the spawnpoint aliases (`spawnp*`, `echosp*`, `spawnsay*`): each autoexec first execs the generic `scripts/spawn/generic_spawnpoints.cfg`, so no values from the previous map remain.

### State-dependent dispatch and guards
A generic alias is re-pointed to a context-specific implementation when state changes; until then it points to a guard that explains what's missing.
```
set so "vstr noTeam"
set teamAllies "set so vstr b_so; set me vstr b_me; ..."
set teamAxis   "set so vstr r_so; set me vstr r_me; ..."
```
Example: `class/cs_backend.cfg` (team → class selectors), `binds_custom.cfg` (each weapon sets the `weaponSwitch` target).

### Run-once hook
An alias that disables itself after running (`set <hook> vstr null`, with `set null ""`), re-armed with `reset`. Prevents repeated side effects, e.g. `vid_restart` or a team switch when the class key is pressed again.
```
set null ""
set preJoinHookb "vstr ta_Allies; vstr setTeamAllies; set preJoinHookb vstr null; reset preJoinHookr"
```
Example: `class/cs_backend.cfg` (pre/post join hooks, re-armed by `autoexec_default.cfg` and the spectator hook).

### Change guard (run only when the context changed)
Runs an action only if the context (e.g. the mod) differs from the one it last ran in, without string comparison. `modLast` points to a per-context alias (`modIs_<mod>`) that is armed with the action. Before checking, the current context disables its own alias, so `vstr modLast` does nothing if the last context was the current one, and runs the action if it was any other.
```
// mods/<mod>/autoexec.cfg (the action itself): remember this context, arm its alias
set modLast "vstr modIs_nitmod"
set modIs_nitmod "exec autoexec.cfg"

// mods/<mod>/autoexec_mod.cfg (the check, exec'd by every map/default autoexec)
set modIs_nitmod "vstr null"
vstr modLast
set modIs_nitmod "exec autoexec.cfg"
```
- The action must set `modLast` to its own context, otherwise it runs every time.
- The action must also arm its own alias: `vstr` on an undefined cvar does nothing, so without it a switch before the first check would not run the action.
- The armed value must not depend on the old context: `exec autoexec.cfg` resolves in the current mod folder when it runs.
- Unlike a run-once hook, it re-arms itself for the next context change without anyone calling `reset`.

Example: mod switch reload (`mods/<mod>/autoexec_mod.cfg`); why it is needed and how it is wired: `docs/autoexec.md`.

### Extension points and shared resets
Empty or default aliases that other scripts fill in (`cs_soldier_mortar`, `classHook`, `resetToggles`), and one reset alias per feature that every exit path uses (`resetSniper` is used by the sniper toggle *and* the class reset). Keeps cleanup in one place.

### Remember-and-resume (movement)
On press, store what to resume; on release, run the stored command of the opposite key. A harmless command (`set cl_noTaunt 0`) or `vstr null` acts as "nothing to resume".
```
bind w "+vstr forwardon forwardoff"
set forwardon  "-back; +forward; set forwarding +forward"
set forwardoff "-forward; vstr backing; set forwarding set cl_noTaunt 0"
```
Example: `scripts/movement.cfg` movement script (no blocked movement when opposite directions overlap).

### Feedback
Every state change plays a menu sound (`vstr playSelect` / `vstr playCancel`, defined in `scripts/common.cfg`) and echoes the new state, so the result is visible without opening the console.

## Useful console commands for debugging

`cvarlist [filter]`, `cmdlist`, `bindlist`, `condump <file>`, `writeconfig <file>`, `cvar_restart` (resets all cvars to hardcoded defaults).

## Sources

Vanilla-era guides (concepts still apply; cvars, limits and details may be outdated — the facts above were checked against the ET: Legacy source):
- https://wolfenstein.fandom.com/wiki/Intro_to_Scripting
- https://wolfet.vexer.info/configs-guide-part-1
- https://www.net-clan.com/WolfWeb/scripts.htm