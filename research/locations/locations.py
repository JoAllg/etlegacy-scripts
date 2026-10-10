#!/usr/bin/env python3
"""Location files of the downloaded maps: dated snapshots of the dlcache pk3s, reports, and the edits that bring
them into <profile>/maps/ (driven by the locations skill).

Usage: python3 research/locations/locations.py extract
         snapshot research/locations/maps_<YYYY-MM-DD>/ (a rerun the same day rebuilds it; legacy_v*.pk3 skipped):
           <pk3>__<file> for a map pk3, <pk3>/<file> for a pack with several maps
         report research/locations/report_<YYYY-MM-DD>.txt (also printed): new and changed files against the newest
         older snapshot (removed or equal ones are not listed), snapshot maps without a file in <profile>/maps/
       python3 research/locations/locations.py diff <snapshot file> [--old]
         points of the snapshot file against the profile file (--old: against the newest older snapshot's file)
       python3 research/locations/locations.py add <snapshot file> --name N --by B [--modified M] [--date D] [--apply]
         new <profile>/maps/<map>_loc_override.dat: header + the file's locations, names fixed (see caps)
       python3 research/locations/locations.py merge <snapshot file> [--add] [--rename] [--only NAME ...] [--apply]
         into the profile file: --add points it lacks, --rename upstream names of shared points (--only: these
         upstream names); points are rewritten, consecutive equal names as @, other lines kept, added points last
       python3 research/locations/locations.py caps <profile file> ... [--apply]
         Title Case names (short words lowercase, caps and leet words kept), typo fixes, Recommended maxChars;
         a file whose names change gets today's date and the editor in Modified by
       python3 research/locations/locations.py --selftest
Without --apply, add/merge/caps only print what they would change.
"""
import argparse
import re
import shutil
import sys
import zipfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from helpers.settings import HOMEPATH, PLAYER_NAME, PROFILE, REPO  # noqa: E402

HERE = Path(__file__).resolve().parent
MAPS = REPO / PROFILE / "maps"
EDITOR = PLAYER_NAME  # settings.conf
TODAY = f"{date.today():%d-%m-%Y}"
LOC = re.compile(r"maps/([^/]+)_loc(_override)?\.dat", re.I)            # file inside a pk3
SNAP = re.compile(r"(?:.+__)?(.+)_loc(?:_override)?\.dat", re.I)        # snapshot file name -> map
POINT = re.compile(r'^\s*(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(.*?)\s*$')
SMALL = {"an", "and", "or", "of", "to", "the", "in", "at", "on", "by", "for", "from", "with", "near", "di"}
UPPER = {"mg": "MG", "cp": "CP"}
TYPO = {"llied": "Allied", "barier": "Barrier", "barriere": "Barrier", "celler": "Cellar", "commandpost": "Command Post",
        "spawnexit": "Spawn Exit", "commandroom": "Command Room", "radarpart": "Radar Part", "floornear": "Floor near",
        "neat": "near"}
WORD = re.compile(r"^((?:\^.|[(\[\"'])*)([A-Za-z][\w.'!?,]*)(.*)$")


# ---- files ------------------------------------------------------------------------------------------------------

def read(path):
    return Path(path).read_bytes().decode("latin-1").replace("\r\n", "\n").replace("\r", "\n")


def write(path, text):
    Path(path).write_bytes(text.encode("latin-1"))


def profile_file(snapshot_file):
    return MAPS / f"{SNAP.fullmatch(Path(snapshot_file).name).group(1).lower()}_loc_override.dat"


def split(text):
    """(header lines, body lines): the header is the comment block at the top."""
    lines = text.split("\n")
    i = 0
    while i < len(lines) and (not lines[i].strip() or lines[i].lstrip().startswith("//")):
        i += 1
    return lines[:i], lines[i:]


def points(lines):
    """[(x, y, z), name] per location line, @ resolved to the previous name."""
    out, name = [], None
    for line in lines:
        m = POINT.match(line)
        if m:
            n = m.group(4).replace('"', "")
            name = name if n == "@" else n
            out.append(((int(m.group(1)), int(m.group(2)), int(m.group(3))), name))
    return out


def body(pts, lines=()):
    """Location lines of pts: in place of the location lines of lines (other lines kept), the rest appended;
    consecutive equal names as @."""
    out, prev, rest = [], None, iter(pts)

    def point():
        nonlocal prev
        (x, y, z), n = next(rest)
        line, prev = f"{x} {y} {z} " + ("@" if n == prev else f'"{n}"'), n
        return line
    out = [point() if POINT.match(line) else line for line in lines]
    while out and not out[-1].strip():
        out.pop()
    return out + [point() for _ in range(len(pts) - sum(1 for line in lines if POINT.match(line)))]


# ---- header -----------------------------------------------------------------------------------------------------

def row(label, value):
    return f"// {label:<15}{value}".ljust(55) + "//"


def header(name, by, modified, recommended, edited):
    rows = [("Map name", name), ("Locations by", by)] + ([("Modified by", modified)] if modified is not None else []) + \
           [("Recommended", f"cg_locations, cg_locationMaxChars {recommended}"), ("Last edited", edited)]
    return ["/" * 57] + [row(k, v) for k, v in rows] + ["/" * 57]


REQUIRED = ("Map name", "Locations by", "Recommended", "Last edited")


def fields(head):
    """{label: (line index, value)} of the header rows; None when a required row is missing: such a header is the
    skill's to edit."""
    out = {}
    for i, line in enumerate(head):
        m = re.fullmatch(r"// (\S+(?: \S+)?)\s+(.*?)\s*//", line.strip())
        if m and m.group(1) in REQUIRED + ("Modified by",):
            out.setdefault(m.group(1), (i, m.group(2)))
    return out if out.keys() >= set(REQUIRED) else None


def finish(head, lines, renamed):
    """(text, note): Recommended = longest name; a file whose names changed gets today's date and the editor.
    A header without the profile rows is kept as it is and the note says what to set in it."""
    longest = max((len(n) for _, n in points(lines)), default=0)
    f = fields(head)
    todo = {"Recommended": f"cg_locations, cg_locationMaxChars {longest}"}
    if renamed:
        todo["Last edited"] = TODAY
        mod = f and f.get("Modified by", (None, None))[1]
        if mod is None or (EDITOR and mod == f["Locations by"][1]):
            todo["Modified by"] = EDITOR
        elif EDITOR and EDITOR not in [n.strip() for n in mod.split(",")]:
            todo["Modified by"] = f"{mod}, {EDITOR}"
    if f is None:
        note = "header without the profile rows, kept: set " + ", ".join(f"{k} {v}" for k, v in todo.items())
        return "\n".join(head + lines).rstrip("\n") + "\n", note
    head = list(head)
    for label, value in todo.items():
        if label in f:
            head[f[label][0]] = row(label, value)
        else:  # Modified by
            head.insert(f["Locations by"][0] + 1, row(label, value))
    return "\n".join(head + lines).rstrip("\n") + "\n", None


# ---- names ------------------------------------------------------------------------------------------------------

def fix_word(tok, first):
    m = WORD.match(tok)
    if not m:
        return tok
    pre, w, post = m.groups()
    core = re.match(r"[A-Za-z]+", w).group(0)
    rest = w[len(core):]
    if core.lower() in TYPO and (rest == "" or not rest[0].isalnum()):
        w = TYPO[core.lower()] + rest
        core = w.split(" ")[0]
    if w[0].islower() and (re.search(r"[a-z]\d+[a-z]", w.lower()) or re.search(r"[A-Z]", w[1:])):
        return tok                                                      # leet and nicknames: h4x0r, n00b, haX
    if len(core) > 1 and core.isupper():
        pass                                                            # AT, MG, CP
    elif core.lower() in UPPER and rest == "":
        w = UPPER[core.lower()]
    elif not first and core.lower() in SMALL and w.lower() == core.lower() and " " not in w:
        w = w.lower()
    else:
        w = w[0].upper() + w[1:]
    return pre + re.sub(r"-([a-z])", lambda x: "-" + x.group(1).upper(), w) + post


def fix_name(name):
    out, first = [], True
    for tok in name.split(" "):
        if tok:
            out.append(fix_word(tok, first))
            bare = re.sub(r"\^.", "", tok)
            first = bare in ("-", ":", "/", "|", "") or bare.endswith(":")
        else:
            out.append(tok)
    return " ".join(out)


def fix_lines(lines):
    """Lines with fixed names, {old: new}."""
    changes = {}

    def sub(m):
        new = fix_name(m.group(2))
        if new != m.group(2):
            changes[m.group(2)] = new
        return f'{m.group(1)}"{new}"'
    return [re.sub(r'^(\s*-?\d+\s+-?\d+\s+-?\d+\s+)"([^"]*)"', sub, line) for line in lines], changes


# ---- commands ---------------------------------------------------------------------------------------------------

def extract(_):
    out = HERE / f"maps_{date.today():%Y-%m-%d}"
    shutil.rmtree(out, ignore_errors=True)
    count = 0
    for pk3 in sorted((HOMEPATH / "etmain" / "dlcache").glob("*.pk3")):
        if "legacy_v" in pk3.name:
            continue
        try:
            with zipfile.ZipFile(pk3) as z:
                locs = [n for n in z.namelist() if LOC.fullmatch(n)]
                pack = len({LOC.fullmatch(n).group(1).lower() for n in locs}) > 1
                for name in locs:
                    file = Path(name).name
                    target = out / pk3.stem / file if pack else out / f"{pk3.stem}__{file}"
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(z.read(name))
                    count += 1
        except zipfile.BadZipFile:
            print(f"skipped, not a zip: {pk3.name}", file=sys.stderr)
    print(f"{count} location files written to {out}")
    # ISO dates sort as text
    older = sorted(p for p in HERE.glob("maps_????-??-??") if p.is_dir() and p.name < out.name)
    lines = compare(older[-1], out) if older else [f"{out.name}: no older snapshot to compare with"]
    text = "\n".join(lines + missing(out)) + "\n"
    (HERE / f"report_{out.name[5:]}.txt").write_text(text)
    print(text, end="")


def files(folder):
    return {p.relative_to(folder): p for p in folder.rglob("*.dat")}


def compare(old, new):
    before, after = files(old), files(new)
    added = sorted(set(after) - set(before))
    changed = sorted(f for f in set(after) & set(before) if after[f].read_bytes() != before[f].read_bytes())
    lines = [f"{new.name} compared with {old.name}: {len(added)} new, {len(changed)} changed"]
    return lines + [f"  {label:8} {f}" for label, names in (("new", added), ("changed", changed)) for f in names]


def missing(new):
    names = sorted(f for f in files(new) if not profile_file(f).exists())
    return [f"missing in {PROFILE}/maps: {len(names)}"] + [f"  missing  {f}" for f in names]


def snapshot_path(arg):
    p = Path(arg)
    return p if p.exists() else max(HERE.glob(f"maps_????-??-??/{arg}"))


def diff(args):
    src = snapshot_path(args.file)
    if args.old:
        snap, *rel = src.resolve().relative_to(HERE).parts
        snaps = sorted(p for p in HERE.glob("maps_????-??-??") if p.name < snap)
        target = snaps[-1].joinpath(*rel) if snaps else None
    else:
        target = profile_file(src)
    if not target or not target.exists():
        sys.exit(f"nothing to compare with: {target}")
    new, old = points(split(read(src))[1]), points(split(read(target))[1])
    strip = plain
    od, nd = dict(old), dict(new)
    print(f"{src.name}: {len(new)} points | {target.name}: {len(old)} points, {len(set(nd) & set(od))} shared")
    for label, pts in (("only upstream", [p for p in new if p[0] not in od]), ("only yours", [p for p in old if p[0] not in nd])):
        for (x, y, z), n in pts:
            print(f"  {label:13} {x} {y} {z} {n}")
    cosmetic = 0
    for c in sorted(set(nd) & set(od)):
        if strip(fix_name(nd[c])) == strip(od[c]):
            cosmetic += nd[c] != od[c]
        else:
            print(f"  {'name':13} {c[0]} {c[1]} {c[2]} {od[c]!r} -> upstream {nd[c]!r}")
    print(f"  {cosmetic} shared points differ only in capitalization or color")


def add(args):
    src = snapshot_path(args.file)
    target = profile_file(src)
    if target.exists():
        sys.exit(f"exists: {target} (use merge)")
    lines, changes = fix_lines(split(read(src))[1])
    head = header(args.name, args.by, args.modified, 0, args.date or "")
    out(target, *finish(head, lines, bool(changes)), changes, args.apply)


def merge(args):
    src = snapshot_path(args.file)
    target = profile_file(src)
    head, lines = split(read(target))
    mine, up = points(lines), points(split(read(src))[1])
    ud = dict(up)
    keep = lambda n: not args.only or n in args.only
    differs = lambda c, n: c in ud and keep(ud[c]) and plain(fix_name(ud[c])) != plain(n)   # not just case or color
    merged = [(c, recolor(ud[c], n) if args.rename and differs(c, n) else n) for c, n in mine]
    have = {c for c, _ in mine}
    if args.add:
        merged += [(c, n) for c, n in up if c not in have and keep(n)]
    new, changes = fix_lines(body(merged, lines))
    if points(new) == mine:
        print(f"{target.name}: nothing to merge")
        return
    out(target, *finish(head, new, True), changes, args.apply, before=mine, after=points(new))


def plain(name):
    return re.sub(r"\^.", "", name)


def recolor(upstream, mine):
    """An uncolored upstream name keeps the color code your name starts with."""
    m = re.match(r"\^.", mine)
    return m.group(0) + upstream if m and "^" not in upstream else upstream


def caps(args):
    for f in args.files:
        head, lines = split(read(f))
        new, changes = fix_lines(lines)
        out(Path(f), *finish(head, new, bool(changes)), changes, args.apply)


def out(target, text, note, changes, apply, before=None, after=None):
    print(f"== {target.name}{'' if apply else ' (dry run)'}")
    if note:
        print(f"   {note}")
    for a, b in changes.items():
        print(f"   name  {a!r} -> {b!r}")
    if before is not None:
        bd = dict(before)
        for c, n in after:
            if c not in bd:
                print(f"   added {c[0]} {c[1]} {c[2]} {n}")
            elif bd[c] != n:
                print(f"   renamed {c[0]} {c[1]} {c[2]} {bd[c]!r} -> {n!r}")
    print("   " + "\n   ".join(l for l in text.split("\n") if l.startswith("// ")))
    if apply:
        write(target, text)


def selftest():
    assert fix_name("Outside The Hut") == "Outside the Hut"
    assert fix_name("^3road to the bank") == "^3Road to the Bank"
    assert fix_name("Main Entrance AT Gun") == "Main Entrance AT Gun"
    assert fix_name("podium mg") == "Podium MG"
    assert fix_name("haX jumper") == "haX Jumper" and fix_name("Confused n00b Land") == "Confused n00b Land"
    assert fix_name("llied first spawn") == "Allied First Spawn"
    assert fix_name("ruins near axis commandpost") == "Ruins near Axis Command Post"
    assert fix_name("The Mill") == "The Mill" and fix_name("S1: the Bridge") == "S1: The Bridge"
    pts = points(['1 2 3 "A"', "4 5 6 @", '7 8 9 "B"'])
    assert pts == [((1, 2, 3), "A"), ((4, 5, 6), "A"), ((7, 8, 9), "B")]
    assert body(pts) == ['1 2 3 "A"', "4 5 6 @", '7 8 9 "B"']
    global EDITOR
    EDITOR = "Jo"
    head = header("Test Map", "someone", None, 0, "01-01-2000")
    text, note = finish(list(head), ['1 2 3 "^3Long Name"'], True)
    assert note is None and "cg_locationMaxChars 11 //" in text and "// Modified by    Jo " in text and TODAY in text
    assert all(len(l) == 57 for l in text.split("\n")[:6]), text
    head = header("Test Map", "someone", "John", 0, "01-01-2000")
    assert "John, Jo " in finish(list(head), ['1 2 3 "A"'], True)[0]                 # whole names, not substrings
    assert "01-01-2000" in finish(list(head), ['1 2 3 "A"'], False)[0]
    EDITOR = ""
    assert "// Modified by    John " in finish(list(head), ['1 2 3 "A"'], True)[0]
    text = finish(header("Test Map", "someone", None, 0, ""), ['1 2 3 "A"'], True)[0]
    assert re.search(r"^// Modified by +//$", text, re.M), text                          # empty editor: empty row
    head = header("Test Map", "someone", None, 0, "")
    head.insert(-1, "// http://example.com/locations/                     //")
    assert "example.com" in finish(head, ['1 2 3 "A"'], True)[0]                          # extra rows kept
    head = ["// Created by someone", ""]
    text, note = finish(list(head), ['1 2 3 "A"'], True)
    assert text.startswith("// Created by someone\n") and "cg_locationMaxChars 1" in note, note
    assert body([((1, 2, 3), "A"), ((4, 5, 6), "B"), ((7, 8, 9), "B")], ['1 2 3 "X"', "// floor", '4 5 6 "Y"', ""]) == \
        ['1 2 3 "A"', "// floor", '4 5 6 "B"', '7 8 9 @']
    assert recolor("Clock road", "^3Clock Road") == "^3Clock road" and recolor("^1A", "^3B") == "^1A"
    assert SNAP.fullmatch("map_b2__map_b2_loc.dat").group(1) == "map_b2"
    assert SNAP.fullmatch("pack_loc_override.dat").group(1) == "pack"
    print("selftest ok")


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--selftest", action="store_true")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("extract")
    d = sub.add_parser("diff")
    d.add_argument("file")
    d.add_argument("--old", action="store_true")
    a = sub.add_parser("add")
    a.add_argument("file")
    a.add_argument("--name", required=True)
    a.add_argument("--by", required=True)
    a.add_argument("--modified")
    a.add_argument("--date")
    a.add_argument("--apply", action="store_true")
    m = sub.add_parser("merge")
    m.add_argument("file")
    m.add_argument("--add", action="store_true")
    m.add_argument("--rename", action="store_true")
    m.add_argument("--only", nargs="+")
    m.add_argument("--apply", action="store_true")
    c = sub.add_parser("caps")
    c.add_argument("files", nargs="+")
    c.add_argument("--apply", action="store_true")
    args = p.parse_args()
    if args.selftest:
        selftest()
    elif args.cmd:
        {"extract": extract, "diff": diff, "add": add, "merge": merge, "caps": caps}[args.cmd](args)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
