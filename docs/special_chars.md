# Special characters (ET font character map)

Transcribed from a character map image from an ETpro scripts pk3. Each cell shows `=<hex byte>` and the glyph the classic 8-bit ET font draws for that byte. The image does not explain the `=xx` notation or the small red markers.

Applicability:
- Classic mods (etpro, etpub, jaymod, …) draw text as 8-bit bytes → this table applies (unverified per mod).
- ET: Legacy decodes text as UTF-8 (`Q_UTF8_*` in `cl_console.c`, `cl_scrn.c`, `cg_drawtools.c`) → write the real Unicode character in a UTF-8 cfg instead of a raw byte. Whether the legacy font has a glyph for it is unverified.
- `0x5E` (`^`) starts a color code, see `colors.md`.

## Printable ASCII (0x20–0x7E)

Standard ASCII glyphs. `0x20` is space, `0x7F` is a special glyph (see below).

| | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | A | B | C | D | E | F |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0x2_ | space | ! | " | # | $ | % | & | ' | ( | ) | * | + | , | - | . | / |
| 0x3_ | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | : | ; | < | = | > | ? |
| 0x4_ | @ | A | B | C | D | E | F | G | H | I | J | K | L | M | N | O |
| 0x5_ | P | Q | R | S | T | U | V | W | X | Y | Z | [ | \ | ] | ^ | _ |
| 0x6_ | ` | a | b | c | d | e | f | g | h | i | j | k | l | m | n | o |
| 0x7_ | p | q | r | s | t | u | v | w | x | y | z | { | \| | } | ~ | (glyph) |

## Latin-1 (0xA0–0xFF)

Matches ISO-8859-1.

| | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | A | B | C | D | E | F |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0xA_ | (blank) | ¡ | ¢ | £ | ¤ | ¥ | ¦ | § | ¨ | © | ª | « | ¬ | (soft hyphen) | ® | ¯ |
| 0xB_ | ° | ± | ² | ³ | ´ | µ | ¶ | · | ¸ | ¹ | º | » | ¼ | ½ | ¾ | ¿ |
| 0xC_ | À | Á | Â | Ã | Ä | Å | Æ | Ç | È | É | Ê | Ë | Ì | Í | Î | Ï |
| 0xD_ | Ð | Ñ | Ò | Ó | Ô | Õ | Ö | × | Ø | Ù | Ú | Û | Ü | Ý | Þ | ß |
| 0xE_ | à | á | â | ã | ä | å | æ | ç | è | é | ê | ë | ì | í | î | ï |
| 0xF_ | ð | ñ | ò | ó | ô | õ | ö | ÷ | ø | ù | ú | û | ü | ý | þ | ÿ |

## Special glyphs (0x00–0x1F, 0x7F–0x9F)

ET-specific box/symbol glyphs. Descriptions are approximate (low-resolution image); every cell in these ranges carries a red marker.

| Byte | Glyph (approx.) |
|---|---|
| 0x00 | small dot |
| 0x01–0x09 | filled blocks/bars of varying width |
| 0x0A | dot (bottom) |
| 0x0B | tall hollow block |
| 0x0C | dark block |
| 0x0D | dot (bottom) |
| 0x0E, 0x0F | small dot (middle) |
| 0x10 / 0x11 | `[` / `]` |
| 0x12 / 0x13 / 0x14 | box corner top-left ┌ / top bar ▔ / corner top-right ┐ |
| 0x15 | vertical bar │ |
| 0x16 | dark block |
| 0x17 | vertical bar │ |
| 0x18 / 0x19 | corner bottom-left └ / bottom bar ▁ |
| 0x1A | corner bottom-right ┘ |
| 0x1B | top bar ▔ |
| 0x1C | small dot |
| 0x1D | left half-disc ◖ |
| 0x1E | small square ■ |
| 0x1F | right half-disc ◗ |
| 0x7F | left arrow ← |
| 0x80 | left bracket/half-circle `(` |
| 0x81 | double bar `=` |
| 0x82 | right bracket/half-circle `)` |
| 0x83 | vertical bar ▌ |
| 0x84 | dark block |
| 0x85 | dot |
| 0x86 / 0x87 | triangle down ▼ / triangle up ▲ |
| 0x88 | triangle left ◀ |
| 0x89, 0x8A | dark block |
| 0x8B | hollow block ▯ |
| 0x8C | dark block |
| 0x8D | triangle right ▶ |
| 0x8E, 0x8F | dot |
| 0x90 / 0x91 | `[` / `]` |
| 0x92–0x9A | digits `0`–`8` (small, boxed style) |
| 0x9B | top bar ▔ |
| 0x9C | small dot |
| 0x9D–0x9F | dark block |

0x5F (`_`) is drawn as a dark block in the image.
