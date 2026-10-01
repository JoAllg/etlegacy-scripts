#!/usr/bin/env python3
"""Server menu: keeps echo menu pages of the favorite servers up to date while the game runs.

Reads the favorites of the profile from the game's database (<fs_homepath>/etl.db, table client_servers; with
db_mode 0 from <profile>/favcache.json), asks every server for its state and writes the menu pages to
default/scripts/servers/: p12_<n>.cfg (heading + 12 servers, mods whose popup area the echo menus can enlarge)
and p7_<n>.cfg (heading + 7, all other mods). scripts/servermenu.cfg execs page 0 of the set the mod uses; a page
echoes its servers and binds the number keys to connect, TAB execs the next page (the same one if there is only
one, which refreshes it). Servers are sorted by humans, then players; servers that don't answer come last.

Query (same as the game's server browser, src/server/sv_main.c SVC_Info / SVC_Status): the UDP packets
"\\xff\\xff\\xff\\xffgetinfo" and "...getstatus" to the game port.
- humans: the "humans" key of getinfo (servers on the ET: Legacy engine, any mod); without it the players of
  getstatus minus those with ping 0 (bots). omnibot_playing is not used: nitmod servers report 0 or -1 with bots playing
- ET: Legacy servers answer one packet per second per address after a burst of 10, so the interval must stay above 2 s

Usage: tools/servermenu.py [--interval 5] [--once]
       tools/servermenu.py --selftest
"""
import argparse
import json
import os
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
TIMEOUT = 1.5


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
        start = time.monotonic()
        for addr in addrs:
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
                server["rtt"] = round((time.monotonic() - start) * 1000)
    finally:
        sock.close()
    return out


def num(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def summarize(address, answer):
    """Row of a server: name, mod, map, humans, bots, slots, ping; humans None if the server is offline."""
    row = {"address": address, "name": address, "humans": None, "bots": 0, "slots": None, "mod": "", "map": "", "ping": None}
    if not answer:
        return row
    info, status, pings = answer.get("info", {}), answer.get("status", {}), answer.get("pings")
    total = num(info.get("clients"))
    if total is None:
        total = len(pings or [])
    humans = num(info.get("humans"))
    if humans is None:
        humans = total - sum(p == 0 for p in pings) if pings is not None else total
    slots = num(info.get("sv_maxclients"))
    if slots is None and num(status.get("sv_maxclients")) is not None:
        slots = num(status["sv_maxclients"]) - (num(status.get("sv_privateClients")) or 0)
    row.update(name=info.get("hostname") or status.get("sv_hostname") or address, humans=humans, bots=max(total - humans, 0),
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


def line(row):
    if row["humans"] is None:
        return f"offline  {cut(row['name'])}"
    slots = f"/{row['slots']}" if row["slots"] is not None else ""
    ping = f"  {row['ping']}ms" if row["ping"] is not None else ""
    return f"{row['humans']}+{row['bots']}{slots}  {cut(row['name'])}{MENU['text']}  {clean(row['mod'])}  {clean(row['map'])}{ping}"


def order(rows):
    return sorted(rows, key=lambda r: (r["humans"] is None, -(r["humans"] or 0), -r["bots"]))


def pages(rows, size, stamp):
    """{file name: cfg text} of one page set."""
    count = max(1, -(-len(rows) // size))
    out = {}
    for page in range(count):
        part = rows[page * size:(page + 1) * size]
        of = f" {page + 1}/{count}" if count > 1 else ""
        tab = "next page" if count > 1 else "refresh"
        cfg = ["// Generated by tools/servermenu.py, rewritten every few seconds while it runs", "vstr popupsMenu",
               f'echo "{MENU["head"]}SERVERS{of} {stamp} {MENU["nav"]}TAB {tab}{MENU["head"]}:"']
        if not rows:
            cfg.append(f'echo "{MENU["text"]}No favorite servers: add some in the server browser"')
        cfg += [f'echo "{MENU["key"]}{n}. {MENU["text"]}{line(row)}"' for n, row in enumerate(part, 1)]
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


def update():
    addresses = favorites()
    addrs = {a: resolve(a) for a in addresses}
    answers = query([addr for addr in addrs.values() if addr])
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
    assert (etl["humans"], etl["bots"], etl["slots"], etl["mod"], etl["map"]) == (17, 2, 40, "nitmod", "radar")  # humans key wins over pings
    old = summarize("5.6.7.8:27960", {"status": kv, "pings": pings})
    assert (old["humans"], old["bots"], old["slots"], old["mod"], old["ping"]) == (2, 2, 30, "jaymod", None)  # ping 0 = bot
    off = summarize("9.9.9.9:27960", None)
    assert off["humans"] is None and line(off) == "offline  9.9.9.9:27960"

    assert cut("^1[^7eG^1] BEGINNERS ^350MAPS ^2XPSAVE") == "^1[^7eG^1] BEGINNERS ^350MAPS ^2XP"  # 24 visible characters
    assert cut("abc^", 10) == "abc" and cut('a"b;c', 10) == "a'b,c" and cut("  ^7x  ", 10) == "^7x"
    assert '"' not in line(old) and ";" not in line(old)
    assert line(etl).startswith("17+2/40  ^1[^7eG") and line(etl).endswith("nitmod  radar  48ms")

    rows = order([off, old, etl])
    assert [r["address"] for r in rows] == ["1.2.3.4:27960", "5.6.7.8:27960", "9.9.9.9:27960"]
    many = order([dict(etl, address=f"1.1.1.{n}:27960", humans=n) for n in range(15)])
    p12, p7 = pages(many, 12, "12:00:00"), pages(many, 7, "12:00:00")
    assert sorted(p12) == ["p12_0.cfg", "p12_1.cfg"] and sorted(p7) == ["p7_0.cfg", "p7_1.cfg", "p7_2.cfg"]
    first = p12["p12_0.cfg"].splitlines()
    assert first[1] == "vstr popupsMenu" and "SERVERS 1/2 12:00:00" in first[2] and "TAB next page" in first[2]
    assert sum(l.startswith("echo") for l in first) == 13 and sum(l.startswith("echo") for l in p7["p7_0.cfg"].splitlines()) == 8
    assert 'bind 1 "vstr resetServerMenu; connect 1.1.1.14:27960"' in first  # most humans first
    assert 'bind US_EQUALS "vstr resetServerMenu; connect 1.1.1.3:27960"' in first
    assert first[-1] == f'bind TAB "exec {EXEC}/p12_1.cfg"' and first.index("vstr unbindNumbers") < first.index(first[-1])
    assert p12["p12_1.cfg"].splitlines()[-1] == f'bind TAB "exec {EXEC}/p12_0.cfg"'  # last page wraps
    assert 'bind 4 ' not in p12["p12_1.cfg"] and 'echo "' + MENU["key"] + "3. " in p12["p12_1.cfg"]
    one = pages(many[:3], 7, "12:00:00")["p7_0.cfg"]
    assert "TAB refresh" in one and one.splitlines()[-1] == f'bind TAB "exec {EXEC}/p7_0.cfg"'
    empty = pages([], 7, "12:00:00")
    assert list(empty) == ["p7_0.cfg"] and "No favorite servers" in empty["p7_0.cfg"]
    assert resolve("1.2.3.4:27961") == ("1.2.3.4", 27961) and resolve("1.2.3.4") == ("1.2.3.4", 27960) and resolve("1.2.3.4:x") is None
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
        for n, row in enumerate(update(), 1):
            print(f"{n:2}. {line(row)}  {row['address']}")
        return
    print(f"Server menu: favorites of profile '{PROFILE}' -> {OUT} every {max(a.interval, 2):g} s (Ctrl+C stops)")
    try:
        while True:
            start = time.monotonic()
            update()
            time.sleep(max(0.0, max(a.interval, 2) - (time.monotonic() - start)))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
