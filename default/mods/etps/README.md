# etps differences (compared to plain legacy mod)

etps is a server mod built on legacy 2.84 (its cgame reports `v2.84.0-552`). Everything not listed here works as in legacy: `team spectator`, minimum FOV 75, map/team autoexecs (`CG_MapAutoexec` in its cgame).

- **Alt-fire:** `+attack2` instead of `weapalt`; its cgame rebinds `weapalt` binds to `+attack2` on start (string `Migrated %i legacy weapalt bind%s to +attack2`), tested in game 2026-10-03
- **Popups:** legacy's `editcomponent popupmessages` plus the cvar `cg_numPopups` (max 8), which caps the lines; `setPopupsMenu` in `mod_general.cfg` sets 8 for the echo menus, `setPopupsNormal` restores `numPopupsNormal` (`cvars.cfg`). Echo menus hold 8 lines, so the server menu uses its pages of 7 servers
- **Chat shortcuts for vsays:** the server expands `[H]`, `[P]`, ... in chat (tested in game 2026-10-03 with `say_team`), so `mod_general.cfg` execs `scripts/vsays/chat_shortcuts.cfg` like nitmod
- **HUD file:** the cgame of 2.84 reads `profiles/<cl_profile>/hud.dat` (HUD JSON version 4, upgraded to 7 in memory), not `huds/hud_v8.dat` (`.claude/rules/hud.md`)
- **Class commands:** legacy weapon IDs up to 55, plus its own weapons 56 Shotgun, 57 Venom, 58 BAR, 59 StG44, 60 Johnson. `mod_classcommands.cfg` appends them as class steps to the cycles and gives the soldier a pistol as second weapon (bank 3 holds two weapons, an SMG would be a third). Every class gets its chosen SMG plus the other team's counterpart in bank 3 (seen in game, 2026-10-05; pairs from `weapEquiv` of the cgame weapon table: MP40/Thompson, StG44/BAR, Sten/MP34, Johnson → MP34), so the class echoes name both with their range

## Weapons

**As of 2026-10-05**, from the cgame in `zzz_etps_2~.pk3` (pack built 2026-10-04). etps changes its packs often, so recheck after a new pack download.

Source: the weapon table (`weaponTable`, layout of legacy 2.84 `weaponTable_t`) in the cgame. No pack has `psweapons/*.weap` server tuning files (which the cgame would read for prediction), so the table values apply. Damage is server-side only and the etps server module is not available, so damage values are unverified.

Units: times in ms, heat = ms of continuous fire until overheat, cooling per second, spread = base / scale (growth by moving and turning), recoil = duration / pitch kick. Damage per second = damage × 1000 / next shot. Heat (legacy 2.84 `src/game/bg_pmove.c`, `PM_Weapon`, `PM_CoolWeapons`): each shot adds its next shot time to the heat, cooling runs all the time (also while firing); bursts below are computed from that. Who gets which weapon: class steps in `mod_classcommands.cfg`.

### etps weapons

| | Shotgun 56 | Venom 57 | BAR 58 | StG44 59 | Johnson 60 |
|---|---|---|---|---|---|
| Damage | 24 per pellet (pellet count unknown) | 20 | 19 | 19 | 14 |
| Spread | 850 / 0.6 | 1000 / 2.0 | 600 / 0.9 | 200 / 0.6 | 200 / 0.6 |
| Spread per shot | 20 | 10 | 15 | 20 | 15 |
| Next shot | 850 | 45, 750 spin-up | 150 | 180 | 150 |
| Damage per second | ~28 per pellet | ~444 | ~127 | ~106 | ~93 |
| Clip / max ammo | 6 / 24 | 250 / 500 | 20 / 80 | 30 / 90 | 32 / 96 |
| Reload | 1500 | 3000 | 2000 | 2400 | 3100 |
| Heat | none | 2500, cools 200, 2000 lockout (~70 shots / 3.1 s burst) | none | none | 1200, cools 540, 2000 lockout |
| Recoil | none | 80 / 0.40 | 25 / 0.10 | 20 / 0.15 | none |
| Attributes | damage falloff, no fast reload | damage falloff | fast reload, falloff | fast reload, falloff | silenced, keeps the covert ops disguise |

### Sten, MP34, Johnson

Same table values, only model, sound and team differ: damage 14, spread 200 / 0.6 (+15 per shot), next shot 150 (~93 damage per second), clip 32 / max ammo 96, reload 3100, heat 1200, cools 540, 2000 lockout. A burst overheats after ~17 shots / 2.4 s, so a clip never empties in one burst; full heat cools down in 2.2 s. Sten: covert ops of both teams; MP34: Axis covert ops, engineer, field ops; Johnson: Allied covert ops.

### SMG alternatives

StG44: Axis soldier, medic, covert ops; BAR: every Allied class; MP34: Axis engineer, field ops. A pick brings the other team's counterpart too (MP40 with Thompson, StG44 with BAR), so a StG44 or BAR pick holds one weapon for range and one for close range.

| | MP40 / Thompson | StG44 | BAR | MP34 |
|---|---|---|---|---|
| Damage | 18 | 19 | 19 | 14 |
| Spread | 400 / 0.6, +15 | 200 / 0.6, +20 | 600 / 0.9, +15 | 200 / 0.6, +15 |
| Next shot | 150 | 180 | 150 | 150 |
| Damage per second | ~120 | ~106 | ~127 | ~93 |
| Clip / max ammo | 30 / 90 | 30 / 90 | 20 / 80 | 32 / 96 |
| Damage per clip | 540 | 570 | 380 | 448 (~240 per burst, heat) |
| Time to empty clip | 4.4 s | 5.2 s | 2.9 s | overheats first |
| Reload | 2400 | 2400 | 2000 | 3100 |
| Recoil | none | 20 / 0.15 | 25 / 0.10 | none |
| Hits for 100 damage | 6 | 6 | 6 | 8 |

- **BAR:** highest damage per second, but 1.5× the spread of the MP40 and more growth by moving; small clip, fastest reload: close range, standing
- **MP40 / Thompson:** all-rounder
- **StG44:** half the spread of the MP40, same hits to kill, 12 % less damage per second and slight recoil: better at range, worse up close
- **MP34:** weakest choice for Axis engineer and field ops; only accuracy and silence over the MP40
