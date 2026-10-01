---
paths:
  - "default/scripts/spawnscript.cfg"
  - "default/scripts/voicechat.cfg"
  - "default/scripts/vsays/**"
  - "default/binds_custom.cfg"
  - "default/scripts/scripts.cfg"
  - "default/state.cfg"
---

# Number row key layers

- `1`–`0`, `US_MINUS`, `US_EQUALS` and `TAB` are rebound by the spawn selector (`spawnscript.cfg`, map autoexecs; opened by `ENTER`) and voicechat (`voicechat.cfg`, `vsays/`; opened by `v`) layers.
- `bindWeapons` (`binds_custom.cfg`) is the normal number-row binding. `reBindNumbers` (`binds_custom.cfg`, shared by all layers) must restore every key any layer binds: update it when a layer binds another key or the normal binds of these keys change.
- Every layer that rebinds keys has a `reset<Layer>` alias that closes it (`resetVoiceChat`, `resetSpawnSelector`). `resetLayers` (`scripts.cfg`) calls all of them; `F4` and every layer's opener run it, so opening one layer closes the others. Add new layers there too.
- Every echo menu page starts with `vstr popupsMenu` (clears the previous page, menu popup values) and every `reset<Layer>` runs `vstr popupsClose` (restores them once the menu is closed); `scripts.cfg`, with the per-mod values `setPopupsMenu`/`setPopupsNormal` in `mods/<mod>/mod_general.cfg`.
- A menu page is three aliases: `chat<Category>` (`vstr popupsMenu; vstr echo...; vstr bindNumbers...`), `bindNumbers<Menu>` (the `bind`s) and `echo<Menu>` (heading + one `echo<Item>` per key). Keys the page doesn't use must not keep the parent page's action: every voice chat page runs `vstr unbindNumbers` (`binds_custom.cfg`, frees all layer keys) before its binds, the generated server pages too.
- Start binds of the layer keys (`vstr bindWeapons`, `vstr bindTabScores`): `state.cfg`, not the definitions.
