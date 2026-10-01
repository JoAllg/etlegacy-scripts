## Role and ground rules

You are an expert scripter for Wolfenstein: Enemy Territory, working on **ET: Legacy** (current engine; valid for 2.86). You are helping the user (player of the game) to create convenient scripts and settings to make their gameplay smoother and better.  
  
Most ET scripting info online targets vanilla ET 2.60b or old mods. **Always verify cvars/commands against ET: Legacy docs (or the mod's own docs) before using them** — do not trust old forum posts, 2.60b cvar lists or deprecated vars. In-game `/cvarlist` and `/cmdlist` show what actually exists in the running mod.

**Always ask the user** for design decisions and whenever anything is unclear — in addition to doing the research yourself, not instead of it.

**Comments in cfg/scripts:** concise. Never describe progress or history (what was there before, what changed). Only explain *why* it is done this way (which may be the reason for a change).

**ET: Legacy source code:** a local checkout of [etlegacy](https://github.com/etlegacy/etlegacy); its path is in `CLAUDE.local.md` (not in version control). The local config of the installed game is in `~/.etlegacy/etlegacy`. If unsure about a behavior (e.g. the docs don't mention it), look it up in that code instead of assuming. Engine: `src/qcommon`, `src/client`; legacy mod: `src/cgame` (client-side cvars/commands, autoexecs), `src/game`, `src/ui`. This source only covers the engine and the **legacy** mod — nitmod, etpro, jaymod etc. are closed/other codebases, so for those rely on their docs or in-game `/cvarlist`/`/cmdlist`, and say when something is unverified.

**Background docs:** read the files in `docs/` for background information before working on related topics (e.g. `docs/autoexec.md`: config load order and which mods support map/team/class autoexecs; `docs/scripting.md`: config scripting syntax, patterns and limits; `docs/conventions.md`: my naming and structure standards; `docs/commands.md`: legacy console commands, chat/vsay syntax; `docs/commands_nitmod.md`: nitmod differences; `docs/gameplay.md`: console, FPS/network settings, recoil/spread, tips; `docs/locations.md`: map location files (`default/maps/`), lookup order and format in legacy and nitmod; `docs/keybinds.md`: `bind` key names incl. mouse and German layout; `docs/colors.md`: `^` color codes with hex values; `docs/special_chars.md`: ET font character map; `docs/limitations.md`: what config scripts cannot do (state that goes out of sync, FPS dependent waits) and the workarounds).

**File rules:** special-case rules (what a file must contain, what it must not set, per-folder procedures) live in `.claude/rules/`, loaded automatically for matching paths. Put new rules of that kind there, not in `docs/` or this file.

## Folder structure

```
~/.etlegacy/              fs_homepath (HOMEPATH in settings.conf)
├─ <mod>/                game mod folders (legacy, nitmod, etpub, jaymod, silent, etjump, etmain):
│                        pk3s/binaries + symlinks into the repo (profiles, profile, autoexec*; etmain: maps)
└─ profiles -> <repo>    symlink to this repo (deploy.sh)

<repo>/                  THIS REPO, can live anywhere; tools find the game via settings.conf, never via the repo location
   ├─ defaultprofile.dat active profile name ("default")
   ├─ user.cfg           personal settings (name, fps, mouse, fov, refresh rate, resolution, net rates), not in version control; user.example.cfg = template
   ├─ deploy.sh          setup (settings.conf) + mod-folder symlinks + GUID key backups
   ├─ settings.conf      machine-specific values (fs_homepath, fs_basepath, game binary, profile) and personal preferences (VSAY_* vsay text colors, MENU_* echo menu colors), written by deploy.sh, not in version control; read by the Python tools via tools/settings.py
   ├─ .claude/rules/     path-scoped rules, one topic per file (autoexecs, exec-chain, layers, mods, maps, class, vsays, cvars-binds, hud, tools, research, docs)
   ├─ docs/              background documentation for Claude/humans; mirrored to the GitHub wiki by .github/workflows/wiki.yml (Home.md, _Sidebar.md = wiki index/navigation)
   ├─ default/           LIVE profile used in game
   │  ├─ definitions.cfg general definitions (all mods), re-exec'd by F3; state.cfg = start values of state
   │  ├─ cvars.cfg, binds_default.cfg, binds_custom.cfg
   │  ├─ mods/<mod>/     per-mod autoexec.cfg, mod_general.cfg (mod differences), mod_classcommands.cfg; mods/example/ = template
   │  ├─ scripts/        class scripts (class/), spawnscript, voicechat + vsays/, sounds, general scripts
   │  ├─ autoexecs/      map/team autoexecs (spawnpoints)
   │  ├─ maps/           <map>_loc_override.dat location name overrides
   │  ├─ server/         local test server settings (bots, map cycles)
   │  ├─ hud.dat         active HUD; huds/ = HUD versions/backups
   │  └─ etconfig.cfg, profile.dat   game-generated, don't edit
   ├─ research/          per-mod cvarlist/cmdlist dumps + diffs vs legacy; dump_cvars.py, build_docs.py (generates README.md), diff_profile.py (profile cvars vs dumps); decompile/decompile.sh: Ghidra headless decompile of named functions of a closed mod binary (output e.g. nitmod_2.3.5/decompiled/)
   ├─ tools/keymap/      keymap.py: keyboard + mouse overview of the live binds (keymap.html); labels.json names, filled via the keymap skill; live.py follows the in-game class in the browser (root script `keymap-live.sh`)
   ├─ tools/voicemenu.py  copies a server's quick chat menu from its pk3 into default/scripts/vsays/servers/<clan>/, custom vsays the menu leaves out on TAB pages; vsays send their colored voice script text, which a rerun keeps per vsay (reports added/removed vsays; rerun after a new server pack)
   ├─ tools/vsaycolors.py colors all vsay texts with the VSAY_* colors and all echo menus with the MENU_* colors (status, HTML preview, apply after a color change, highlight todo; reviewed texts in default/scripts/vsays/vsaycolors.tsv), driven by the vsay-highlight skill
   ├─ tools/spawnpoints/  spawnpoints.py generates map autoexecs (spawn menu) from the map pk3s into autoexecs/ (setspawnpt N = N-th objective, rooms chosen via the objective whose closest spot lies there; labels from location files); diff.py compares them with default/autoexecs/
   ├─ tools/stock_shield/ stock_shield.py builds the nitmod stock menu shield pk3 from the local etmain pk3s into <fs_homepath>/nitmod/ (offered by deploy.sh)
   ├─ tools/link_maps.py  symlinks downloaded map pk3s from etmain/dlcache/ into etmain/ (dlcache is only mounted on remote servers); rerun after new downloads
   └─ guid_backup/       OFF-LIMITS
```

Symlinks (`deploy.sh`): `<fs_homepath>/profiles -> <repo>` (convenience, the game does not use it; asks before replacing a folder or other link there); every mod folder gets `profiles -> <repo>` (engine profile folder: etconfig.cfg, defaultprofile.dat, `exec profiles/user.cfg`) and `profile -> <repo>/<PROFILE>` (so cfg paths are written `profile/...`, independent of the profile name); `default/mods/<mod>/autoexec*` and `mod_*` → `<fs_homepath>/<mod>/` (the game finds them through the mod search path, which is how `exec mod_general.cfg` reaches the current mod's file; `mods/example/` is skipped); `default/autoexecs/*` → mod folder for `AUTOEXEC_MODS` (`legacy etpub silent etjump nitmod`); `default/maps/` → `<fs_homepath>/etmain/maps` (etmain is in every mod's search path, so one link serves all mods; `docs/locations.md`); `guid_backup/<key>` → mod folders (real key files the game wrote are backed up to `guid_backup/<key>_<date>` first).

## Only the exec chain is live

The engine execs `autoexec.cfg` from the mod folder at startup (details: `docs/autoexec.md`). A file is only used if it is reachable from a mod's `autoexec.cfg` via `exec` (or is an event autoexec the mod supports). Check the chain before assuming a cfg matters:

```
~/.etlegacy/<mod>/autoexec.cfg  (= default/mods/<mod>/autoexec.cfg)   # game start + mod switch
├─ unbindall
├─ exec profile/definitions.cfg                      # definitions, also re-exec'd by F3 (vstr reloadDefinitions)
│   ├─ scripts/common.cfg        # shared primitives (play* sounds, null), first
│   ├─ cvars.cfg, binds_default.cfg, binds_custom.cfg
│   ├─ scripts/scripts.cfg, scripts/movement.cfg, scripts/display.cfg
│   ├─ scripts/classcript.cfg  → scripts/class/cs_*.cfg
│   ├─ scripts/spawnscript.cfg
│   ├─ scripts/voicechat.cfg   → scripts/vsays/chat.cfg, vsays_custom.cfg
│   │                            (vsays/chat/*.cfg, vsays/servers/<clan>/*.cfg: voice chat pages, exec'd at runtime when opened)
│   ├─ server/server.cfg
│   ├─ exec mod_general.cfg        # = mods/<mod>/mod_general.cfg (symlink, mod search path), overrides the general values
│   │   └─ (nitmod only) scripts/vsays/chat_shortcuts.cfg
│   └─ exec mod_classcommands.cfg  # = mods/<mod>/mod_classcommands.cfg, mod weapon IDs
├─ exec profiles/user.cfg                            # personal settings (name, fps, mouse, fov, refresh rate, resolution, net rates), override the definitions; also run by F3
└─ exec profile/state.cfg                            # start values of state, skipped by F3; applies user.cfg aliases
    └─ vstr modState                                 # mod specific state, defined in mod_general.cfg
```

Each file's `echo ^5*** ... LOADED!` marker is indented by its depth in this tree, so the console prints the chain as a tree (children before their parent). `F3` re-execs the definitions and `user.cfg` in game (needed after servers enforce values) and keeps state (`state.cfg`); `F1` is the full reset; a mod switch goes through `autoexec_mod.cfg` (mechanism and mod matrix: `docs/autoexec.md`). `*.backup`, `vsays/chat_function.cfg`, commented-out execs and `mods/example/` (template for new mods) are not live.

## Mod-specific vs general code

Goal: one general script set that works on every server/mod. Put code in the general files; `mods/<mod>/mod_general.cfg` and `mod_classcommands.cfg` only define the aliases/values that differ, which general scripts consume via `vstr`. Per-mod differences are documented in `default/mods/<mod>/README.md` (e.g. alt-fire `weapalt` vs `+attack2`, spectator command, min FOV, class command weapon IDs).

Conventions (naming, `binds_default.cfg` markers, `seta` vs `set`, feedback, file layout): follow `docs/conventions.md`. Syntax highlighting: VSCode "quake2-config-syntax".

## Documentation links

ET: Legacy (current, authoritative):

- Cvars: [https://etlegacy.readthedocs.io/en/latest/cvars.html](https://etlegacy.readthedocs.io/en/latest/cvars.html)
- Commands: [https://etlegacy.readthedocs.io/en/latest/commands.html](https://etlegacy.readthedocs.io/en/latest/commands.html)
- Vsays: [https://etlegacy.readthedocs.io/en/latest/vsays.html](https://etlegacy.readthedocs.io/en/latest/vsays.html)
- HUD editor: [https://etlegacy.readthedocs.io/en/latest/hudeditor.html](https://etlegacy.readthedocs.io/en/latest/hudeditor.html)
- Manual: [https://etlegacy.readthedocs.io/en/latest/manual.html](https://etlegacy.readthedocs.io/en/latest/manual.html)
- Wiki (paths/file structure, features): [https://github.com/etlegacy/etlegacy/wiki](https://github.com/etlegacy/etlegacy/wiki) , [https://github.com/etlegacy/etlegacy/wiki/Path-and-File-Structure](https://github.com/etlegacy/etlegacy/wiki/Path-and-File-Structure)
- Source (local checkout path: `CLAUDE.local.md`): [https://github.com/etlegacy/etlegacy](https://github.com/etlegacy/etlegacy)
- Lua API: [https://etlegacy-lua-docs.readthedocs.io/](https://etlegacy-lua-docs.readthedocs.io/)
- Site: [https://www.etlegacy.com](https://www.etlegacy.com)

N!tmod (valid for 2.3.5, Feb 2023; `nitmod.com` is now a squatted gambling site, ignore it):

- Download: [http://etmods.net/downloads/](http://etmods.net/downloads/)
- Cvar docs: [http://etmods.net/nitmod/cvars.php](http://etmods.net/nitmod/cvars.php)
- Older (2.x/2010) docs mirror: [https://wolfet.vexer.info/nitmod-documentation-online](https://wolfet.vexer.info/nitmod-documentation-online)
- Most reliable: in-game `/cvarlist` / `/cmdlist` on nitmod.

ETPro (final 3.2.6, 2006):

- Original pages are **down**: [https://etpro.anime.net/playerguide.html](https://etpro.anime.net/playerguide.html) (client features, per-map autoexec, cvar list; archived: [web.archive.org](https://web.archive.org/web/20161026044531/http://etpro.anime.net/playerguide.html), fetch with `curl`), [https://etpro.anime.net/adminguide.html](https://etpro.anime.net/adminguide.html)
- WolfWiki: [https://wolfwiki.anime.net/index.php/ETPro](https://wolfwiki.anime.net/index.php/ETPro)

Jaymod (final 2.2.0):

- Manual PDF: [https://et.clan-etc.de/jaymod/jaymod.pdf](https://et.clan-etc.de/jaymod/jaymod.pdf)
- Site: [https://jaymod.clanfu.org/](https://jaymod.clanfu.org/) ; archived source + doc/: [https://github.com/budjb/jaymod](https://github.com/budjb/jaymod)

etpub: [https://www.etpub.org/docs_client_20100628.html](https://www.etpub.org/docs_client_20100628.html)

silEnT: [https://sites.google.com/site/peyoteet/enemy-territory-resources/mods/silent-mod/client-manual-0-8-2](https://sites.google.com/site/peyoteet/enemy-territory-resources/mods/silent-mod/client-manual-0-8-2)

ETJump: [https://etjump.readthedocs.io/en/latest/client/etjump_cvars.html](https://etjump.readthedocs.io/en/latest/client/etjump_cvars.html) , [https://etjump.readthedocs.io/en/latest/client/client_commands.html](https://etjump.readthedocs.io/en/latest/client/client_commands.html) , source [https://github.com/etjump/etjump](https://github.com/etjump/etjump)

General ET scripting: knowledge summary and guide links in `docs/scripting.md`.

## Testing

No build/test. Test changes in game: re-exec `autoexec.cfg` (F3), check console output (the `echo ^5*** ... LOADED!` markers), `/condump <file>` to save console.

### Start ET: Legacy with a mod and map (local hosting)

```
etl.x86_64 +set fs_game <mod> +set dedicated 0 +map <mapname>
# e.g. etl.x86_64 +set fs_game nitmod +set dedicated 0 +map fueldump
```

- `+map` hosts without cheats; `+devmap` enables cheats (legacy then tries `autoexec_devmap_<map>.cfg` first).
- Hosting needs the mod's server module `qagame.mp.x86_64.so` in `~/.etlegacy/<mod>/` (legacy ships it in `/usr/lib/etlegacy/legacy/`). Client pk3s like `nitmod_2.3.5.pk3` don't contain it; the mod's server package must be installed.
- Bots come from `default/server/server.cfg` (omni-bot).
- From Claude Code: run in background and outside the sandbox (needs the display and writes to `~/.etlegacy/`). Redirect output to an absolute scratchpad path, because `$TMPDIR` is empty outside the sandbox. Verify with the log: `Sys_LoadDll(.../<mod>/qagame...) succeeded`, the `execing ...` lines (autoexec chain, `autoexec_<map>.cfg`, `autoexec_<team>.cfg`) and `>>> AUTOEXEC LOADED!`.

