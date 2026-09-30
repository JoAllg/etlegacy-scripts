---
name: keymap
description: Regenerate the keyboard + mouse keymap (tools/keymap/keymap.html) and name new binds in tools/keymap/labels.json. Use when binds, class scripts or menu layers changed, or the user asks for the keymap / keybind overview.
---

# Keymap

`tools/keymap/keymap.py` runs the exec chain in a console emulator and simulates key presses, so views (Base + class variants from `cs_<class>_<weapon>`), toggles (⟳) and layers (hover: keys a key rebinds) are detected automatically. Your job is only the names: `labels.json` maps a bind command to a short action name.

## Steps

1. `python3 tools/keymap/keymap.py --missing` (repeat with `--mod legacy`; mods bind different commands, e.g. `+attack2` vs `weapalt`). Each entry: the command, `keys` where it appears (`F6 -> MOUSE2` = shown on MOUSE2 while hovering F6), `expands` (one alias level), `at` (file:line).
2. For every unlabeled command read `at` (the bind or alias and its comments) when `expands` does not make the purpose obvious. Add `"<command exactly as printed>": "<Label>"` to `labels.json`:
   - 1–2 words, max ~16 chars, English, what the player does, not how (`Med pack`, not `weapon6 hold`).
   - Same action, same name: mod variants (`+attack2` / `weapalt` = `Alt fire`), hold and toggle variants of one feature (`+vstr crouchON crouchOFF` and `vstr crouchswitch` = `Crouch`).
   - No "toggle"/"cycle"/"menu" in the name, the detected icon shows it: ⇄ toggle, ⟳ cycle (pointer named `cycle*` or more than 2 values; wins over menu), ☰ menu (gives ≥ `MENU_MIN` other keys new actions) (`vstr SniperToggle` = `Sniper Mode`).
   - Menu layer entries are named by what they select (`vstr cCat1` = `Statements`, from the `echoCat*` text).
   - Ask the user when the purpose stays unclear.
3. `unused label(s)`: remove an entry only if it is unused for every mod in `default/mods/` (except `example`).
4. `python3 tools/keymap/keymap.py --selftest`, then `python3 tools/keymap/keymap.py`: must report `0 unlabeled commands`.
5. If views look wrong (missing class, key not detected as layer), adjust the scenario constants at the top of `keymap.py` (`SCENARIO`, `CLASS_HOOK`, `CLASS_ALIAS`), not per-script code. Publish `keymap.html` as an Artifact only when the user asks.
