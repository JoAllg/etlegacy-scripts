#!/usr/bin/env python3
"""Downloads all ET files of the wolffiles.eu Bots category (omni-bot waypoints) into this folder.

Usage: python3 research/omnibot/download.py
         walks LISTING (advanced search of category 12 with game=ET), reads each file's name from the redirect
         of <file page>/download and fetches only the newest version of every file: names that differ only in
         _bN or _vN tokens (N: 1-2 digits, decimals like v1.10 compared by number; b and v never compared with
         each other; a trailing _waypoints or _waypoints_<omni-bot version> is ignored) are versions of one file;
         a file is saved under the server's file name (a name already taken by another file gets a <slug>__
         prefix); index.tsv (slug, file name, status) records each file as "downloaded", "ignored <newer file>"
         or "removed" (deleted by hand), so a rerun only fetches new files; a downloaded file that a newer
         version replaced is deleted once the newer one is downloaded; a second run on the same folder exits
         while the first one is running; --jobs N parallel downloads (5)
       python3 research/omnibot/download.py --selftest
research/maps/download.py runs the same download for the maps.
"""
import argparse
import concurrent.futures
import fcntl
import http.client
import re
import shutil
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from email.message import Message
from pathlib import Path

LISTING = "https://wolffiles.eu/search?q=&category_id=12&game=ET&author=&min_size=&max_size=&min_rating=&date_from=&date_to="
UA = {"User-Agent": "Mozilla/5.0 (wolffiles research download)"}
ERRORS = (OSError, http.client.HTTPException)
WAYPOINTS = re.compile(r"_waypoints(_\d+(\.\d+)*)?$")  # omni-bot suffix, with or without the omni-bot version
VERSION = re.compile(r"_([bv])(\d{1,2}(?:\.\d+)*)(?![\d.])", re.I)


def retry(action, attempts=3):
    for attempt in range(attempts):
        try:
            return action()
        except ERRORS:
            if attempt == attempts - 1:
                raise
            time.sleep(5)


def open_url(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60)


def page(url):
    def action():
        with open_url(url) as r:
            return r.read().decode("utf-8", "replace")
    return retry(action)


def save(url, out):
    def action():
        with open_url(url) as r, out.open("wb") as f:
            shutil.copyfileobj(r, f, 1 << 20)
    retry(action)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def resolve(slug):
    """Server file name of a file, read from the storage redirect of its download link (no download)."""
    opener = urllib.request.build_opener(NoRedirect)

    def action():
        try:
            with opener.open(urllib.request.Request(download_url(slug), headers=UA), timeout=60) as r:
                return r.headers.get("Content-Disposition", "")
        except urllib.error.HTTPError as e:
            if e.code not in (301, 302, 303, 307, 308):
                raise
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(e.headers.get("Location", "")).query)
            return query.get("response-content-disposition", [""])[0]
    return filename(retry(action), slug)


def download_url(slug):
    return f"https://wolffiles.eu/files/{slug}/download"


def page_url(listing, page):
    return f"{listing}{'&' if '?' in listing else '?'}page={page}"


def file_pages(listing):
    slugs, n = [], 1
    while True:
        html = page(page_url(listing, n))
        found = [s for s in dict.fromkeys(re.findall(r'href="https://wolffiles\.eu/files/([^"/?#]+)"', html))
                 if s not in slugs]
        if not found:
            return slugs
        slugs += found
        n += 1


def filename(disposition, slug):
    msg = Message()
    msg["content-disposition"] = disposition
    return Path(msg.get_filename() or slug).name


def version_key(name):
    """(group, version) of a file name; group None for names without a version token."""
    stem = WAYPOINTS.sub("", name.rsplit(".", 1)[0].lower())
    tokens = VERSION.findall(stem)
    if not tokens:
        return None, ()
    group = VERSION.sub(lambda m: f"_{m.group(1).lower()}#", stem)
    return group, tuple(tuple(int(p) for p in number.split(".")) for _, number in tokens)


def newer_versions(names):
    """{slug: newest file name} for every slug whose file name has a newer version among names ({slug: name})."""
    groups = defaultdict(list)
    for slug, name in names.items():
        group, version = version_key(name)
        if group is not None:
            groups[group].append((version, slug, name))
    newer = {}
    for members in groups.values():
        top = max(version for version, _, _ in members)
        newest = next(name for version, _, name in members if version == top)
        newer.update({slug: newest for version, slug, _ in members if version < top})
    return newer


def selftest():
    assert filename('attachment; filename="example_waypoints_1.0.zip"', "x") == "example_waypoints_1.0.zip"
    assert filename('attachment; filename="../evil.zip"', "x") == "evil.zip"
    assert filename("", "example-slug") == "example-slug"
    assert page_url("https://example.org/categories/1", 2) == "https://example.org/categories/1?page=2"
    assert page_url("https://example.org/search?q=&game=ET", 3) == "https://example.org/search?q=&game=ET&page=3"
    assert version_key("examplemap_b10_waypoints_0.9.rar") == ("examplemap_b#", ((10,),))
    assert version_key("examplemap_b9_waypoints.rar") == ("examplemap_b#", ((9,),))
    assert version_key("ExampleMap_bots_v1.10_xyz.zip") == ("examplemap_bots_v#_xyz", ((1, 10),))
    assert version_key("examplemap_waypoints_0.9.rar") == (None, ())
    assert version_key("examplemap_v123.pk3") == (None, ())
    names = {"a": "foo_b2_wp.rar", "b": "foo_b10_wp.rar", "c": "foo_b1_wp.rar", "d": "foo_v1_wp.rar",
             "e": "bar_bots_v1.9.zip", "f": "bar_bots_v1.10.zip", "g": "baz_b4.rar", "h": "baz_b4.rar",
             "i": "qux.pk3", "j": "Foo_B3_wp.zip"}
    assert newer_versions(names) == {"a": "foo_b10_wp.rar", "c": "foo_b10_wp.rar", "j": "foo_b10_wp.rar",
                                     "e": "bar_bots_v1.10.zip"}
    print("selftest ok")


def run(listing, dest, doc):
    ap = argparse.ArgumentParser(description=doc.split("\n")[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--jobs", type=int, default=5, help="parallel downloads")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return 0
    lock = (dest / ".lock").open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print(f"another download into {dest} is running", file=sys.stderr)
        return 1
    index = dest / "index.tsv"
    rows = {}  # slug: (file name, status); a later line of a slug replaces an earlier one
    if index.exists():
        for line in index.read_text().splitlines():
            slug, name, *status = line.split("\t")
            status = status[0] if status else "downloaded"
            if status == "downloaded" and not (dest / name).exists():
                status = "removed"  # deleted by hand: never fetched again
            rows[slug] = (name, status)

    guard = threading.Lock()

    def record(slug, name, status):
        with guard:
            rows[slug] = (name, status)
            with index.open("a") as f:
                f.write(f"{slug}\t{name}\t{status}\n")

    def server_name(slug):
        name, status = rows[slug]
        return name.removeprefix(f"{slug}__") if status == "downloaded" else name

    slugs = file_pages(listing)
    new = [s for s in slugs if s not in rows]
    print(f"{len(slugs)} files listed, {len(slugs) - len(new)} already in index.tsv", flush=True)
    failed = []
    pool = concurrent.futures.ThreadPoolExecutor(max(1, args.jobs))

    def try_resolve(slug):
        try:
            return slug, resolve(slug)
        except ERRORS as e:
            failed.append(slug)
            print(f"FAILED {slug}: {e!r}", file=sys.stderr, flush=True)
            return slug, None

    names = {s: server_name(s) for s in slugs if s in rows}
    names.update((s, n) for s, n in pool.map(try_resolve, new) if n is not None)
    newer = newer_versions(names)
    for slug in new:
        if slug in newer:
            record(slug, names[slug], f"ignored {newer[slug]}")
    reserved = {"download.py", index.name, lock.name}
    taken = {name for name, status in rows.values() if status == "downloaded"}

    def download(slug):
        name = names[slug]
        with guard:
            if name in taken or name in reserved:
                name = f"{slug}__{name}"
            taken.add(name)
        part = dest / f".part-{slug}"
        try:
            save(download_url(slug), part)
        except ERRORS as e:
            part.unlink(missing_ok=True)
            with guard:
                taken.discard(name)
            failed.append(slug)
            print(f"FAILED {slug}: {e!r}", file=sys.stderr, flush=True)
            return
        size = part.stat().st_size
        part.rename(dest / name)
        record(slug, name, "downloaded")
        print(f"{slug} -> {name} ({size} bytes)", flush=True)
        time.sleep(0.5)

    with pool:
        list(pool.map(download, [s for s in new if s in names and s not in newer]))
    downloaded = {server_name(s) for s in rows if rows[s][1] == "downloaded"}
    for slug in slugs:
        name, status = rows.get(slug, (None, None))
        if status == "downloaded" and slug in newer and newer[slug] in downloaded:
            (dest / name).unlink(missing_ok=True)
            record(slug, names[slug], f"ignored {newer[slug]}")
            print(f"{slug}: deleted {name}, newer {newer[slug]}", flush=True)
    index.write_text("".join(f"{s}\t{n}\t{st}\n" for s, (n, st) in rows.items()))
    ignored = sum(st.startswith("ignored") for _, st in rows.values())
    print(f"done, {ignored} older versions ignored, {len(failed)} failed" + (": " + " ".join(failed) if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run(LISTING, Path(__file__).resolve().parent, __doc__))
