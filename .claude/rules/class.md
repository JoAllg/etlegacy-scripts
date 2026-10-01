---
paths:
  - "default/scripts/classcript.cfg"
  - "default/scripts/class/**"
  - "default/mods/*/mod_classcommands.cfg"
---

# Class script

Naming (`b_`/`r_`, class codes, `cs_`, `ta_`, hooks): `docs/conventions.md` "Team/class". Bind overview per class: `tools/keymap/keymap.html` (never read it, run the keymap skill).

| File | Holds |
|---|---|
| `scripts/classcript.cfg` | user-facing part: team/class key binds (keypad), `cs_<class>_<weapon>` assignments (which `bind*` scripts a class gets), `cs_default`, `resetToggles`, `ta_<Team>`, `fireteamChoice`, general `setTeamSpectator` |
| `class/cs_backend.cfg` | logic: team aliases, hooks, class keys, the weapon cycles `<b\|r>_<class>`, `...Again`, `<b\|r>_<class><n>` |
| `class/cs_classcommands.cfg` | etmain default class commands `<b\|r>_<class>_<weapon>` (`team <b\|r> <class> <weapon> <weapon2>`) |
| `mods/<mod>/mod_classcommands.cfg` | the same aliases with the mod's weapon IDs (`.claude/rules/mods.md` "Class commands") |
| `class/cs_classcripts.cfg` | feature scripts the assignments bind (`bind<Key><Script>`), sniper mode, class vsays toggle (F7) |
| `class/cs_output.cfg` | `echo-<b\|r>_<class><n>` / `say-<b\|r>_<class><n>` texts |

Flow of a class key (e.g. allies soldier): `vstr so` → `b_so` (first press: `reset cycleAlliesSoldier`, points the key to `b_soAgain`) → `b_soAgain`: `chatFunction`, `classHook` (`resetToggles`, `cs_default`, spawn selector), `preJoinHookb`, `cycleAlliesSoldier` → `b_so<n>` (`cs_soldier_<weapon>`, `b_soldier_<weapon>`, next cycle step, `echo-`/`say-`), `postJoinHookb`.

A new weapon variant touches, for both teams:
1. `cs_backend.cfg`: the cycle step `<b|r>_<class><n>` and the previous step's pointer
2. `classcript.cfg`: `cs_<class>_<weapon>`
3. `cs_classcommands.cfg` and every `mods/<mod>/mod_classcommands.cfg` (`example/` included): `<b|r>_<class>_<weapon>`
4. `cs_output.cfg`: `echo-`/`say-<b|r>_<class><n>`

Rules:
- Start values of state live in `default/state.cfg`: the armed join hooks, the cycle pointers `cycle<Team><Class>`, `chatFunction`, the class vsays toggle, the team brightness.
- Everything a class script changes must be undone on a class change: binds through `cs_default`, toggles through `resetToggles`. Only what is safe while alive belongs there (class keys are pressed mid-life): prone is reset by `resetTemporary` (kill key, F4) instead.
- `ta_Axis`/`ta_Allies` run `vid_restart` when the team's overbright values are not active yet (`brightness<Team>` guard, armed in `state.cfg`), which re-runs the map autoexec; join hooks run once per team join, so nothing in a class change may re-arm them.
- Class vsays (`classVsay<Action>`) send the texts of `scripts/vsays/vsays_custom.cfg`.
