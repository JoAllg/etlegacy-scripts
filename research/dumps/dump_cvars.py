#!/usr/bin/env python3
"""Launch ET: Legacy per mod on a local map, run cvarlist/cmdlist via the stdin console, parse into TSV.

Usage: python3 dump_cvars.py [mod ...]   (default: every mod found in fs_homepath, legacy in the client's fs_basepath)
       python3 dump_cvars.py --list      print what would run per mod, start nothing
       python3 dump_cvars.py --parse <dir> ...   re-parse existing console.log files without launching the game
       python3 dump_cvars.py --selftest
Output: research/dumps/<mod>_<version>/{console.log,modules.tsv,cvars.tsv,cmds.tsv}; nothing is written for a failed run.
Every mod runs with the 32-bit client (GAME_BIN_I386; GAME_BIN if that is not set), so all dumps share one engine
build. Its fs_basepath is read from the dedicated server next to it (each client has its own install path, not BASEPATH of
settings.conf). legacy = the pk3 and qagame of that install, version from `<client> --version`.
Per mod: the newest original pk3 (<mod>[-_]v?<version>.pk3) and the qagame module of the client's arch run in a temporary
fs_homepath (no profile, no other pk3s); mods without that module can't host locally and are skipped.
Engine cvars (client/server side) need the ET: Legacy source: ETLEGACY_SRC in settings.conf (asked by deploy.sh) or the environment.
Next: python3 build_docs.py, then python3 diff_profile.py
"""
import argparse
import functools
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from build_docs import MAP  # noqa: E402
from helpers.settings import ETLEGACY_SRC, GAME_BIN, GAME_BIN_I386, HOMEPATH  # noqa: E402

# Cvar set on the command line: the only user-created ('?') row of a run without configs
MARKER = "dump_marker"
OUT = Path(__file__).resolve().parent
READY = re.compile(r"^CL_InitCGame:")
DONE = re.compile(r"^\d+ commands$")
ANSI = re.compile(r"\x1b\[[0-9;]*m")
# Com_Printf prefixes every new line with "%8i " (snapshot server time)
STAMP = re.compile(r"^[ \d-]{8} ")
# 12 flag columns, name, "value", - or ! (value differs from default), "default"
CVAR = re.compile(r'^(.{12}) (\S+)\s+"(.*)" (?:-|\^3!|!) "(.*)"$')
CMD = re.compile(r"^(\S+)\s*(?:: (.*))?$")
# ET: Legacy source checkout: engine cvars are sorted into client/server by the directory registering
# (Cvar_Get*) or creating (Cvar_Set) them
ETL_SRC = Path(ETLEGACY_SRC)
MOD_DIRS = {"cgame", "game", "ui", "tvgame"}
REGISTER = re.compile(rb'Cvar_(?:Get(?:AndDescribe)?|Set)\s*\(\s*"([^"]+)"')
LOADED = re.compile(r"^Sys_LoadDll\((/\S+)\)\.\.\. succeeded$")
STRING = re.compile(rb"[\x20-\x7e]{3,}")
WHITESPACE = re.compile(rb"\s")
CLIENT_PREFIX = ("cg_", "cl_", "ui_")
FAILURE = re.compile(r"ERROR|Sys_Error|Signal|Segmentation|crash|Com_Error|failed", re.I)
# one client for every mod: the 32-bit one runs the i386-only mods too
CLIENT = GAME_BIN_I386 or GAME_BIN
ARCH = "i386" if GAME_BIN_I386 else "x86_64"
QAGAME = f"qagame.mp.{ARCH}.so"
NO_QAGAME = f"no server module ({ARCH})"
# `/path` rows of the search path the game prints at startup ("   0 D /x/home/probe"), colors stripped
SEARCH_DIR = re.compile(r"^ *[0-9-]* +D +(.*)$")
CARET = re.compile(r"\^.")


class Fail(Exception):
    pass


def pk3_version(mod, name):
    """Version tuple of an original mod pk3 name, else None (renamed or patched pk3s don't match)."""
    m = re.match(rf"^{re.escape(mod)}[-_]v?(\d+(?:[._]\d+)*)\.pk3$", name, re.I)
    return tuple(int(x) for x in re.split(r"[._]", m[1])) if m else None


def newest(mod, names):
    """(version, [names with that version]); (None, []) without a match."""
    found = {n: v for n in names if (v := pk3_version(mod, n))}
    top = max(found.values(), default=None)
    return top, sorted(n for n, v in found.items() if v == top)


def search_dirs(text):
    """(fs_homepath, fs_basepath) from the game's search path output: the first two directory rows, each
    with its mod folder (last component) removed."""
    rows = [m[1] for l in text.splitlines() if (m := SEARCH_DIR.match(CARET.sub("", ANSI.sub("", l))))][:2]
    if len(rows) < 2:
        raise Fail("search path not found in the output of the dedicated server")
    return Path(rows[0]).parent, Path(rows[1]).parent


def probe_basepath(tmp):
    """fs_basepath of CLIENT, read from its dedicated server (<dir>/etlded<suffix> next to <dir>/etl<suffix>)
    run in a throwaway fs_homepath inside tmp: the client has its own install path."""
    client = Path(CLIENT)
    ded = client.with_name("etlded" + client.name.removeprefix("etl"))
    if not ded.is_file():
        sys.exit(f"dedicated server {ded} not found: it is read for the fs_basepath of {client.name}")
    home = Path(tmp) / "probe_home"
    home.mkdir()
    try:
        # stdin not a terminal, else the tty console adds a prompt and \r to every line
        out = subprocess.run([ded, "+set", "fs_homepath", str(home), "+set", "fs_game", "dump_probe", "+quit"],
                             stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30)
        base = search_dirs(out.stdout + out.stderr)[1]
    except (Fail, subprocess.TimeoutExpired) as e:
        sys.exit(f"fs_basepath of {client.name} not readable from {ded.name}: {e}")
    if not (base / "etmain").is_dir():
        sys.exit(f"fs_basepath {base} of {client.name} has no etmain")
    return base


def mod_dirs(home):
    """Mods in fs_homepath: real directories except etmain and profiles; legacy lives in fs_basepath."""
    return sorted({"legacy"} | {p.name for p in home.iterdir()
                                if p.is_dir() and not p.is_symlink() and p.name not in ("etmain", "profiles")})


def installed_version(binary):
    """Version tuple of the game binary ('ET Legacy v2.86.0 ...' from --version), else None."""
    out = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=30).stdout
    m = re.search(r"ET Legacy v(\d+(?:\.\d+)*)", out)
    return tuple(map(int, m[1].split("."))) if m else None


def discover(home, base):
    """{mod: {version, pk3 [Path], qagame Path | None}}; version None = no original pk3.
    A file in both paths counts once, the homepath one wins. legacy is the installed game's own mod:
    only fs_basepath, the pk3 of the client's version."""
    mods = {}
    for mod in mod_dirs(home):
        if mod == "legacy":
            files = {p.name: p for p in (base / mod).iterdir() if p.is_file()} if (base / mod).is_dir() else {}
            version = installed_version(CLIENT)
            if not version:
                mods[mod] = {"version": None, "pk3": [], "qagame": None,
                             "why": f"cannot read the version from '{CLIENT} --version'"}
                continue
            pk3 = f"legacy_v{'.'.join(map(str, version))}.pk3"
            mods[mod] = {"version": version if pk3 in files else None, "pk3": [files[pk3]] if pk3 in files else [],
                         "qagame": files.get(QAGAME)}
            continue
        dirs = [home / mod, base / mod]
        files = {}
        for d in reversed(dirs):
            if d.is_dir():
                files.update({p.name: p for p in d.iterdir() if p.is_file()})
        version, names = newest(mod, files)
        mods[mod] = {"version": version, "pk3": [files[n] for n in names], "qagame": files.get(QAGAME)}
    return mods


def folder_name(mod, version):
    return f"{mod}_{'.'.join(map(str, version))}"


def choose(mod, paths):
    if len(paths) == 1:
        return paths[0]
    if not sys.stdin.isatty():
        raise Fail(f"several pk3s match the newest version, run on a terminal to choose: {', '.join(p.name for p in paths)}")
    for i, p in enumerate(paths, 1):
        print(f"  {i}: {p}")
    while True:
        a = input(f"[{mod}] which pk3 (1-{len(paths)})? ").strip()
        if a.isdigit() and 1 <= int(a) <= len(paths):
            return paths[int(a) - 1]


def failure_reason(lines, rc):
    """The game's own error lines, else the exit code (None = killed on timeout)."""
    errors = [l.strip() for l in lines if FAILURE.search(l)][-3:]
    return "; ".join(errors) or ("timeout" if rc is None else f"exit code {rc}")


def run(mod, info, tmp):
    """Dump one mod; the output folder is created only when the run succeeded."""
    if not info["qagame"]:
        raise Fail(NO_QAGAME)
    qagame = info["qagame"]
    pk3 = choose(mod, info["pk3"])
    moddir = Path(tmp) / mod
    moddir.mkdir()
    for f in (pk3, qagame):
        if f.parent == HOMEPATH / mod:
            shutil.copy2(f, moddir)
    lines = launch(mod, CLIENT, tmp)
    outdir = OUT / folder_name(mod, info["version"])
    outdir.mkdir(exist_ok=True)
    (outdir / "console.log").write_text("\n".join(lines) + "\n", encoding="utf-8")
    # the binaries vanish with the temporary homepath
    (outdir / "modules.tsv").write_text("side\tstring\n" + "".join(f"{s}\t{t}\n" for s, t in module_strings(lines)),
                                        encoding="utf-8")
    return write_tsv(outdir, lines)


def launch(mod, binary, tmp):
    """Console lines of a complete run; Fail without data (crash, timeout)."""
    lines = []
    seen = threading.Condition()
    eof = False

    proc = subprocess.Popen(
        # small window: the default r_mode -2 opens a window of desktop size (src/sdl/sdl_glimp.c);
        # no fs_basepath: each client keeps its own install (the 32-bit one has its own renderer libs)
        [binary, "+set", "fs_homepath", str(tmp), "+set", "fs_game", mod,
         "+set", "dedicated", "0", "+set", "r_fullscreen", "0", "+set", "r_mode", "-1",
         "+set", "r_customwidth", "640", "+set", "r_customheight", "480", "+set", MARKER, "1", "+map", MAP],
        cwd=tmp, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    def reader():
        nonlocal eof
        for raw in proc.stdout:
            line = STAMP.sub("", ANSI.sub("", raw.decode("utf-8", "replace")).rstrip("\r\n"))
            with seen:
                lines.append(line)
                seen.notify_all()
        with seen:
            eof = True
            seen.notify_all()

    def wait_for(pattern, timeout, start=0):
        """True once the pattern was printed; returns early when the game's output ended."""
        with seen:
            seen.wait_for(lambda: eof or any(pattern.match(l) for l in lines[start:]), timeout)
            return any(pattern.match(l) for l in lines[start:])

    def fail(why=None):
        proc.kill()
        rc = proc.wait()
        raise Fail(failure_reason(lines, None if why == "timeout" else rc))

    threading.Thread(target=reader, daemon=True).start()
    try:
        if not wait_for(READY, 120):
            fail("timeout" if not eof else None)
        with seen:  # let map/team autoexecs and late registrations finish
            seen.wait_for(lambda: eof, 5)
            if eof:
                fail()
        sent = len(lines)
        try:
            proc.stdin.write(b"cvarlist;cmdlist\n")
            proc.stdin.flush()
        except BrokenPipeError:
            fail()
        if not wait_for(DONE, 30, sent):
            fail("timeout" if not eof else None)
        try:
            proc.stdin.write(b"quit\n")
            proc.stdin.flush()
            proc.wait(30)
        except (subprocess.TimeoutExpired, BrokenPipeError):
            pass  # the data is complete
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
    return lines


def parse(lines):
    """Blocks are located by their footers: '<n> total cvars', '<n> cvar indexes', '<n> commands'."""
    idx = max((i for i, l in enumerate(lines) if re.match(r"^\d+ cvar indexes$", l)), default=None)
    if idx is None:
        return [], [], 0
    # Scan forward to the footer, skipping non-matching lines: cvar values may span several lines
    # (s_alAvailableDevices lists one audio device per line), which truncates a backwards walk.
    cvars, user, total = [], [], 0
    for line in lines[:idx]:
        if not (m := CVAR.match(line)):
            continue
        total += 1
        # '?' = user-created (command line), not registered by engine or mod.
        # The engine clears CVAR_USER_CREATED as soon as mod code registers the cvar and takes the
        # code default as resetString (src/qcommon/cvar.c Cvar_Get), so a surviving '?' row is one
        # only the command line knows.
        if "?" in m[1]:
            user.append(m[2].lower())
            continue
        cvars.append((m[2], m[1].replace(" ", ""), m[3], m[4]))
    # Without configs the only '?' row is MARKER. Missing means the flag column moved: a
    # user-created cvar would be dumped as if the mod registered it.
    if MARKER not in user:
        print(f"WARNING: marker cvar {MARKER} not user-created ('?') among {total} parsed rows - flag parsing broken?")
    elif len(user) > 1:
        print(f"WARNING: unexpected user-created cvars: {', '.join(sorted(set(user) - {MARKER}))}")
    cmds = []
    for line in lines[idx + 1:]:
        if DONE.match(line):
            break
        if m := CMD.match(line):
            cmds.append((m[1], (m[2] or "").strip()))
    return cvars, cmds, len(user)


@functools.lru_cache(maxsize=None)  # the source tree is the same for every mod of a run
def engine_cvars():
    """(client, server): {name: source file} of cvars the engine registers outside / inside src/server;
    qcommon counts as client."""
    if not ETLEGACY_SRC or not (ETL_SRC / "src/server").is_dir():
        sys.exit("ET: Legacy source checkout needed: set ETLEGACY_SRC in settings.conf (deploy.sh) or the environment")
    client, server = {}, {}
    for f in sorted((ETL_SRC / "src").rglob("*.c*")):
        rel = f.relative_to(ETL_SRC / "src")
        if rel.parts[0] not in MOD_DIRS:
            for m in REGISTER.findall(f.read_bytes()):
                (server if rel.parts[0] == "server" else client).setdefault(m.decode().lower(), str(rel))
    return client, server


def loaded_modules(lines):
    """{'client': cgame/ui paths, 'server': qagame paths} from the Sys_LoadDll lines."""
    files = {m[1] for l in lines if (m := LOADED.match(l))}
    return {"client": sorted(f for f in files if Path(f).name.startswith(("cgame.", "ui."))),
            "server": sorted(f for f in files if Path(f).name.startswith("qagame."))}


def module_strings(lines):
    """[(side, string)] of the loaded module binaries: sorted, deduplicated, lowercased, without whitespace
    (cvar names have none)."""
    return sorted({(side, s.decode().lower()) for side, files in loaded_modules(lines).items() for f in files
                   for s in STRING.findall(Path(f).read_bytes()) if not WHITESPACE.search(s)})


def read_modules(outdir, lines):
    """(client, server) string sets: modules.tsv, else the binaries at the logged paths."""
    tsv = outdir / "modules.tsv"
    if tsv.exists():
        pairs = [r.split("\t", 1) for r in tsv.read_text(encoding="utf-8").splitlines()[1:]]
    else:
        files = [f for fs in loaded_modules(lines).values() for f in fs]
        if not files or not all(Path(f).exists() for f in files):
            sys.exit(f"{outdir}: no modules.tsv and the module binaries of the log are not available: "
                     "client and server cvars can't be told apart")
        pairs = module_strings(lines)
    return {s for side, s in pairs if side == "client"}, {s for side, s in pairs if side == "server"}


def classify(name, flags, engine, modules):
    """(side, source). Mod cvars are located by their name string in the module binaries. A name in
    both, or in neither (built at runtime: session%i, fireteam%i), is the client's if userinfo or
    client-prefixed, else a server value (ui host menu, cgame mirrors like g_gametype, session data)."""
    n = name.lower()
    if n.startswith("sv_") or (n in engine[1] and n not in engine[0]):
        return "server", "engine"
    if n in engine[0]:
        return "client", "engine"
    in_cl, in_sv = n in modules[0], n in modules[1]
    if in_cl != in_sv:
        return ("client", "cgame/ui") if in_cl else ("server", "qagame")
    side = "client" if "U" in flags or n.startswith(CLIENT_PREFIX) else "server"
    return side, "both" if in_cl else "-"


def write_tsv(outdir, lines):
    cvars, cmds, skipped = parse(lines)
    engine, modules = engine_cvars(), read_modules(outdir, lines)
    with open(outdir / "cvars.tsv", "w", encoding="utf-8") as f:
        f.write("name\tflags\tvalue\tdefault\tside\tsource\n")
        f.writelines("\t".join((*c, *classify(c[0], c[1], engine, modules))) + "\n"
                     for c in sorted(cvars, key=lambda c: c[0].lower()))
    with open(outdir / "cmds.tsv", "w", encoding="utf-8") as f:
        f.write("name\tdescription\n")
        f.writelines("\t".join(c) + "\n" for c in sorted(set(cmds), key=lambda c: c[0].lower()))
    print(f"[{outdir.name}] {len(cvars)} cvars ({skipped} user-created skipped), {len(cmds)} commands")
    return f"{outdir.name}: {len(cvars)} cvars, {len(cmds)} commands"


def plan(mods, base):
    """Print per mod what would run."""
    print(f"binary {CLIENT}, fs_basepath {base}")
    for mod, i in mods.items():
        if not i["version"]:
            print(f"{mod}: {i.get('why', 'no original pk3')}")
        else:
            print(f"{mod}: {folder_name(mod, i['version'])}, pk3 {', '.join(p.name for p in i['pk3'])}, "
                  f"{'qagame ' + str(i['qagame']) if i['qagame'] else NO_QAGAME}")


def main(names, list_only):
    with tempfile.TemporaryDirectory() as tmp:
        base = probe_basepath(tmp)
        mods = discover(HOMEPATH, base)
        if unknown := [n for n in names if n not in mods]:
            sys.exit(f"unknown mod: {', '.join(unknown)}; discovered: {', '.join(m for m, i in mods.items() if i['version'])}")
        mods = {m: mods[m] for m in names} if names else mods
        if list_only:
            return plan(mods, base)
        dumped, nopk3, noqagame, failed = [], [], [], {}
        for mod, info in mods.items():
            if "why" in info:
                failed[mod] = info["why"]
                continue
            if not info["version"]:
                nopk3.append(mod)
                continue
            try:
                dumped.append(run(mod, info, tmp))
            except Fail as e:
                (noqagame.append(mod) if str(e) == NO_QAGAME else failed.__setitem__(mod, str(e)))
                print(f"[{mod}] {e}")
    print("\nSummary")
    for d in dumped:
        print(f"  dumped  {d}")
    for mod in noqagame:
        print(f"  {NO_QAGAME}  {mod}")
    for mod, why in failed.items():
        print(f"  failed  {mod}: {why}")
    if nopk3:
        print(f"  no original pk3: {', '.join(nopk3)}")
    sys.exit(1 if failed else 0)


def selftest():
    from contextlib import redirect_stdout
    from io import StringIO
    marker = f'    A?       {MARKER} "1" - "1"'
    lines = ['    A        cg_fov "90" - "90"', marker, '  S    R     sv_x "1" ^3! "0"', "noise",
             "3 total cvars", "3 cvar indexes", "+attack", "team : join a team", "2 commands", "late"]
    out = StringIO()
    with redirect_stdout(out):
        cvars, cmds, skipped = parse(lines)
    assert cvars == [("cg_fov", "A", "90", "90"), ("sv_x", "SR", "1", "0")] and skipped == 1, (cvars, skipped)
    assert cmds == [("+attack", ""), ("team", "join a team")], cmds
    assert not out.getvalue(), out.getvalue()
    for bad, text in ((lines[:1] + lines[2:], "not user-created"),
                      (lines[:2] + ['    A?       myAlias "x" - "x"'] + lines[2:], "unexpected user-created cvars: myalias")):
        out = StringIO()
        with redirect_stdout(out):
            parse(bad)
        assert text in out.getvalue(), out.getvalue()
    engine, modules = ({"com_maxfps": "qcommon/common.c"}, {"g_x": "server/sv_init.c"}), ({"cg_fov", "g_both"}, {"g_both", "g_y"})
    got = [classify(n, f, engine, modules) for n, f in (("sv_x", ""), ("g_x", ""), ("com_maxFps", ""), ("cg_fov", "A"),
                                                        ("g_y", ""), ("g_both", ""), ("name2", "U"))]
    assert got == [("server", "engine"), ("server", "engine"), ("client", "engine"), ("client", "cgame/ui"),
                   ("server", "qagame"), ("server", "both"), ("client", "-")], got
    for name, mod, v in (("nitmod_2.3.5.pk3", "nitmod", (2, 3, 5)), ("jaymod-2.2.0.pk3", "jaymod", (2, 2, 0)),
                         ("etpro-3_2_6.pk3", "etpro", (3, 2, 6)), ("legacy_v2.86.0.pk3", "legacy", (2, 86, 0)),
                         ("Nitmod_2.3.5.PK3", "nitmod", (2, 3, 5)), ("~~~nitmod_2.3.5.pk3", "nitmod", None),
                         ("nitmod_2.3.5._custom.pk3", "nitmod", None), ("zzz_etps_4.pk3", "etps", None),
                         ("nitmod_2.3.5.pk3.tmp", "nitmod", None), ("nitmod2_2.3.5.pk3", "nitmod", None)):
        assert pk3_version(mod, name) == v, (name, pk3_version(mod, name))
    names = ["legacy_v2.84.0.pk3", "legacy_v2.86.0.pk3", "legacy_v2.9.0.pk3", "legacy_v2.85.0.pk3", "zz_legacy_v3.pk3"]
    assert newest("legacy", names) == ((2, 86, 0), ["legacy_v2.86.0.pk3"])  # int tuples: 86 > 9
    assert newest("legacy", names + ["Legacy_v2_86_0.pk3"]) == ((2, 86, 0), ["Legacy_v2_86_0.pk3", "legacy_v2.86.0.pk3"])
    assert newest("x", names) == (None, [])
    assert folder_name("etpro", (3, 2, 6)) == "etpro_3.2.6"
    assert failure_reason(["a", "Signal caught", "b"], 139) == "Signal caught"
    assert failure_reason(["a"], 1) == "exit code 1" and failure_reason(["a"], None) == "timeout"
    with tempfile.TemporaryDirectory() as t:
        home, base = Path(t) / "home", Path(t) / "base"
        other = "qagame.mp.x86_64.so" if ARCH == "i386" else "qagame.mp.i386.so"
        for p in ("home/m1", "home/etmain", "home/profiles", "home/none", "base/legacy", "base/m1"):
            (Path(t) / p).mkdir(parents=True)
        (home / "link").symlink_to(home / "m1")
        for p in ("home/m1/m1-1_0.pk3", "home/m1/m1-1_2.pk3", "base/m1/m1-1_2.pk3", f"base/m1/{QAGAME}",
                  "base/legacy/legacy_v2.0.pk3", f"base/legacy/{other}"):
            (Path(t) / p).touch()
        found = discover(home, base)
        assert list(found) == ["legacy", "m1", "none"], list(found)
        assert found["m1"]["version"] == (1, 2) and found["m1"]["pk3"] == [home / "m1/m1-1_2.pk3"]
        assert found["m1"]["qagame"] == base / "m1" / QAGAME
        assert found["legacy"]["qagame"] is None  # module of the other arch only
        assert found["none"]["version"] is None and found["none"]["qagame"] is None
        out = Path(t) / "old"
        out.mkdir()
        (out / "modules.tsv").write_text("side\tstring\nclient\tcg_fov\nserver\tg_y\n")
        assert read_modules(out, []) == ({"cg_fov"}, {"g_y"})
    sample = "noise\n   0 D \x1b[0m/x/home/probe\n^7  -1 D ^3/x/base/probe\n   1 D /x/base/etmain\n"
    assert search_dirs(sample) == (Path("/x/home"), Path("/x/base")), search_dirs(sample)
    try:
        search_dirs("   0 D /x/home/probe\n")
        raise AssertionError("one row accepted")
    except Fail:
        pass
    print("selftest ok")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mods", nargs="*", metavar="mod")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--parse", nargs="+", metavar="dir", type=Path)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if not (a.selftest or a.list):
        engine_cvars()  # exits without the source before a run writes anything
    if a.selftest:
        selftest()
    elif a.parse:
        for d in a.parse:
            write_tsv(d, (d / "console.log").read_text(encoding="utf-8").split("\n"))
    else:
        main(a.mods, a.list)
