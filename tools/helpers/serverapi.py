#!/usr/bin/env python3
"""Server API: the one place where the tools talk to game servers and tell which server is which.

Query (same as the game's server browser, src/server/sv_main.c SVC_Info / SVC_Status): the UDP packets
"\\xff\\xff\\xff\\xffgetinfo" and "...getstatus" to the game port; status(addresses) returns one row per server.
- humans and bots: the "humans" key of getinfo (servers on the ET: Legacy engine, any mod), else the players of
  getstatus minus those with ping 0 (bots). Teams: the slot string P of getstatus (1 axis, 2 allies, 3 spectator,
  0 connecting); team players minus bots are the playing humans. Without P only humans and bots are known. omnibot_playing is not used: nitmod servers report 0 or -1 with bots playing
- ET: Legacy servers answer one packet per second per address after a burst of 10, so a poll interval must stay above 2 s

Identity: default/serverconfigs/servers.tsv (user-maintained, "<id><TAB><text>[<TAB><mod>[<TAB><addresses>]]") names
the servers that have settings or a voice chat of their own. A row matches a server whose name contains the text
(colors ignored, any case) and, if the row names a mod, whose gamename is that mod; the first matching row wins, so
one clan tag covers all servers of a clan. The addresses (ip:port, comma-separated) only record the servers a row
matched, they play no part in the match. history.tsv next to it remembers the name
and mod ("<ip:port><TAB><name><TAB><mod>") of every server the game connected to, so a server is recognized without
asking it again.

Usage: tools/helpers/serverapi.py <address> ...   (prints name, id, mod, map, players, ping)
       tools/helpers/serverapi.py --selftest
"""
import argparse
import collections
import contextlib
import io
import json
import re
import select
import socket
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tools/: this module also runs as a command
from helpers.common import COLOR, clean, strip_colors, write_atomic  # noqa: E402
from helpers.settings import HOMEPATH, PROFILE, REPO  # noqa: E402

DB = HOMEPATH / "etl.db"
CONFIGS = REPO / PROFILE / "serverconfigs"
SERVERS = CONFIGS / "servers.tsv"
HISTORY = CONFIGS / "history.tsv"
ID = re.compile(r"(?!(?:default|local|current|current_vsay)$)[a-z0-9_]{1,16}")  # part of a file name and of an alias
# name; not the name of another file of serverconfigs/
ID_RULE = "1 to 16 characters of a-z, 0-9, _, not default, local, current, current_vsay"
Row = collections.namedtuple("Row", "id text mod addresses", defaults=("", ()))
TIMEOUT = 1.5


def favorites():
    """{address: name} of the profile's favorites, in the order they were added; the name as the server browser saw
    it last (cut to about 32 characters, "" if never seen)."""
    try:
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=1)
        try:
            return {a: n or "" for a, n in con.execute("SELECT address, name FROM client_servers WHERE profile = ? ORDER BY created", (PROFILE,))}
        finally:
            con.close()
    except sqlite3.Error:
        pass
    try:
        return {s["address"]: s.get("name") or "" for s in json.loads((REPO / PROFILE / "favcache.json").read_text("latin1"))}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return {}


def resolve(address):
    """(ip, port) of "host[:port]", "[ipv6][:port]" or a bare IPv6 address, None if it doesn't resolve."""
    # ponytail: a host name resolves to IPv4 only and a link-local scope ("%eth0") is dropped; use getaddrinfo's full
    # answer when a server is reachable no other way
    m = re.fullmatch(r"\[([^\]]+)\](?::(\d*))?", address)
    v6 = m or address.count(":") > 1
    host, port = (m.group(1), m.group(2)) if m else (address, "") if v6 else address.partition(":")[::2]
    try:
        if v6:
            return socket.getaddrinfo(host, None, socket.AF_INET6, flags=socket.AI_NUMERICHOST)[0][4][0], int(port or 27960)
        return socket.gethostbyname(host), int(port or 27960)
    except (OSError, ValueError):
        return None


def adr_string(addr):
    """(ip, port) as the game logs a connect: "ip:port", IPv6 "[ip]:port" (src/qcommon/net_ip.c NET_AdrToString)."""
    return ("[%s]:%d" if ":" in addr[0] else "%s:%d") % addr


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


def query(addrs, cmds=(b"getinfo xxx", b"getstatus")):
    """{addr: {"info": {...}, "status": {...}, "pings": [...], "rtt": ms}} of the servers that answered; one packet
    per command and server."""
    out, socks = {}, {}  # one socket per address family in use
    try:
        start, sent = time.monotonic(), {}
        for addr in addrs:
            sent[addr] = time.monotonic()
            family = socket.AF_INET6 if ":" in addr[0] else socket.AF_INET
            for cmd in cmds:
                try:
                    if family not in socks:
                        socks[family] = socket.socket(family, socket.SOCK_DGRAM)
                    socks[family].sendto(b"\xff\xff\xff\xff" + cmd, addr)
                except OSError:  # e.g. no IPv6 on this machine: the server counts as not answering
                    pass
        missing = len(cmds) * len(set(addrs))
        while missing > 0 and socks:
            left = start + TIMEOUT - time.monotonic()
            if left <= 0:
                break
            try:
                ready = select.select(list(socks.values()), [], [], left)[0]
                answers = [sock.recvfrom(65535) for sock in ready]
            except OSError:
                break
            if not ready:
                break
            for packet, addr in answers:
                parsed, addr = parse(packet), addr[:2]  # IPv6 adds flow info and scope
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
        for sock in socks.values():
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
    """Row of a server: name, hostname (as the server sends it, "" if unknown), mod, map, playing humans,
    spectators (None without P), bots, slots, ping; playing None if the server is offline."""
    row = {"address": address, "name": address, "hostname": "", "playing": None, "spec": None, "bots": 0, "slots": None,
           "mod": "", "map": "", "ping": None}
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
    hostname = info.get("hostname") or status.get("sv_hostname") or ""
    row.update(name=hostname or address, hostname=hostname, playing=playing, spec=spec, bots=bots,
               slots=slots, mod=info.get("game") or status.get("gamename") or "etmain",
               map=info.get("mapname") or status.get("mapname") or "", ping=answer.get("rtt"))
    return row


def status(addresses, path=HISTORY, names=None):
    """{address: row (summarize)} of the servers "host[:port]", asked at once; one that doesn't answer is offline,
    named from the history if the game was on it before, else from `names` ({address: name}, e.g. favorites())."""
    addrs = {a: resolve(a) for a in addresses}
    answers = query([addr for addr in addrs.values() if addr])
    retry = [addr for addr, answer in answers.items() if "status" not in answer]  # dropped by a busy server's rate limit
    for addr, answer in query(retry, (b"getstatus",)).items() if retry else ():
        answers[addr].update(answer)
    known = history(path)
    rows = {a: summarize(a, answers.get(addrs[a])) for a in addresses}
    for a, row in rows.items():
        if row["playing"] is None and addrs[a]:
            row["name"] = known.get(adr_string(addrs[a])) or (names or {}).get(a) or a
    return rows


def hostname(address):
    """(name, mod) of the server "host[:port]" as it sends them, ("", "") if it doesn't answer: a single getstatus
    packet. The mod is its gamename (MODNAME, e.g. "legacy"), "" if the server doesn't send one."""
    addr = resolve(address)
    answer = query([addr], (b"getstatus",)).get(addr, {}) if addr else {}
    status = answer.get("status", {})
    return status.get("sv_hostname", ""), status.get("gamename", "")


def row(line):
    """The Row of a line of servers.tsv; None for a comment, an empty line or a line without text."""
    cells = [c.strip() for c in line.split("\t")] + ["", ""]
    if len(cells) < 4 or not cells[1] or cells[0].startswith("#"):
        return None
    return Row(cells[0], cells[1], cells[2].lower(), tuple(a.strip() for a in cells[3].split(",") if a.strip()))


def row_line(r):
    """The line of servers.tsv for a Row."""
    return "\t".join((r.id, r.text, r.mod, ",".join(r.addresses))).rstrip("\t")


def servers(path=SERVERS):
    """[Row] of servers.tsv in file order; no file, no rows. Lines starting with # are comments."""
    try:
        lines = path.read_text("latin1").splitlines()
    except OSError:
        return []
    rows = []
    for r in filter(None, map(row, lines)):
        if not ID.fullmatch(r.id):
            print(f"⚠️  {path.name}: id '{r.id}' skipped ({ID_RULE})", file=sys.stderr)
            continue
        rows.append(r)
    return rows


def matches(r, hostname, mod):
    """True if the Row covers the server: its text in the name, and its mod (if any) the server's mod. An unknown mod
    ("") only matches rows without one: a config written for one mod never applies on another."""
    return r.text.lower() in strip_colors(hostname).lower() and r.mod in ("", mod.lower())


def identify(hostname, rows, mod=""):
    """Id of the first row of servers() that covers the server, else None."""
    return next((r.id for r in rows if matches(r, hostname, mod)), None)


def note_address(hostname, mod, address, path=SERVERS):
    """Adds the address to the first row of servers.tsv that covers the server, if it doesn't list it yet; returns
    the id of that row, None if no row covers it."""
    try:
        lines = path.read_text("latin1").splitlines()
    except OSError:
        return None
    for n, r in enumerate(map(row, lines)):
        if r and ID.fullmatch(r.id) and matches(r, hostname, mod):
            if address not in r.addresses:
                lines[n] = row_line(r._replace(addresses=r.addresses + (address,)))
                write_atomic(path, "\n".join(lines) + "\n")
            return r.id
    return None


def tag(hostname, text):
    """The part of a server name that shows `text`, with its color codes ("^1[^7xY^1] Fraghouse", "[xy]" ->
    "^1[^7xY^1]"); None if the name doesn't show it."""
    spans, shown, lead = [], "", None  # per shown character: where it starts in the name (its color codes included) and ends
    for m in re.finditer(rf"{COLOR}|.", hostname, re.S):
        if len(m.group()) == 2:
            lead = m.start() if lead is None else lead
            continue
        spans.append((m.start() if lead is None else lead, m.end()))
        shown, lead = shown + m.group(), None
    pos = shown.lower().find(text.lower())
    if not text or pos < 0:
        return None
    return hostname[spans[pos][0]:spans[pos + len(text) - 1][1]]


def server_tag(server, names, rows):
    """The tag of a server id as a server shows it, safe inside a cfg: the longest text of the id (rows of servers())
    found in one of the server names; None if no name shows one."""
    for name in names:
        for text in sorted((r.text for r in rows if r.id == server), key=len, reverse=True):
            if tag(name, text):
                return clean(tag(name, text))
    return None


def seen(path=HISTORY):
    """{"ip:port": (server name, mod)} of the servers remembered so far, as the servers sent them; mod "" if unknown."""
    try:
        lines = path.read_text("latin1").splitlines()
    except OSError:
        return {}
    return {a: (n, m[0] if m else "") for a, n, *m in (line.split("\t") for line in lines if "\t" in line)}


def history(path=HISTORY):
    """{"ip:port": server name as the server sent it} of the servers remembered so far."""
    return {a: n for a, (n, _) in seen(path).items()}


def remember(address, hostname, mod="", path=HISTORY):
    """Stores the name and mod of a server; a server that got a new name or mod replaces its old row."""
    known = seen(path)
    hostname, mod = ("".join(c for c in t if c >= " ") for t in (hostname, mod))  # a tab or line break would break the file
    if hostname and known.get(address) != (hostname, mod):
        known[address] = hostname, mod
        path.parent.mkdir(parents=True, exist_ok=True)
        write_atomic(path, "".join(f"{a}\t{h}\t{m}\n" for a, (h, m) in known.items()))


def selftest():
    info = b'\xff\xff\xff\xffinfoResponse\n\\challenge\\xxx\\hostname\\^1[^7xY^1] FRAGHOUSE ^324MAPS ^2NOL\\mapname\\radar\\clients\\19\\humans\\17\\sv_maxclients\\40\\game\\nitmod'
    status_packet = b'\xff\xff\xff\xffstatusResponse\n\\sv_hostname\\Old "Server"; x\\mapname\\oasis\\gamename\\jaymod\\sv_maxclients\\32\\sv_privateClients\\2\n0 0 "^o[BOT]^7Bean"\n12 48 "Pl ayer"\n3 0 "Bot"\n-5 999 "Joining"\n'
    assert parse(b"\xff\xff\xff\xffprint\nhi") is None and parse(b"garbage") is None
    kind, kv, pings = parse(info)
    assert kind == "info" and kv["humans"] == "17" and pings == []
    kind, kv, pings = parse(status_packet)
    assert kind == "status" and kv["gamename"] == "jaymod" and pings == [0, 48, 0, 999]

    etl = summarize("192.0.2.1:27960", {"info": parse(info)[1], "status": {}, "pings": [0] * 5 + [50] * 14, "rtt": 48})
    assert (etl["playing"], etl["spec"], etl["bots"], etl["slots"], etl["mod"], etl["map"]) == (17, None, 2, 40, "nitmod", "radar")  # humans key wins over pings
    assert etl["hostname"] == etl["name"] == "^1[^7xY^1] FRAGHOUSE ^324MAPS ^2NOL"
    old = summarize("192.0.2.2:27960", {"status": kv, "pings": pings})
    assert (old["playing"], old["spec"], old["bots"], old["slots"], old["mod"], old["ping"]) == (2, None, 2, 30, "jaymod", None)  # ping 0 = bot
    off = summarize("192.0.2.3:27960", None)
    assert off["playing"] is None and off["hostname"] == "" and off["name"] == "192.0.2.3:27960"

    assert teams("-1-30-2", 1) == (1, 2) and teams("--", 0) is None and teams("", 0) is None and teams("3", 2) == (0, 1)
    split = summarize("192.0.2.4:27960", {"info": {"clients": "3", "humans": "2", "sv_maxclients": "40", "game": "nitmod"}, "status": {"P": "1-32", "sv_hostname": "x"}, "pings": [40, 70, 0], "rtt": 5})
    assert (split["playing"], split["spec"], split["bots"]) == (1, 1, 1)
    joining = summarize("192.0.2.5:27960", {"info": {"clients": "4", "humans": "4"}, "status": {"P": "1-32"}, "pings": [40, 70, 30, 999]})
    assert (joining["playing"], joining["spec"], joining["bots"]) == (2, 1, 0)  # P one behind the player lines: split kept
    assert resolve("192.0.2.1:27961") == ("192.0.2.1", 27961) and resolve("192.0.2.1") == ("192.0.2.1", 27960) and resolve("192.0.2.1:x") is None
    assert resolve("[2001:db8::1]:27961") == ("2001:db8::1", 27961) and resolve("[2001:DB8:0::1]") == resolve("2001:db8::1") == ("2001:db8::1", 27960)
    assert resolve("[nope]:27960") is None and resolve("[2001:db8::1]:x") is None
    assert adr_string(("192.0.2.7", 27960)) == "192.0.2.7:27960" and adr_string(("2001:db8::1", 27961)) == "[2001:db8::1]:27961"

    name = "^1[^7xY^1] FRAGHOUSE ^324MAPS"
    with tempfile.TemporaryDirectory() as d:
        tsv = Path(d) / "servers.tsv"
        assert servers(tsv) == []
        tsv.write_text("# id\ttext\nxy_legacy\t[xY]\tLegacy\t192.0.2.1:27960, 192.0.2.1:27961\nxy\t[xY]\n\nBad Id\tx\ncurrent\tx\nlocal\tx\nnotab\n"
                       "solo\tFull Name | Of {Server}\t\t192.0.2.5:27960\nxy2\tfraghouse\tnitmod\n", "latin1")
        with contextlib.redirect_stderr(io.StringIO()):  # the three bad ids are reported
            rows = servers(tsv)
        assert rows == [("xy_legacy", "[xY]", "legacy", ("192.0.2.1:27960", "192.0.2.1:27961")), ("xy", "[xY]", "", ()),
                        ("solo", "Full Name | Of {Server}", "", ("192.0.2.5:27960",)), ("xy2", "fraghouse", "nitmod", ())], rows
        assert identify(name, rows, "legacy") == "xy_legacy" and identify(name, rows, "nitmod") == identify(name, rows) == "xy"  # first row wins
        assert identify("^7Other ^1Fraghouse", rows, "nitmod") == "xy2" and identify("^7Other ^1Fraghouse", rows) is None  # any case; unknown mod
        assert identify("^3Full ^7Name | Of {Server} #2", rows, "etpub") == "solo" and identify("nobody", rows) is None
        assert [row_line(r) for r in rows] == ["xy_legacy\t[xY]\tlegacy\t192.0.2.1:27960,192.0.2.1:27961", "xy\t[xY]",
                                              "solo\tFull Name | Of {Server}\t\t192.0.2.5:27960", "xy2\tfraghouse\tnitmod"]
        assert note_address(name, "legacy", "192.0.2.1:27961", tsv) == "xy_legacy" and note_address("nobody", "", "192.0.2.9:1", tsv) is None
        text = tsv.read_text("latin1")
        assert note_address(name, "etpub", "192.0.2.2:27960", tsv) == "xy" and note_address(name, "etpub", "192.0.2.2:27960", tsv) == "xy"
        assert tsv.read_text("latin1") == text.replace("\nxy\t[xY]\n", "\nxy\t[xY]\t\t192.0.2.2:27960\n")  # once, the rest as it was
        log = Path(d) / "sub/history.tsv"
        assert history(log) == {}
        log.parent.mkdir()
        log.write_text("192.0.2.4:27960\tOld row\n", "latin1")  # a row without mod
        remember("192.0.2.1:27960", name, "legacy", log)
        remember("192.0.2.2:27960", "Tab\there", "", log)
        remember("192.0.2.1:27960", "^2renamed", "nitmod", log)
        remember("192.0.2.3:27960", "", "legacy", log)
        assert history(log) == {"192.0.2.4:27960": "Old row", "192.0.2.1:27960": "^2renamed", "192.0.2.2:27960": "Tabhere"}, history(log)
        assert seen(log)["192.0.2.1:27960"] == ("^2renamed", "nitmod") and seen(log)["192.0.2.4:27960"] == ("Old row", "")
        off = status(["192.0.2.1", "192.0.2.9:27960"], log)  # TEST-NET: no answer
        assert off["192.0.2.1"]["name"] == "^2renamed" and off["192.0.2.1"]["hostname"] == "" and off["192.0.2.9:27960"]["name"] == "192.0.2.9:27960"
        off = status(["192.0.2.1", "192.0.2.9:27960", "192.0.2.8"], log, {"192.0.2.1": "^3old", "192.0.2.9:27960": "^3Browser", "192.0.2.8": ""})
        assert [r["name"] for r in off.values()] == ["^2renamed", "^3Browser", "192.0.2.8"]  # history first, then the browser's name
    assert all(ID.fullmatch(i) for i in ("e", "xy", "e_2", "abcd", "tm_nitmod", "locals", "abc_legacy_server"[:16]))
    assert not any(ID.fullmatch(i) for i in ("", "local", "default", "current", "current_vsay", "Eg", "e g", "e-g", "a" * 17))
    assert tag(name, "[xy]") == "^1[^7xY^1]" and tag(name, "fraghouse") == "FRAGHOUSE" and tag(name, "24maps") == "^324MAPS"
    assert tag(name, "nope") is None and tag(name, "") is None and tag("plain [x] name", "[x]") == "[x]"
    assert tag("^1a^", "a^") == "^1a^" and tag("^4^5ab", "b") == "b" and tag("^4^5ab", "ab") == "^4^5ab"
    rows = [Row("abc", "ABc|"), Row("x", "[x]"), Row("x", "X-Clan")]
    assert server_tag("x", ["^7other", "^1The ^4X-^5Clan ^7#1"], rows) == "^4X-^5Clan"
    assert server_tag("x", ['^1[^7X"^1]; fun'], [Row("x", '[x"]')]) == "^1[^7X'^1]"  # cfg-safe
    assert server_tag("x", ["^1[x] ^2X-Clan"], rows) == "^2X-Clan"  # the longest text
    assert server_tag("x", ["nope"], rows) is None and server_tag("y", ["[x]"], rows) is None
    print("selftest ok")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("address", nargs="*", help="host[:port] of a server")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.address:
        ap.error("an address is required")
    rows = servers()
    for address, row in status(a.address).items():
        if row["playing"] is None:
            print(f"{address}  offline")
            continue
        spec = "" if row["spec"] is None else f"+{row['spec']}"
        print(f"{address}  {row['hostname']}  id {identify(row['hostname'], rows, row['mod']) or '-'}  {row['mod']}  {row['map']}  "
              f"{row['playing']}{spec}+{row['bots']}/{row['slots']}  {row['ping']}ms")


if __name__ == "__main__":
    main()
