---
paths:
  - "default/hud.dat"
  - "default/huds/**"
---

# HUD files

Written by the legacy HUD editor (`edithud`, docs: https://etlegacy.readthedocs.io/en/latest/hudeditor.html); the user normally changes the HUD in game. Legacy mod only, other mods ignore these files.

- JSON, 55–70 KB (3000+ lines): never read a whole file. Query it instead:
  ```
  python3 -c "import json;d=json.load(open('default/hud.dat'));print([(h['name'],len(h['components'])) for h in d['huds']])"
  python3 -c "import json;d=json.load(open('default/hud.dat'));print(json.dumps(next(h for h in d['huds'] if h['name']=='default')['components']['popupmessages'],indent=1))"
  ```
- Structure: `{"version": N, "huds": [{"name", "parent", "components": {<component>: {rect, visible, style, scale, colors, textStyle, anchor, parent}}}]}`. The HUD in use is the one named by `cg_altHud` (`default/cvars.cfg`).
- Which file the game loads (`src/cgame/cg_hud_io.c` `CG_ReadHudsFromFile`): `profiles/<profile>/huds/hud_v<version>.dat` of the mod's JSON version, falling back to older versions; `profiles/<profile>/hud.dat` is the unversioned path of older mod versions and is copied into `huds/` when no file of its version exists. So the files in `huds/` are live HUD versions, not just backups: check `"version"` and ask the user which file to change before editing.
- Edit with a script that loads and dumps the JSON (tab indent, as the game writes it), not by hand, and only the component asked for. The game rewrites the file when the HUD editor saves.
- Popups: lines, stay and fade time are values of the `popupmessages` component in legacy (no popup cvars); the echo menu colors (`MENU_*`) are chosen for its `textStyle 3` shadow.
