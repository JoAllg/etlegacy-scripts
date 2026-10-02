# N!tmod differences (compared to plain legacy mod)

- **Alt-fire:** `+attack2` instead of `weapalt`
- **Spectator command:** `team s` instead of `team spectator`
- **Minimum FOV:** `cg_fov 90` (legacy allows 75)
- **Chat shortcuts for vsays:** `mod_general.cfg` additionally execs `scripts/vsays/chat_shortcuts.cfg`, which makes the voicechat pages load their texts with shortcuts (`scripts/vsays/chat/*_shortcuts.cfg`)
- **`cg_drawGun`:** values 0-7; 2-7 do not hide any weapon but draw all of them as transparent colored models (different color per value). Transparency and color are hardcoded in the pk3 shaders `textures/sfx/transgunWhite/Red/Green/Blue` (`scripts/nitrox.shader`, additive blend with a constant color), no cvar. Changing them would take an own pk3 overriding these shaders, which pure servers (`sv_pure 1`) don't load.
- **Popups:** `cg_numPopups` (max 8) and `cg_popupFadeTime` after a fixed 1500 ms stay time instead of the HUD component values; see `setPopupsMenu` in `mod_general.cfg`. Echo menus hold 8 lines, so the server menu uses its pages of 7 servers
- **Class commands:** different weapon IDs, see `mod_classcommands.cfg`
- **Weapon keys with fallback:** every `weaponbank` command starts `cg_weaponCycleDelay`, also one for a bank without ammo (`research/nitmod_2.3.5/decompiled/cgame_weaponswitch.c` `CG_WeaponBank_f`; legacy starts it only when the weapon changes, `src/cgame/cg_weapons.c` `CG_FinishWeaponChange`). `mod_general.cfg` therefore sets the delay to 0 and puts the fallback bank first (`bankPistolSelect`, `bankSMGSelect`); tested in game 2026-10-02. That form switches twice, so while pistol or SMG is in hand (a guess of the script) both keys run the plain command (`bankPistolPlain`, `bankSMGPlain`), which steps to the next weapon of the bank; tested in game 2026-10-02. Limits: comment there
