#!/usr/bin/env python3
"""Copy a server's quick chat menu (V) into voicechat pages: default/serverconfigs/vsays/<clan>/*.cfg.

Reads ui/wm_quickmessageAlt.menu (the number-key variant) and the pages it opens in the pack's other ui/*.menu files
(menu and item macros of any name, the first label of bilingual ones: the English one in the packs seen so far,
and raw execKey blocks), plus all its scripts/*.voice (a voice file without a team in its name counts for both), and writes one cfg per
menu page the server adds; pages named like a stock menu (etmain pak0.pk3) or sending only stock vsays (the general
voice chat pages vsays/chat/ offer those) and the class vsay are left out, the server's own vsays of such a page go to the
extra pages. _menu.cfg is the top page (TAB of the voice chat opens it on that server, tools/serverconfig.py; a top page with a
single link is the page that link opens), its TAB goes through its pages and back to the general voice chat; the other pages are named after
their menu (wm_ and _alt stripped). Custom vsays of the pk3's voice scripts that its menu leaves out go on
extra pages of 10 (extra1, extra2, ...), each linked from the server's sound menu (the page of the top page with the most
vsays below it) on a free number key; a page with more than 10 keys continues on a second page (<page>2.cfg, _menu2.cfg, TAB
switches between them). Extra pages hold only those available to both teams whose
sounds no listed or stock vsay (etmain pak0.pk3) plays already, e.g. as a random variant. Each page is exec'd when
opened: it defines its vsays in the aliases vsay<key> that all voice chat pages share (vsays/chat.cfg), echoes the menu
and binds the keys, CAPSLOCK to the parent page (a TAB page: the parent of its chain; the top page: the stock voice chat); aliases of their own for the ~300 server vsays would exceed MAX_CVARS (2048).

Vsays send their text from the voice script, colored with the VSAY_* colors of settings.conf (base color, punctuation);
the echo shows it without colors. Vsays with several different texts send none: the sound is random and only the server's own
text matches it (picking a variant with "vsay <n> <id>" only works in the legacy mod). On a rerun the texts of the
existing pages are kept per vsay (edited or highlighted ones too), and so are the echoes of the keys that send no text
(random vsays, page links) and the page headings; added and removed vsays are reported.
vsays.tsv next to the pages lists the server's own vsays (not in etmain pak0.pk3) of the voice scripts: id, variant
number, team (allies, axis, both) and text without color codes of every sound.

Menu items on other keys than the number row are left out (a page binds its keys, a letter is a game bind), except a
labelled link to a page ("N. Next" of a page series), which goes on a free number key; links back to a page nearer the
top (Back, Previous) are left out, CAPSLOCK goes up. Pages only left-out items open are left out with them; their vsays
count as not in the server menu (extra pages). Only vsay keys
and links to pages that send vsays (themselves or a subpage) are kept, so pages of cvar toggles and server commands
drop out. Settings pages (name, title or link says settings/options/config, also in the languages of the servers) without
vsays of their own are left out too; the key that opened one opens its first subpage with more than 3 vsays instead.

Every page heading starts with the server tag as the server writes it in its name, colors included: the text of
<clan> in default/serverconfigs/servers.tsv, looked up in the name of --address (asked now) or of a server the game
connected to before (history.tsv); "[<clan>]" if no such name is known. An [address] that doesn't answer is an error. The server's own tag is cut from the heading.
Headings, keys and items are echoed in the MENU_* colors of settings.conf, like the general voice chat.

Texts with chat shortcuts ([S], [P], ...; mods that replace them) of a page's vsays are in shortcuts/<page>.cfg (same lines as the page's
// Vsays block): the page execs it after its vsays and echoes those texts; a rerun keeps them per vsay (on their new key and page)
and reports the ones whose vsay is gone.

Usage: tools/voicemenu.py <clan> <pk3> [<pk3> ...] [--address host:port]
       e.g. tools/voicemenu.py xy <fs_homepath>/nitmod/<server pack>.pk3
       several pk3s: a pack whose menu and voice scripts are in different pk3s; a file in several comes from the last by name (the game's order)
       tools/voicemenu.py --find <clan>
       tools/voicemenu.py --selftest
Rerun after the server ships a new pack; the old pages of that clan are replaced. --find lists the pk3s of the clan's mod folders
(servers.tsv mod, else history.tsv mods of its addresses, else all) that have a quick chat menu and own vsays, newest first, with
how many vsays of the last run they hold, "names-tag" if their menu has the servers.tsv text and "LAST" for the pk3 of the last run;
packs with none of those vsays and without the tag are left out (a clan without pages: all).
A pk3 with a menu but without its vsays is listed with the pk3 of its folder that defines most of them. "SERVER" (listed first):
the pk3s the game loaded these files from on a server of the clan (default/serverconfigs/packs.tsv, tools/serverconfig.py).
"""
import argparse
import datetime
import re
import sys
import tempfile
import zipfile
from pathlib import Path

from helpers.common import COLOR, strip_colors
from helpers.serverapi import history, hostname, packs as loaded, seen, server_tag, servers, tag as shown
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


def split_args(text):
    """Arguments of a macro call, split at the commas outside quotes and brackets."""
    out, cur, quoted, depth = [], "", False, 0
    for c in text:
        if c == '"':
            quoted = not quoted
        elif not quoted and c in "([{":
            depth += 1
        elif not quoted and c in ")]}":
            depth -= 1
        elif c == "," and not quoted and not depth:
            out.append(cur.strip())
            cur = ""
            continue
        cur += c
    return out + [cur.strip()]


def macro_item(args):
    """(label, action, key) of a menu item macro, else None: the key is the last quoted single character, the action the
    first argument that is neither a quoted text nor a number, the label the first quoted text in front of the action that
    starts with the key (else the first that isn't a bare name). Bilingual macros give the
    English label first in the packs seen so far."""
    quoted = [bool(re.fullmatch(r'"[^"]*"', a)) for a in args]
    keys = [i for i, a in enumerate(args) if re.fullmatch(r'"\w"', a)]
    acts = [i for i, a in enumerate(args) if not quoted[i] and not re.fullmatch(r"-?[\d.]+", a) and a]
    if not keys or not acts or acts[0] > keys[-1]:
        return None
    key, act = args[keys[-1]][1], acts[0]
    labels = [args[i][1:-1] for i in range(act) if quoted[i]]
    label = next((l for l in labels if re.match(rf"(?:{COLOR})*\s*{key}\.", l)), None) \
        or next((l for l in labels if not re.fullmatch(r"\w+", l)), labels[0] if labels else "")
    return label, args[act], key


def parse(text, menus=None):
    """{menu: [(label, action, key)]} of a menu file: a menu starts at a macro with START in its name and its name as first
    argument (QM_MENU_START( "wm_x_alt", ... ), XY_START(...)); items are the item macros of macro_item() and the raw
    execKey "<key>" { action } blocks, labelled by the first itemDef text since the item before. Macro definitions
    (#define and their continuation lines) are skipped. menus: menus of files read before, which keep their definition."""
    menus, new, cur, text_label, cont = menus if menus is not None else {}, {}, None, None, False
    for line in text.splitlines():
        skip, cont = cont or line.lstrip().startswith(("#", "//")), line.rstrip().endswith("\\")
        if skip:
            continue
        m = re.match(r'\s*([A-Z]\w*START\w*)\(\s*"([^"]+)"', line)
        if m:
            cur = None if m.group(2) in menus else new.setdefault(m.group(2), [])
            text_label = None
            continue
        if cur is None:
            continue
        m = re.match(r"\s*([A-Z]\w*)\s*\((.*)\)\s*$", line)
        item = m and "END" not in m.group(1) and macro_item(split_args(m.group(2)))
        if not item:
            t = re.search(r'\btext\s+"([^"]*)"', line)
            text_label = text_label or (t and t.group(1))
            k = re.search(r'\bexecKey\s+"(\w)"\s*\{(.*)\}', line)
            item = k and (text_label or f"{k.group(1)}.", k.group(2).strip(), k.group(1))
        if item:
            cur.append(item)
            text_label = None
    menus.update(new)
    return menus


def menu_files(z):
    """The menu files of a pk3 or Pack: the quick chat menu first, then every other ui/*.menu (pages it opens can live there)."""
    return [MENU] + sorted(n for n in z.namelist() if n.startswith("ui/") and n.endswith(".menu") and n != MENU) if MENU in z.namelist() else []


def read_menus(z):
    """({menu: items} of all menu files, first definition wins; {menu: title}; all menu text)."""
    menus, heads, texts = {}, {}, []
    for name in menu_files(z):
        text = z.read(name).decode("latin-1")
        parse(text, menus)
        heads = {**titles(text), **heads}
        texts.append(text)
    return menus, heads, "\n".join(texts)


def voice_files(z):
    """[(file, teams)] of a pk3's voice scripts: wm_allies_chat / wm_axis_chat for their team, any other scripts/*.voice
    (e.g. a mod's extra voice file) for both (unverified per mod: closed cgames load them)."""
    names = z.namelist()
    std = [(f"scripts/wm_{t}_chat.voice", (t,)) for t in ("allies", "axis") if f"scripts/wm_{t}_chat.voice" in names]
    return std + [(n, ("allies", "axis")) for n in sorted(names) if n.startswith("scripts/") and n.endswith(".voice") and n not in dict(std)]


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
    """The pages reachable from root with their items on number keys; a letter key with a label that opens a page (e.g.
    "N. Next" of a page series) goes on a free number key ("?", see split()). Links back to a page nearer root (Back, Previous) are
    left out: CAPSLOCK goes to the parent page."""
    out, depth, todo = {}, {root: 0}, [root]
    while todo:
        menu = todo.pop(0)
        if menu in out or menu not in menus:
            continue
        out[menu] = []
        for label, action, key in menus[menu]:
            targets = re.findall(r"open (\w+)", action)
            if key not in KEYS + "?":  # ?: a key split() gives
                if not targets or not strip_colors(label).strip():  # no label: a hidden key (easter egg)
                    continue
                label, key = "?. " + re.sub(rf"^(?:{COLOR})*\w\.\s*", "", label), "?"
            if targets and depth.get(targets[0], depth[menu] + 1) < depth[menu]:
                continue
            out[menu].append((label, action, key))
            for t in targets:
                depth.setdefault(t, depth[menu] + 1)
                todo.append(t)
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
                links = [(heads.get(s, page_name(s, root)), f"open {s}") for s in dict.fromkeys(subs)]
                keep += [(f"{key}. {h}", a, key) for h, a in links[:1]]
                more += [(f"?. {h}", a, "?") for h, a in links[1:]]
        out[menu] = (renumber(keep) if len(keep) < len(items) else keep) + more
    return visible(out, root)


def natural(v):
    """Sort key: numbers in the id by value (xy2 before xy10)."""
    return [int(c) if c.isdigit() else c for c in re.split(r"(\d+)", v)]


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
    for name, teams in voice_files(z):
        for vsay, lines in parse_voice(z.read(name).decode("latin-1")):
            for team in teams:
                sounds.setdefault(vsay.lower(), {}).setdefault(team, [s.lower() for s, _ in lines])
            texts.setdefault(vsay.lower(), (vsay, [t for _, t in lines]))
    return sounds, texts


def vsay_list(z, stock):
    """vsays.tsv text: the server's own vsays (not in stock) with every variant's text without color codes, one row per team or "both"."""
    teams = {}
    for name, sides in voice_files(z):
        for vsay, lines in parse_voice(z.read(name).decode("latin-1")):
            for team in sides:
                teams.setdefault(vsay.lower(), {}).setdefault(team, (vsay, [strip_colors(t).replace("\t", " ") for _, t in lines]))
    rows = ["# variant: \"vsay <variant> <vsay>\" plays that sound, legacy mod only (other mods pick one at random)", "vsay\tvariant\tteam\ttext"]
    for v in sorted(teams.keys() - stock, key=natural):
        t = teams[v]
        same = len(t) == 2 and t["allies"][1] == t["axis"][1]
        for team, (vsay, texts) in ({"both": t["allies"]} if same else t).items():
            rows += [f"{vsay}\t{n}\t{team}\t{text}" for n, text in enumerate(texts)]
    return "\n".join(rows) + "\n"


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
    return dict(re.findall(r'^\s*[A-Z]\w*START\w*\(\s*"([^"]+)"\s*,\s*"([^"]+)"', text, re.M))


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
    for v in sorted(set(sounds) - listed - stock, key=natural):
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


def page_name(menu, root):
    """_menu, _menu2, ... for the pages of root (split()), else the menu without wm_ and _alt."""
    return f"_menu{menu[len(root):]}" if re.fullmatch(rf"{re.escape(root)}\d*", menu) else re.sub(r"^wm_|_alt$", "", menu)


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
        return f'bind {key} "execq {EXEC}/{clan}/{page_name(o.group(1), root)}.cfg"', o.group(1)  # execq: a key press prints no "execing" line
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


def render(clan, pk3name, menus, stock={}, root="wm_quickmessageAlt", tag=None, texts={}, kept={}, colors=COLORS, heads={}, menu_colors=MENU_COLORS, names=(), labels={}, shortcuts={}, date="2000-01-01"):
    """{file name: cfg text} for every page reachable from root, without the stock entries, and
    {(cmd, vsay): (page, key, text or None)} of its vsays; kept = {(cmd, vsay): text} to send instead of the voice script's,
    labels = {(cmd, vsay) or page file: item} to echo for the keys that send no text, {("head", page file): heading},
    shortcuts = {(cmd, vsay): text with [S]-style shortcuts}: shortcuts/<page>.cfg, exec'd by the page after its vsays."""
    tag = tag or f"[{clan}]"
    full = {m for m, v in stock.items() if m != root and vsays_of(menus[m]) <= v}  # nothing added: the general voice chat covers it; root: the last extra page's TAB
    files, vsays, todo = {}, {}, [(root, "VOICE CHAT", "vstr chatCategories")]  # chatCategories: top page of the stock voice chat (vsays/chat.cfg)
    while todo:
        menu, head, back = todo.pop(0)
        name = page_name(menu, root)
        if name + ".cfg" in files:
            continue
        head = labels.get(("head", name + ".cfg")) or strip_tag(heads.get(menu, head) if menu != root else head, clan, names)
        title = strip_colors(f"{tag} {head}")
        top = [f"// {title}: menu {menu} of {MENU} in {pk3name}, generated by tools/voicemenu.py on {date}"]
        lines = ["vstr popupsMenu",  # clears the previous page (scripts/scripts.cfg)
                 f'echo "{tag} {menu_colors["head"]}{plain(head)}:"']  # format of menu_echo(server=True)
        sets, binds, short = [], [], []
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
                if (v[0], v[1].lower()) in shortcuts:
                    short.append(f'set vsay{key} "{v[0]} {v[1]} {shortcuts[v[0], v[1].lower()]}"')
                    shown = plain(shortcuts[v[0], v[1].lower()])
            item = shown or re.sub(rf"^(?:{COLOR})*(?:\d+\.|TAB)?\s*", "", label)
            line, sub = bind(clan, label, action, key, menus, root)
            binds.append(line)
            own = labels.get((v[0], v[1].lower()) if v else sub and page_name(sub, root) + ".cfg")
            if own and not text:
                item = own
            lines.append(f'echo "{menu_echo(f"{key}. {item}", menu_colors)}"')
            if sub:
                todo.append((sub, re.sub(r"^(\^?\w?\d+\^?\w?\.|TAB)\s*", "", label).strip(),
                             back if key == "TAB" else f"execq {EXEC}/{clan}/{name}.cfg"))  # a TAB page shares the parent of its chain
        if short:  # some mods replace [S], [P], ... in a vsay text (default/scripts/vsays/README.MD)
            files[f"shortcuts/{name}.cfg"] = "\n".join([f"// {title}: texts with chat shortcuts of {name}.cfg, kept per vsay by tools/voicemenu.py", "", "// Vsays"] + short) + "\n"
            sets += [f"execq {EXEC}/{clan}/shortcuts/{name}.cfg"]
        # unbindNumbers (binds_custom.cfg) frees every layer key first, so no action of the parent page stays on a key
        files[name + ".cfg"] = "\n".join(top + (["", "// Vsays"] + sets if sets else []) + ["", "// Echos"] + lines
                                         + ["", "// Binds", "vstr unbindNumbers"] + binds + [f'bind CAPSLOCK "{back}"']) + "\n"
    return files, vsays


class Pack:
    """The quick chat menu and voice scripts of one or more pk3s as the game sees them: a file in several comes from
    the last by name (src/qcommon/files.c: a folder's pk3s are sorted case-insensitively by FS_PathCmp, a later one wins)."""
    def __init__(self, paths):
        self.paths, self.files = sorted(paths, key=lambda p: p.name.upper()), {}
        for path in self.paths:
            with zipfile.ZipFile(path) as z:
                self.files.update({n: z.read(n) for n in z.namelist() if n.startswith(("ui/", "scripts/")) and n.endswith((".menu", ".voice"))})

    def namelist(self):
        return list(self.files)

    def read(self, name):
        return self.files[name]

    def name(self):
        return " + ".join(p.name for p in self.paths)


def custom_vsays(z, stock):
    """The pack's own vsays (not in stock) if it holds a quick chat menu, else None."""
    return set(voices(z)[0]) - stock if MENU in z.namelist() else None


def find(clan, stock):
    """Prints the packs of the clan's mod folders with a quick chat menu and own vsays, newest first: how many of the
    vsays of the last run (vsays.tsv) they hold, whether their menu names the servers.tsv text, the pack of the last run.
    A pk3 whose menu sends vsays it doesn't define pairs with the pk3 of its folder that defines most of them."""
    rows = [r for r in servers() if r.id == clan]
    mods = {rows[0].mod} if rows and rows[0].mod else {m for a, (_, m) in seen().items() if m and rows and a in rows[0].addresses}
    mods = mods or {d.name for d in HOMEPATH.iterdir() if d.is_dir() and not d.is_symlink() and d.name != "etmain"}
    out = OUT / clan
    known = {l.split("\t")[0].lower() for l in (out / "vsays.tsv").read_text("latin1").splitlines()[2:]} if (out / "vsays.tsv").exists() else set()
    last = next((m.group(1) for f in sorted(out.glob("*.cfg")) for m in [re.search(r" in (.+\.pk3), generated by", f.read_text("latin1"))] if m), None)
    words = [strip_colors(r.text).lower() for r in rows]

    def packs(mods):
        found = []
        for folder in sorted({HOMEPATH / m / d for m in mods for d in ("", "dlcache")}):
            menus, voice = [], []
            for pk3 in sorted(folder.glob("*.pk3")):
                try:
                    with zipfile.ZipFile(pk3) as z:
                        names = z.namelist()
                        own = set(voices(z)[0]) - stock
                        sent = vsays_of([i for items in read_menus(z)[0].values() for i in items])
                except (zipfile.BadZipFile, OSError):
                    continue
                if own:
                    voice.append((pk3, own))
                if MENU in names:
                    menus.append((pk3, own, sent))
            for pk3, own, sent in menus:
                parts = [pk3]
                missing = sent - own - stock
                if missing:  # vsays of the menu come from another pk3
                    best = max((v for v in voice if v[0] != pk3), key=lambda v: (len(v[1] & missing), v[0].stat().st_mtime), default=None)
                    if best and best[1] & missing:
                        parts.append(best[0])
                    elif not own:
                        continue
                pack = Pack(parts)
                own = custom_vsays(pack, stock)
                named = any(w in strip_colors(read_menus(pack)[2]).lower() for w in words)
                if own and (not known or own & known or named):
                    found.append((max(p.stat().st_mtime for p in parts), pack, own, named))
        return found
    found = packs(mods)
    print(f"{clan}: mods {' '.join(sorted(mods))}, last run: {last or 'none'}, {len(known)} vsays in vsays.tsv")
    record = loaded()
    for a in rows[0].addresses if rows else ():
        if a in record:
            files = record[a]
            print(f"{a} loads ({max(d for _, d in files.values())}): " + ", ".join(f"{f} {p or '-'}" for f, (p, _) in files.items()))
            parts = [HOMEPATH / p for p in dict.fromkeys(p for p, _ in files.values()) if p]
            if parts and all(p.exists() for p in parts) and not any(set(f[1].paths) == set(parts) for f in found):
                pack = Pack(parts)
                own = custom_vsays(pack, stock) or set()
                found.append((max(p.stat().st_mtime for p in parts), pack, own, any(w in strip_colors(read_menus(pack)[2]).lower() for w in words)))
    server = {frozenset(HOMEPATH / p for p, _ in record[a].values() if p) for a in (rows[0].addresses if rows else ()) if a in record}
    for mtime, pack, own, named in sorted(found, key=lambda f: (frozenset(f[1].paths) not in server, -f[0])):
        mark = (" SERVER" if frozenset(pack.paths) in server else "") + (" LAST" if pack.name() == last else "") + (" names-tag" if named else "")
        print(f"{datetime.date.fromtimestamp(mtime)}  {len(own):4} own  {len(own & known):4}/{len(known)} known{mark}  "
              + " ".join(str(p.relative_to(HOMEPATH)) for p in pack.paths))


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
    assert set(files) == {"_menu.cfg", "fun.cfg"}, files
    assert files["_menu.cfg"].startswith("// [x] VOICE CHAT: menu wm_quickmessageAlt of ui/wm_quickmessageAlt.menu in x.pk3, generated by tools/voicemenu.py on 2000-01-01\n"), files["_menu.cfg"]
    assert files["_menu.cfg"].splitlines()[1:4] == ["", "// Echos", "vstr popupsMenu"]  # no vsays: no Vsays section
    assert "Statements" not in files["_menu.cfg"] and 'echo "^31. ^7FUN"' in files["_menu.cfg"]
    assert f"bind 1 \"execq {EXEC}/x/fun.cfg\"" in files["_menu.cfg"], files["_menu.cfg"]
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
                                        ("head", "_menu.cfg"): "VOICE CHAT", ("head", "fun.cfg"): "FUN"}, read_labels(Path(d))
    own = {"fun.cfg": "Jokes", ("vsay_team", "ftattack"): "Charge! (random)", ("vsay", "xy11"): "unused", ("head", "fun.cfg"): "Fun time"}
    files3, _ = render("x", "x.pk3", menus, stock, texts=texts, kept=kept, colors=col, menu_colors=mc, labels=own)
    assert 'echo "^31. ^7Jokes"' in files3["_menu.cfg"] and 'echo "[x] ^8Fun time:"' in files3["fun.cfg"] and 'echo "[x] ^8VOICE CHAT:"' in files3["_menu.cfg"], files3
    assert 'echo "^32. ^7Charge! (random)"' in files3["fun.cfg"] and 'echo "^31. ^7Hi you!"' in files3["fun.cfg"], files3["fun.cfg"]
    files4, _ = render("x", "x.pk3", menus, stock, texts=texts, kept=kept, colors=col, menu_colors=mc, shortcuts={("vsay", "xy11"): "^lHi ^x[P]^3!"})
    assert files4["shortcuts/fun.cfg"].endswith('// Vsays\nset vsay1 "vsay xy11 ^lHi ^x[P]^3!"\n'), files4["shortcuts/fun.cfg"]
    assert f'set vsay2 "vsay_team FTAttack"\nexecq {EXEC}/x/shortcuts/fun.cfg\n' in files4["fun.cfg"] and 'echo "^31. ^7Hi [P]!"' in files4["fun.cfg"], files4["fun.cfg"]
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "fun.cfg").write_text(files4["shortcuts/fun.cfg"], encoding="latin1")
        assert read_pages(Path(d)) == {("vsay", "xy11"): ("fun.cfg", "1", "^lHi ^x[P]^3!")}
    hidden = {"r": [("1. A", "open a", "1"), ("^3G. ^7Go", "open b", "g")], "a": [("1. x", 'exec "VoiceChat v1"', "1"), ("Q. Quit", "close a", "q")],
              "b": [("1. y", 'exec "VoiceChat v2"', "1")]}
    assert visible({"r": [("", "open b", "g")], "b": [("1. y", 'exec "VoiceChat v2"', "1")]}, "r") == {"r": []}
    hidden["b"].append(("^30. ^wBack", "close b; open r", "0"))  # back to a page nearer root: left out
    assert visible(hidden, "r") == {"r": [hidden["r"][0], ("?. ^7Go", "open b", "?")], "a": hidden["a"][:1], "b": hidden["b"][:1]}, visible(hidden, "r")
    series = parse('XY_START("s1", "Q [1/2]", "PL", 9)\nXY_ITEM("^31. ^wHi", exec "VoiceChat v1"; closeAll, "1", 0)\n'
                   'XY_LANG("^3N. ^wNext", "^3N. ^wWeiter", close s1; open s2, "n", 8)\n}\n'
                   'QM_MENU_START("r", "Top", "PL", 9)\nXY_PAIR("^31. ^wFun", "^31. ^wSpass", close r; open s1, "1", 0)\n'
                   'itemDef { name "x_en" text "^32. ^wMore" visible 1 }\nitemDef { name "x_pl" text "^32. ^wMehr" visible 1 }\nexecKey "2" { close r; open s2 }\n'
                   'XY_LINK("r_back", 180, "^3B. ^wBack", "^3B. ^wZur", close r; open s1, "b")\nQM_MENU_END\n'
                   '#define XY_ITEM(T,A,K,R) \\\nitemDef { text "^39. x" } execKey "9" { A }\nXY_START("s2", "Q [2/2]", "PL", 9)\n'
                   'XY_ITEM("^31. ^wBye", exec "VoiceChat v2"; closeAll, "1", 0)\n}')
    assert series["r"] == [("^31. ^wFun", "close r; open s1", "1"), ("^32. ^wMore", "close r; open s2", "2"), ("^3B. ^wBack", "close r; open s1", "b")], series["r"]
    assert series["s1"][1] == ("^3N. ^wNext", "close s1; open s2", "n") and series["s2"] == [("^31. ^wBye", 'exec "VoiceChat v2"; closeAll', "1")], series
    assert titles('XY_START("s1", "Q [1/2]", "PL", 9)') == {"s1": "Q [1/2]"}
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
    assert page_name("r2", "r") == "_menu2" and page_name("r", "r") == "_menu" and page_name("wm_ra_alt", "r") == "ra"
    assert set(one) == {"r", "r2", "e"} and one["r"][-1] == ("TAB ^2Page 2", "open r2", "TAB"), one
    assert one["r2"] == [("1. More", "open e", "1"), ("TAB ^2Voice chat", "vstr chatCategories", "TAB")], one["r2"]
    assert bind("x", "TAB", "vstr chatCategories", "TAB", one, "r") == ('bind TAB "vstr chatCategories"', None)
    add_extra(menus, "x", extra)
    split(menus)
    files, _ = render("x", "x.pk3", menus, dict(stock, wm_quickmessageAlt=set()), texts=texts, colors=col, menu_colors=mc)
    assert f'bind 4 "execq {EXEC}/x/extra1.cfg"' in files["fun.cfg"] and f'bind 5 "execq {EXEC}/x/extra2.cfg"' in files["fun.cfg"], files["fun.cfg"]
    assert "extra1" not in files["_menu.cfg"] and "TAB" not in files["extra2.cfg"], files["extra2.cfg"]
    assert files["fun.cfg"].index("\nvstr unbindNumbers\n") < files["fun.cfg"].index("\nbind 1 "), files["fun.cfg"]
    assert 'set vsay1 "vsay XYV ^ltext xyv"\n' in files["extra2.cfg"], files["extra2.cfg"]
    assert files["_menu.cfg"].endswith('bind CAPSLOCK "vstr chatCategories"\n')
    assert files["extra2.cfg"].endswith(f'bind CAPSLOCK "execq {EXEC}/x/fun.cfg"\n'), files["extra2.cfg"]
    assert files["fun.cfg"].endswith(f'bind CAPSLOCK "execq {EXEC}/x/_menu.cfg"\n'), files["fun.cfg"]
    assert 'echo "[x] ^8More sounds 1:"' in files["extra1.cfg"], files["extra1.cfg"]
    with tempfile.TemporaryDirectory() as d:
        with zipfile.ZipFile(Path(d) / "x.pk3", "w") as z:
            z.writestr("scripts/wm_allies_chat.voice", 'male\nxy1 {\n a.wav "Hi!"\n b.wav "Yo\tx"\n}\nxy10 {\n c.wav "Ten"\n}\nmedic {\n m.wav "Medic!"\n}')
            z.writestr("scripts/wm_axis_chat.voice", 'male\nxy1 {\n a.wav "Hi!"\n b.wav "^1Yo\tx"\n}\nxy2 {\n d.wav "Two"\n}')
        with zipfile.ZipFile(Path(d) / "x.pk3") as z:
            rows = vsay_list(z, {"medic"}).splitlines()
            assert custom_vsays(z, {"medic"}) is None  # no quick chat menu
        with zipfile.ZipFile(Path(d) / "x.pk3", "a") as z:
            z.writestr(MENU, "")
        with zipfile.ZipFile(Path(d) / "x.pk3") as z:
            assert custom_vsays(z, {"medic"}) == {"xy1", "xy2", "xy10"}, custom_vsays(z, {"medic"})
        with zipfile.ZipFile(Path(d) / "X_2.pk3", "w") as z:  # a later pk3 by name: its menu wins
            z.writestr(MENU, "new")
        pack = Pack([Path(d) / "X_2.pk3", Path(d) / "x.pk3"])
        assert pack.name() == "x.pk3 + X_2.pk3" and pack.read(MENU) == b"new" and custom_vsays(pack, {"medic"}) == {"xy1", "xy2", "xy10"}
    assert rows[1:] == ["vsay\tvariant\tteam\ttext", "xy1\t0\tboth\tHi!", "xy1\t1\tboth\tYo x", "xy2\t0\taxis\tTwo", "xy10\t0\tallies\tTen"], rows
    print("selftest ok")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("clan", nargs="?")
    ap.add_argument("pk3", nargs="*", help="the server's pack: one pk3, or the pk3s that hold its menu and voice scripts")
    ap.add_argument("--address", help="host[:port] of a server of the clan, asked for its name")
    ap.add_argument("--find", action="store_true", help="list the pk3s with a quick chat menu and own vsays of the clan's mod folders")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.find:
        if not a.clan:
            ap.error("--find needs the clan")
        with zipfile.ZipFile(next(p for p in STOCK if p.exists())) as s:
            return find(a.clan, set(voices(s)[0]))
    if not a.pk3:
        ap.error("clan and pk3 are required")
    clan, z = a.clan, Pack([Path(p).expanduser() for p in a.pk3])
    if MENU not in z.namelist():
        sys.exit(f"no {MENU} in {z.name()}")
    parsed, heads, _ = read_menus(z)
    sounds, texts = voices(z)
    with zipfile.ZipFile(next(p for p in STOCK if p.exists())) as s:
        stock = set(voices(s)[0])
        stock_menus = parse(s.read(MENU).decode("latin-1"))
    listing = vsay_list(z, stock)
    menus = prune(visible(parsed), heads, stock=stock, stock_menus=stock_menus)
    names, rows = [hostname(a.address)[0]] if a.address else list(history().values()), servers()
    if a.address and not names[0]:  # also a tag passed where the address belongs
        sys.exit(f"'{a.address}' doesn't answer: --address is the address of a server, its tag is taken from the server's name")
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
    shortcuts = {k: text for k, (_, _, text) in read_pages(out / "shortcuts").items() if text}
    files, new = render(clan, z.name(), menus, stock_pages(menus, stock_menus), tag=tag, names=[r.text for r in rows if r.id == clan],
                        texts=texts, kept=kept, heads=heads, labels=read_labels(out), shortcuts=shortcuts, date=datetime.date.today().isoformat())
    (out / "shortcuts").mkdir(parents=True, exist_ok=True)
    for f in [*out.glob("*.cfg"), *out.glob("shortcuts/*.cfg")]:
        f.unlink()
    for name, text in files.items():
        (out / name).write_text(text, encoding="latin1")
    if not any((out / "shortcuts").iterdir()):
        (out / "shortcuts").rmdir()
    (out / "vsays.tsv").write_text(listing, encoding="latin1")
    print(f"{out.relative_to(REPO)}: {len(files)} pages, {len(extra)} vsays not in the server menu: {' '.join(v for v, _ in extra)}")
    print("\n".join(report(old, new)) if old else f"{len(new)} vsays")
    print("\n".join(f"- shortcut {c} {v}  (vsay gone): {t}" for (c, v), t in sorted(shortcuts.items()) if (c, v) not in new))


if __name__ == "__main__":
    main()
