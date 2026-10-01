#!/usr/bin/env python3
"""Server menu: keeps echo menu pages of the favorite servers up to date while the game runs.

Reads the favorites of the profile from the game's database (<fs_homepath>/etl.db, table client_servers; with
db_mode 0 from <profile>/favcache.json), asks every server for its state and writes the menu pages to
default/scripts/servers/: p12_<n>.cfg (heading + 12 servers, mods whose popup area the echo menus can enlarge)
and p7_<n>.cfg (heading + 7, all other mods). scripts/servermenu.cfg execs page 0 of the set the mod uses; a page
echoes its servers and binds the number keys to connect, TAB execs the next page (the same one if there is only
one, which refreshes it). A server shows as name, playing humans+spectators+bots/slots, map, ping, mod, the columns
aligned with spaces (the popup font courbd is monospaced). Servers are sorted by playing humans, then spectators and
bots; servers that don't answer come last.

Query (same as the game's server browser, src/server/sv_main.c SVC_Info / SVC_Status): the UDP packets
"\\xff\\xff\\xff\\xffgetinfo" and "...getstatus" to the game port.
- humans and bots: the "humans" key of getinfo (servers on the ET: Legacy engine, any mod), else the players of
  getstatus minus those with ping 0 (bots). Teams: the slot string P of getstatus (1 axis, 2 allies, 3 spectator,
  0 connecting); team players minus bots are the playing humans. Without P only humans and bots are shown. omnibot_playing is not used: nitmod servers report 0 or -1 with bots playing
- ET: Legacy servers answer one packet per second per address after a burst of 10, so the interval must stay above 2 s

Usage: tools/servermenu.py [--interval 5] [--once]
       tools/servermenu.py --selftest
"""
import argparse
import json
import os
import re
import socket
import sqlite3
import time

from settings import HOMEPATH, MENU, PROFILE, REPO

OUT = REPO / PROFILE / "scripts/servers"
EXEC = "profile/scripts/servers"  # the profile link of deploy.sh in each mod folder
DB = HOMEPATH / "etl.db"
KEYS = ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "US_MINUS", "US_EQUALS")
SIZES = (12, 7)  # servers per page: all keys / nitmod's cap of 8 popup lines minus the heading
NAME_LEN = 24
MAP_LEN = 16
TIMEOUT = 1.5
PING_POLLS = 6  # the ping shown is the lowest of this many polls


def favorites():
    """[address] of the profile's favorites, in the order they were added."""
    try:
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=1)
        try:
            return [r[0] for r in con.execute("SELECT address FROM client_servers WHERE profile = ? ORDER BY created", (PROFILE,))]
        finally:
            con.close()
    except sqlite3.Error:
        pass
    try:
        return [s["address"] for s in json.loads((REPO / PROFILE / "favcache.json").read_text("latin1"))]
    except (OSError, ValueError, KeyError, TypeError):
        return []


def resolve(address):
    """(ip, port) of "host[:port]", None if it doesn't resolve."""
    # ponytail: IPv4 only, the favorites of the browser are stored as ip:port; add "[v6]:port" parsing when one shows up
    host, _, port = address.partition(":")
    try:
        return socket.gethostbyname(host), int(port or 27960)
    except (OSError, ValueError):
        return None


def info_dict(line):
    r"""{key: value} of an info string (\key\value\key\value)."""
    parts = line.split("\\")[1:]
    return dict(zip(parts[::2], parts[1::2]))


def parse(packet):
    """("info" | "status", {key: value}, [player ping]) of a response packet, None for anything else."""
    lines = packet[4:].decode("latin1").split("\n")
    kind = {"infoResponse": "info", "statusResponse": "status"}.get(lines[0].strip())
    if not packet.startswith(b"\xff\xff\xff\xff") or not kind or len(lines) < 2:
        return None
    pings = []
    for player in lines[2:]:  # score ping "name"
        fields = player.split(" ", 2)
        if len(fields) == 3 and fields[1].lstrip("-").isdigit():
            pings.append(int(fields[1]))
    return kind, info_dict(lines[1]), pings


def query(addrs):
    """{addr: {"info": {...}, "status": {...}, "pings": [...], "rtt": ms}} of the servers that answered."""
    out = {}
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        start, sent = time.monotonic(), {}
        for addr in addrs:
            sent[addr] = time.monotonic()
            for cmd in (b"getinfo xxx", b"getstatus"):
                try:
                    sock.sendto(b"\xff\xff\xff\xff" + cmd, addr)
                except OSError:
                    pass
        missing = 2 * len(set(addrs))
        while missing > 0:
            left = start + TIMEOUT - time.monotonic()
            if left <= 0:
                break
            sock.settimeout(left)
            try:
                packet, addr = sock.recvfrom(65535)
            except OSError:
                break
            parsed = parse(packet)
            if not parsed or addr not in addrs:
                continue
            kind, info, pings = parsed
            server = out.setdefault(addr, {})
            if kind not in server:
                missing -= 1
            server[kind] = info
            if kind == "status":
                server["pings"] = pings
            else:
                server["rtt"] = round((time.monotonic() - sent[addr]) * 1000)
    finally:
        sock.close()
    return out


def num(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def teams(slots, bots):
    """(playing humans, spectators) from the slot string P of getstatus, None without P.

    P has one character per client slot (legacy src/game/g_main.c etpro_PlayerInfo): 1 axis, 2 allies, 3 spectator,
    0 connecting (counted as spectator), - free. Bots play, so they are taken from the team players. P is counted on its
    own instead of matching it to the player lines: while a player joins or leaves, the two can differ by one."""
    if not slots.strip("-"):
        return None
    return max(sum(c in "12" for c in slots) - bots, 0), sum(c in "30" for c in slots)


def summarize(address, answer):
    """Row of a server: name, mod, map, playing humans, spectators (None without P), bots, slots, ping;
    playing None if the server is offline."""
    row = {"address": address, "name": address, "playing": None, "spec": None, "bots": 0, "slots": None, "mod": "", "map": "", "ping": None}
    if not answer:
        return row
    info, status, pings = answer.get("info", {}), answer.get("status", {}), answer.get("pings")
    total = num(info.get("clients"))
    if total is None:
        total = len(pings or [])
    humans = num(info.get("humans"))
    if humans is None:
        humans = total - sum(p == 0 for p in pings) if pings is not None else total
    bots = max(total - humans, 0)
    split = teams(status.get("P", ""), bots)
    playing, spec = split if split else (humans, None)
    slots = num(info.get("sv_maxclients"))
    if slots is None and num(status.get("sv_maxclients")) is not None:
        slots = num(status["sv_maxclients"]) - (num(status.get("sv_privateClients")) or 0)
    row.update(name=info.get("hostname") or status.get("sv_hostname") or address, playing=playing, spec=spec, bots=bots,
               slots=slots, mod=info.get("game") or status.get("gamename") or "etmain",
               map=info.get("mapname") or status.get("mapname") or "", ping=answer.get("rtt"))
    return row


def clean(text):
    """Text that is safe inside a quoted cfg command: no quote, no command separator, printable latin1 only."""
    text = text.replace('"', "'").replace(";", ",")
    return "".join(c for c in text if 32 <= ord(c) < 256 and ord(c) != 127)


def cut(name, length=NAME_LEN):
    """Name with its color codes, cut to `length` visible characters."""
    out, visible, i = "", 0, 0
    name = clean(name).strip()
    while i < len(name) and visible < length:
        if name[i] == "^" and i + 1 < len(name) and name[i + 1] != "^":
            out += name[i:i + 2]
            i += 2
            continue
        out += name[i]
        visible += 1
        i += 1
    return out.rstrip().rstrip("^")  # a trailing ^ would swallow the color code that follows


def width(text):
    """Visible characters of a text with color codes."""
    return len(re.sub(r"\^[^^]", "", text))


def pad(text, size):
    return text + " " * (size - width(text))


def cells(row):
    """[name, players, map, ping, mod] of a row; players as [playing, spectators, bots, slots] ("" if unknown), or "offline"."""
    name = cut(row["name"]) + MENU["text"]
    if row["playing"] is None:
        return [name, "offline", "", "", ""]
    numbers = [row["playing"], row["spec"], row["bots"], row["slots"]]
    ping = f"{row['ping']}ms" if row["ping"] is not None else ""
    return [name, ["" if n is None else str(n) for n in numbers], clean(row["map"])[:MAP_LEN], ping, clean(row["mod"])]


def players(numbers, sizes):
    """playing+spectators+bots/slots, every number right-aligned in its own column so the last digits line up;
    playing humans colored only when the spectators are known (without P they are all humans)."""
    t = MENU["text"]
    playing, spec, bots, slots = (n.rjust(size) for n, size in zip(numbers, sizes))
    colored = MENU["playing"] if numbers[1] else t
    text = f"{colored}{playing}{t}{'+' if numbers[1] else ' '}{MENU['spec']}{spec}{t}+{MENU['bots']}{bots}{t}"
    return text + (f"/{slots}" if numbers[3] else " " * (sizes[3] + 1))


def table(rows):
    """Lines of the rows with the columns aligned by spaces: the popup font (courbd) is monospaced."""
    grid = [cells(r) for r in rows]
    numbers = [c[1] for c in grid if isinstance(c[1], list)]
    digits = [max((len(n[i]) for n in numbers), default=0) for i in range(4)]
    for c in grid:
        if isinstance(c[1], list):
            c[1] = players(c[1], digits)
    sizes = [max((width(c[i]) for c in grid), default=0) for i in range(5)]
    out = []
    for c in grid:
        ping = " " * (sizes[3] - width(c[3])) + c[3]  # right-aligned
        out.append("  ".join([pad(c[0], sizes[0]), pad(c[1], sizes[1]), pad(c[2], sizes[2]), ping, c[4]]).rstrip())
    return out


def order(rows):
    return sorted(rows, key=lambda r: (r["playing"] is None, -(r["playing"] or 0), -(r["spec"] or 0), -r["bots"]))


def pages(rows, size, stamp):
    """{file name: cfg text} of one page set; the columns are aligned over all pages."""
    count = max(1, -(-len(rows) // size))
    lines = table(rows)
    out = {}
    for page in range(count):
        part = rows[page * size:(page + 1) * size]
        of = f" {page + 1}/{count}" if count > 1 else ""
        tab = "next page" if count > 1 else "refresh"
        cfg = ["// Generated by tools/servermenu.py, rewritten every few seconds while it runs", "vstr popupsMenu",
               f'echo "{MENU["head"]}SERVERS{of} {stamp} {MENU["nav"]}TAB {tab}{MENU["head"]}:"']
        if not rows:
            cfg.append(f'echo "{MENU["text"]}No favorite servers: add some in the server browser"')
        cfg += [f'echo "{MENU["key"]}{f"{n}.":<4}{MENU["text"]}{text}"' for n, text in enumerate(lines[page * size:(page + 1) * size], 1)]
        cfg.append("vstr unbindNumbers")
        cfg += [f'bind {key} "vstr resetServerMenu; connect {row["address"]}"' for key, row in zip(KEYS, part)]
        cfg.append(f'bind TAB "exec {EXEC}/p{size}_{(page + 1) % count}.cfg"')
        out[f"p{size}_{page}.cfg"] = "\n".join(cfg) + "\n"
    return out


def write(files):
    """Replaces the pages; exec reads a page at any time, so every file is swapped in atomically."""
    OUT.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        tmp = OUT / (name + ".tmp")
        tmp.write_text(text, "latin1")
        os.replace(tmp, OUT / name)
    for old in OUT.glob("p*_*.cfg"):  # pages of favorites that were removed
        if old.name not in files:
            old.unlink()


def steady(history, answers):
    """Replaces each measured ping by the lowest of the last PING_POLLS polls (history: {addr: [ms]}, kept between polls).
    A ping can only be too high (a busy PC or connection reads the answer late, often several at once), never too low."""
    for addr, answer in answers.items():
        if answer.get("rtt") is not None:
            pings = history.setdefault(addr, [])
            pings.append(answer["rtt"])
            del pings[:-PING_POLLS]
            answer["rtt"] = min(pings)


def update(history):
    addresses = favorites()
    addrs = {a: resolve(a) for a in addresses}
    answers = query([addr for addr in addrs.values() if addr])
    steady(history, answers)
    rows = order([summarize(a, answers.get(addrs[a])) for a in addresses])
    stamp = time.strftime("%H:%M:%S")
    files = {}
    for size in SIZES:
        files.update(pages(rows, size, stamp))
    write(files)
    return rows


def selftest():
    info = b'\xff\xff\xff\xffinfoResponse\n\\challenge\\xxx\\hostname\\^1[^7eG^1] BEGINNERS ^350MAPS ^2XPS\\mapname\\radar\\clients\\19\\humans\\17\\sv_maxclients\\40\\game\\nitmod'
    status = b'\xff\xff\xff\xffstatusResponse\n\\sv_hostname\\Old "Server"; x\\mapname\\oasis\\gamename\\jaymod\\sv_maxclients\\32\\sv_privateClients\\2\n0 0 "^o[BOT]^7Bean"\n12 48 "Pl ayer"\n3 0 "Bot"\n-5 999 "Joining"\n'
    assert parse(b"\xff\xff\xff\xffprint\nhi") is None and parse(b"garbage") is None
    kind, kv, pings = parse(info)
    assert kind == "info" and kv["humans"] == "17" and pings == []
    kind, kv, pings = parse(status)
    assert kind == "status" and kv["gamename"] == "jaymod" and pings == [0, 48, 0, 999]

    etl = summarize("1.2.3.4:27960", {"info": parse(info)[1], "status": {}, "pings": [0] * 5 + [50] * 14, "rtt": 48})
    assert (etl["playing"], etl["spec"], etl["bots"], etl["slots"], etl["mod"], etl["map"]) == (17, None, 2, 40, "nitmod", "radar")  # humans key wins over pings
    old = summarize("5.6.7.8:27960", {"status": kv, "pings": pings})
    assert (old["playing"], old["spec"], old["bots"], old["slots"], old["mod"], old["ping"]) == (2, None, 2, 30, "jaymod", None)  # ping 0 = bot
    off = summarize("9.9.9.9:27960", None)
    assert off["playing"] is None and cells(off)[1] == "offline"

    assert teams("-1-30-2", 1) == (1, 2) and teams("--", 0) is None and teams("", 0) is None and teams("3", 2) == (0, 1)
    split = summarize("2.2.2.2:27960", {"info": {"clients": "3", "humans": "2", "sv_maxclients": "40", "game": "nitmod"}, "status": {"P": "1-32", "sv_hostname": "x"}, "pings": [40, 70, 0], "rtt": 5})
    assert (split["playing"], split["spec"], split["bots"]) == (1, 1, 1)
    joining = summarize("3.3.3.3:27960", {"info": {"clients": "4", "humans": "4"}, "status": {"P": "1-32"}, "pings": [40, 70, 30, 999]})
    assert (joining["playing"], joining["spec"], joining["bots"]) == (2, 1, 0)  # P one behind the player lines: split kept

    assert cut("^1[^7eG^1] BEGINNERS ^350MAPS ^2XPSAVE") == "^1[^7eG^1] BEGINNERS ^350MAPS ^2XP"  # 24 visible characters
    assert cut("abc^", 10) == "abc" and cut('a"b;c', 10) == "a'b,c" and cut("  ^7x  ", 10) == "^7x"
    assert width("^1ab^7c") == 3 and pad("^1a", 3) == "^1a  "
    m, t = MENU, MENU["text"]
    assert cells(split)[1] == ["1", "1", "1", "40"] and cells(etl)[1] == ["17", "", "2", "40"]
    assert players(["1", "1", "1", "40"], [2, 1, 2, 2]) == f"{m['playing']} 1{t}+{m['spec']}1{t}+{m['bots']} 1{t}/40"
    assert players(["17", "", "2", ""], [2, 1, 1, 2]) == f"{t}17{t} {m['spec']} {t}+{m['bots']}2{t}   "
    lines = table([split, etl, off])
    assert len({width(l[:l.index("ms") + 2]) for l in lines[:2]}) == 1  # name, players, map and ping end in the same column
    assert lines[0].endswith("5ms  nitmod") and lines[1].endswith("48ms  nitmod") 
    plain = [re.sub(r"\^[^^]", "", x) for x in lines]
    assert plain[2].endswith("offline") and plain[2].index("offline") == plain[0].index(" 1+1+1/40") == plain[1].index("17  +2/40")
    assert '"' not in table([old])[0] and ";" not in table([old])[0]

    rows = order([off, old, etl])
    assert [r["address"] for r in rows] == ["1.2.3.4:27960", "5.6.7.8:27960", "9.9.9.9:27960"]
    many = order([dict(etl, address=f"1.1.1.{n}:27960", playing=n) for n in range(15)])
    p12, p7 = pages(many, 12, "12:00:00"), pages(many, 7, "12:00:00")
    assert sorted(p12) == ["p12_0.cfg", "p12_1.cfg"] and sorted(p7) == ["p7_0.cfg", "p7_1.cfg", "p7_2.cfg"]
    first = p12["p12_0.cfg"].splitlines()
    assert first[1] == "vstr popupsMenu" and "SERVERS 1/2 12:00:00" in first[2] and "TAB next page" in first[2]
    assert sum(l.startswith("echo") for l in first) == 13 and sum(l.startswith("echo") for l in p7["p7_0.cfg"].splitlines()) == 8
    assert 'bind 1 "vstr resetServerMenu; connect 1.1.1.14:27960"' in first  # most playing humans first
    assert 'bind US_EQUALS "vstr resetServerMenu; connect 1.1.1.3:27960"' in first
    assert first[3].startswith(f'echo "{m["key"]}1.  {t}') and first[14].startswith(f'echo "{m["key"]}12. {t}')  # keys 1-12 equally wide
    assert first[-1] == f'bind TAB "exec {EXEC}/p12_1.cfg"' and first.index("vstr unbindNumbers") < first.index(first[-1])
    assert p12["p12_1.cfg"].splitlines()[-1] == f'bind TAB "exec {EXEC}/p12_0.cfg"'  # last page wraps
    assert 'bind 4 ' not in p12["p12_1.cfg"] and 'echo "' + m["key"] + "3. " in p12["p12_1.cfg"]
    one = pages(many[:3], 7, "12:00:00")["p7_0.cfg"]
    assert "TAB refresh" in one and one.splitlines()[-1] == f'bind TAB "exec {EXEC}/p7_0.cfg"'
    empty = pages([], 7, "12:00:00")
    assert list(empty) == ["p7_0.cfg"] and "No favorite servers" in empty["p7_0.cfg"]
    assert resolve("1.2.3.4:27961") == ("1.2.3.4", 27961) and resolve("1.2.3.4") == ("1.2.3.4", 27960) and resolve("1.2.3.4:x") is None
    history, a = {}, ("1.2.3.4", 27960)
    for ms, shown in ((300, 300), (40, 40), (320, 40)):
        answers = {a: {"rtt": ms}}
        steady(history, answers)
        assert answers[a]["rtt"] == shown
    for ms in range(100, 100 + PING_POLLS):
        steady(history, {a: {"rtt": ms}})
    assert history[a] == list(range(100, 100 + PING_POLLS))  # older pings drop out
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
