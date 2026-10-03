#!/usr/bin/env python3
"""Render the live keybinds as keyboard + mouse with action names: tools/keymap/keymap.html

Runs the exec chain in a minimal emulator of the ET console, then simulates key presses and diffs the
bind table. Class overlays (cs_* aliases), toggles/cycles and menu layers (keys that rebind other keys)
are detected from that diff, so new scripts need no code here. Names come from labels.json
(bind command -> short name), maintained with the keymap skill (.claude/skills/keymap/SKILL.md).

Usage: python3 keymap.py [--mod <mod>, default KEYMAP_MOD of settings.conf] [--missing] [--selftest]
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from helpers.settings import HOMEPATH as GAME, KEYMAP_MOD, REPO as PROFILES  # noqa: E402  exec paths resolve in GAME/<mod>/ and GAME/etmain/ through the links of deploy.sh

# Scenario: state the views start from. Team + map autoexec, so the spawn selector layer (ENTER) is live.
START = "exec autoexec.cfg"
SCENARIO = "exec autoexec_fueldump.cfg; vstr teamAxis; exec autoexec_axis.cfg"  # ponytail: one map/team, spawn names of other maps not shown
CLASS_HOOK = "vstr classHook"  # runs cs_default, the binds every class starts with
CLASS_ALIAS = re.compile(r"cs_([a-z]+)_(\w+)$")  # cs_<class>_<weapon>, see docs/conventions.md
TAPS = 6  # presses per key: enough to walk through the longest toggle/cycle
MENU_MIN = 4  # distinct new actions on other keys that make a key a menu (voicechat 8, team keys 5); cycles win
MAX_DEPTH = 64  # vstr/exec nesting; the engine has no limit, this stops alias loops
# cfgs that tools write while the game runs (servermenu.py, serverconfig.py): they hold the favorite servers and the
# server joined last, which are no binds of the profile and must not end up in the versioned keymap.html
GENERATED = re.compile(r"(?:^|/)(?:servermenu/|serverconfigs/current)")
KEY_ALIASES = {"ALT": "LEFTALT", "CTRL": "LEFTCTRL", "SHIFT": "LEFTSHIFT"}  # cl_keys.c keynames[], same keynum


# ---- console emulator (src/qcommon/cmd.c, cvar.c, client/cl_keys.c, cgame/cg_consolecmds.c) ----

def split_commands(text):
    """Cbuf_Execute: break on newline, and on ; outside quotes and outside // comments."""
    out, start, quotes, comment = [], 0, 0, False
    for i, c in enumerate(text):
        if c == '"':
            quotes += 1
        if not quotes & 1 and text.startswith("//", i):
            comment = True
        if c in "\r\n" or (c == ";" and not quotes & 1 and not comment):
            out.append((start, text[start:i]))
            start, quotes = i + 1, 0
            if c != ";":
                comment = False
    out.append((start, text[start:]))
    return out


def tokenize(s):
    """Cmd_TokenizeString: quoted tokens, // comment ends the line (except after ':')."""
    args, i, n = [], 0, len(s)

    def comment_at(j):
        return s.startswith("//", j) and (j == 0 or s[j - 1] != ":")

    while True:
        while i < n and s[i] <= " ":
            i += 1
        if i >= n or comment_at(i):
            return args
        if s[i] == '"':
            j = s.find('"', i + 1)
            j = n if j < 0 else j
            args.append(s[i + 1:j])
            i = j + 1
            continue
        j = i
        while j < n and s[j] > " " and s[j] != '"' and not comment_at(j):
            j += 1
        args.append(s[i:j])
        i = j


def keyname(name):
    """Key_StringToKeynum: single char is lowercased, names are case-insensitive."""
    if len(name) == 1:
        return name.lower()
    name = name.upper()
    return KEY_ALIASES.get(name, name)


def halves(cmd):
    """What a key press runs: +vstr a b = vstr a (down), vstr b (up); other +buttons change no binds."""
    args = tokenize(cmd)
    if not args:
        return []
    if args[0].lower() == "+vstr":
        return [f"vstr {a}" for a in args[1:3]]
    return [] if cmd.startswith("+") else [cmd]


class Console:
    def __init__(self, mod):
        self.root = GAME / mod
        self.cvars = {}  # lowercase name -> (value, reset value = value at creation)
        self.binds = {}  # key -> command
        self.where = {}  # ("set", cvar) / ("bind", key) -> file:line
        self.read = set()  # cvars vstr'd since last clear
        self.written = set()  # cvars set by aliases (not by exec'd files) since last clear
        self.execs = 0
        self.files = {}

    def snapshot(self):
        return dict(self.cvars), dict(self.binds), dict(self.where)

    def restore(self, snap):
        self.cvars, self.binds, self.where = (dict(s) for s in snap)

    def run(self, text, where="", depth=0, lines=False):
        if depth > MAX_DEPTH:
            return
        for pos, cmd in split_commands(text):
            loc = f"{where}:{text.count(chr(10), 0, pos) + 1}" if lines else where
            self.execute(tokenize(cmd), loc, depth)

    def execute(self, args, where, depth):
        if not args:
            return
        cmd, argc = args[0].lower(), len(args)
        if cmd in ("exec", "execq") and argc > 1:
            self.exec_file(args[1], depth)
        elif cmd in ("set", "seta", "sets", "setu") and argc > 2:
            name = args[1].lower()
            reset = self.cvars[name][1] if name in self.cvars else " ".join(args[2:])
            self.cvars[name] = (" ".join(args[2:]), reset)
            self.where[("set", name)] = where
            if not self.execs:
                self.written.add(name)
        elif cmd == "reset" and argc == 2 and args[1].lower() in self.cvars:
            name = args[1].lower()
            self.cvars[name] = (self.cvars[name][1],) * 2
            if not self.execs:
                self.written.add(name)
        elif cmd == "vstr" and argc == 2:
            name = args[1].lower()
            self.read.add(name)
            if name in self.cvars:
                self.run(self.cvars[name][0], self.where.get(("set", name), ""), depth + 1)
        elif cmd == "bind" and argc > 2:
            key = keyname(args[1])
            self.binds[key] = " ".join(args[2:])
            self.where[("bind", key)] = where
        elif cmd == "unbind" and argc == 2:
            self.binds.pop(keyname(args[1]), None)
        elif cmd == "unbindall":
            self.binds.clear()
        # ponytail: wait, cvar commands and server-forced values are ignored; enough for binds, compare with /bindlist if a view looks wrong

    def exec_file(self, name, depth):
        if GENERATED.search(name):
            return
        name = name if "." in Path(name).name else name + ".cfg"
        path = self.root / name
        if not path.exists():  # the game's search path: mod folder, then etmain (map and team autoexecs)
            path = GAME / "etmain" / name
        if path not in self.files:
            try:
                self.files[path] = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                self.files[path] = None
        if self.files[path] is None:
            return
        real = path.resolve()
        shown = real.relative_to(PROFILES) if real.is_relative_to(PROFILES) else path.relative_to(GAME)
        self.execs += 1
        self.run(self.files[path], str(shown), depth + 1, lines=True)
        self.execs -= 1


# ---- simulation ----

def vstr_targets(cmd):
    """Aliases a bind calls directly (vstr / +vstr arguments)."""
    out = []
    for _, c in split_commands(cmd):
        args = tokenize(c)
        if args and args[0].lower() in ("vstr", "+vstr"):
            out += [a.lower() for a in args[1:3]]
    return out


def pointers(con, key):
    """Aliases one press of key reads (vstr, any depth) and sets itself: its own toggle/cycle/menu state,
    e.g. ENTER -> spawnSelector -> ... -> spawnSelector3."""
    start = con.snapshot()
    con.read, con.written = set(), set()
    for half in halves(con.binds.get(key, "")):
        con.run(half, con.where.get(("bind", key), ""))
    own = con.read & con.written
    con.restore(start)
    return own


def press(con, key, own, nested=False, baseline=None):
    """Tap a key TAPS times (or until the state is back at the start).
    Returns (mode, affects):
    - mode, first match (details: README.md):
      "cycle"  the press reads and sets an alias named cycle*, or an alias it reads takes more than 2 values
      "menu"   at least MENU_MIN other keys get distinct new actions (bind, or the alias their bind calls)
      "toggle" an alias the press reads takes 2 values, changed by more than one tap
    - affects: other keys whose binding changed, whose called alias changed or was set by a script, or whose
      own pointers (own: key -> pointers(), e.g. F4 resets ENTER's spawnSelector3) were set
      -> [(command, mode of that key in the state where it had that command, binds of that state)],
      e.g. MOUSE3 -> LEFTALT crouch toggle.
      nested: only the mode is needed (no modes of affected keys); baseline: binds of the view, so a key that
      closes a menu (spawn 1 restores the weapon binds) doesn't count those restored binds as new actions
    ponytail: one level deep, a layer inside a layer (voicechat category -> vsays) is not expanded."""
    start = con.snapshot()
    baseline = start[1] if baseline is None else baseline
    targets = {k: vstr_targets(c) for k, c in start[1].items() if k != key}
    values, affects = {}, {}  # pointer alias -> values seen
    flips = {}  # alias -> taps that changed it
    cycle = False  # read and set a cycle* alias, also to the same value (class with a single weapon variant)
    new_binds, new_aliases = {}, {}  # other key -> first new bind / first new values of its called aliases
    states = {}  # (other key, command) -> state where the key first had that command
    for _ in range(TAPS):
        tap, read = dict(con.cvars), set()  # values compared per tap: a hold key that sets an alias on down and resets it on up is no toggle
        for half in halves(con.binds.get(key, "")):
            con.read, con.written = set(), set()
            con.run(half, con.where.get(("bind", key), ""))
            read |= con.read
            cycle |= any(n.startswith("cycle") for n in con.read & con.written)
            for k in (set(con.binds) | set(start[1])) - {key}:
                cmd = con.binds.get(k, "")
                if norm(cmd) != norm(start[1].get(k, "")):
                    if cmd and norm(cmd) != norm(baseline.get(k, "")):
                        new_binds.setdefault(k, norm(cmd))
                else:
                    # written counts even with an unchanged value: team keys are menus also for the team already chosen,
                    # F4 resets a closed spawn menu
                    now = tuple(con.cvars.get(t, ("",))[0] for t in targets.get(k, ()))
                    if now != tuple(start[0].get(t, ("",))[0] for t in targets.get(k, ())) \
                            or con.written & set(targets.get(k, ())):
                        new_aliases.setdefault(k, now)  # menu: only the alias the bind calls directly
                    elif not con.written & own.get(k, set()):
                        continue
                if cmd not in affects.setdefault(k, []):
                    affects[k].append(cmd)
                    if not nested:
                        states[k, cmd] = con.snapshot()
        for n in read:
            old, new = tap.get(n, ("",))[0], con.cvars.get(n, ("",))[0]
            if old != new:
                values.setdefault(n, set()).update((old, new))
                flips[n] = flips.get(n, 0) + 1
        if (con.cvars, con.binds) == start[:2]:
            break
    modes, lands = {}, {}
    for (k, cmd), state in states.items():
        con.restore(state)
        modes[k, cmd] = press(con, k, {}, nested=True, baseline=start[1])[0] if cmd else ""
        lands[k, cmd] = frozenset(state[1].items())
    con.restore(start)
    if cycle or max(map(len, values.values()), default=0) > 2:
        mode = "cycle"
    elif max(len(set(new_binds.values())), len(set(new_aliases.values()))) >= MENU_MIN:
        mode = "menu"
    else:
        # a toggle flips its alias on every tap; a single change (MOUSE4 leaves the SMG: bankSMG) is no toggle
        mode = "toggle" if max(flips.values(), default=0) > 1 else ""
    return mode, {k: [(c, modes.get((k, c), ""), lands.get((k, c))) for c in v] for k, v in affects.items() if v}


def views(mod):
    """[(name, snapshot, [(class, weapon)])]: base state plus one per distinct class bind set (identical variants merged)."""
    con = Console(mod)
    con.run(START)
    con.run(SCENARIO)
    con.run(CLASS_HOOK)
    base = con.snapshot()
    groups = {}  # frozen binds -> [(class, weapon)]
    snaps = {}
    for alias in sorted(n for n in base[0] if CLASS_ALIAS.match(n)):
        con.restore(base)
        con.run(f"{CLASS_HOOK}; vstr {alias}")
        frozen = frozenset(con.binds.items())
        groups.setdefault(frozen, []).append(CLASS_ALIAS.match(alias).groups())
        snaps.setdefault(frozen, con.snapshot())
    def name(members):
        return " / ".join(f"{c.capitalize()}: {', '.join(w for k, w in members if k == c)}"
                          for c in sorted({c for c, _ in members}))

    same = groups.pop(frozenset(base[1].items()), [])
    out = [("Base" + (f" · {name(same)}" if same else ""), base, same)]
    return con, out + [(name(members), snaps[frozen], members) for frozen, members in groups.items()]


# ---- labels ----

def norm(cmd):
    return " ".join(cmd.lower().split())


def guess(cmd):
    args = tokenize(split_commands(cmd)[0][1]) or [""]
    name = args[1] if args[0].lower() in ("vstr", "+vstr") and len(args) > 1 else args[0].lstrip("+")
    name = re.sub(r"_?(ON|On)$", "", name)
    return re.sub(r"(?<=[a-z])(?=[A-Z0-9])", " ", name)


class Labels:
    def __init__(self, path):
        self.path = path
        raw = json.loads(path.read_text()) if path.exists() else {}
        self.map = {norm(k): v for k, v in raw.items()}
        self.raw_keys = {norm(k): k for k in raw}
        self.used, self.missing = set(), {}  # missing: norm cmd -> (cmd, [places])

    def __call__(self, cmd, place):
        n = norm(cmd)
        if n in self.map:
            self.used.add(n)
            return self.map[n], False
        self.missing.setdefault(n, (cmd, []))[1].append(place)
        return guess(cmd), True


def build(mod):
    con, vs = views(mod)
    labels = Labels(HERE / "labels.json")
    data = []
    base_binds = vs[0][1][1]
    view_of = {frozenset(snap[1].items()): i for i, (_, snap, _) in enumerate(vs)}  # a layer state that is a class view
    for name, snap, members in vs:
        con.restore(snap)
        keys, own = {}, {k: pointers(con, k) for k in con.binds}
        for key, cmd in sorted(con.binds.items()):
            mode, affects = press(con, key, own)
            label, guessed = labels(cmd, (name, key, con.where.get(("bind", key), "")))
            alt = {}
            for k, cmds in affects.items():
                alt[k] = [[labels(c, (name, f"{key} -> {k}", ""))[0] if c else "(unbound)", m, c, view_of.get(land, -1)]
                          for c, m, land in cmds]
            keys[key] = {"l": label, "c": cmd, "w": con.where.get(("bind", key), ""), "g": guessed,
                         "h": cmd.startswith("+"),  # hold command: active while the key is down
                         "t": mode, "a": alt, "x": norm(cmd) != norm(base_binds.get(key, ""))}
        data.append({"name": name, "keys": keys, "m": [f"{c}_{w}" for c, w in members]})  # live.py selects by member
    used = {k: v["keys"][k]["l"] for v in data for k in v["keys"]}
    data.append({"name": "Free keys", "names": "free", "keys": {}})
    data.append({"name": "All keys", "names": "all", "keys": {}})
    return con, data, labels, used


# ---- render ----

U = 58  # px per key unit
# rows of (legend, bind name or None, width); legend "" = gap of that width. German ISO QWERTZ, docs/keybinds.md
ROWS = [
    (0, [("Esc", "ESCAPE", 1), ("", 0, 1)] + [(f"F{i}", f"F{i}", 1) for i in range(1, 5)] + [("", 0, .5)]
     + [(f"F{i}", f"F{i}", 1) for i in range(5, 9)] + [("", 0, .5)] + [(f"F{i}", f"F{i}", 1) for i in range(9, 13)]
     + [("", 0, .25), ("Druck", "PRINT", 1), ("Rollen", "SCROLLOCK", 1), ("Pause", "PAUSE", 1)]),
    (1.5, [("^", "CONSOLE", 1)] + [(c, c, 1) for c in "1234567890"] + [("ß", "US_MINUS", 1), ("´", "US_EQUALS", 1),
     ("⌫", "BACKSPACE", 2), ("", 0, .25), ("Einfg", "INS", 1), ("Pos1", "HOME", 1), ("Bild↑", "PGUP", 1),
     ("", 0, .25), ("Num", "KP_NUMLOCK", 1), ("/", "KP_SLASH", 1), ("*", "KP_STAR", 1), ("-", "KP_MINUS", 1)]),
    (2.5, [("Tab", "TAB", 1.5)] + [(c.upper(), c, 1) for c in "qwertzuiop"] + [("Ü", "US_LEFTBRACKET", 1),
     ("+", "+", 1), ("", 0, 1.5), ("", 0, .25), ("Entf", "DEL", 1), ("Ende", "END", 1), ("Bild↓", "PGDN", 1),
     ("", 0, .25), ("7", "KP_HOME", 1), ("8", "KP_UPARROW", 1), ("9", "KP_PGUP", 1)]),
    (3.5, [("Caps", "CAPSLOCK", 1.75)] + [(c.upper(), c, 1) for c in "asdfghjkl"] + [("Ö", "US_SEMICOLON", 1),
     ("Ä", "US_APOSTROPHE", 1), ("#", "#", 1), ("", 0, 4.75), ("4", "KP_LEFTARROW", 1), ("5", "KP_5", 1),
     ("6", "KP_RIGHTARROW", 1)]),
    (4.5, [("⇧", "LEFTSHIFT", 1.25), ("<", "<", 1)] + [(c.upper(), c, 1) for c in "yxcvbnm"] + [(",", ",", 1),
     (".", ".", 1), ("-", "-", 1), ("⇧", "RIGHTSHIFT", 2.75), ("", 0, 1.25), ("↑", "UPARROW", 1), ("", 0, 1.25),
     ("1", "KP_END", 1), ("2", "KP_DOWNARROW", 1), ("3", "KP_PGDN", 1)]),
    (5.5, [("Strg", "LEFTCTRL", 1.25), ("Win", "WINDOWS", 1.25), ("Alt", "LEFTALT", 1.25), ("Space", "SPACE", 6.25),
     ("AltGr", "MODE", 1.25), ("Win", None, 1.25), ("Menu", "COMPOSE", 1.25), ("Strg", "RIGHTCTRL", 1.25),
     ("", 0, .25), ("←", "LEFTARROW", 1), ("↓", "DOWNARROW", 1), ("→", "RIGHTARROW", 1), ("", 0, .25),
     ("0", "KP_INS", 2), (",", "KP_DEL", 1)]),
]
# (legend, bind name, x, y, w, h): keys that are not a plain row cell
EXTRA = [("Enter", "ENTER", 13.75, 2.5, 1.25, 2), ("+", "KP_PLUS", 21.5, 2.5, 1, 2), ("Enter", "KP_ENTER", 21.5, 4.5, 1, 2)]
MOUSE = [
    ("M1", "MOUSE1", 1.25, .1, 1.75, 2.5), ("M2", "MOUSE2", 4.5, .1, 1.75, 2.5),
    ("▲", "MWHEELUP", 3.0, .1, 1.5, .8), ("M3", "MOUSE3", 3.0, .95, 1.5, .8), ("▼", "MWHEELDOWN", 3.0, 1.8, 1.5, .8),
    ("M5", "MOUSE5", 0, .9, 1.15, 1), ("M4", "MOUSE4", 0, 2.0, 1.15, 1),
]
KEYBOARD_SIZE = (22.5, 6.5)  # units
MOUSE_SIZE = (6.4, 4.3)
# Engine behavior no cfg can change (src/sdl/sdl_input.c IN_IsConsoleKey, src/client/cl_keys.c CL_KeyEvent):
# the key left of 1 and the characters in cl_consoleKeys ("~ ` 0x7e 0x60") become the console key before binds
# are looked up; Shift+Esc toggles the console too
ENGINE_KEYS = {"CONSOLE": {"l": "Console", "c": "console key, can't be rebound (engine, see docs/keybinds.md)",
                           "w": "src/sdl/sdl_input.c IN_IsConsoleKey", "g": False, "t": "engine", "a": {}, "x": False}}
ENGINE_COMBOS = [["Shift+Esc", "Console"]]
COMBO_KEYS = {"`": "Shift+´", "~": "AltGr++"}  # German layout: keys typing a character bound as key


def layout():
    cells = []
    for y, row in ROWS:
        x = 0
        for legend, name, w in row:
            if legend:
                cells.append((legend, name, x, y, w, 1))
            x += w
    return cells + EXTRA


def svg(cells, size, label, extra="", style=""):
    width, height = size[0] * U + 8, size[1] * U + 8
    out = [f'<svg viewBox="-4 -4 {width} {height}" role="img" aria-label="{label}"{style}>', extra]
    for legend, name, x, y, w, h in cells:
        attr = f' data-key="{html.escape(name)}" data-w="{w}" data-h="{h}"' if name else ' data-w="0"'
        out.append(f'<g class="key"{attr} transform="translate({x * U + 2},{y * U + 2})"><title></title>'
                   f'<rect width="{w * U - 4}" height="{h * U - 4}" rx="6"/>'
                   f'<text class="legend" x="5" y="12">{html.escape(legend)}</text>'
                   f'<text class="label" x="{(w * U - 4) / 2}" y="{(h * U - 4) / 2 + 6}"></text>'
                   f'<text class="icon" x="{w * U - 9}" y="12"></text></g>')
    return "\n".join(out + ["</svg>"])


def boards():
    """Keyboard at full width; mouse below at the same scale (its width as share of the keyboard's)."""
    share = (MOUSE_SIZE[0] * U + 8) / (KEYBOARD_SIZE[0] * U + 8) * 100
    body = f'<rect class="mouse" x="{.75 * U}" y="0" width="{5.65 * U}" height="{4.2 * U}" rx="{1.4 * U}"/>'
    return (svg(layout(), KEYBOARD_SIZE, "Keyboard binds"),
            svg(MOUSE, MOUSE_SIZE, "Mouse binds", body, f' class="mouse-svg" style="width:{share:.2f}%;min-width:{share * 11:.0f}px"'))


PAGE = """<title>Taranis Keymap</title>
<style>
/* contrast: --muted/--accent carry small text (9-11px), so both stay >= 6:1 on their background */
:root{--panel:#e7e5de;--bg:#f3f2ee;--fg:#17181a;--muted:#5b5c61;--key:#fff;--edge:#adaca5;--accent:#076970;--changed:#ffe9a6;--hl:#c9efec;--mouse:#dedcd4}
/* both dark blocks must stay identical: the media query only applies before a theme was picked */
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--panel:#1d2026;--bg:#131519;--fg:#f0f1f4;--muted:#a3a7b1;--key:#272b32;--edge:#545963;--accent:#45d0d4;--changed:#55471a;--hl:#15494a;--mouse:#1f2229}}
:root[data-theme=dark]{--panel:#1d2026;--bg:#131519;--fg:#f0f1f4;--muted:#a3a7b1;--key:#272b32;--edge:#545963;--accent:#45d0d4;--changed:#55471a;--hl:#15494a;--mouse:#1f2229}
body{background:var(--bg);color:var(--fg);font:14px system-ui,sans-serif;padding-inline:16px;padding-block:12px}
h1{font-size:18px;margin:0}
.top{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:16px;margin-bottom:12px}
.search{position:relative;flex:1;min-width:220px;max-width:460px}
#search{width:100%;box-sizing:border-box;font:inherit;border:1px solid var(--edge);background:var(--key);color:var(--fg);border-radius:8px;padding:7px 34px 7px 11px}
#clear{position:absolute;right:4px;top:50%;translate:0 -50%;font:16px/1 system-ui,sans-serif;border:0;background:none;color:var(--muted);border-radius:6px;padding:5px 8px;cursor:pointer}#clear:hover{color:var(--fg);background:var(--hl)}
#results{position:absolute;z-index:5;left:0;right:0;top:calc(100% + 4px);max-height:70vh;overflow:auto;padding:6px;background:var(--panel);border:1px solid var(--edge);border-radius:10px;box-shadow:0 8px 24px #0005}
#results h3{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--accent);margin:8px 6px 4px}#results p{margin:6px;color:var(--muted)}
.hit{display:grid;grid-template-columns:auto 1fr;gap:0 10px;align-items:center;width:100%;text-align:left;font:inherit;color:var(--fg);background:none;border:0;border-radius:6px;padding:5px 6px;cursor:pointer}
.hit>*{min-width:0}.hit .sw{grid-row:span 2}.hit small{color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.hit:hover,.hit:focus{background:var(--hl);outline:none}.hit.pinned{box-shadow:inset 0 0 0 2px var(--accent)}
.top small{color:var(--muted);font-weight:400}
#theme{font:16px/1 system-ui,sans-serif;border:1px solid var(--edge);background:var(--key);color:var(--fg);border-radius:8px;padding:7px 11px;cursor:pointer}
.classes{display:flex;flex-wrap:wrap;gap:12px 28px;justify-content:space-between;border:1px solid var(--edge);border-radius:10px;padding:8px 12px 10px;margin-bottom:16px;background:var(--panel)}
.classes h2{font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--accent);margin:0 0 6px}
nav{display:flex;flex-wrap:wrap;gap:6px}
nav button{font:inherit;border:1px solid var(--edge);background:var(--key);color:var(--fg);border-radius:6px;padding:4px 10px;cursor:pointer}
nav button[aria-pressed=true]{background:var(--changed);border-color:color-mix(in srgb,var(--changed) 60%,var(--fg));font-weight:600}
.wrap{overflow-x:auto}.wrap svg{min-width:1100px}svg{width:100%;display:block}
.lower{display:flex;flex-wrap:wrap;align-items:flex-start;justify-content:space-between;gap:32px;margin-top:40px}
.lower svg.mouse-svg{flex:none}
aside{max-width:340px;border-left:1px solid var(--edge);padding-left:20px}
aside h2.combos{margin-top:20px}aside h2{font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin:0 0 8px}
aside ul{list-style:none;margin:0;padding:0;display:grid;gap:8px}
aside li{display:flex;align-items:center;gap:10px;color:var(--fg)}aside li[hidden]{display:none}
.sw{flex:none;width:28px;height:20px;border:1px solid var(--edge);border-radius:4px;background:var(--key);display:grid;place-items:center;color:var(--accent);font-size:13px}
.sw.changed{background:var(--changed)}.sw.combo{width:auto;padding:0 6px;font-size:12px;color:var(--fg);white-space:nowrap}.sw.guess{border:1px dashed var(--accent)}.sw.unbound{opacity:.7}.sw.hl{background:var(--hl);border:2px solid var(--accent)}.sw.dim{opacity:.62}.sw.keyname{color:var(--fg);font-size:10px;font-weight:600}.sw.hover{border:1.5px solid color-mix(in srgb,var(--accent) 55%,var(--edge))}
.mouse{fill:var(--mouse)}
.key rect{fill:var(--key);stroke:var(--edge);stroke-width:1.2;transition:opacity .1s}
.key text{fill:var(--fg);font-size:10px;pointer-events:none}
.key .legend{fill:var(--muted);font-size:10px}.key .label{text-anchor:middle;font-weight:600}
.key .icon{fill:var(--accent);font-size:11px;text-anchor:end}
.key.unbound .label{display:none}.key.unbound rect{opacity:.7}
.key.dim{opacity:.62}
.key.changed rect{fill:var(--changed)}
.key.hover rect{stroke:color-mix(in srgb,var(--accent) 55%,var(--edge));stroke-width:1.5}
.key.guess rect{stroke-dasharray:4 3;stroke:var(--accent)}
.focus .key:not(.hl):not(.src){opacity:.38}
.key.hl rect{fill:var(--hl);stroke:var(--accent);stroke-width:2}.key.src rect{stroke:var(--accent);stroke-width:2}
</style>
<header class="top"><h1>Taranis keymap <small>MOD</small></h1>
<div class="search"><input id="search" type="text" autocomplete="off" placeholder="Search key or script (e.g. F5, revive, weaponSwitch)" aria-label="Search key or script">
<button id="clear" type="button" title="Clear search and selection" aria-label="Clear search and selection" hidden>✕</button>
<div id="results" hidden></div></div>
<button id="theme" type="button" title="Switch light / dark" aria-label="Switch light / dark">☾</button></header>
<section class="classes"><div><h2>Class settings</h2><nav aria-label="Class settings"></nav></div>
<div><h2>View</h2><nav class="extra" aria-label="Other views"></nav></div></section>
<div class="board"><div class="wrap">KEYBOARD</div>
<div class="lower">MOUSE
<aside><h2>Legend</h2><ul>
<li data-when="binds"><span class="sw changed"></span>Bind differs from Base (in a class tab)</li>
<li data-when="binds"><span class="sw">⇄</span>Toggle: switches between 2 states</li>
<li data-when="binds"><span class="sw">⟳</span>Cycle: steps through values</li>
<li data-when="binds"><span class="sw">☰</span>Menu: gives other keys a list of options</li>
<li data-when="binds"><span class="sw">⤓</span>Hold: works while the key is held</li>
<li data-when="binds"><span class="sw hover"></span>Has a hover function: rebinds or resets other keys</li>
<li data-when="binds"><span class="sw hl"></span>Hover a key: keys it rebinds or resets, all others dimmed</li>
<li data-when="binds"><span class="sw guess"></span>No name yet (keymap skill)</li>
<li data-when="binds"><span class="sw unbound"></span>Unbound</li>
<li data-when="free"><span class="sw hl"></span>Still free</li>
<li data-when="free"><span class="sw dim keyname">Tab</span>Already in use</li>
<li data-when="all"><span class="sw keyname">Tab</span>In-game bind name of every key</li>
<li><span class="sw">🔒</span>Engine key, can't be rebound</li>
</ul>
<h2 class="combos">Combinations &amp; other keys</h2><ul id="combos"></ul></aside>
</div></div>
<script id="data" type="application/json">DATA</script>
<script>
const root = document.documentElement, themeBtn = document.getElementById('theme');
const setTheme = t => {
  root.dataset.theme = t;
  themeBtn.textContent = t === 'dark' ? '\u2600' : '\u263e';
  try { localStorage.setItem('keymapTheme', t); } catch {}  // file:// may block storage
};
let savedTheme = null;
try { savedTheme = localStorage.getItem('keymapTheme'); } catch {}
setTheme(savedTheme || (matchMedia('(prefers-color-scheme:dark)').matches ? 'dark' : 'light'));
themeBtn.onclick = () => setTheme(root.dataset.theme === 'dark' ? 'light' : 'dark');
const D = JSON.parse(document.getElementById('data').textContent);
const board = document.querySelector('.board'), nav = document.querySelector('nav');
const els = [...board.querySelectorAll('.key[data-key]')];
const byKey = Object.fromEntries(els.map(g => [g.dataset.key, g]));
const ICONS = {toggle: '⇄', cycle: '⟳', menu: '☰', engine: '🔒'};
const icon = k => ICONS[k.t] || (k.h ? '⤓' : '');
const altIcon = ([, m, c]) => ICONS[m] || (c.startsWith('+') ? '⤓' : '');  // layer entry [name, mode, command]: same rule as icon()
let view = 0, home = 0, pinned = null;  // home: view picked by tab/live.py; pinned: search result kept on the keyboard
function fill(g, text) {
  const t = g.querySelector('.label'), w = +g.dataset.w, h = +g.dataset.h, per = Math.max(5, Math.floor(w * 10.5));
  const lines = [];
  for (const word of String(text).split(/\\s+/)) {
    if (lines.length && (lines.at(-1) + ' ' + word).length <= per) lines[lines.length - 1] += ' ' + word;
    else lines.push(word);
  }
  const max = h > 1 ? 4 : 2, shown = lines.slice(0, max);
  if (lines.length > max) shown[max - 1] = shown[max - 1].slice(0, per - 1) + '…';
  t.textContent = '';
  const longest = Math.max(...shown.map(l => l.length));
  t.style.fontSize = longest > per ? `${Math.max(7, 10 * per / longest)}px` : '';
  shown.forEach((line, i) => {
    const s = document.createElementNS('http://www.w3.org/2000/svg', 'tspan');
    s.setAttribute('x', t.getAttribute('x'));
    s.setAttribute('dy', i ? '1.15em' : `${-(shown.length - 1) * 0.575}em`);
    s.textContent = line;
    t.appendChild(s);
  });
}
function render() {
  const V = D.views[view], keys = V.keys;
  board.classList.remove('focus');
  const kind = V.names || 'binds';  // legend entries that apply to this view
  document.querySelectorAll('aside li[data-when]').forEach(li => { li.hidden = li.dataset.when !== kind; });
  const combos = document.getElementById('combos');
  combos.textContent = '';
  const others = Object.keys(keys).filter(key => !byKey[key]).map(key => [D.comboKeys[key] ? `${D.comboKeys[key]} (${key})` : key, keys[key].l]);
  for (const [key, label] of [...D.engineCombos, ...others]) {
    const li = document.createElement('li'), sw = document.createElement('span');
    sw.className = 'sw combo';
    sw.textContent = key;
    li.append(sw, label);
    combos.appendChild(li);
  }
  for (const g of els) {
    const key = g.dataset.key;
    if (V.names) {  // key name views: "free" dims the keys in use, "all" shows every name equally
      const engine = !!D.engine[key], used = key in D.used, free = V.names === 'free';
      g.classList.remove('src', 'changed', 'guess', 'hover', 'unbound');
      g.classList.toggle('dim', free && (used || engine));  // keeps the name visible, unlike "unbound"
      g.classList.toggle('hl', free && !used && !engine);
      fill(g, key.replace(/_/g, '_ '));  // long names wrap after the underscore
      g.querySelector('.icon').textContent = engine ? ICONS.engine : '';
      g.querySelector('title').textContent = engine ? `${key}: can't be bound`
        : used ? `${key}: used by "${D.used[key]}"` : `${key}: free`;
      continue;
    }
    const k = keys[key] || D.engine[key];
    g.classList.remove('hl', 'src', 'dim');
    for (const [c, on] of [['unbound', !k], ['changed', k && k.x && view], ['guess', k && k.g], ['hover', k && Object.keys(k.a).length]]) g.classList.toggle(c, !!on);
    fill(g, k ? k.l : '');
    g.querySelector('.icon').textContent = k ? icon(k) : '';
    g.querySelector('title').textContent = k ? `${g.dataset.key}: ${k.c}\\n${k.w}` : `${g.dataset.key}: unbound`;
  }
}
for (const g of els) {
  g.addEventListener('mouseenter', () => {
    const k = D.views[view].keys[g.dataset.key];
    if (!k || !Object.keys(k.a).length) return;  // engine keys and the name view have no affects
    if (pinned) render();
    board.classList.add('focus');
    g.classList.add('src');
    for (const [key, labels] of Object.entries(k.a)) {
      const t = byKey[key];
      if (!t) continue;
      t.classList.add('hl');
      t.classList.remove('unbound');
      fill(t, [...new Set(labels.map(x => x[0]))].join(' / '));
      t.querySelector('.icon').textContent = labels.map(altIcon).find(Boolean) || '';  // icon in the new state
    }
  });
  g.addEventListener('mouseleave', restore);
}
function show(i) {
  view = i;
  document.querySelectorAll('nav button').forEach(x => x.setAttribute('aria-pressed', +x.dataset.view === view));
  render();
}
function select(i) {
  home = i;
  pinned = null;
  clear.hidden = !search.value;
  show(i);
}
function restore() {
  show(home);
  if (pinned) mark(pinned);
}

const extraNav = document.querySelector('nav.extra');
D.views.forEach((v, i) => {
  const b = document.createElement('button');
  b.textContent = v.name;
  b.dataset.view = i;
  b.onclick = () => select(v.names && view === i ? 0 : i);  // clicking the active view button again goes back to Base
  b.setAttribute('aria-pressed', i === 0);
  (v.names ? extraNav : nav).appendChild(b);
});
render();

// ---- search: every bind of every class view, plus what a key gets after pressing another key (one layer, like hover) ----
const binds = D.views.flatMap((v, i) => v.names ? [] : [i]);
const legend = Object.fromEntries(els.map(g => [g.dataset.key, g.querySelector('.legend').textContent]));
const keyText = key => {
  const l = legend[key] || D.comboKeys[key];
  return !l || l.toLowerCase() === key.toLowerCase() ? key : `${l} [${key}]`;
};
const same = (a, b) => !!b && a.toLowerCase().split(/\\s+/).join(' ') === b.toLowerCase().split(/\\s+/).join(' ');
const entries = new Map();  // key + branch + command -> {key, via, viaL, l, c, ic, views, to: views the press lands in}
function addEntry(i, key, l, c, ic, via, to = -1) {
  if (!c) return;  // unbound in that layer
  const viaL = via && D.views[i].keys[via].l, id = [key, via, viaL, l, c].join('|');  // same branch key can have another name per class
  if (!entries.has(id)) entries.set(id, {key, via, viaL, l, c, ic, views: [], to: []});
  const e = entries.get(id);
  if (!e.views.includes(i)) e.views.push(i);
  if (to >= 0 && !e.to.includes(to)) e.to.push(to);
}
for (const i of binds) for (const [key, k] of Object.entries({...D.engine, ...D.views[i].keys})) {
  addEntry(i, key, k.l, k.c, icon(k), '');
  for (const [t, alts] of Object.entries(k.a)) for (const alt of alts) {
    const [l, , c, to] = alt;
    // only resets that key (F4 -> ENTER) or brings back its Base bind (listed from Base already): no new function
    if (same(c, (D.views[i].keys[t] || {}).c) || same(c, (D.views[0].keys[t] || {}).c)) continue;
    addEntry(i, t, l, c, altIcon(alt), key, to);
  }
}
// a class bind and the layer entries of the class keys that lead to its views are one function:
// one result per class key, in the views that key lands in (Weapon 7: Engineer via KP_PGUP, Medic via KP_UPARROW)
for (const [eid, e] of [...entries]) {
  if (e.via || e.views.includes(0)) continue;  // Base binds need no key press
  const parts = new Map();  // via -> {viaL, views}
  for (const [id, x] of [...entries]) {
    const to = x.to.filter(i => e.views.includes(i));
    if (!x.via || x.key !== e.key || !same(x.c, e.c) || !to.length) continue;
    if (!parts.has(x.via)) parts.set(x.via, {viaL: x.viaL, views: new Set()});
    to.forEach(i => parts.get(x.via).views.add(i));
    entries.delete(id);
  }
  const rest = e.views.filter(i => ![...parts.values()].some(p => p.views.has(i)));
  if (rest.length) e.views = rest;
  else entries.delete(eid);
  for (const [via, p] of parts) entries.set(`${eid}|${via}`, {...e, via, viaL: p.viaL, views: [...p.views].sort((a, b) => a - b), to: []});
}
const allKeys = [...new Set([...els.map(g => g.dataset.key), ...[...entries.values()].map(e => e.key)])];
function fuzzy(q, s) {  // -1 = no match; a substring (best at a word start) beats scattered letters
  s = s.toLowerCase();
  const i = s.indexOf(q);
  if (i >= 0) return 200 - i - s.length / 10 + (i === 0 || !/[a-z0-9]/.test(s[i - 1]) ? 50 : 0);
  let j = 0, gaps = 0, last = -1;
  for (let k = 0; k < s.length && j < q.length; k++) {
    if (s[k] !== q[j]) continue;
    if (last >= 0) gaps += k - last - 1;
    last = k;
    j++;
  }
  return j < q.length || gaps > 4 * q.length ? -1 : 100 - gaps;
}
const where = e => (e.via ? `after ${keyText(e.via)} “${e.viaL}” · in ` : '')  // branch first, the view list can be long
  + (e.views.length === binds.length ? 'every class' : e.views.map(i => D.views[i].name).join(' | '));
const path = e => (e.via ? `${keyText(e.via)} ${e.viaL} ` : '')  // searchable branch + views; "every class" would match everything
  + (e.views.length === binds.length ? '' : e.views.map(i => D.views[i].name).join(' '));
function mark(e) {  // show a result on the keyboard: its key with the name it has there, the key that opens that layer
  board.classList.add('focus');
  const t = byKey[e.key], v = byKey[e.via];
  if (v) v.classList.add('src');
  if (!t) return;  // sidebar key: the result row names it
  t.classList.add('hl');
  t.classList.remove('unbound', 'dim');
  fill(t, e.l);
  t.querySelector('.icon').textContent = e.ic;
}
function spot(e) {
  show(e.views.includes(home) ? home : e.views[0]);
  mark(e);
}
const search = document.getElementById('search'), results = document.getElementById('results');
function row(e) {
  const b = document.createElement('button'), sw = document.createElement('span'), name = document.createElement('span'), small = document.createElement('small');
  b.type = 'button';
  b.className = 'hit' + (e === pinned ? ' pinned' : '');
  b.title = `${e.c}\\n${where(e)}`;
  sw.className = 'sw combo';
  sw.textContent = keyText(e.key);
  name.textContent = `${e.l} ${e.ic}`;
  small.textContent = where(e);
  b.append(sw, name, small);
  b.onmouseenter = b.onfocus = () => spot(e);
  b.onclick = () => {
    home = e.views.includes(home) ? home : e.views[0];
    pinned = e;
    clear.hidden = false;
    results.querySelectorAll('.hit').forEach(x => x.classList.toggle('pinned', x === b));
    restore();
  };
  return b;
}
function heading(text) {
  const h = document.createElement('h3');
  h.textContent = text;
  results.appendChild(h);
}
function find() {
  const words = search.value.toLowerCase().split(/\\s+/).filter(Boolean);
  results.textContent = '';
  results.hidden = !words.length;
  if (!words.length) return;
  // a key: everything bound to it, direct binds first
  const keys = words.length > 1 ? [] : allKeys.filter(k => [k, legend[k] || '', D.comboKeys[k] || ''].some(s => s.toLowerCase().startsWith(words[0])))
    .sort((a, b) => (b.toLowerCase() === words[0]) - (a.toLowerCase() === words[0]) || a.length - b.length).slice(0, 3);
  for (const key of keys) {
    heading(`Key ${keyText(key)}`);
    const on = [...entries.values()].filter(e => e.key === key).sort((a, b) => !!a.via - !!b.via || a.views[0] - b.views[0]);
    if (!on.length) results.insertAdjacentHTML('beforeend', '<p>unbound in every view</p>');
    on.forEach(e => results.appendChild(row(e)));
  }
  // a script: name, command (alias names) and the class/branch it lives in
  const hits = [];
  for (const e of entries.values()) {
    let total = 0;
    for (const w of words) {
      const sc = Math.max(fuzzy(w, e.l), fuzzy(w, e.c) - 30, fuzzy(w, path(e)) - 80);
      if (sc < 0) { total = -1; break; }
      total += sc;
    }
    if (total >= 0) hits.push([total, e]);
  }
  hits.sort((a, b) => b[0] - a[0]);
  if (hits.length) heading('Scripts & binds');
  hits.slice(0, 40).forEach(([, e]) => results.appendChild(row(e)));
  if (!keys.length && !hits.length) results.insertAdjacentHTML('beforeend', '<p>no match</p>');
}
const clear = document.getElementById('clear');
function unpin() {
  pinned = null;
  results.hidden = true;
  clear.hidden = !search.value;
  restore();
}
clear.onclick = () => {
  search.value = '';
  unpin();
  search.focus();
};
search.addEventListener('input', () => { clear.hidden = !search.value && !pinned; find(); });
search.addEventListener('focus', find);
results.addEventListener('mouseleave', restore);
results.addEventListener('focusout', ev => { if (!results.contains(ev.relatedTarget)) restore(); });
document.querySelector('.search').addEventListener('keydown', ev => {
  const hits = [...results.querySelectorAll('.hit')], i = hits.indexOf(document.activeElement);
  if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') {
    ev.preventDefault();
    const next = hits[i + (ev.key === 'ArrowDown' ? 1 : -1)];
    (next || search).focus();
  }
});
document.addEventListener('keydown', ev => { if (ev.key === 'Escape') unpin(); });
document.addEventListener('click', ev => { if (!ev.target.closest('.search')) results.hidden = true; });
if (location.protocol.startsWith('http')) {  // served by live.py: follow the class picked in game, manual clicks stay until the next change
  let last;
  setInterval(async () => {
    const s = await fetch('state').then(r => r.json()).catch(() => null);
    if (!s) return;
    if (s.mod !== D.mod) return location.reload();
    if (s.cls === last) return;
    last = s.cls;
    select(Math.max(0, D.views.findIndex(v => (v.m || []).includes(s.cls))));
  }, 500);
}
</script>
"""


def page(mod, data, used):
    keyboard, mouse = boards()
    out = PAGE.replace("MOD", html.escape(mod)).replace("KEYBOARD", keyboard).replace("MOUSE", mouse, 1)
    return out.replace("DATA", json.dumps({"mod": mod, "views": data, "engine": ENGINE_KEYS, "engineCombos": ENGINE_COMBOS,
                                           "comboKeys": COMBO_KEYS, "used": used}, ensure_ascii=False).replace("</", "<\\/"))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--mod", default=KEYMAP_MOD)
    ap.add_argument("--missing", action="store_true", help="list commands without label and unused labels")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest(a.mod)
    con, data, labels, used = build(a.mod)
    if a.missing:
        for n, (cmd, places) in sorted(labels.missing.items()):
            target = tokenize(cmd)
            expand = con.cvars.get(target[1].lower(), ("",))[0] if len(target) > 1 and "vstr" in target[0].lower() else ""
            where = next((w for _, _, w in places if w), "")
            seen = ", ".join(sorted({k for _, k, _ in places}))
            print(f"{cmd}\n    keys: {seen}\n    expands: {expand}\n    at: {where}")
        unused = sorted(labels.raw_keys[n] for n in set(labels.map) - labels.used)
        print(f"\n{len(labels.missing)} unlabeled, {len(unused)} unused label(s): {unused}")
        return
    (HERE / "keymap.html").write_text(page(a.mod, data, used))
    print(f"wrote {HERE / 'keymap.html'}: {len(data)} views, {len(labels.missing)} unlabeled commands")


def selftest(mod):
    assert [c for _, c in split_commands('bind x "kill;forcetapout"  // a;b')] == ['bind x "kill;forcetapout"  // a;b']
    assert tokenize('set a "b c" d // e') == ["set", "a", "b c", "d"]
    assert all(GENERATED.search(n) for n in ("profile/servermenu/p7_0.cfg", "profile/serverconfigs/current.cfg", "profile/serverconfigs/current_vsay.cfg"))
    assert not GENERATED.search("profile/serverconfigs/default.cfg") and not GENERATED.search("profile/scripts/servermenu.cfg")
    con, data, _, _ = build(mod)
    base = data[0]["keys"]
    assert base["MOUSE2"]["c"] == "vstr weaponSwitch", base["MOUSE2"]
    medic = next(v["keys"] for v in data if v["name"].startswith("Medic"))
    assert medic["MOUSE4"]["c"] == "+vstr weapon6Medpack_ON weapon6Medpack_OFF"
    assert {"1", "7", "TAB"} <= set(base["v"]["a"]), base["v"]
    spawn = base["ENTER"]["a"]  # fueldump axis: 4 spawnpoints, the other number keys are free while the menu is open
    assert spawn["4"][0][2] == "vstr spawnp3r" and spawn["5"][0][0] == "(unbound)" and "0" not in spawn, spawn
    assert "MOUSE2" in base["F5"]["a"] and base["F5"]["t"] == "cycle", base["F5"]
    scoped = next(v["keys"] for v in data if v["name"].startswith("Covops: fg42"))
    assert "MOUSE3" not in base, base["MOUSE3"]  # sniper mode only with a scope
    assert [x[:2] for x in scoped["MOUSE3"]["a"]["LEFTALT"]] == [["Crouch", "toggle"]], scoped["MOUSE3"]
    assert all(m != "menu" for k, alts in base["ENTER"]["a"].items() if k != "v" for _, m, *_ in alts), base["ENTER"]  # v: ENTER closes the voice chat (resetLayers)
    assert base["v"]["a"]["1"][0][1] == "menu", base["v"]  # a chat category opens its vsay list
    medic_i = next(i for i, v in enumerate(data) if v["name"].startswith("Medic"))
    assert base["KP_UPARROW"]["a"]["MOUSE4"][0][3] == medic_i, base["KP_UPARROW"]  # a class key lands in its class view
    assert scoped["MOUSE3"]["t"] == "toggle" and base["MOUSE2"]["t"] == "toggle", scoped["MOUSE3"]  # MOUSE2: pistols and back to the SMG
    assert scoped["MOUSE4"]["t"] == "" and scoped["MOUSE4"]["h"], scoped["MOUSE4"]  # hold: leaving the SMG once is no toggle
    assert all(base[k]["t"] == "menu" for k in ("v", "ENTER", "KP_END", "KP_PGDN")), base["KP_END"]
    assert all(base[k]["t"] == "cycle" for k in ("KP_HOME", "KP_UPARROW", "KP_PGUP", "KP_LEFTARROW", "KP_5"))
    assert base["KP_DOWNARROW"]["t"] != "menu" and base["KP_RIGHTARROW"]["t"] != "menu"
    assert "ENTER" in base["F4"]["a"] and "v" in base["F4"]["a"], base["F4"]
    con.run('set r_so1 "set cycleSoldier vstr r_so1; bind MOUSE4 a; bind MOUSE5 b; bind CAPSLOCK c; bind u d"')
    assert press(con, "KP_HOME", {})[0] == "cycle", "single weapon variant with 4 rebinds"
    print("selftest ok")


if __name__ == "__main__":
    main()
