# Keymap

Keyboard (German ISO QWERTZ) + mouse overview of the live binds, with short action names instead of commands.

```
python3 tools/keymap/keymap.py              # writes tools/keymap/keymap.html (default mod: nitmod)
python3 tools/keymap/keymap.py --mod legacy
python3 tools/keymap/keymap.py --missing    # commands without a name, unused names
python3 tools/keymap/live.py                # opens the keymap in the browser, follows the class picked in game
python3 tools/keymap/keymap.py --selftest
```

Nothing in `keymap.py` is written for a particular script. The keymap is derived in four steps:

1. **Emulate** the exec chain in a minimal ET console → bind table + aliases.
2. **Build views**: Base and one per class bind set.
3. **Press** every bound key in every view and diff the state → icon (toggle / cycle / menu) and the keys it affects (hover).
4. **Name** every command from `labels.json` and render the HTML.

Names are maintained with the `keymap` skill (`.claude/skills/keymap/SKILL.md`).

## 1. Console emulator

Rules follow the ET: Legacy source (`src/qcommon/cmd.c`, `cvar.c`, `src/client/cl_keys.c`, `src/cgame/cg_consolecmds.c`).

- **Command splitting** (`Cbuf_Execute`): a new command starts at every newline, and at `;` outside quotes and outside a `//` comment. So `bind x "kill;forcetapout"` stays one bind.
- **Tokens** (`Cmd_TokenizeString`): `"..."` is one token; `//` ends the line (except directly after `:`).
- **Emulated commands**; everything else (`wait`, `echo`, `cg_fov 90`, ...) is ignored:

  | Command | Effect |
  |---|---|
  | `exec <file>` | runs `<HOMEPATH>/<mod>/<file>` (`.cfg` added if no extension, HOMEPATH from `settings.conf`). Paths resolve through the real symlinks of `deploy.sh`, so `exec mod_general.cfg` reaches the mod's file like in game. Missing file = no-op. Files that tools write while the game runs are skipped (`servermenu/` pages, `serverconfigs/current*.cfg`): they hold your favorite servers and the server joined last |
  | `set` / `seta` / `sets` / `setu <name> <value...>` | stores the alias, arguments joined with spaces |
  | `reset <name>` | back to the value the alias had when it was first created (engine `resetString`). This is why `state.cfg` sets `spawnSelector` twice |
  | `vstr <name>` | runs the alias value (undefined alias = no-op) |
  | `bind <key> <command...>` / `unbind <key>` / `unbindall` | bind table |

- **Case**: alias names are case-insensitive. Key names: a single character is lowercased; other names are uppercased, with `ALT`/`CTRL`/`SHIFT` = `LEFTALT`/`LEFTCTRL`/`LEFTSHIFT`.
- Every `bind` and `set` records its `file:line`: the line itself, or, when run through `vstr`, the line where that alias was set. This shows in the tooltip and in `--missing`.
- `vstr`/`exec` nesting stops at depth 64 (guards against alias loops).

## 2. Views

Constants at the top of `keymap.py`:

| Constant | Value | Purpose |
|---|---|---|
| `START` | `exec autoexec.cfg` | game start: definitions + `user.cfg` + `state.cfg` |
| `SCENARIO` | `exec autoexec_fueldump.cfg; vstr teamAxis; exec autoexec_axis.cfg` | a team and a map autoexec, so the spawn selector (`ENTER`) has spawnpoints |
| `CLASS_HOOK` | `vstr classHook` | runs `cs_default`, the binds every class starts with |
| `CLASS_ALIAS` | `cs_<class>_<weapon>` | class script assignments (`scripts/classcript.cfg`) |

- **Base** = `START` + `SCENARIO` + `CLASS_HOOK`.
- **Free keys** / **All keys** (buttons in the "View" group): not a state of the game but a lookup — every drawable key shows its in-game bind name. "Free keys" highlights the keys no view binds and dims the rest; "All keys" shows every name equally. The console key shows 🔒.
- **Class views**: for every alias matching `cs_<class>_<weapon>`, Base + `vstr classHook; vstr cs_<class>_<weapon>`. The run goes directly, not through the class keys.
- **Merging**: variants with identical bind tables share one tab ("Medic: smg, sten"). Variants identical to Base are listed in the Base tab name ("Base · Soldier: fthrower, mg42, panzer").
- **Yellow key**: its bind differs from Base (compared case-insensitively, ignoring extra whitespace).

## 3. Key presses

Each bound key is pressed from the view's state; afterwards the state is restored.

- **One press** runs what the engine runs:
  - `+vstr a b` → `vstr a` (key down), then `vstr b` (key up). The state is checked after each half.
  - Other `+commands` (`+attack`, ...) → nothing; they change no binds.
  - Any other bind → the whole bind.
- The key is pressed up to `TAPS = 6` times, each time using its *current* bind. It stops early when aliases and binds are back at the start (a toggle after 2 presses).
- Only one level deep: hovering `v` shows the chat categories on the number row, not the vsays behind a category.

### Pointers

The **pointers** of a press are the aliases it reads via `vstr` and that change during the presses. For each one, all values seen are collected. Example: `F5` reads `cycleWeaponSwitch` and sets it to 3 different values.

"Set by a script" below means a `set`/`reset` executed from an alias. Sets while a file runs via `exec` don't count, so `F1` (`exec autoexec.cfg`) and `F3` (re-exec definitions) don't look like they set anything.

### Icon (first match wins)

| Icon | Mode | Rule | Current keys |
|---|---|---|---|
| ⟳ | cycle | the press reads **and sets** an alias whose name **starts with `cycle`**; it counts even when set to its current value. Or: a pointer takes **more than 2** values | `F5`, class keys (`KP_HOME`, `KP_UPARROW`, `KP_PGUP`, `KP_LEFTARROW`, `KP_5`), `HOME`, `END`, `PGUP`, `PGDN`, `DEL`, `+`, `-` |
| ☰ | menu | at least `MENU_MIN = 4` other keys get **distinct** new actions (see below) | `v`, `ENTER`, `KP_END`, `KP_PGDN` |
| ⇄ | toggle | a pointer takes exactly 2 values | `MOUSE3`, `F8`, `F9`, `F12`, `INS`, `LEFTCTRL`, `g` (mortar) |
| ⤓ | hold | the bind is a `+command` (`+attack`, `+vstr a b`), so it works while the key is held; shown when the key has no mode icon | `MOUSE1`, `LEFTALT`, the movement keys, the class actions on `MOUSE4`/`MOUSE5` |
| none | | no pointer, no hold | |

- **Why cycle wins over menu**: a class key stays a cycle however many keys its class script rebinds.
- **Why the name counts even for an unchanged value**: a class with a single weapon variant sets `cycle<Team><Class>` back to the same value.
- **Menu detail**: new actions are counted two ways, and the larger count decides:
  - keys whose **bind** changed, counted by distinct new bind (unbinding doesn't count), e.g. `v` binds 1–7 + `TAB` to 8 categories;
  - keys whose bind stayed the same but whose **called alias** (the `vstr`/`+vstr` target of the bind) changed or was set by a script, counted by distinct new alias values. E.g. `KP_END` sets `so`/`me`/`en`/`fo`/`co` to 5 different class aliases.
  - `KP_DOWNARROW` (spectator) and `KP_RIGHTARROW` (class reset) set all class keys to the same `vstr noTeam`, which is 1 distinct action, so no menu.
  - Set by a script counts even with an unchanged value, so the team key of the team already chosen in `SCENARIO` is still a menu.

### Affected keys (hover)

Hovering a key dims all others and highlights every key that changed in any press step, showing the name(s) it had there:

- its **bind** changed (`F5` → `MOUSE2` "Alt fire", `ENTER` → spawns on the number row);
- or its **called alias** (the `vstr`/`+vstr` target of its bind) changed or was set by a script. For example:
  - the team keys → class keys
  - `1` → `MOUSE2`, because it sets `weaponSwitch`
  - the class keys → `MOUSE3`, because `resetToggles` resets `sniperToggle`
  - `F4` → `v`, because `resetVoiceChat` resets `voiceChatSelector`
- or one of its **own pointers** was set by a script. Own pointers are the aliases a single press of that key reads at any depth *and* sets itself (`pointers()`, computed once per key per view). For example:
  - `F4` → `ENTER`: `ENTER` runs `spawnSelector` → `spawnSelector2` → `spawnSelectorMap` → `spawnSelector3` and sets `spawnSelector3`, which `resetSpawnSelector` resets
  - each class key → the other class keys: `classKeys<Team>` points the other class keys back to their first press (which resets their `cycle<Team><Class>`)
- Aliases another key only *reads* don't count, e.g. `END` (FPS cycle) sets `maxFpsNormal`, which the weapon keys read. Otherwise nearly every script key would light up.

The key itself is never listed.

Each highlighted key also shows its **icon in the changed state**: the script restores the state right after the change and runs the same press detection for that key there. E.g.:
- `MOUSE3` → `LEFTALT` "Crouch" ⇄: Sniper Mode rebinds it to the crouch toggle.
- `v` → the chat categories ☰: each opens its vsay list.
- the team keys → class keys ⟳.

In that check, binds that return to the view's normal binds don't count as new actions. So a key that *closes* a menu is not a menu itself: spawn 1–7 bind the number row back to the weapons.

Keys with a hover function (at least one affected key) get a mild accent border.

## 4. Names and rendering

- `labels.json`: `"<bind command>": "<name>"`. Lookup is case-insensitive and ignores extra whitespace.
- **Unnamed** commands get a guessed name from the alias (`vstr fooBarON` → "foo Bar") and a dashed border. `--missing` lists them with their keys (`F6 -> MOUSE2` = seen on MOUSE2 while hovering F6), the value of the called alias and `file:line`. It also lists unused names; these can be the other mod's variant (`+attack2` / `weapalt`), so check every mod before removing one.
- **Name rule**: a name belongs to the command, not the key or class. The same command always shows the same name (`<` `vstr weapon7` = "Weapon 7" for medic and engineer).
- **Layout** (`ROWS`, `EXTRA`, `MOUSE`): German QWERTZ with the bind names from `docs/keybinds.md`: `ß` = `US_MINUS`, `´` = `US_EQUALS`, `ü` = `US_LEFTBRACKET`, `ö` = `US_SEMICOLON`, `ä` = `US_APOSTROPHE`, `^` = console key (not bindable). Mouse: `MOUSE1`–`MOUSE5`, `MWHEELUP`, `MWHEELDOWN`.
- **Engine keys** (`ENGINE_KEYS`, `ENGINE_COMBOS`): behavior no cfg can change, from the engine source. The key left of 1 (`^`) and the characters in `cl_consoleKeys` become the console key before binds are looked up (`src/sdl/sdl_input.c` `IN_IsConsoleKey`), and Shift+Esc toggles the console too (`src/client/cl_keys.c` `CL_KeyEvent`). `^` shows "Console" 🔒.
- **Combinations & other keys** (sidebar): the engine combos plus every bound key that isn't drawn on the map, per view. Keys that are typed as a combination on the German layout get it in front (`COMBO_KEYS`: `` ` `` = Shift+´, `~` = AltGr++).
- **Legend**: each entry is marked with the views it applies to (`data-when`), so a key name view only shows its own entries (free / in use / engine key).
- **Page**: `keymap.html` is self-contained (inline SVG, data as JSON, a little JS). Top: the "Class settings" tabs switch views. Below: the keyboard at full width; under it the mouse (same scale) on the left and the legend on the right. On narrow screens only the keyboard scrolls sideways, and mouse and legend stack. The tooltip shows key, raw command and `file:line`. Unbound keys are faint. It follows the system light/dark theme.

### Search

The search field in the header searches every bind of every class view plus every layer entry from the hover data (key `T` gets name `L` after pressing `S`). Entries with the same key, branch, name and command are merged, with the views they occur in. Layer entries that only reset a key to its own bind in that view (`F4` → `ENTER`) or bring back its Base bind (class keys leaving the mortar view restore `g`) are left out; the Base bind is listed already.

Every layer entry records the view its state lands in (`keymap.py` compares the bind table after the press with the views). A class bind (not in Base) and the layer entries that land in its views are one result per branch key: `<` "Weapon 7" after `KP_PGUP` in Engineer, and after `KP_UPARROW` in Medic. A class key lands in the variant its first press picks, so other variants of a cycle (Covops: fg42, rifle) stay without branch.

- **Fuzzy**: every word must match the name, the command (alias names, e.g. `weaponswitch`), the branch key or the view names ("every class" is not searched, it would match everything); a substring beats scattered letters, the name weighs most.
- **Key**: a query that starts a bind name, key legend or German combination (`f6`, `mouse4`, `pos1`, `shift+´`) lists everything on that key first: its direct binds, then what other keys give it.
- **Result line**: key, name + icon, then the branch: `after <key> "<name>" · in <views>` (`every class` = in all views).
- **Hover / arrow keys** preview the result: the view switches, the key shows the name it has there (highlighted) and the branch key is outlined. Leaving the list goes back. **Click / Enter** pins it until a tab click or `Esc` (anywhere on the page, keeps the search text). The ✕ in the field (shown while there is text or a pin) clears both. The field is `type="text"`: the native search field has its own ✕ and clears the text on `Esc`.
- One layer only, like hover: vsays behind a chat category are not searchable.

## Live view (`live.py`)

Opens `http://127.0.0.1:27999/` and switches the "Class settings" tab to the class picked in the running game. Manual clicks work until the next change.

- **Finding the game**: the most recently written `<HOMEPATH>/<mod>/etconsole.log` (`HOMEPATH` of `settings.conf`). The engine opens the log once, after `autoexec.cfg`, in the mod folder of game start and keeps it until quit (`src/qcommon/common.c`). Views always come from this repo.
- **Needs `logfile 2`** (`default/cvars.cfg`): `logfile 1` buffers the log in 4 KB chunks.
- The log is read from the start (the game truncates it at launch), then followed. A truncated log (next game start) or a newer log of another mod is read again from its start.
- The page polls `/state` every 500 ms: `{mod, cls}`. A different mod reloads the page.

| Log line (colors stripped, whole line) | Effect |
|---|---|
| `Sys_LoadDll(<home>/<mod>/ui.mp…` or `cgame.mp…` | page for that mod, if `~/.etlegacy/<mod>/autoexec.cfg` exists (built once per mod, ~2 s) |
| echo text of a class alias, e.g. `[CLASS] Covert Ops: FG42` | tab containing `cs_covops_fg42` |
| `*CLASSES CLEANED*`, `>>> AUTOEXEC LOADED!` (`BASE_MARKERS`) | Base |

Class echo texts are found in the emulator: every alias that runs a `cs_<class>_<weapon>` alias and an alias whose value is an `echo` (`b_co2` → `cs_covops_fg42`, `echo-b_co2`). Connected, `echo` goes through `cpm`, which still prints to the console (verified on nitmod and in the legacy source).

Not seen: a class picked only in the limbo menu (binds don't change then), F3, team keys and server joins (binds stay, so the tab stays).

## Naming contract

The detection relies on these names; keep them when renaming scripts, or adjust the constants:

- `cycle<Feature>` for cycle pointers (`docs/conventions.md`), e.g. `cycleWeaponSwitch`, `cycleAxisSoldier`, `cycleCrosshairSizeUp`.
- `cs_<class>_<weapon>` for class script assignments, and `classHook`.
- `teamAxis`, `autoexec_fueldump.cfg`, `autoexec_axis.cfg` in `SCENARIO`.
- `live.py`: class aliases run `cs_<class>_<weapon>` and an echo alias in the same alias; the reset echoes match `BASE_MARKERS`.

Toggles and menus need no naming; they are detected from behavior.

## Limits

- `wait`, cvar commands (`cg_fov 90`) and values forced by servers are ignored. If a view looks wrong, compare it with `/bindlist` in game.
- Spawn names come from the one map and team in `SCENARIO`.
- Hover shows one level of layers only.
- `MENU_MIN` is a threshold: a non-menu key that gives 4 or more keys distinct new actions without setting a `cycle*` alias would show ☰.

## Selftest

`--selftest` checks:
- the tokenizer and command splitting;
- Base `MOUSE2`, and medic `MOUSE4`;
- the icons of `v`, `ENTER`, the team and class keys, `F5`, `MOUSE3`, spectator and class reset;
- the hover keys of `v`, `ENTER`, `F5`, and `F4` (must include `v` and `ENTER`), `MOUSE3` → `LEFTALT` as "Crouch" ⇄, a class key lands in its class view (`KP_UPARROW` → Medic), no ☰ on the spawn keys under `ENTER`, ☰ on the chat categories under `v`;
- a simulated single-variant class that rebinds 4 keys and must stay ⟳.

`live.py --selftest` checks the class echo map (`[CLASS] Covert Ops: FG42` → `covops_fg42`) and a sequence of log lines: mod switch, class echo, a `/cvarlist` line with the reset echo (must not count), reset, a mod without autoexec (page stays), `AUTOEXEC LOADED!`.
