#!/bin/bash
# Starts the game (64-bit) with everything around it:
# 1. tools/link_maps.py (downloaded maps for local hosting), tools/spawnpoints/spawnpoints.py (map autoexecs of new maps)
# 2. deploy.sh (links, settings.conf) without a terminal, so every question takes its safe default;
#    after the generator, so it links the autoexecs of new maps on the same start
# 3. servermenu.sh, serverconfig.sh and keymap-live.sh in the background, stopped when the game exits; only their errors are shown
# The game's own output is not shown (etconsole.log in the mod folder has it).
# All arguments go to the game, e.g. ./play.sh +set fs_game nitmod +connect <ip>
# play32.sh starts the 32-bit client (i386-only mods) the same way.

REPO=$(cd "$(dirname "$0")" && pwd -P)

# without the list of skipped pk3s: it is the same on every start
python3 "$REPO/tools/link_maps.py" | grep -v '^skip ('
[ "${PIPESTATUS[0]}" = 0 ] || echo "⚠️  link_maps.py failed, the game starts without new map links"
python3 "$REPO/tools/spawnpoints/spawnpoints.py" || echo "⚠️  spawnpoints.py failed"

if ! out=$("$REPO/deploy.sh" </dev/null 2>&1); then
	echo "$out"
	exit 1
fi
grep -E '⚠️|ERROR' <<<"$out"

# shellcheck source=/dev/null
source "$REPO/settings.conf"
bin=$GAME_BIN
if [ "$1" = --i386 ]; then
	shift
	bin=$GAME_BIN_I386
	[ -n "$bin" ] || { echo "ERROR: GAME_BIN_I386 is empty in settings.conf (no etl.i386 next to GAME_BIN)" >&2; exit 1; }
fi

# stderr stays on the terminal: a tool that dies says why
pids=()
"$REPO/servermenu.sh" >/dev/null &
pids+=($!)
"$REPO/serverconfig.sh" >/dev/null &
pids+=($!)
"$REPO/keymap-live.sh" >/dev/null &
pids+=($!)
trap 'kill "${pids[@]}" 2>/dev/null' EXIT

"$bin" "$@" >/dev/null 2>&1
