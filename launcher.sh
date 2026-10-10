#!/bin/bash
# Starts the game (64-bit) with everything around it; needs a complete settings.conf (deploy.sh writes it):
# 1. tools/link_maps.py (downloaded maps for local hosting), tools/spawnpoints/spawnpoints.py (map autoexecs of new maps)
# 2. deploy.sh --unattended (links, settings.conf): asks nothing, every question takes its safe default;
#    after the generator, so it links the autoexecs of new maps on the same start
# 3. tools/servermenu.py, tools/serverconfig.py and tools/keymap/live.py in the background, stopped when the game exits; only their errors are shown
# The game's own output is not shown (etconsole.log in the mod folder has it).
# All arguments go to the game, e.g. ./launcher.sh +set fs_game nitmod +connect <ip>
# launcher32.sh starts the 32-bit client (i386-only mods) the same way.

REPO=$(cd "$(dirname "$0")" && pwd -P)

# every tool below exits without settings.conf or one of its required values (tools/helpers/settings.py names it);
# deploy.sh has to run in a terminal for that, here it could not ask
if ! PYTHONPATH="$REPO/tools" python3 -c 'import helpers.settings'; then
	echo "ERROR: settings.conf is missing or incomplete, run $REPO/deploy.sh first" >&2
	exit 1
fi

# without the list of skipped pk3s: it is the same on every start
python3 "$REPO/tools/link_maps.py" | grep -v '^skip ('
[ "${PIPESTATUS[0]}" = 0 ] || echo "⚠️  link_maps.py failed, the game starts without new map links"
python3 "$REPO/tools/spawnpoints/spawnpoints.py" || echo "⚠️  spawnpoints.py failed"

if ! out=$("$REPO/deploy.sh" --unattended 2>&1); then
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
python3 "$REPO/tools/servermenu.py" >/dev/null &
pids+=($!)
python3 "$REPO/tools/serverconfig.py" >/dev/null &
pids+=($!)
python3 "$REPO/tools/keymap/live.py" >/dev/null &
pids+=($!)
trap 'kill "${pids[@]}" 2>/dev/null' EXIT

# Memory: com_zoneMegs is only read from the command line (the zone is allocated before any cfg runs,
# src/qcommon/common.c Com_InitZoneMemory); before "$@", so an argument can override them
"$bin" +set com_hunkMegs 512 +set com_zoneMegs 192 +set com_soundMegs 192 "$@" >/dev/null 2>&1
status=$?
case $status in
	0) ;;
	126 | 127) echo "ERROR: cannot start $bin (GAME_BIN / GAME_BIN_I386 in settings.conf: delete the line and run deploy.sh to detect it again)" >&2 ;;
	*) echo "ERROR: the game exited with status $status (etconsole.log in the mod folder has its output)" >&2 ;;
esac
exit $status
