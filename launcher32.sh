#!/bin/sh
# launcher.sh with the 32-bit client (GAME_BIN_I386 of settings.conf), for i386-only mods
exec "$(dirname "$0")/launcher.sh" --i386 "$@"
