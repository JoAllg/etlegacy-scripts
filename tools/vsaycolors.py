#!/usr/bin/env python3
"""Colors of the vsay texts (vsay / vsay_team <id> <text>, vsay_buddy <class> <n> [client ids] <id> <text>) and the chat texts
(say / say_team / say_teamnl / say_buddy <text>; not "say !command") in the profile cfgs, from the VSAY_* values of settings.conf.

  status              current colors and how many texts still need base/punctuation colors or a highlight review
  preview [role=^c]   tools/vsaycolors.html: current vs proposed colors (roles: team global buddy punct highlight urgent),
                      sample texts and the full palette
  apply               after a color change: codes of the old colors (last apply, RECORD) are replaced by the new ones;
                      texts without base/punctuation colors (and without highlights) are colored like voicemenu.py does;
                      server page echoes show their vsay's text without colors; echo menus (voice chat, spawn selector)
                      get the MENU_* colors; then lists the highlight todo
  todo                texts with base/punctuation colors but no highlight that were not reviewed yet
  done                marks all texts of the todo as reviewed (left plain on purpose)
  --selftest
"""
import argparse
import html
import re
from pathlib import Path

from helpers.common import COLOR, COLOR_CHAR, strip_colors
from helpers.settings import MENU, PROFILE, REPO, VSAY

LIVE = REPO / PROFILE
SKIP = {"etconfig.cfg"}  # game-generated
RECORD = LIVE / "scripts/vsays/vsaycolors.tsv"  # colors of the last apply + reviewed texts (cmd, id, plain text)
HTML = REPO / "tools/vsaycolors.html"
ROLES = ("team", "global", "buddy", "punct", "highlight", "urgent")
MENU_ROLES = ("head", "key", "text", "nav", "global", "axis", "allies")
MENU_DIRS = ("scripts/vsays", "scripts/spawn", "autoexecs")  # files with echo menus
ECHO = re.compile(r'(\becho "?)([^;"]+)')
# vsay_buddy (fireteam) needs the class (-1) and the target clients; VoiceFireTeamChat <id> takes no text
TEXT = re.compile(r'\b(vsay(?:_team)?|vsay_buddy(?: -?\d+)+) (\w+) ([^;"]+)')
# say at the start of a command (not a word of an echo text or an alias name); "say !stats", "say /cmd" are commands of the server
SAY = re.compile(r'((?:^|(?<!echo )"|;)\s*|\bset \w+ )(say(?:_team(?:nl)?|_buddy)?) (?![!/\\])([^;"]+)')
CODE = re.compile(rf"\^({COLOR_CHAR})")  # the code's character as group 1


def colorize(text, base, punct):
    """Server colors removed, base color on the words, punct on punctuation runs that end a word (not ":D", "(:");
    ; would split the bind."""
    text = strip_colors(text).replace(";", ",").strip()
    out, cur = "", None
    for i, part in enumerate(re.split(r"((?<=[\w'\")\]])[.,!?:]+(?=\s|$)\s*)", text)):
        if part:
            col = punct if i % 2 else base
            out, cur = out + ("" if col == cur else col) + part, col
    return out


def idx(c):
    """Color index of a code character (^x = ^X = ^8): (c - '0') & 31, like ColorIndex."""
    return (ord(c) - ord("0")) & 31


def base(cmd):
    return {"vsay_team": "team", "say_team": "team", "say_teamnl": "team", "vsay_buddy": "buddy", "say_buddy": "buddy"}.get(cmd.split()[0], "global")


def found(line):
    """[(cmd, id, text)] of a line; chat texts have no id ("")."""
    return [m.groups() for m in TEXT.finditer(line)] + [(m.group(2), "", m.group(3)) for m in SAY.finditer(line)]


def sub_texts(line, fn):
    """line with every text replaced by fn(cmd, id, text)."""
    line = TEXT.sub(lambda m: f"{m.group(1)} {m.group(2)} {fn(*m.groups())}", line)
    return SAY.sub(lambda m: f"{m.group(1)}{m.group(2)} {fn(m.group(2), '', m.group(3))}", line)


def plain(text):
    return strip_colors(text)


def chars(text):
    """[(char, color index)] of the visible non-space characters."""
    out, cur = [], None
    for m in re.finditer(rf"{CODE.pattern}|(.)", text, re.S):
        if m.group(1):
            cur = idx(m.group(1))
        elif not m.group(2).isspace():
            out.append((m.group(2), cur))
    return out


def highlighted(text, colors):
    hl = {idx(colors["highlight"][1]), idx(colors["urgent"][1])}
    return any(idx(c) in hl for c in CODE.findall(text))


def base_done(text, cmd, colors):
    """Same colors as colorize() gives, once the highlights count as base color."""
    hl = {idx(colors["highlight"][1]), idx(colors["urgent"][1])}
    flat = CODE.sub(lambda m: colors[base(cmd)] if idx(m.group(1)) in hl else m.group(0), text)
    return chars(flat) == chars(colorize(plain(text), colors[base(cmd)], colors["punct"]))


def remap(text, cmd, old, new):
    """Codes of the old role colors replaced by the new ones (highlights first: they may share a base color)."""
    table = {}
    for role in ("highlight", "urgent", "punct", base(cmd)):
        table.setdefault(idx(old[role][1]), new[role])
    return CODE.sub(lambda m: table.get(idx(m.group(1)), m.group(0)), text)


def menu_echo(text, menu, old=None, server=False):
    """Echo menu line in the menu colors: heading (ends with ":", a server tag "[..]" in front keeps its colors; on a
    server page the tag is everything in front of the last color code, as a tag may be any part of a server name),
    "<n>. item" or "TAB item"; other echoes unchanged. With old (menu colors of the last apply), an item keeps
    its role by its old color (global chat, spawnpoint owner); server pages pass none: their items are plain text."""
    # ponytail: the ":" of a heading follows a word ("FUN:", "... menu):"); one that ends a smiley ("(:", " ):", ")':") is an item's
    if re.search(r"\w\)?:$", plain(text).rstrip()):
        tag = (server and re.match(rf".*(?={COLOR}[^^]*$)", text)) or re.match(r".*\]\s*", text)
        tag = tag.group() if tag else ""
        if tag.count("[") > tag.count("]"):  # the last color code lies inside the tag's brackets: the tag ends behind them
            tag += re.match(r"[^\]]*\]?\s*", text[len(tag):]).group()
        return tag + menu["head"] + plain(text[len(tag):]).strip()
    m = re.match(rf"(?:{COLOR})*(TAB|\d+)\.?\s+(.*)", text, re.S)
    if not m:
        return text
    item = plain(m.group(2)).strip()
    if m.group(1) == "TAB":
        return f"{menu['nav']}TAB {item}"
    code = CODE.match(m.group(2))
    role = next((r for r in ("global", "axis", "allies") if old and code and idx(code.group(1)) == idx(old[r][1])), "text")
    return f"{menu['key']}{m.group(1)}. {menu[role]}{item}"


def files():
    return [f for f in sorted(LIVE.rglob("*.cfg")) if f.name not in SKIP and not f.is_symlink()]


def texts(f):
    """[(line number, cmd, id, text)] of the vsay and chat texts outside comments."""
    return [(n, *g) for n, line in enumerate(f.read_text(encoding="latin-1").splitlines())
            if not line.lstrip().startswith("//") for g in found(line)]


def read_record():
    """(vsay colors of the last apply or None, menu colors of the last apply, {(cmd, id, plain text)} reviewed)."""
    if not RECORD.exists():
        return None, dict(MENU), set()
    lines = RECORD.read_text(encoding="latin-1").splitlines()
    rec = dict(re.findall(r"(\w+)=(\S+)", lines[0])) if lines and lines[0].startswith("# colors") else None
    old = rec and {**VSAY, **{r: c for r, c in rec.items() if r in ROLES}}  # a role added since the last apply has no old color
    old_menu = {**MENU, **{r[5:]: c for r, c in (rec or {}).items() if r.startswith("menu_")}}
    return old, old_menu, {tuple(l.split("\t")) for l in lines if l and not l.startswith("#")}


def write_record(colors, menu, reviewed):
    head = "# colors " + " ".join([f"{r}={colors[r]}" for r in ROLES] + [f"menu_{r}={menu[r]}" for r in MENU_ROLES])
    body = sorted("\t".join(r) for r in reviewed)
    RECORD.write_text("\n".join([head, "# reviewed vsay texts (cmd, id, text without colors), kept plain on purpose", *body]) + "\n",
                      encoding="latin-1")


def todo(colors, reviewed):
    return [(f, n, cmd, vsay, text) for f in files() for n, cmd, vsay, text in texts(f)
            if base_done(text, cmd, colors) and not highlighted(text, colors) and (cmd, vsay.lower(), plain(text)) not in reviewed]


def fix_echoes(lines):
    """Server pages: the echo of a vsay key shows the text of its alias vsay<key> without colors (random vsays: their own text)."""
    binds = {m.group(1): m.group(2) for m in (re.match(r'set vsay(\S+) "vsay(?:_team)? \w+(?: ([^;"]*))?"', l) for l in lines) if m}
    out = []
    for line in lines:
        m = re.match(rf'echo "((?:{COLOR})*(\d)\.) (.*)"$', line)
        if m and m.group(2) in binds:
            line = f'echo "{m.group(1)} {plain(binds[m.group(2)] or m.group(3))}"'
        out.append(line)
    return out


def apply(colors):
    old, old_menu, reviewed = read_record()
    changed, irregular = [], []
    for f in files():
        lines = f.read_text(encoding="latin-1").splitlines()
        server = "servers" in f.parts
        for n, line in enumerate(lines):
            if line.lstrip().startswith("//"):
                continue

            def fix(cmd, vsay, text):
                new = remap(text, cmd, old, colors) if old and old != colors else text
                if not base_done(new, cmd, colors):
                    if highlighted(new, colors):
                        irregular.append(f"{f.relative_to(REPO)}:{n + 1} {cmd} {vsay} {new}")
                    else:
                        new = colorize(plain(new), colors[base(cmd)], colors["punct"])
                if new != text:
                    changed.append(f"{f.relative_to(REPO)}:{n + 1} {cmd} {vsay} {new}")
                return new
            lines[n] = sub_texts(line, fix)
        if server:
            lines = fix_echoes(lines)
        if any(d in f.relative_to(LIVE).as_posix() for d in MENU_DIRS):
            lines = [l if l.lstrip().startswith("//") else ECHO.sub(lambda m: m.group(1) + menu_echo(m.group(2), MENU, None if server else old_menu, server), l)
                     for l in lines]
        orig = f.read_text(encoding="latin-1")
        text = "\n".join(lines) + ("\n" if orig.endswith("\n") else "")
        if text != orig:
            f.write_text(text, encoding="latin-1")
    write_record(colors, MENU, reviewed)
    return changed, irregular


def render(text):
    """ET color string as HTML spans (hex from docs/colors.md)."""
    out, cur = [], PALETTE[7]
    for m in re.finditer(rf"{CODE.pattern}|([^^]+|\^)", text):
        if m.group(1):
            cur = PALETTE[idx(m.group(1))]
        else:
            out.append(f'<span style="color:{cur}">{html.escape(m.group(2))}</span>')
    return "".join(out)


def palette():
    rows = re.findall(r"^\| (\d+) \| `(#[0-9a-f]{6})`", (REPO / "docs/colors.md").read_text(), re.M)
    return {int(i): h for i, h in rows}


def samples_of(found_texts, colors):
    """Up to 6 highlighted texts per vsay command; a chat text counts for the vsay of its base color (say_teamnl -> vsay_team)."""
    samples = {c: [] for c in ("vsay_team", "vsay", "vsay_buddy")}
    for cmd, text in found_texts:
        key = {"team": "vsay_team", "buddy": "vsay_buddy"}.get(base(cmd), "vsay")
        if highlighted(text, colors) and len(samples[key]) < 6 and text not in samples[key]:
            samples[key].append(text)
    return samples


def preview(colors, proposed):
    samples = samples_of(((cmd, text) for f in files() for _, cmd, _, text in texts(f)), colors)
    if not samples["vsay_buddy"]:  # none written yet: the team texts in the buddy color
        samples["vsay_buddy"] = [remap(t, "vsay_team", colors, dict(colors, team=colors["buddy"])) for t in samples["vsay_team"][:3]]
    prefix = {"vsay_team": "^7(Player^7)^3(Location^3): ", "vsay": "^7Player^3: ", "vsay_buddy": "^7(Player^7)^3(Location^3): "}
    names = {"team": "vsay_team base", "global": "vsay base", "buddy": "vsay_buddy base", "punct": "punctuation", "highlight": "key word", "urgent": "urgent"}
    rows = "".join(f"<tr><td>{names[r]}</td><td><code>VSAY_{r.upper()}</code></td>"
                   + "".join(f'<td><span class="sw" style="background:{PALETTE[idx(c[r][1])]}"></span><code>{html.escape(c[r])}</code></td>'
                             for c in (colors, proposed)) + "</tr>" for r in ROLES)
    chat = "".join(f"<tr><td>{render(prefix[cmd] + t)}</td><td>{render(prefix[cmd] + remap(t, cmd, colors, proposed))}</td></tr>"
                   for cmd, ts in samples.items() for t in ts)
    grid = "".join(f'<div class="c"><span class="sw" style="background:{h}"></span><code>^{chr(48 + i)}</code> {h}</div>'
                   for i, h in sorted(PALETTE.items()))
    HTML.write_text(f"""<!doctype html><html><head><meta charset="utf-8"><title>Vsay colors</title><style>
body{{background:#1b1b1b;color:#ddd;font:15px system-ui,sans-serif;margin:24px}} table{{border-collapse:collapse;margin-bottom:24px}}
td,th{{padding:6px 12px;border-bottom:1px solid #333;text-align:left}} code{{font-family:monospace}}
.sw{{display:inline-block;width:14px;height:14px;margin-right:6px;vertical-align:middle;border:1px solid #555}}
.chat td{{background:#000;font-family:monospace;font-size:16px}} .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:6px}}
</style></head><body><h2>Vsay colors</h2><table><tr><th>Role</th><th>settings.conf</th><th>Current</th><th>Proposed</th></tr>{rows}</table>
<h3>Chat</h3><table class="chat"><tr><th>Current</th><th>Proposed</th></tr>{chat}</table>
<h3>Palette</h3><div class="grid">{grid}</div></body></html>
""")


def selftest():
    c = {"team": "^9", "global": "^l", "buddy": "^f", "punct": "^3", "highlight": "^x", "urgent": "^1"}
    assert TEXT.search('x "vsay_buddy -1 2 3 5 Medic ^fHeal me^3!; y"').groups() == ("vsay_buddy -1 2 3 5", "Medic", "^fHeal me^3!")
    assert base("vsay_buddy -1 0") == "buddy" and base_done("^fHeal ^1me^3!", "vsay_buddy -1 0", c)
    assert colorize("^4Can you do this? :D }:) (: 1.5 ok...", "^l", "^3") == "^lCan you do this^3? ^l:D }:) (: 1.5 ok^3..."
    assert base_done("^9I need ^1backup^3!", "vsay_team", c) and base_done("^9Clear the ^Xpath^3!", "vsay_team", c)
    assert not base_done("^4Hi!", "vsay", c) and not base_done("^lHi!", "vsay", c) and base_done("^lHi ^xyou^3!", "vsay", c)
    assert highlighted("^9I need ^8ammo^3!", c) and not highlighted("^9Hi^3!", c)
    new = dict(c, team="^7", highlight="^d")
    assert remap("^9Clear the ^xpath^3! ^1Now", "vsay_team", c, new) == "^7Clear the ^dpath^3! ^1Now"
    assert remap("^lHi ^xyou", "vsay", c, new) == "^lHi ^dyou"
    lines = ['echo "^31. old"', 'echo "2. ^lX (random)"', 'set vsay1 "vsay a ^lNew^3!"', 'set vsay2 "vsay b"', 'bind 1 "vstr vsay1; vstr resetLayers"']
    assert [m.groups() for l in lines for m in TEXT.finditer(l)] == [("vsay", "a", "^lNew^3!")]  # alias name and bind are no vsay texts
    says = ['set say-x "say_teamnl ^9Go ^xnow"', 'set a "vstr b; say_team Hi; echo say what"', 'set c "x; set classSay say_teamnl Hi there; echo y"',
            'echo "say cheese"', 'bind x "say !stats"', 'vstr say-x', 'set d "vsay Hi Hello"']
    assert [g for l in says for g in found(l)] == [("say_teamnl", "", "^9Go ^xnow"), ("say_team", "", "Hi"), ("say_teamnl", "", "Hi there"), ("vsay", "Hi", "Hello")]
    assert sub_texts(says[2], lambda cmd, vsay, text: text.upper()) == 'set c "x; set classSay say_teamnl HI THERE; echo y"'
    assert sub_texts(says[6], lambda cmd, vsay, text: text.upper()) == 'set d "vsay Hi HELLO"' and base("say_teamnl") == "team" and base("say") == "global"
    s = samples_of([("say_teamnl", "^9I will spawn at ^xBunker"), ("vsay_buddy -1 0", "^fHeal ^1me"), ("say", "^lHi ^xall"), ("say_team", "^9plain")], c)
    assert s == {"vsay_team": ["^9I will spawn at ^xBunker"], "vsay": ["^lHi ^xall"], "vsay_buddy": ["^fHeal ^1me"]}, s
    assert fix_echoes(lines)[:2] == ['echo "^31. New!"', 'echo "2. X (random)"']
    m = {"head": "^8", "key": "^3", "text": "^7", "nav": "^2", "global": "^6", "axis": "^i", "allies": "^d"}
    old_m = dict(m, **{"global": "^2"})
    assert menu_echo("^05.1 GLOBAL:", m, old_m) == "^85.1 GLOBAL:" and menu_echo("^9[^7xY^9] ^1FUN:", m) == "^9[^7xY^9] ^8FUN:"
    assert menu_echo("^?1. ^5Path cleared.", m, old_m) == "^31. ^7Path cleared." and menu_echo("^?5. ^2Global", m, old_m) == "^35. ^6Global"
    assert menu_echo("^n2 ^iBunker", m, old_m) == "^32. ^iBunker" and menu_echo("^?TAB ^2SECOND PAGE", m, old_m) == "^2TAB SECOND PAGE"
    assert menu_echo("^87. Never give you up!! (:", m) == "^37. ^7Never give you up!! (:" and menu_echo("More (not in the menu):", m) == "^8More (not in the menu):"
    assert menu_echo("^87. Aaaw ):", m) == "^37. ^7Aaaw ):" and menu_echo("^83. Don't kill me )':", m) == "^33. ^7Don't kill me )':"
    assert menu_echo("^vSO^7ME ^7NA^vME ^1FUN:", m, server=True) == "^vSO^7ME ^7NA^vME ^8FUN:"  # tag without brackets
    assert menu_echo("^9[^7xY^9] FUN:", m, server=True) == "^9[^7xY^9] ^8FUN:"  # no color code behind the tag: its bracket keeps its color
    assert menu_echo("^9[^7xY^9] ^1FUN:", m, server=True) == "^9[^7xY^9] ^8FUN:" and menu_echo("[x] FUN:", m, server=True) == "[x] ^8FUN:"
    assert menu_echo("^31. ^2Hi", m) == "^31. ^7Hi" and menu_echo("^5    *** CHAT LOADED!", m, old_m) == "^5    *** CHAT LOADED!"
    assert render("^1a^3b") == '<span style="color:#ff0000">a</span><span style="color:#ffff00">b</span>'
    print("selftest ok")


PALETTE = palette()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", nargs="?", choices=["status", "preview", "apply", "todo", "done"])
    ap.add_argument("roles", nargs="*", metavar="role=^c", help="preview only")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.command or (a.roles and a.command != "preview"):
        ap.error("one command; role=^c only with preview")
    args = [a.command, *a.roles]
    colors = dict(VSAY)
    old, old_menu, reviewed = read_record()
    if args == ["status"]:
        for r in ROLES:
            print(f"VSAY_{r.upper():<9} {colors[r]}  {PALETTE[idx(colors[r][1])]}" + (f"  (last apply: {old[r]})" if old and old.get(r) != colors[r] else ""))
        for r in MENU_ROLES:
            print(f"MENU_{r.upper():<9} {MENU[r]}  {PALETTE[idx(MENU[r][1])]}" + (f"  (last apply: {old_menu[r]})" if old_menu[r] != MENU[r] else ""))
        all_texts = [(cmd, t) for f in files() for _, cmd, _, t in texts(f)]
        need = sum(not base_done(t, cmd, colors) and not highlighted(t, colors) for cmd, t in all_texts)
        print(f"{len(all_texts)} texts: {need} without base/punctuation colors, {len(todo(colors, reviewed))} to review for highlights"
              + (", colors changed since the last apply" if old and old != colors else ""))
    elif args and args[0] == "preview":
        proposed = dict(colors, **dict(a.split("=", 1) for a in args[1:]))
        assert set(proposed) == set(ROLES), f"roles: {' '.join(ROLES)}"
        preview(colors, proposed)
        print(HTML)
    elif args == ["apply"]:
        changed, irregular = apply(colors)
        print(f"{len(changed)} texts recolored")
        print("\n".join(changed))
        if irregular:
            print("highlighted, but base/punctuation differ from the colors (left as they are):\n" + "\n".join(irregular))
    elif args == ["todo"]:
        for f, n, cmd, vsay, text in todo(colors, reviewed):
            print(f"{f.relative_to(REPO)}:{n + 1} {cmd} {vsay} {text}")
    elif args == ["done"]:
        write_record(old or colors, old_menu, reviewed | {(cmd, vsay.lower(), plain(text)) for _, _, cmd, vsay, text in todo(colors, reviewed)})


if __name__ == "__main__":
    main()
