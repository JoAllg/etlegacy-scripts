---
name: vsay
description: Vsay and chat texts (vsay / vsay_team / vsay_buddy with text, say / say_team / say_teamnl / say_buddy; profile cfgs, server voice chat pages included) and the echo menus. Translate non-English pages to English, color the texts with the user's VSAY_* colors from settings.conf, show or change those colors (HTML preview), highlight key words; also applies the MENU_* colors of the echo menus (voice chat, spawn selector). Use after tools/voicemenu.py added vsays, after new vsay or chat texts were written, or when the user asks about vsay/chat text colors, highlighting, translation or echo menu colors.
---

# Vsay and chat texts

`tools/vsaycolors.py` does everything deterministic; your part is translating, talking to the user about the colors and choosing the key words. It handles vsay texts and chat texts (`say`, `say_team`, `say_teamnl`, `say_buddy` anywhere in the profile, e.g. class report, spawn report; not `say !command`) alike.

Echo menu colors (`settings.conf`, voice chat and spawn selector, server pages included): `MENU_HEAD` heading, `MENU_KEY` key number, `MENU_TEXT` item, `MENU_NAV` TAB line, `MENU_GLOBAL` global chat item (general voice chat only), `MENU_AXIS` / `MENU_ALLIES` spawnpoint owner. `apply` recolors every echo menu line with them (an item keeps its role by its color of the last apply); `tools/voicemenu.py` and `tools/spawnpoints/spawnpoints.py` generate with them. They are chosen for the popup shadow of the HUD (`huds/hud_v8.dat` `popupmessages` `textStyle 3`). To change one: edit the line in `settings.conf`, run `apply` (step 4), and for spawn menus of the generator also rerun `tools/spawnpoints/spawnpoints.py`.

Roles (`settings.conf`): `VSAY_TEAM` / `VSAY_GLOBAL` / `VSAY_BUDDY` base color of `vsay_team` + `say_team` / `say_teamnl`, `vsay` + `say`, `vsay_buddy` + `say_buddy` (fireteam; only the raw form `vsay_buddy -1 <n> [client ids] <id> <text>` carries a text, `VoiceFireTeamChat <id>` takes none), `VSAY_PUNCT` punctuation (`. , ! ? :` ending a word), `VSAY_HIGHLIGHT` key word, `VSAY_URGENT` urgent/danger word. If a value is missing, ask the user which color to use and add the line (never invent one).

## 1. Current colors

Run `python3 tools/vsaycolors.py status` and tell the user the values (code, hex and the name from `docs/colors.md`; vsay and menu colors) and the counts. Ask whether they want to change a color.

## 2. Translate

Judge the language per page (voice chat pages in `default/scripts/vsays/`, server pages in `servers/<clan>/` included). If most texts of a page are not English, translate the whole page to English: its vsay and chat texts and its echoes that are not a vsay key (heading, page links, TAB line, keys of random vsays without text). A single text in another language on an English page is on purpose: leave it.

- Short chat English in the style of the stock pages, same meaning and tone; keep names, map/server words and the server tag at the start of a heading.
- Keep the color codes: base color around the words, punctuation color on the punctuation, an existing highlight on the translated word that carries it.
- Change only the text: never the id, the key, the rest of the line, and never add `;` or `"`. Translate every copy of a vsay the same way (see step 5).
- Server pages: echoes of vsay keys follow their text in `apply` (step 4), don't edit them. General voice chat pages: translate the echo of each translated vsay key by hand.
- A rerun of `tools/voicemenu.py` keeps the translations (texts per vsay, headings, echoes of keys without text); new vsays it reports come in the server's language: translate them too.

Show the user the first page's translations before doing the rest. Translated texts without highlight land in the todo list of step 5.

## 3. Changing colors (only if the user asks)

1. `python3 tools/vsaycolors.py preview <role>=<code> ...` (roles: `team global buddy punct highlight urgent`) writes `tools/vsaycolors.html`: current vs proposed colors, real chat lines in both, the full palette. Give the user the path and offer alternatives; repeat until they decide.
2. Edit the chosen `VSAY_*` lines in `settings.conf` (keep the quotes). Don't touch the vsays file `vsaycolors.tsv`: its first line holds the colors of the last apply, which `apply` needs to map old codes to new ones.

## 4. Apply

`python3 tools/vsaycolors.py apply`, then report its list:
- Colors changed since the last apply: every code of an old role color becomes the new one, so existing highlights stay.
- Texts without base/punctuation colors and without highlights (new texts, server colors) are colored like `tools/voicemenu.py` does.
- Texts that are already right are not touched. "highlighted, but base/punctuation differ" lines are left alone: show them to the user.
- Server page echoes show the text of their key's `set vsay<key>` line without colors. Echoes of the general voice chat pages are fixed: `apply` only recolors them.
- Echo menu lines get the `MENU_*` colors.

## 5. Highlight

`python3 tools/vsaycolors.py todo` lists the texts that have base/punctuation colors but no highlight and were not reviewed. Texts containing a highlight or urgent color are done; never change them again.

For each todo text edit only the color codes inside the text (file:line from the list):
- Highlight 1–3 words that carry the message (the action or its object) with `VSAY_HIGHLIGHT`, and switch back to the base color before the next plain word. Style: the stock pages in `default/scripts/vsays/chat/`, e.g. `^9Clear the ^xpath^3!`; chat texts the same way, e.g. `^9I will spawn at ^xBunker`.
- `VSAY_URGENT` only for urgency or danger (help, incoming, fire, disarm, medic, backup): `^9I need ^1backup^3!`.
- Leave pure sounds and jokes plain (onomatopoeia, laughs, song lines): not every text needs a highlight.
- No highlights on the general talk pages `chat/talk.cfg`, `chat/global.cfg`, `chat/global2.cfg` (yes/no, thanks, greetings); they stay plain. The same kind of text on server pages may be highlighted.
- Never change the words, the id, the key or the rest of the line, and never add `;` or `"`.
- Server pages (`default/scripts/vsays/servers/`): the same vsay can be on several pages; `voicemenu.py` keeps the text of the first page in file-name order, so edit every copy the same way.

Large todo lists: work through them file by file and show the user the first file's result before doing the rest.

Afterwards run `python3 tools/vsaycolors.py apply` (server page echoes follow the new texts), then `python3 tools/vsaycolors.py done`: the remaining plain texts are marked as reviewed, so they are not offered again. Finish with a short list: file, key/line, new text.
