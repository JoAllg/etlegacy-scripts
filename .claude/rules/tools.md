---
paths:
  - "tools/**"
  - "research/*.py"
  - "deploy.sh"
  - "keymap-live.sh"
  - "servermenu.sh"
---

# Tools (Python helpers, deploy.sh)

What each tool does and its usage line: `tools/README.md` and the module docstring at the top of each script (read those, not the whole script).

- Python 3, standard library only, no new dependencies.
- Machine paths and preferences come only from `settings.conf` through `tools/settings.py` (`HOMEPATH`, `BASEPATH`, `GAME_BIN`, `PROFILE`, `REPO`, `VSAY`, `MENU`, ...): never hard-code a path, never derive the game folder from the repo location. Scripts in a subfolder add `tools/` to `sys.path` first.
- A new setting needs three places: `tools/settings.py`, its detection/default in `deploy.sh` (only missing values are appended, existing ones never changed), and the `settings.conf` line in `CLAUDE.md`.
- cfg, location and pk3 text files have no fixed encoding: classic mods draw 8-bit bytes, legacy decodes UTF-8 (`docs/special_chars.md`). A tool that writes them back reads and writes `latin1`, which keeps every byte as it is; UTF-8 would re-encode the bytes above 0x7F.
- Every tool parses its arguments with `argparse` (unknown arguments are an error, never ignored) and has a `--selftest` (plain `assert`s, prints `selftest ok`, changes nothing): run it after a change and extend it for new logic. `ponytail:` comments mark deliberate shortcuts with their ceiling.
- Tools are rerunnable: a rerun keeps what the user edited (vsay texts, the settings block of a map autoexec) and reports what it added or removed.
- A new tool gets a section in `tools/README.md` and a line in the `CLAUDE.md` folder tree; the usage stays in the docstring.
- Tools that start the game (`research/dump_cvars.py`) need the display and write to `fs_homepath`: run them outside the sandbox.

Generated output, never read whole or edited by hand:

| Output | Written by |
|---|---|
| `tools/keymap/keymap.html` (174 KB) | `tools/keymap/keymap.py`; names in `labels.json` via the keymap skill |
| `tools/spawnpoints/autoexecs/*.cfg` (~250) | `tools/spawnpoints/spawnpoints.py`; `diff.py` compares with `default/autoexecs/` |
| `default/scripts/vsays/servers/<clan>/*.cfg` | `tools/voicemenu.py` |
| `default/scripts/servers/p12_<n>.cfg`, `p7_<n>.cfg` | `tools/servermenu.py`, rewritten every few seconds while it runs |
| `tools/vsaycolors.html`, `default/scripts/vsays/vsaycolors.tsv` | `tools/vsaycolors.py` |
| `research/<mod>/*.tsv`, `diff_*.md`, `research/README.md` | `research/dump_cvars.py`, `build_docs.py`, `diff_profile.py` |

`deploy.sh`: safe to rerun, asks before replacing a folder or foreign link, never touches `guid_backup/` contents except to back up and link keys. Its header comment lists every step: keep it in sync with the code. Mod lists: `MODS` (all mod folders), `AUTOEXEC_MODS` (mods with event autoexecs, get `default/autoexecs/*`). `default/maps/` needs no list: it is linked once to `etmain/maps`.
