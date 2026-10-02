#!/bin/bash

# =============================================================================
# ET Legacy Deploy Script
# =============================================================================
#
# Sets up this repo as the profile of every mod: one set of configs for all mods.
# Safe to rerun (after pulling, adding autoexecs, new mods or new GUID keys).
#
# WHAT THIS SCRIPT DOES:
# ----------------------
# 0. Setup: writes machine-specific values to settings.conf (read by the Python tools too).
#    Only missing values are detected and appended; existing ones are never changed,
#    so delete a line to detect it again:
#    - GAME_BIN:  the running game's executable (/proc), else etl/etl.x86_64 on PATH, else asks
#    - HOMEPATH, BASEPATH (fs_homepath, fs_basepath): the search path the game prints, taken from
#      the running game's etconsole.log (/proc), else from a quick `etlded +quit`, else asks
#    - GAME_BIN_I386 (32-bit client next to GAME_BIN, for i386-only mods), PROFILE ("default"),
#      KEYMAP_MOD (default mod of tools/keymap)
#    - VSAY_TEAM, VSAY_GLOBAL, VSAY_BUDDY (base color of vsay_team/vsay/vsay_buddy text), VSAY_PUNCT (punctuation),
#      VSAY_HIGHLIGHT, VSAY_URGENT (key words): colors of the vsay texts (tools/voicemenu.py, vsay-highlight skill)
#    - MENU_HEAD, MENU_KEY, MENU_TEXT, MENU_NAV (TAB line), MENU_GLOBAL (global chat), MENU_AXIS, MENU_ALLIES (spawnpoint owner),
#      MENU_PLAYING, MENU_SPEC, MENU_BOTS (server menu player numbers): colors of the echo menus
#      (voice chat, spawn selector, server menu; tools/vsaycolors.py apply, voicemenu.py, spawnpoints.py, servermenu.py)
# 1. Asks to set defaultprofile.dat to PROFILE, the profile the game writes etconfig.cfg into
# 2. Creates user.cfg from user.example.cfg (personal settings, omnibot_path from HOMEPATH) if missing,
#    else appends the set/seta values of the template that user.cfg lacks (reported)
#    Rewrites the HUD VALUES block of user.cfg from the legacy HUD file (tools/helpers/hudvalues.py): the aliases
#    that put the HUD back after a script changed it in game
# 3. Deletes broken symlinks at the top level of each mod directory
# 4. Symlinks HOMEPATH/profiles -> this repo (the repo can live anywhere); asks before replacing a
#    folder or a symlink to another path (a folder is renamed to profiles.bak_<date>, not deleted).
#    Creates mod directories and symlinks into each (a real profiles folder the game created there
#    is renamed to profiles.bak_<date> after asking):
#    profiles -> this repo (engine profile folder: etconfig.cfg, defaultprofile.dat, user.cfg)
#    profile  -> this repo's PROFILE folder (all cfg exec paths: exec profile/...)
# 5. Backs up GUID key files to guid_backup/<key>_<date> and symlinks them into the mod directories
# 6. Symlinks the map/team autoexecs into HOMEPATH/etmain and the location overrides to HOMEPATH/etmain/maps
#    (etmain is in every mod's search path); removes links to the same files/folder from the mod directories
# 7. Symlinks the mod-specific autoexec* and mod_* files
# 8. Offers to build the nitmod stock shield pk3 from the stock etmain pk3s (tools/stock_shield/README.md)
# 9. Offers desktop files (application menu entries with the game's icon) that start launcher.sh and,
#    if GAME_BIN_I386 is set, launcher32.sh: etlegacy-launcher.<arch>.desktop in ~/.local/share/applications
#    (XDG_DATA_HOME). Asked only while one is missing; existing ones are rewritten when the repo path changed.
#    The 64-bit entry opens et:// links.
#
# ⚠️ IMPORTANT BEHAVIOR:
# ----------------------
# - Broken symlinks at the top level of each mod directory are deleted first,
#   including ones this script did not create
# - Existing symlinks are replaced to ensure they point to the correct locations
# - profiles: a real directory is renamed to profiles.bak_<date> after asking (kept if declined)
# - profile and maps: real files/directories are PRESERVED with orange
#   warning messages; remove them manually if you want to replace them
# - GUID keys: a real key file in a mod directory is backed up, then replaced by a symlink.
#   If it differs from guid_backup/<key>, you are asked which one to keep (default: guid_backup)
# - autoexec and mod_* files: real files with the same name are OVERWRITTEN

# CONFIGURATION VARIABLES (MODIFY THESE FOR YOUR SETUP):
# ======================================================

# MODS: Space-separated list of all mods you want to set up
# - These are the mod directories that will be created in HOMEPATH
# - Common mods: etmain, legacy, etpub, nitmod, silent, jaymod, etjump
MODS="etmain legacy etpub nitmod silent jaymod etjump"

# GUID: Array of "mod keyfile" pairs for authentication
# - Format: "modname keyfilename"
# - These key files are symlinked from guid_backup/ into each mod directory
# - Common combinations:
#   - "etmain etkey" (standard ET key)
#   - "nitmod nkey.dat" (NitMod authentication)
#   - "etjump etguid.dat" (ETJump authentication)
GUID=("etmain etkey" "nitmod nkey.dat" "etjump etguid.dat")

# =============================================================================
# END OF CONFIGURATION - DO NOT MODIFY BELOW THIS LINE
# =============================================================================

# -P: the real path, so the links do not go through HOMEPATH/profiles
REPO=$(cd "$(dirname "$0")" && pwd -P)
SETTINGS="$REPO/settings.conf"
GUID_DIR="$REPO/guid_backup"
PROFILE_LINK="profile" # exec paths of all cfgs start with it

# Color codes for better visibility
RED='\033[0;31m'
ORANGE='\033[38;5;208m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ask <question> <default y|n>: true on yes; without a terminal the default is taken
ask() {
	local reply=""
	[ -t 0 ] && read -r -p "$1 " reply
	case "${reply:-$2}" in [yY]*) return 0 ;; *) return 1 ;; esac
}

# -----------------------------------------------------------------------------
# 0. Setup: settings.conf
# -----------------------------------------------------------------------------

# Appends KEY="value"; existing values are never changed
set_value() {
	# the file is sourced, so these characters would break it or run code
	if [[ $2 == *[\"\$\`\\]* ]]; then
		echo -e "${RED} ERROR: $1 must not contain \" \$ \` or \\: $2 ${NC}" >&2
		exit 1
	fi
	# a hand-edited file may lack the final newline
	[ -s "$SETTINGS" ] && [ -n "$(tail -c 1 "$SETTINGS")" ] && echo >>"$SETTINGS"
	echo "$1=\"$2\"" >>"$SETTINGS"
	printf -v "$1" '%s' "$2"
	echo -e "  + $1=\"$2\""
}

# PID of a running ET: Legacy client (first match); the 32-bit client only runs i386-only mods
game_pid() {
	local exe
	for exe in /proc/[0-9]*/exe; do
		case "$(readlink "$exe" 2>/dev/null)" in */etl.i386) ;; */etl | */etl.*)
			exe=${exe%/exe}
			echo "${exe#/proc/}"
			return
			;;
		esac
	done
}

# read_dir <prompt> <default> <required subfolder>: asks until the folder exists; ~ is expanded
read_dir() {
	local dir
	while true; do
		read -r -p "$1 [$2]: " dir
		dir=${dir:-$2}
		dir=${dir/#\~/$HOME}
		dir=${dir%/}
		[ -d "$dir/$3" ] && echo "$dir" && return
		echo -e "  ${ORANGE}⚠️  Not found: $dir/$3${NC}" >&2
	done
}

# Directories of the "Current search path" the game prints (D lines), from stdin:
# the first is fs_homepath/<mod>, the second fs_basepath/<mod> (the same one if both paths are equal)
search_dirs() {
	sed -E 's/\x1b\[[0-9;]*m//g; s/\^.//g' | sed -nE 's/^ *[0-9-]* +D +(.*)$/\1/p' | head -n 2
}

setup() {
	local missing="" key
	# shellcheck source=/dev/null
	[ -f "$SETTINGS" ] && source "$SETTINGS"
	for key in GAME_BIN HOMEPATH BASEPATH GAME_BIN_I386 PROFILE KEYMAP_MOD VSAY_TEAM VSAY_GLOBAL VSAY_BUDDY VSAY_PUNCT VSAY_HIGHLIGHT VSAY_URGENT MENU_HEAD MENU_KEY MENU_TEXT MENU_NAV MENU_GLOBAL MENU_AXIS MENU_ALLIES MENU_PLAYING MENU_SPEC MENU_BOTS; do
		grep -q "^$key=" "$SETTINGS" 2>/dev/null || missing+=" $key"
	done
	[ -z "$missing" ] && return
	needs() { [[ "$missing " == *" $1 "* ]]; }
	echo -e "\n${CYAN}🔍 Detecting settings:${missing}${NC}"
	[ -f "$SETTINGS" ] || echo "# Machine-specific values and personal preferences, written by deploy.sh (existing values are kept, delete a line to detect it again)" >"$SETTINGS"

	local pid dirs log fd
	pid=$(game_pid)

	if needs GAME_BIN; then
		local bin=""
		if [ -n "$pid" ]; then
			bin=$(readlink "/proc/$pid/exe")
		else
			bin=$(command -v etl etl.x86_64 etl.aarch64 | head -n 1)
		fi
		while [ -z "$bin" ]; do
			echo -e "  ${ORANGE}⚠️  ET: Legacy executable not found${NC}"
			[ -t 0 ] || exit 1
			read -r -p "  Name or path of the game executable (empty = abort): " bin
			[ -z "$bin" ] && exit 1
			bin=$(command -v "${bin/#\~/$HOME}")
		done
		set_value GAME_BIN "$(readlink -f "$bin")"
	fi

	if needs HOMEPATH || needs BASEPATH; then
		if [ -n "$pid" ]; then
			for fd in /proc/"$pid"/fd/*; do
				log=$(readlink "$fd")
				[[ $log == */etconsole.log ]] && dirs=$(search_dirs <"$log") && break
			done
		fi
		# The dedicated server prints the same search path without opening a window.
		# - stdin not a terminal, else its tty console adds a prompt and \r to every line
		# - an empty mod folder: no autoexec.cfg runs, and the etconfig it writes on quit lands there
		#   instead of the profile (common.c Com_WriteConfiguration), so deleting the folder leaves nothing
		local name=${GAME_BIN##*/} probe="deploy_probe"
		local ded="${GAME_BIN%/*}/etlded${name#etl}"
		if [ -z "$dirs" ] && [ -x "$ded" ]; then
			dirs=$(timeout 30 "$ded" +set fs_game "$probe" +quit </dev/null 2>&1 | search_dirs)
		fi
		local home base
		home=$(dirname "$(sed -n 1p <<<"$dirs")")
		base=$(dirname "$(sed -n 2p <<<"$dirs")")
		[[ $dirs == */$probe* && -d "$home/$probe" ]] && rm -rf "${home:?}/$probe"
		if [ -z "$dirs" ] || [ ! -d "$home" ] || [ ! -d "$base/etmain" ]; then
			echo -e "  ${ORANGE}⚠️  Could not read the search path from the game${NC}"
			[ -t 0 ] || exit 1
			home=$(read_dir "  fs_homepath" "$HOME/.etlegacy" "")
			base=$(read_dir "  fs_basepath (folder with etmain/pak0.pk3)" "/usr/lib/etlegacy" "etmain")
		fi
		needs HOMEPATH && set_value HOMEPATH "$home"
		needs BASEPATH && set_value BASEPATH "$base"
	fi

	if needs GAME_BIN_I386; then
		local i386="${GAME_BIN%/*}/etl.i386"
		[ -x "$i386" ] || i386=""
		set_value GAME_BIN_I386 "$i386"
	fi
	needs PROFILE && set_value PROFILE "default"
	needs KEYMAP_MOD && set_value KEYMAP_MOD "nitmod"
	# the colors of scripts/vsays/chat.cfg
	needs VSAY_TEAM && set_value VSAY_TEAM "^9"
	needs VSAY_GLOBAL && set_value VSAY_GLOBAL "^l"
	needs VSAY_BUDDY && set_value VSAY_BUDDY "^f"
	needs VSAY_PUNCT && set_value VSAY_PUNCT "^3"
	needs VSAY_HIGHLIGHT && set_value VSAY_HIGHLIGHT "^x"
	needs VSAY_URGENT && set_value VSAY_URGENT "^1"
	# the colors of the echo menus; readable on bright and dark maps with the popup shadow (huds/hud_v<version>.dat textStyle 3)
	needs MENU_HEAD && set_value MENU_HEAD "^8"
	needs MENU_KEY && set_value MENU_KEY "^3"
	needs MENU_TEXT && set_value MENU_TEXT "^7"
	needs MENU_NAV && set_value MENU_NAV "^2"
	needs MENU_GLOBAL && set_value MENU_GLOBAL "^6"
	needs MENU_AXIS && set_value MENU_AXIS "^i"
	needs MENU_ALLIES && set_value MENU_ALLIES "^d"
	needs MENU_PLAYING && set_value MENU_PLAYING "^2"
	needs MENU_SPEC && set_value MENU_SPEC "^5"
	needs MENU_BOTS && set_value MENU_BOTS "^9"
}

setup
# shellcheck source=/dev/null
source "$SETTINGS"

echo -e "\n${CYAN}=== HOMEPATH: $HOMEPATH | profile: $PROFILE ===${NC}"
for key in GAME_BIN HOMEPATH BASEPATH PROFILE KEYMAP_MOD; do
	if [ -z "${!key}" ]; then
		echo -e "${RED} ERROR: $key is empty in settings.conf (delete the line to detect it again) ${NC}" >&2
		exit 1
	fi
done
if [ ! -d "$BASEPATH/etmain" ]; then
	echo -e "${RED} ERROR: BASEPATH has no etmain folder: $BASEPATH (settings.conf) ${NC}" >&2
	exit 1
fi
if [ ! -d "$REPO/$PROFILE" ]; then
	echo -e "${RED} ERROR: Profile folder not found: $REPO/$PROFILE ${NC}" >&2
	exit 1
fi
if [ ! -d "$HOMEPATH" ]; then
	echo -e "${RED} ERROR: HOMEPATH not found: $HOMEPATH (settings.conf) ${NC}" >&2
	exit 1
fi

# -----------------------------------------------------------------------------
# 1. defaultprofile.dat: the profile the game loads (and writes etconfig.cfg into)
# -----------------------------------------------------------------------------
PROFILE_FILE="$REPO/defaultprofile.dat"
ACTIVE=$(tr -d '[:space:]"' <"$PROFILE_FILE" 2>/dev/null)
if [ "$ACTIVE" != "$PROFILE" ]; then
	echo -e "\n${ORANGE}⚠️  defaultprofile.dat selects \"$ACTIVE\", the cfgs are linked from \"$PROFILE\"${NC}"
	if ask "  Set \"$PROFILE\" as the game's default profile? [Y/n]" y; then
		printf '"%s"' "$PROFILE" >"$PROFILE_FILE"
		echo "    - defaultprofile.dat set to \"$PROFILE\""
	else
		echo -e "    ${ORANGE}Kept: the game writes etconfig.cfg into profiles/$ACTIVE, not $PROFILE${NC}"
	fi
fi

# -----------------------------------------------------------------------------
# 2. Personal settings: user.cfg (gitignored), created from the template
# -----------------------------------------------------------------------------
USER_CFG="$REPO/user.cfg"

# example_cfg: the template with omnibot_path set to HOMEPATH
# - omnibot_path must be absolute: a relative one is resolved from the directory ET was started in
# - the inner sed escapes & | \ of the path for the outer replacement
example_cfg() {
	# shellcheck disable=SC2001
	sed "s|/home/<user>/.etlegacy|$(sed 's/[&|\\]/\\&/g' <<<"$HOMEPATH")|" "$REPO/user.example.cfg"
}

if [ ! -f "$REPO/user.example.cfg" ]; then
	echo -e "${ORANGE}⚠️  user.example.cfg not found, user.cfg not checked${NC}"
elif [ ! -e "$USER_CFG" ]; then
	example_cfg >"$USER_CFG"
	echo -e "${RED}"
	echo -e "  ╔══════════════════════════════════════════════════════════════╗"
	echo -e "  ║  ⚠️  Created user.cfg from the example                        ║"
	echo -e "  ║      SET YOUR PLAYER NAME IN IT BEFORE PLAYING                ║"
	echo -e "  ╚══════════════════════════════════════════════════════════════╝"
	echo -e "  $USER_CFG${NC}"
else
	# Settings the template gained since user.cfg was created: without them the general defaults apply.
	# A value counts as present even commented out (// set name ...), so it can be dropped on purpose.
	# Any letter case and a bare "<cvar> <value>" line count too: the engine reads both as the same cvar,
	# and a default appended behind them would override the personal value.
	added=()
	while IFS= read -r line; do
		[[ $line =~ ^[[:space:]]*seta?[[:space:]]+([A-Za-z0-9_]+) ]] || continue
		grep -qiE "^[[:space:]]*((//[[:space:]]*)?seta?[[:space:]]+)?${BASH_REMATCH[1]}([[:space:]]|$)" "$USER_CFG" && continue
		added+=("$line")
	done < <(example_cfg)
	if [ ${#added[@]} -gt 0 ]; then
		block=$(printf '%s\n' "// From user.example.cfg (added by deploy.sh): defaults, adjust or comment out" "${added[@]}")
		# before the load marker, so it stays the last line
		awk -v block="$block" '/USER SETTINGS LOADED/ && !done { print block; print ""; done = 1 } { print } END { if (!done) print block }' \
			"$USER_CFG" >"$USER_CFG.tmp" && mv "$USER_CFG.tmp" "$USER_CFG"
		echo -e "\n${ORANGE}⚠️  Added ${#added[@]} missing setting(s) from user.example.cfg to user.cfg, adjust them:${NC}"
		printf '    + %s\n' "${added[@]}"
	fi
fi

# HUD values: the HUD is changed in the game's HUD editor, so the aliases that reset it are read from its file on every run
if [ -e "$USER_CFG" ]; then
	if command -v python3 >/dev/null; then
		python3 "$REPO/tools/helpers/hudvalues.py" | sed 's/^/  /'
	else
		echo -e "  ${ORANGE}⚠️  python3 not found, HUD values in user.cfg not updated${NC}"
	fi
fi

echo -e "${CYAN}🚀 Setting up ET Legacy mod symlinks...${NC}"

# 3. Delete stale symlinks (target no longer exists), e.g. from renamed/removed autoexecs
# Top level only: all links this script creates live there
echo -e "\n${CYAN}🧹 Deleting stale symlinks...${NC}"
for mod in etmain $MODS; do  # etmain holds the autoexec links even if it is no mod of the list
	[ -d "$HOMEPATH/$mod" ] || continue
	find "$HOMEPATH/$mod" -maxdepth 1 -xtype l -printf "    - Deleted stale symlink: %p -> %l\n" -delete
done

# link_dir <target> <link>: (re)creates a directory symlink, never replaces a real file/directory
link_dir() {
	if [ -L "$2" ]; then
		rm "$2"
	elif [ -e "$2" ]; then
		echo -e "    ${ORANGE}⚠️  SKIPPED: Found existing non-symlink at $2${NC}"
		echo -e "    ${ORANGE}    Not overwriting existing file/directory. Remove manually if you want to replace it.${NC}"
		return
	fi
	# -n: if rm failed, never follow the old link and create the link inside the target
	if ln -sfn "$1" "$2"; then
		echo "    - Symlinked $2 -> $1"
	else
		echo -e "    ${RED}⚠️  WARNING:${NC} Failed to symlink $2"
	fi
}

# move_aside <path>: asks to rename a real folder at <path> to <path>.bak_<date>; true if <path> is free now
move_aside() {
	[ -e "$1" ] && [ ! -L "$1" ] || return 0
	local backup="$1.bak_$(date +%F_%H%M%S)"
	echo -e "    ${ORANGE}⚠️  $1 is a real folder, not a link to this repo${NC}"
	ask "    Move it to ${backup##*/} and link $REPO there? [y/N]" n && mv "$1" "$backup" && echo "    - Moved $1 -> $backup"
}

# 4. Create mod folders and symlink the profile folders into each
echo -e "\n${CYAN}📁 Creating mod folders and symlinking profiles...${NC}"

# HOMEPATH/profiles: the usual place of the repo, kept as a link when the repo lives elsewhere
HOME_LINK="$HOMEPATH/profiles"
if [ "$(readlink -f "$HOME_LINK")" != "$REPO" ]; then
	if [ -L "$HOME_LINK" ]; then
		echo -e "  ${ORANGE}⚠️  $HOME_LINK links to $(readlink "$HOME_LINK"), not this repo${NC}"
		ask "  Replace it with a link to $REPO? [y/N]" n && link_dir "$REPO" "$HOME_LINK"
	else
		move_aside "$HOME_LINK" && link_dir "$REPO" "$HOME_LINK"
	fi
fi

for mod in $MODS; do
	mod_dir="$HOMEPATH/$mod"
	echo "  Processing mod: $mod"
	mkdir -p "$mod_dir"
	move_aside "$mod_dir/profiles"  # a profiles folder the game created there would hide user.cfg
	link_dir "$REPO" "$mod_dir/profiles"
	link_dir "$REPO/$PROFILE" "$mod_dir/$PROFILE_LINK"
done

# 5. Back up GUID key files, then symlink them into the mod folders

# backup_key <file> <key>: copies to guid_backup/<key>_<mtime> unless an identical backup exists
backup_key() {
	local b dest
	for b in "$GUID_DIR/$2"_*; do
		[ -f "$b" ] && cmp -s "$1" "$b" && return
	done
	b="$GUID_DIR/$2_$(date -r "$1" +%F_%H%M%S)"
	dest=$b
	local n=1
	# never overwrite: another key can have the same mtime
	while [ -e "$dest" ]; do dest="${b}_$((++n))"; done
	cp -p "$1" "$dest" && echo "    - Backed up $1 -> guid_backup/${dest##*/}"
}

echo -e "\n${CYAN}🔑 Backing up and symlinking GUID key files...${NC}"
mkdir -p "$GUID_DIR"
for guid_entry in "${GUID[@]}"; do
	read -r mod key <<<"$guid_entry"
	mod_file="$HOMEPATH/$mod/$key"
	current="$GUID_DIR/$key"
	echo "  Processing key file for mod: $mod"

	[ -f "$current" ] && backup_key "$current" "$key"

	# A real file was written by the game: a new key, or the first run on this machine.
	# It is only replaced by the symlink once a copy of it is safe in guid_backup/.
	if [ -f "$mod_file" ] && [ ! -L "$mod_file" ]; then
		if ! backup_key "$mod_file" "$key"; then
			echo -e "    ${RED}⚠️  WARNING:${NC} Backup of $mod_file failed, left it in place"
			continue
		fi
		if [ ! -f "$current" ]; then
			if ! cp -p "$mod_file" "$current"; then
				echo -e "    ${RED}⚠️  WARNING:${NC} Copy to guid_backup/$key failed, left $mod_file in place"
				continue
			fi
		elif ! cmp -s "$mod_file" "$current"; then
			echo -e "    ${ORANGE}⚠️  $mod_file ($(date -r "$mod_file" +%F)) differs from guid_backup/$key ($(date -r "$current" +%F)): the key was changed${NC}"
			if ask "    Use the new key from $mod/ from now on? [y/N]" n; then
				# the old key has a backup already (above), and the new one too
				cp -p "$mod_file" "$current" && echo "    - guid_backup/$key replaced by the new key"
			else
				echo "    - Keeping guid_backup/$key, the new key stays in the backups"
			fi
		fi
		rm "$mod_file"
	fi

	if [ -f "$current" ]; then
		if ln -sf "$current" "$mod_file"; then
			echo "    - Symlinked $key to $mod_file"
		else
			echo -e "    ${RED}⚠️  WARNING:${NC} Failed to symlink $key to $mod_file"
		fi
	else
		echo -e "    ${RED}⚠️  WARNING:${NC} Key file guid_backup/$key not found for mod $mod"
	fi
done

# 6. Symlink the map/team autoexecs and the location overrides into etmain:
# it is in the search path of every mod, so one set of links serves all of them
mkdir -p "$HOMEPATH/etmain"
echo -e "\n${CYAN}⚙️  Symlinking autoexec files...${NC}"
AUTOEXEC_DIR="$REPO/$PROFILE/autoexecs"
if [ -d "$AUTOEXEC_DIR" ]; then
	# single files, not the folder: the game execs them by bare name
	if ln -sf "$AUTOEXEC_DIR"/autoexec_*.cfg "$HOMEPATH/etmain/"; then
		echo "    - Symlinked all autoexec files to $HOMEPATH/etmain/"
	else
		echo -e "    ${RED}⚠️  WARNING:${NC} Failed to symlink all autoexec files to $HOMEPATH/etmain/"
	fi
	# a link to the same file in a mod folder would outrank the one in etmain
	for mod in $MODS; do
		[ "$mod" != etmain ] && [ -d "$HOMEPATH/$mod" ] || continue
		removed=$(find "$HOMEPATH/$mod" -maxdepth 1 -type l -lname "$AUTOEXEC_DIR/*" -print -delete | wc -l)
		[ "$removed" -gt 0 ] && echo "    - Removed $removed autoexec links from $HOMEPATH/$mod (etmain covers them)"
	done
else
	echo -e "    ${RED}⚠️  WARNING:${NC} Autoexecs directory not found"
fi

echo -e "\n${CYAN}🗺️  Symlinking location overrides...${NC}"
if [ -d "$REPO/$PROFILE/maps" ]; then
	link_dir "$REPO/$PROFILE/maps" "$HOMEPATH/etmain/maps"
	# a link to the same folder in a mod folder would outrank the mod's own pk3s
	for mod in $MODS; do
		mod_maps="$HOMEPATH/$mod/maps"
		if [ "$mod" != etmain ] && [ -L "$mod_maps" ] && [ "$(readlink -f "$mod_maps")" = "$(readlink -f "$REPO/$PROFILE/maps")" ]; then
			rm "$mod_maps"
			echo "    - Removed $mod_maps (etmain/maps covers it)"
		fi
	done
else
	echo -e "    ${RED}⚠️  WARNING:${NC} Maps directory not found"
fi

# 7. Symlink mod-specific autoexec files
# Only autoexec* and mod_* files: the game looks them up in the mod folder (search path), all other cfgs are exec'd via profile/ paths
echo -e "\n${CYAN}🔧 Symlinking mod-specific autoexec files...${NC}"
for mod_config_dir in "$REPO/$PROFILE/mods"/*/; do
	mod_config_dir=${mod_config_dir%/}
	mod_name=$(basename "$mod_config_dir")
	target_mod_dir="$HOMEPATH/$mod_name"

	# example/ is the template for new mods, not a real mod folder
	[ "$mod_name" = "example" ] && continue

	echo "  Processing mod-specific autoexec files for: $mod_name"

	if [ -d "$target_mod_dir" ]; then
		# Skip unmatched globs: not every mod folder has both kinds of file
		mod_files=()
		for mod_file in "$mod_config_dir"/autoexec* "$mod_config_dir"/mod_*; do
			[ -e "$mod_file" ] && mod_files+=("$mod_file")
		done
		if [ ${#mod_files[@]} -gt 0 ]; then
			if ln -sf "${mod_files[@]}" "$target_mod_dir/"; then
				echo "    - Symlinked autoexec files to $target_mod_dir/"
			else
				echo -e "    ${RED}⚠️  WARNING:${NC} Failed to symlink autoexec files to $target_mod_dir/"
			fi
		else
			echo -e "    ${ORANGE}⚠️  No autoexec files found in $mod_config_dir${NC}"
		fi
	else
		echo -e "    ${RED}⚠️  WARNING:${NC} Target mod directory $target_mod_dir not found"
	fi
done

# 8. nitmod stock shield: built from the local game, the files are game assets (not in the repo)
SHIELD="$HOMEPATH/nitmod/$(printf '~%.0s' {1..60})stock_shield.pk3"
if [[ " $MODS " == *" nitmod "* ]] && [ ! -e "$SHIELD" ]; then
	echo -e "\n${CYAN}🛡️  nitmod stock shield (keeps menus and sounds stock when servers push their packs, tools/stock_shield/README.md)${NC}"
	if ! command -v python3 >/dev/null; then
		echo -e "    ${ORANGE}⚠️  python3 not found, skipped${NC}"
	elif ask "  Build and install the stock shield pk3? [y/N]" n; then
		python3 "$REPO/tools/stock_shield/stock_shield.py" | sed 's/^/    - /'
	fi
fi

# 9. Desktop files: menu entries that start the game through the launcher scripts
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"

# desktop_entry <bits> <launcher> [url]: the entry text; with a third argument it takes et:// links
desktop_entry() {
	cat <<EOF
[Desktop Entry]
Type=Application
Name=ET: Legacy Launcher ($1-bit)
GenericName=World War II first-person shooter
Comment=ET: Legacy with the profile tools (launcher.sh)
Icon=etl
Exec="$REPO/$2"${3:+ +connect %u}
Terminal=false
${3:+MimeType=x-scheme-handler/et;
}Categories=Game;ActionGame;
StartupNotify=false
Keywords=team-based;multiplayer;tactical;WWII;enemy;territory;etl;etlegacy;
PrefersNonDefaultGPU=true
EOF
}

# only the 64-bit entry takes et:// links, so a link has one target
DESKTOPS=("x86_64 64 launcher.sh url")
[ -n "$GAME_BIN_I386" ] && DESKTOPS+=("i386 32 launcher32.sh")
desktop_missing=""
for entry in "${DESKTOPS[@]}"; do
	[ -e "$APPS/etlegacy-launcher.${entry%% *}.desktop" ] || desktop_missing=1
done
echo -e "\n${CYAN}🖥️  Desktop files (start the game through launcher.sh)...${NC}"
if [[ $REPO == *[\"\$\`\\%]* ]]; then
	# they would need escaping in the quoted Exec path
	echo -e "    ${ORANGE}⚠️  Skipped: the repo path contains \" \$ \` \\ or %${NC}"
elif [ -z "$desktop_missing" ] || ask "  Create desktop files in $APPS? [y/N]" n; then
	# existing ones are rewritten without asking: the repo may have moved
	mkdir -p "$APPS"
	for entry in "${DESKTOPS[@]}"; do
		read -r arch bits launcher url <<<"$entry"
		file="$APPS/etlegacy-launcher.$arch.desktop"
		text=$(desktop_entry "$bits" "$launcher" "$url")
		[ "$text" = "$(cat "$file" 2>/dev/null)" ] && continue
		if echo "$text" >"$file"; then
			echo "    - Wrote $file"
		else
			echo -e "    ${RED}⚠️  WARNING:${NC} Failed to write $file"
		fi
	done
fi

echo -e "\n${GREEN}✅ Deploy completed!${NC}"
