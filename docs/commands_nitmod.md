# nitmod command differences (vs legacy)

Valid for nitmod 2.3.5. nitmod is closed-source, so this is based on its live `/cmdlist` and `/cvarlist` output, the mod's own config/README (`default/mods/nitmod/`) and, where noted, its decompiled binaries — not source like `docs/commands.md`. Baseline for comparison is `docs/commands.md`.

## Alt-fire: weapalt vs +attack2

`weapalt` does not work in nitmod. MOUSE2 is bound to `+attack2` by default there, and `+attack2` is what triggers the alt-fire behavior (scoped-weapon swap / reload-on-empty / quickchat), controlled by the same `cg_weapaltReloads`, `cg_weapaltSwitches` and `cg_weapaltMgAutoProne` cvars as legacy.

## Known interaction differences

- **Spectator command:** `team s`, not `team spectator`.
- **Minimum FOV:** `cg_fov 90` (legacy allows down to 75).
- **Class commands:** different weapon IDs than legacy — see `default/mods/nitmod/mod_classcommands.cfg`.
- **Chat shortcuts:** adds vsay shortcuts via `scripts/vsays/chat_shortcuts.cfg` (legacy doesn't exec this file).
- **`class`** takes no letter-code argument the way legacy's `class <s|m|e|f|c>` does — nitmod's own class scripts drive class choice through the `b_*`/`r_*` aliases instead (see `classKeysAllies`, `teamAllies`/`teamAxis` in `scripts/class/cs_backend.cfg`). `setclass` also exists as a separate command; neither's exact syntax is confirmed (no source, no usage string captured).

## Chat and voice chat syntax

From nitmod's decompiled `qagame`/`cgame` (functions `ClientCommand`, `Cmd_Say_f`, `G_Say`, `G_Voice`, `G_VoiceTo`, `G_PrivateMessage`, `CG_VoiceChat_f` ...).

| Command | Effect |
|---|---|
| `say <text>` | chat: all, `<name>^7: ` + default color `^2` |
| `say_team <text>` | chat: team, `(<name>^7) (<location>): ` + `^5` |
| `say_teamnl <text>` | chat: team without location, `(<name>^7): ` + `^5` |
| `say_buddy <text>` | chat: fireteam, `(<name>^7) (<location>): ` + `^3` |
| `m <name\|slot#> <message>` / `pm ...` | private message (server needs `g_privateMessages`); also as `say /m ...`, `say /pm ...` (and with `say_team` / `say_buddy`) |
| `ma <message>` / `say /ma <message>` | admin chat |
| `vsay <id> [<text>]` | voice chat: all |
| `vsay_team <id> [<text>]` | voice chat: team |
| `vsay_buddy <class> <count> [<client> ...] <id> [<text>]` | voice chat: fireteam; `<class>` `-1` = all classes, `<count>` `0` = whole fireteam, else only the listed client numbers |
| `VoiceChat <id>` / `VoiceTeamChat <id>` / `VoiceFireTeamChat <id>` | exactly one argument (more: ignored), sent as `vsay <id>` / `vsay_team <id>` / `vsay_buddy -1 <selected fireteam members> <id>`; no text, no spectator check |

Differences from legacy:

- **No variant number:** `vsay <n> <id>` takes `<n>` as the id (unknown vsay, nothing plays). The server only sends `vchat <voiceonly> <client> <color> <id> <random>` (team/fireteam: plus the origin), so every client picks the variant at random.
- **The text is a normal chat line:** a `<text>` of 2+ characters is sent like `say` / `say_team` / `say_buddy` (same prefix, default color, 149 character limit, censor and `g_shortcuts` expansion such as `[S]`), and the vsay only plays its sound and icon (`voiceonly`). A 1-character text is ignored.
- `<id>`: at most 31 characters.
- Spam limit: every vsay adds `34000 / g_voiceChatsAllowed` ms, refused above 30000 (admins exempt).

## Commands legacy has that nitmod doesn't

Absent from nitmod's `/cmdlist` entirely — no equivalent found:

| Command(s) | Legacy feature |
|---|---|
| `+lookup` / `+lookdown` | digital look up/down (nitmod has no keyboard look-pitch commands, mouselook only) |
| `freecam`, `+freecam_turnleft/right/up/down`, `+freecam_rollleft/right`, `freecamsetpos`, `freecamgetpos` | free-flying spectator camera |
| `mvactivate`, `mvnew`, `mvdel`, `mvshow`, `mvhide`, `mvswap`, `mvtoggle` | multiview (several POV windows at once) |
| `edithud`, `editcomponent`, `readHuds`, `writeHuds` | HUD editor |
| `camera` | cutscene/editor camera |
| `scPlusRedScore`, `scMinusRedScore`, `scResetRedScore`, `scPlusBlueScore`, `scMinusBlueScore`, `scResetBlueScore`, `scSwapTeamLabels` | shoutcaster score overlay controls |
| `spawnmenu`, `teammenu`, `listspawnpt`, `setclosestspawnpt` | quick spawn-point/team selector UI |
| `+objectives` / `-objectives` | objectives overlay (hold) |
| `+weapzoom` / `-weapzoom`, `toggleweapzoom` | iron-sight weapon zoom |
| `sharetimer`, `sharetimer_buddy` | share personal countdown timer |
| `timerReset` | present only as `resetTimer` in nitmod |
| `timeout` / `timein` | present only as `pause` / `unpause` in nitmod |
| `toggleRecord` | present only as `autoRecord` in nitmod |
| `loc`, `oinfo`, `spechelp`, `fade` | location print, objective info, spectator help, screen fade |

## Commands nitmod has that legacy doesn't

Player-facing additions found in nitmod's `/cmdlist` with no legacy counterpart:

| Command(s) | Purpose |
|---|---|
| `m`, `pm`, `ma` | private message, admin chat (syntax above) |
| `fireteam`, `specinvite`, `swap_teams` | fireteam management; invite a spectator; swap team sides |
| `dropobj`, `playdead`, `nofatigue` | drop carried objective; feign death; disable stamina fatigue |
| `ready`/`unready` also as `imready`/`notready` | alternate spellings of ready-toggle |
| `start_match`, `reset_match` | match control (competitive play) |
| `vote`, `callvote` | server-side voting |
| `team`, `setclass` | direct team/class selection commands (see above — syntax unconfirmed) |
| `scores`, `topshots`, `bottomshots`, `showstats`, `statsall`, `weaponstats`, `globalstats`, `tdminfo`, `damage` | assorted stats/leaderboard printouts |
| `auth`, `sclogin`/`sclogout`, `sslogin`/`sslogout` | stats-tracking account login |
| `irc_connect`, `irc_disconnect`, `irc_say` | built-in IRC bridge |
| `tv` | spectator/shoutcast TV feature |
| `follownext`, `followprev` | cycle spectate target |
| `pausedemo`, `rewind`, `seek`, `seekend`, `seeknext`, `seekprev`, `seekservertime`, `demo_play`, `demo_stop`, `demo_ff`, `demo_autoplay`, `demo_record`, `benchmark` | extended demo playback/recording controls (legacy only has `record`/`stoprecord`) |
| `setviewpos` | set view position (legacy only has `viewpos`, which prints it) |
| `setRecommended` | auto-apply recommended cvar values |
| `players` | print connected-player list |
