#!/usr/bin/env python3
"""Spawnpoints that a command post turns on, from the map scripts of the map pk3s (and legacy's replacement scripts).

Purpose: find most CP spawns whose name doesn't say so, to give them a "(CP)" hint in the spawn menu through a
"// spawnname[:axis|:allies] <description> = <name> (CP)" line in default/autoexecs/autoexec_<map>.cfg
(tools/spawnpoints/spawnpoints.py). Spawns named "CP" or "Command Post" need no hint and are skipped.

A CP is built where a script event runs "sethqstatus <team> 1". Its team comes from the names of that event, its
entity and their callers ("axis", "allied"/"allies"): mappers copy the number wrongly (stock radar: "sethqstatus 0 1" for
the allied CP); the number (0 axis, 1 allies) only without a name. From every such event, and every event that triggers
one (a constructible's "built final"), the script is followed through "trigger <entity> <event>", "trigger self
<event>", accum/globalaccum "trigger_if_*" and "alertentity <entity>" (its "activate" events). A spawn objective is a CP spawn when that chain makes it visible ("setstate <objective> default") or
turns on spawn spots that start inactive ("alertentity <targetname>", no STARTACTIVE flag): the objective whose
"target" names them, else the objective closest to them.
Prints map, team, objective, check and chain of the CP spawns whose objective description (the name the game's limbo
menu shows) has neither "CP" nor "Command Post" in it; --all prints every CP spawn. check names why a hit may be wrong
(see doubt()), empty when the chain is plain.
ponytail: heuristic; a spawn turned on outside the chain (a constructible's own target, a timer) is not found.

Usage: research/cpspawns/cpspawns.py [--all] [map ...]   (default: all maps)
       research/cpspawns/cpspawns.py --selftest
"""
import argparse
import math
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "spawnpoints"))
import spawnpoints as sp  # noqa: E402
from helpers.common import LEGACY_PAKS, fix_name  # noqa: E402

CP_NAME = re.compile(r"\bcp\b|command\s*post", re.I)
DOUBT_EVENT = re.compile(r"captur|force|flag|detonat|disable|destroy|\boff\b")  # events that hint at something else than the CP opening a spawn


def parse(text):
    """{entity: {event: [lines]}} of a map script; "trigger <name>" events are stored as "<name>", all lowercase."""
    text = re.sub(r"//[^\n]*|/\*.*?\*/", "", text, flags=re.S)
    ents, depth, ent, event, last = {}, 0, None, None, ""
    for t in re.findall(r"[{}]|[^{}\n]+", text):
        t = t.strip()
        if not t:
            continue
        if t == "{":
            depth += 1
            if depth == 1:
                ent = last.split()[0].lower() if last else ""
                ents.setdefault(ent, {})
            elif depth == 2:
                words = last.lower().split()
                event = " ".join(words[1:] if words[:1] == ["trigger"] else words)
                ents[ent].setdefault(event, [])
        elif t == "}":
            depth -= 1
        else:
            if depth == 2:
                ents[ent][event].append(t)
            last = t
    return ents


def calls(ents, e, ev):
    """[(entity, event)] an event runs: trigger, trigger self, accum trigger_if_*, alertentity (its activate events)."""
    out = []
    for line in ents[e][ev]:
        w = line.lower().split()
        if w[0] == "alertentity" and len(w) >= 2:
            out += [(w[1], ev2) for ev2 in ents.get(w[1], {}) if ev2.startswith("activate")]
        elif (w[0] == "trigger" and len(w) >= 3) or (w[0] in ("accum", "globalaccum") and len(w) >= 6 and w[2].startswith("trigger_if")):
            out.append((e if w[-2] == "self" else w[-2], w[-1]))
    return [c for c in out if c[1] in ents.get(c[0], {})]


def hq_team(names, number):
    """0 axis / 1 allies of a "sethqstatus" event from the names of its event, entity and callers, else its number."""
    text = " ".join(names)
    axis, allies = "axis" in text, bool(re.search(r"allie[ds]", text))
    return 0 if axis and not allies else 1 if allies and not axis else number


def enabled(ents, team):
    """{name: chain} of the names the "CP built" chain of team 0/1 sets to default or alerts; chain = "entity:event > ...".
    The chain starts at the events with "sethqstatus <team> 1" and at every event that triggers one of them: a
    constructible's "built final" often turns the spawn on itself and runs the HQ status in a sibling event."""
    callers = {}
    for e, evs in ents.items():
        for ev in evs:
            for c in calls(ents, e, ev):
                callers.setdefault(c, set()).add((e, ev))
    roots = set()
    for e, evs in ents.items():
        for ev, lines in evs.items():
            hq = [int(m[1]) for m in (re.match(r"sethqstatus\s+(\d)\s+1\b", line, re.I) for line in lines) if m]
            if hq and hq_team([e, ev, *(f"{c} {cev}" for c, cev in callers.get((e, ev), ()))], hq[0]) == team:
                roots.add((e, ev))
    up = list(roots)
    while up:
        for c in callers.get(up.pop(), ()):
            if c not in roots:
                roots.add(c)
                up.append(c)
    stack = [(e, ev, f"{e}:{ev}") for e, ev in sorted(roots)]
    seen, names = set(), {}
    while stack:
        e, ev, chain = stack.pop()
        if (e, ev) in seen:
            continue
        seen.add((e, ev))
        for line in ents[e][ev]:
            w = line.lower().split()
            if w[0] == "setstate" and len(w) >= 3 and w[2] == "default":
                names.setdefault(w[1], chain)
            elif w[0] == "alertentity" and len(w) >= 2:
                names.setdefault(w[1], chain)
        stack += [(c[0], c[1], f"{chain} > {c[0]}:{c[1]}") for c in calls(ents, e, ev)]
    return names


def cp_spawns(ents, names):
    """{objective description: chain} of the spawn objectives the names turn on."""
    objs = [e for e in ents if e.get("classname", "").lower() == "team_wolf_objective"]
    spots = [e for e in ents if e.get("classname", "").lower() in ("team_ctf_redspawn", "team_ctf_bluespawn")
             and sp.vec(e.get("origin", "")) and not int(e.get("spawnflags", "0") or 0) & 2]
    desc = lambda i: fix_name(sp.label(objs[i].get("description", "").replace("_", " "))) or f"Spawn {i + 1}"
    found = {}
    for i, o in enumerate(objs):
        for key in ("targetname", "scriptname"):
            if o.get(key, "").lower() in names:
                found.setdefault(desc(i), f"{names[o[key].lower()]} > setstate {o[key]} default")
    for name, chain in names.items():
        group = [sp.vec(s["origin"]) for s in spots if s.get("targetname", "").lower() == name]
        if group and objs:
            linked = [i for i, o in enumerate(objs) if o.get("target", "").lower() == name]
            i = linked[0] if linked else min(range(len(objs)), key=lambda j: math.dist(sp.vec(objs[j].get("origin", "")) or (0, 0, 0), sp.centre(group)))
            found.setdefault(desc(i), f"{chain} > alertentity {name}" + ("" if linked else " (closest objective)"))
    return found


def doubt(chain):
    """Why a chain may not mean "the CP opens this spawn", "" if it looks plain."""
    if chain.endswith("(closest objective)"):
        return "objective guessed from the spots' position"
    if " > alertentity " in chain:
        return "alertentity toggles: may turn spots off"
    events = [step.split(":", 1)[1] for step in chain.split(": ", 1)[-1].split(" > ")[1:] if ":" in step]
    odd = [ev for ev in events if DOUBT_EVENT.search(ev)]
    return f"via {', '.join(odd)}" if odd else ""


def scripts(mapname, pk3):
    """[(pk3 name, script text)]: the map pk3's script, legacy's replacement scripts."""
    out = []
    for p in [pk3, *LEGACY_PAKS.glob("*.pk3")]:
        try:
            with zipfile.ZipFile(p) as z:
                out += [(p.name, z.read(n).decode("latin1")) for n in z.namelist() if n.lower() == f"maps/{mapname}.script"]
        except (zipfile.BadZipFile, OSError):
            pass
    return out


def selftest():
    script = """
    game_manager { spawn { setstate cp_wobj invisible } }
    cp_hq  // the CP
    {
        trigger built
        {
            sethqstatus 0 1
            trigger self spawns_on
        }
        trigger spawns_on
        {
            setstate cp_wobj default
            alertentity cp_spots
        }
        trigger destroyed { sethqstatus 0 0 setstate other_wobj default }
    }
    cp_built  // constructible: spawn on itself, HQ status in a sibling event
    {
        built final
        {
            trigger cp_hq built
            trigger self spawn2
        }
        trigger spawn2 { setstate cp2_wobj default }
    }
    """
    ents = parse(script)
    assert ents["cp_hq"]["built"] == ["sethqstatus 0 1", "trigger self spawns_on"], ents
    assert enabled(ents, 1) == {}
    names = enabled(ents, 0)
    assert set(names) == {"cp_wobj", "cp_spots", "cp2_wobj"} and names["cp_wobj"] == "cp_hq:built > cp_hq:spawns_on", names
    bsp = [{"classname": "team_WOLF_objective", "targetname": "cp_wobj", "description": "Back_spawn", "origin": "0 0 0"},
           {"classname": "team_WOLF_objective", "targetname": "other", "description": "Barracks", "origin": "900 0 0"},
           {"classname": "team_CTF_redspawn", "targetname": "cp_spots", "spawnflags": "1", "origin": "800 0 0"}]
    found = cp_spawns(bsp, names)
    assert set(found) == {"Back Spawn", "Barracks"} and found["Barracks"].endswith("(closest objective)"), found
    assert hq_team(["allied_radio_built_model", "enable_allied_features"], 0) == 1 and hq_team(["neutral_cp", "built"], 0) == 0
    assert doubt("x.pk3: cp:built final > setstate a_wobj default") == ""
    assert doubt("x.pk3: cp:built final > flag:force_allies > setstate a_wobj default") == "via force_allies"
    assert doubt("x.pk3: cp:built final > alertentity spots").startswith("alertentity")
    assert CP_NAME.search("Allied CP Spawn") and CP_NAME.search("command post") and not CP_NAME.search("Capture Spawn")
    print("selftest ok")


def main(args, show_all):
    src = sp.sources()
    noscript = []
    for mapname in [a.lower() for a in args] or sorted(src):
        pk3 = src.get(mapname)
        if not pk3:
            print(f"not found: {mapname}", file=sys.stderr)
            continue
        try:
            with zipfile.ZipFile(pk3) as z:
                ents = sp.entities(z.read(next(n for n in z.namelist() if n.lower() == f"maps/{mapname}.bsp")))
        except Exception as error:  # one unreadable map must not stop the others
            print(f"failed: {mapname} ({pk3.name}): {error!r}", file=sys.stderr)
            continue
        texts = scripts(mapname, pk3)
        if not texts:
            noscript.append(mapname)
            continue
        found = {}
        for pk3name, text in texts:
            for team in (0, 1):
                for d, chain in cp_spawns(ents, enabled(parse(text), team)).items():
                    found.setdefault((("axis", "allies")[team], d), f"{pk3name}: {chain}")
        for (team, d), chain in sorted(found.items()):
            if show_all or not CP_NAME.search(d):
                print(f"{mapname}\t{team}\t{d}\t{doubt(chain)}\t{chain}")
    if noscript:
        print(f"no script: {' '.join(noscript)}", file=sys.stderr)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("maps", nargs="*", metavar="map")
    ap.add_argument("--all", action="store_true", help="also CP spawns that have CP or Command Post in their name")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    selftest() if a.selftest else main(a.maps, a.all)
