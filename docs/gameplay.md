# Game knowledge

How ET works in game: console, commands, settings, tips. Scripting syntax and patterns: `docs/scripting.md`.

## Good to read
- https://te666.forumotion.com/t522-interpreting-the-lagometer-rate-fps-snaps-etc#4979

## Tips
- Servers can enforce their own values: press `F3` (re-execs the definitions and `user.cfg`) to get yours back for the next server.

## FAQ
### Sniper
- If you try to pull down the mouse (do it a fraction of second before actually firing) then the recoil is reduced a lot. 
- Otherwise zoom out as soon as you fired your first shot so that you can shoot another one quickly after the first one.

### Console
Open it by pressing the tilde (`~`) key or the `^` key.

#### Console view shortcuts:
- `~` - normal console view
- `Ctrl + ~` - small console
- `Alt + ~` - fullscreen console

#### Browsing the console:
- `Page Up` / `Mouse Wheel Up` - scroll console up
- `Page Down` / `Mouse Wheel Down` - scroll console down
- `Ctrl + Home` - jump to start of console
- `Ctrl + End` - jump to end of console

#### Finding cvar values:
Type `/com_hunk` then press `Tab` to show options for similar cvars. Press `Tab` again until the desired cvar is selected, then `Enter` to show its current and default values.

#### Useful console commands:
- `/cvarlist` - lists all the cvars you have in use
- `/cmdlist` - lists all the commands that can be used via console
- `/bindlist` - lists all the binds you have in use
- `/clear` - clears whole console
- `/condump <name>.log` - manual dump into permanent file

## Commands
### +prone
>I guess you can rather think of it in this way: +prone will always toggle the current prone state, but since it is a +command, you need to release it as well, otherwise you just keep toggling, this is a bit more logical perhaps cause you do not press -prone to stand up, you press +prone
Same for +activate
However it is difficult to include +activate in the same execution as +prone?

## Settings
Checked against the ET: Legacy source (2026-09) and the decompiled nitmod 2.3.5 `qagame`. Old guides (e.g. [fearless-assassins](https://fearless-assassins.com/forums/topic/92394-somethings-not-right/)) describe vanilla 2.60b and are partly outdated.

**Engine vs. mod:** `com_maxfps`, `cl_maxpackets`, `snaps` and mouse input are handled by the ET: Legacy engine and behave the same in every mod. Spread and recoil are computed by the mod on the server (pmove), so they depend on the mod the server runs.

### FPS (`com_maxfps`)
- Range 20–500, default 125. The frame limiter works in microseconds, so any value gives exact FPS; the old "round_down(1000/N)" list is only needed for accurate FPS in vanilla.
- Commands still carry whole milliseconds: 125 (8 ms), 250 (4 ms) and 500 (2 ms) give even frame times; e.g. 144 fps alternates 6/7 ms.
- Physics: servers with `g_fixedphysics 1` + `g_fixedphysicsfps 125` (legacy default) only fix the gravity rounding (jump height). They do **not** make recoil or spread FPS independent.

### maxpackets (`cl_maxpackets`)
- Range 15–125, default 125 (the old limit of 100 no longer applies). Servers can still force lower values.
- A packet goes out in the first frame after `1000/cl_maxpackets` ms (whole ms), so FPS should be a multiple of the packet rate: 125 fps or 250 fps with 125 maxpackets give 125 packets/s; 333 fps gives ~111/s (125) or ~83/s (100).
- Recommended: `com_maxfps 125` or `250` with `cl_maxpackets 125`.

### snaps
- The server caps `snaps` at its `sv_fps` (usually 20, some servers 40). Setting it high is harmless but gains nothing beyond that.

### Recoil (pistols, scoped weapons)
- **legacy:** FPS independent (since 2021).
- **nitmod:** vanilla behavior. Recoil is applied in fixed 15 ms steps with at least one step per frame, so more FPS = more recoil: smallest at ~66–71 fps (one step per frame), about 5× at 333 fps. Only a server with `pmove_fixed 1` (pmove runs in fixed 8 ms steps) removes the FPS dependency.
- **Other mods** (etpro, jaymod, etpub, silEnT; not verified): based on 2.60b code, so vanilla behavior like nitmod is likely.

### Spread
Same formula in legacy and nitmod (both based on vanilla); `cg_drawSpreadScale`/`cg_crosshairPulse` show it.
- **Turning:** each command measures turn speed, capped at 150 °/s (below 30 °/s it adds nothing); spread recovers in every frame.
  - Fast flicks: if the mouse only reports every k-th frame, the increase drops to 1/k. So FPS well above the mouse polling rate reduces flick spread. It does not reach zero at FPS = 2× polling rate.
  - Slow tracking: the opposite. At 20 °/s with input every frame there is no increase; with input only every 4th frame the frames with input measure 80 °/s and spread grows.
  - With a 1000 Hz mouse every frame has input (`com_maxfps` ≤ 500), so the effect only exists with polling rates of 250 Hz or lower.
  - Likely reason it doesn't work on every server: with `pmove_fixed 1` the anti-warp code drops commands that fall into the same `pmove_msec` step, so the server effectively sees at most 125 fps.
- **Crouch/prone:** spread recovers twice as fast and you can turn twice as fast before it grows (not "half the spread"). Machine guns also get ×0.6 spread crouched/prone.
- **Jumping/falling:** legacy uses double the maximum spread in the air (nitmod not verified).
- **Going prone:** only if the server enables it — legacy `g_pronedelay` (default 0): maximum spread for 1 s; nitmod `n_proneDelay 1/2`: spread ×2 for 1 s.
- **Movement:** legacy counts running speed only for scoped weapons. nitmod decides per weapon whether movement and turning count (server weapon config).

### Understanding the lagometer
https://te666.forumotion.com/t522-interpreting-the-lagometer-rate-fps-snaps-etc#4983

>Advanced Lagometer consists of two lines - bottom and top. The bottom line advances one pixel per each snapshot received from server (by default they are being sent at 20 snapshots per second rate), while the top one advances one pixel per each frame that is rendered by client. Thus, if the machine framerate was 20 per second, both lines - top and bottom - would run at the same speed.
>
> Bottom bars correspond to delay before sending a snapshot by a server and receiving it by a client (so called "ping"). The shorter the bar, the smaller the ping was. Red bars mean that the frame has not arrived on time, yellow ones - that the snapshot was suppressed to stay under the rate limit. 
> Top bars can be drawn in blue or in yellow. While server shapshots are usually received at lower rate as the client framerate, the software interpolates position and movements until it gets an update from a server, when it adjusts own state accordingly. The height of upper bars is proportional to the interpolated time between snapshots received (so as long as they come regularly, it stays below the "zero line" and is drawn in blue), or - if snapshots stop to arrive on time - is extrapolated after the last snapshot expected (then bars crosse the "zero line" and are drawn in yellow). If those bars stay yellow for too long, client is forced to interpolate its frames beyond the "reasonable level" and finally, when the snapshot arrives, the prediction turns out to hardly correspond to the server-side version, which results in a jerky, uncontinuous movement of scenery (obviously lowering the quality of gameplay).
