#!/bin/sh
# Keeps the pages of the in-game server menu (KP_MINUS) up to date while the game runs, see tools/README.md
exec python3 "$(dirname "$0")/tools/servermenu.py" "$@"
