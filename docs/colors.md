# Color codes

Transcribed from two community charts (color names; index, hex, characters). Verified against
ET: Legacy source (`src/qcommon/q_math.c` `g_color_table[32]`, `src/qcommon/q_shared.h` `ColorIndex`, `Q_IsColorString`).

## Rules

- `^` + character colors the following text: `echo ^1red ^7white`.
- Color index = `(character - '0') & 31`, so every printable character maps to one of 32 colors. Upper and lower case letters are the same color (`^a` = `^A`).
- Not a color code: `^^` (escape followed by `^`), `^` followed by space or end of string.
- `^*` resets to the default text color in the legacy mod (console, HUD and cgame text drawing check `COLOR_NULL` before the table). Only the hex chart lists `*` as index 26 (raw table value).
- Use ASCII characters in ET: Legacy cfgs; the extended columns come from 8-bit (Latin-1) text and don't map cleanly to UTF-8 files.

## Table

"Name" = label from the color name chart (only for codes it lists); "source name" = comment in `g_color_table`.

| Index | Hex | Codes (ASCII) | Extended bytes (Latin-1) | Name (chart) | Source name |
|---:|---|---|---|---|---|
| 0 | `#000000` | `^0` `^P` `^p` | 0xB0 ° 0xD0 Ð 0xF0 ð | ^0 Black | black |
| 1 | `#ff0000` | `^1` `^Q` `^q` | 0xB1 ± 0xD1 Ñ 0xF1 ñ | ^1 Red | red |
| 2 | `#00ff00` | `^2` `^R` `^r` | 0xB2 ² 0xD2 Ò 0xF2 ò | ^2 Green | green |
| 3 | `#ffff00` | `^3` `^S` `^s` | 0xB3 ³ 0xD3 Ó 0xF3 ó | ^3 Yellow | yellow |
| 4 | `#0000ff` | `^4` `^T` `^t` | 0xB4 ´ 0xD4 Ô 0xF4 ô | ^4 Blue | blue |
| 5 | `#00ffff` | `^5` `^U` `^u` | 0xB5 µ 0xD5 Õ 0xF5 õ | ^5 Cyan, ^u Cyan | cyan |
| 6 | `#ff00ff` | `^6` `^V` `^v` | 0xB6 ¶ 0xD6 Ö 0xF6 ö | ^6 Pink | purple |
| 7 | `#ffffff` | `^7` `^W` `^w` | 0xB7 · 0xD7 × 0xF7 ÷ | ^7 White | white |
| 8 | `#ff7f00` | `^8` `^X` `^x` | 0xB8 ¸ 0xD8 Ø 0xF8 ø | ^8 Orange | orange |
| 9 | `#7f7f7f` | `^9` `^Y` `^y` | 0xB9 ¹ 0xD9 Ù 0xF9 ù | ^9 Grey | md.grey |
| 10 | `#bfbfbf` | `^:` `^Z` `^z` | 0xBA º 0xDA Ú 0xFA ú | ^z Orange (**wrong in the chart**, it is light grey) | lt.grey |
| 11 | `#bfbfbf` | `^;` `^[` `^{` | 0xBB » 0xDB Û 0xFB û | | lt.grey |
| 12 | `#007f00` | `^<` `^\` `^\|` | 0xBC ¼ 0xDC Ü 0xFC ü | ^< Green | md.green |
| 13 | `#7f7f00` | `^=` `^]` `^}` | 0xBD ½ 0xDD Ý 0xFD ý | | md.yellow |
| 14 | `#00007f` | `^>` `^~` (`^^` is no color) | 0xBE ¾ 0xDE Þ 0xFE þ | ^> Dark Blue | md.blue |
| 15 | `#7f0000` | `^?` `^_` | 0xBF ¿ 0xDF ß 0xFF ÿ | ^? Dark Brown | md.red |
| 16 | `#7f3f00` | `^@` `` ^` `` | 0xC0 À 0xE0 à | ^@ Brown | md.orange |
| 17 | `#ff9919` | `^!` `^A` `^a` | 0xA1 ¡ 0xC1 Á 0xE1 á | ^a Orange | lt.orange |
| 18 | `#007f7f` | `^"` `^B` `^b` | 0xA2 ¢ 0xC2 Â 0xE2 â | ^b Turquoise | md.cyan |
| 19 | `#7f007f` | `^#` `^C` `^c` | 0xA3 £ 0xC3 Ã 0xE3 ã | ^c Violet | md.purple |
| 20 | `#007fff` | `^$` `^D` `^d` | 0xA4 ¤ 0xC4 Ä 0xE4 ä | ^d Light Blue | |
| 21 | `#7f00ff` | `^%` `^E` `^e` | 0xA5 ¥ 0xC5 Å 0xE5 å | ^e Purple | |
| 22 | `#3399cc` | `^&` `^F` `^f` | 0xA6 ¦ 0xC6 Æ 0xE6 æ | ^f Lighter Blue | |
| 23 | `#ccffcc` | `^'` `^G` `^g` | 0xA7 § 0xC7 Ç 0xE7 ç | ^g Light Green | |
| 24 | `#006633` | `^(` `^H` `^h` | 0xA8 ¨ 0xC8 È 0xE8 è | ^h Dark Green | |
| 25 | `#ff0033` | `^)` `^I` `^i` | 0xA9 © 0xC9 É 0xE9 é | ^i Dark Red | |
| 26 | `#b21919` | `^J` `^j` (`^*` resets, see rules) | 0xAA ª 0xCA Ê 0xEA ê | ^j Claret, ^* Light Grey (**see rules**) | |
| 27 | `#993300` | `^+` `^K` `^k` | 0xAB « 0xCB Ë 0xEB ë | ^k Brown, ^+ Foxy Red | |
| 28 | `#cc9933` | `^,` `^L` `^l` | 0xAC ¬ 0xCC Ì 0xEC ì | ^l Light Brown | |
| 29 | `#999933` | `^-` `^M` `^m` | 0xAD (soft hyphen) 0xCD Í 0xED í | ^m Olive, ^- Olive | |
| 30 | `#ffffbf` | `^.` `^N` `^n` | 0xAE ® 0xCE Î 0xEE î | ^n Beige | |
| 31 | `#ffff7f` | `^/` `^O` `^o` | 0xAF ¯ 0xCF Ï 0xEF ï | ^o Beige, ^/ Beige | |

The hex chart renders some extended bytes with a Windows-1252/ISO-8859-15 font (e.g. Œ œ Ÿ Ž instead of ¼ ½ ¾ ´); the byte values above are what count.
