---
paths:
  - "default/scripts/spawnscript.cfg"
  - "default/scripts/voicechat.cfg"
  - "default/scripts/servermenu.cfg"
  - "default/scripts/vsays/**"
  - "default/binds_custom.cfg"
  - "default/scripts/scripts.cfg"
  - "default/state.cfg"
---

# Number row key layers

- `1`–`0`, `US_MINUS`, `US_EQUALS` (and `TAB`, voicechat and server menu only) are rebound by the spawn selector (`spawnscript.cfg`, map autoexecs; opened by `ENTER`), voicechat (`voicechat.cfg`, `vsays/`; opened by `v`) and server menu (`servermenu.cfg`, generated pages in `servers/`; opened by `KP_MINUS`) layers.
- `bindWeapons` (`binds_custom.cfg`) is the normal number-row binding. `reBindNumbers` (`binds_custom.cfg`, shared by all layers) must restore every key any layer binds: update it when a layer binds another key or the normal binds of these keys change.
- Every layer that rebinds keys has a `reset<Layer>` alias that closes it (`resetVoiceChat`, `resetSpawnSelector`, `resetServerMenu`). `resetLayers` (`scripts.cfg`) calls all of them; `F4`, the release of `ESCAPE` and every layer's opener run it, so opening one layer closes the others. Add new layers there too.
- Every echo menu page starts with `vstr popupsMenu` (clears the previous page, menu popup values) and every `reset<Layer>` runs `vstr popupsClose` (restores them once the menu is closed); `scripts.cfg`, with the per-mod values `setPopupsMenu`/`setPopupsNormal` in `mods/<mod>/mod_general.cfg`.
- The spawn selector page is the map's `spawnpsr`/`spawnpsb` (echo list + the `bind`s of that map's keys, `.claude/rules/autoexecs.md`), run by `spawnSelector4` after `vstr unbindNumberRow` (number row without `TAB`, which keeps the scores). A voice chat page is a file exec'd when opened (`.claude/rules/vsays.md`). Keys the page doesn't use must not keep the parent page's action: every voice chat page runs `vstr unbindNumbers` (`binds_custom.cfg`, frees all layer keys) before its binds, the generated server pages too.
- Start binds of the layer keys (`vstr bindWeapons`, `vstr bindTabScores`): `state.cfg`, not the definitions.
- A menu stays visible until it is closed where the mod allows it (`setPopupsMenu`: legacy, nitmod; jaymod caps it at 9 s), so every exit path must run the layer's reset.
- Page sizes: a mod shows only as many popup lines as its `setPopupsMenu` allows (legacy and jaymod 15, nitmod 8, mods without popup settings their default). Pages that must fit every mod hold a heading + 7 items (server menu `p7_<n>.cfg`; `serverMenuPage` in `mod_general.cfg` selects the pages of 12 where they fit).
