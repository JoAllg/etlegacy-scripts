"""Machine-specific values from settings.conf (written by deploy.sh), shared by all tools."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FILE = REPO / "settings.conf"

if not FILE.exists():
    sys.exit(f"{FILE} missing: run deploy.sh first")
# KEY="value" lines; deploy.sh writes no escapes, so stripping the quotes is enough
_values = {k.strip(): v.strip().strip('"') for k, sep, v in
           (line.partition("=") for line in FILE.read_text().splitlines())
           if sep and not k.lstrip().startswith("#")}


def _get(key):
    """Required value; an empty one would silently become Path(".") (the cwd)."""
    if not _values.get(key):
        sys.exit(f"{key} missing or empty in {FILE}: delete the line and run deploy.sh to detect it again")
    return _values[key]


HOMEPATH = Path(_get("HOMEPATH"))  # fs_homepath: mod folders, etmain/dlcache
BASEPATH = Path(_get("BASEPATH"))  # fs_basepath: stock and legacy pk3s
GAME_BIN = _get("GAME_BIN")
GAME_BIN_I386 = _values.get("GAME_BIN_I386", "")  # 32-bit client, only for i386-only mods
PROFILE = _get("PROFILE")
KEYMAP_MOD = _get("KEYMAP_MOD")
# colors of the vsay texts: base of vsay_team / vsay / vsay_buddy, punctuation, key words, urgent words
VSAY = {k: _get("VSAY_" + k.upper()) for k in ("team", "global", "buddy", "punct", "highlight", "urgent")}
# colors of the echo menus (voice chat, spawn selector): heading, key, item, TAB line, global chat item, spawnpoint owner
MENU = {k: _get("MENU_" + k.upper()) for k in ("head", "key", "text", "nav", "global", "axis", "allies")}
