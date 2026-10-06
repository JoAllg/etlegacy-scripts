---
paths:
  - "default/huds/**"
  - "default/hud.dat"
---

# HUD files

Written by the legacy HUD editor (`edithud`, docs: https://etlegacy.readthedocs.io/en/latest/hudeditor.html); the user normally changes the HUD in game. Legacy mod only, other mods ignore these files.

- JSON, 55–70 KB (3000+ lines): never read a whole file. Query it instead:
  ```
  python3 -c "import json;d=json.load(open('default/huds/hud_v8.dat'));print([(h['name'],len(h['components'])) for h in d['huds']])"
  python3 -c "import json;d=json.load(open('default/huds/hud_v8.dat'));print(json.dumps(next(h for h in d['huds'] if h['name']=='default')['components']['popupmessages'],indent=1))"
  ```
- Structure: `{"version": N, "huds": [{"name", "parent", "components": {<component>: {rect, visible, style, scale, colors, textStyle, anchor, parent}}}]}`. The HUD in use is the one named by `cg_altHud` (`default/cvars.cfg`).
- Which file the game loads (`src/cgame/cg_hud_io.c` `CG_ReadHudsFromFile`): the fixed path `profiles/<cl_profile>/huds/hud_v<version>.dat`, `<version>` being the JSON version compiled into the cgame (`CURRENT_HUD_JSON_VERSION`, `src/cgame/cg_local.h`: 8); no cvar selects the file. The game writes it itself: on a HUD editor save, and upgraded from the highest older `hud_v<n>.dat` when the current one is missing. After a mod update with a higher JSON version the game writes the new file from the live `hud_v8.dat`. Cgames before 2.85 read only `profiles/<cl_profile>/hud.dat`: 2.83 accepts JSON version ≤ 4 and deletes a newer file (after a `hud_backup(<date>).dat` copy), 2.84 (legacy 2.84 servers, etps) accepts ≤ 7 and upgrades older versions in memory. So `default/hud.dat` is version 4, converted from `huds/hud_v7.dat` by reversing the 2.84 upgrade steps 4→7 (`CG_ReadHudJsonObject`: `barStyle` back into `style`, dynamic color bits of healthbar/crosshairbar, popup filter echo bit 5 removed); a HUD editor save on a 2.84 server rewrites it as version 7, which the next 2.83 server deletes. `huds/hud_v4.dat` mirrors `hud.dat` (2.85+ copies `hud.dat` into `huds/hud_v<its version>.dat` when that file is missing). `huds/hud_v7.dat` is read by 2.84 dev snapshots and is the upgrade source of 2.85+ when `hud_v8.dat` is missing; its only difference to `hud_v8.dat`: crosshairbar `style` BIT(2) dynamic color is BIT(3) in version 7, BIT(2) is prestige.
- Edit with a script that loads and dumps the JSON (tab indent, as the game writes it), not by hand, and only the component asked for. The game rewrites the file when the HUD editor saves.
- Scripts that change a component in game (`editcomponent`, in memory only) need an alias that puts it back as the file has it. `tools/helpers/hudvalues.py` (run by `deploy.sh`) writes those into the `HUD VALUES` block of `user.cfg`: it takes the command from `default/mods/legacy/mod_general.cfg` (fallback with the built-in HUD's numbers) and replaces the numbers. Today: `popupmessagesNormal`, `popupmessagesMenu`. A new script of that kind gets its alias there and in the tool, never a literal HUD position in a versioned cfg.
- Popups: lines, stay and fade time are values of the `popupmessages` component in legacy 2.84+; 2.83 has no `feedStayTime`/`feedFadeTime` and uses `cg_popupStayTime`/`cg_popupFadeTime` instead, so `popupmessagesNormal`/`popupmessagesMenu` set both with the same times (hudvalues.py fills both); the echo menu colors (`MENU_*`) are chosen for its `textStyle 3` shadow.
