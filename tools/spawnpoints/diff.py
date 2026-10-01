#!/usr/bin/env python3
"""Compare generated map autoexecs (tools/spawnpoints/autoexecs/) with the live ones (default/autoexecs/).

Only the spawn menu counts: per team the setspawnpt arguments (spawnp<k>r/b) and their echosp<k>r/b labels,
in any order (key order is a matter of taste).

Usage: tools/spawnpoints/diff.py [--spawns] [map ...]
       --spawns  ignore label-only differences (compare setspawnpt values only)
       tools/spawnpoints/diff.py --selftest
"""
import argparse
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from settings import PROFILE, REPO  # noqa: E402

HERE = Path(__file__).resolve().parent
GENERATED = HERE / "autoexecs"
LIVE = REPO / PROFILE / "autoexecs"


def menu(path):
    """{(team, key): (setspawnpt argument, label)} of an autoexec."""
    sets = dict(re.findall(r'^\s*set\s+(spawnp\d+[rb]|echosp\d+[rb])\s+"(.*)"', path.read_text(encoding="latin1"), re.M))

    def resolve(name, depth=0):  # "vstr spawnp1r" style references
        value = sets.get(name, "")
        m = re.fullmatch(r"\s*vstr\s+(\S+?);?\s*", value)
        return resolve(m[1], depth + 1) if m and depth < 5 else value

    out = {}
    for name in sets:
        m = re.fullmatch(r"spawnp(\d+)([rb])", name)
        if not m:
            continue
        spawn = re.search(r"setspawnpt\s+([\d ]*\d)", resolve(name))
        label = re.sub(r"\^.", "", resolve(f"echosp{m[1]}{m[2]}"))
        label = re.sub(r"^\s*echo\s+|;\s*$", "", label).strip()
        label = re.sub(r"^\d+\.?\s*", "", label)
        out[(m[2], int(m[1]))] = (spawn[1] if spawn else "-", label)
    return out


def main(maps, spawns_only):
    maps = [m.lower() for m in maps]
    generated = {p.stem[9:]: p for p in GENERATED.glob("autoexec_*.cfg")}
    live = {p.stem[9:]: p for p in LIVE.glob("autoexec_*.cfg")}
    names = maps or sorted(generated.keys() & live.keys())
    same = 0
    for name in names:
        if name not in generated or name not in live:
            print(f"{name}: {'no generated' if name not in generated else 'no live'} autoexec")
            continue
        a, b = menu(live[name]), menu(generated[name])
        lines = []
        for team, title in (("r", "axis"), ("b", "allies")):
            old = {v: l for (t, _), (v, l) in sorted(a.items()) if t == team}
            new = {v: l for (t, _), (v, l) in sorted(b.items()) if t == team}
            if old.keys() != new.keys() or (not spawns_only and old != new):
                lines.append(f"  {title:<7}live: " + ", ".join(f"{v} {l}" for v, l in old.items()))
                lines.append(f"  {'':<7}gen:  " + ", ".join(f"{v} {l}" for v, l in new.items()))
        if lines:
            print(name, *lines, sep="\n")
        else:
            same += 1
    if not maps:
        print(f"\n{len(names)} maps in both, {same} without differences; "
              f"{len(live.keys() - generated.keys())} only live, {len(generated.keys() - live.keys())} only generated")


def selftest():
    with tempfile.NamedTemporaryFile("w", suffix=".cfg", encoding="latin1") as f:
        f.write('set spawnp0r "setspawnpt 3; vstr resetSpawnSelector"\nset spawnp0b "vstr spawnp0r;"\n'
                'set spawnp1b ""\nset echosp0r "echo ^31. ^iTunnel (east)"\nset echosp0b "vstr echosp0r"\n')
        f.flush()
        got = menu(Path(f.name))
    assert got == {("r", 0): ("3", "Tunnel (east)"), ("b", 0): ("3", "Tunnel (east)"), ("b", 1): ("-", "")}, got
    print("selftest ok")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("maps", nargs="*", metavar="map")
    ap.add_argument("--spawns", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    selftest() if a.selftest else main(a.maps, a.spawns)
