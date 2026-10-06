# Tools

Optional Python 3 helpers (stdlib only). They read the game paths and color preferences from `settings.conf` (via `helpers/settings.py`), so run `deploy.sh` first. All have a `--selftest` and reject unknown arguments.

## keymap/

Keyboard + mouse overview of the live binds. `keymap.py` emulates the exec chain, presses every bound key and writes `keymap.html` (one self-contained page, tabs per class bind set). New commands get their short names in `labels.json` (`--missing` lists unnamed ones). `live.py` serves the page and switches to the class picked in the running game by following the newest `<HOMEPATH>/<mod>/etconsole.log`. Details: [`keymap/README.md`](keymap/README.md).

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

Copies a server's quick chat menu (`V`) from its pk3 into voicechat pages in `default/scripts/vsays/servers/<clan>/`; in game they are on `TAB` of the voice chat while playing on that server (`serverconfig.py`). `<clan>` is the server's id in `default/serverconfigs/servers.tsv`, and the headings carry its tag as the server writes it (taken from `[address]` or from a server the game connected to before). Pages that duplicate the stock menu are left out; custom vsays the menu leaves out go on extra pages behind `TAB`. The pages have the format of the stock pages (`default/scripts/vsays/chat/`) and share their `vsay<key>` aliases. Menu items on letter keys are left out (the pages bind their keys); vsays only reachable through them go on the extra pages. A rerun after a new server pack keeps edited texts and the edited echoes of keys that send no text (random vsays, page names) and page headings, and reports added and removed vsays.

```sh
python3 tools/voicemenu.py <clan> <pk3> [address]
```

## vsaycolors.py

Colors all vsay texts and chat texts (`say`, `say_team`, `say_teamnl`, `say_buddy`; not `say !command`) with the `VSAY_*` colors and the echo menus with the `MENU_*` colors of `settings.conf`. `preview` writes `vsaycolors.html` (current vs proposed colors), `apply` recolors after a color change, `todo` / `done` track which texts were reviewed for highlights (`default/scripts/vsays/vsaycolors.tsv`).

```sh
python3 tools/vsaycolors.py status | preview [role=^c ...] | apply | todo | done
```

## servermenu.py

Feeds the in-game server menu (`RIGHTCTRL`, `default/scripts/servermenu.cfg`): while it runs, it asks the favorite servers of the server browser for their state every `SERVERMENU_POLL` seconds (`settings.conf`, default and minimum 5) and writes the menu pages to `default/servermenu/`. Each server shows as `name  playing+spectators+bots/slots  map  ping  mod` in columns aligned with spaces, sorted by playing humans; the number keys connect. The server the game is on (its last connect in the console log) is left out. Whatever a server doesn't send in a poll (no answer at all, no `getstatus`, no split of playing humans and spectators) shows its last value for `SERVERMENU_KEEP` seconds (default 60). Start it before or while playing and leave it running; `--once` prints the list in the terminal. How servers are queried: [`docs/serverquery.md`](../docs/serverquery.md).

```sh
python3 tools/servermenu.py [--interval <s>] [--once]
```

## serverconfig.py

Settings and voice chat per server ([`docs/serverconfigs.md`](../docs/serverconfigs.md)). While it runs, it follows the game's console log, asks a joined server for its name and looks it up in `default/serverconfigs/servers.tsv` (`<id><TAB><text in the server name>`, yours to maintain; format: `servers.example.tsv`). It then writes `current.cfg`, through which the game execs `default.cfg` and that server's `<id>.cfg`, and `current_vsay.cfg`, which puts the server's voice chat on `TAB`. On every change of the server address `current.cfg` also runs `snd_restart` once, because the engine keeps the last server's vsay sounds cached. `add` appends a row for a server (default: the one you are on) and creates its cfg. At start it warns about names a server cfg sets that `default.cfg` does not reset.

It also remembers the crosshair color per map: a color you choose with `HOME` is written into `default/autoexecs/autoexec_<map>.cfg` of the map you are on and set again on every later load of that map ([`docs/autoexec.md`](../docs/autoexec.md)). A map without autoexec gets one, which the game finds after the next `./launcher.sh` start.

```sh
python3 tools/serverconfig.py
python3 tools/serverconfig.py add <id> [address] [--match <text>]
python3 tools/serverconfig.py --check
```

## link_maps.py

Symlinks downloaded map pk3s from `etmain/dlcache/` into `etmain/`, so local hosting (`+map`) finds them (the engine mounts `dlcache/` only on remote servers). Skips pk3s that would override stock maps or shaders. Rerun after new downloads.

## stock_shield/

Builds the nitmod stock shield pk3 from your own `etmain/pak*.pk3`: it keeps the nitmod main menu, local games and unpure servers on stock menus and sounds after servers pushed their own menu and sound packs. `deploy.sh` offers it. Details: [`stock_shield/README.md`](stock_shield/README.md).

## helpers/

Modules shared by the tools, imported as `helpers.<module>`:

- `settings.py`: reader for `settings.conf`; exits with a hint when a value is missing.
- `common.py`: follower of the game's console log, color code stripping, cfg-safe text, atomic file write.
- `serverapi.py`: the one module that talks to game servers and tells them apart, used by `servermenu.py`, `serverconfig.py` and `voicemenu.py`: server state (`getinfo`/`getstatus`), favorites, matching against `servers.tsv`, the server's tag, the history of seen servers. On the command line it prints the state of a server.
- `menupages.py`: sorts the servers and builds the server menu pages (echo lines, number keys that connect, TAB) from server rows, used by `servermenu.py` and, with made-up servers, by `keymap/keymap.py`.
- `hudvalues.py`: run by `deploy.sh`. Reads the popup position, size and times of your legacy HUD (`default/huds/hud_v<n>.dat`, the HUD named by `cg_altHud`) and writes them into the `HUD VALUES` block of `user.cfg`, so the echo menus put the popups back where your HUD has them. Without a HUD file the values of the built-in HUD apply.

```sh
python3 tools/helpers/serverapi.py <address> ...
python3 tools/helpers/hudvalues.py
```
