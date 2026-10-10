---
name: locations
description: Bring location files of downloaded maps into default/maps/. Runs research/locations/locations.py extract (snapshot of the dlcache pk3s + dated report), adds overrides for maps without one (header in the profile style), evaluates changed upstream files and merges the worthwhile changes after the user reviewed them; names in Title Case, date and editor updated. Use after new map downloads, when the user asks about new or changed location files, or to handle the reports in research/locations/.
---

# Location files from downloaded maps

Background: `docs/locations.md` (lookup order, format, limits), file rules: `.claude/rules/maps.md`. `research/locations/locations.py` does everything deterministic (docstring = usage); your part is the header data, judging changes and talking to the user.

- `.dat` files: the Read tool refuses them, use `sed -n`/`grep` in Bash. Never list `default/maps/` as a whole (~480 files).
- `add`, `merge`, `caps` are dry runs without `--apply`: always run them dry first and read the output.
- Every write through the script fixes the names (Title Case, short words lowercase, caps and leet words kept, typo list `TYPO`), sets Recommended maxChars to the longest name and, when names changed, sets Last edited to today and the editor (`PLAYER_NAME` in `settings.conf`, may be empty) in Modified by (replaces it when Modified by = Locations by, appends `, <editor>` otherwise, adds the line when missing). A new typo or leet pattern you find goes into the script (`TYPO`, `fix_word`) with a selftest line, then `--selftest`.
- The script edits only headers with the profile rows (`Map name`, `Locations by`, `Recommended`, `Last edited`; other rows stay). Any other header it keeps and prints `header without the profile rows, kept: set ...`: rewrite that header yourself into the profile layout (`add` output shows it; credits from the old header kept, the values the note names), then rerun the command dry to check.
- Comment and blank lines between the locations stay; `merge` appends added points at the end.

## 1. Snapshot and reports

1. `python3 research/locations/locations.py extract`: writes `research/locations/maps_<date>/` and `report_<date>.txt`.
2. Pending reports: `grep -L '^handled' research/locations/report_*.txt`. Work through them oldest first. A report's first line names its snapshot folder; `new`/`changed` entries are paths in it, `missing` entries are snapshot files whose map has no `default/maps/<map>_loc_override.dat`. Recheck `missing` against the current folder (an older report may be handled already by a newer file).

## 2. Missing maps: add

Group the entries by map (`<pk3>__<file>`: several pk3 versions of one map). Identical files: take one. Different ones: compare them (`diff -u` of the two files) and ask the user which to take.

Header data per map, from the source file's own comment header (`sed -n 1,12p <file>`) and the map pk3:

| Field | Rule |
|---|---|
| Map name | the map's long name from `scripts/*.arena` in its pk3 (`unzip -p <pk3> 'scripts/*.arena'`, `longname`), without color codes, tidied: Title Case, beta as `B<n>`, version tags like `(v4)` dropped (`Erdenberg B3`, `ETL Adlernest`) |
| Locations by | the author in the source header (`Locations by`, `Created by`, `Creator:`, `<name> - <date>`); `$Id: ...$` lines and map names are no authors. None: `extracted from <pk3 file name>` (server pack: the pk3 name only, never a server name: public repo) |
| Modified by | only when the source names one (`--modified`) |
| Last edited | the source's date as `DD-MM-YYYY` (pad day and month: `13-1-2022` → `13-01-2022`; month and year only: `MM-YYYY`); empty when there is none. Never today for an unchanged file |

Ask the user when a header is unclear: it names another map (copied header), an author field holds something else, the map name is ambiguous. Then:

```
python3 research/locations/locations.py add <snapshot file> --name "<Map name>" --by "<author>" [--modified "<name>"] [--date DD-MM-YYYY]
python3 research/locations/locations.py add ... --apply
```

A map whose bsp name has capitals (`unzip -l <pk3> 'maps/*.bsp'`) also gets the link `ln -s <lower>_loc_override.dat <Name>_loc_override.dat` in `default/maps/` (`.claude/rules/maps.md`).

## 3. Changed upstream files: evaluate, review, merge

For each `changed` entry: `diff <snapshot file>` (upstream against the user's file, which may hold their own edits) and `diff <snapshot file> --old` (what upstream changed since the last snapshot). Cosmetic differences (capitalization, color) are only counted, never taken over.

Judge every difference, one verdict per change:

- Worth it: points in areas the user's file doesn't cover (`only upstream`), a more specific or corrected name (a callout players use: `MG Nest`, `Tank Hill`, `Blast Door Switch`), a fixed wrong name.
- Not worth it: shorter or vaguer names (`CP` for `Command Post`, `Area1`, `Ammo Depot no.1` for `West Ammo Depot`), placeholders (`Put better loc here`), coarser areas, removal of the user's points, worse spelling.

Report to the user before changing anything: per map what upstream adds/renames, your verdict with the reason, and the exact merge you propose. Wait for their review; apply only what they approve:

```
python3 research/locations/locations.py merge <snapshot file> [--add] [--rename] [--only "<upstream name>" ...]
python3 research/locations/locations.py merge ... --apply
```

`--add` takes the upstream points the user's file lacks, `--rename` the upstream names of shared points (an uncolored name keeps the user's color), `--only` limits both to the listed upstream names. The user's points, colors and header credits stay. Changes the flags can't express: edit the file with a small script (latin-1, LF), then `caps <file> --apply`.

## 4. Finish

1. Spawn menus label rooms with location names: `python3 tools/spawnpoints/spawnpoints.py` (only maps whose location file changed are read again; it prints the autoexecs it changed).
2. Mark each processed report: `echo "handled $(date +%F)" >> research/locations/report_<date>.txt`.
3. Tell the user: maps added (header source), merges applied, changes skipped and why, autoexecs regenerated. No commit unless asked.
