---
paths:
  - "research/**"
---

# research/ (cvar and command dumps, decompiles)

Local folder, not in version control. Workflow, column meanings and caveats: `research/README.md` (read the section you need, 8 KB).

- Folders: `<mod>_<version>/` (`legacy_2.85.0`, `nitmod_2.3.5`, `jaymod_2.2.0`), legacy is the base of all diffs.
- Generated, never edit by hand: `cvars.tsv`, `cmds.tsv`, `diff_legacy.md`, `diff_profile.md`, `profile_unused.md` and `README.md` (its template is in `build_docs.py`). Regenerate: `dump_cvars.py [mod ...]` (starts the game: needs the display, outside the sandbox) → `build_docs.py` → `diff_profile.py`; `dump_cvars.py --parse <dir>` re-parses a `console.log` without starting the game.
- `dump_cvars.py` (also `--parse`) and `diff_profile.py` need the ET: Legacy source in the environment: `ETLEGACY_SRC=<ET: Legacy source checkout> python3 research/diff_profile.py` (path: `CLAUDE.local.md`). They scan `src/**/*.c` for `Cvar_Get`/`Cvar_Set` to tell client from server engine cvars (`side`, `source` columns) and, in `profile_unused.md`, engine cvars a dump missed from names that do not exist. No checkout on this machine: clone it into the scratchpad for the run (`git clone --depth 1 https://github.com/etlegacy/etlegacy`), never into the repo; `build_docs.py` needs no source.
- `console.log` is 120–230 KB: never read it, `grep -n` for the line. The `.tsv` files are for `grep '^<name>	'` (columns `name, flags, value, default, side, source` / `name, description`), the `diff_*.md` files (15 KB) for `grep` too.
- `maps/maps_<YYYY-MM-DD>/`: snapshot of the location files in the dlcache pk3s, written by `maps/extract_locations.py` (`<pk3>__<file>` for a map pk3, `<pk3>/<file>` for a pack with several maps; `legacy_v*.pk3` skipped; a rerun the same day rebuilds that day's folder). It reports new and changed files against the newest older snapshot, and the snapshot maps without a file in `<profile>/maps/`, in `maps/report_<YYYY-MM-DD>.txt`. Rerun after new downloads.
- `changelog_2.84-2.86.md` (19 KB): legacy changes per version, grep by cvar or keyword.
- Decompiles of closed mods: `<mod>_<version>/decompiled/<binary>_<topic>.c`, made with `research/decompile/decompile.sh <binary> <func,func,...> <out.c>` (Ghidra headless). Grep the existing files before decompiling again, and add new functions there, never in the scratchpad. The files are 10–65 KB: grep for the function (`// ==== <name>`) and read only that part.
- A fact taken from a dump or decompile is cited in docs with its source (`research/<mod>/decompiled/<file>.c`), and marked "not tested in game" until the user confirmed it.
