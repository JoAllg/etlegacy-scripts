---
paths:
  - "docs/**"
  - "README.md"
  - "**/README.md"
  - "CLAUDE.md"
---

# Documentation

- One line per paragraph and per list item, no hard wraps.
- Only what the reader needs now: no history, no "previously"/"changed"/deprecation notes, no progress reports.
- No machine-specific paths in versioned files: write `<fs_homepath>`, `<repo>`, `<ET: Legacy source checkout>`; the real paths live in `CLAUDE.local.md` and `settings.conf`.
- Every claim about game behavior names its evidence (source file and function, mod docs, a dump or decompile in `research/`, or an in-game test with its date); what could not be verified is marked "unverified" / "not tested in game".
- One place per fact: `docs/` holds background, `.claude/rules/` the per-path rules, `CLAUDE.md` the map of both. Link instead of repeating.

`docs/` is mirrored to the GitHub wiki by `.github/workflows/wiki.yml` on every push to `main` (wiki edits are overwritten):
- Flat folder: only `docs/*.md` and `docs/images/` are copied, no other subfolders.
- Images: `docs/images/<name>.png`, linked from a doc as `![text](images/<name>.png)` and from the root `README.md` as `docs/images/<name>.png`. Screenshots show no real server names, player names or addresses (public repo).
- Links between docs: `[text](file.md)` or `[text](file.md#anchor)` with the bare file name (letters, digits, `_`, `-`); the workflow strips `.md` for the wiki. Links to other repo files don't work in the wiki: name the path in backticks instead.
- A new doc is added to `docs/Home.md`, `docs/_Sidebar.md` and the "Background docs" list in `CLAUDE.md`.

`README.md` files: the root one is for users of the repo (setup, usage); `research/README.md` is generated (`build_docs.py`); `default/scripts/vsays/README.MD` is the vsay id reference; `default/mods/<mod>/README.md` lists only that mod's differences to legacy.

`CLAUDE.md`: keep the folder tree and the exec chain in sync when files are added, moved or (un)linked. Special-case rules go to `.claude/rules/<topic>.md` with a `paths:` frontmatter, not into `CLAUDE.md` or `docs/`.
