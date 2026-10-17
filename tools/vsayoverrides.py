#!/usr/bin/env python3
"""Server sounds on the stock voice chat pages (vsay-server-overrides skill): which servers have overrides and which of
their sounds the server no longer has.

Reads default/serverconfigs/vsays/<id>/override/*.cfg and compares every vsay id in them with the server's vsays.tsv
(tools/voicemenu.py); ids of the stock vsays (default/scripts/vsays/) are always valid.

  vsayoverrides.py [id ...]   per id (default: every id with a vsays.tsv): "no overrides", or its override files and
                              the lines whose sound is missing (<file>:<line>: <sound>)
  --selftest
"""
import argparse
from pathlib import Path

from helpers.common import VSAY_TEXT
from helpers.settings import PROFILE, REPO

LIVE = REPO / PROFILE
SERVERS = LIVE / "serverconfigs/vsays"
STOCK = LIVE / "scripts/vsays"


def sounds(text):
    """Vsay ids of a cfg text, comments included: a stale sound in a comment is reported too."""
    return [m.group(2) for m in VSAY_TEXT.finditer(text)]


def tsv_ids(path):
    """Vsay ids of a vsays.tsv (first column, without comment and header)."""
    rows = path.read_text(encoding="latin1").splitlines()
    return {r.split("\t")[0] for r in rows if r and not r.startswith("#") and not r.startswith("vsay\t")}


def stale(files, valid):
    """(file, line number, sound) of every sound in the files that is not valid."""
    return [(f, n, s) for f in files for n, line in enumerate(f.read_text(encoding="latin1").splitlines(), 1)
            for s in sounds(line) if s not in valid]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ids", nargs="*", help="server ids (servers.tsv), default: all with a vsays.tsv")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    ids = a.ids or sorted(p.parent.name for p in SERVERS.glob("*/vsays.tsv"))
    stock = {s for f in STOCK.rglob("*.cfg") for s in sounds(f.read_text(encoding="latin1"))}
    for i in ids:
        tsv = SERVERS / i / "vsays.tsv"
        if not tsv.is_file():
            print(f"{i}: no vsays.tsv (tools/voicemenu.py)")
            continue
        files = sorted((SERVERS / i / "override").glob("*.cfg"))
        if not files:
            print(f"{i}: no overrides")
            continue
        print(f"{i}: overrides in {', '.join(f.name for f in files)}")
        missing = stale(files, tsv_ids(tsv) | stock)
        for f, n, s in missing:
            print(f"  {f.relative_to(REPO)}:{n}: {s}")
        print(f"  {len(missing)} sound(s) the server no longer has")


def selftest():
    import tempfile
    assert sounds('set vsay2b "vsay_team xy7 ^9No^3!; set cycleVsayTalkKey2 vstr vsay2c"') == ["xy7"]
    assert sounds('set vsay3b "vsay_team 2 xy7 ^9Oops^3!"') == ["xy7"] and sounds('set x "vsay 12 ^lTwelve^3!"') == ["12"]
    assert sounds('// set vsay3 "vsay_team xy8 ^9Old^3!"') == ["xy8"] and sounds('set vsay1 "vsay_buddy -1 0 xy6 ^fGo^3!"') == ["xy6"]
    assert sounds('set vsay4 "vsay Hi ^lHi^3!"') == ["Hi"] and sounds('set vsay4  "vstr cycleVsayGlobalKey4"') == []
    with tempfile.TemporaryDirectory() as d:
        t = Path(d, "vsays.tsv")
        t.write_text("# variant: ...\nvsay\tvariant\tteam\ttext\nxy1\t0\tboth\tHello!\nxy2\t0\tallies\tBye!\n")
        assert tsv_ids(t) == {"xy1", "xy2"}
        c = Path(d, "global.cfg")
        c.write_text('// x\nset vsay4a "vsay Hi ^lHi^3!; set p vstr vsay4b"\nset vsay4b "vsay xy9 ^lHi^3!; set p vstr vsay4a"\n')
        assert stale([c], tsv_ids(t) | {"Hi"}) == [(c, 3, "xy9")]
    print("selftest ok")


if __name__ == "__main__":
    main()
