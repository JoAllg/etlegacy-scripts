#!/usr/bin/env python3
"""Server configs: tells the game which server it is on, so it can exec that server's settings and voice chat.

Runs next to the game and follows its console log (tools/helpers/common.py follow). A connect ("<address> resolved to
<ip:port>", src/client/cl_main.c CL_Connect_f) names only the address, so the server is asked for its name
(tools/helpers/serverapi.py) and its name and mod are looked up in default/serverconfigs/servers.tsv; a server seen before
is recognized at once from history.tsv, the answer then corrects it and adds the server's address to its row. A server
that doesn't answer (map change, restart, its rate limit) is asked again after 2, 4, 8, ... up to 60 s, until it
answers or the game moves on. A locally hosted map ("----- Server Initialization ----", src/server/sv_init.c
SV_SpawnServer) is the id "local". The log found at the tool's start counts
only while a game runs (profile.pid), and the tool leaves the files for "no server" when it ends, so a game started
without it applies no server's settings. Written to default/serverconfigs/:
- current.cfg: execs default.cfg, then <id>.cfg if the id has one. Its guard applies them only when another id was
  applied last, so the game execs it on many events (map load, team and class change, voice chat) and catches up
  whenever this tool was slower than the game. A second guard runs snd_restart once after every change of the
  address: the engine keeps loaded sounds by file name across servers (src/client/snd_dma.c S_FindName), so the vsay
  sounds of the last server's packs would play on the next one where both use the same names. The same guard runs
  "which" for the voice chat files: the pk3s they come from on that server (the pure server's versions) go into
  packs.tsv (address, file, pk3 relative to fs_homepath or "" for none, date), read by tools/voicemenu.py --find.
- current_vsay.cfg: exec'd each time the voice chat opens; puts the server's voice chat (serverconfigs/vsays/<id>/,
  tools/voicemenu.py) on TAB, or nothing.
- current_bots.cfg: what the MODE key opens (devMode, scripts/devmode.cfg): the dev mode on a local game or without a
  server (the file then sets nothing, so MODE also works without the tool); on a server the bot class switch while
  bots play in the own team, else a note. The server is asked every
  BOT_POLL s (serverapi.team_bots); the own player is found by the names of user.cfg and etconfig.cfg.

Crosshair color per map (docs/autoexec.md): a step of the color cycle taken on a map is written into
default/autoexecs/autoexec_<map>.cfg; a map without autoexec gets one.

At start (and with --check) every name a server cfg sets is looked up in default.cfg, which runs before every server
cfg: a name it doesn't mention keeps the server's value on all other servers, so it is reported (warning only).

Usage: tools/serverconfig.py                                      follow the game (Ctrl+C stops)
       tools/serverconfig.py add <id> [address] [--match <text>] [--any-mod]
                                                                  row in servers.tsv, <id>.cfg if missing; the
                                                                  address defaults to the last connect in the log,
                                                                  the text to the tag at the start of the server's name,
                                                                  the mod to the server's (--any-mod: none); an id that
                                                                  has a row is replaced after asking
       tools/serverconfig.py --check | --selftest
"""
import argparse
import contextlib
import io
import os
import re
import signal
import sys
import tempfile
import time
from pathlib import Path

from helpers.common import RESERVED, STAMP, clean, event, follow, last_connect, map_color, strip_colors, with_map_color, write_atomic
from helpers.serverapi import CONFIGS, ID, ID_RULE, SERVERS, Row, adr_string, hostname, identify, note_address, own_team_bots, remember, \
    remember_pack, resolve, row, row_line, seen, server_tag, servers
from helpers.settings import HOMEPATH, MENU, PROFILE, REPO

EXEC = "profile/serverconfigs"  # the profile link of deploy.sh in each mod folder
VOICE = REPO / PROFILE / "serverconfigs/vsays"
VOICE_EXEC = "profile/serverconfigs/vsays"
PIDFILE = REPO / PROFILE / "profile.pid"  # the game's profiles/<profile>/profile.pid, through the profiles link of deploy.sh
BOT_POLL = 10  # seconds between the questions for the bots of the own team; a server answers one packet per second
OWN_NAME = re.compile(r'(?:\bname |\bseta name ")([^";]+)')  # user.cfg: name1 "name <x>", etconfig.cfg: seta name "<x>"
RETRY, RETRY_MAX = 2, 60  # seconds until a server that didn't answer is asked again: doubled after every try, up to the maximum
GENERATED = {"default", "current", "current_vsay", "current_bots"}  # cfgs of serverconfigs/ that are no server's settings
NAME = re.compile(r'\s*(?:(?:set[asu]?|bind|reset|toggle|cycle)\s+)?"?([^\s";]+)')
NO_NAME = {"exec", "execq", "vstr", "echo", "wait"}
AUTOEXECS = REPO / PROFILE / "autoexecs"
# a server can make the game print both lines: the names end up in a file name and a cfg
MAP_LOAD = re.compile(r"LOADING\.\.\. +(?:- )?maps/([\w.+-]+)\.bsp(?: -)?", re.A)  # legacy: "LOADING...  - maps/<map>.bsp -"
RESTART = re.compile(r"^// Address: (\S+) ([ab])$", re.M)  # last address and the key of its sound restart guard
COLOR_STEP = re.compile(r"CROSSHAIR COLOR ([a-z]{1,16})")
PACK_FILES = ("ui/wm_quickmessageAlt.menu", "scripts/wm_allies_chat.voice", "scripts/wm_axis_chat.voice")  # tools/voicemenu.py
WHICH = re.compile(r'File "([^"]+)" found in "([^"]+\.pk3)"|File not found: "([^"]+)"')  # src/qcommon/files.c FS_Which_f


def stub(mapname):
    """Autoexec of a map that has none: the default autoexec, plus a place for the color."""
    return ["// Map name       " + mapname,
            "// Autoexec by    tools/serverconfig.py (crosshair color; the map has no spawnpoints of its own here)",
            "",
            "// Settings",
            "exec autoexec_default.cfg  // generic spawn menu and mod switch guard, as on a map without autoexec",
            "",
            "echo ^5>>> AUTOEXEC_MAP LOADED!"]


def save_color(mapname, color, out=AUTOEXECS):
    """Sets the crosshair color in the map's autoexec; True if the file was written (not for the color it has:
    the autoexec's own line echoes at every map load)."""
    path = out / f"autoexec_{mapname}.cfg"
    try:
        old = path.read_text("latin1").splitlines()
    except FileNotFoundError:
        old = None
    lines = old or stub(mapname)
    if map_color(lines) == color:
        return False
    new = with_map_color(lines, color)
    if new is None:
        print(f"⚠️  crosshair color: {path.name} has no settings line (exec autoexec_mod.cfg) to put the color after", file=sys.stderr)
        return False
    write_atomic(path, "\n".join(new) + "\n")
    if old is None:
        print(f"⚠️  crosshair color: created {path.name}, the game finds it after the next deploy.sh run (./launcher.sh)", file=sys.stderr)
    return True


def on_map(line, mapname, out=AUTOEXECS):
    """The map the game is on after this log line (None: unknown); a step of the color cycle is saved for it."""
    text = strip_colors(STAMP.sub("", line)).strip()
    m = MAP_LOAD.fullmatch(text)
    if m:
        name = m.group(1).lower()
        return None if name in RESERVED else name
    m = COLOR_STEP.fullmatch(text)
    if m and mapname:
        try:
            save_color(mapname, m.group(1).capitalize(), out)
        except OSError as e:
            print(f"⚠️  crosshair color: {e}", file=sys.stderr)
    return mapname


def on_which(line, target, date):
    """Stores the pk3 a "which" line names for a file of PACK_FILES on the server "ip:port" (packs.tsv)."""
    m = WHICH.fullmatch(strip_colors(STAMP.sub("", line)).strip())
    if not m or target in (None, "local") or (m.group(1) or m.group(3)) not in PACK_FILES:
        return False
    pk3 = Path(m.group(2)) if m.group(2) else None
    if pk3 and pk3.is_relative_to(HOMEPATH):
        pk3 = pk3.relative_to(HOMEPATH)
    remember_pack(target, m.group(1) or m.group(3), str(pk3 or ""), date)
    return True


def settings_cfg(server, address="-", key="a"):
    """current.cfg of a settings id. serverLast runs the alias of the id applied last, which is null while this file
    runs if that is this id; else it applies. scripts set serverLast to "vstr serverApply" to force it (serverForce).
    execq: a key press can apply them (class key, voice chat), which prints no "execing" line.
    The same guard with two keys that swap on every new address runs snd_restart once per server (one alias per
    address would fill MAX_CVARS); serverRestartLast starts as "vstr serverRestartAdopt" (state.cfg): the first server
    after game start takes the key without a restart, its sounds are fresh. Taking the key also asks the game which pk3
    the voice chat files come from (which: the pk3s the server allows), see on_which()."""
    own = "" if server == "default" else f"execq {EXEC}/{server}.cfg; "
    return "\n".join([
        "// Generated by tools/serverconfig.py: settings of the server the game is on, applied once per server (docs/serverconfigs.md)",
        f'set serverApply "execq {EXEC}/default.cfg; {own}set serverLast vstr serverIs_{server}"',
        f'set serverIs_{server} "vstr null"',
        "vstr serverLast",
        f'set serverIs_{server} "vstr serverApply"',
        f"// Address: {address} {key}",
        f'set serverRestartAdopt "set serverRestartLast vstr serverRestart_{key}; {"; ".join(f"which {p}" for p in PACK_FILES)}"',
        'set serverRestart "vstr serverRestartAdopt; snd_restart"',
        f'set serverRestart_{key} "vstr null"',
        "vstr serverRestartLast",
        f'set serverRestart_{key} "vstr serverRestart"',
        f'echo "^5Server: {server} {address}"']) + "\n"


def vsay_cfg(server, tag):
    """current_vsay.cfg: the TAB line and bind of the voice chat's first page; no server page, no TAB."""
    head = "// Generated by tools/serverconfig.py: TAB of the voice chat on this server (scripts/vsays/chat/_menu.cfg)\n"
    if not server:
        return head
    return head + f'echo "{MENU["nav"]}TAB {tag}{MENU["nav"]} Voice chat"\nbind TAB "execq {VOICE_EXEC}/{server}/_menu.cfg"\n'


def write(server, name="", rows=(), out=CONFIGS, voice=VOICE, address=None):
    """Writes current.cfg and current_vsay.cfg for a server id (None: no row of servers.tsv matches) and returns the ids
    used: settings fall back to "default" without <id>.cfg, the voice chat to None without a page folder. A file is
    only replaced when its text changes. An address ("ip:port", "local") other than the last one swaps the key of the
    sound restart guard; None (no server) keeps both."""
    try:
        last, key = RESTART.search((out / "current.cfg").read_text("latin1")).groups()
    except (OSError, AttributeError):
        last, key = "-", "a"
    if address and address != last:
        last, key = address, "b" if key == "a" else "a"
    settings = server if server and (out / f"{server}.cfg").exists() else "default"
    chat = server if server and (voice / server / "_menu.cfg").exists() else None
    tag = chat and (server_tag(server, [name], rows) or f"[{server}]")
    out.mkdir(parents=True, exist_ok=True)
    for file, text in (("current.cfg", settings_cfg(settings, last, key)), ("current_vsay.cfg", vsay_cfg(chat, tag))):
        try:
            same = (out / file).read_text("latin1") == text
        except OSError:
            same = False
        if not same:
            write_atomic(out / file, text)
    return settings, chat


def own_names(files=(REPO / "user.cfg", REPO / PROFILE / "etconfig.cfg")):
    """Names the player may use: every "name <x>" of user.cfg (the name keys) and the name etconfig.cfg saved."""
    names = set()
    for f in files:
        with contextlib.suppress(OSError):
            names.update(n.strip() for n in OWN_NAME.findall(f.read_text("latin1")))
    return names


def bots_cfg(bots, mine=True):
    """current_bots.cfg: what MODE opens; bots None: no server or a local game, MODE keeps the dev mode. The title of
    the bot class switch (botModeHead, devmode/bots.cfg) names the bots: in the own team, or on the server if the own
    player wasn't found (mine False)."""
    head = "// Generated by tools/serverconfig.py: what MODE opens on a server, by bots in the own team (scripts/devmode.cfg)\n"
    if bots is None:
        return head
    if not bots:
        return head + "set devModeKind vstr botModeNone\n"
    where = "in your team" if mine else "on the server"
    title = f'{MENU["head"]}BOTS {MENU["text"]}{bots} {MENU["head"]}{where}: {MENU["text"]}switch a bot from class'
    return head + f'set devModeKind vstr botModeOpen\nset botModeHead "echo {title}"\n'


def write_bots(target, out=CONFIGS, count=own_team_bots):
    """Brings current_bots.cfg up to where the game is (None: no server, "local", "ip:port"); an unclear answer of
    the server (none, a player joining) keeps the file."""
    answer = None, True
    if target not in (None, "local"):
        answer = count(target, own_names())
        if answer is None:
            return
    text, path = bots_cfg(*answer), out / "current_bots.cfg"
    with contextlib.suppress(OSError):
        if path.read_text("latin1") == text:
            return
    out.mkdir(parents=True, exist_ok=True)
    write_atomic(path, text)


def ask(target, name=hostname):
    """Asks the server "ip:port" for its name once and brings the files up to the answer; False without one."""
    name, mod = name(target)
    if not name:
        return False
    remember(target, name, mod)
    rows = servers()
    write(identify(name, rows, mod), name, rows, address=target)
    note_address(name, mod, target)
    return True


def settle(target):
    """Brings the files up to where the game is now (None: no server, "local", or "ip:port"): at once from the
    history, then from the server's own answer. False if the server has yet to answer."""
    if target in (None, "local"):
        write(target, address=target)
        return True
    rows = servers()
    name, mod = seen().get(target, ("", ""))
    write(identify(name, rows, mod), name, rows, address=target)
    return ask(target)


def pauses():
    """Seconds to wait before each further try."""
    pause = RETRY
    while True:
        yield pause
        pause = min(pause * 2, RETRY_MAX)


def unreset(text, default):
    """Names a server cfg sets (after set/seta/bind/..., else the first word of a line) that default.cfg doesn't mention
    anywhere: a reset can be indirect ("vstr fovNormal  // cg_fov"), so a comment counts."""
    # ponytail: only the first command of a line is looked at; split on ";" outside quotes when cfgs chain commands
    out = []
    for line in text.splitlines():
        m = NAME.match(line.split("//")[0])
        if m and m.group(1).lower() not in NO_NAME and m.group(1) not in out \
                and not re.search(rf"(?<!\w){re.escape(m.group(1))}(?!\w)", default, re.I):
            out.append(m.group(1))
    return out


def check(out=CONFIGS):
    """Warns about every name of a server cfg that default.cfg doesn't reset; returns the warnings."""
    try:
        default = (out / "default.cfg").read_text("latin1")
    except OSError:
        default = ""
    lines = [f"⚠️  serverconfigs/{f.name}: {name} is not in default.cfg, so it keeps this value on other servers"
             for f in sorted(out.glob("*.cfg")) if f.stem not in GENERATED
             for name in unreset(f.read_text("latin1"), default)]
    for line in lines:
        print(line, file=sys.stderr)
    return lines


def guess(name):
    """The text proposed for a server name: its first word up to the first sign that ends a tag ("ABc|Clan" -> "ABc|")."""
    m = re.match(r"\W*\w+[^\w\s]?", strip_colors(name).strip())
    return m.group() if m else ""


def with_row(lines, new):
    """(lines of servers.tsv with the Row, rows it replaces): the row takes the place of the id's first row and its
    other rows go; a new id is appended. It keeps the addresses of the replaced rows with its own text and mod."""
    out, old = [], []
    for line in lines:
        r = row(line)
        if r and r.id == new.id:
            if not old:
                out.append(None)
            old.append(r)
        else:
            out.append(line)
    kept = [a for r in old if (r.text, r.mod) == (new.text, new.mod) for a in r.addresses]
    line = row_line(new._replace(addresses=tuple(dict.fromkeys(kept + list(new.addresses)))))
    return ([line if x is None else x for x in out] if old else out + [line]), old


def add(server, address, text, any_mod=False):
    if not ID.fullmatch(server):
        sys.exit(f"id '{server}': {ID_RULE}")
    address = address or last_connect()
    if not address:
        sys.exit("no address given and no connect in the game's log")
    name, mod = hostname(address)
    if not name:
        sys.exit(f"{address} doesn't answer")
    text = text or guess(name)
    if not text or "\t" in text or identify(name, [Row(server, text)]) != server:
        sys.exit(f"the server's name doesn't contain '{text}': {name}")
    if not mod and not any_mod:
        sys.exit(f"{address} doesn't tell its mod: --any-mod adds the row for every mod")
    address = adr_string(resolve(address))
    new = Row(server, text, "" if any_mod else mod.lower(), (address,))
    CONFIGS.mkdir(parents=True, exist_ok=True)
    lines = SERVERS.read_text("latin1").splitlines() if SERVERS.exists() else \
        ["# <id><TAB><text in the server name><TAB><mod, empty: any><TAB><addresses seen>, the first matching row wins (docs/serverconfigs.md)"]
    lines, old = with_row(lines, new)
    if any((r.text, r.mod) != (new.text, new.mod) for r in old):
        shown = " | ".join(f"{r.text} ({r.mod or 'any mod'})" for r in old)
        print(f"⚠️  '{server}' is in {SERVERS.name} already, with: {shown}", file=sys.stderr)
        if not sys.stdin.isatty() or input(f"Replace with '{text}' ({new.mod or 'any mod'})? [y/N] ").strip().lower() != "y":  # no terminal: nobody to ask
            sys.exit(f"{SERVERS.name} unchanged")
    write_atomic(SERVERS, "\n".join(lines) + "\n")
    cfg = CONFIGS / f"{server}.cfg"
    if not cfg.exists():
        cfg.write_text(f"// Settings on the servers of '{server}' (docs/serverconfigs.md): absolute values only, and every name set here gets its normal value in default.cfg\n", "latin1")
    remember(address, name, mod)
    print(f"{name}\n{SERVERS.relative_to(REPO)}: {row_line(new)}\n{cfg.relative_to(REPO)}")
    first = identify(name, servers(), mod)
    if first != server:
        print(f"⚠️  the earlier row of '{first}' matches this server first", file=sys.stderr)


def game_running(pidfile=PIDFILE):
    """True while a game runs: its pid file holds the pid and goes at exit (src/sys/sys_main.c Sys_WritePIDFile,
    Sys_Exit); after a crash it stays, with a pid that is gone."""
    try:
        os.kill(int(pidfile.read_text()), 0)
    except PermissionError:  # the pid lives, under another user
        return True
    except (OSError, ValueError):
        return False
    return True


def attempt(target):
    """settle(), with a failed write or socket counted as "no answer yet": the tool lives on and tries again."""
    try:
        return settle(target)
    except OSError as e:
        print(f"⚠️  server configs: {e} (trying again)", file=sys.stderr)
        return False


def run():
    check()
    print(f"Server configs: following the game -> {CONFIGS} (Ctrl+C stops)")
    done, target, wait, due, stale, first, mapname = object(), None, None, 0, False, True, None
    bots_for, bots_due = object(), 0
    for sig in (signal.SIGTERM, signal.SIGHUP):  # launcher.sh ends the tool with SIGTERM: leave through the finally below
        signal.signal(sig, lambda *_: sys.exit(0))
    try:
        for line in follow():
            if line is None:  # a new game session is on no server
                # the log found at the tool's start is the last session's unless a game runs: its connects don't count
                target, stale, first, mapname = None, first and not game_running(), False, None
            elif line:
                if not stale:
                    target = event(line) or target
                    mapname = on_map(line, mapname)
                    with contextlib.suppress(OSError):
                        on_which(line, target, time.strftime("%Y-%m-%d"))
            elif target != done:  # end of the log: act on the last event only, not on every connect of a replay
                done, wait = target, None if attempt(target) else pauses()
                due = time.monotonic() + next(wait) if wait else 0
            elif wait and time.monotonic() >= due:  # between the tries the log is followed on, so a new connect is not held up
                wait = None if attempt(target) else wait
                due = time.monotonic() + next(wait) if wait else 0
            if line == "" and (target != bots_for or time.monotonic() >= bots_due):  # end of the log: the game is where target says
                bots_for, bots_due = target, time.monotonic() + BOT_POLL
                with contextlib.suppress(OSError):
                    write_bots(target)
    except KeyboardInterrupt:
        pass
    finally:  # without the tool nobody corrects the files: a game started without it must find no server's settings
        with contextlib.suppress(OSError):
            write(None)
            write_bots(None)


def selftest():
    assert WHICH.fullmatch('File "ui/wm_quickmessageAlt.menu" found in "/x/xymod/a~.0badf00d.pk3"').groups() == ("ui/wm_quickmessageAlt.menu", "/x/xymod/a~.0badf00d.pk3", None)
    assert WHICH.fullmatch('File not found: "scripts/wm_axis_chat.voice"').group(3) == "scripts/wm_axis_chat.voice"
    assert not on_which('File "ui/wm_quickmessageAlt.menu" found in "/x/a.pk3"', "local", "2000-01-01")  # local hosting: no record
    assert event("       0 192.0.2.7:27980 resolved to 192.0.2.7:27980\n") == "192.0.2.7:27980"
    assert event("  165000 my.server.org resolved to 192.0.2.1:27960\n") == "192.0.2.1:27960"
    assert event("       0 [2001:db8::1]:27961 resolved to [2001:db8::1]:27961\n") == "[2001:db8::1]:27961"
    assert event("       0 MOTD: resolving motd.example.org... resolved to 192.0.2.9:27951\n") is None
    assert event("       0 localhost resolved to loopback\n") is None and event("       0 Server: fueldump\n") is None
    assert event("    1200 ----- Server Initialization ----\n") == "local"

    with tempfile.TemporaryDirectory() as d:
        out, note = Path(d), "  // crosshair color on this map as set in-game via HOME key and saved by tools/serverconfig.py"
        radar = out / "autoexec_radar.cfg"
        radar.write_text("// Settings\nexec autoexec_mod.cfg  // x\nset spawnSelectorMap \"vstr spawnSelector3\"\n\n// Spawnpoints\n")
        assert on_map("     100 ^8CROSSHAIR COLOR ^2cyan\n", None, out) is None and "Color" not in radar.read_text()  # no map yet
        assert on_map("       0 LOADING... maps/Radar.bsp\n", None, out) == "radar" and on_map("       0 LOADING... :models:\n", "radar", out) == "radar"
        assert on_map("    1200 LOADING...  - maps/supply.bsp -\n", "radar", out) == "supply"
        assert on_map("     100 ^8CROSSHAIR COLOR ^2cyan\n", "radar", out) == "radar"
        assert radar.read_text().splitlines()[1:4] == ["exec autoexec_mod.cfg  // x", 'set spawnSelectorMap "vstr spawnSelector3"', "vstr crosshairColorCyan" + note]
        before = radar.stat().st_mtime_ns
        assert save_color("radar", "Cyan", out) is False and radar.stat().st_mtime_ns == before  # the autoexec's own echo
        assert save_color("radar", "Red", out) and radar.read_text().count("crosshairColor") == 1 and "vstr crosshairColorRed" + note in radar.read_text()
        for line in ("Someone: CROSSHAIR COLOR green", "CROSSHAIR COLOR x; quit", "CROSSHAIR COLOR ../x"):  # chat, no color names
            on_map(f"     100 {line}\n", "radar", out)
        assert "Red" in radar.read_text()
        assert [on_map(f"       0 LOADING... maps/{m}.bsp\n", "radar", out) for m in ("default", "../x", "a/b", "te-1_b2.x")] == [None, "radar", "radar", "te-1_b2.x"]
        with contextlib.redirect_stderr(io.StringIO()) as err:
            assert save_color("newmap", "Green", out) and "created autoexec_newmap.cfg" in err.getvalue()
            assert (out / "autoexec_newmap.cfg").read_text().splitlines()[3:6] == ["// Settings", "exec autoexec_default.cfg  // generic spawn menu and mod switch guard, as on a map without autoexec", "vstr crosshairColorGreen" + note]
            (out / "autoexec_odd.cfg").write_text("echo x\n")
            assert save_color("odd", "Green", out) is False and "no settings line" in err.getvalue()
        assert not list(out.glob("*.tmp"))

    xy = settings_cfg("xy").splitlines()
    assert xy[1] == f'set serverApply "execq {EXEC}/default.cfg; execq {EXEC}/xy.cfg; set serverLast vstr serverIs_xy"'
    assert xy[2:5] == ['set serverIs_xy "vstr null"', "vstr serverLast", 'set serverIs_xy "vstr serverApply"']
    assert xy[5:] == ["// Address: - a", 'set serverRestartAdopt "set serverRestartLast vstr serverRestart_a; which ui/wm_quickmessageAlt.menu; '
                                             'which scripts/wm_allies_chat.voice; which scripts/wm_axis_chat.voice"',
                      'set serverRestart "vstr serverRestartAdopt; snd_restart"', 'set serverRestart_a "vstr null"',
                      "vstr serverRestartLast", 'set serverRestart_a "vstr serverRestart"', 'echo "^5Server: xy -"']
    assert f'set serverApply "execq {EXEC}/default.cfg; set serverLast vstr serverIs_default"' in settings_cfg("default")
    assert vsay_cfg(None, None).count("\n") == 1 and vsay_cfg(None, None).startswith("//")
    nav = MENU["nav"]
    assert vsay_cfg("xy", "^1[^7xY^1]").splitlines()[1:] == [f'echo "{nav}TAB ^1[^7xY^1]{nav} Voice chat"', f'bind TAB "execq {VOICE_EXEC}/xy/_menu.cfg"']

    with tempfile.TemporaryDirectory() as d:
        out, voice = Path(d) / "serverconfigs", Path(d) / "voice"
        rows = [Row("xy", "[xY]"), Row("solo", "Solo Server")]
        assert write(None, out=out, voice=voice) == ("default", None)
        assert (out / "current.cfg").read_text() == settings_cfg("default") and (out / "current_vsay.cfg").read_text() == vsay_cfg(None, None)
        assert write("xy", "^1[^7xY^1] x", rows, out, voice) == ("default", None)  # neither a cfg nor voice pages yet
        (out / "xy.cfg").write_text("set fovLow 100\ncg_fov 100 // x\nbind F9 \"vstr a; cg_drawFPS 1\"\n\nvstr hook\n// com_maxfps 1\nseta \"r_gamma\" 2\n")
        (voice / "xy").mkdir(parents=True)
        (voice / "xy/_menu.cfg").write_text("")
        (voice / "solo").mkdir()
        (voice / "solo/_menu.cfg").write_text("")
        assert write("xy", '^1[^7xY"^1] x', [Row("xy", '[xY"]')], out, voice) == ("xy", "xy")
        assert (out / "current.cfg").read_text() == settings_cfg("xy")
        assert f"TAB ^1[^7xY'^1]{nav} Voice chat" in (out / "current_vsay.cfg").read_text()  # cfg-safe tag
        before = (out / "current.cfg").stat().st_mtime_ns
        assert write("solo", "", rows, out, voice) == ("default", "solo")  # voice pages only, name unknown
        assert f"TAB [solo]{nav} Voice chat" in (out / "current_vsay.cfg").read_text()
        write("solo", "", rows, out, voice)
        assert not list(out.glob("*.tmp")) and (out / "current.cfg").stat().st_mtime_ns > before
        same = (out / "current.cfg").stat().st_mtime_ns
        write("solo", "", rows, out, voice)
        assert (out / "current.cfg").stat().st_mtime_ns == same  # unchanged text: file left alone
        keys = []
        for address in ("192.0.2.1:27960", "192.0.2.1:27960", None, "local", "192.0.2.2:27960", None):
            write("solo", "", rows, out, voice, address)
            keys.append(RESTART.search((out / "current.cfg").read_text()).groups())
        assert keys == [("192.0.2.1:27960", "b"), ("192.0.2.1:27960", "b"), ("192.0.2.1:27960", "b"), ("local", "a"),
                        ("192.0.2.2:27960", "b"), ("192.0.2.2:27960", "b")]  # a new address swaps the key, no server keeps it

        with contextlib.redirect_stderr(io.StringIO()):  # the warnings are the result here
            assert check(out) == [f"⚠️  serverconfigs/xy.cfg: {n} is not in default.cfg, so it keeps this value on other servers"
                                  for n in ("fovLow", "cg_fov", "F9", "r_gamma")]
            (out / "default.cfg").write_text('vstr fovLowNormal  // fovLow\nCG_FOV 90\nbind F9 "vstr b"\n')
            assert check(out) == ["⚠️  serverconfigs/xy.cfg: r_gamma is not in default.cfg, so it keeps this value on other servers"]
    assert [guess(n) for n in ("^1[^7xY^1] FRAGHOUSE", "^8ABc|^4Clan^9,XPSave", " {SomeName} #1", "^3Full Name", "^1")] == ["[xY]", "ABc|", "{SomeName}", "Full", ""]
    tsv = ["# head", "xy\t[xY]\tnitmod\t192.0.2.1:27960", "sn\tSOME", "abc\tABc|", "sn\tSOME NAME"]
    assert with_row(tsv, Row("sn", "Name")) == (["# head", tsv[1], "sn\tName", "abc\tABc|"], [Row("sn", "SOME"), Row("sn", "SOME NAME")])
    assert with_row(tsv, Row("new", "x y", "legacy", ("192.0.2.3:27960",))) == (tsv + ["new\tx y\tlegacy\t192.0.2.3:27960"], [])
    assert with_row(tsv, Row("xy", "[xY]", "nitmod", ("192.0.2.2:27960",)))[0][1] == "xy\t[xY]\tnitmod\t192.0.2.1:27960,192.0.2.2:27960"  # same row: one more address
    assert with_row(tsv, Row("xy", "[xY]", "legacy", ("192.0.2.2:27960",)))[0][1] == "xy\t[xY]\tlegacy\t192.0.2.2:27960"  # other mod: its servers go
    wait = pauses()
    assert [next(wait) for _ in range(7)] == [2, 4, 8, 16, 32, 60, 60]
    assert ask("192.0.2.1:27960", lambda address: ("", "")) is False  # no answer: nothing is written
    with tempfile.TemporaryDirectory() as d:
        pid, log = Path(d) / "profile.pid", Path(d) / "etconsole.log"
        assert not game_running(pid)  # no file: no game
        pid.write_text(str(os.getpid()))
        assert game_running(pid)
        pid.write_text("x")
        assert not game_running(pid)
        log.write_text("       0 logfile opened on A\n")
        with contextlib.redirect_stdout(io.StringIO()):  # "following ..."
            lines = follow(lambda: log, 0)
            assert [next(lines) for _ in range(3)] == [None, "       0 logfile opened on A\n", ""] and next(lines) == ""
            log.write_text("       0 logfile opened on B\n       0 a longer log than the one before\n")  # restart, not smaller
            assert [next(lines) for _ in range(2)] == [None, "       0 logfile opened on B\n"]
        write_atomic(log, "x")
        assert not list(Path(d).glob("*.tmp"))
    with tempfile.TemporaryDirectory() as d:
        out, user = Path(d), Path(d) / "user.cfg"
        user.write_text('set name1 "name ^1A^7b"\nset name2 "name C d"  // x\nseta name "^2E"\nset nameMain "vstr name1; echo x"\n')
        assert own_names([user, Path(d) / "none.cfg"]) == {"^1A^7b", "C d", "^2E"}
        bots, asked = out / "current_bots.cfg", []
        write_bots("192.0.2.1:27960", out, lambda a, own: asked.append(a) or (2, True))
        assert bots.read_text() == bots_cfg(2) and bots_cfg(2).splitlines()[1:] == [
            "set devModeKind vstr botModeOpen", f'set botModeHead "echo {MENU["head"]}BOTS {MENU["text"]}2 {MENU["head"]}in your team: {MENU["text"]}switch a bot from class"']
        assert "3 " + MENU["head"] + "on the server" in bots_cfg(3, False)
        write_bots("192.0.2.1:27960", out, lambda a, own: None)  # unclear answer: file kept
        assert bots.read_text() == bots_cfg(2)
        write_bots("192.0.2.1:27960", out, lambda a, own: (0, False))
        assert bots.read_text() == bots_cfg(0) and bots_cfg(0).endswith("set devModeKind vstr botModeNone\n") and bots_cfg(0).count("\n") == 2
        for target in ("local", None):  # dev mode, the server isn't asked
            write_bots(target, out, lambda a, own: 1 / 0)
            assert bots.read_text() == bots_cfg(None) and bots_cfg(None).count("\n") == 1
        assert asked == ["192.0.2.1:27960"] and not list(out.glob("*.tmp"))
    assert unreset("cg_fov 1\ncg_fov 2\nexec x.cfg\nwait 5", "my_cg_fov 1") == ["cg_fov"]
    print("selftest ok")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", nargs="?", choices=["add"])
    ap.add_argument("id", nargs="?")
    ap.add_argument("address", nargs="?", help="host[:port], default: the last connect in the game's log")
    ap.add_argument("--match", metavar="TEXT", help="text in the server's name, default: the tag at its start")
    ap.add_argument("--any-mod", action="store_true", help="the row covers servers of every mod, default: only the server's mod")
    ap.add_argument("--check", action="store_true", help="only report names that default.cfg doesn't reset")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.check:
        return check()
    if a.command:
        if not a.id:
            ap.error("add needs an id")
        return add(a.id, a.address, a.match, a.any_mod)
    run()


if __name__ == "__main__":
    main()
