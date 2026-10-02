#!/bin/sh
# Tells the game which server it is on (settings and voice chat per server) while the game runs, see tools/README.md
exec python3 "$(dirname "$0")/tools/serverconfig.py" "$@"
