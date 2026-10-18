---
name: vsay
description: Vsay and chat texts (vsay / vsay_team / vsay_buddy with text, say / say_team / say_teamnl / say_buddy; profile cfgs, server voice chat pages included) and the echo menus. Creates or updates a server's voice chat pages from its pk3 (tools/voicemenu.py, checks for a newer or different pack), translates non-English pages to English, colors the texts with the user's VSAY_* colors from settings.conf, shows or changes those colors (HTML preview), highlights key words, applies the MENU_* colors of the echo menus (voice chat, spawn selector), and suggests chat shortcut variants ([H], [P], [S], ...) of a nitmod/etps server's own vsays. Use when a server got a new voice pack or needs its voice chat, after tools/voicemenu.py added vsays, after new vsay or chat texts were written, or when the user asks about vsay/chat text colors, highlighting, translation, echo menu colors or shortcuts in server vsays.
---

# Vsay and chat texts

`tools/vsaycolors.py` and `tools/voicemenu.py` do everything deterministic; your part is choosing the pack with the user, translating, talking to the user about the colors, choosing the key words and suggesting shortcut texts. `vsaycolors.py` handles vsay texts and chat texts (`say`, `say_team`, `say_teamnl`, `say_buddy` anywhere in the profile, e.g. class report, spawn report; not `say !command`) alike.

Echo menu colors (`settings.conf`, voice chat and spawn selector, server pages included): `MENU_HEAD` heading, `MENU_KEY` key number, `MENU_TEXT` item, `MENU_NAV` TAB line, `MENU_GLOBAL` global chat item (general voice chat only), `MENU_AXIS` / `MENU_ALLIES` spawnpoint owner. `apply` recolors every echo menu line with them (an item keeps its role by its color of the last apply); `tools/voicemenu.py` and `tools/spawnpoints/spawnpoints.py` generate with them. They are chosen for the popup shadow of the HUD (`huds/hud_v8.dat` `popupmessages` `textStyle 3`). To change one: edit the line in `settings.conf`, run `apply` (step 5), and for spawn menus of the generator also rerun `tools/spawnpoints/spawnpoints.py`.

Roles (`settings.conf`): `VSAY_TEAM` / `VSAY_GLOBAL` / `VSAY_BUDDY` base color of `vsay_team` + `say_team` / `say_teamnl`, `vsay` + `say`, `vsay_buddy` + `say_buddy` (fireteam; only the raw form `vsay_buddy -1 <n> [client ids] <id> <text>` carries a text, `VoiceFireTeamChat <id>` takes none), `VSAY_PUNCT` punctuation (`. , ! ? :` ending a word), `VSAY_HIGHLIGHT` key word, `VSAY_URGENT` urgent/danger word. If a value is missing, ask the user which color to use and add the line (never invent one).

## 1. Server voice chat (pk3)

Ask (multiSelect) which servers to create or update: the ids with a folder `default/serverconfigs/vsays/<id>/` and the ids of `default/serverconfigs/servers.tsv` without one. None: go to step 2.

Per chosen id:
1. `python3 tools/voicemenu.py --find <id>`: the packs with a quick chat menu and own vsays in the id's mod folders. A pack can be split (menu in one pk3, voice scripts in another: listed together), and a server that updated its pack leaves versions `<name>.<checksum>.pk3` (the engine's download name when the name exists already). Marks: `SERVER` (listed first, after a line per address with what it loads) = the pk3s the game loaded the menu and voice scripts from on that server (`default/serverconfigs/packs.tsv`, written by `tools/serverconfig.py` at the first map load on a server); `known` = how many vsays of the last run (`vsays.tsv`) a pack holds; `names-tag` = its menu has the servers.tsv text; `LAST` = the pk3s of the last run (named in the first line of every page).
2. Judge: `SERVER` is the pack the server uses; the date of its line says when the game last asked. `LAST` = `SERVER`: nothing to do. No `SERVER` line (the server wasn't joined since the record exists): tell the user that joining it once (one map load, with `launcher.sh` running) records it; only if they don't want to, recommend from the rest (newest with most known vsays or `names-tag`; the versions of a split pack can't be told apart that way). An id without pages lists all packs.
3. Tell the user what you found and ask which pk3s to use (recommend one; "keep" when nothing changed). Not found at all: the pack arrives by joining the server once (download), then rerun `--find`.
4. `python3 tools/voicemenu.py <id> <fs_homepath>/<pk3> [<fs_homepath>/<pk3> ...]` (all pk3s of the chosen line; `--address <ip:port>` of the row only if it warns that no server name with the tag is known; asking a server needs the network: outside the sandbox).
5. Report its output: pages, vsays not in the server menu, added (`+`), removed (`-`) and changed (`~`) vsays, shortcut texts whose vsay is gone (`- shortcut`). Removed vsays or a new pack: suggest the vsay-server-overrides skill for that id (its rerun drops sounds the server no longer has).

New vsays come in the server's colors and language: steps 3–6 handle them.

## 2. Current colors

Run `python3 tools/vsaycolors.py status` and tell the user the values (code, hex and the name from `docs/colors.md`; vsay and menu colors) and the counts. Ask whether they want to change a color.

## 3. Translate

Judge the language per page (voice chat pages in `default/scripts/vsays/`, server pages in `default/serverconfigs/vsays/<clan>/` included). If most texts of a page are not English, translate the whole page to English: its vsay and chat texts and its echoes that are not a vsay key (heading, page links, TAB line, keys of random vsays without text). A single text in another language on an English page is on purpose: leave it.

- Short chat English in the style of the stock pages, same meaning and tone; keep names, map/server words and the server tag at the start of a heading.
- Keep the color codes: base color around the words, punctuation color on the punctuation, an existing highlight on the translated word that carries it.
- Change only the text: never the id, the key, the rest of the line, and never add `;` or `"`. Translate every copy of a vsay the same way (see step 6).
- Server pages: echoes of vsay keys follow their text in `apply` (step 5), don't edit them. General voice chat pages: translate the echo of each translated vsay key by hand.
- A rerun of `tools/voicemenu.py` keeps the translations (texts per vsay, headings, echoes of keys without text); new vsays it reports come in the server's language: translate them too.

Show the user the first page's translations before doing the rest. Translated texts without highlight land in the todo list of step 6.

## 4. Changing colors (only if the user asks)

1. `python3 tools/vsaycolors.py preview <role>=<code> ...` (roles: `team global buddy punct highlight urgent`) writes `tools/vsaycolors.html`: current vs proposed colors, real chat lines in both, the full palette. Give the user the path and offer alternatives; repeat until they decide.
2. Edit the chosen `VSAY_*` lines in `settings.conf` (keep the quotes). Don't touch the vsays file `vsaycolors.tsv`: its first line holds the colors of the last apply, which `apply` needs to map old codes to new ones.

## 5. Apply

`python3 tools/vsaycolors.py apply`, then report its list:
- Colors changed since the last apply: every code of an old role color becomes the new one, so existing highlights stay.
- Texts without base/punctuation colors and without highlights (new texts, server colors) are colored like `tools/voicemenu.py` does.
- Texts that are already right are not touched. "highlighted, but base/punctuation differ" lines are left alone: show them to the user.
- Server page echoes show the text of their key's `set vsay<key>` line without colors (a key with a shortcut text: that text, step 7). Echoes of the general voice chat pages are fixed: `apply` only recolors them.
- Echo menu lines get the `MENU_*` colors.

## 6. Highlight

`python3 tools/vsaycolors.py todo` lists the texts that have base/punctuation colors but no highlight and were not reviewed. Texts containing a highlight or urgent color are done; never change them again.

For each todo text edit only the color codes inside the text (file:line from the list):
- Highlight 1–3 words that carry the message (the action or its object) with `VSAY_HIGHLIGHT`, and switch back to the base color before the next plain word. Style: the stock pages in `default/scripts/vsays/chat/`, e.g. `^9Clear the ^xpath^3!`; chat texts the same way, e.g. `^9I will spawn at ^xBunker`.
- `VSAY_URGENT` only for urgency or danger (help, incoming, fire, disarm, medic, backup): `^9I need ^1backup^3!`.
- Leave pure sounds and jokes plain (onomatopoeia, laughs, song lines): not every text needs a highlight.
- No highlights on the general talk pages `chat/talk.cfg`, `chat/global.cfg`, `chat/global2.cfg` (yes/no, thanks, greetings); they stay plain. The same kind of text on server pages may be highlighted.
- Never change the words, the id, the key or the rest of the line, and never add `;` or `"`.
- Server pages (`default/serverconfigs/vsays/`): the same vsay can be on several pages; `voicemenu.py` keeps the text of the first page in file-name order, so edit every copy the same way.

Large todo lists: work through them file by file and show the user the first file's result before doing the rest.

Afterwards run `python3 tools/vsaycolors.py apply` (server page echoes follow the new texts), then `python3 tools/vsaycolors.py done`: the remaining plain texts are marked as reviewed, so they are not offered again. Finish with a short list: file, key/line, new text.

## 7. Shortcuts (nitmod and etps servers)

nitmod and etps replace chat shortcuts like `[H]` (last healer) in a vsay text (they send it as a chat line); legacy and the other mods show them literally. Ids: those of step 1; if step 1 was skipped, ask (multiSelect) which ids with pages.

1. **Mod:** the mod column of the id's row in `servers.tsv`. `nitmod` or `etps`: go on. Empty (the row matches servers of any mod) or another mod: skip the id and tell the user why. Then look in `default/serverconfigs/history.tsv` for servers whose name contains the row's text (colors ignored, any case): none, or some of them with another mod (the clan also runs servers of that mod) → tell the user which and ask whether to go on.
2. **Shortcuts:** read the Shortcuts section of `default/scripts/vsays/README.MD`. Use only `[A] [D] [H] [K] [P] [R]` (names; a person not known yet becomes `*unknown*`), `[S] [T] [W]` (own health, ammo, weapon) and `[N]` (own name); never `[L]` (coordinates, not a location name) or the jaymod/legacy ones.
3. **Candidates:** the server's vsays that send a text (`set vsay<key> "<cmd> <id> <text>"` on the pages, not the random ones without text) and have no shortcut text yet (`shortcuts/<page>.cfg`). Only those where a shortcut fits the meaning: thanks for health, revive or ammo (`[H]`, `[R]`, `[A]`), taunt of a victim (`[K]`), words to the killer (`[D]`), words to a teammate (`[P]`), call for a medic or ammo (`[S]`, `[T]`), weapon talk (`[W]`), introducing oneself (`[N]`). No forced shortcuts on jokes, songs and pure sounds.
4. **Variants:** 2–3 per vsay: the original words with the shortcut woven in or appended (`Thanks [H]!`, `Nice try [D]`, `[S] HP left, medic!`). Keep the text's color codes: the shortcut in the base color (or the highlight, if it is the word that carries the message), punctuation in `VSAY_PUNCT`. No `;` or `"`; the line expanded must stay within 149 characters including color codes: count a name shortcut as 36 characters (`MAX_NAME_LENGTH`, `src/qcommon/q_shared.h`).
5. **Questionnaire:** AskUserQuestion, up to 4 vsays per call, one question each: header the vsay id, question with the current text without colors, page and key; options the variants (plain text in the label, the colored text in the description) and "Keep original" (the user can type an own text under Other). Show the text with the shortcut expanded by an example name if that helps.
6. **Write:** a chosen variant goes into `default/serverconfigs/vsays/<id>/shortcuts/<page>.cfg` of a page holding the vsay: the page's `set vsay<key>` line with the new text (`// Vsays` block; new file: just the lines, the rerun adds the header). `tools/voicemenu.py` keeps these texts per vsay: its rerun puts them on every page and key the vsay is on, adds `execq .../shortcuts/<page>.cfg` after the page's vsays and echoes the shortcut text. Then rerun `python3 tools/voicemenu.py <id> <pk3s>` with the pk3s of the page header (their folders: the `LAST` line of `--find`).
7. `python3 tools/vsaycolors.py apply`; shortcut texts that land in `todo` are handled like step 6. Finish with a short list: id, page, key, vsay, new text.
