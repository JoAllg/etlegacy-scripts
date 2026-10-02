# Tools

Optional Python 3 helpers (stdlib only). They read the game paths and color preferences from `settings.conf` (via `helpers/settings.py`), so run `deploy.sh` first. All have a `--selftest` and reject unknown arguments.

## keymap/

Keyboard + mouse overview of the live binds. `keymap.py` emulates the exec chain, presses every bound key and writes `keymap.html` (one self-contained page, tabs per class bind set). New commands get their short names in `labels.json` (`--missing` lists unnamed ones). `live.py` serves the page and switches to the class picked in the running game by following the newest `<HOMEPATH>/<mod>/etconsole.log`. Details: `keymap/README.md`.

```sh
python3 tools/keymap/keymap.py [--mod <mod>] [--missing]
python3 tools/keymap/live.py
```

## spawnpoints/

`spawnpoints.py` generates map autoexecs with a spawnpoint menu from the map pk3s into `default/autoexecs/`: every `setspawnpt N` whose closest spawn spot lies in another room becomes a menu entry, labeled with the objective and the location name. A rerun reads only the maps whose pk3, location file or autoexec changed since the last run (maps named on the command line are always read), only touches files whose content changes and prints them; an existing autoexec of the map is replaced (its settings block and tail are kept).

```sh
python3 tools/spawnpoints/spawnpoints.py [map ...]
```

## voicemenu.py

Copies a server's quick chat menu (`V`) from its pk3 into voicechat pages in `default/scripts/vsays/servers/<clan>/`; in game they are on `TAB` of the voice chat while playing on that server (`serverconfig.py`). `<clan>` is the server's id in `default/serverconfigs/servers.tsv`, and the headings carry its tag as the server writes it (taken from `[address]` or from a server the game connected to before). Pages that duplicate the stock menu are left out; custom vsays the menu leaves out go on extra pages behind `TAB`. The pages have the format of the stock pages (`default/scripts/vsays/chat/`) and share their `vsay<key>` aliases. A rerun after a new server pack keeps edited texts and reports added and removed vsays.

```sh
python3 tools/voicemenu.py <clan> <pk3> [address]
```

## vsaycolors.py

Colors all vsay texts with the `VSAY_*` colors and the echo menus with the `MENU_*` colors of `settings.conf`. `preview` writes `vsaycolors.html` (current vs proposed colors), `apply` recolors after a color change, `todo` / `done` track which texts were reviewed for highlights (`default/scripts/vsays/vsaycolors.tsv`).

```sh
python3 tools/vsaycolors.py status | preview [role=^c ...] | apply | todo | done
```

## servermenu.py

Feeds the in-game server menu (`KP_MINUS`, `default/scripts/servermenu.cfg`): while it runs, it asks the favorite servers of the server browser for their state every 5 seconds and writes the menu pages to `default/servermenu/`. Each server shows as `name  playing+spectators+bots/slots  map  ping  mod` in columns aligned with spaces, sorted by playing humans; the number keys connect. Start it before or while playing and leave it running; `--once` prints the list in the terminal. How servers are queried: `docs/serverquery.md`.

```sh
python3 tools/servermenu.py [--interval 5] [--once]
```

## serverconfig.py

Settings and voice chat per server (`docs/serverconfigs.md`). While it runs, it follows the game's console log, asks a joined server for its name and looks it up in `default/serverconfigs/servers.tsv` (`<id><TAB><text in the server name>`, yours to maintain; format: `servers.example.tsv`). It then writes `current.cfg`, through which the game execs `default.cfg` and that server's `<id>.cfg`, and `current_vsay.cfg`, which puts the server's voice chat on `TAB`. `add` appends a row for a server (default: the one you are on) and creates its cfg. At start it warns about names a server cfg sets that `default.cfg` does not reset.

```sh
python3 tools/serverconfig.py
python3 tools/serverconfig.py add <id> [address] [--match <text>]
python3 tools/serverconfig.py --check
```

## link_maps.py

Symlinks downloaded map pk3s from `etmain/dlcache/` into `etmain/`, so local hosting (`+map`) finds them (the engine mounts `dlcache/` only on remote servers). Skips pk3s that would override stock maps or shaders. Rerun after new downloads.

## stock_shield/

Builds the nitmod stock shield pk3 from your own `etmain/pak*.pk3`: it keeps the nitmod main menu and unpure servers on stock menus after servers pushed their own menu packs. `deploy.sh` offers it. Details: `stock_shield/README.md`.

## helpers/

Modules shared by the tools, imported as `helpers.<module>`:

- `settings.py`: reader for `settings.conf`; exits with a hint when a value is missing.
- `common.py`: follower of the game's console log, color code stripping, cfg-safe text, atomic file write.
- `serverapi.py`: the one module that talks to game servers and tells them apart, used by `servermenu.py`, `serverconfig.py` and `voicemenu.py`: server state (`getinfo`/`getstatus`), favorites, matching against `servers.tsv`, the server's tag, the history of seen servers. On the command line it prints the state of a server.
- `hudvalues.py`: run by `deploy.sh`. Reads the popup position, size and times of your legacy HUD (`default/huds/hud_v<n>.dat`, the HUD named by `cg_altHud`) and writes them into the `HUD VALUES` block of `user.cfg`, so the echo menus put the popups back where your HUD has them. Without a HUD file the values of the built-in HUD apply.

```sh
python3 tools/helpers/serverapi.py <address> ...
python3 tools/helpers/hudvalues.py
```
