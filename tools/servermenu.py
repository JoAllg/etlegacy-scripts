#!/usr/bin/env python3
"""Server menu: keeps echo menu pages of the favorite servers up to date while the game runs.

Reads the favorites of the profile from the game's database (<fs_homepath>/etl.db, table client_servers; with
db_mode 0 from <profile>/favcache.json), asks every server for its state and writes the menu pages to
default/servermenu/: p12_<n>.cfg (heading + 12 servers, mods whose popup area the echo menus can enlarge)
and p7_<n>.cfg (heading + 7, all other mods). scripts/servermenu.cfg execs page 0 of the set the mod uses; a page
echoes its servers and binds the number keys to connect, TAB execs the next page (the same one if there is only
one, which refreshes it). A server shows as name, playing humans+spectators+bots/slots, map, ping, mod, the columns
aligned with spaces (the popup font courbd is monospaced). Servers are sorted by playing humans, then spectators and
bots; servers that don't answer come last.

How the servers are asked: tools/helpers/serverapi.py (status). The interval must stay above 2 s (rate limit of the servers).

Usage: tools/servermenu.py [--interval 5] [--once]
       tools/servermenu.py --selftest
"""
import argparse
import time

from helpers.common import strip_colors, write_atomic
from helpers.menupages import EXEC, cells, cut, order, pad, pages, players, table, width
from helpers.serverapi import favorites, status, summarize
from helpers.settings import MENU, PROFILE, REPO

OUT = REPO / PROFILE / "servermenu"
SIZES = (12, 7)  # servers per page: all keys / nitmod's cap of 8 popup lines minus the heading
PING_POLLS = 6  # the ping shown is the lowest of this many polls


def write(files):
    """Replaces the pages; exec reads a page at any time, so every file is swapped in atomically."""
    OUT.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        write_atomic(OUT / name, text)
    for old in OUT.glob("p*_*.cfg"):  # pages of favorites that were removed
        if old.name not in files:
            old.unlink()


def steady(history, rows):
    """Replaces each measured ping by the lowest of the last PING_POLLS polls (history: {address: [ms]}, kept between polls).
    A ping can only be too high (a busy PC or connection reads the answer late, often several at once), never too low."""
    for row in rows:
        if row["ping"] is not None:
            pings = history.setdefault(row["address"], [])
            pings.append(row["ping"])
            del pings[:-PING_POLLS]
            row["ping"] = min(pings)


def update(history):
    rows = list(status(favorites()).values())
    steady(history, rows)
    rows = order(rows)
    stamp = time.strftime("%H:%M:%S")
    files = {}
    for size in SIZES:
        files.update(pages(rows, size, stamp))
    write(files)
    return rows


def selftest():
    etl = summarize("192.0.2.1:27960", {"info": {"hostname": "^1[^7xY^1] FRAGHOUSE ^324MAPS ^2NOL", "mapname": "radar", "clients": "19", "humans": "17", "sv_maxclients": "40", "game": "nitmod"}, "rtt": 48})
    old = summarize("192.0.2.2:27960", {"status": {"sv_hostname": 'Old "Server"; x', "mapname": "oasis", "gamename": "jaymod", "sv_maxclients": "32"}, "pings": [0, 48, 0, 999]})
    off = summarize("192.0.2.3:27960", None)
    split = summarize("192.0.2.4:27960", {"info": {"clients": "3", "humans": "2", "sv_maxclients": "40", "game": "nitmod"}, "status": {"P": "1-32", "sv_hostname": "x"}, "pings": [40, 70, 0], "rtt": 5})
    assert cells(off)[1] == "offline"

    assert cut("^1[^7xY^1] FRAGHOUSE ^324MAPS ^2NOLAGS") == "^1[^7xY^1] FRAGHOUSE ^324MAPS ^2NO"  # 24 visible characters
    assert cut("abc^", 10) == "abc" and cut('a"b;c', 10) == "a'b,c" and cut("  ^7x  ", 10) == "^7x"
    assert width("^1ab^7c") == 3 and pad("^1a", 3) == "^1a  "
    m, t = MENU, MENU["text"]
    assert cells(split)[1] == ["1", "1", "1", "40"] and cells(etl)[1] == ["17", "", "2", "40"]
    assert players(["1", "1", "1", "40"], [2, 1, 2, 2]) == f"{m['playing']} 1{t}+{m['spec']}1{t}+{m['bots']} 1{t}/40"
    assert players(["17", "", "2", ""], [2, 1, 1, 2]) == f"{t}17{t} {m['spec']} {t}+{m['bots']}2{t}   "
    lines = table([split, etl, off])
    assert len({width(l[:l.index("ms") + 2]) for l in lines[:2]}) == 1  # name, players, map and ping end in the same column
    assert lines[0].endswith("5ms  nitmod") and lines[1].endswith("48ms  nitmod") 
    plain = [strip_colors(x) for x in lines]
    assert plain[2].endswith("offline") and plain[2].index("offline") == plain[0].index(" 1+1+1/40") == plain[1].index("17  +2/40")
    assert '"' not in table([old])[0] and ";" not in table([old])[0]

    rows = order([off, old, etl])
    assert [r["address"] for r in rows] == ["192.0.2.1:27960", "192.0.2.2:27960", "192.0.2.3:27960"]
    many = order([dict(etl, address=f"192.0.2.{n}:27960", playing=n) for n in range(15)])
    p12, p7 = pages(many, 12, "12:00:00"), pages(many, 7, "12:00:00")
    assert sorted(p12) == ["p12_0.cfg", "p12_1.cfg"] and sorted(p7) == ["p7_0.cfg", "p7_1.cfg", "p7_2.cfg"]
    first = p12["p12_0.cfg"].splitlines()
    assert first[1] == "vstr popupsMenu" and "SERVERS 1/2 12:00:00" in first[2] and "TAB next page" in first[2]
    assert sum(l.startswith("echo") for l in first) == 13 and sum(l.startswith("echo") for l in p7["p7_0.cfg"].splitlines()) == 8
    assert 'bind 1 "vstr resetLayers; connect 192.0.2.14:27960"' in first  # most playing humans first
    assert 'bind US_EQUALS "vstr resetLayers; connect 192.0.2.3:27960"' in first
    assert first[3].startswith(f'echo "{m["key"]}1.  {t}') and first[14].startswith(f'echo "{m["key"]}12. {t}')  # keys 1-12 equally wide
    assert first[-1] == f'bind TAB "execq {EXEC}/p12_1.cfg"' and first.index("vstr unbindNumbers") < first.index(first[-1])
    assert p12["p12_1.cfg"].splitlines()[-1] == f'bind TAB "execq {EXEC}/p12_0.cfg"'  # last page wraps
    assert 'bind 4 ' not in p12["p12_1.cfg"] and 'echo "' + m["key"] + "3. " in p12["p12_1.cfg"]
    one = pages(many[:3], 7, "12:00:00")["p7_0.cfg"]
    assert "TAB refresh" in one and one.splitlines()[-1] == f'bind TAB "execq {EXEC}/p7_0.cfg"'
    empty = pages([], 7, "12:00:00")
    assert list(empty) == ["p7_0.cfg"] and "No favorite servers" in empty["p7_0.cfg"]
    history, a = {}, "192.0.2.1:27960"
    for ms, shown in ((300, 300), (40, 40), (320, 40)):
        rows = [{"address": a, "ping": ms}, {"address": "off", "ping": None}]
        steady(history, rows)
        assert rows[0]["ping"] == shown and rows[1]["ping"] is None
    for ms in range(100, 100 + PING_POLLS):
        steady(history, [{"address": a, "ping": ms}])
    assert history == {a: list(range(100, 100 + PING_POLLS))}  # older pings drop out
    print("selftest ok")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--interval", type=float, default=5, help="seconds between two updates (default 5, at least 2)")
    ap.add_argument("--once", action="store_true", help="update once, print the servers and exit")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.once:
        rows = update({})
        for n, (text, row) in enumerate(zip(table(rows), rows), 1):
            print(f"{n:2}. {text}  {row['address']}")
        return
    print(f"Server menu: favorites of profile '{PROFILE}' -> {OUT} every {max(a.interval, 2):g} s (Ctrl+C stops)")
    history = {}
    try:
        while True:
            start = time.monotonic()
            update(history)
            time.sleep(max(0.0, max(a.interval, 2) - (time.monotonic() - start)))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
