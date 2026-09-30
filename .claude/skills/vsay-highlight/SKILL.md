---
name: vsay-highlight
description: Color all vsay chat texts (vsay / vsay_team / vsay_buddy with text in the profile cfgs, server voice chat pages included) with the user's VSAY_* colors from settings.conf, show or change those colors (HTML preview), and highlight key words; also applies the MENU_* colors of the echo menus (voice chat, spawn selector). Use after tools/voicemenu.py added vsays, after new vsay texts were written, or when the user asks about vsay text colors, highlighting or echo menu colors.
---

# Vsay colors

`tools/vsaycolors.py` does everything deterministic; your part is talking to the user about the colors and choosing the key words.

Echo menu colors (`settings.conf`, voice chat and spawn selector, server pages included): `MENU_HEAD` heading, `MENU_KEY` key number, `MENU_TEXT` item, `MENU_NAV` TAB line, `MENU_GLOBAL` global chat item (general voice chat only), `MENU_AXIS` / `MENU_ALLIES` spawnpoint owner. `apply` recolors every echo menu line with them (an item keeps its role by its color of the last apply); `tools/voicemenu.py` and `tools/spawnpoints/spawnpoints.py` generate with them. They are chosen for the popup shadow of the HUD (`hud.dat` `popupmessages` `textStyle 3`). To change one: edit the line in `settings.conf`, run `apply` (step 3), and for spawn menus of the generator also rerun `tools/spawnpoints/spawnpoints.py`.

Roles (`settings.conf`): `VSAY_TEAM` / `VSAY_GLOBAL` / `VSAY_BUDDY` base color of `vsay_team` / `vsay` / `vsay_buddy` (fireteam; only the raw form `vsay_buddy -1 <n> [client ids] <id> <text>` carries a text, `VoiceFireTeamChat <id>` takes none), `VSAY_PUNCT` punctuation (`. , ! ? :` ending a word), `VSAY_HIGHLIGHT` key word, `VSAY_URGENT` urgent/danger word. If a value is missing, ask the user which color to use and add the line (never invent one).

## 1. Current colors

Run `python3 tools/vsaycolors.py status` and tell the user the values (code, hex and the name from `docs/colors.md`; vsay and menu colors) and the counts. Ask whether they want to change a color.

## 2. Changing colors (only if the user asks)

1. `python3 tools/vsaycolors.py preview <role>=<code> ...` (roles: `team global buddy punct highlight urgent`) writes `tools/vsaycolors.html`: current vs proposed colors, real chat lines in both, the full palette. Give the user the path and offer alternatives; repeat until they decide.
2. Edit the chosen `VSAY_*` lines in `settings.conf` (keep the quotes). Don't touch the vsays file `vsaycolors.tsv`: its first line holds the colors of the last apply, which `apply` needs to map old codes to new ones.

## 3. Apply

`python3 tools/vsaycolors.py apply`, then report its list:
- Colors changed since the last apply: every code of an old role color becomes the new one, so existing highlights stay.
- Texts without base/punctuation colors and without highlights (new texts, server colors) are colored like `tools/voicemenu.py` does.
- Texts that are already right are not touched. "highlighted, but base/punctuation differ" lines are left alone: show them to the user.
- Server page echoes show their bind's text without colors.
- Echo menu lines get the `MENU_*` colors.

## 4. Highlight

`python3 tools/vsaycolors.py todo` lists the texts that have base/punctuation colors but no highlight and were not reviewed. Texts containing a highlight or urgent color are done; never change them again.

For each todo text edit only the color codes inside the text (file:line from the list):
- Highlight 1–3 words that carry the message (the action or its object) with `VSAY_HIGHLIGHT`, and switch back to the base color before the next plain word. Style: `default/scripts/vsays/chat.cfg`, e.g. `^9Clear the ^xpath^3!`.
- `VSAY_URGENT` only for urgency or danger (help, incoming, fire, disarm, medic, backup): `^9I need ^1backup^3!`.
- Leave pure sounds and jokes plain (onomatopoeia, laughs, song lines): not every text needs a highlight.
- No highlights in the general talk sections of `chat.cfg` (TALK, GLOBAL, GLOBAL 2: yes/no, thanks, greetings) and their copies in `server.example.cfg`; they stay plain. The same kind of text on server pages may be highlighted.
- Never change the words, the id, the key or the rest of the line, and never add `;` or `"`.
- Server pages (`default/scripts/vsays/servers/`): the same vsay can be on several pages; `voicemenu.py` keeps the text of the first page in file-name order, so edit every copy the same way.

Large todo lists: work through them file by file and show the user the first file's result before doing the rest.

Afterwards run `python3 tools/vsaycolors.py apply` (echoes of server pages follow the new binds), then `python3 tools/vsaycolors.py done`: the remaining plain texts are marked as reviewed, so they are not offered again. Finish with a short list: file, key/line, new text.
