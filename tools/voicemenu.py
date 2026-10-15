#!/usr/bin/env python3
"""Copy a server's quick chat menu (V) into voicechat pages: default/serverconfigs/vsays/<clan>/*.cfg.

Reads ui/wm_quickmessageAlt.menu (the number-key variant) from the server's pk3 and writes one cfg per
menu page the server adds; pages named like a stock menu (etmain pak0.pk3) or sending only stock vsays (the general
voice chat pages vsays/chat/ offer those) and the class vsay are left out, the server's own vsays of such a page go to the
extra pages. <clan>_menu.cfg is the top page (TAB of the voice chat opens it on that server, tools/serverconfig.py; a top page with a
single link is the page that link opens), its TAB goes through its pages and back to the general voice chat; the other pages are named after
their menu (wm_ and _alt stripped). Custom vsays of the pk3's voice scripts that its menu leaves out go on
extra pages of 10 (extra1, extra2, ...), each linked from the server's sound menu (the page of the top page with the most
vsays below it) on a free number key; a page with more than 10 keys continues on a second page (<page>2.cfg, <clan>_menu2.cfg, TAB
switches between them). Extra pages hold only those available to both teams whose
sounds no listed or stock vsay (etmain pak0.pk3) plays already, e.g. as a random variant. Each page is exec'd when
opened: it defines its vsays in the aliases vsay<key> that all voice chat pages share (vsays/chat.cfg), echoes the menu
and binds the keys, CAPSLOCK to the parent page (a TAB page: the parent of its chain; the top page: the stock voice chat); aliases of their own for the ~300 server vsays would exceed MAX_CVARS (2048).

Vsays send their text from the voice script, colored with the VSAY_* colors of settings.conf (base color, punctuation);
the echo shows it without colors. Vsays with several different texts send none: the sound is random and only the server's own
text matches it (picking a variant with "vsay <n> <id>" only works in the legacy mod). On a rerun the texts of the
existing pages are kept per vsay (edited or highlighted ones too), and so are the echoes of the keys that send no text
(random vsays, page links) and the page headings; added and removed vsays are reported.

Menu items on other keys than the number row are left out: a page binds its keys, and a letter is a game bind. Pages
only such items open are left out with them; their vsays count as not in the server menu (extra pages). Only vsay keys
and links to pages that send vsays (themselves or a subpage) are kept, so pages of cvar toggles and server commands
drop out. Settings pages (name, title or link says settings/options/config, also in the languages of the servers) without
vsays of their own are left out too; the key that opened one opens its first subpage with more than 3 vsays instead.

Every page heading starts with the server tag as the server writes it in its name, colors included: the text of
<clan> in default/serverconfigs/servers.tsv, looked up in the name of [address] (asked now) or of a server the game
connected to before (history.tsv); "[<clan>]" if no such name is known. An [address] that doesn't answer is an error. The server's own tag is cut from the heading.
Headings, keys and items are echoed in the MENU_* colors of settings.conf, like the general voice chat.

Usage: tools/voicemenu.py <clan> <pk3> [address]
       e.g. tools/voicemenu.py xy <fs_homepath>/nitmod/<server pack>.pk3
       tools/voicemenu.py --selftest
Rerun after the server ships a new pack; the old pages of that clan are replaced.
"""
import argparse
import datetime
import re
import sys
import tempfile
import zipfile
from pathlib import Path

from helpers.common import COLOR, strip_colors
from helpers.serverapi import history, hostname, server_tag, servers, tag as shown
from helpers.settings import BASEPATH, HOMEPATH, MENU as MENU_COLORS, PROFILE, REPO, VSAY
from vsaycolors import colorize, menu_echo, plain

OUT = REPO / PROFILE / "serverconfigs/vsays"
EXEC = "profile/serverconfigs/vsays"  # the profile link of deploy.sh in each mod folder
MENU = "ui/wm_quickmessageAlt.menu"
KEYS = "1234567890"
# settings/options pages (cvar toggles, server commands), also in the languages of the servers: no vsays to send
SETTINGS = re.compile(r"(?i)setting|option|config|setup|pref|einstellung|ustawieni|opcj|r[eé]glage|param[eè]tre|opcion|impostazion|opzion")
STOCK = [HOMEPATH / "etmain/pak0.pk3", BASEPATH / "etmain/pak0.pk3"]
COLORS = {"vsay_team": VSAY["team"], "vsay": VSAY["global"], "punct": VSAY["punct"]}


def parse(text):
    """{menu: [(label, action, key)]} from the QM_MENU_START(_<suffix>) / QM_MENU_ITEM(_TEAM) macros (a server's own: QM_MENU_START_XY)."""
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


def is_settings(menu, label, menus, heads):
    """A settings page: its name, title or the label linking to it says so, and it sends no vsay."""
    return bool(SETTINGS.search(f"{menu} {heads.get(menu, '')} {strip_colors(label)}")) and not vsays_of(menus.get(menu, []))


def visible(menus, root="wm_quickmessageAlt"):
    """The pages reachable from root with their items on number keys."""
    out, todo = {}, [root]
    while todo:
        menu = todo.pop()
        if menu not in out and menu in menus:
            out[menu] = [i for i in menus[menu] if i[2] in KEYS + "?"]  # ?: a key split() gives
            todo += [m for _, action, _ in out[menu] for m in re.findall(r"open (\w+)", action)]
    return out


def prune(menus, heads={}, root="wm_quickmessageAlt", stock=set(), stock_menus=()):
    """The pages reachable from root with only vsay keys and links to pages that send vsays (themselves or a subpage);
    a link to a settings page is replaced by links to its subpages with more than 3 vsays (the first on its key, the
    others on "?", see split()), else it is left out.
    Pages named like a stock menu or sending only stock vsays (stock: vsays of etmain pak0.pk3) are left out:
    the general voice chat offers stock vsays, the server's own ones of such a page go to the extra pages."""
    def gone(menu):
        return menu != root and (menu in stock_menus or bool(vsays_of(menus.get(menu, []))) and vsays_of(menus[menu]) <= stock)

    def below(menu, seen=()):
        return menu in menus and menu not in seen and not gone(menu) and (bool(vsays_of(menus[menu])) or any(
            below(t, seen + (menu,)) for _, a, _ in menus[menu] for t in re.findall(r"open (\w+)", a)))
    out = {}
    for menu, items in menus.items():
        keep, more = [], []
        for label, action, key in items:
            t = re.findall(r"open (\w+)", action)
            if vsay_of(action) or t and not is_settings(t[0], label, menus, heads) and below(t[0]):
                keep.append((label, action, key))
            elif t:
                subs = [s for _, a, _ in menus.get(t[0], []) for s in re.findall(r"open (\w+)", a) if s != menu and not gone(s) and len(vsays_of(menus.get(s, []))) > 3]
                links = [(heads.get(s, page_name(s, root, "")), f"open {s}") for s in dict.fromkeys(subs)]
                keep += [(f"{key}. {h}", a, key) for h, a in links[:1]]
                more += [(f"?. {h}", a, "?") for h, a in links[1:]]
        out[menu] = (renumber(keep) if len(keep) < len(items) else keep) + more
    return visible(out, root)


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
        for key, cmd, vsay, text in re.findall(r'^set vsay(\S+) "(vsay(?:_team)?) (\w+)(?: (.*?))?"$', f.read_text(encoding="latin1"), re.M):
            pages.setdefault((cmd, vsay.lower()), (f.name, key, text or None))
    return pages


def read_labels(folder):
    """{(cmd, vsay) or page file: echoed item} of the keys that send no text and {("head", page file): heading},
    on the pages a previous run wrote."""
    out = {}
    for f in sorted(folder.glob("*.cfg")):
        text = f.read_text(encoding="latin1")
        head = re.search(rf'^echo ".*{COLOR}([^^"]*):"$', text, re.M)  # the first echo; the tag is in front of the last color code
        if head:
            out["head", f.name] = head.group(1)
        echo = {k: plain(i) for k, i in re.findall(rf'^echo "(?:{COLOR})*(TAB|\d)\.? (.*)"$', text, re.M)}
        for key, cmd, vsay in re.findall(r'^set vsay(\S+) "(vsay(?:_team)?) (\w+)"$', text, re.M):
            if key in echo:
                out.setdefault((cmd, vsay.lower()), echo[key])
        for key, page in re.findall(rf'^bind (\d) "execq {EXEC}/[^/]+/(\S+)"$', text, re.M):
            if key in echo:
                out.setdefault(page, echo[key])
    return out


def report(old, new):
    """Lines for the vsays added, removed or no longer sending their text."""
    lines = [f"+ {c} {v}  {new[c, v][0]} key {new[c, v][1]}" for c, v in sorted(new.keys() - old.keys())]
    lines += [f"- {c} {v}  (was {old[c, v][0]} key {old[c, v][1]}: {old[c, v][2] or 'random'})" for c, v in sorted(old.keys() - new.keys())]
    lines += [f"~ {c} {v}  {new[c, v][0]} key {new[c, v][1]}: several variants now, text dropped: {old[c, v][2]}"
              for c, v in sorted(old.keys() & new.keys()) if old[c, v][2] and not new[c, v][2]]
    return lines


def titles(text):
    """{menu: title} of the menus whose QM_MENU_START macro has one (QM_MENU_START_XY( "wm_xy_more_alt", "[xY] More" ))."""
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


def hub(menus, root="wm_quickmessageAlt"):
    """The server's own sound menu: the page linked from root with the most vsays on it and its subpages, else root."""
    def count(menu, seen):
        if menu in seen or menu not in menus:
            return 0
        seen.add(menu)
        return len(vsays_of(menus[menu])) + sum(count(t, seen) for _, a, _ in menus[menu] for t in re.findall(r"open (\w+)", a))
    subs = [t for _, a, _ in menus.get(root, []) for t in re.findall(r"open (\w+)", a)]
    return max(subs, key=lambda t: count(t, {root}), default=root)


def add_extra(menus, clan, extra, root="wm_quickmessageAlt"):
    """Menu pages of 10 for the unlisted vsays, each linked from the server's sound menu (hub) on "?" (see split())."""
    pages, top = [extra[i:i + 10] for i in range(0, len(extra), 10)], hub(menus, root)
    for n, page in enumerate(pages, 1):
        menus[f"wm_extra{n}_alt"] = [(f"{KEYS[i]}. ^2{txt}", f'exec "VoiceChat {vsay}"', KEYS[i]) for i, (vsay, txt) in enumerate(page)]
        menus[top] = menus[top] + [(f"?. More sounds {n}", f"open wm_extra{n}_alt", "?")]


def collapse(menus, root="wm_quickmessageAlt"):
    """A top page with a single link is replaced by the page it opens (links to that page then open root)."""
    t = len(menus[root]) == 1 and re.findall(r"open (\w+)", menus[root][0][1])
    if t and t[0] in menus and t[0] != root:
        menus[root] = menus.pop(t[0])
        for m in menus:
            menus[m] = [(l, re.sub(rf"open {t[0]}\b", f"open {root}", a), k) for l, a, k in menus[m]]


def split(menus, root="wm_quickmessageAlt"):
    """Items on "?" get the free number keys; a page with more than 10 number keys goes on pages of 10 that TAB cycles
    through (wm_x_alt, wm_x2_alt, ...), the number keys of each in list order. The pages of root end on TAB back to
    the general voice chat, whose TAB opens root (tools/serverconfig.py)."""
    for menu in list(menus):
        num = [i for i in menus[menu] if i[2] != "TAB"]
        if len(num) <= 10:
            free = iter(k for k in KEYS if k not in {i[2] for i in num})
            menus[menu] = [i if i[2] != "?" else (lambda k: (k + i[0][1:], i[1], k))(next(free)) for i in menus[menu]]
            chunks = [menus[menu]]
        else:
            chunks = [renumber(num[i:i + 10]) for i in range(0, len(num), 10)]
        if len(chunks) == 1 and menu != root:
            continue
        names = [menu] + [re.sub(r"(_alt)?$", rf"{n}\1", menu, count=1) for n in range(2, len(chunks) + 1)]
        for n, chunk in enumerate(chunks):
            nxt = n + 1 if n + 1 < len(chunks) or menu != root else None
            tab = ("TAB ^2Voice chat", "vstr chatCategories", "TAB") if nxt is None else (f"TAB ^2Page {nxt % len(chunks) + 1}", f"open {names[nxt % len(chunks)]}", "TAB")
            menus[names[n]] = [i for i in chunk if i[2] != "TAB"] + [tab]


def page_name(menu, root, clan):
    """<clan>_menu, <clan>_menu2, ... for the pages of root (split()), else the menu without wm_ and _alt."""
    return f"{clan}_menu{menu[len(root):]}" if re.fullmatch(rf"{re.escape(root)}\d*", menu) else re.sub(r"^wm_|_alt$", "", menu)


def vsay_of(action):
    """(vsay command, vsay) of a voice chat action, else None."""
    m = re.search(r'exec "(VoiceTeamChat|VoiceChat) (\w+)"', action)
    return m and ("vsay_team" if m.group(1) == "VoiceTeamChat" else "vsay", m.group(2))


def bind(clan, label, action, key, pages, root):
    """(bind line, submenu to render or None); a vsay key runs its alias vsay<key>."""
    if vsay_of(action):
        return f'bind {key} "vstr vsay{key}; vstr resetLayers"', None
    if action.startswith("vstr "):  # back to the general voice chat
        return f'bind {key} "{action}"', None
    o = re.search(r"open (\w+)", action)
    if o and o.group(1) in pages:
        return f'bind {key} "execq {EXEC}/{clan}/{page_name(o.group(1), root, clan)}.cfg"', o.group(1)  # execq: a key press prints no "execing" line
    if o:  # a UI menu that isn't a chat page (e.g. name editor): not reachable from the console
        return f'bind {key} "echo ^1Only in the server\'s own menu ({o.group(1)}); vstr resetLayers"', None
    cmds = [c or f"{v} {x}" for c, v, x in re.findall(r'exec "([^"]+)"|setCvar (\w+) "([^"]*)"', action)]
    return f'bind {key} "' + "; ".join(cmds + ["vstr resetLayers"]) + '"', None


def strip_tag(head, clan, texts=()):
    """Heading without the server's own tag ("^1[^7ABc^1]^0-^3Hello" -> "^3Hello"), the page heading adds the tag;
    texts: the clan's texts of servers.tsv, cut from the start too."""
    for text in sorted(texts, key=len, reverse=True):
        if head.startswith(shown(head, text) or "\0"):
            head = head[len(shown(head, text)):]
            break
    for m in re.finditer(rf"(?:{COLOR})*\[([^\]]*)\]", head):
        if re.sub(rf"{COLOR}|[^a-z0-9]", "", m.group(1).lower()) == clan.lower():
            head = head[:m.start()] + head[m.end():]
            break
    head = re.sub(rf"(?i)(?:^|(?<=[\s\]-])|(?<={COLOR})){re.escape(clan)}[\s|-]+", "", head)  # "ABc-classics"
    while (m := re.match(rf"\s+|-+|{COLOR}(?=[\s^-])", head)):  # separators and the color codes in front of them
        head = head[m.end():]
    return head


def renumber(items):
    """Number keys in list order, also in the label ("^78. x" -> "^71. x"); TAB stays."""
    out, n = [], 0
    for label, action, key in items:
        if key in KEYS or key == "?":
            key, n = KEYS[n], n + 1
            label = re.sub(rf"^((?:{COLOR})*)[\d?]", lambda m: m.group(1) + key, label, count=1)
        out.append((label, action, key))
    return out


def render(clan, pk3name, menus, stock={}, root="wm_quickmessageAlt", tag=None, texts={}, kept={}, colors=COLORS, heads={}, menu_colors=MENU_COLORS, names=(), labels={}, date="2000-01-01"):
    """{file name: cfg text} for every page reachable from root, without the stock entries, and
    {(cmd, vsay): (page, key, text or None)} of its vsays; kept = {(cmd, vsay): text} to send instead of the voice script's,
    labels = {(cmd, vsay) or page file: item} to echo for the keys that send no text, {("head", page file): heading}."""
    tag = tag or f"[{clan}]"
    full = {m for m, v in stock.items() if m != root and vsays_of(menus[m]) <= v}  # nothing added: the general voice chat covers it; root: the last extra page's TAB
    files, vsays, todo = {}, {}, [(root, "VOICE CHAT", "vstr chatCategories")]  # chatCategories: top page of the stock voice chat (vsays/chat.cfg)
    while todo:
        menu, head, back = todo.pop(0)
        name = page_name(menu, root, clan)
        if name + ".cfg" in files:
            continue
        head = labels.get(("head", name + ".cfg")) or strip_tag(heads.get(menu, head) if menu != root else head, clan, names)
        title = strip_colors(f"{tag} {head}")
        top = [f"// {title}: menu {menu} of {MENU} in {pk3name}, generated by tools/voicemenu.py on {date}"]
        lines = ["vstr popupsMenu",  # clears the previous page (scripts/scripts.cfg)
                 f'echo "{tag} {menu_colors["head"]}{plain(head)}:"']  # format of menu_echo(server=True)
        sets, binds = [], []
        items = [i for i in menus[menu] if not is_stock(i[1], full)
                 and not (vsay_of(i[1]) and vsay_of(i[1])[1].lower() in stock.get(menu, ()))]
        if len(items) < len(menus[menu]):  # keys start at 1 again without the stock entries
            items = renumber(items)
        for label, action, key in items:
            v, text, shown = vsay_of(action), None, None
            if v:
                text, shown = say_text(*v, texts, kept, colors)
                vsays.setdefault((v[0], v[1].lower()), (name + ".cfg", key, text))
                sets.append(f'set vsay{key} "{v[0]} {v[1]}{" " + text if text else ""}"')
            item = shown or re.sub(rf"^(?:{COLOR})*(?:\d+\.|TAB)?\s*", "", label)
            line, sub = bind(clan, label, action, key, menus, root)
            binds.append(line)
            own = labels.get((v[0], v[1].lower()) if v else sub and page_name(sub, root, clan) + ".cfg")
            if own and not text:
                item = own
            lines.append(f'echo "{menu_echo(f"{key}. {item}", menu_colors)}"')
            if sub:
                todo.append((sub, re.sub(r"^(\^?\w?\d+\^?\w?\.|TAB)\s*", "", label).strip(),
                             back if key == "TAB" else f"execq {EXEC}/{clan}/{name}.cfg"))  # a TAB page shares the parent of its chain
        # unbindNumbers (binds_custom.cfg) frees every layer key first, so no action of the parent page stays on a key
        files[name + ".cfg"] = "\n".join(top + (["", "// Vsays"] + sets if sets else []) + ["", "// Echos"] + lines
                                         + ["", "// Binds", "vstr unbindNumbers"] + binds + [f'bind CAPSLOCK "{back}"']) + "\n"
    return files, vsays


def selftest():
    menus = parse('''#define QM_MENU_ITEM( A, B, C, D ) x
QM_MENU_START( "wm_quickmessageAlt" )
QM_MENU_ITEM_TEAM( "1. ^5Statements", close wm_quickmessageAlt; open wm_quickstatements_alt, "1", 0 )
QM_MENU_ITEM( "0. ^1FUN", close wm_quickmessageAlt; open wm_fun_alt, "0", 9 )
QM_MENU_END
QM_MENU_START_XY( "wm_fun_alt", "Fun" )
QM_MENU_ITEM( "1. ^2Hi", exec "VoiceChat xy11"; close wm_fun_alt, "1", 0 )
QM_MENU_ITEM_TEAM( "2. ^2Go", exec "VoiceTeamChat FTAttack"; close wm_fun_alt, "2", 1 )
QM_MENU_ITEM( "3. Off", close wm_fun_alt; setCvar cg_x "1"; exec "cg_novoicechats 1", "3", 2 )
QM_MENU_END''')
    menus["wm_quickstatements_alt"] = []
    stock = stock_pages(menus, {"wm_quickstatements_alt": [], "wm_fun_alt": []})
    assert stock == {"wm_quickstatements_alt": set(), "wm_fun_alt": set()}, stock
    col = {"vsay_team": "^9", "vsay": "^l", "punct": "^3"}
    mc = {"head": "^8", "key": "^3", "text": "^7", "nav": "^2"}
    part, _ = render("x", "x.pk3", menus, dict(stock, wm_fun_alt={"xy11"}), texts={}, colors=col, menu_colors=mc)
    assert "xy11" not in part["fun.cfg"] and 'set vsay1 "vsay_team FTAttack"\n' in part["fun.cfg"], part["fun.cfg"]
    texts = {"xy11": ("xy11", ["^4Hi; you!"]), "ftattack": ("FTAttack", ["Attack!", "Go go!"])}
    files, vsays = render("x", "x.pk3", menus, stock, texts=texts, colors=col, menu_colors=mc)
    assert set(files) == {"x_menu.cfg", "fun.cfg"}, files
    assert files["x_menu.cfg"].startswith("// [x] VOICE CHAT: menu wm_quickmessageAlt of ui/wm_quickmessageAlt.menu in x.pk3, generated by tools/voicemenu.py on 2000-01-01\n"), files["x_menu.cfg"]
    assert files["x_menu.cfg"].splitlines()[1:4] == ["", "// Echos", "vstr popupsMenu"]  # no vsays: no Vsays section
    assert "Statements" not in files["x_menu.cfg"] and 'echo "^31. ^7FUN"' in files["x_menu.cfg"]
    assert f"bind 1 \"execq {EXEC}/x/fun.cfg\"" in files["x_menu.cfg"], files["x_menu.cfg"]
    assert renumber([("^78. a", "", "8"), ("^70. b", "", "0"), ("TAB c", "", "TAB")]) == [("^71. a", "", "1"), ("^72. b", "", "2"), ("TAB c", "", "TAB")]
    fun = files["fun.cfg"]
    assert 'set vsay1 "vsay xy11 ^lHi^3, ^lyou^3!"\n' in fun and 'bind 1 "vstr vsay1; vstr resetLayers"' in fun and 'echo "^31. ^7Hi, you!"' in fun, fun
    assert 'set vsay2 "vsay_team FTAttack"\n' in fun and 'echo "^32. ^7Attack! (random)"' in fun, fun
    assert fun.index("// Vsays") < fun.index("// Echos") < fun.index("// Binds"), fun
    assert 'echo "^33. ^7Off"' in fun and vsays[("vsay", "xy11")] == ("fun.cfg", "1", "^lHi^3, ^lyou^3!")
    kept = {("vsay", "xy11"): "^lHi ^xyou^3!"}
    files2, new = render("x", "x.pk3", menus, stock, texts=texts, kept=kept, colors=col, menu_colors=mc)
    assert 'set vsay1 "vsay xy11 ^lHi ^xyou^3!"\n' in files2["fun.cfg"] and 'echo "^31. ^7Hi you!"' in files2["fun.cfg"]
    with tempfile.TemporaryDirectory() as d:  # a rerun reads back what render wrote
        for n, t in files2.items():
            (Path(d) / n).write_text(t, encoding="latin1")
        assert read_pages(Path(d)) == new, read_pages(Path(d))
        assert read_labels(Path(d)) == {"fun.cfg": "FUN", ("vsay_team", "ftattack"): "Attack! (random)",
                                        ("head", "x_menu.cfg"): "VOICE CHAT", ("head", "fun.cfg"): "FUN"}, read_labels(Path(d))
    own = {"fun.cfg": "Jokes", ("vsay_team", "ftattack"): "Charge! (random)", ("vsay", "xy11"): "unused", ("head", "fun.cfg"): "Fun time"}
    files3, _ = render("x", "x.pk3", menus, stock, texts=texts, kept=kept, colors=col, menu_colors=mc, labels=own)
    assert 'echo "^31. ^7Jokes"' in files3["x_menu.cfg"] and 'echo "[x] ^8Fun time:"' in files3["fun.cfg"] and 'echo "[x] ^8VOICE CHAT:"' in files3["x_menu.cfg"], files3
    assert 'echo "^32. ^7Charge! (random)"' in files3["fun.cfg"] and 'echo "^31. ^7Hi you!"' in files3["fun.cfg"], files3["fun.cfg"]
    hidden = {"r": [("1. A", "open a", "1"), ("", "open b", "g")], "a": [("1. x", 'exec "VoiceChat v1"', "1"), ("Q. Quit", "close a", "q")],
              "b": [("1. y", 'exec "VoiceChat v2"', "1")]}
    assert visible(hidden, "r") == {"r": hidden["r"][:1], "a": hidden["a"][:1]}, visible(hidden, "r")
    opts = {"r": [("1. Sounds", "open a", "1"), ("2. ^1Extra Options", "open o", "2"), ("3. Misc", "open s", "3"), ("4. More", "open m", "4")],
            "a": [("1. x", 'exec "VoiceChat v1"', "1")], "o": [("1. Off", 'setCvar cg_novoicechats "1"', "1"), ("2. Sub", "open q", "2")],
            "q": [("1. y", 'exec "VoiceChat v2"', "1")], "s": [("1. Off", "close s", "1")], "m": [("1. z", 'exec "VoiceChat v3"', "1")]}
    opts["o"].append(("3. Back", "open b", "3"))
    opts["b"] = [(f"{k}. b{k}", f'exec "VoiceChat b{k}"', k) for k in "1234"]
    pruned = prune(opts, {"s": "[x] Settings", "m": "More Sounds & Options", "b": "Big"}, "r")
    assert set(pruned) == {"r", "a", "m", "b"}, pruned
    loop = {"r": [("1. Settings", "open s", "1")], "s": [("1. Back", "open m", "1")],
            "m": [(f"{k}. m{k}", f'exec "VoiceChat m{k}"', k) for k in "1234"] + [("0. Settings", "open s", "0")]}
    assert prune(loop, root="r")["m"] == loop["m"][:4] and prune(loop, root="r")["r"][0][1] == "open m"  # never a link to itself
    alt = {"r": [("1. Statements", "open st", "1"), ("2. More", "open nq", "2"), ("3. Mix", "open mx", "3")],
           "st": [("1. x", 'exec "VoiceChat xy1"', "1")], "nq": [("1. f", 'exec "VoiceTeamChat FTMortar"', "1")],
           "mx": [("1. f", 'exec "VoiceTeamChat FTMortar"', "1"), ("2. x", 'exec "VoiceChat xy2"', "2")]}
    assert set(prune(alt, root="r", stock={"ftmortar"}, stock_menus={"st": []})) == {"r", "mx"}
    assert pruned["r"] == [("1. Sounds", "open a", "1"), ("2. Big", "open b", "2"), ("3. More", "open m", "3")], pruned["r"]
    old = {("vsay", "xy11"): ("fun.cfg", "1", "^lHi"), ("vsay", "gone"): ("fun.cfg", "4", "^lBye"), ("vsay_team", "ftattack"): ("fun.cfg", "2", "^9Go")}
    assert report(old, {**new, ("vsay", "xynew"): ("fun.cfg", "5", None)}) == [
        "+ vsay xynew  fun.cfg key 5", "- vsay gone  (was fun.cfg key 4: ^lBye)",
        "~ vsay_team ftattack  fun.cfg key 2: several variants now, text dropped: ^9Go"]
    voice = parse_voice('male\n/* c\n */ Hi { sound/a.wav "Hi!" sprites/x\n sound/b.ogg Yo } // c\nBye\n{\n sound/c.wav "Bye." }')
    assert voice == [("Hi", [("sound/a.wav", "Hi!"), ("sound/b.ogg", "Yo")]), ("Bye", [("sound/c.wav", "Bye.")])], voice
    assert 'bind 3 "cg_x 1; cg_novoicechats 1; vstr resetLayers"' in fun, fun
    assert titles('QM_MENU_START_XY( "wm_fun_alt", "[x] Fun" )\n#define QM_MENU_START_XY( A, B )') == {"wm_fun_alt": "[x] Fun"}
    assert 'echo "[x] ^8FUN:"' in fun, fun
    assert strip_tag("^1[^7ABc^1]^0-^3ABc-classics", "abc") == "^3classics"
    assert strip_tag("^1[^7ABc^1]^0-^3Hello&Bye", "abc") == "^3Hello&Bye" and strip_tag("^9[^7xY^9] ^1FUN", "xy") == "^1FUN"
    assert strip_tag("^1Some ^7Name ^3Options", "sn", ["some", "SOME NAME"]) == "^3Options" and strip_tag("^1My Some", "sn", ["some"]) == "^1My Some"
    assert 'echo "^vPO^7L ^8FUN:"' in render("x", "x.pk3", menus, stock, tag="^vPO^7L", texts=texts, colors=col, menu_colors=mc)[0]["fun.cfg"]
    assert strip_tag("[^8ABc| ^7] ^dSounds 2", "abc") == "^dSounds 2" and strip_tag("^dExtra Options", "abc") == "^dExtra Options"
    both = lambda *w: {"allies": list(w), "axis": list(w)}
    sounds = {"xy11": both("a"), "medic": both("m1", "b"), "xyx": both("a"), "xyy": both("b"), "xyz": {"allies": ["z"]},
              "xyw": both("w"), "xyv": both("w"), **{f"e{i}": both(f"s{i}") for i in range(10)}}
    texts = {v: (v.upper(), [f"text {v}"]) for v in sounds}
    extra = unlisted(menus, sounds, texts, {"medic"})
    assert [v for v, _ in extra] == ["E0", "E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8", "E9", "XYV"], extra
    assert hub(menus) == "wm_fun_alt" and hub({"r": [("1. x", 'exec "VoiceChat v"', "1")]}, "r") == "r"
    side = {"r": [("1. a", "open a", "1")], "a": [("1. x", 'exec "VoiceChat v"', "1")]}
    add_extra(side, "x", extra[:1], "r")
    split(side)
    assert side["a"][-1] == ("2. More sounds 1", "open wm_extra1_alt", "2") and "TAB" not in str(side["wm_extra1_alt"]), side
    full = {"r": [("1. a", "open a", "1")], "a": [(f"{k}. x", f'exec "VoiceChat v{k}"', k) for k in KEYS]}
    add_extra(full, "x", extra, "r")
    split(full)
    assert full["a"][-1] == ("TAB ^2Page 2", "open a2", "TAB") and len(full["a"]) == 11, full["a"]
    assert full["a2"] == [("1. More sounds 1", "open wm_extra1_alt", "1"), ("2. More sounds 2", "open wm_extra2_alt", "2"),
                          ("TAB ^2Page 1", "open a", "TAB")], full["a2"]
    multi = {"r": [("1. Settings", "open s", "1")], "s": [("1. A", "open m", "1"), ("2. B", "open n", "2")],
             "m": [(f"{k}. m", f'exec "VoiceChat m{k}"', k) for k in "1234"], "n": [(f"{k}. n", f'exec "VoiceChat n{k}"', k) for k in "1234"]}
    multi = prune(multi, {"m": "Mm", "n": "Nn"}, "r")
    split(multi, "r")
    assert multi["r"] == [("1. Mm", "open m", "1"), ("2. Nn", "open n", "2"), ("TAB ^2Voice chat", "vstr chatCategories", "TAB")], multi["r"]
    one = {"r": [("1. Fun", "open f", "1")], "f": [(f"{k}. f", f'exec "VoiceChat f{k}"', k) for k in KEYS] + [("?. More", "open e", "?")],
           "e": [("1. e", 'exec "VoiceChat e1"', "1")]}
    collapse(one, "r")
    split(one, "r")
    assert page_name("r2", "r", "x") == "x_menu2" and page_name("r", "r", "x") == "x_menu" and page_name("wm_ra_alt", "r", "x") == "ra"
    assert set(one) == {"r", "r2", "e"} and one["r"][-1] == ("TAB ^2Page 2", "open r2", "TAB"), one
    assert one["r2"] == [("1. More", "open e", "1"), ("TAB ^2Voice chat", "vstr chatCategories", "TAB")], one["r2"]
    assert bind("x", "TAB", "vstr chatCategories", "TAB", one, "r") == ('bind TAB "vstr chatCategories"', None)
    add_extra(menus, "x", extra)
    split(menus)
    files, _ = render("x", "x.pk3", menus, dict(stock, wm_quickmessageAlt=set()), texts=texts, colors=col, menu_colors=mc)
    assert f'bind 4 "execq {EXEC}/x/extra1.cfg"' in files["fun.cfg"] and f'bind 5 "execq {EXEC}/x/extra2.cfg"' in files["fun.cfg"], files["fun.cfg"]
    assert "extra1" not in files["x_menu.cfg"] and "TAB" not in files["extra2.cfg"], files["extra2.cfg"]
    assert files["fun.cfg"].index("\nvstr unbindNumbers\n") < files["fun.cfg"].index("\nbind 1 "), files["fun.cfg"]
    assert 'set vsay1 "vsay XYV ^ltext xyv"\n' in files["extra2.cfg"], files["extra2.cfg"]
    assert files["x_menu.cfg"].endswith('bind CAPSLOCK "vstr chatCategories"\n')
    assert files["extra2.cfg"].endswith(f'bind CAPSLOCK "execq {EXEC}/x/fun.cfg"\n'), files["extra2.cfg"]
    assert files["fun.cfg"].endswith(f'bind CAPSLOCK "execq {EXEC}/x/x_menu.cfg"\n'), files["fun.cfg"]
    assert 'echo "[x] ^8More sounds 1:"' in files["extra1.cfg"], files["extra1.cfg"]
    print("selftest ok")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("clan", nargs="?")
    ap.add_argument("pk3", nargs="?")
    ap.add_argument("address", nargs="?", help="host[:port] of a server of the clan, asked for its name")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.pk3:
        ap.error("clan and pk3 are required")
    clan, pk3 = a.clan, Path(a.pk3).expanduser()
    with zipfile.ZipFile(pk3) as z:
        menu_text = z.read(MENU).decode("latin-1")
        heads = titles(menu_text)
        sounds, texts = voices(z)
    with zipfile.ZipFile(next(p for p in STOCK if p.exists())) as z:
        stock = set(voices(z)[0])
        stock_menus = parse(z.read(MENU).decode("latin-1"))
    menus = prune(visible(parse(menu_text)), heads, stock=stock, stock_menus=stock_menus)
    names, rows = [hostname(a.address)] if a.address else list(history().values()), servers()
    if a.address and not names[0]:  # also a tag passed where the address belongs
        sys.exit(f"'{a.address}' doesn't answer: the third argument is the address of a server, its tag is taken from the server's name")
    tag = server_tag(clan, names, rows)
    if not tag:
        print(f"⚠️  no server name with the text of '{clan}' (serverconfigs/servers.tsv) known: headings get [{clan}]", file=sys.stderr)
    extra = unlisted(menus, sounds, texts, stock)
    add_extra(menus, clan, extra)
    collapse(menus)
    split(menus)
    out = OUT / clan
    old = read_pages(out)
    kept = {k: text for k, (_, _, text) in old.items() if text}
    files, new = render(clan, pk3.name, menus, stock_pages(menus, stock_menus), tag=tag, names=[t for i, t in rows if i == clan],
                        texts=texts, kept=kept, heads=heads, labels=read_labels(out), date=datetime.date.today().isoformat())
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("*.cfg"):
        f.unlink()
    for name, text in files.items():
        (out / name).write_text(text, encoding="latin1")
    print(f"{out.relative_to(REPO)}: {len(files)} pages, {len(extra)} vsays not in the server menu: {' '.join(v for v, _ in extra)}")
    print("\n".join(report(old, new)) if old else f"{len(new)} vsays")


if __name__ == "__main__":
    main()
