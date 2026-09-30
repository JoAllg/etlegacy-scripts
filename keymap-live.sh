#!/bin/sh
# Opens the keymap in the browser and follows the class picked in game, see tools/keymap/README.md
exec python3 "$(dirname "$0")/tools/keymap/live.py" "$@"
