# Key names for `bind` (ET: Legacy)

**All key tables below describe a US ANSI keyboard** (as in the key name chart this is transcribed from), except the sections "German QWERTZ layout" and "Other names". On another layout, first read "How a physical key becomes a key number": letter and symbol keys follow the active layout, so the same physical key can have a different bind name.

**Test which name a key has** before binding it:
- Keyboard: `/in_keyboardDebug 1`, press the key; the console prints SDL scancode, keycode and modifiers. `/in_keyboardDebug 0` to stop.
- Mouse: there is no mouse debug cvar (`cl_showmouserate 1` only prints mouse speed). Assign the button to any action in Options → Controls: the menu shows its bind name. That changes a game bind; `F1` (full reset) restores the scripted binds.
- `/bind <name>` without a command prints what the key is currently bound to.

Rules and names verified against ET: Legacy source (`src/client/cl_keys.c` `keynames[]`, `Key_StringToKeynum`, `Key_KeynumToString`, `CL_KeyEvent`; `src/sdl/sdl_input.c` `IN_TranslateSDLToQ3Key`, `IN_IsConsoleKey`, `IN_ProcessEvents`). Other mods use the same engine key names (key handling is engine-side).

## How a key name is resolved

`bind <key> "<commands>"` resolves `<key>` in this order:

1. **Single character** → that character, lowercased (`bind Q` = `bind q`). On a US keyboard: `a`–`z`, `0`–`9`, `-`, `=`, `[`, `]`, `\`, `'`, `,`, `.`, `/`.
2. **4-char hex `0xNN`** → raw key number (e.g. `0x3b` = the `;` key, same as `SEMICOLON`).
3. **Name from the tables below**, case-insensitive (`kp_enter` = `KP_ENTER`).

A name existing does not mean a key can produce it: only keys listed in the tables (or produced as described below) ever trigger a bind.

`bindlist` prints keys back as: single char for printable ASCII 33–126 (except `"` and `;`), else the name, else `0xNN`.

## How a physical key becomes a key number

- The key's character **without modifiers** in the OS layout (SDL keycode) decides:
  - an **ASCII character** (32–126) → key = that character. So letter/symbol keys follow the **active keyboard layout**, not the physical position (German Z key → `z`).
  - a **non-ASCII character** (e.g. German `ö`, `ä`, `ü`, `ß`) → falls back to the **US physical position** → `US_*` name.
- **Key combinations have no key of their own.** Shift, AltGr, Ctrl and Alt are separate keys; Shift+0 is key `0` with `LEFTSHIFT` held. So a character that is only typed with a modifier can never trigger a bind: `bind "+"`, `bind #` or `bind <` do nothing on a US keyboard (Shift+`=`, Shift+`3`, Shift+`,`), and `bind =` / `bind }` do nothing on a German keyboard (Shift+0 / AltGr+0). The typed characters only reach chat/console input.
- **Console keys cannot be bound** (they are turned into the console key before binds are looked up, `CL_KeyEvent`):
  - `US_GRAVE` (the key left of 1, when its character is non-ASCII, e.g. German `^`) and Shift+Esc: hard-coded;
  - every key or typed character listed in `cl_consoleKeys` (default `"~ ` 0x7e 0x60"`), also when typed with a modifier (German AltGr++ = `~`).

## Keyboard (US ANSI)

| Physical key | Bind name |
|---|---|
| Esc | `ESCAPE` |
| F1 … F12 | `F1` … `F12` |
| Print Screen / Scroll Lock / Pause | `PRINT` / `SCROLLOCK` / `PAUSE` (the desktop may catch Print Screen) |
| `` ` `` / `~` (left of 1) | console key, **not bindable**: its character `` ` `` is in `cl_consoleKeys` |
| 1 … 0 | `1` … `0` |
| `-` / `=` | `-` / `=` |
| Backspace | `BACKSPACE` |
| Tab | `TAB` |
| Q … P, A … L, Z … M | `q` … `p`, `a` … `l`, `z` … `m` |
| `[` / `]` / `\` | `[` / `]` / `\` |
| Caps Lock | `CAPSLOCK` |
| `;` | `SEMICOLON` (a raw `;` would split the command) |
| `'` | `'` |
| Enter | `ENTER` |
| Shift (left / right) | `SHIFT` = `LEFTSHIFT` / `RIGHTSHIFT` |
| `,` / `.` / `/` | `,` / `.` / `/` |
| Ctrl (left / right) | `CTRL` = `LEFTCTRL` / `RIGHTCTRL` |
| Alt (left / right) | `ALT` = `LEFTALT` / `RIGHTALT` |
| Windows / Super (left and right) | `WINDOWS` (the desktop may catch it) |
| Context menu key | `COMPOSE` |
| Space | `SPACE` |
| Ins / Home / PgUp | `INS` / `HOME` / `PGUP` |
| Del / End / PgDn | `DEL` / `END` / `PGDN` |
| Arrow up / down / left / right | `UPARROW` / `DOWNARROW` / `LEFTARROW` / `RIGHTARROW` |

### Numpad

| Numpad key | Bind name |
|---|---|
| Num Lock | `KP_NUMLOCK` |
| `/` | `KP_SLASH` |
| `*` | `KP_STAR` |
| `-` | `KP_MINUS` |
| `+` | `KP_PLUS` |
| Enter | `KP_ENTER` |
| 7 (Home) | `KP_HOME` |
| 8 (Up) | `KP_UPARROW` |
| 9 (PgUp) | `KP_PGUP` |
| 4 (Left) | `KP_LEFTARROW` |
| 5 | `KP_5` |
| 6 (Right) | `KP_RIGHTARROW` |
| 1 (End) | `KP_END` |
| 2 (Down) | `KP_DOWNARROW` |
| 3 (PgDn) | `KP_PGDN` |
| 0 (Ins) | `KP_INS` |
| `.` (Del) | `KP_DEL` |

The numpad names are the same regardless of Num Lock (the chart's arrows show which arrow name belongs to which digit).

## German QWERTZ layout

Only keys that differ from the US table.

| German key (position) | Character | Bind name |
|---|---|---|
| `^` (left of 1, US `` ` `` position) | none (dead key\*) | `US_GRAVE` (tested): hard-coded console key, **not bindable** |
| `ß` (right of 0, US `-`) | non-ASCII | `US_MINUS` |
| `´` (right of ß, US `=`) | none (dead key\*) | `US_EQUALS` (bindable) |
| `ü` (right of P, US `[`) | non-ASCII | `US_LEFTBRACKET` |
| `+` (right of ü, US `]`) | `+` | `+` |
| `#` (left of Enter, US `\`) | `#` | `#` |
| `ö` (right of L, US `;`) | non-ASCII | `US_SEMICOLON` |
| `ä` (right of ö, US `'`) | non-ASCII | `US_APOSTROPHE` |
| `<` (between left Shift and Y; not on US ANSI) | `<` | `<` |
| `Z` (US Y position) | `z` | `z` |
| `Y` (US Z position) | `y` | `y` |
| `-` (US `/` position) | `-` | `-` |
| `,` / `.` | `,` / `.` | `,` / `.` |
| Pos1 / Ende | | `HOME` / `END` |
| Bild↑ / Bild↓ | | `PGUP` / `PGDN` |
| Einfg / Entf | | `INS` / `DEL` |
| Strg | | `CTRL` = `LEFTCTRL`, `RIGHTCTRL` |
| AltGr | | `MODE` (tested on a laptop keyboard: the desktop reports AltGr as a mode switch key); other keyboards/desktops may send `RIGHTALT` |
| Feststelltaste | | `CAPSLOCK` |
| Druck / Rollen | | `PRINT` / `SCROLLOCK` |
| Numpad `,` (Entf) | | `KP_DEL` |

- \*Dead key: a typing term. The key types nothing by itself and changes the next letter (`´` + `e` = `é`). For binds it counts as a key without an ASCII character, so it gets its US-position name like `ö`/`ä`/`ü`.
- Not bindable on German keyboards (only typed with a modifier): `=`, `}`, `{`, `[`, `]`, `\`, `~`, `` ` ``, `'`, `/`, `;`, `:`, `_`, `*`, `?`, `!`, `"`, `§`, `$`, `%`, `&`, `(`, `)`, `>`, `|`, `@`, `€`.
- Free keys close to WASD (per `default/binds_custom.cfg`): `t`, `z`, `x`, `CAPSLOCK`, `LEFTALT`.

## Mouse

From `IN_ProcessEvents` in `src/sdl/sdl_input.c`.

| Mouse input | Bind name |
|---|---|
| Left button | `MOUSE1` |
| Right button | `MOUSE2` |
| Middle button (wheel click) | `MOUSE3` |
| Side button back (X1) | `MOUSE4` |
| Side button forward (X2) | `MOUSE5` |
| SDL button 6 … 19 | `AUX3` … `AUX16` (`AUX1` + (button − 4) mod 16) |
| SDL button 20, 21, … | `AUX1`, `AUX2`, … (wraps around) |
| Wheel up | `MWHEELUP` |
| Wheel down | `MWHEELDOWN` |

- Wheel events send press and release in the same frame: a `+command` bound to the wheel is released immediately, so only instant commands (`weapnext`, `vstr ...`) make sense there.
- Horizontal wheel / wheel tilt is ignored (only `wheel.y` is read) — not bindable.
- `MOUSE6`+ names don't exist; use `AUX*` for extra buttons (check the actual name in Options → Controls, see top).

## Other names

Only produced by hardware or layouts that have these keys; on a standard US keyboard they never trigger. On a German keyboard the `US_*` names in the second row are used (see the German table), the rest never trigger.

| Device / key | Bind names |
|---|---|
| Number row when it types non-ASCII (e.g. AZERTY) | `US_0` … `US_9` |
| US-position symbol keys when they type non-ASCII | `US_MINUS`, `US_EQUALS`, `US_LEFTBRACKET`, `US_RIGHTBRACKET`, `US_BACKSLASH`, `US_SEMICOLON`, `US_APOSTROPHE`, `US_GRAVE`, `US_COMMA`, `US_PERIOD`, `US_SLASH` |
| ISO extra key (between left Shift and Z) when it types non-ASCII | `NONUSBACKSLASH` |
| Extra function keys | `F13` … `F15` |
| Special keys (only if the keyboard sends them) | `MODE` (German AltGr, see above), `HELP`, `SYSREQ`, `MENU`, `POWER`, `EURO`, `UNDO` |
| macOS Command key | `COMMAND` (instead of `WINDOWS`) |
| Joystick | `JOY1` … `JOY32` |
| Gamepad | `PAD0_A`, `PAD0_B`, `PAD0_X`, `PAD0_Y`, `PAD0_BACK`, `PAD0_GUIDE`, `PAD0_START`, `PAD0_LEFTSTICK_CLICK`, `PAD0_RIGHTSTICK_CLICK`, `PAD0_LEFTSHOULDER`, `PAD0_RIGHTSHOULDER`, `PAD0_DPAD_UP/DOWN/LEFT/RIGHT`, `PAD0_LEFTSTICK_LEFT/RIGHT/UP/DOWN`, `PAD0_RIGHTSTICK_LEFT/RIGHT/UP/DOWN`, `PAD0_LEFTTRIGGER`, `PAD0_RIGHTTRIGGER`, `PAD0_MISC1`, `PAD0_PADDLE1`–`PAD0_PADDLE4`, `PAD0_TOUCHPAD` |

Names that exist but no input ever produces (binding them does nothing): `KP_EQUALS` (no SDL keypad `=` mapping), `BREAK` (Pause always arrives as `PAUSE`).
