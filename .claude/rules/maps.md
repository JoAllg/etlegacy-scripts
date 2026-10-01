---
paths:
  - "default/maps/**"
---

# default/maps (location files)

Read `docs/locations.md` before working on these files (lookup order, format, limits, cvars, legacy vs nitmod).

- ~450 files: never read or list the folder as a whole; open only the map you work on and change many files with a script.
- Only `<map>_loc_override.dat` files belong here; the folder is symlinked to `<fs_homepath>/etmain/maps` and serves every mod.
- `<map>` keeps the case of the map name as the server reports it (Linux is case-sensitive).
- Every header has the line `// Recommended    cg_locations, cg_locationMaxChars <n>` (`cg_locations` without a value, `<n>` about the longest name incl. color codes); legacy cvar names, never the ETPro ones (`b_locationMaxChars`).
- Keep the author credits in the headers.
- `tools/spawnpoints/spawnpoints.py` labels spawn rooms with these names: after renaming locations of a map with a generated autoexec, rerun it for that map.
