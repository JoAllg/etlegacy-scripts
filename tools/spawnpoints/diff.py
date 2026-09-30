#!/usr/bin/env python3
"""Compare generated map autoexecs (tools/spawnpoints/autoexecs/) with the live ones (default/autoexecs/).

Only the spawn menu counts: per team the setspawnpt arguments (spawnp<k>r/b) and their echosp<k>r/b labels,
in any order (key order is a matter of taste).

Usage: tools/spawnpoints/diff.py [--spawns] [map ...]
       --spawns  ignore label-only differences (compare setspawnpt values only)
"""
import re
import sys
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


def main(args):
    spawns_only = "--spawns" in args
    maps = [a.lower() for a in args if not a.startswith("--")]
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


if __name__ == "__main__":
    main(sys.argv[1:])
