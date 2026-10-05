#!/usr/bin/env python3
"""Server API: the one place where the tools talk to game servers and tell which server is which.

Query (same as the game's server browser, src/server/sv_main.c SVC_Info / SVC_Status): the UDP packets
"\\xff\\xff\\xff\\xffgetinfo" and "...getstatus" to the game port; status(addresses) returns one row per server.
- humans and bots: the "humans" key of getinfo (servers on the ET: Legacy engine, any mod), else the players of
  getstatus minus those with ping 0 (bots). Teams: the slot string P of getstatus (1 axis, 2 allies, 3 spectator,
  0 connecting); team players minus bots are the playing humans. Without P only humans and bots are known. omnibot_playing is not used: nitmod servers report 0 or -1 with bots playing
- ET: Legacy servers answer one packet per second per address after a burst of 10, so a poll interval must stay above 2 s

Identity: default/serverconfigs/servers.tsv (user-maintained, "<id><TAB><text>") names the servers that have settings
or a voice chat of their own. A row matches a server whose name contains the text (colors ignored, any case); the
first matching row wins, so one clan tag covers all servers of a clan. history.tsv next to it remembers the name
of every server the game connected to, so a server is recognized without asking it again.

Usage: tools/helpers/serverapi.py <address> ...   (prints name, id, mod, map, players, ping)
       tools/helpers/serverapi.py --selftest
"""
import argparse
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
ID = re.compile(r"[a-z0-9_]{1,4}")  # an id is part of a file name and of an alias name; short like a clan tag, which also
# keeps it apart from the other files of serverconfigs/ (default, local, current, current_vsay)
ID_RULE = "1 to 4 characters of a-z, 0-9, _"
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
    """Name of the server "host[:port]" as it sends it, "" if it doesn't answer: a single getstatus packet."""
    addr = resolve(address)
    answer = query([addr], (b"getstatus",)).get(addr, {}) if addr else {}
    return answer.get("status", {}).get("sv_hostname", "")


def servers(path=SERVERS):
    """[(id, text)] of servers.tsv in file order; no file, no rows. Lines starting with # are comments."""
    try:
        lines = path.read_text("latin1").splitlines()
    except OSError:
        return []
    rows = []
    for line in lines:
        name, sep, text = line.partition("\t")
        name, text = name.strip(), text.strip()
        if not sep or not text or name.startswith("#"):
            continue
        if not ID.fullmatch(name):
            print(f"⚠️  {path.name}: id '{name}' skipped ({ID_RULE})", file=sys.stderr)
            continue
        rows.append((name, text))
    return rows


def identify(hostname, rows):
    """Id of the first row of servers() whose text is in the server name, else None."""
    name = strip_colors(hostname).lower()
    return next((i for i, text in rows if text.lower() in name), None)


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
        for text in sorted((t for i, t in rows if i == server), key=len, reverse=True):
            if tag(name, text):
                return clean(tag(name, text))
    return None


def history(path=HISTORY):
    """{"ip:port": server name as the server sent it} of the servers remembered so far."""
    try:
        lines = path.read_text("latin1").splitlines()
    except OSError:
        return {}
    return dict(line.split("\t", 1) for line in lines if "\t" in line)


def remember(address, hostname, path=HISTORY):
    """Stores the name of a server; a server that got a new name replaces its old one."""
    known = history(path)
    hostname = "".join(c for c in hostname if c >= " ")  # a tab or line break would break the file
    if hostname and known.get(address) != hostname:
        known[address] = hostname
        path.parent.mkdir(parents=True, exist_ok=True)
        write_atomic(path, "".join(f"{a}\t{h}\n" for a, h in known.items()))


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
        tsv.write_text("# id\ttext\nxy\t[xY]\n\nBad Id\tx\ncurrent\tx\nlocal\tx\nnotab\nsolo\tFull Name | Of {Server}\nxy2\tfraghouse\n", "latin1")
        with contextlib.redirect_stderr(io.StringIO()):  # the three bad ids are reported
            rows = servers(tsv)
        assert rows == [("xy", "[xY]"), ("solo", "Full Name | Of {Server}"), ("xy2", "fraghouse")], rows
        assert identify(name, rows) == "xy" and identify("^7Other ^1Fraghouse", rows) == "xy2"  # first row wins, any case
        assert identify("^3Full ^7Name | Of {Server} #2", rows) == "solo" and identify("nobody", rows) is None
        log = Path(d) / "sub/history.tsv"
        assert history(log) == {}
        remember("192.0.2.1:27960", name, log)
        remember("192.0.2.2:27960", "Tab\there", log)
        remember("192.0.2.1:27960", "^2renamed", log)
        remember("192.0.2.3:27960", "", log)
        assert history(log) == {"192.0.2.1:27960": "^2renamed", "192.0.2.2:27960": "Tabhere"}, history(log)
        off = status(["192.0.2.1", "192.0.2.9:27960"], log)  # TEST-NET: no answer
        assert off["192.0.2.1"]["name"] == "^2renamed" and off["192.0.2.1"]["hostname"] == "" and off["192.0.2.9:27960"]["name"] == "192.0.2.9:27960"
        off = status(["192.0.2.1", "192.0.2.9:27960", "192.0.2.8"], log, {"192.0.2.1": "^3old", "192.0.2.9:27960": "^3Browser", "192.0.2.8": ""})
        assert [r["name"] for r in off.values()] == ["^2renamed", "^3Browser", "192.0.2.8"]  # history first, then the browser's name
    assert all(ID.fullmatch(i) for i in ("e", "xy", "e_2", "abcd")) and not any(ID.fullmatch(i) for i in ("", "local", "default", "current", "Eg", "e g", "e-g"))
    assert tag(name, "[xy]") == "^1[^7xY^1]" and tag(name, "fraghouse") == "FRAGHOUSE" and tag(name, "24maps") == "^324MAPS"
    assert tag(name, "nope") is None and tag(name, "") is None and tag("plain [x] name", "[x]") == "[x]"
    assert tag("^1a^", "a^") == "^1a^" and tag("^4^5ab", "b") == "b" and tag("^4^5ab", "ab") == "^4^5ab"
    rows = [("abc", "ABc|"), ("x", "[x]"), ("x", "X-Clan")]
    assert server_tag("x", ["^7other", "^1The ^4X-^5Clan ^7#1"], rows) == "^4X-^5Clan"
    assert server_tag("x", ['^1[^7X"^1]; fun'], [("x", '[x"]')]) == "^1[^7X'^1]"  # cfg-safe
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
        print(f"{address}  {row['hostname']}  id {identify(row['hostname'], rows) or '-'}  {row['mod']}  {row['map']}  "
              f"{row['playing']}{spec}+{row['bots']}/{row['slots']}  {row['ping']}ms")


if __name__ == "__main__":
    main()
