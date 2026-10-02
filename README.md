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

Config, scripts and keybinds for **Wolfenstein: Enemy Territory** on **ET: Legacy**, one script set for every mod (legacy, nitmod, jaymod; etpub, silEnT and ETJump with default values, not tested in game): class scripts, autoexecs per map, team and mod, a voicechat menu, an in-game server menu, settings and voicechat menus per server, plus a keymap tool that renders the live binds as a keyboard overview.

## Requirements

- Linux
- ET: Legacy 2.86 or newer
- Python 3, only for the optional tools in `tools/`

Windows support is not planned, but only the setup is Linux-specific: the cfgs reach each other through the `profile/` and `profiles/` links instead of absolute paths, and machine-specific values live in `settings.conf`. A Windows port mainly needs a port the existing shell scripts.

## Setup

1. Clone the repo anywhere:

   ```sh
   git clone https://github.com/JoAllg/etlegacy-scripts.git <repo>
   ```

2. Run `deploy.sh`:

   ```sh
   <repo>/deploy.sh
   ```

   The first run detects the game (executable, fs_homepath, fs_basepath) and writes `settings.conf`, asking for anything it cannot find (delete a line to detect it again). It links the repo into the mod folders, backs up and links the GUID keys (`guid_backup/`) and creates `user.cfg` from `user.example.cfg`. Rerun it after pulling: it adds new `user.example.cfg` settings to your `user.cfg` and lists them. It also rewrites the `HUD VALUES` block of `user.cfg` from your legacy HUD, so run it (or start through `launcher.sh`) after moving the popups in the HUD editor.

   A `profiles/` folder the game already created in a mod folder blocks the link to this repo; the script offers to rename it to `profiles.bak_<date>`.

3. Put your player name into `user.cfg` (name + the `PGDN` name cycle) and adjust fps, mouse, fov, refresh rate, fullscreen resolution and network rates. It is gitignored.

4. Start the game. The profile is `default`; the mod's `autoexec.cfg` runs the whole chain.

   ```sh
   ./launcher.sh [game arguments]    # e.g. ./launcher.sh +set fs_game nitmod +connect <ip>
   ./launcher32.sh [game arguments]  # 32-bit client, for i386-only mods
   ```

   Starting the game without `launcher.sh`: add `+set com_hunkMegs 512 +set com_zoneMegs 192 +set com_soundMegs 192` to its arguments (recommended, `launcher.sh` passes them). `com_zoneMegs` can only be set on the command line.

   `launcher.sh` starts the game and handles everything around it:

   - Downloaded maps become available for local hosting (`tools/link_maps.py`).
   - New maps get their spawn menu, the map autoexec `autoexec_<map>.cfg` (`tools/spawnpoints/spawnpoints.py`).
   - Links and settings are refreshed without questions, each taking its safe default (`deploy.sh`).
   - The in-game [server menu](#server-menu) stays up to date (`tools/servermenu.py`).
   - Your [settings per server](#settings-per-server) apply when you join one (`tools/serverconfig.py`).
   - The [live keymap](#live-view-while-playing) follows your class in the browser (`tools/keymap/live.py`).

   The last three run next to the game and stop when it exits. The terminal shows only the warnings of these tools; the game's output is in `<fs_homepath>/<mod>/etconsole.log`.

## In game

- `F3` re-execs the definitions (after a server enforced its own values); `F1` is the full reset.
- The console prints the load order as an indented `*** ... LOADED!` tree; a missing line means that file was not found.
- On a map load the mod execs `autoexec_<mapname>.cfg` (spawnpoint menu); team and class autoexecs follow on respawn. Per-mod support: `docs/autoexec.md`.
- The spawnpoints of the 1944 maps (`autoexec_1944_*.cfg`, by +Kommando+) do not always work because of a map scripting bug.

Console, commands, FPS/network settings, recoil and spread: `docs/gameplay.md`.

## Sound (OpenAL HRTF)

For headphones, HRTF places every sound in its exact direction including height (better than a virtual surround sink). Requires the OpenAL backend (`s_initsound 2`, set in `default/cvars.cfg`). Create `~/.config/alsoft.conf`:

```ini
[general]
channels = stereo
stereo-mode = headphones
stereo-encoding = hrtf
```

Output to the plain headphone device. Applies after `snd_restart`; check with `openal-info | grep -i hrtf`.

## Keymap

A keyboard + mouse overview of the binds that are actually loaded, with short action names. The tool emulates the exec chain, presses every bound key and derives the views, toggles (⇄), cycles (⟳) and menus (☰) from what changes.

```sh
python3 tools/keymap/keymap.py              # writes tools/keymap/keymap.html (mod: KEYMAP_MOD in settings.conf)
python3 tools/keymap/keymap.py --mod legacy # other mod (mods bind different commands)
python3 tools/keymap/keymap.py --missing    # commands that still have no name
```

`keymap.html` is a single self-contained file. Tabs switch between Base and the class bind sets, hovering a key shows which keys it changes, the tooltip shows the raw command and its `file:line`. Rerun after changing binds; new commands get their names in `tools/keymap/labels.json`.

### Live view while playing

```sh
python3 tools/keymap/live.py
```

Serves the page at <http://127.0.0.1:27999/>, opens the browser and follows the running game: picking a class switches to its tab, a reset returns to Base, a mod switch reloads the page for that mod. It keeps running across game restarts. Requires `logfile 2` (set in `default/cvars.cfg`). Details: `tools/keymap/README.md`.

## Server menu

`KP_MINUS` lists your favorite servers of the server browser in game, in aligned columns `name  playing+spectators+bots/slots  map  ping  mod` (playing humans green, spectators cyan, bots grey: `MENU_PLAYING`, `MENU_SPEC`, `MENU_BOTS` in `settings.conf`), sorted by playing humans. A number key connects, `TAB` shows the next page (or refreshes), `KP_MINUS` or `ESC` closes it.

```sh
python3 tools/servermenu.py
```

The game can't query servers from a script, so this helper has to run next to it: it asks the favorites every 5 seconds and writes the menu pages. The time in the menu heading shows how old the list is.

## Settings per server

Your own settings and the voice chat of a server, applied when you join it. Details: `docs/serverconfigs.md`.

```sh
python3 tools/serverconfig.py                    # runs next to the game
python3 tools/serverconfig.py add <id> [address] # row for a server in servers.tsv (default: the server you are on) + its cfg
python3 tools/voicemenu.py <id> <pk3>            # the server's own voice chat, from its pk3
```

- `<id>` is a short name you pick for a server or a clan, e.g. `xy` for all servers with `[xY]` in their name: 1 to 4 characters of lowercase letters, digits and `_`. It names that server's files (`serverconfigs/<id>.cfg`, `scripts/vsays/servers/<id>/`) and an alias in game, so it can't be the clan tag itself: tags contain colors, spaces, brackets or `|`, which don't work in a file path inside a bind or in an alias name.
- `default/serverconfigs/servers.tsv` says which servers an id stands for: `<id><TAB><text in the server name>`, e.g. the clan tag as the server shows it, which covers every server of the clan (format: `servers.example.tsv`). If a clan renames its servers, only this text changes; several rows may share one id.
- `default/serverconfigs/<id>.cfg` holds your settings for them; `default.cfg` resets them on every other server, so each value set in a server cfg needs its normal value there. They override `user.cfg`.
- With voice chat pages for the id, `TAB` in the voice chat (`V`) opens the server's own menu.

The game can't tell a script which server it is on, so this helper reads the console log and asks the server for its name.

## Agent skills

The repo ships project skills in `.claude/skills/` (`.agents` links to `.claude`), usable by [Claude Code](https://claude.com/claude-code) and every agent that reads `.agents/skills/` (`/<name>` or picked up automatically):

| Skill | Use |
| --- | --- |
| `keymap` | regenerates `tools/keymap/keymap.html` and names new binds in `labels.json`; after bind, class script or menu layer changes |
| `vsay-highlight` | colors all vsay texts and echo menus with the `VSAY_*` / `MENU_*` colors from `settings.conf`, previews and changes them, highlights key words; after `tools/voicemenu.py` or new vsay texts |

## Where things live

| Path | Contents |
| --- | --- |
| `user.cfg` | personal settings, gitignored (template: `user.example.cfg`) |
| `settings.conf` | machine paths and color preferences, written by `deploy.sh`, gitignored |
| `default/` | the profile: `cvars.cfg`, `binds_*.cfg`, `definitions.cfg`, `state.cfg` |
| `default/scripts/` | class scripts, spawn menu, voicechat, general scripts |
| `default/mods/<mod>/` | per-mod `autoexec.cfg` and the values that differ per mod |
| `default/autoexecs/`, `default/maps/` | per-map spawnpoints and location name overrides |
| `default/serverconfigs/` | settings per server (`default.cfg`; your `servers.tsv` and `<id>.cfg` are gitignored) |
| `docs/` | mirrored to the [wiki](https://github.com/JoAllg/etlegacy-scripts/wiki) on push (`.github/workflows/wiki.yml`): game knowledge (`gameplay.md`), load order, scripting patterns, conventions, key names, colors, characters |
| `tools/` | keymap renderer, generators for spawnpoints and server voice menus, server menu and server settings helpers, nitmod stock shield (`tools/README.md`) |

## Developing

Load order and mod support: `docs/autoexec.md`. Script patterns and limits: `docs/scripting.md`. Naming and file conventions: `docs/conventions.md`.

- Syntax highlighting in VSCode: [quake2-config-syntax](https://marketplace.visualstudio.com/items?itemName=amokmen.quake2-config-syntax) and [quake2-config-theme-dark](https://marketplace.visualstudio.com/items?itemName=amokmen.quake2-config-theme-dark) (recommended by `.vscode/extensions.json`).
- Test changes: `F3` in game, `/condump <file>` saves the console.
- `INS` toggles fullscreen ⇄ borderless window at desktop resolution to reach the editor (`scripts/display.cfg`, runs `vid_restart`). `Alt + Enter` toggles fullscreen without a restart but keeps the resolution.
