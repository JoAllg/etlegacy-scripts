# Script conventions (Taranis)

Standards used in the live scripts. Not enforced everywhere yet — follow them for new code; see "Known deviations" for existing exceptions.

## Keys and binds

- `binds_default.cfg` holds the game's default binds (`unbindall` runs before it, in `mods/<mod>/autoexec.cfg`). Each default key is marked:
  - `bind ...` (active): default is kept
  - `//bind ...`: key is used/overwritten by my own scripts in another cfg
  - `////bind ...`: key is not used at all

  When a script takes over a default key, change its line to `//`; when a key is freed, mark it `////`.
- `binds_custom.cfg`: basic overrides and weapon binds.
- Feature scripts bind their own keys directly in their block (`bind F8 "vstr soundToggle"`).



## Alias naming


| Pattern                                                  | Meaning                                                  | Examples                                                                                      |
| -------------------------------------------------------- | -------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| `bind<Key><Script>`                                      | value is a `bind` command; `vstr` it to (re)bind the key | `bindMouse2Weapalt`, `bindLeftaltCrouch`, `bindLessAirstrike`, `bindSpaceJump`            |
| `bindNumbers<Menu>`                                      | binds a group of keys for a menu layer                   | `bindNumbersCategories`, `bindNumbersSpawnpsr`                                                |
| `set<Thing>`                                             | sets cvars / a setting when `vstr`'d                     | `setPopupsMenu`, `setPopupsNormal`, `setTeamSpectator` (mod-overridable commands)            |
| `<cvar>Normal` / `Low` / `Higher` / `Sniper` / `Default` | value alias: full `cvar value` command                   | `fovNormal`, `fovLow`, `pitchSniper`, `maxFpsLow`, `nameDefault`                              |
| `<feature>Toggle` + `<feature>ON` / `OFF`                | toggle pointer and its states                            | `sniperToggle`, `soundToggle`, `hudToggle`                                                    |
| `+vstr <feature>ON <feature>OFF`                         | hold press/release aliases                               | `crouchON`/`crouchOFF`, `statisticsON`/`statisticsOFF`                                        |
| `cycle<Feature>` + `<feature><Value>`                    | manual cycle pointer and steps named by their value      | `cycleCrosshairColor` → `crosshairColorCyan`, `cycleGamma` → `gamma175`, `cycleFPS` → `fps71` |
| `cycle<Feature>Up` / `Down` + `<feature><Value>`         | bidirectional cycle pointers                             | `cycleCrosshairSizeUp` / `Down` → `crosshairSize15`                                           |
| `reset<Feature>`                                         | shared cleanup used by every exit path                   | `resetSniper`, `resetProne`, `resetToggles`, `resetLayers`, `resetTemporary`, `resetTeamBinds`, `resetVoiceChat`          |
| `play<Sound>`                                            | sound command aliases (`scripts/common.cfg`)             | `playSelect`, `playCancel`, `playFilter`                                                      |
| `null`                                                   | empty no-op alias for disabled hooks                     | `set preJoinHookb vstr null`                                                                  |


Menu layers (voicechat, spawn selector): `chat<Category>` opens a category (echo + bind), `echo<Item>` prints one line, `c<Cat><n>` is the key action, `vsay<Cat><n>` holds the vsay text.

Team/class (`scripts/classcript.cfg`, `scripts/class/`):

- `b_` = allies, `r_` = axis (ET team letters); class codes `so`, `me`, `en`, `fo`, `co`
- `b_<class>_<weapon>` / `r_...`: class commands (per mod in `mods/<mod>/mod_classcommands.cfg`)
- `cs_<class>_<weapon>`: class script assignments (binds per class), `cs_default`: defaults restored on every class change
- `ta_<Team>`: team settings (brightness etc.)
- Hooks: `classHook` (every class selection), `preJoinHook<b|r>` / `postJoinHook<b|r>` (run once per team join)
- Output: `echo-<b|r>_<class><n>`, `say-<b|r>_<class><n>`



## Variables

- **Start values of state** (toggle/cycle pointers, keys scripts rebind, cvars scripts change) go into `state.cfg` (mod specific ones into `modState` in `mods/<mod>/mod_general.cfg`), not into the definitions, so `F3` keeps them; decide per feature (`.claude/rules/exec-chain.md`).
- `seta` **only for real game cvars**, in `cvars.cfg` (state cvars in `state.cfg`) (they persist in `etconfig.cfg`). User aliases use `set`, so they don't persist outside the scripts.
- **Every cvar a script changes** has its `seta` default in `cvars.cfg` and a `...Normal` value alias next to it, so scripts can restore it (`vstr fovNormal`) and a default changes in one place.
- **Mod differences:** the general default lives in the general files (e.g. `fovLow` in `cvars.cfg`, `setTeamSpectator` in `classcript.cfg`); `mods/<mod>/mod_general.cfg` overrides it later in the exec chain. Class command IDs go in `mods/<mod>/mod_classcommands.cfg`.



## Feedback

- Every state change plays a sound and echoes the new state:
  - `vstr playSelect`: activating / selecting / on
  - `vstr playCancel`: deactivating / cancel / reset
  - `vstr playFilter`: before team messages (`say_team...`)
- Echo format: `echo ^8<FEATURE> ^2<on / value>` or `^1<off>` (`^8` label, `^2` positive/value, `^1` negative).
- Vsay text colors (`vsay`, `vsay_team` text): use the user's `VSAY_*` colors in `settings.conf` (base color per command, punctuation, key word and urgent highlight); if they are missing, ask the user which colors to use. `tools/vsaycolors.py` / the `vsay-highlight` skill apply them to all vsay texts.
- Echo menus (voice chat, spawn selector): `<key>. <item>` lines under a `<HEADING>:` line, in the user's `MENU_*` colors in `settings.conf` (heading, key, item, TAB line, global chat item, spawnpoint owner); `tools/vsaycolors.py apply` recolors them after a change.



## File layout

- Header: ASCII "TARANIS" banner with the file's title.
- Sections: `//--- [ NAME ] ---//`; feature blocks start with an uppercase title comment (`// CROUCH TOGGLE`) followed by `// -`  notes, then the bind, then the aliases.
- Last line: load marker `echo "^5*** <NAME> LOADED!"`, indented by two spaces per exec level, so the console shows the chain as a tree (autoexecs: `>>> ` instead of `*** `, unindented):
  ```
  >>> AUTOEXEC LOADED!            mods/<mod>/autoexec.cfg, map autoexecs (>>> AUTOEXEC_MAP / AUTOEXEC_DEFAULT)
    *** DEFINITIONS LOADED!       definitions.cfg, user.cfg, state.cfg
      *** CONFIG LOADED!          their children (cvars, binds, scripts, server, mod_general, mod_classcommands)
        *** CHAT LOADED!          one level deeper (scripts/class/, scripts/vsays/)
  ```
  The marker needs the quotes: `echo` rejoins unquoted arguments with single spaces and would drop the indent. A parent prints after its children (a nested `exec` runs before the caller's remaining lines), so the markers read like closing brackets.
- `exec` paths are always `profile/...` (the profile link of `deploy.sh`), never `profiles/<name>/...`; comments that name a file write `profiles/<profile>/...`, so they show where the path leads (commented-out commands keep their `profile/` path); `wait 10` / `wait 50` between execs and larger sections.
- Bigger scripts are split by role: e.g. `class/cs_backend.cfg` (logic), `cs_classcommands.cfg` (commands), `cs_classcripts.cfg` (feature scripts), `cs_output.cfg` (echo/say text).



## Known deviations

- Toggle/hold naming varies where the states have better names than ON/OFF: `demotoggle`/`demostart`/`demostop`, `crouchswitch`/`duck`/`stand`, `mapToggle`/`mapOUT`/`mapIN`, `weapon6Satchel_ON`, `fieldopArty1`/`fieldopArty2`, movement `on`/`off` in lowercase.

