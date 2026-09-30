# ET: Legacy player/console commands

Verified against the ET: Legacy source at `<ET: Legacy source checkout>` (engine: `src/qcommon/cmd.c`, `src/qcommon/cvar.c`, `src/client/cl_input.c`, `cl_keys.c`, `cl_console.c`, `cl_demo.c`, `cl_main.c`; legacy mod: `src/cgame/cg_consolecmds.c`, `src/game/g_cmds_ext.c`). Case shown is the source's registered casing; the engine matches command names case-insensitively, so casing in binds doesn't matter. `+cmd` commands take an implicit key/time arg from a bind and support release (`-cmd`) — see `docs/scripting.md`.

## Movement

| Command | Effect |
|---|---|
| `+forward` / `+back` | move forward / backward |
| `+moveleft` / `+moveright` | strafe left / right |
| `+left` / `+right` | turn view left / right |
| `+lookup` / `+lookdown` | look up / down; removed by the legacy cgame (`Unknown command`, see `docs/scripting.md`) |
| `+moveup` / `+movedown` | jump / crouch |
| `+speed` | speed modifier (walk/run toggle key) |
| `+strafe` | strafe modifier (turns +left/+right into strafe while held) |
| `+sprint` | sprint |
| `+prone` | go prone |
| `+leanleft` / `+leanright` | lean around corners |
| `+mlook` | mouse-look modifier |

## Combat & weapons

| Command | Effect |
|---|---|
| `+attack` | primary fire |
| `+attack2` | secondary-fire button bit — **no-op in legacy** (see [weapalt vs +attack2](#weapalt-vs-attack2) below) |
| `+reload` | reload |
| `+activate` | use/interact (doors, levers, objectives, health/ammo cabinets) |
| `+zoom` | scope/binocular zoom |
| `+weapzoom` / `toggleweapzoom` | iron-sight/weapon zoom (hold / toggle) |
| `zoomin` / `zoomout` | binocular zoom step |
| `weapon <bank>` | switch to weapon bank |
| `weaponbank <bank>` | switch to weapon bank (bank-cycle aware) |
| `weapalt` | alt-fire: scoped-weapon swap / reload-on-empty / quickchat fallback (legacy, see [weapalt vs +attack2](#weapalt-vs-attack2) below) |
| `weapnext` / `weapprev` | next/previous weapon |
| `weapnextinbank` / `weapprevinbank` | next/previous weapon within the current bank |
| `weaplastused` | switch to last-used weapon |
| `+useitem` | use held item |
| `+button1` | secondary action button (engine-level, mod-mapped) |
| `+salute` | salute animation |
| `kill` | suicide |
| `forcetapout` | immediate respawn when incapacitated (medic revive window) |
| `resetmaxspeed` | reset move-speed cap (e.g. after airstrike knockback) |

### weapalt vs +attack2

`weapalt` is the alt-fire command: switches to a weapon's scoped/unscoped alt variant if it has one; otherwise reloads (`cg_weapaltReloads 1`) or sends a class quickchat callout (`cg_quickchat` set). `cg_weapaltSwitches` and `cg_weapaltMgAutoProne` further tune this behavior.

`+attack2` is currently not implemented in legacy — binding a key to it has no effect.

nitmod: `+attack2` instead, see `docs/commands_nitmod.md`.

## Class, team & spawn

| Command | Effect |
|---|---|
| `class <s\|m\|e\|f\|c> [weapon1] [weapon2]` | pick class by letter code + loadout |
| `classmenu` | open class-selection UI |
| `teammenu` | open team-selection UI |
| `openlimbomenu` | open limbo (class/team/spawn) menu |
| `spawnmenu` | open the quick spawnpoint selector |
| `listspawnpt` | list current map's spawn points |
| `setspawnpt <id>` | pick a spawn point |
| `setclosestspawnpt` | pick the spawn point closest to current position |
| `wm_sayPlayerClass` | announce your class to team chat |
| `wm_ftsayPlayerClass` | announce your class to fireteam chat |

## HUD, view & UI

| Command | Effect |
|---|---|
| `+stats` / `-stats` | hold to show personal stats overlay |
| `+topshots` / `-topshots` | hold to show leaderboard overlay |
| `+objectives` / `-objectives` | hold to show objectives overlay |
| `+scores` / `-scores` | hold to show scoreboard |
| `readHuds` / `writeHuds` | reload / save HUD definitions |
| `edithud` | open the HUD editor |
| `editcomponent <name>` | select a HUD component to edit |
| `toggleConsole` | open/close console |
| `MapZoomIn` / `MapZoomOut` | zoom the command map |
| `+mapexpand` / `-mapexpand` | hold to expand the command map |
| `ToggleAutoMap` | toggle automap on/off |
| `camera` | camera command (cutscene/editor use) |
| `SetWeaponCrosshair <slot> <name>` | assign a crosshair per weapon slot |

## Communication

| Command | Effect |
|---|---|
| `say <text>` | chat: all, `^7<name>^7: ^2<text>` |
| `say_team <text>` | chat: team, with location, default text color `^5` |
| `say_teamnl <text>` | chat: team without location, `^5` |
| `say_buddy <text>` | chat: fireteam, with location, `^3` |
| `messageMode` / `messageMode2` / `messageMode3` | open chat input (all/team/fireteam) |
| `messageSend` | send the typed chat message |
| `cpm <text>` | print a centered screen message to yourself |
| `vsay [<n>] <id> [<text>]` | voice chat: all, shown as `^7<name>^3: ^2<text>` |
| `vsay_team [<n>] <id> [<text>]` | voice chat: team, `^7(<name>^7)^3(<location>^3): ^5<text>` |
| `vsay_buddy <class> <count> [<client> ...] [<n>] <id> [<text>]` | voice chat: fireteam, `^3<text>` |
| `VoiceChat <id>` / `VoiceTeamChat <id>` / `VoiceFireTeamChat <id>` | cgame shortcuts: exactly one argument (more: ignored), sent as `vsay <id>` / `vsay_team <id>` / `vsay_buddy -1 <selected fireteam members> <id>`; no text, no variant; team/fireteam refused as spectator |
| `mp_QuickMessage` | open quick-message menu |
| `mp_fireteammsg` | open fireteam quick-message menu |
| `mp_fireteamadmin` | open fireteam admin menu (invite/promote/kick) |
| `selectbuddy <num>` | select a fireteam buddy slot |
| `ignore <clientname>` / `unignore <clientname>` | mute / unmute a player's chat |
| `loc` | print current location name |
| `oinfo` | print objective info |

Chat and voice chat details (`src/game/g_cmds.c` `G_Say`, `G_Voice_f`, `G_Voice`; `src/cgame/cg_servercmds.c` `CG_VoiceChatLocal`):

- `say*`: the text is all arguments joined; at most 149 characters (`MAX_SAY_TEXT` 150), the rest is cut. The default text color is the one shown above, a color code in the text overrides it.
- `vsay*` `<id>`: a vsay of the voice scripts (`scripts/wm_allies_chat.voice`, `wm_axis_chat.voice`), case-insensitive; the first definition counts. Unknown ids play nothing.
- `<n>`: only if the argument starts with a digit: the n-th variant of the vsay (0-based) instead of a random one; out of range means random. legacy mod only.
- `<text>`: all remaining arguments; replaces the voice script's text in the vsay line (the sound still plays). Without text the voice script's text is shown.
- `vsay_buddy`: `<class>` `-1` = all, else only players of that class (`PC_*` number); `<count>` `0` = all fireteam members, else only the `<count>` client numbers that follow. Only players in the sender's fireteam receive it.
- `say_buddy` / `vsay_buddy` are refused for spectators (server side).
- No private message commands in the mod itself. Servers often add them with a Lua script (`et_ClientCommand` hook, `src/game/g_lua.c`), usually as `m` / `pm <name|slot#> <message>` or `/m` in `say`; whether they exist and their syntax depend on the server (check `/m` without arguments or the server's `!help`).
- Spam limit: every vsay adds `30000 / g_voiceChatsAllowed` ms, vsays are refused above 30000 (decreases in real time).

## Match / spectator

| Command | Effect |
|---|---|
| `follow <player_ID\|allies\|axis>` | spectate a player or team |
| `pause` / `unpause` | request/lift a team pause |
| `timeout` / `timein` | same (ETPro-style aliases of `pause`/`unpause`) |
| `ready` / `unready` | set your ready status |
| `readyteam` | set your whole team ready (captain) |
| `lock` / `unlock` | lock/unlock your team (captain) |
| `speclock` / `specunlock` | lock/unlock your team from spectators |
| `spechelp` | print spectator command help |
| `freecam` | toggle free-flying spectator camera |
| `+freecam_turnleft` / `+freecam_turnright` / `+freecam_turnup` / `+freecam_turndown` / `+freecam_rollleft` / `+freecam_rollright` | freecam rotation (hold) |
| `freecamsetpos` / `freecamgetpos` | save / recall a freecam position |
| `mvactivate` | toggle all multiview windows |
| `mvnew` / `mvdel` | add / remove a multiview window |
| `mvshow` / `mvhide` / `mvswap` / `mvtoggle` | show / hide / swap / toggle a multiview window |
| `statsdump` | export match statistics to a file |
| `scPlusRedScore` / `scMinusRedScore` / `scResetRedScore` | shoutcaster: adjust/reset red score overlay |
| `scPlusBlueScore` / `scMinusBlueScore` / `scResetBlueScore` | shoutcaster: adjust/reset blue score overlay |
| `scSwapTeamLabels` | shoutcaster: swap red/blue team labels |

## Timer

| Command | Effect |
|---|---|
| `timerSet <seconds>` | start a personal countdown |
| `timerReset` (alias `resetTimer`) | clear the countdown |
| `sharetimer` / `sharetimer_buddy` | share your countdown with team / fireteam |

## Demo & capture

| Command | Effect |
|---|---|
| `record <name>` | start demo recording |
| `stoprecord` | stop demo recording |
| `autoRecord` | toggle automatic demo recording |
| `toggleRecord` | toggle demo recording |
| `screenshot` | capture screenshot (TGA/JPG per `r_screenshotFormat`) |
| `screenshotJPEG` | capture a JPEG screenshot |
| `autoScreenshot` | toggle automatic end-of-match screenshot |
| `video-pipe` | pipe video+audio to ffmpeg for recording |
| `currentTime` | print system time to console |

## Cheat/debug (sv_cheats or local hosting only)

| Command | Effect |
|---|---|
| `noclip` | walk through walls |
| `god` | invulnerability |
| `notarget` | invisible to bots |
| `give <all\|skill\|medal\|health\|weapons\|ammo\|allammo\|keys>` | grant items |
| `testgun` | weapon view-model test |
| `testmodel <model>` | spawn a test model |
| `nextframe` / `prevframe` | step test-model animation frame |
| `nextskin` / `prevskin` | cycle test-model skin |
| `viewpos` | print current view position/angles |
| `generateTracemap` | generate map tracemap data |
| `editSpeakers` / `modifySpeaker` / `undoSpeaker` / `dumpSpeaker` | ambient-sound entity editor |
| `fade` | trigger a screen fade |

## Config & scripting

Documented in `docs/scripting.md`: `set`, `seta`, `sets`, `setu`, `reset`, `unset`, `vstr`, `bind`, `unbind`, `unbindall`, `bindlist`, `toggle`, `cycle`, `+vstr`, `wait`, `exec`, `echo`. Additional ones from the forum list, verified:

| Command | Effect |
|---|---|
| `writeconfig <file>` | write current cvars to a cfg file |
| `condump <file>` | dump console text to a file |
| `clear` | clear the console display |
| `cvarlist [filter]` | list cvars |
| `cmdlist [filter]` | list commands |
