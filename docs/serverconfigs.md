# Server configs

Settings and a voice chat page per server or clan. A config script cannot tell which server the game is on ([Limitations](limitations.md)), so `tools/serverconfig.py` runs next to the game, finds it out and writes two cfg files the scripts exec. Pattern: [Config scripting](scripting.md), "Live data from an external tool".

## Detection

The tool follows the console log `<fs_homepath>/<mod>/etconsole.log` (`logfile 2`, `default/cvars.cfg`).

| Log line | Meaning | Evidence |
|---|---|---|
| `<address> resolved to <ip:port>` (IPv6: `[<ip>]:<port>`) | the game connects to a server: server menu, server browser, `connect`, `reconnect` | `src/client/cl_main.c` `CL_Connect_f`, `src/qcommon/net_ip.c` `NET_AdrToString`; IPv6 not tested in game |
| `----- Server Initialization ----` | the game hosts a map itself (`+map`, `+devmap`), on every local map load | `src/server/sv_init.c` `SV_SpawnServer`; seen in a log of a local host on 2026-10-02 |
| a log that starts again (smaller, or another first line `logfile opened on <date>`) | new game session, on no server | the engine truncates the log at launch (`src/qcommon/common.c` `Com_Printf`) |

The log the tool finds at its start belongs to an earlier session unless a game runs, so its connects don't count then. A game runs while `profiles/<profile>/profile.pid` holds a live pid (`src/sys/sys_main.c` `Sys_WritePIDFile`, removed in `Sys_Exit`).

A connect names only the address, the server's name is not logged. The tool asks the server for it (`getstatus`, [Server queries](serverquery.md)) and looks the name up in `servers.tsv`. `history.tsv` keeps the name of every server asked so far, so a known server is recognized without waiting for its answer; the answer still follows and corrects the result. An unknown server counts as "no server of the list" until it answers. A server that doesn't answer (map change, restart, its rate limit dropping the packet) is asked again after 2, 4, 8, ... up to 60 s, with one packet per try, until it answers or the game connects elsewhere.

## Files

All in `default/serverconfigs/`; only `default.cfg` and `servers.example.tsv` are in version control.

| File | Written by | Content |
|---|---|---|
| `servers.tsv` | you, or `tools/serverconfig.py add` | the servers that have settings or a voice chat: `<id><TAB><text>` |
| `<id>.cfg` | you | settings on the servers of that id |
| `local.cfg` | you | settings while hosting a map yourself |
| `default.cfg` | you | normal value of everything a server cfg sets |
| `current.cfg` | tool | execs `default.cfg` and the `<id>.cfg` of the server the game is on |
| `current_vsay.cfg` | tool | puts that server's voice chat on `TAB` of the voice chat |
| `history.tsv` | tool | `<ip:port><TAB><server name>` of the servers seen |

### servers.tsv

```
xy	[xY]
fun	Full Name Of A Server Without Tag
```

- A row matches a server whose name contains the text. Color codes are ignored, upper and lower case are the same, the text is taken literally (no patterns).
- The first matching row wins. One clan tag covers every server of the clan; a single server of that clan with settings of its own goes above it.
- An id is a name of your choice for the server or clan. It is part of file names and of an alias name (`serverIs_<id>`), which is why the tag itself can't serve: a path with spaces needs quotes, and a bind that execs it is already quoted. 1 to 4 characters of `a-z`, `0-9`, `_`. If the server's own page titles start with a short tag (`PS VOICE MUSIC`), use that as id: `tools/voicemenu.py` cuts the id from the titles.
- Several rows may carry the same id (a clan whose servers share no common text).
- The id links both parts and either may be missing: `serverconfigs/<id>.cfg` (settings) and `scripts/vsays/servers/<id>/` (voice chat pages of `tools/voicemenu.py <id> <pk3>`).

`tools/serverconfig.py add <id> [address] [--match <text>]` appends a row: it asks the server (default: the one the game connected to last) for its name, proposes the tag at the start of the name as text, prints name and row and creates an empty `<id>.cfg`. An id that already has a row gets the new text in its place, after a question; further rows of one id are added by hand.

## How the game applies the settings

`current.cfg` for the id `xy`:

```
set serverApply "execq profile/serverconfigs/default.cfg; execq profile/serverconfigs/xy.cfg; set serverLast vstr serverIs_xy"
set serverIs_xy "vstr null"
vstr serverLast
set serverIs_xy "vstr serverApply"
```

This is the change guard of [Config scripting](scripting.md): `serverLast` runs the alias of the id applied last, which does nothing while the file of that same id runs. So exec'ing the file is free of side effects until the id changes. A server without `<id>.cfg` has the id `default` and only execs `default.cfg`.

The tool can be slower than the game: the map autoexec may run before `current.cfg` is rewritten. The scripts therefore exec it on every event that can follow a server change (`vstr serverCheck`, `default/definitions.cfg`), and the first one after the tool wrote applies the settings:

| Event | Where |
|---|---|
| map load | `mods/<mod>/autoexec_mod.cfg`, exec'd by every map and default autoexec |
| join, team change | `autoexecs/autoexec_spectator.cfg`, `autoexec_axis.cfg`, `autoexec_allies.cfg` |
| class key | `classHook`, `scripts/class/cs_backend.cfg` |
| voice chat | `voiceChatSelector`, `scripts/voicechat.cfg` |

jaymod runs no event autoexecs ([Autoexec behavior](autoexec.md)), so only the class keys and the voice chat apply there.

### Sound restart

The engine keeps every loaded sound by its file name until `snd_restart` (`src/client/snd_dma.c` `S_FindName`, `S_Base_BeginRegistration`), also across servers. Vsay packs of different servers use the same names (`sound/chat/allies/21c.wav`), so after a server change the voices of the last server's pack play, even on a pure server that doesn't load that pack. `vid_restart` keeps the cache; `snd_restart` empties it and runs `vid_restart` itself (`src/client/cl_main.c` `CL_Snd_Restart_f`).

**Workaround for an engine bug: remove it once ET: Legacy empties the sound cache itself** ([etlegacy PR #3639](https://github.com/etlegacy/etlegacy/pull/3639)). Then remove: the guard lines and `RESTART` in `tools/serverconfig.py` (`settings_cfg`, `write`, selftest), the `serverRestart*` lines in `default/state.cfg`, the `set serverRestartModSwitch ...;` part of `modIs_<mod>` in every `mods/<mod>/autoexec_mod.cfg`, this section and its mentions in `docs/limitations.md`, `tools/README.md`, `CLAUDE.md` and `.claude/rules/serverconfigs.md`.

`current.cfg` therefore ends with a second guard of the same kind, for the address instead of the id:

```
// Address: 192.0.2.1:27960 b
set serverRestartAdopt "set serverRestartLast vstr serverRestart_b"
set serverRestart "vstr serverRestartAdopt; snd_restart"
set serverRestart_b "vstr null"
vstr serverRestartLast
set serverRestart_b "vstr serverRestart"
```

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

`serverCheck` and `serverApply` use `execq` (a class key or the voice chat can run them, [Config scripting](scripting.md)), so the console shows no `execing` line for these files; an apply shows as the load marker of `default.cfg` (`>>> SERVER DEFAULTS LOADED!`). Not tested in game with `execq`.

## Precedence

Later wins:

1. `definitions.cfg` (general files, then the mod's `mod_general.cfg`)
2. `user.cfg` (personal values)
3. `state.cfg` (start values of state; game start, mod switch and `F1` only)
4. `serverconfigs/default.cfg`
5. `serverconfigs/<id>.cfg`

A server cfg is a personal preference for that server, so it overrides these files. It does not override what the event that applies it sets afterwards: `serverCheck` runs at the start of the event, so the class script of a class key, the rest of a map or team autoexec and the binds of the voice chat page run after the server cfg and win for the names they set. `F3` and `autoexec.cfg` apply it last (`serverForce`).

- Nothing undoes a server cfg except `default.cfg`, which runs before every server cfg: each name a server cfg sets (cvar, alias, bind) needs its normal value there, or it keeps the server's value on all other servers. The tool reports such names at its start (`tools/serverconfig.py --check`); it only compares names.
- Both files run again after every server change, `F3` and `F1`: absolute values only (`cg_fov 100`), no toggle or cycle steps.
- Never set state a key changes (toggle and cycle pointers of `state.cfg`): `F3` would throw the player's choice away. Set what the steps mean instead, so the pointer stays untouched: the weapon switch cycle (`F5`) steps through first, second and off, and `vstr weaponSwitchOrderPistol` / `vstr weaponSwitchOrderSMG` (`scripts/movement.cfg`) choose the weapon of the first step, the start mode on that server.
- A fixed value in `default.cfg` overrides `user.cfg` and the definitions on every server. Where a value alias exists, restore with it and name the cvar in a comment for the check: `vstr fovNormal  // cg_fov`.

## Voice chat

`scripts/vsays/chat/categories.cfg` (first page of the voice chat) execs `current_vsay.cfg` each time it opens. On a server with voice chat pages the file echoes the `TAB` line with the server's tag and binds `TAB` to the top page `scripts/vsays/servers/<id>/<id>.cfg`; on every other server it is empty and `TAB` does nothing. The file is read when the page opens, so it needs no guard.

The tag in the headings of the pages and in the `TAB` line is the text of `servers.tsv` as the server writes it in its name, with its colors.

## Limits

- Until the tool has written, the settings of the previous server stay; the next event of the table corrects it.
- Leaving a server for the main menu and playing a demo keep the last server's settings.
- The sound restart (a short black screen) comes with the first event after the tool wrote, e.g. the map load or the team join. `F2` does it by hand.
- Without the tool (`tools/serverconfig.py`, started by `./launcher.sh`) no server's settings apply: when it ends (Ctrl+C, the `SIGTERM` of `./launcher.sh`) it writes both files for "no server". Only a tool that is killed hard (`SIGKILL`, power loss) leaves the files of its last server, until it starts again. Tested on 2026-10-02 without a game: start with an old log and `SIGTERM` both wrote the "no server" files.
- A failed write or query is reported and tried again with the pauses above; the tool keeps running.
