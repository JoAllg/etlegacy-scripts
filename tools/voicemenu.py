#!/usr/bin/env python3
"""Copy a server's quick chat menu (V) into voicechat pages: default/scripts/vsays/servers/<clan>/*.cfg.

Reads ui/wm_quickmessageAlt.menu (the number-key variant) from the server's pk3 and writes one cfg per
menu page the server adds; entries that open a stock page (etmain pak0.pk3, covered by the general voice chat
vsays/chat.cfg) or say the class vsay are left out; a stock page the server added vsays to keeps only those. <clan>.cfg is the top page (chat_custom.cfg opens it); the other pages are named after
their menu (wm_ and _alt stripped). Custom vsays of the pk3's voice scripts that its menu leaves out go on
extra pages behind TAB of the top page (extra1, extra2, ...): only those available to both teams whose
sounds no listed or stock vsay (etmain pak0.pk3) plays already, e.g. as a random variant. Each page binds the number keys
directly when exec'd: aliases for the ~300 server vsays would exceed MAX_CVARS (2048).

Vsays send their text from the voice script, colored with the VSAY_* colors of settings.conf (base color, punctuation);
the echo shows it without colors. Vsays with several different texts send none: the sound is random and only the server's own
text matches it (picking a variant with "vsay <n> <id>" only works in the legacy mod). On a rerun the texts of the
existing pages are kept per vsay (edited or highlighted ones too); added and removed vsays are reported.

Every page heading starts with the server tag (default "[<clan>]"); the server's own tag is cut from the heading.
Headings, keys and items are echoed in the MENU_* colors of settings.conf, like the general voice chat.

Usage: tools/voicemenu.py <clan> <pk3> [tag]
       e.g. tools/voicemenu.py eg <fs_homepath>/nitmod/z_eg_s48.pk3 "^9[^7eG^9]"
       tools/voicemenu.py --selftest
Rerun after the server ships a new pack; the old pages of that clan are replaced.
"""
import re
import sys
import zipfile
from pathlib import Path

from settings import BASEPATH, HOMEPATH, MENU as MENU_COLORS, PROFILE, REPO, VSAY
from vsaycolors import colorize, menu_echo, plain

OUT = REPO / PROFILE / "scripts/vsays/servers"
EXEC = "profile/scripts/vsays/servers"  # the profile link of deploy.sh in each mod folder
MENU = "ui/wm_quickmessageAlt.menu"
KEYS = "1234567890"
PAGE_KEYS = [*KEYS, "TAB"]  # keys a page unbinds when it doesn't use them
STOCK = [HOMEPATH / "etmain/pak0.pk3", BASEPATH / "etmain/pak0.pk3"]
COLORS = {"vsay_team": VSAY["team"], "vsay": VSAY["global"], "punct": VSAY["punct"]}


def parse(text):
    """{menu: [(label, action, key)]} from the QM_MENU_START(_<suffix>) / QM_MENU_ITEM(_TEAM) macros (eG: QM_MENU_START_EG)."""
    menus, cur = {}, None
    for line in text.splitlines():
        if line.lstrip().startswith(("#define", "//")):
            continue
        m = re.search(r'QM_MENU_START\w*\(\s*"([^"]+)"', line)
        if m:
            cur = menus.setdefault(m.group(1), [])
            continue
        m = re.search(r'QM_MENU_ITEM(?:_TEAM)?\(\s*"([^"]*)"\s*,(.*),\s*"(\w)"\s*,\s*\d+\s*\)', line)
        if m and cur is not None:
            cur.append(m.groups())
    return menus


def tokens(text):
    """[(token, line)] like COM_ParseExt: quoted or whitespace separated, // and /* */ comments skipped."""
    out = []
    for m in re.finditer(r'//[^\n]*|/\*.*?(?:\*/|$)|"([^"]*)"?|(\S+)', text, re.S):
        if m.group(1) is not None or m.group(2):
            out.append((m.group(1) if m.group(1) is not None else m.group(2), text.count("\n", 0, m.start())))
    return out


def parse_voice(text):
    """[(vsay, [(sound, text)])] like CG_ParseVoiceChats: gender, then id { sound text [sprite on the same line] ... }."""
    toks, out, i = tokens(text), [], 1
    while i + 1 < len(toks) and toks[i + 1][0] == "{":
        vsay, lines, i = toks[i][0], [], i + 2
        while i + 1 < len(toks) and toks[i][0] != "}":
            lines.append((toks[i][0], toks[i + 1][0]))
            i += 2
            if i < len(toks) and toks[i][1] == toks[i - 1][1] and toks[i][0] != "}":
                i += 1
        out.append((vsay, lines))
        i += 1
    return out


def voices(z):
    """{vsay: {team: [sound, ...]}} and {vsay: (name, [text, ...])}, from the pk3's voice scripts (first definition wins)."""
    sounds, texts = {}, {}
    for team in ("allies", "axis"):
        name = f"scripts/wm_{team}_chat.voice"
        if name not in z.namelist():
            continue
        for vsay, lines in parse_voice(z.read(name).decode("latin-1")):
            sounds.setdefault(vsay.lower(), {}).setdefault(team, [s.lower() for s, _ in lines])
            texts.setdefault(vsay.lower(), (vsay, [t for _, t in lines]))
    return sounds, texts



def say_text(cmd, vsay, texts, kept, colors):
    """(text to send or None, text to echo or None) of a vsay."""
    if vsay.lower() not in texts:
        return None, None
    variants = texts[vsay.lower()][1]
    if len(set(variants)) > 1:  # random sound: only the server's text matches it
        return None, plain(colorize(variants[0] + " (random)", colors[cmd], colors["punct"]))
    text = kept.get((cmd, vsay.lower())) or colorize(variants[0], colors[cmd], colors["punct"])
    return text, plain(text)


def read_pages(folder):
    """{(cmd, vsay): (page, key, text or None)} of the pages a previous run wrote."""
    pages = {}
    for f in sorted(folder.glob("*.cfg")):
        for key, cmd, vsay, text in re.findall(r'^bind (\S+) "(vsay(?:_team)?) (\w+)(?: (.*?))?; vstr resetVoiceChat"$', f.read_text(), re.M):
            pages.setdefault((cmd, vsay.lower()), (f.name, key, text or None))
    return pages


def report(old, new):
    """Lines for the vsays added, removed or no longer sending their text."""
    lines = [f"+ {c} {v}  {new[c, v][0]} key {new[c, v][1]}" for c, v in sorted(new.keys() - old.keys())]
    lines += [f"- {c} {v}  (was {old[c, v][0]} key {old[c, v][1]}: {old[c, v][2] or 'random'})" for c, v in sorted(old.keys() - new.keys())]
    lines += [f"~ {c} {v}  {new[c, v][0]} key {new[c, v][1]}: several variants now, text dropped: {old[c, v][2]}"
              for c, v in sorted(old.keys() & new.keys()) if old[c, v][2] and not new[c, v][2]]
    return lines


def titles(text):
    """{menu: title} of the menus whose QM_MENU_START macro has one (eG: QM_MENU_START_EG( "wm_eg_more_alt", "[eG] More" ))."""
    return dict(re.findall(r'^\s*QM_MENU_START\w*\(\s*"([^"]+)"\s*,\s*"([^"]+)"', text, re.M))


def vsays_of(items):
    return {v.lower() for _, a, _ in items for v in re.findall(r'exec "Voice\w*Chat (\w+)"', a)}


def stock_pages(menus, stock_menus):
    """{page: vsays of the stock page} of the server pages named like a stock page, e.g. wm_quickstatements_alt."""
    return {m: vsays_of(stock_menus[m]) for m in menus if m in stock_menus}


def is_stock(action, stock):
    o = re.search(r"open (\w+)", action)
    return "wm_sayPlayerClass" in action or bool(o and o.group(1) in stock)


def unlisted(menus, sounds, texts, stock):
    """[(vsay, text)] of custom vsays the menu doesn't offer and whose sounds are not reachable otherwise."""
    listed = {v for items in menus.values() for v in vsays_of(items)}
    reachable = {w for v, t in sounds.items() if v in listed or v in stock for ws in t.values() for w in ws}
    out = []
    for v in sorted(set(sounds) - listed - stock, key=lambda v: [int(c) if c.isdigit() else c for c in re.split(r"(\d+)", v)]):
        ws = {w for t in sounds[v].values() for w in t}
        if len(sounds[v]) == 2 and not ws & reachable:
            out.append((texts[v][0], texts[v][1][0]))
            reachable |= ws  # a later vsay with the same sound adds nothing
    return out


def add_extra(menus, clan, extra, root="wm_quickmessageAlt"):
    """Menu pages for the unlisted vsays, reached with TAB from root (TAB pages on, the last back to the first)."""
    pages = [extra[i:i + 10] for i in range(0, len(extra), 10)]
    for n, page in enumerate(pages, 1):
        items = [(f"{KEYS[i]}. ^2{txt}", f'exec "VoiceChat {vsay}"', KEYS[i]) for i, (vsay, txt) in enumerate(page)]
        if len(pages) > 1:
            items.append(("TAB ^2More sounds", f"open wm_extra{n % len(pages) + 1}_alt", "TAB"))
        menus[f"wm_extra{n}_alt"] = items
    if pages:
        menus[root] = menus[root] + [("TAB ^2More sounds (not in the server menu)", "open wm_extra1_alt", "TAB")]


def page_name(menu, root, clan):
    return clan if menu == root else re.sub(r"^wm_|_alt$", "", menu)


def vsay_of(action):
    """(vsay command, vsay) of a voice chat action, else None."""
    m = re.search(r'exec "(VoiceTeamChat|VoiceChat) (\w+)"', action)
    return m and ("vsay_team" if m.group(1) == "VoiceTeamChat" else "vsay", m.group(2))


def bind(clan, label, action, key, pages, text=None):
    """(bind line, submenu to render or None)."""
    v = vsay_of(action)
    if v:
        return f'bind {key} "{v[0]} {v[1]}{" " + text if text else ""}; vstr resetVoiceChat"', None
    o = re.search(r"open (\w+)", action)
    if o and o.group(1) in pages:
        return f'bind {key} "exec {EXEC}/{clan}/{page_name(o.group(1), None, clan)}.cfg"', o.group(1)
    if o:  # a UI menu that isn't a chat page (e.g. name editor): not reachable from the console
        return f'bind {key} "echo ^1Only in the server\'s own menu ({o.group(1)}); vstr resetVoiceChat"', None
    cmds = [c or f"{v} {x}" for c, v, x in re.findall(r'exec "([^"]+)"|setCvar (\w+) "([^"]*)"', action)]
    return f'bind {key} "' + "; ".join(cmds + ["vstr resetVoiceChat"]) + '"', None


def strip_tag(head, clan):
    """Heading without the server's own tag ("^1[^7ETc^1]^0-^3Hello" -> "^3Hello"), the page heading adds the tag."""
    for m in re.finditer(r"(?:\^.)*\[([^\]]*)\]", head):
        if re.sub(r"\^.|[^a-z0-9]", "", m.group(1).lower()) == clan.lower():
            head = head[:m.start()] + head[m.end():]
            break
    head = re.sub(rf"(?i)(?:^|(?<=[\s\]-])|(?<=\^.)){re.escape(clan)}[\s|-]+", "", head)  # "ETc-classics"
    while (m := re.match(r"\s+|-+|\^.(?=[\s^-])", head)):  # separators and the color codes in front of them
        head = head[m.end():]
    return head


def renumber(items):
    """Number keys in list order, also in the label ("^78. x" -> "^71. x"); TAB stays."""
    out, n = [], 0
    for label, action, key in items:
        if key in KEYS:
            key, n = KEYS[n], n + 1
            label = re.sub(r"^((?:\^.)*)\d", lambda m: m.group(1) + key, label, count=1)
        out.append((label, action, key))
    return out


def render(clan, pk3name, menus, stock={}, root="wm_quickmessageAlt", tag=None, texts={}, kept={}, colors=COLORS, heads={}, menu_colors=MENU_COLORS):
    """{file name: cfg text} for every page reachable from root, without the stock entries, and
    {(cmd, vsay): (page, key, text or None)} of its vsays; kept = {(cmd, vsay): text} to send instead of the voice script's."""
    tag = tag or f"[{clan}]"
    full = {m for m, v in stock.items() if vsays_of(menus[m]) <= v}  # nothing added: the general voice chat covers it
    files, vsays, todo = {}, {}, [(root, "VOICE CHAT")]
    while todo:
        menu, head = todo.pop(0)
        name = page_name(menu, root, clan)
        if name + ".cfg" in files:
            continue
        head = strip_tag(heads.get(menu, head) if menu != root else head, clan)
        title = re.sub(r"\^.", "", f"{tag} {head}")
        lines = [f"// {title}: menu {menu} of {MENU} in {pk3name}, generated by tools/voicemenu.py",
                 "vstr popupsMenu",  # clears the previous page (scripts/scripts.cfg)
                 f'echo "{menu_echo(f"{tag} {plain(head)}:", menu_colors)}"']
        binds = []
        items = [i for i in menus[menu] if not is_stock(i[1], full)
                 and not (vsay_of(i[1]) and vsay_of(i[1])[1].lower() in stock.get(menu, ()))]
        if len(items) < len(menus[menu]):  # keys start at 1 again without the stock entries
            items = renumber(items)
        for label, action, key in items:
            v, text, shown = vsay_of(action), None, None
            if v:
                text, shown = say_text(*v, texts, kept, colors)
                vsays.setdefault((v[0], v[1].lower()), (name + ".cfg", key, text))
            item = shown or re.sub(r"^(?:\^.)*(?:\d+\.|TAB)?\s*", "", label)
            lines.append(f'echo "{menu_echo(f"{key}. {item}", menu_colors)}"')
            line, sub = bind(clan, label, action, key, menus, text)
            binds.append(line)
            if sub:
                todo.append((sub, re.sub(r"^(\^?\w?\d+\^?\w?\.|TAB)\s*", "", label).strip()))
        used = {b.split()[1] for b in binds}
        binds += [f"unbind {k}" for k in PAGE_KEYS if k not in used]  # no action of the parent page stays on the key
        files[name + ".cfg"] = "\n".join(lines + binds) + "\n"
    return files, vsays


def selftest():
    menus = parse('''#define QM_MENU_ITEM( A, B, C, D ) x
QM_MENU_START( "wm_quickmessageAlt" )
QM_MENU_ITEM_TEAM( "1. ^5Statements", close wm_quickmessageAlt; open wm_quickstatements_alt, "1", 0 )
QM_MENU_ITEM( "0. ^1FUN", close wm_quickmessageAlt; open wm_fun_alt, "0", 9 )
QM_MENU_END
QM_MENU_START_EG( "wm_fun_alt", "Fun" )
QM_MENU_ITEM( "1. ^2Hi", exec "VoiceChat eg11"; close wm_fun_alt, "1", 0 )
QM_MENU_ITEM_TEAM( "2. ^2Go", exec "VoiceTeamChat FTAttack"; close wm_fun_alt, "2", 1 )
QM_MENU_ITEM( "3. Off", close wm_fun_alt; setCvar cg_x "1"; exec "cg_novoicechats 1", "3", 2 )
QM_MENU_END''')
    menus["wm_quickstatements_alt"] = []
    stock = stock_pages(menus, {"wm_quickstatements_alt": [], "wm_fun_alt": []})
    assert stock == {"wm_quickstatements_alt": set(), "wm_fun_alt": set()}, stock
    col = {"vsay_team": "^9", "vsay": "^l", "punct": "^3"}
    mc = {"head": "^8", "key": "^3", "text": "^7", "nav": "^2"}
    part, _ = render("x", "x.pk3", menus, dict(stock, wm_fun_alt={"eg11"}), texts={}, colors=col, menu_colors=mc)
    assert "eg11" not in part["fun.cfg"] and 'bind 1 "vsay_team FTAttack; vstr resetVoiceChat"' in part["fun.cfg"], part["fun.cfg"]
    texts = {"eg11": ("eg11", ["^4Hi; you!"]), "ftattack": ("FTAttack", ["Attack!", "Go go!"])}
    files, vsays = render("x", "x.pk3", menus, stock, texts=texts, colors=col, menu_colors=mc)
    assert set(files) == {"x.cfg", "fun.cfg"}, files
    assert files["x.cfg"].splitlines()[1] == "vstr popupsMenu"
    assert "Statements" not in files["x.cfg"] and 'echo "^31. ^7FUN"' in files["x.cfg"]
    assert f"bind 1 \"exec {EXEC}/x/fun.cfg\"" in files["x.cfg"], files["x.cfg"]
    assert renumber([("^78. a", "", "8"), ("^70. b", "", "0"), ("TAB c", "", "TAB")]) == [("^71. a", "", "1"), ("^72. b", "", "2"), ("TAB c", "", "TAB")]
    fun = files["fun.cfg"]
    assert 'bind 1 "vsay eg11 ^lHi^3, ^lyou^3!; vstr resetVoiceChat"' in fun and 'echo "^31. ^7Hi, you!"' in fun, fun
    assert 'bind 2 "vsay_team FTAttack; vstr resetVoiceChat"' in fun and 'echo "^32. ^7Attack! (random)"' in fun, fun
    assert 'echo "^33. ^7Off"' in fun and vsays[("vsay", "eg11")] == ("fun.cfg", "1", "^lHi^3, ^lyou^3!")
    kept = {("vsay", "eg11"): "^lHi ^xyou^3!"}
    files2, new = render("x", "x.pk3", menus, stock, texts=texts, kept=kept, colors=col, menu_colors=mc)
    assert 'bind 1 "vsay eg11 ^lHi ^xyou^3!; vstr resetVoiceChat"' in files2["fun.cfg"] and 'echo "^31. ^7Hi you!"' in files2["fun.cfg"]
    old = {("vsay", "eg11"): ("fun.cfg", "1", "^lHi"), ("vsay", "gone"): ("fun.cfg", "4", "^lBye"), ("vsay_team", "ftattack"): ("fun.cfg", "2", "^9Go")}
    assert report(old, {**new, ("vsay", "egnew"): ("fun.cfg", "5", None)}) == [
        "+ vsay egnew  fun.cfg key 5", "- vsay gone  (was fun.cfg key 4: ^lBye)",
        "~ vsay_team ftattack  fun.cfg key 2: several variants now, text dropped: ^9Go"]
    voice = parse_voice('male\n/* c\n */ Hi { sound/a.wav "Hi!" sprites/x\n sound/b.ogg Yo } // c\nBye\n{\n sound/c.wav "Bye." }')
    assert voice == [("Hi", [("sound/a.wav", "Hi!"), ("sound/b.ogg", "Yo")]), ("Bye", [("sound/c.wav", "Bye.")])], voice
    assert 'bind 3 "cg_x 1; cg_novoicechats 1; vstr resetVoiceChat"' in fun, fun
    assert titles('QM_MENU_START_EG( "wm_fun_alt", "[x] Fun" )\n#define QM_MENU_START_EG( A, B )') == {"wm_fun_alt": "[x] Fun"}
    assert 'echo "[x] ^8FUN:"' in fun, fun
    assert strip_tag("^1[^7ETc^1]^0-^3ETc-classics", "etc") == "^3classics"
    assert strip_tag("^1[^7ETc^1]^0-^3Hello&Bye", "etc") == "^3Hello&Bye" and strip_tag("^9[^7eG^9] ^1FUN", "eg") == "^1FUN"
    assert strip_tag("[^8ETc| ^7] ^dSounds 2", "etc") == "^dSounds 2" and strip_tag("^dExtra Options", "etc") == "^dExtra Options"
    both = lambda *w: {"allies": list(w), "axis": list(w)}
    sounds = {"eg11": both("a"), "medic": both("m1", "b"), "egx": both("a"), "egy": both("b"), "egz": {"allies": ["z"]},
              "egw": both("w"), "egv": both("w"), **{f"e{i}": both(f"s{i}") for i in range(10)}}
    texts = {v: (v.upper(), [f"text {v}"]) for v in sounds}
    extra = unlisted(menus, sounds, texts, {"medic"})
    assert [v for v, _ in extra] == ["E0", "E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8", "E9", "EGV"], extra
    add_extra(menus, "x", extra)
    files, _ = render("x", "x.pk3", menus, stock, texts=texts, colors=col, menu_colors=mc)
    assert f'bind TAB "exec {EXEC}/x/extra1.cfg"' in files["x.cfg"] and "unbind TAB" in files["fun.cfg"] and "unbind 0" in files["x.cfg"]
    assert 'bind 1 "vsay EGV ^ltext egv; vstr resetVoiceChat"' in files["extra2.cfg"] and f'bind TAB "exec {EXEC}/x/extra1.cfg"' in files["extra2.cfg"]
    assert 'echo "[x] ^8More sounds (not in the server menu):"' in files["extra1.cfg"], files["extra1.cfg"]
    print("selftest ok")


def main():
    if sys.argv[1:] == ["--selftest"]:
        return selftest()
    if len(sys.argv) not in (3, 4):
        sys.exit(__doc__)
    clan, pk3 = sys.argv[1], Path(sys.argv[2]).expanduser()
    with zipfile.ZipFile(pk3) as z:
        menu_text = z.read(MENU).decode("latin-1")
        menus, heads = parse(menu_text), titles(menu_text)
        sounds, texts = voices(z)
    with zipfile.ZipFile(next(p for p in STOCK if p.exists())) as z:
        stock = set(voices(z)[0])
        stock_menus = parse(z.read(MENU).decode("latin-1"))
    extra = unlisted(menus, sounds, texts, stock)
    add_extra(menus, clan, extra)
    out = OUT / clan
    old = read_pages(out)
    kept = {k: text for k, (_, _, text) in old.items() if text}
    files, new = render(clan, pk3.name, menus, stock_pages(menus, stock_menus), tag=sys.argv[3] if len(sys.argv) == 4 else None,
                        texts=texts, kept=kept, heads=heads)
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("*.cfg"):
        f.unlink()
    for name, text in files.items():
        (out / name).write_text(text)
    print(f"{out.relative_to(REPO)}: {len(files)} pages, {len(extra)} vsays not in the server menu: {' '.join(v for v, _ in extra)}")
    print("\n".join(report(old, new)) if old else f"{len(new)} vsays")


if __name__ == "__main__":
    main()
