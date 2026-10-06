#!/usr/bin/env python3
"""Server configs: tells the game which server it is on, so it can exec that server's settings and voice chat.

Runs next to the game and follows its console log (tools/helpers/common.py follow). A connect ("<address> resolved to
<ip:port>", src/client/cl_main.c CL_Connect_f) names only the address, so the server is asked for its name
(tools/helpers/serverapi.py) and the name is looked up in default/serverconfigs/servers.tsv; a server seen before is
recognized at once from history.tsv, the answer then corrects it. A server that doesn't answer (map change, restart,
its rate limit) is asked again after 2, 4, 8, ... up to 60 s, until it answers or the game moves on. A locally hosted map ("----- Server
Initialization ----", src/server/sv_init.c SV_SpawnServer) is the id "local". The log found at the tool's start counts
only while a game runs (profile.pid), and the tool leaves the files for "no server" when it ends, so a game started
without it applies no server's settings. Written to default/serverconfigs/:
- current.cfg: execs default.cfg, then <id>.cfg if the id has one. Its guard applies them only when another id was
  applied last, so the game execs it on many events (map load, team and class change, voice chat) and catches up
  whenever this tool was slower than the game. A second guard runs snd_restart once after every change of the
  address: the engine keeps loaded sounds by file name across servers (src/client/snd_dma.c S_FindName), so the vsay
  sounds of the last server's packs would play on the next one where both use the same names.
- current_vsay.cfg: exec'd each time the voice chat opens; puts the server's voice chat (scripts/vsays/servers/<id>/,
  tools/voicemenu.py) on TAB, or nothing.

Crosshair color per map (docs/autoexec.md): a step of the color cycle taken on a map is written into
default/autoexecs/autoexec_<map>.cfg; a map without autoexec gets one.

At start (and with --check) every name a server cfg sets is looked up in default.cfg, which runs before every server
cfg: a name it doesn't mention keeps the server's value on all other servers, so it is reported (warning only).

Usage: tools/serverconfig.py                                      follow the game (Ctrl+C stops)
       tools/serverconfig.py add <id> [address] [--match <text>]  row in servers.tsv, <id>.cfg if missing; the
                                                                  address defaults to the last connect in the log,
                                                                  the text to the tag at the start of the server's name;
                                                                  an id that has a row is replaced after asking
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
from helpers.serverapi import CONFIGS, ID, ID_RULE, SERVERS, adr_string, history, hostname, identify, remember, resolve, server_tag, servers
from helpers.settings import MENU, PROFILE, REPO

EXEC = "profile/serverconfigs"  # the profile link of deploy.sh in each mod folder
VOICE = REPO / PROFILE / "scripts/vsays/servers"
VOICE_EXEC = "profile/scripts/vsays/servers"
PIDFILE = REPO / PROFILE / "profile.pid"  # the game's profiles/<profile>/profile.pid, through the profiles link of deploy.sh
RETRY, RETRY_MAX = 2, 60  # seconds until a server that didn't answer is asked again: doubled after every try, up to the maximum
GENERATED = {"default", "current", "current_vsay"}  # cfgs of serverconfigs/ that are no server's settings
NAME = re.compile(r'\s*(?:(?:set[asu]?|bind|reset|toggle|cycle)\s+)?"?([^\s";]+)')
NO_NAME = {"exec", "execq", "vstr", "echo", "wait"}
AUTOEXECS = REPO / PROFILE / "autoexecs"
# a server can make the game print both lines: the names end up in a file name and a cfg
MAP_LOAD = re.compile(r"LOADING\.\.\. +(?:- )?maps/([\w.+-]+)\.bsp(?: -)?", re.A)  # legacy: "LOADING...  - maps/<map>.bsp -"
RESTART = re.compile(r"^// Address: (\S+) ([ab])$", re.M)  # last address and the key of its sound restart guard
COLOR_STEP = re.compile(r"CROSSHAIR COLOR ([a-z]{1,16})")


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


def settings_cfg(server, address="-", key="a"):
    """current.cfg of a settings id. serverLast runs the alias of the id applied last, which is null while this file
    runs if that is this id; else it applies. scripts set serverLast to "vstr serverApply" to force it (serverForce).
    execq: a key press can apply them (class key, voice chat), which prints no "execing" line.
    The same guard with two keys that swap on every new address runs snd_restart once per server (one alias per
    address would fill MAX_CVARS); serverRestartLast starts as "vstr serverRestartAdopt" (state.cfg): the first server
    after game start takes the key without a restart, its sounds are fresh."""
    own = "" if server == "default" else f"execq {EXEC}/{server}.cfg; "
    return "\n".join([
        "// Generated by tools/serverconfig.py: settings of the server the game is on, applied once per server (docs/serverconfigs.md)",
        f'set serverApply "execq {EXEC}/default.cfg; {own}set serverLast vstr serverIs_{server}"',
        f'set serverIs_{server} "vstr null"',
        "vstr serverLast",
        f'set serverIs_{server} "vstr serverApply"',
        f"// Address: {address} {key}",
        f'set serverRestartAdopt "set serverRestartLast vstr serverRestart_{key}"',
        'set serverRestart "vstr serverRestartAdopt; snd_restart"',
        f'set serverRestart_{key} "vstr null"',
        "vstr serverRestartLast",
        f'set serverRestart_{key} "vstr serverRestart"']) + "\n"


def vsay_cfg(server, tag):
    """current_vsay.cfg: the TAB line and bind of the voice chat's first page; no server page, no TAB."""
    head = "// Generated by tools/serverconfig.py: TAB of the voice chat on this server (scripts/vsays/chat/categories.cfg)\n"
    if not server:
        return head
    return head + f'echo "{MENU["nav"]}TAB {tag}{MENU["nav"]} Voice chat"\nbind TAB "execq {VOICE_EXEC}/{server}/{server}.cfg"\n'


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
    chat = server if server and (voice / server / f"{server}.cfg").exists() else None
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


def ask(target, name=hostname):
    """Asks the server "ip:port" for its name once and brings the files up to the answer; False without one."""
    name = name(target)
    if not name:
        return False
    remember(target, name)
    rows = servers()
    write(identify(name, rows), name, rows, address=target)
    return True


def settle(target):
    """Brings the files up to where the game is now (None: no server, "local", or "ip:port"): at once from the
    history, then from the server's own answer. False if the server has yet to answer."""
    if target in (None, "local"):
        write(target, address=target)
        return True
    rows = servers()
    name = history().get(target, "")
    write(identify(name, rows), name, rows, address=target)
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


def with_row(lines, server, text):
    """(lines of servers.tsv with the row "<id><TAB><text>", texts it replaces): the row takes the place of the id's
    first row and its other rows go; a new id is appended."""
    out, old = [], []
    for line in lines:
        name, sep, was = line.partition("\t")
        if sep and name.strip() == server:
            if not old:
                out.append(f"{server}\t{text}")
            old.append(was.strip())
        else:
            out.append(line)
    return (out if old else out + [f"{server}\t{text}"]), old


def add(server, address, text):
    if not ID.fullmatch(server):
        sys.exit(f"id '{server}': {ID_RULE}")
    address = address or last_connect()
    if not address:
        sys.exit("no address given and no connect in the game's log")
    name = hostname(address)
    if not name:
        sys.exit(f"{address} doesn't answer")
    text = text or guess(name)
    if not text or "\t" in text or identify(name, [(server, text)]) != server:
        sys.exit(f"the server's name doesn't contain '{text}': {name}")
    CONFIGS.mkdir(parents=True, exist_ok=True)
    lines = SERVERS.read_text("latin1").splitlines() if SERVERS.exists() else \
        ["# <id><TAB><text in the server name>, the first matching row wins (docs/serverconfigs.md)"]
    lines, old = with_row(lines, server, text)
    if old and old != [text]:
        print(f"⚠️  '{server}' is in {SERVERS.name} already, with: {' | '.join(old)}", file=sys.stderr)
        if not sys.stdin.isatty() or input(f"Replace with '{text}'? [y/N] ").strip().lower() != "y":  # no terminal: nobody to ask
            sys.exit(f"{SERVERS.name} unchanged")
    write_atomic(SERVERS, "\n".join(lines) + "\n")
    cfg = CONFIGS / f"{server}.cfg"
    if not cfg.exists():
        cfg.write_text(f"// Settings on the servers of '{server}' (docs/serverconfigs.md): absolute values only, and every name set here gets its normal value in default.cfg\n", "latin1")
    remember(adr_string(resolve(address)), name)
    print(f"{name}\n{SERVERS.relative_to(REPO)}: {server}\t{text}\n{cfg.relative_to(REPO)}")
    first = identify(name, servers())
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
            elif target != done:  # end of the log: act on the last event only, not on every connect of a replay
                done, wait = target, None if attempt(target) else pauses()
                due = time.monotonic() + next(wait) if wait else 0
            elif wait and time.monotonic() >= due:  # between the tries the log is followed on, so a new connect is not held up
                wait = None if attempt(target) else wait
                due = time.monotonic() + next(wait) if wait else 0
    except KeyboardInterrupt:
        pass
    finally:  # without the tool nobody corrects the files: a game started without it must find no server's settings
        with contextlib.suppress(OSError):
            write(None)


def selftest():
    assert event("       0 192.0.2.7:27980 resolved to 192.0.2.7:27980\n") == "192.0.2.7:27980"
    assert event("  165000 my.server.org resolved to 192.0.2.1:27960\n") == "192.0.2.1:27960"
    assert event("       0 [2001:db8::1]:27961 resolved to [2001:db8::1]:27961\n") == "[2001:db8::1]:27961"
    assert event("       0 MOTD: resolving motd.example.org... resolved to 192.0.2.9:27951\n") is None
    assert event("       0 localhost resolved to loopback\n") is None and event("       0 Server: fueldump\n") is None
    assert event("    1200 ----- Server Initialization ----\n") == "local"

    with tempfile.TemporaryDirectory() as d:
        out, note = Path(d), "  // crosshair color on this map (HOME), saved by tools/serverconfig.py"
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
    assert xy[5:] == ["// Address: - a", 'set serverRestartAdopt "set serverRestartLast vstr serverRestart_a"',
                      'set serverRestart "vstr serverRestartAdopt; snd_restart"', 'set serverRestart_a "vstr null"',
                      "vstr serverRestartLast", 'set serverRestart_a "vstr serverRestart"']
    assert f'set serverApply "execq {EXEC}/default.cfg; set serverLast vstr serverIs_default"' in settings_cfg("default")
    assert vsay_cfg(None, None).count("\n") == 1 and vsay_cfg(None, None).startswith("//")
    nav = MENU["nav"]
    assert vsay_cfg("xy", "^1[^7xY^1]").splitlines()[1:] == [f'echo "{nav}TAB ^1[^7xY^1]{nav} Voice chat"', f'bind TAB "execq {VOICE_EXEC}/xy/xy.cfg"']

    with tempfile.TemporaryDirectory() as d:
        out, voice = Path(d) / "serverconfigs", Path(d) / "voice"
        rows = [("xy", "[xY]"), ("solo", "Solo Server")]
        assert write(None, out=out, voice=voice) == ("default", None)
        assert (out / "current.cfg").read_text() == settings_cfg("default") and (out / "current_vsay.cfg").read_text() == vsay_cfg(None, None)
        assert write("xy", "^1[^7xY^1] x", rows, out, voice) == ("default", None)  # neither a cfg nor voice pages yet
        (out / "xy.cfg").write_text("set fovLow 100\ncg_fov 100 // x\nbind F9 \"vstr a; cg_drawFPS 1\"\n\nvstr hook\n// com_maxfps 1\nseta \"r_gamma\" 2\n")
        (voice / "xy").mkdir(parents=True)
        (voice / "xy/xy.cfg").write_text("")
        (voice / "solo").mkdir()
        (voice / "solo/solo.cfg").write_text("")
        assert write("xy", '^1[^7xY"^1] x', [("xy", '[xY"]')], out, voice) == ("xy", "xy")
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
    tsv = ["# head", "xy\t[xY]", "sn\tSOME", "abc\tABc|", "sn\tSOME NAME"]
    assert with_row(tsv, "sn", "Name") == (["# head", "xy\t[xY]", "sn\tName", "abc\tABc|"], ["SOME", "SOME NAME"])
    assert with_row(tsv, "new", "x y") == (tsv + ["new\tx y"], []) and with_row(tsv, "xy", "[xY]")[1] == ["[xY]"]
    wait = pauses()
    assert [next(wait) for _ in range(7)] == [2, 4, 8, 16, 32, 60, 60]
    assert ask("192.0.2.1:27960", lambda address: "") is False  # no answer: nothing is written
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
    assert unreset("cg_fov 1\ncg_fov 2\nexec x.cfg\nwait 5", "my_cg_fov 1") == ["cg_fov"]
    print("selftest ok")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", nargs="?", choices=["add"])
    ap.add_argument("id", nargs="?")
    ap.add_argument("address", nargs="?", help="host[:port], default: the last connect in the game's log")
    ap.add_argument("--match", metavar="TEXT", help="text in the server's name, default: the tag at its start")
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
        return add(a.id, a.address, a.match)
    run()


if __name__ == "__main__":
    main()
