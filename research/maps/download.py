#!/usr/bin/env python3
"""Downloads all ET maps of wolffiles.eu (Maps category; about 3100 files, roughly 45 GB) into this folder.

Usage: python3 research/maps/download.py
         same download as research/omnibot/download.py (file names, index.tsv, rerun, lock, --jobs N),
         listing: advanced search of category 10 with game=ET
       python3 research/maps/download.py --selftest
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "omnibot"))
from download import run  # noqa: E402

LISTING = "https://wolffiles.eu/search?q=&category_id=10&game=ET&author=&min_size=&max_size=&min_rating=&date_from=&date_to="

if __name__ == "__main__":
    sys.exit(run(LISTING, Path(__file__).resolve().parent, __doc__))
