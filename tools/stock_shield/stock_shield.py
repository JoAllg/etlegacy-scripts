#!/usr/bin/env python3
"""Build the nitmod stock shield pk3 from the stock etmain pk3s and install it into the nitmod folder.

Also hides arena files of server packs whose map can't be hosted locally (bsp only in etmain/dlcache/ or nowhere):
the host game list shows every arena, starting one without its bsp leaves the menu at "connecting".
Rebuild after new server downloads.

Usage: python3 tools/stock_shield/stock_shield.py   (see README.md next to it)
       python3 tools/stock_shield/stock_shield.py --selftest
The files are game assets (ET EULA), so the pk3 is built from the local game instead of being shipped.
"""
import argparse
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers.common import ETMAIN, STOCK_PAKS, maps  # noqa: E402
from helpers.settings import BASEPATH, HOMEPATH  # noqa: E402

# more tildes than any server pk3, so it sorts last and wins (README.md)
NAME = "~" * 60 + "stock_shield.pk3"
# the pk3 that sorts last wins, so pak2 before pak1 before pak0
PAKS = ["pak2.pk3", "pak1.pk3", "pak0.pk3"]
FILES = """
fonts/ariblk_16.dat
gfx/2d/compass.tga gfx/2d/compass2.tga gfx/2d/compass_mask.tga
icons/iconw_ammopack_1_select.tga icons/iconw_medheal_select.tga
maps/battery.script maps/fueldump.script maps/oasis.script maps/radar.script
scripts/battery.arena scripts/fueldump.arena scripts/goldrush.arena scripts/oasis.arena scripts/radar.arena
scripts/railgun.arena scripts/battery.shader scripts/sprites.shader scripts/wm_allies_chat.voice scripts/wm_axis_chat.voice
ui/assets/3_cursor3.tga ui/assets/background_mask.tga ui/assets/check.tga ui/assets/check_no.tga
ui/assets/check_not.tga ui/assets/gradientbar1.tga ui/assets/hudsprint.tga ui/assets/mp_gun_blue.tga
ui/assets/scrollbar.tga ui/assets/scrollbar_arrow_dwn_a.tga ui/assets/scrollbar_arrow_left.tga
ui/assets/scrollbar_arrow_right.tga ui/assets/scrollbar_arrow_up_a.tga ui/assets/scrollbar_thumb.tga
ui/assets/slider2.tga ui/assets/sliderbutt_1.tga ui/assets2/stamp_complete.tga ui/assets2/stamp_failed.tga
ui/credits_activision.menu ui/credits_additional.menu ui/credits_idsoftware.menu ui/credits_quit.menu
ui/credits_splashdamage.menu ui/hostgame.menu ui/ingame_disconnect.menu ui/ingame_messagemode.menu
ui/ingame_serverinfo.menu ui/ingame_tapout.menu ui/ingame_tapoutlms.menu ui/ingame_vote.menu
ui/ingame_vote_disabled.menu ui/ingame_vote_map.menu ui/ingame_vote_misc_refrcon.menu ui/ingame_vote_players.menu
ui/ingame_vote_players_warn.menu ui/mods.menu ui/options.menu ui/options_controls.menu
ui/options_controls_default.menu ui/options_customise_game.menu ui/options_customise_hud.menu ui/options_system.menu
ui/options_system_gamma.menu ui/playonline_connecttoip.menu ui/playonline_disablepb.menu ui/playonline_enablepb.menu
ui/playonline_serverinfo.menu ui/popup_autoupdate.menu ui/popup_errormessage.menu ui/popup_errormessage_pb.menu
ui/popup_hostgameerrormessage.menu ui/popup_password.menu ui/popup_serverredirect.menu ui/profile.menu
ui/profile_create.menu ui/profile_create_error.menu ui/profile_create_initial.menu ui/profile_delete.menu
ui/profile_delete_error.menu ui/profile_rename.menu ui/quit.menu ui/rec_restart.menu ui/vid_confirm.menu
ui/vid_restart.menu ui/viewreplay.menu ui/viewreplay_delete.menu ui/wm_ftquickmessage.menu
ui/wm_ftquickmessageAlt.menu ui/wm_quickmessage.menu ui/wm_quickmessageAlt.menu
""".split()
# whole folders: sound packs replace stock sounds under their stock names
FOLDERS = ("sound/",)
# search path of a local nitmod game, lowest priority first; dlcache/ is not mounted there
MOUNTED = (STOCK_PAKS, ETMAIN, BASEPATH / "nitmod", HOMEPATH / "nitmod")
HIDDEN = b"// map not hostable locally, hidden by the stock shield\n"
TOKEN = re.compile(rb'//[^\n]*|/\*.*?(?:\*/|$)|"[^"]*"?|[{}]|[^\s{}"]+', re.S)


def shielded(paks):
    """{file: pak} of FILES and everything below FOLDERS, each from the first pak that has it."""
    found = {}
    for pak in paks:
        for name in pak.namelist():
            if name in FILES or (name.startswith(FOLDERS) and not name.endswith("/")):
                found.setdefault(name, pak)
    return found


def arena_blocks(text):
    """[(map name lowercase, block bytes)] of an arena file, tokens as the engine's precompiler splits them."""
    blocks, start, name, key = [], None, None, False
    for m in TOKEN.finditer(text):
        tok = m.group()
        if tok.startswith((b"//", b"/*")):
            continue
        if tok == b"{" and start is None:
            start, name, key = m.start(), None, False
        elif tok == b"}" and start is not None:
            blocks.append((name, text[start:m.end()]))
            start = None
        elif start is not None:
            if key and name is None:
                name = tok.strip(b'"').decode("latin1").lower()
            key = tok.lower() == b"map"
    return blocks


def arenas(hostable):
    """{arena path: new content} for the winning arena files whose maps aren't all hostable."""
    winners = {}
    for folder in MOUNTED:
        for pk3 in sorted(folder.glob("*.pk3"), key=lambda p: p.name.upper()):  # FS_PathCmp: later wins
            if pk3.name == NAME:
                continue
            try:
                with zipfile.ZipFile(pk3) as z:
                    for i in z.infolist():
                        path = i.filename.replace("\\", "/").lower()
                        if re.fullmatch(r"scripts/[^/]+\.arena", path) and path not in FILES:
                            winners[path] = z.read(i)
            except (zipfile.BadZipFile, OSError):
                continue
    out = {}
    for path, text in winners.items():
        blocks = arena_blocks(text)
        kept = [b for name, b in blocks if name in hostable]
        if len(kept) < len(blocks):
            out[path] = b"\n".join(kept) + b"\n" if kept else HIDDEN
    return out


def hostable_maps():
    """Lowercase names of the maps a local nitmod game can load (bsp in a pk3 of its search path)."""
    return {m for folder in MOUNTED for pk3 in folder.glob("*.pk3") if pk3.name != NAME for m in maps(pk3) or {}}


def main():
    paks = [zipfile.ZipFile(BASEPATH / "etmain" / p) for p in PAKS]
    out = HOMEPATH / "nitmod" / NAME
    if not out.parent.is_dir():
        sys.exit(f"{out.parent} missing: nitmod is not installed")
    found = shielded(paks)
    missing = sorted(set(FILES) - set(found))
    if missing:
        sys.exit(f"{', '.join(missing)} in none of {', '.join(PAKS)} in {BASEPATH / 'etmain'}")
    hidden = arenas(hostable_maps())
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as pk3:
        for name, pak in sorted(found.items()):
            pk3.writestr(name, pak.read(name))
        for name, text in sorted(hidden.items()):
            pk3.writestr(name, text)
    print(f"wrote {out} ({len(found) + len(hidden)} files)")
    for name, text in sorted(hidden.items()):
        print(f"  {'hidden' if text == HIDDEN else 'trimmed'}: {name}")


def selftest():
    """Arena parsing; every listed file and every folder exists in the local stock paks (reads only)."""
    text = b'// x { map "no" }\n{\n map "Alpha"\n longname "A { b"\n}\n/* { */ {map beta briefing "x"}'
    assert [n for n, _ in arena_blocks(text)] == ["alpha", "beta"], arena_blocks(text)
    assert arena_blocks(text)[0][1] == b'{\n map "Alpha"\n longname "A { b"\n}'
    assert len(set(FILES)) == len(FILES), [f for f in FILES if FILES.count(f) > 1]
    found = shielded([zipfile.ZipFile(BASEPATH / "etmain" / p) for p in PAKS])
    assert not set(FILES) - set(found), sorted(set(FILES) - set(found))
    for folder in FOLDERS:
        assert any(n.startswith(folder) for n in found), folder
    print("selftest ok")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true")
    selftest() if ap.parse_args().selftest else main()
