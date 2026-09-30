# nitmod stock shield

The stock shield pk3 keeps the nitmod main menu, local games and unpure servers on stock ET content, even after servers push their own menu packs into `~/.etlegacy/nitmod/`.

## Why

Servers auto-download pk3s with names like `~~~~~~~~~~{Clan}.pk3` or `~~~nitmod~~.pk3`. The engine loads every top-level pk3 of the mod folder and sorts them by name (`FS_PathCmp`, lowercase counts as uppercase); the name that sorts last wins when two pk3s contain the same file. `~` (126) is the highest printable character, so tilde prefixes win over normal pk3s.

Renaming `nitmod_2.3.5.pk3` doesn't help: nitmod's `ui/menus.txt` loads ~50 menus (`options.menu`, `profile.menu`, `quit.menu`, ...) that the nitmod pk3 doesn't contain. Normally they fall back to `etmain/pak0.pk3`; a server pack that ships these names overrides them.

## Content

90 files, extracted unchanged from stock `etmain/pak0.pk3`/`pak2.pk3` (highest-priority stock version of each):

- 70 `ui/` files: every menu from nitmod's `menus.txt` that nitmod lacks, plus menus/assets that server packs override
- 20 other files that server packs override: `gfx/2d/compass*.tga`, 2 `icons/`, `fonts/ariblk_16.dat`, `maps/{battery,fueldump,oasis,radar}.script`, 6 `scripts/*.arena`, `scripts/{battery,sprites}.shader`, `scripts/wm_{allies,axis}_chat.voice`

## Install

The files are game assets, so the pk3 is built from your own `etmain/pak*.pk3` (`BASEPATH` of
`settings.conf`) and written to `<HOMEPATH>/nitmod/`. `deploy.sh` offers to run it; manually:

```
python3 tools/stock_shield/stock_shield.py
```

The name needs more tildes than any server pk3 (60 here). Check in game: `/path` lists it at the top.

## Effect and limits

| Situation | Result |
|---|---|
| Pure server (`sv_pure 1`) | Shield ignored (not in the server's checksum list, `FS_PakIsPure`); server files load normally |
| Unpure server (`sv_pure 0`) | Shield wins for its 90 files |
| Local hosting (`+map`) | Shield wins (`com_sv_running` disables the pure check) |
| Main menu | Shield wins |

- Also hides these 90 files from wanted packs in the mod folder, e.g. `x_nitmod_skin.2.7.pk3` (quit menu, icons, map scripts) and voice packs (`wm_*_chat.voice`, `wm_quickmessagealt.menu`) outside pure servers.
- Files outside the 90 (new menu names, sounds, maps) are not shielded; a server pk3 with more than 60 tildes wins again.
- Uninstall: delete the pk3 from `~/.etlegacy/nitmod/`.
