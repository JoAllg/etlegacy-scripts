```
/////////////////////////////////////////////////////////////////
//                                                             //
//  ████████  █████  ██████   █████  ███    ██ ██ ███████ █    //
//     ██    ██   ██ ██   ██ ██   ██ ████   ██ ██ ██           //
//     ██    ███████ ██████  ███████ ██ ██  ██ ██ ███████      //
//     ██    ██   ██ ██   ██ ██   ██ ██  ██ ██ ██      ██      //
//     ██    ██   ██ ██   ██ ██   ██ ██   ████ ██ ███████      //
//                                            Wolfenstein:     //
//                                            Enemy Territory  //
//                                            Scripts & Tools  //
//                                                             //
/////////////////////////////////////////////////////////////////
```

Config, scripts and keybinds for **Wolfenstein: Enemy Territory** on **ET: Legacy**, one script
set for every mod (legacy, nitmod, etpub, jaymod, silEnT, ETJump): class scripts, spawnpoint
autoexecs, a voicechat menu, weapon-switch and network toggles, plus a keymap tool that renders
the live binds as a keyboard overview.

## Requirements

- Linux
- ET: Legacy 2.86 or newer
- Python 3, only for the optional tools in `tools/`

Windows support is not planned, but only the setup is Linux-specific: the cfgs reach each other
through the `profile/` and `profiles/` links instead of absolute paths, and machine-specific
values live in `settings.conf`. A Windows port mainly needs a `deploy.sh` equivalent (links into
the mod folders).

## Setup

1. Clone the repo anywhere:

   ```sh
   git clone https://github.com/JoAllg/etlegacy-scripts.git <repo>
   ```

2. Pick your mods in `deploy.sh` (`MODS`, `AUTOEXEC_MODS`, `GUID`), then run it:

   ```sh
   <repo>/deploy.sh
   ```

   The first run detects the game (executable, fs_homepath, fs_basepath) and writes
   `settings.conf`, asking for anything it cannot find (delete a line to detect it again). It
   links the repo into the mod folders, backs up and links the GUID keys (`guid_backup/`) and
   creates `user.cfg` from `user.example.cfg`. Rerun it after pulling: it adds new
   `user.example.cfg` settings to your `user.cfg` and lists them.

   A real `profiles/` folder the game already created in a mod folder (e.g.
   `~/.etlegacy/legacy/profiles/`) would hide this repo; the script asks to rename it to
   `profiles.bak_<date>`.

3. Put your player name into `user.cfg` (name + the `PGDN` name cycle) and adjust fps, mouse,
   fov, refresh rate, fullscreen resolution and network rates. It is gitignored.

4. Start the game. The profile is `default`; the mod's `autoexec.cfg` runs the whole chain.

## In game

- `F3` re-execs the definitions (after a server enforced its own values); `F1` is the full reset.
- The console prints the load order as an indented `*** ... LOADED!` tree; a missing line means
  that file was not found.
- On a map load the mod execs `autoexec_<mapname>.cfg` (spawnpoint menu); team and class
  autoexecs follow on respawn. Per-mod support: `docs/autoexec.md`.
- The spawnpoints of the 1944 maps (`autoexec_1944_*.cfg`, by +Kommando+) do not always work
  because of a map scripting bug.

Console, commands, FPS/network settings, recoil and spread: `docs/gameplay.md`.

## Sound (OpenAL HRTF)

For headphones, HRTF places every sound in its exact direction including height (better than a
virtual surround sink). Requires the OpenAL backend (`s_initsound 2`, set in `default/cvars.cfg`).
Create `~/.config/alsoft.conf`:

```ini
[general]
channels = stereo
stereo-mode = headphones
stereo-encoding = hrtf
```

Output to the plain headphone device. Applies after `snd_restart`; check with
`openal-info | grep -i hrtf`.

## Keymap

A keyboard + mouse overview of the binds that are actually loaded, with short action names. The
tool emulates the exec chain, presses every bound key and derives the views, toggles (⇄),
cycles (⟳) and menus (☰) from what changes.

```sh
python3 tools/keymap/keymap.py              # writes tools/keymap/keymap.html (mod: KEYMAP_MOD in settings.conf)
python3 tools/keymap/keymap.py --mod legacy # other mod (mods bind different commands)
python3 tools/keymap/keymap.py --missing    # commands that still have no name
```

`keymap.html` is a single self-contained file. Tabs switch between Base and the class bind sets,
hovering a key shows which keys it changes, the tooltip shows the raw command and its
`file:line`. Rerun after changing binds; new commands get their names in
`tools/keymap/labels.json`.

### Live view while playing

```sh
./keymap-live.sh          # = python3 tools/keymap/live.py
```

Serves the page at <http://127.0.0.1:27999/>, opens the browser and follows the running game:
picking a class switches to its tab, a reset returns to Base, a mod switch reloads the page for
that mod. It keeps running across game restarts. Requires `logfile 2` (set in
`default/cvars.cfg`). Details: `tools/keymap/README.md`.

## Where things live

| Path | Contents |
| --- | --- |
| `user.cfg` | personal settings, gitignored (template: `user.example.cfg`) |
| `settings.conf` | machine paths and color preferences, written by `deploy.sh`, gitignored |
| `default/` | the profile: `cvars.cfg`, `binds_*.cfg`, `definitions.cfg`, `state.cfg` |
| `default/scripts/` | class scripts, spawn menu, voicechat, general scripts |
| `default/mods/<mod>/` | per-mod `autoexec.cfg` and the values that differ per mod |
| `default/autoexecs/`, `default/maps/` | per-map spawnpoints and location name overrides |
| `docs/` | game knowledge (`gameplay.md`), load order, scripting patterns, conventions, key names, colors, characters |
| `tools/` | keymap renderer, generators for spawnpoints and server voice menus, nitmod stock shield (`tools/README.md`) |

## Developing

Load order and mod support: `docs/autoexec.md`. Script patterns and limits: `docs/scripting.md`.
Naming and file conventions: `docs/conventions.md`.

- Syntax highlighting in VSCode: [quake2-config-syntax](https://marketplace.visualstudio.com/items?itemName=amokmen.quake2-config-syntax)
  and [quake2-config-theme-dark](https://marketplace.visualstudio.com/items?itemName=amokmen.quake2-config-theme-dark)
  (recommended by `.vscode/extensions.json`).
- Test changes: `F3` in game, `/condump <file>` saves the console.
- `INS` toggles fullscreen ⇄ borderless window at desktop resolution to reach the editor
  (`scripts/display.cfg`, runs `vid_restart`). `Alt + Enter` toggles fullscreen without a
  restart but keeps the resolution.
