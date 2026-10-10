#!/usr/bin/env bash
# Decompiles named functions of a mod binary (symbols needed, e.g. nitmod) with Ghidra headless.
# Runs outside a sandbox: Ghidra writes its settings to ~/.config/ghidra.
# Ghidra: GHIDRA_HOME, else the install folder of `ghidra` on PATH (symlinks resolved).
#
# Usage: research/decompile/decompile.sh <binary> <func,func,...> <out.c>
#   e.g. research/decompile/decompile.sh <fs_homepath>/nitmod/qagame.mp.x86_64.so G_Say,G_Voice research/decompile/nitmod_2.3.5/decompiled/qagame_say.c
set -euo pipefail

[ $# -eq 3 ] || { sed -n '2,7p' "$0" >&2; exit 1; }
# analyzeHeadless is not on PATH, only in <install>/support/; the `ghidra` launcher sits in <install>
if [ -z "${GHIDRA_HOME:-}" ] && launcher=$(command -v ghidra || command -v ghidraRun); then
	GHIDRA_HOME=$(dirname "$(readlink -f "$launcher")")
fi
[ -x "${GHIDRA_HOME:-}/support/analyzeHeadless" ] || { echo "Ghidra not found: set GHIDRA_HOME or put ghidra on PATH" >&2; exit 1; }
binary=$(realpath "$1") funcs=$2 out=$(realpath -m "$3")
script_dir=$(realpath "$(dirname "${BASH_SOURCE[0]}")")
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
mkdir -p "$(dirname "$out")"

"$GHIDRA_HOME/support/analyzeHeadless" "$work" decompile \
	-import "$binary" \
	-postScript DecompileFunctions.java "$funcs" "$out" \
	-scriptPath "$script_dir" \
	-analysisTimeoutPerFile 600 \
	-deleteProject \
	-log "$work/ghidra.log" >"$work/stdout.log" 2>&1 || { tail -20 "$work/stdout.log" >&2; exit 1; }
echo "$out: $(grep -c '^// ==== ' "$out") functions"
