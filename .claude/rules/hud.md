---
paths:
  - "default/huds/**"
---

# HUD files

Written by the legacy HUD editor (`edithud`, docs: https://etlegacy.readthedocs.io/en/latest/hudeditor.html); the user normally changes the HUD in game. Legacy mod only, other mods ignore these files.

- JSON, 55–70 KB (3000+ lines): never read a whole file. Query it instead:
  ```
  python3 -c "import json;d=json.load(open('default/huds/hud_v8.dat'));print([(h['name'],len(h['components'])) for h in d['huds']])"
  python3 -c "import json;d=json.load(open('default/huds/hud_v8.dat'));print(json.dumps(next(h for h in d['huds'] if h['name']=='default')['components']['popupmessages'],indent=1))"
  ```
- Structure: `{"version": N, "huds": [{"name", "parent", "components": {<component>: {rect, visible, style, scale, colors, textStyle, anchor, parent}}}]}`. The HUD in use is the one named by `cg_altHud` (`default/cvars.cfg`).
- Which file the game loads (`src/cgame/cg_hud_io.c` `CG_ReadHudsFromFile`): the fixed path `profiles/<cl_profile>/huds/hud_v<version>.dat`, `<version>` being the JSON version compiled into the cgame (`CURRENT_HUD_JSON_VERSION`, `src/cgame/cg_local.h`: 8); no cvar selects the file. The game writes it itself: on a HUD editor save, and upgraded from the highest older `hud_v<n>.dat` when the current one is missing. The repo keeps only the live `hud_v8.dat`; after a mod update with a higher JSON version the game writes the new file from it.
- Edit with a script that loads and dumps the JSON (tab indent, as the game writes it), not by hand, and only the component asked for. The game rewrites the file when the HUD editor saves.
- Scripts that change a component in game (`editcomponent`, in memory only) need an alias that puts it back as the file has it. `tools/helpers/hudvalues.py` (run by `deploy.sh`) writes those into the `HUD VALUES` block of `user.cfg`: it takes the command from `default/mods/legacy/mod_general.cfg` (fallback with the built-in HUD's numbers) and replaces the numbers. Today: `popupmessagesNormal`, `popupmessagesMenu`. A new script of that kind gets its alias there and in the tool, never a literal HUD position in a versioned cfg.
- Popups: lines, stay and fade time are values of the `popupmessages` component in legacy (no popup cvars); the echo menu colors (`MENU_*`) are chosen for its `textStyle 3` shadow.
