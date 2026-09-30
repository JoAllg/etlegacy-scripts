#!/usr/bin/env python3
"""Open the keymap in the browser and follow the class picked in the running game.

The game is found by the most recently written <HOMEPATH>/<mod>/etconsole.log (HOMEPATH of
settings.conf); views and names always come from this repo. The game needs `logfile 2`, `logfile 1`
buffers the log in 4 KB chunks. The page polls /state, see keymap.py PAGE.

Usage: python3 live.py [--mod <mod>, default KEYMAP_MOD of settings.conf] [--port 27999] [--selftest]
"""
import argparse
import json
import re
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import keymap

DLL = re.compile(r"Sys_LoadDll\(.*/([^/]+)/(?:ui|cgame)\.mp\.")  # the module's folder is the running mod
BASE_MARKERS = {"*CLASSES CLEANED*", ">>> AUTOEXEC LOADED!"}  # classReset and autoexec.cfg (unbindall) bring back Base binds
STAMP = re.compile(r"^ *\d+ ")  # game time column of every log line


def clean(text):
    return re.sub(r"\^.", "", text).strip()


def class_echoes(con):
    """echo text -> "<class>_<weapon>", from every alias that runs a cs_<class>_<weapon> alias and an echo alias."""
    out = {}
    for value, _ in con.cvars.values():
        targets = [a[1].lower() for a in (keymap.tokenize(c) for _, c in keymap.split_commands(value))
                   if len(a) > 1 and a[0].lower() == "vstr"]
        classes = [m.groups() for m in map(keymap.CLASS_ALIAS.match, targets) if m]
        echoes = [keymap.tokenize(con.cvars[t][0]) for t in targets if t in con.cvars]
        echoes = [" ".join(e[1:]) for e in echoes if e and e[0].lower() == "echo"]  # engine echo: Cmd_Args
        if classes and echoes:
            out[clean(echoes[0])] = "_".join(classes[0])
    return out


class Follower:
    def __init__(self, mod):
        self.cache = {}  # mod -> (mod, page, echoes); keymap.build takes ~2 s
        self.cls = None
        self.use(mod)

    def use(self, mod):
        if mod not in self.cache:
            con, data, _, used = keymap.build(mod)
            self.cache[mod] = (mod, keymap.page(mod, data, used).encode(), class_echoes(con))
        self.current = self.cache[mod]  # one assignment, so the server never pairs a mod with another mod's page

    def feed(self, line):
        text = clean(STAMP.sub("", line))  # whole line must match, so /cvarlist dumps of the aliases don't count
        mod = DLL.search(text)
        if mod and mod[1] != self.current[0] and (keymap.GAME / mod[1] / "autoexec.cfg").exists():
            self.use(mod[1])
        elif text in self.current[2]:
            self.cls = self.current[2][text]
        elif text in BASE_MARKERS:
            self.cls = None


def find_log():
    """Most recently written <HOMEPATH>/<mod>/etconsole.log (the engine writes it into fs_game), or None."""
    logs = []
    for path in keymap.GAME.glob("*/etconsole.log"):
        try:
            logs.append((path.stat().st_mtime, path))
        except OSError:
            continue
    return max(logs)[1] if logs else None


def follow(follower):
    while True:
        path = find_log()
        if not path:
            time.sleep(2)
            continue
        print(f"following {path}")
        with open(path, errors="replace") as log:  # from the start: the game truncates it at launch, replay restores the class
            line = ""
            while True:
                line += log.readline()
                if line.endswith("\n"):
                    follower.feed(line)
                    line = ""
                    continue
                time.sleep(.2)
                try:
                    if path.stat().st_size < log.tell() or find_log() != path:  # game restarted or another mod's log is newer
                        break
                except OSError:
                    break


def serve(follower, port):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            mod, page, _ = follower.current
            if self.path == "/state":
                body, kind = json.dumps({"mod": mod, "cls": follower.cls}).encode(), "application/json"
            else:
                body, kind = page, "text/html; charset=utf-8"
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()


def selftest():
    f = Follower("nitmod")
    assert f.current[2].get("[CLASS] Medic: Sten") == "medic_sten", f.current[2]
    for line, mod, cls in [
        ("       0 Sys_LoadDll(/home/x/.etlegacy/legacy/ui.mp.x86_64.so)... succeeded\n", "legacy", None),
        ("   52000 ^0[^nCLASS^0] ^nMedic^1: ^nSten\n", "legacy", "medic_sten"),
        ('    5600           ?  classReset    "vstr cs_default; echo ^2*^7CLASSES CLEANED^2*" - ""\n', "legacy", "medic_sten"),
        ("   53000 ^2*^7CLASSES CLEANED^2*\n", "legacy", None),
        ("   54000 ^0[^nCLASS^0] ^nSoldier^1: ^nMortar\n", "legacy", "soldier_mortar"),
        ("   55000 Sys_LoadDll(/home/x/.etlegacy/testmod/cgame.mp.x86_64.so)... succeeded\n", "legacy", "soldier_mortar"),
        ("       0 ^5>>> AUTOEXEC LOADED!\n", "legacy", None),
    ]:
        f.feed(line)
        assert (f.current[0], f.cls) == (mod, cls), (line, f.current[0], f.cls)
    print("selftest ok")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--mod", default=keymap.KEYMAP_MOD, help="page until the game log names the mod")
    ap.add_argument("--port", type=int, default=27999)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    follower = Follower(a.mod)
    serve(follower, a.port)
    webbrowser.open(f"http://127.0.0.1:{a.port}/")
    try:
        follow(follower)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
