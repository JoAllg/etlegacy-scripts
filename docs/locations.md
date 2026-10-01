# Location files (map location names)

A location file names places on a map. The client uses it to show a place name (`Fuel Dump`) instead of a grid coordinate (`C,4`) wherever a position is printed. Valid for legacy 2.86 (source: `src/cgame/cg_locations.c`) and nitmod 2.3.5 (decompiled: `research/nitmod_2.3.5/decompiled/cgame_locations.c`).

Location files are client-side only. The server sends coordinates, every client names them with its own files, so other players do not see these names.

## Files and lookup order

The client looks in `maps/` of the mod search path and takes the first file it finds:

| Order | File | legacy | nitmod | Purpose |
|---|---|---|---|---|
| 1 | `maps/<map>_loc_local.dat` | yes | no | private file, written by the location editor |
| 2 | `maps/<map>_loc_override.dat` | yes | yes | replaces the file the map ships |
| 3 | `maps/<map>_loc.dat` | yes | yes | shipped by the mapper in the map pk3 |

- `<map>` is the lowercase map name in legacy: `CG_LoadObjectiveData` lowercases the name the server reports in place (`src/cgame/cg_main.c`, `Q_strlwr(cgs.rawmapname)`), and it runs before `CG_LoadLocations`. A loose file is opened by its exact name on Linux, so `stargate_1945_loc_override.dat` is found and `StarGate_1945_loc_override.dat` is not. Whether nitmod lowercases the name is unverified, so `default/maps/` keeps a link in the reported case for such maps.
- Files are not merged: the first file found supplies all locations of the map.
- Loose `.dat` files are also read on pure servers, so the overrides work on every server.
- `deploy.sh` symlinks `default/maps/` to `<fs_homepath>/etmain/maps`. `etmain` is in the search path of every mod, so this one link serves all of them. A `_loc_override.dat` of the same map in the mod folder or its pk3s (legacy's own, a server pack) is found first and wins; a `_loc.dat` anywhere loses, because the override name is looked up first.
- The path `maps/...` is fixed in the mod code and resolved against the search path roots only (mod folder, then `etmain`, each first in the homepath, loose files before pk3s). The profile folder is no search path root, so files under `profile/maps/` are never found without the link.
- legacy ships 362 `_loc_override.dat` files in its own pk3, which win over `default/maps/` for those maps (same locations); nitmod ships none, so on nitmod only `default/maps/` and the map pk3s provide locations.
- Without any file, legacy prints `LoadLocations: Warning: No location data found for map <map>` and falls back to grid coordinates.

## Mod support

The file names and the format come from ETPro; the other mods adopted them, so one set of override files serves all of them.

| Mod | Location files | Cvars | Source |
|---|---|---|---|
| legacy 2.86 | yes, plus `_loc_local.dat` | `cg_locations` (bitmask), `cg_locationMaxChars` | source code |
| nitmod 2.3.5 | yes | `cg_locations` (bitmask), `cg_locationMaxChars` | decompiled binary |
| ETPro 3.2.6 | yes; without a file it builds the locations from the map's `target_location` entities | `b_locationMode`, `b_locationMaxChars`, `b_locationJustify` | ETPro 3.2.0 release notes, binary strings |
| etpub | yes | `cg_locations` (default `1`) | source code (`cg_localents.c`) |
| silEnT 0.9.0 | yes | `cg_locations` `0` coordinates, `1` name, `2` both | binary strings, client manual 0.8.2 |
| Jaymod 2.2.0 | yes | `cg_locationMaxChars` | binary strings |
| No Quarter | "location files support" in its feature list; file names unverified | unverified | No Quarter wiki |
| ETJump 3.4.0 | no | none | binary strings |

Only legacy and nitmod are verified beyond the file names; the lookup order, limits and cvar bits below describe these two. ETPro cannot be played with the ET: Legacy client.

## Format

```
// comment
<x> <y> <z> "<name>"
<x> <y> <z> @
```

- One location point per line: integer map coordinates, separated by exactly one space, then the name.
- `@` repeats the name of the previous line, to cover one area with several points.
- Names may contain `^` color codes ([colors.md](colors.md)). Quotes are dropped.
- Limits: 1024 points per map, 32768 bytes per file, 127 characters per name. A point at `0 0 0` is ignored.
- The first location line after the header is read with `x = 0` in legacy, because only a comment at the very start of the file is recognised and the closing `/////` line of the header merges into the next line. The first point of every file therefore lies in the wrong place. nitmod has the same parser structure (not tested in game).

## How a name is chosen

For a position, the client takes the nearest location point that is in the same PVS (potentially visible from the position), so points behind walls do not count. If no point qualifies, the name is `Unknown`, which is replaced by the grid coordinate unless `cg_locations` bit 8 is set.

## Cvars

Both exist in legacy and nitmod and are set in `default/cvars.cfg`.

`cg_locations` (bitmask):

| Bit | Effect | legacy | nitmod |
|---|---|---|---|
| 1 | location names in the fireteam overlay | yes | unverified |
| 2 | location names in team chat, fireteam chat and voice chat | yes | yes |
| 4 | location names in landmine popups | yes | unverified |
| 8 | keep `Unknown` instead of the grid coordinate | yes | yes |
| 16 | append the grid coordinate to the name | yes | yes |
| 32 | show the distance to the player instead of the name | yes | unverified |

`cg_locationMaxChars <n>`: cuts location names after `n` characters, `0` = no limit. Defaults: legacy `0`, nitmod `12`. The header line `// Recommended    cg_locations, cg_locationMaxChars <n>` of every file names both: `cg_locations` has to be set for the names to show at all, `<n>` is about the length of the longest name of that map, color codes included.

## Location editor (legacy)

`loc <open|close|save [path]|add <name>|rename <name>|move|remove|dump|reload>` edits the locations of the current map in game. It needs cheats (`devmap`). `save` writes `maps/<map>_loc_local.dat`, which then wins over the override.
