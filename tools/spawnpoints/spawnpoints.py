#!/usr/bin/env python3
"""Generate map autoexecs (spawn selector) from the map pk3s: tools/spawnpoints/autoexecs/autoexec_<map>.cfg.

How the game picks the spawn spot (legacy g_team.c SelectRandomTeamSpawnPoint, same in 2.60b and nitmod):
"setspawnpt N" takes the origin of the N-th team_WOLF_objective (bsp entity order) without checking its
owner, and spawns at the team's free, enabled team_CTF_redspawn/-bluespawn closest to it. Players of the
same wave take the next closest free spot, so they alternate between rooms of similar distance.
So every N whose closest spot lies in another room is a way to choose that room (e.g. fueldump axis:
setspawnpt 3 = Allied Entrance, closest axis spot is in the west tunnel room).

Per team: spots are grouped into rooms, each room belongs to the objective closest to it. A room is
selectable when it holds the closest spot for some N (the room's own objective preferred). Spots are taken
as all enabled, so the entry is the first choice while that room is active; the others are listed as a comment.
Labels: the objective description, plus the room's location name when an objective has several selectable
rooms. Location: nearest entry of default/maps/<map>_loc_override.dat, else of a pk3's
maps/<map>_loc_override.dat or _loc.dat, else target_location entities; coordinates if none within LOC_RANGE.

Usage: tools/spawnpoints/spawnpoints.py [map ...]   (default: all maps)
       tools/spawnpoints/spawnpoints.py --selftest
"""
import math
import re
import struct
import sys
import zipfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from link_maps import DLCACHE, ETMAIN, LEGACY_PAKS, STOCK_PAKS, maps, rank  # noqa: E402
from settings import MENU, PROFILE as PROFILE_NAME, REPO  # noqa: E402

PROFILE = REPO / PROFILE_NAME
OUT = Path(__file__).resolve().parent / "autoexecs"
LIVE = PROFILE / "autoexecs"
TEMPLATE = LIVE / "autoexec_fueldump.cfg"  # settings and tail for maps without a live autoexec
LOC_RANGE = 768        # farther than this from the room centre: coordinates instead of a location name
ROOM_GAP = 224         # horizontal distance between spots of one room
ROOM_DZ = 64           # height difference between spots of one room
MAX_ENTRIES = 12       # keys 1..0, -, = of the spawn selector (spawnp0-11)
RESERVED = {"axis", "allies", "spectator", "default"}  # event autoexecs of the same name (docs/autoexec.md)
OWN_BONUS = 256        # see menu()
TEAMS = (("r", "team_ctf_redspawn", MENU["axis"], 1), ("b", "team_ctf_bluespawn", MENU["allies"], 2))  # color of the spawn name, objective spawnflag of the team


def entities(bsp):
    """Entity dicts of a bsp (lump 0)."""
    if bsp[:4] != b"IBSP":
        return []
    off, ln = struct.unpack_from("<ii", bsp, 8)
    text = bsp[off:off + ln].decode("latin1")
    return [{k.lower(): v for k, v in re.findall(r'"([^"]*)"\s+"([^"]*)"', block)}
            for block in re.findall(r"\{([^{}]*)\}", text)]


def vec(s):
    try:
        return tuple(float(x) for x in s.split()[:3])
    except ValueError:
        return None


def strip_colors(s):
    return re.sub(r"\^.", "", s).strip()


def parse_locations(text):
    """[(origin, name)] of a location file ("x y z name" per line; "@" repeats the previous name, cg_locations.c)."""
    text = re.sub(r"//[^\n]*|/\*.*?\*/", "", text, flags=re.S)
    locs, last = [], ""
    for x, y, z, name in re.findall(r"^\s*(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(.+?)\s*$", text, re.M):
        name = name.replace('"', "")
        last = last if name == "@" else strip_colors(name)
        locs.append(((float(x), float(y), float(z)), last))
    return locs


def sources():
    """{map: pk3}: stock, legacy and etmain paks first, then the best dlcache pk3 (link_maps ranking)."""
    found = {}
    for pk3 in [*STOCK_PAKS.glob("*.pk3"), *LEGACY_PAKS.glob("*.pk3"),
                *(p for p in ETMAIN.glob("*.pk3") if not p.is_symlink())]:
        for name in maps(pk3) or {}:
            found.setdefault(name, pk3)
    best = {}
    for pk3 in sorted(DLCACHE.glob("*.pk3")):
        for name, bsp in (maps(pk3) or {}).items():
            if name in found:
                continue
            r = rank(pk3, bsp.date_time)
            if name not in best or r > best[name][0]:
                best[name] = (r, pk3)
    return found | {name: pk3 for name, (_, pk3) in best.items()}


def pk3_locations(pk3s):
    """{map: location file text} from all pk3s, _loc_override over _loc."""
    locs = {}
    for pk3 in pk3s:
        try:
            with zipfile.ZipFile(pk3) as z:
                for n in z.namelist():
                    m = re.fullmatch(r"maps/(.+?)_loc(_override)?\.dat", n, re.I)
                    if m and (m[2] or m[1].lower() not in locs):
                        locs[m[1].lower()] = z.read(n).decode("latin1")
        except (zipfile.BadZipFile, OSError):
            pass
    return locs


def rooms(spots):
    """Group spot origins into rooms (single linkage)."""
    groups = []
    for s in spots:
        near = [g for g in groups if any(math.dist(s[:2], t[:2]) <= ROOM_GAP and abs(s[2] - t[2]) <= ROOM_DZ for t in g)]
        merged = [s] + [t for g in near for t in g]
        groups = [g for g in groups if g not in near] + [merged]
    return groups


def centre(room):
    return tuple(sum(c) / len(room) for c in zip(*room))


def menu(objs, spots, own=()):
    """[(setspawnpt N, owner objective index, room)] selectable rooms and [(owner, room)] unselectable ones.

    objs: [origin] in setspawnpt order (N = index + 1); spots: [origin] of one team; own: indexes of the team's
    objectives, preferred up to OWN_BONUS farther (flags and CPs often have one objective per team at one place)."""
    groups = rooms(spots)
    room_of = {s: i for i, g in enumerate(groups) for s in g}
    owner = [min(range(len(objs)), key=lambda o: math.dist(objs[o], centre(g)) - OWN_BONUS * (o in own)) for g in groups]
    hits = {}  # room -> [N]
    for n, o in enumerate(objs, 1):
        hits.setdefault(room_of[min(spots, key=lambda s: math.dist(o, s))], []).append(n)
    chosen = [((owner[r] + 1) if owner[r] + 1 in ns else ns[0], owner[r], groups[r]) for r, ns in hits.items()]
    chosen.sort(key=lambda c: (c[1], c[0]))
    missed = [(owner[r], g) for r, g in enumerate(groups) if r not in hits]
    return chosen, missed


def location(locs, point):
    if locs:
        dist, name = min((math.dist(o, point), n) for o, n in locs)
        if dist <= LOC_RANGE and name:
            return name
    return " ".join(str(round(c)) for c in point)


def analyse(ents, locs):
    """{team letter: ([(N, label, objective description)], [unselectable label])}, None if the map has no spawn objectives."""
    objs = [e for e in ents if e.get("classname", "").lower() == "team_wolf_objective"]
    origins = [vec(e.get("origin", "")) or (0.0, 0.0, 0.0) for e in objs]
    if not objs:
        return None
    result = {}
    for team, cls, _, flag in TEAMS:
        spots = [vec(e["origin"]) for e in ents
                 if e.get("classname", "").lower() == cls and vec(e.get("origin", ""))
                 and (int(e.get("spawnflags", "0") or 0) & 2 or "targetname" in e or "scriptname" in e)]
        spots = list(dict.fromkeys(spots))
        if not spots:
            result[team] = ([], [])
            continue
        chosen, missed = menu(origins, spots, {i for i, e in enumerate(objs) if int(e.get("spawnflags", "0") or 0) & flag})
        owners = [o for _, o, _ in chosen]
        desc = lambda o: strip_colors(objs[o].get("description", "")) or f"Spawn {o + 1}"
        labels = [f"{desc(o)} - {location(locs, centre(g))}" if owners.count(o) > 1 else desc(o) for _, o, g in chosen]
        labels = disambiguate(labels, [centre(g) for _, _, g in chosen])
        result[team] = ([(n, label, desc(o)) for (n, o, _), label in zip(chosen, labels)][:MAX_ENTRIES - 1],
                        list(dict.fromkeys(f"{desc(o)} - {location(locs, centre(g))}" for o, g in missed)))
    return result


def disambiguate(labels, centres):
    """Append directions (upper/lower, then north/south or east/west; +x east, +y north) to labels used by several
    rooms: height first, then the compass direction among the rooms of the same height (along their longer extent)."""
    out = list(labels)
    for label in set(labels):
        idx = [i for i, l in enumerate(labels) if l == label]
        if len(idx) < 2:
            continue
        pts = [centres[i] for i in idx]
        vertical = [""] * len(pts)
        if max(p[2] for p in pts) - min(p[2] for p in pts) > 48:
            zmid = sum(p[2] for p in pts) / len(pts)
            vertical = ["upper" if p[2] > zmid else "lower" for p in pts]
        words = []
        for p, v in zip(pts, vertical):
            same = [q for q, w in zip(pts, vertical) if w == v]  # compass only among rooms of the same height
            if len(same) < 2:
                words.append(v)
                continue
            mid = [sum(c) / len(same) for c in zip(*same)]
            span = [max(c) - min(c) for c in zip(*same)]
            c = ("east", "west")[p[0] <= mid[0]] if span[0] > span[1] else ("north", "south")[p[1] <= mid[1]]
            words.append(f"{v} {c}".strip())
        for i, word in zip(idx, words):
            out[i] = f"{label} ({word})"
    return out


def longname(z, mapname):
    for n in z.namelist():
        if n.lower().startswith("scripts/") and n.lower().endswith(".arena"):
            text = z.read(n).decode("latin1")
            for block in re.findall(r"\{([^{}]*)\}", text):
                if re.search(rf'\bmap\s+"?{re.escape(mapname)}"?\s', block, re.I):
                    m = re.search(r'longname\s+"([^"]*)"', block, re.I)
                    if m:
                        return strip_colors(m[1])
    return mapname


def template_parts(mapname):
    """(settings, tail): the lines between "// Settings" and "// Spawnpoints" and those after the last spawnsay,
    from the live autoexec_<map>.cfg (else TEMPLATE), so manual changes there carry over."""
    for path in (LIVE / f"autoexec_{mapname.lower()}.cfg", TEMPLATE):
        lines = path.read_text(encoding="latin1").splitlines() if path.exists() else []
        says = [i for i, l in enumerate(lines) if re.match(r"\s*set\s+spawnsay", l)]
        ends = [i for i, l in enumerate(lines) if l.startswith("// Spawnpoints")]
        if "// Settings" in lines and ends and says:
            return lines[lines.index("// Settings") + 1:ends[0]], lines[says[-1] + 1:]
    sys.exit(f"{TEMPLATE} lacks the // Settings, // Spawnpoints or spawnsay lines")


def render(mapname, title, pk3name, result):
    head = [f"Map name       {title}", "Generated by   Taranis with tools/spawnpoints/spawnpoints.py", f"From           {pk3name}",
            f"Last edited    {date.today():%d.%m.%Y}"]
    width = max(59, *map(len, head))
    settings, tail = template_parts(mapname)
    lines = ["/" * (width + 6), *(f"// {h:<{width}} //" for h in head), "/" * (width + 6), "",
             "// Settings", *settings]
    says = {"Default Spawn": 0}  # one per objective: rooms of one objective announce the same spawnpoint
    for team, *_ in TEAMS:
        for _, _, desc in result[team][0]:
            says.setdefault(desc, len(says))
    lines.append("// Spawnpoints")
    for team, *_ in TEAMS:
        for k, (n, _, desc) in enumerate([(0, "", "Default Spawn"), *result[team][0]]):
            lines.append(f'set spawnp{k}{team:<5}"setspawnpt {n}; vstr resetSpawnSelector; set spawnsay vstr spawnsay{says[desc]}; vstr playSelect;"')
        lines.append("")
    lines.append("// Echo spawnpoints")
    for team, _, color, _ in TEAMS:
        entries = [(0, "Default Spawn", ""), *result[team][0]]
        lines.append(f'set echosp{team:<7}"echo {MENU["head"]}SPAWNPOINTS:; ' + "; ".join(f"vstr echosp{k}{team}" for k in range(len(entries))) + '"')
        for k, (_, label, _) in enumerate(entries):
            lines.append(f'set echosp{k}{team:<5}"echo {MENU["key"]}{k + 1}. {MENU["text"] if k == 0 else color}{label}"')
        if result[team][1]:
            lines.append(f"// not selectable while the rooms above are active: {'; '.join(result[team][1])}")
        lines.append("")
    lines.append("// Announce spawnpoints")
    for label, i in says.items():
        lines.append(f'set spawnsay{i:<4}"vstr playFilter; say_teamnl ^5will spawn at {"^0" if i == 0 else "^w"}{label}"')
    return "\n".join(lines + tail) + "\n"


def selftest():
    pak0 = next(p for p in (ETMAIN / "pak0.pk3", STOCK_PAKS / "pak0.pk3") if p.exists())  # home: downloaded stock paks
    with zipfile.ZipFile(pak0) as z:
        result = analyse(entities(z.read("maps/fueldump.bsp")), [])
    axis = [n for n, *_ in result["r"][0]]
    assert axis == [1, 3, 2], axis                     # tunnel east, tunnel west (via Allied Entrance), fuel dump
    assert len(result["r"][1]) == 1, result["r"][1]    # upper fuel dump room: only after the tunnel is lost
    assert [n for n, *_ in result["b"][0]][-1] == 3, result["b"]
    print("selftest ok")


def main(args):
    if args == ["--selftest"]:
        return selftest()
    src = sources()
    locs = pk3_locations(src.values()) | pk3_locations(LEGACY_PAKS.glob("*.pk3"))
    OUT.mkdir(exist_ok=True)
    written = 0
    for mapname in args or sorted(src):
        pk3 = src.get(mapname.lower())
        if mapname.lower() in RESERVED:
            print(f"skipped: autoexec_{mapname}.cfg is a team/default autoexec", file=sys.stderr)
            continue
        if not pk3:
            print(f"not found: {mapname}", file=sys.stderr)
            continue
        with zipfile.ZipFile(pk3) as z:
            bsp = next(n for n in z.namelist() if n.lower() == f"maps/{mapname.lower()}.bsp")
            ents = entities(z.read(bsp))
            title = longname(z, mapname)
        override = PROFILE / "maps" / f"{mapname}_loc_override.dat"
        if override.exists():
            loc = parse_locations(override.read_text(encoding="latin1"))
        elif mapname in locs:
            loc = parse_locations(locs[mapname])
        else:
            loc = [(vec(e["origin"]), strip_colors(e.get("message", ""))) for e in ents
                   if e.get("classname", "").lower() == "target_location" and vec(e.get("origin", ""))]
        result = analyse(ents, loc)
        if result is None or not any(result[t][0] for t, *_ in TEAMS):
            continue
        (OUT / f"autoexec_{mapname.lower()}.cfg").write_text(render(mapname, title, pk3.name, result))
        written += 1
    print(f"{written} autoexecs written to {OUT}")


if __name__ == "__main__":
    main(sys.argv[1:])
