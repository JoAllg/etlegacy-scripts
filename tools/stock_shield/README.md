# nitmod stock shield

The stock shield pk3 keeps the nitmod main menu, local games and unpure servers on stock ET content, even after servers push their own menu and sound packs into `~/.etlegacy/nitmod/`.

## Why

Servers auto-download pk3s with names like `~~~~~~~~~~{Clan}.pk3` or `~~~nitmod~~.pk3`. The engine loads every top-level pk3 of the mod folder and sorts them by name (`FS_PathCmp`, lowercase counts as uppercase); the name that sorts last wins when two pk3s contain the same file. `~` (126) is the highest printable character, so tilde prefixes win over normal pk3s.

Renaming `nitmod_2.3.5.pk3` doesn't help: nitmod's `ui/menus.txt` loads ~50 menus (`options.menu`, `profile.menu`, `quit.menu`, ...) that the nitmod pk3 doesn't contain. Normally they fall back to `etmain/pak0.pk3`; a server pack that ships these names overrides them.

## Content

1189 stock files (106 MB) extracted unchanged from `etmain/pak0.pk3`/`pak2.pk3` (highest-priority stock version of each), plus the hidden arenas:

- 70 `ui/` files: every menu from nitmod's `menus.txt` that nitmod lacks, plus menus/assets that server packs override
- 20 other files that server packs override: `gfx/2d/compass*.tga`, 2 `icons/`, `fonts/ariblk_16.dat`, `maps/{battery,fueldump,oasis,radar}.script`, 6 `scripts/*.arena`, `scripts/{battery,sprites}.shader`, `scripts/wm_{allies,axis}_chat.voice`
- 1099 `sound/` files, the whole stock folder: sound packs replace stock sounds under their stock names (vsay voices in `sound/chat/`, announcer in `sound/vo/`, weapons, footsteps, win music, menu clicks, `sound/scripts/*.sounds`)
- `scripts/*.arena` of server packs whose map can't be hosted locally (bsp in no pk3 of `etmain/`, `nitmod/` or the basepath; `etmain/dlcache/` is not mounted there): an empty file, or for arenas with several maps only the hostable ones. The host game list then shows only maps that start ([`docs/limitations.md`](../../docs/limitations.md)); the build prints each hidden or trimmed arena. Rebuild after new server downloads.

## Install

The files are game assets, so the pk3 is built from your own `etmain/pak*.pk3` (`BASEPATH` of `settings.conf`) and written to `<HOMEPATH>/nitmod/`. `deploy.sh` offers to run it while the pk3 is missing; manually (also to rebuild an installed one, e.g. after new server downloads):

```
python3 tools/stock_shield/stock_shield.py
```

The name needs more tildes than any server pk3 (60 here). Check in game: `/path` lists it at the top.

## Effect and limits

| Situation | Result |
|---|---|
| Pure server (`sv_pure 1`) | Shield ignored (not in the server's checksum list, `FS_PakIsPure`); server files load normally |
| Unpure server (`sv_pure 0`) | Shield wins for its 1189 files |
| Local hosting (`+map`) | Shield wins (`com_sv_running` disables the pure check) |
| Main menu | Shield wins |

- Also hides these 1189 files from wanted packs in the mod folder, e.g. `x_nitmod_skin.2.7.pk3` (quit menu, icons, map scripts) and voice and sound packs (`wm_*_chat.voice`, `wm_quickmessagealt.menu`, every stock name below `sound/`) outside pure servers.
- Hidden arenas also drop the map's long name, briefing and levelshot on unpure remote servers that run it (its bsp comes from `etmain/dlcache/` there).
- Files outside the 1189 (new menu names, sounds under new names, maps) are not shielded; a server pk3 with more than 60 tildes wins again.
- Uninstall: delete the pk3 from `~/.etlegacy/nitmod/`.
