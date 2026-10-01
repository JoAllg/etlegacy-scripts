# Server queries

How to ask an ET server for its state from outside the game, as used by `tools/servermenu.py` for the server menu (`KP_MINUS`). Verified against the ET: Legacy source (`src/server/sv_main.c` `SVC_Info`, `SVC_Status`; client side `src/client/cl_main.c` `CL_SetServerInfo`) and a live test against the 392 servers of `master.etlegacy.com:27950` on 2026-10-01 (348 answered).

## Protocol

One UDP packet to the server's game port: four `0xff` bytes followed by the command. The answer is one packet with the same prefix, lines separated by `\n`.

| Request | Answer | Content |
|---|---|---|
| `getinfo <challenge>` | `infoResponse` + info string | `hostname`, `mapname`, `clients`, `humans`, `sv_maxclients` (private slots already subtracted), `sv_privateclients`, `game` (mod folder, missing on etmain), `needpass`, `protocol`, `version` |
| `getstatus` | `statusResponse` + info string + one line per player | all serverinfo cvars (`sv_hostname`, `mapname`, `gamename`, `sv_maxclients`, `sv_privateClients`, `P`, ...); player lines: `<score> <ping> "<name>"` |
| `getservers <protocol> [empty] [full]` to a master server | `getserversResponse` | `\` + 4 address bytes + 2 port bytes (big endian) per server; protocol is 84 |

An info string is `\key\value\key\value`. The ping of a server is the round trip time of the request.

## Humans and bots

| Source | Available on | Result |
|---|---|---|
| `humans` of `getinfo` | servers running the ET: Legacy engine, with any mod (204 of 256 servers compared) | exact: the engine counts the clients whose address is not a bot (`SVC_Info`) |
| players with ping 0 in `getstatus` | every server | bots have ping 0; differed from `humans` by at most 1 where both exist (a connecting client) |
| `omnibot_playing` of `getstatus` | 299 of 348 servers | not usable: nitmod servers reported `0` or `-1` while 19 to 24 bots were playing |

`tools/servermenu.py` uses `humans` when the key exists and the players minus the ping 0 players otherwise.

`P` of `getstatus` (legacy `src/game/g_main.c` `etpro_PlayerInfo`, 245 of 348 servers) holds one character per client slot: `1` axis, `2` allies, `3` spectator, `0` connecting, `-` free.

## Rate limit

ET: Legacy servers answer `getinfo` and `getstatus` from one address in a burst of 10 packets, then one packet per second (`SVC_RateLimitAddress(from, 10, 1000)`). Asking for both every second runs into the limit; every 5 seconds stays below it.

## Favorites of the server browser

With `db_mode` 1 or 2 (default 2, `src/db/db_sqlite3.c`) the favorites are rows of the table `client_servers` (`profile`, `address`, `name`) in `<fs_homepath>/etl.db`; mode 2 writes the file at once, so it can be read while the game runs. With `db_mode 0` they are in `profiles/<profile>/favcache.json` (`src/client/cl_ui.c` `LAN_LoadCachedServers`), an array of `{"address", "name", "game"}`.

## Other tools

`qstat` and [etstat](https://github.com/koen92/etstat) (a browser built on it) speak the same protocol.
