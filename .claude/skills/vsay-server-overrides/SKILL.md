---
name: vsay-server-overrides
description: Server sounds on the stock voice chat. Replaces stock vsays (pages in default/scripts/vsays/chat/, class vsays of chat.cfg and vsays_custom.cfg) with fitting sounds of a server's voice chat (default/serverconfigs/vsays/<id>/vsays.tsv), for that server only, keeping the stock text; several sounds per key form a cycle. Suggests candidates, lets the user pick per key in a questionnaire, writes the override files, hooks and cycle pointers, and on a rerun first removes sounds the server no longer has. Use when the user wants server sounds on the normal voice chat keys, after tools/voicemenu.py brought a new or changed server pack, or names a server whose overrides should be created or updated.
---

# Server sounds on the stock voice chat

Background and mechanism: `docs/serverconfigs.md` ("Server sounds on the stock pages"), rules: `.claude/rules/serverconfigs.md`, `.claude/rules/vsays.md`. The user decides every key; you find the candidates and write the files.

## How it is built

- **Pages:** each stock page opener (`scripts/vsays/chat.cfg`, nitmod/etps: `chat_shortcuts.cfg`) ends with `vstr chatServer<Page>`. `chat.cfg` (next to the openers) and `default.cfg` set it to `vstr null`; `<id>.cfg` sets it to `execq profile/serverconfigs/vsays/<id>/override/<page>.cfg`. That file holds only the replaced `set vsay<key>` lines (page format, `// Vsays` block). Every page has its hook (Fireteam too); a new stock page gets one in its opener(s) and its `vstr null` line in `chat.cfg` and `default.cfg`.
- **Aliases outside the pages** (class vsays `vsaySoldier` … of `chat.cfg`, `vsayGrenade` … of `vsays_custom.cfg`): `<id>.cfg` sets the alias, `default.cfg` restores it with `reset <alias>  // first value of the session: scripts/vsays/<stock file>.cfg` (the cvar keeps the value it was created with; after a change of the stock text the game needs a restart). Steps of a cycle go into `override/<stock file>.cfg` (e.g. `override/vsays_custom.cfg`), which `<id>.cfg` execs (`execq`) before setting the alias. Don't override an alias that `chat_shortcuts.cfg` redefines (`vsaySyringe`): `reset` would bring back the value of `vsays_custom.cfg`, not the mod's; tell the user.
- **Cycles** (two or more sounds on one key): steps `vsay<key>a`, `b`, … in the override file, each `"<cmd> <sound> <text>; set <pointer> vstr <next step>"`, the last pointing to `a`; the key itself is `set vsay<key> "vstr <pointer>"`. Outside pages: steps `vsay<Name>A`, `B`, …. Pointers: `cycleServerVsay<Page>Key<key>` (Page: `Statements Requests Commands Talk Global GlobalN2 Objectives Fireteam FireteamN2 FireteamN3`) or `cycleServerVsay<Name>`, one per page and key, shared by all servers, start value in `default/serverconfigs/vsays/cycles.cfg` (not in git, layout in step 6; `default.cfg` execs it, so the cycles start again on every server change, `F3` and `F1`). Add missing pointers; remove a pointer only when no override file of any server uses it any more.
- **Text:** every step sends the stock text of that key, never the server's text. On nitmod and etps the stock text is the one of `chat/<page>_shortcuts.cfg` where it redefines the key (e.g. `[S]`, `[D]`). In a stock cycle with different texts a server sound takes the text of the step whose meaning fits it, else the first step's. The command stays the stock one (`vsay_team` stays team only). Copy the stock text with its color codes.
- **Variant number** (`vsay <n> <sound> <text>`, plays that variant): legacy mod only, nitmod and the others take none. Write one only on a legacy server and only when the user picked a variant. The text can't be quoted (cfg quotes don't nest), so tools read an all-digit first word as the variant: a vsay id is never all digits.
- **Order of steps:** stock sound(s) first (all steps of a stock cycle), then the server sounds in the order of the questionnaire.

## 1. Scope

- The user names a server (tag, part of its name or id): find its id in `default/serverconfigs/servers.tsv` (text in the server name, first matching row wins). Only that id.
- Else: the ids with a `default/serverconfigs/vsays/<id>/vsays.tsv`. Ask (multiSelect) which of them; never leave one out on your own (some packs only play for VIP players, the user knows which).
- Ask whether the Fireteam pages (8.1–8.3) should get overrides too; default no.

## 2. Rerun: remove sounds the server no longer has

Don't read any override file in this step.

1. `python3 tools/vsayoverrides.py <ids>`: per id "no overrides" (first run) or its override files and the lines whose sound is missing.
2. For every id with missing sounds, start one subagent (general-purpose) with this task: remove the listed sounds from `default/serverconfigs/vsays/<id>/override/*.cfg` following "How it is built" (paste the section): drop the step, relink the remaining steps (`a`, `b`, … in order, last back to `a`); one server sound left: plain `set vsay<key> "<cmd> <sound> <text>"`; only stock steps or none left: the key is no override any more, drop its lines (an alias: also its line in `<id>.cfg`); a file without vsay lines: delete it and remove its `chatServer<Page>` or `execq` line from `<id>.cfg`; an alias no server overrides any more: remove its `reset` line from `default.cfg`; pointers in `default/serverconfigs/vsays/cycles.cfg` that no override file of any server uses any more: remove them. A pointer that names a removed step is harmless in the files (it starts at `a` again), but a running game keeps the old aliases: tell the user to press `F3` (default.cfg resets the pointers). It must answer only with the removed sounds per file and key, nothing of the remaining content.
3. Tell the user what was removed.

## 3. Candidates (before reading the existing overrides)

- Server sounds: read `vsays/<id>/vsays.tsv` (`vsay`, `variant`, `team`, `text`). Every sound plays for both teams; `team` only tells which team the pack meant it for.
- Stock vsays: the pages `default/scripts/vsays/chat/*.cfg` without `*_shortcuts.cfg` (Fireteam pages only if chosen in step 1), the class vsays of `chat.cfg` (`vsay<Class>`) and the vsays of the other cfgs in `default/scripts/vsays/` (e.g. `vsays_custom.cfg`). Never `chat_shortcuts.cfg` (its texts are the stock text on nitmod/etps, see above) or `chat_function.cfg` (not live). Ids and meanings: `default/scripts/vsays/README.MD`.
- Mod of the server: its address from `default/serverconfigs/history.tsv` (row whose name contains the `servers.tsv` text), then `cd tools && python3 -m helpers.serverapi <address>` (needs the network: outside the sandbox). nitmod/etps: the shortcut texts apply.
- For each stock key, the server sounds whose meaning fits it (greeting for Hi, "Nein!" for No, "Run!" for Move, ...). Judge the sound by its text; a joke that still says the same thing fits.
- Class vsays of `vsays_custom.cfg` (`vsayGrenade`, `vsaySatchel`, ...) inform the teammates of what the class script just did: only sounds that name that action unmistakably (grenade, dynamite, satchel, airstrike, ...). A sound that hides it ("Surprise!", "Say hello to my little friend!") is no candidate, however well it fits the mood.

## 4. Existing choices

Only now read `vsays/<id>/override/*.cfg` and the override lines of `<id>.cfg`: the current sounds per key (stock steps count as "stock").

## 5. Questionnaire

One question per key that has candidates or a current override, `AskUserQuestion` with `multiSelect: true`, up to 4 questions per call, one server after the other.

- Header: `<id> <key>` with the page letters `S R C T G G2 O F F2 F3` (`etc G.4`), or the alias (`etc Grenade`). Question: the stock line, e.g. "etc 5.1 GLOBAL key 4: Hi! (Hi). Which sounds?".
- Options: `stock` (description: the stock sound(s) and text of the key, all steps of a stock cycle), one per candidate sound (label: the sound id, `(R)` behind it if `team` is `axis`, `(B)` if `allies`; on a legacy server with several variants of the sound one option per variant, `<sound> v<n>`; description: its text from the tsv), and `none` (no override, the stock key stays).
- Current choices: the tool can't preselect options, so put `(current)` at the end of the label and say in the question that the current choice is marked and must be selected again to keep it.
- At most 4 options per question: with more, continue the key in further questions (`etc G.4 2/2`) with the remaining candidates; `stock` and `none` stay in the first one.
- Meaning of the answer: the selected options together; one sound = plain override, several = cycle in step order (stock first); `none` or nothing selected = no override on that key. "Other" text is the user's instruction for that key.

## 6. Write

For each server, from the answers (keys without a change stay as they are):

- `vsays/<id>/override/<page>.cfg`: header line `// <heading of the page>: server sounds of '<id>' with the stock texts, exec'd after the page (chatServer<Page>, serverconfigs/<id>.cfg)`, empty line, `// Vsays`, the key lines in key order `1`..`9`, `0`. Rewrite the lines of the changed keys; drop keys answered `none` or only `stock` (no server sound = no override); a file without keys is deleted with its hook line.
- `<id>.cfg` (the user's file, but this skill is asked to write it): one block, which replaces the existing block and stays at the end of the file. Hooks in page order, then per alias the `execq` of its steps file (only for a cycle) and the alias:

  ```
  // Server sounds on the stock voice chat pages (vsays/<id>/override/, cycle pointers: vsays/cycles.cfg)
  set chatServerRequests "execq profile/serverconfigs/vsays/xy/override/requests.cfg"
  set chatServerGlobal "execq profile/serverconfigs/vsays/xy/override/global.cfg"
  execq profile/serverconfigs/vsays/xy/override/vsays_custom.cfg  // steps of the class vsays below
  set vsayGrenade "vstr cycleServerVsayGrenade"  // stock / xy_boom
  ```

- `default.cfg`, `chat.cfg`, `chat_shortcuts.cfg`: only for a new stock page or a new alias (see "How it is built"): an alias gets its `reset` line in `default.cfg`.
- `vsays/cycles.cfg`: missing pointers, in this layout (page pointers sorted by name, alias pointers last):

  ```
  // Cycle pointers of the server sounds on the stock voice chat (<id>/override/*.cfg), written by the vsay-server-overrides skill:
  // one per page and key, shared by all servers. Exec'd by default.cfg, so every cycle starts again on a server change, F3 and F1:
  // a pointer may name a step the new server lacks

  set cycleServerVsayCommandsKey2 "vstr vsay2a"
  set cycleServerVsayGlobalKey4 "vstr vsay4a"
  set cycleServerVsayGlobalN2Key3 "vstr vsay3a"

  // Aliases outside the pages (steps: <id>/override/<stock file>.cfg)
  set cycleServerVsayGrenade "vstr vsayGrenadeA"
  ```

## 7. Check and report

- `python3 tools/serverconfig.py --check` (names `default.cfg` doesn't reset), `python3 tools/vsayoverrides.py <ids>` (0 missing), `python3 tools/vsaycolors.py status`. Texts copied from the stock pages land in its highlight todo (`todo`): if the todo holds only those, `done`; anything else goes to the vsay skill.
- Report per server: keys changed (sound list, cycle or single), keys removed, files and hooks added. Nothing is committed unless the user asks.
- In-game test: on the server open the page, press the key several times (the cycle steps through the sounds), then on another server the stock sound plays again.
