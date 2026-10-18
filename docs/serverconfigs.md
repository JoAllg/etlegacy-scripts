# Server configs

Settings and a voice chat page per server or clan. A config script cannot tell which server the game is on ([Limitations](limitations.md)), so `tools/serverconfig.py` runs next to the game, finds it out and writes two cfg files the scripts exec. Pattern: [Config scripting](scripting.md), "Live data from an external tool".

- [Server configs](#server-configs)
  - [Detection](#detection)
  - [Files](#files)
    - [servers.tsv](#serverstsv)
  - [How the game applies the settings](#how-the-game-applies-the-settings)
    - [Sound restart](#sound-restart)
  - [Precedence](#precedence)
  - [Voice chat](#voice-chat)
    - [Server sounds on the stock pages](#server-sounds-on-the-stock-pages)
  - [Limits](#limits)


## Detection

The tool follows the console log `<fs_homepath>/<mod>/etconsole.log` (`logfile 2`, `default/cvars.cfg`).

| Log line | Meaning | Evidence |
|---|---|---|
| `<address> resolved to <ip:port>` (IPv6: `[<ip>]:<port>`) | the game connects to a server: server menu, server browser, `connect`, `reconnect` | `src/client/cl_main.c` `CL_Connect_f`, `src/qcommon/net_ip.c` `NET_AdrToString`; IPv6 not tested in game |
| `----- Server Initialization ----` | the game hosts a map itself (`+map`, `+devmap`), on every local map load | `src/server/sv_init.c` `SV_SpawnServer`; seen in a log of a local host on 2026-10-02 |
| a log that starts again (smaller, or another first line `logfile opened on <date>`) | new game session, on no server | the engine truncates the log at launch (`src/qcommon/common.c` `Com_Printf`) |

The log the tool finds at its start belongs to an earlier session unless a game runs, so its connects don't count then. A game runs while `profiles/<profile>/profile.pid` holds a live pid (`src/sys/sys_main.c` `Sys_WritePIDFile`, removed in `Sys_Exit`).

A connect names only the address, the server's name is not logged. The tool asks the server for it (`getstatus`, [Server queries](serverquery.md)) and looks its name and mod (`gamename`) up in `servers.tsv`. `history.tsv` keeps the name of every server asked so far, so a known server is recognized without waiting for its answer; the answer still follows and corrects the result. An unknown server counts as "no server of the list" until it answers. A server that doesn't answer (map change, restart, its rate limit dropping the packet) is asked again after 2, 4, 8, ... up to 60 s, with one packet per try, until it answers or the game connects elsewhere.

## Files

All in `default/serverconfigs/`; only `default.cfg` and `servers.example.tsv` are in version control.

| File | Written by | Content |
|---|---|---|
| `servers.tsv` | you, or `tools/serverconfig.py add`; the tool adds addresses | the servers that have settings or a voice chat: `<id><TAB><text><TAB><mod><TAB><addresses>` |
| `<id>.cfg` | you | settings on the servers of that id |
| `local.cfg` | you | settings while hosting a map yourself |
| `default.cfg` | you | normal value of everything a server cfg sets |
| `current.cfg` | tool | execs `default.cfg` and the `<id>.cfg` of the server the game is on |
| `current_vsay.cfg` | tool | puts that server's voice chat on `TAB` of the voice chat |
| `history.tsv` | tool | `<ip:port><TAB><server name><TAB><mod>` of the servers seen |
| `packs.tsv` | tool | `<ip:port><TAB><file><TAB><pk3><TAB><date>`: the pk3 the game loaded each voice chat file from on that server ([Voice chat pk3s](#voice-chat-pk3s)) |

### servers.tsv

```
xy_legacy	[xY]	legacy	192.0.2.1:27960
xy_nitmod	[xY]	nitmod	192.0.2.1:27970,192.0.2.2:27960
fun	Full Name Of A Server Without Tag		192.0.2.3:27960
```

- A row matches a server whose name contains the text and, if the row names a mod, whose mod (`gamename` of `getstatus`, as in `history.tsv`) is that mod. Color codes are ignored, upper and lower case are the same, the text is taken literally (no patterns). An empty mod matches every mod; a server whose mod is unknown only matches rows without one.
- The first matching row wins. One clan tag covers every server of the clan; a single server of that clan with settings of its own goes above it.
- The mod keeps a config away from servers of another mod: names that differ between the mods (alt-fire, weapon IDs, cvars only one mod has: `default/mods/<mod>/README.md`), the override texts with the nitmod/etps chat shortcuts and the variant numbers of the legacy mod ([Server sounds on the stock pages](#server-sounds-on-the-stock-pages)) only work on their mod. A clan with servers of two mods gets one id per mod, named `<clan>_<mod>` with the full mod name (`tm_nitmod`, `tm_legacy`), each with its own `<id>.cfg` and voice chat. What both share goes into a cfg without a row that both `execq`.
- The addresses (`ip:port`, comma-separated) record the servers the row matched; they play no part in the match. `tools/serverconfig.py` adds the address of a server it identifies to the first matching row.
- An id is a name of your choice for the server or clan. It is part of file names and of an alias name (`serverIs_<id>`), which is why the tag itself can't serve: a path with spaces needs quotes, and a bind that execs it is already quoted. 1 to 16 characters of `a-z`, `0-9`, `_`, not `default`, `local`, `current`, `current_vsay` (the other files of the folder). If the server's own page titles start with a short tag (`PS VOICE MUSIC`), use that as id: `tools/voicemenu.py` cuts the id from the titles.
- Several rows may carry the same id (a clan whose servers share no common text).
- The id links both parts and either may be missing: `serverconfigs/<id>.cfg` (settings) and `serverconfigs/vsays/<id>/` (voice chat pages of `tools/voicemenu.py <id> <pk3> [<pk3> ...]`).

`tools/serverconfig.py add <id> [address] [--match <text>] [--any-mod]` appends a row: it asks the server (default: the one the game connected to last) for its name and mod, proposes the tag at the start of the name as text, prints name and row and creates an empty `<id>.cfg`. The row names the server's mod; `--any-mod` leaves it empty, which a server that doesn't tell its mod needs. Adding a further server with the same text and mod only adds its address; an id that has a row with another text or mod gets the new one in its place, after a question; further rows of one id are added by hand.

## How the game applies the settings

`current.cfg` for the id `xy`:

```
set serverApply "execq profile/serverconfigs/default.cfg; execq profile/serverconfigs/xy.cfg; set serverLast vstr serverIs_xy"
set serverIs_xy "vstr null"
vstr serverLast
set serverIs_xy "vstr serverApply"
```

This is the change guard of [Config scripting](scripting.md): `serverLast` runs the alias of the id applied last, which does nothing while the file of that same id runs. So exec'ing the file is free of side effects until the id changes. A server without `<id>.cfg` has the id `default` and only execs `default.cfg`.

Every server change loads a map, also a change between two servers of one mod and a change to another mod (file system restart, then the map). The map autoexec execs `current.cfg` (`vstr serverCheck`, `default/definitions.cfg`); the first exec after the tool wrote applies the settings:

| Event | Where |
|---|---|
| map load | `mods/<mod>/autoexec_mod.cfg`, exec'd by every map and default autoexec; after a mod switch the chain it runs ends with `vstr serverForce` |
| class key | `classHook`, `scripts/class/cs_backend.cfg` |

The tool usually writes before the map load: it reads the log every 0.2 s and a server of `history.tsv` is known at once, while the connect still waits for the gamestate and the map. It is late only for a server that is not in `history.tsv` and whose first answer is lost (next try after 2 s); then the next class key applies the settings. jaymod runs no event autoexecs ([Autoexec behavior](autoexec.md)), so only the class keys apply there.

In-game test on 2026-10-18 (legacy, local host of de_dust): the map autoexec applied the settings at the first map load.

### Sound restart

The engine keeps every loaded sound by its file name until `snd_restart` (`src/client/snd_dma.c` `S_FindName`, `S_Base_BeginRegistration`), also across servers. Vsay packs of different servers use the same names (`sound/chat/allies/21c.wav`), so after a server change the voices of the last server's pack play, even on a pure server that doesn't load that pack. `vid_restart` keeps the cache; `snd_restart` empties it and runs `vid_restart` itself (`src/client/cl_main.c` `CL_Snd_Restart_f`).

**Workaround for an engine bug: remove it once ET: Legacy empties the sound cache itself** ([etlegacy PR #3639](https://github.com/etlegacy/etlegacy/pull/3639)). Then remove (keep the `which` part, [Voice chat pk3s](#voice-chat-pk3s)): the guard lines and `RESTART` in `tools/serverconfig.py` (`settings_cfg`, `write`, selftest), the `serverRestart*` lines in `default/state.cfg`, the `set serverRestartModSwitch ...;` part of `modIs_<mod>` in every `mods/<mod>/autoexec_mod.cfg`, this section and its mentions in `docs/limitations.md`, `tools/README.md`, `CLAUDE.md` and `.claude/rules/serverconfigs.md`.

`current.cfg` therefore ends with a second guard of the same kind, for the address instead of the id:

```
// Address: 192.0.2.1:27960 b
set serverRestartAdopt "set serverRestartLast vstr serverRestart_b; which ui/wm_quickmessageAlt.menu; which scripts/wm_allies_chat.voice; which scripts/wm_axis_chat.voice"
set serverRestart "vstr serverRestartAdopt; snd_restart"
set serverRestart_b "vstr null"
vstr serverRestartLast
set serverRestart_b "vstr serverRestart"
```

The file ends with `echo "^5Server: <id> <address>"`, so each exec shows in the console which server the settings belong to.

### Voice chat pk3s

A server's voice chat can be split over several pk3s (menu in one, voice scripts in another), and a server that updates its pack gets downloaded under the same name plus its checksum (`<name>.<checksum>.pk3`, `src/qcommon/files.c` `FS_ComparePaks`), so the mod folder holds many versions. Which ones a pure server uses is in its pak list, which `getstatus` doesn't send. `which <file>` prints the pk3 the game reads a file from, with the same pure check as every read (`FS_Which_f`, `FS_FOpenFileReadDir`; `ALLOW_RAW_FILE_ACCESS` is off on a client). `serverRestartAdopt` runs it for the quick chat menu and both voice scripts once per address (also for the first server after game start), and `tools/serverconfig.py` stores the answers in `packs.tsv`; `tools/voicemenu.py --find <id>` lists that pack first (`SERVER`). The three lines show in the console and the notify area once per server change.

When the sound restart guard goes (above), keep the `which` part: move it into `serverApply` (once per id) or a guard of its own.

The tool swaps the key (`a`, `b`) whenever the game joins another address (`ip:port`, `local`) and reads the last address and key back from the comment line; "no server" keeps both. Two keys instead of one alias per address keep the number of cvars fixed (`MAX_CVARS`). This works for every server, also without a row in `servers.tsv`. `F3` does not touch this guard. Not tested in game.

Start value, `state.cfg` (runs on game start, mod switch and `F1`):

```
set serverRestartLast "vstr serverRestartAdopt"
vstr serverRestartModSwitch
set serverRestartModSwitch "vstr null"
```

| Event | `serverRestartModSwitch` | Next `current.cfg` |
|---|---|---|
| game start | not defined yet: nothing | takes the key, no restart (no sounds loaded yet) |
| `F1` | `vstr null` | takes the key, no restart (the sounds are of this server) |
| mod switch | arms the restart | `snd_restart` |

A mod switch only restarts the file system (`src/qcommon/files.c` `FS_ConditionalRestart`), so the last mod's sounds stay. The mod switch guard of every `mods/<mod>/autoexec_mod.cfg` ([Autoexec behavior](autoexec.md)) sets the flag before it execs `autoexec.cfg`:

```
set modIs_nitmod "set serverRestartModSwitch set serverRestartLast vstr serverRestart; exec autoexec.cfg"
```

`modIs_<mod>` runs only on a mod switch (`modLast` holds the alias of the mod whose `autoexec.cfg` ran last, the current mod's own alias is `vstr null`), never on `F1` or game start, which exec `autoexec.cfg` directly. `state.cfg` then runs the flag, which arms the restart, and `vstr serverForce` at the end of `autoexec.cfg` restarts. A new mod folder copies this line from `mods/example/autoexec_mod.cfg`. jaymod runs no map autoexecs and has no `autoexec_mod.cfg`: a switch to jaymod does not restart, `F2` does it by hand.

`F3` and `autoexec.cfg` (game start, mod switch, `F1`) overwrite the server's values with the definitions, so both end with `vstr serverForce`, which applies `current.cfg` regardless of the guard.

In-game test on 2026-10-02 (legacy, local host of fueldump with a `local.cfg`): game start exec'd `current.cfg` and `default.cfg` after `state.cfg`; the map autoexec exec'd `current.cfg`, `default.cfg` and `local.cfg` in this order; the spectator autoexec exec'd `current.cfg` only. A remote server change and the other mods are not tested in game.

`serverCheck` and `serverApply` use `execq` (a class key can run them, [Config scripting](scripting.md)), so the console shows no `execing` line for these files; an apply shows as the load marker of `default.cfg` (`>>> SERVER DEFAULTS LOADED!`). Not tested in game with `execq`.

## Precedence

Later wins:

1. `definitions.cfg` (general files, then the mod's `mod_general.cfg`)
2. `user.cfg` (personal values)
3. `state.cfg` (start values of state; game start, mod switch and `F1` only)
4. `serverconfigs/default.cfg`
5. `serverconfigs/<id>.cfg`

A server cfg is a personal preference for that server, so it overrides these files. It does not override what the event that applies it sets afterwards: `serverCheck` runs at the start of the event, so the class script of a class key and the rest of a map autoexec run after the server cfg and win for the names they set. `F3` and `autoexec.cfg` apply it last (`serverForce`).

- Nothing undoes a server cfg except `default.cfg`, which runs before every server cfg: each name a server cfg sets (cvar, alias, bind) needs its normal value there, or it keeps the server's value on all other servers. The tool reports such names at its start (`tools/serverconfig.py --check`); it only compares names.
- Both files run again after every server change, `F3` and `F1`: absolute values only (`cg_fov 100`), no toggle or cycle steps.
- Never set state a key changes (toggle and cycle pointers of `state.cfg`): `F3` would throw the player's choice away. Pointers of cycles the server configs introduce themselves are the exception: they start again on every server change, `F3` and `F1` (`vsays/cycles.cfg` below; losing the step of a vsay cycle doesn't matter). Set what the steps mean instead, so the pointer stays untouched: the weapon switch cycle (`F5`) steps through first, second and off, and `vstr weaponSwitchOrderPistol` / `vstr weaponSwitchOrderSMG` (`scripts/movement.cfg`) choose the weapon of the first step, the start mode on that server.
- A fixed value in `default.cfg` overrides `user.cfg` and the definitions on every server. Where a value alias exists, restore with it and name the cvar in a comment for the check: `vstr fovNormal  // cg_fov`.

## Voice chat

`scripts/vsays/chat/categories.cfg` (first page of the voice chat) execs `current_vsay.cfg` each time it opens. On a server with voice chat pages the file echoes the `TAB` line with the server's tag and binds `TAB` to the top page `serverconfigs/vsays/<id>/<id>_menu.cfg`; on every other server it is empty and `TAB` does nothing. The file is read when the page opens, so it needs no guard.

The tag in the headings of the pages and in the `TAB` line is the text of `servers.tsv` as the server writes it in its name, with its colors.

### Server sounds on the stock pages

A server's own sounds can replace stock vsays on the stock pages, with the stock text. Each page opener of `scripts/vsays/chat.cfg` (and `chat_shortcuts.cfg`) ends with `vstr chatServer<Page>`, which `chat.cfg` and `default.cfg` set to `vstr null` (without the tool `default.cfg` doesn't run). A server cfg points it to a file that redefines some `vsay<key>` of that page:

```
set chatServerGlobal "execq profile/serverconfigs/vsays/xy/override/global.cfg"
```

- `vsays/<id>/override/<page>.cfg`: only the replaced `set vsay<key>` lines, in the page format. The subfolder survives a rerun of `tools/voicemenu.py`, which replaces the `*.cfg` of `vsays/<id>/` and rewrites `vsays/<id>/shortcuts/` (shortcut texts, kept per vsay).
- A key with several sounds is a cycle (pointers named `cycleServerVsay...`, apart from the stock pointers `cycleVsay<Name>` of `chat.cfg`): steps `vsay<key>a`, `b`, ... in the override file, pointer `cycleServerVsay<Page>Key<key>` in `vsays/cycles.cfg`, one per page and key, shared by all servers. The pointers can't live on the page (it restarts what it defines each time it opens); `default.cfg` execs the file, so the cycles start again on every server change, `F3` and `F1`, since a pointer may name a step the new server lacks. Not in version control (it lists the keys the servers use), `deploy.sh` creates it empty.
- The hook runs after the nitmod/etps shortcut files, so an override of a key with a shortcut text copies that text.
- Aliases outside the pages (class vsays of `scripts/vsays/vsays_custom.cfg` and `chat.cfg`, e.g. `vsayGrenade`) are set in the server cfg; `default.cfg` restores them with `reset <alias>` (the first value of the game session, from the stock file). The steps of their cycles are server sounds, so they go into `vsays/<id>/override/<stock file>.cfg`, which the server cfg execs; the pointer `cycleServerVsay<Name>` is shared in `vsays/cycles.cfg`.
- `tools/vsayoverrides.py` lists the servers with overrides and the sounds there that the server's `vsays.tsv` no longer has; the vsay-server-overrides skill builds and updates them.

## Limits

- Until the tool has written, the settings of the previous server stay; the next map load or class key corrects it.
- Leaving a server for the main menu and playing a demo keep the last server's settings.
- The sound restart (a short black screen) comes with the first event after the tool wrote, usually the map load. `F2` does it by hand.
- Without the tool (`tools/serverconfig.py`, started by `./launcher.sh`) no server's settings apply: when it ends (Ctrl+C, the `SIGTERM` of `./launcher.sh`) it writes both files for "no server". Only a tool that is killed hard (`SIGKILL`, power loss) leaves the files of its last server, until it starts again. Tested on 2026-10-02 without a game: start with an old log and `SIGTERM` both wrote the "no server" files.
- A failed write or query is reported and tried again with the pauses above; the tool keeps running.
