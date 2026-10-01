---
paths:
  - "default/maps/**"
---

# default/maps (location files)

Read `docs/locations.md` before working on these files (lookup order, format, limits, cvars, legacy vs nitmod).

- Only `<map>_loc_override.dat` files belong here; the folder is symlinked into the mod folders and wins over the files in pk3s
- Header comments name the legacy cvar (`cg_locationMaxChars`), never the ETPro one (`b_locationMaxChars`)
- Keep the author credits in the headers
