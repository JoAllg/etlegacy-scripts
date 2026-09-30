# Tools

Optional Python 3 helpers (stdlib only). They read the game paths and color preferences from `settings.conf` (via `settings.py`), so run `deploy.sh` first. Most have a `--selftest`.

## keymap/

Keyboard + mouse overview of the live binds. `keymap.py` emulates the exec chain, presses every bound key and writes `keymap.html` (one self-contained page, tabs per class bind set). New commands get their short names in `labels.json` (`--missing` lists unnamed ones). `live.py` (`keymap-live.sh`) serves the page and switches to the class picked in the running game by following the newest `<HOMEPATH>/<mod>/etconsole.log`. Details: `keymap/README.md`.

```sh
python3 tools/keymap/keymap.py [--mod <mod>] [--missing]
./keymap-live.sh
```

## spawnpoints/

`spawnpoints.py` generates map autoexecs with a spawnpoint menu from the map pk3s into `spawnpoints/autoexecs/`: every `setspawnpt N` whose closest spawn spot lies in another room becomes a menu entry, labeled with the objective and the location name. `diff.py` compares the generated files with the live ones in `default/autoexecs/`.

```sh
python3 tools/spawnpoints/spawnpoints.py [map ...]
python3 tools/spawnpoints/diff.py [--spawns] [map ...]
```

## voicemenu.py

Copies a server's quick chat menu (`V`) from its pk3 into voicechat pages in `default/scripts/vsays/servers/<clan>/`. Pages that duplicate the stock menu are left out; custom vsays the menu leaves out go on extra pages behind `TAB`. A rerun after a new server pack keeps edited texts and reports added and removed vsays.

```sh
python3 tools/voicemenu.py <clan> <pk3> [tag]
```

## vsaycolors.py

Colors all vsay texts with the `VSAY_*` colors and the echo menus with the `MENU_*` colors of `settings.conf`. `preview` writes `vsaycolors.html` (current vs proposed colors), `apply` recolors after a color change, `todo` / `done` track which texts were reviewed for highlights (`default/scripts/vsays/vsaycolors.tsv`).

```sh
python3 tools/vsaycolors.py status | preview [role=^c ...] | apply | todo | done
```

## link_maps.py

Symlinks downloaded map pk3s from `etmain/dlcache/` into `etmain/`, so local hosting (`+map`) finds them (the engine mounts `dlcache/` only on remote servers). Skips pk3s that would override stock maps or shaders. Rerun after new downloads.

## stock_shield/

Builds the nitmod stock shield pk3 from your own `etmain/pak*.pk3`: it keeps the nitmod main menu and unpure servers on stock menus after servers pushed their own menu packs. `deploy.sh` offers it. Details: `stock_shield/README.md`.

## settings.py

Shared reader for `settings.conf`; exits with a hint when a value is missing.
