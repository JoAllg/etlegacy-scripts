#!/usr/bin/env python3
"""Symlink downloaded map pk3s from etmain/dlcache/ into etmain/ so local hosting (+map) finds them.

ET: Legacy mounts dlcache/ only while connected to a server: all of it on a pure server, only the
paks the server references on an unpure one (src/qcommon/files.c, FS_AddContainerDirectory), so a
local server started from the menu sees just pak0-2.

Skipped: pk3s without a map, pk3s containing a stock map or a map already provided by a real pk3
in etmain/ (they would override it in every mod), and pk3s with a shader file that replaces a
stock one with other content or breaks the shader parser (see shader_problem).
Several pk3s with the same map: the newest wins, originals over server re-packs.
Rerunnable: all symlinks from etmain/ into dlcache/ are replaced.
A pure server mounts every pk3 of etmain/ and dlcache/, each keeps a file open: if the pk3s after linking
come near the open files soft limit ("Invalid game folder", docs/limitations.md), it asks before linking.

Usage: tools/link_maps.py
       tools/link_maps.py --selftest
"""
import argparse
import io
import re
import resource
import sys
import zipfile
import zlib
from pathlib import Path

from helpers.common import DLCACHE, ETMAIN, LEGACY_PAKS, STOCK_PAKS, maps, rank
from helpers.settings import HOMEPATH

UNREADABLE = (zipfile.BadZipFile, NotImplementedError, RuntimeError, OSError, zlib.error)  # broken, unknown compression, encrypted


def tokens(text):
    """Tokens as the engine's COM_ParseExt reads them (signed char: bytes >= 0x80 count as whitespace)."""
    return re.findall(rb'"[^"]*"?|[\x21-\x7f]+', re.sub(rb"//[^\n]*|/\*.*?(\*/|$)", b" ", text, flags=re.S))


def shader_problem(pk3, stock_shaders):
    """Why pk3's shaders would break other shaders, None if they don't.

    The renderer concatenates all shader files into one text and scans it as "name { ... }" pairs
    (tr_shader.c, ScanAndLoadShaderFiles). One stray token (e.g. a header line without //) shifts
    the scan for all following files: stock and legacy shaders like "white" vanish, menus turn yellow.
    A shader file with a stock name replaces the stock file in every map."""
    with zipfile.ZipFile(pk3) as z:
        for name in z.namelist():
            if not name.lower().endswith(".shader"):
                continue
            text = z.read(name).split(b"\0")[0].replace(b"\r", b"")
            stock = stock_shaders.get(name.lower())
            if stock is not None and stock != text:
                return f"changes stock {name}"
            toks, i = tokens(text), 0
            while i < len(toks):
                if i + 1 == len(toks) or toks[i + 1] != b"{":
                    return f"breaks shader parsing in {name} at {toks[i][:40].decode('latin1')!r}"
                depth, i = 0, i + 1
                while i < len(toks):
                    depth += (toks[i] == b"{") - (toks[i] == b"}")
                    i += 1
                    if depth == 0:
                        break
    return None


def dlcache_link(path):
    return path.is_symlink() and path.readlink().parts[:1] == ("dlcache",)
OTHER_FILES = 100  # ponytail: guessed headroom for the game's other open files (sounds, logs, libraries); the 2026-10-10 failure had 990 pk3s at 1024


def open_files_warning(pk3s, limit):
    """Warning text if this many mounted pk3s leave too few of the open files soft limit, None if they fit."""
    if pk3s + OTHER_FILES <= limit:
        return None
    return (f"warning: a pure server would mount {pk3s} pk3s, the open files soft limit is {limit}: joining fails with "
            f"\"Invalid game folder\" (docs/limitations.md). Remove pk3s from etmain/dlcache/ or raise the limit (ulimit -n).")


def main():
    taken = set()
    for pk3 in [*STOCK_PAKS.glob("*.pk3"), *(p for p in ETMAIN.glob("*.pk3") if not dlcache_link(p))]:
        taken |= set(maps(pk3) or {})

    stock_shaders = {}
    for pk3 in [*STOCK_PAKS.glob("*.pk3"), *LEGACY_PAKS.glob("*.pk3")]:
        with zipfile.ZipFile(pk3) as z:
            stock_shaders |= {n.lower(): z.read(n).replace(b"\r", b"") for n in z.namelist()
                              if n.lower().endswith(".shader")}

    candidates = []  # (map name, bsp ZipInfo, pk3)
    for pk3 in sorted(DLCACHE.glob("*.pk3")):
        found = maps(pk3)
        if found is None:
            print(f"unreadable: {pk3.name}", file=sys.stderr)
            continue
        if found.keys() & taken:
            print(f"skip (overrides {', '.join(sorted(found.keys() & taken))}): {pk3.name}")
            continue
        try:
            problem = found and shader_problem(pk3, stock_shaders)
        except UNREADABLE as error:  # one broken pk3 must not stop the others
            print(f"unreadable: {pk3.name} ({error!r})", file=sys.stderr)
            continue
        if problem:
            print(f"skip ({problem}): {pk3.name}")
            continue
        candidates += [(name, bsp, pk3) for name, bsp in found.items()]

    # Re-packing can shift a bsp's zip date by the timezone: identical bsps (same CRC) count as equally old
    compiled = {}
    for _, bsp, _ in candidates:
        compiled[bsp.CRC] = min(compiled.get(bsp.CRC, bsp.date_time), bsp.date_time)

    best = {}  # map name -> (rank, pk3)
    for name, bsp, pk3 in candidates:
        r = rank(pk3, compiled[bsp.CRC])
        if name not in best or r > best[name][0]:
            best[name] = (r, pk3)

    # the soft limit of this process: the game started from the same session gets the same one
    mounted = [p for d in (ETMAIN, STOCK_PAKS, HOMEPATH / "legacy", LEGACY_PAKS) for p in d.glob("*.pk3") if not dlcache_link(p)]
    warning = open_files_warning(len(mounted) + len({pk3 for _, pk3 in best.values()}) + len(list(DLCACHE.glob("*.pk3"))),
                                 resource.getrlimit(resource.RLIMIT_NOFILE)[0])
    if warning:
        print(warning)
        try:
            answer = input("Link anyway? [y/N] ")
        except EOFError:  # no terminal: nothing changes
            answer = ""
        if answer.strip().lower() != "y":
            print("links left as they are")
            return

    # the old links go only now: an error above leaves them as they are
    for link in ETMAIN.glob("*.pk3"):
        if dlcache_link(link):
            link.unlink()

    winners = {pk3 for _, pk3 in best.values()}
    for pk3 in sorted(winners):
        lost = [n for n in maps(pk3) if best[n][1] != pk3]
        if lost:
            print(f"warning: {pk3.name} also brings {', '.join(lost)} (newer preferred in another pk3), pak order decides")
        target = ETMAIN / pk3.name
        if target.exists() or target.is_symlink():
            print(f"skip (exists in etmain): {pk3.name}")
            continue
        target.symlink_to(Path("dlcache") / pk3.name)
    print(f"{len(winners)} map pk3s linked for {len(best)} maps")


def selftest():
    def pk3(**files):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for name, text in files.items():
                z.writestr(f"scripts/{name}.shader", text)
        return buf

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name in ("maps/Radar.BSP", "maps/sub/other.bsp", "maps/radar.script", "radar.bsp"):
            z.writestr(name, "")
    assert list(maps(buf)) == ["radar"]

    assert tokens(b'a // c\n{ "b c" } /* d */ e') == [b"a", b"{", b'"b c"', b"}", b"e"]
    stock = {"scripts/common.shader": b"white\n{\n}\n"}
    assert shader_problem(pk3(x=b"textures/a\r\n{\n\t{\n\t\tmap a.tga\n\t}\n}\n"), stock) is None
    assert shader_problem(pk3(common=b"white\r\n{\r\n}\r\n"), stock) is None  # stock file, same content
    assert shader_problem(pk3(common=b"white\n{\nmap x\n}\n"), stock) == "changes stock scripts/common.shader"
    assert shader_problem(pk3(x=b"Made by me\ntextures/a\n{\n}\n"), stock).startswith("breaks shader parsing in scripts/x.shader at 'Made'")
    assert open_files_warning(900, 1024) is None and "990 pk3s" in open_files_warning(990, 1024)
    print("selftest ok")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true")
    selftest() if ap.parse_args().selftest else main()
