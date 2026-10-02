#!/usr/bin/env python3
"""Build the nitmod stock shield pk3 from the stock etmain pk3s and install it into the nitmod folder.

Usage: python3 tools/stock_shield/stock_shield.py   (see README.md next to it)
       python3 tools/stock_shield/stock_shield.py --selftest
The files are game assets (ET EULA), so the pk3 is built from the local game instead of being shipped.
"""
import argparse
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
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


def main():
    paks = [zipfile.ZipFile(BASEPATH / "etmain" / p) for p in PAKS]
    out = HOMEPATH / "nitmod" / NAME
    if not out.parent.is_dir():
        sys.exit(f"{out.parent} missing: nitmod is not installed")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as pk3:
        for name in FILES:
            pak = next((p for p in paks if name in p.NameToInfo), None)
            if pak is None:
                out.unlink()
                sys.exit(f"{name} is in none of {', '.join(PAKS)} in {BASEPATH / 'etmain'}")
            pk3.writestr(name, pak.read(name))
    print(f"wrote {out} ({len(FILES)} files)")


def selftest():
    """Every listed file exists in the local stock paks (reads only)."""
    assert len(set(FILES)) == len(FILES), [f for f in FILES if FILES.count(f) > 1]
    names = set()
    for p in PAKS:
        with zipfile.ZipFile(BASEPATH / "etmain" / p) as z:
            names |= set(z.namelist())
    assert not set(FILES) - names, sorted(set(FILES) - names)
    print("selftest ok")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true")
    selftest() if ap.parse_args().selftest else main()
