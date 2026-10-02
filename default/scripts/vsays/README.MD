# Messages
Details and color formats: `docs/commands.md` (legacy), `docs/commands_nitmod.md` (nitmod).

| Command | Sends to |
|---|---|
| `say <text>` | all |
| `say_team <text>` | team, with location |
| `say_teamnl <text>` | team, no location |
| `say_buddy <text>` | fireteam |
| `m` / `pm <name\|slot#> <text>` | one player; nitmod (`g_privateMessages`), elsewhere only via server Lua scripts |

Text max. 149 characters, a color code in the text overrides the default color.

# Voice Commands
| Command | Sends to |
|---|---|
| `vsay [<n>] <vsay> [<text>]` | all |
| `vsay_team [<n>] <vsay> [<text>]` | team |
| `vsay_buddy <class> <count> [<client> ...] [<n>] <vsay> [<text>]` | fireteam; `-1 0` = all classes, whole fireteam |
| `VoiceChat` / `VoiceTeamChat` / `VoiceFireTeamChat <vsay>` | same, only the vsay (no text, no variant); `VoiceFireTeamChat` = selected fireteam members |

- `<vsay>`: name from the lists below, case-insensitive; unknown names play nothing.
- `<text>`: replaces the vsay text, the sound still plays. nitmod: sent as normal chat line (shortcuts like `[S]` work), vsay plays only sound.
- `<n>`: variant number (0-based, see lists), else random; out of range = random. Legacy only, nitmod takes `<n>` as vsay name.
- Spectators: `say_buddy`/`vsay_buddy` refused; legacy also refuses `VoiceTeamChat`/`VoiceFireTeamChat`. Spam limit: about `g_voiceChatsAllowed` vsays per 30 s.

## Vsays
Legacy 2.86 (`scripts/wm_allies_chat.voice`, `wm_axis_chat.voice` in `legacy_v2.86.0.pk3`), grouped like the quick chat menu (`mp_QuickMessage`, team except Global). Several texts: variants by number. Axis `=`: same as Allies.

### Statements

`TakingFire`: only in the fireteam version of the menu.

| Vsay | Allies | Axis |
|---|---|---|
| `PathCleared` | Path cleared. | = |
| `EnemyWeak` | The enemy is weakened. | = |
| `AllClear` | All clear. | = |
| `Incoming` | Incoming! | = |
| `FireInTheHole` | Fire in the hole! | = |
| `OnDefense` | I'm on defense. | = |
| `OnOffense` | I'm on offense. | = |
| `TakingFire` | Taking fire! | = |
| `MinesCleared` | Mines cleared. | = |
| `EnemyDisguised` | Enemy in disguise. | = |

### Requests

| Vsay | Allies | Axis |
|---|---|---|
| `Medic` | 0: Need a Medic! / 1: I need a Medic! | Need a Medic! |
| `NeedAmmo` | I need ammo! | = |
| `NeedBackup` | I need backup! | = |
| `NeedEngineer` | We need an engineer! | = |
| `CoverMe` | 0: Covering fire! / 1: Covering fire! / 2: Cover me! / 3: Cover me! | 0: Need covering fire! / 1: Need covering fire! / 2: Cover me! / 3: Cover me! |
| `HoldFire` | Hold your fire! | = |
| `WhereTo` | Where to? | = |
| `NeedOps` | We need Covert Ops! | = |

### Commands

| Vsay | Allies | Axis |
|---|---|---|
| `FollowMe` | Follow me! | = |
| `LetsGo` | Let's go! | = |
| `Move` | Move! | = |
| `ClearPath` | Clear the path! | = |
| `DefendObjective` | Defend our objective! | = |
| `DisarmDynamite` | Disarm the dynamite! | = |
| `ClearMines` | Clear the mines! | = |
| `ReinforceOffense` | Reinforce the offense! | = |
| `ReinforceDefense` | Reinforce the defense! | = |

### Talk

| Vsay | Allies | Axis |
|---|---|---|
| `Affirmative` | 0: Affirmative! / 1: Yes! / 2: Yes! | 0: Ja! / 1: Jawohl! / 2: Affirmative!! |
| `Negative` | 0: No! / 1: No! / 2: Negative! / 3: Negative! | 0: Negative! / 1: Nein! / 2: Nein! |
| `Thanks` | 0: Thanks! / 1: Thanks! / 2: Thank you! / 3: Thank you! | 0: Danke! / 1: Danke! / 2: Danke sehr! |
| `Welcome` | 0: You're welcome. / 1: You're welcome. / 2: No problem. / 3: No problem. | 0: You're welcome. / 1: Bitte sehr. / 2: Kein problem. |
| `Sorry` | Sorry! | = |
| `Oops` | Oops! | = |

### Global

Global menu (`vsay`) also has `Affirmative`, `Negative`, `EnemyWeak`, `Thanks`, `Welcome`, `Oops`, `Sorry`, `HoldFire`.

| Vsay | Allies | Axis |
|---|---|---|
| `Hi` | 0: Hi! / 1: Hi! / 2: Hi! / 3: Hello! / 4: Hello! | Hallo! |
| `Bye` | 0: Bye. / 1: Bye. / 2: Bye. / 3: Good bye. / 4: Good bye. | Auf wiedersehen. |
| `GreatShot` | Great shot! | = |
| `Cheer` | 0: Hahaa! / 1: Alright! / 2: Yes! / 3: Yes! / 4: 'Atta way, baby! / 5: You got it, man! / 6: Yeehaa! / 7: Yoohoo! / 8: Yeah! / 9: Yeah! / 10: Yeah! / 11: Woo! | 0: Oh yes! / 1: Wunderbar! / 2: Excellent! / 3: Excellent! / 4: Jahaa! / 5: Sehr gut! / 6: Sehr gut! / 7: Wunderbar! |
| `GoodGame` | Good game! | = |

### Function

Menu sends only the vsay of your own class.

| Vsay | Allies | Axis |
|---|---|---|
| `IamSoldier` | I'm a soldier. | I'm a soldat. |
| `IamMedic` | I'm a medic. | = |
| `IamEngineer` | I'm an engineer. | = |
| `IamFieldOps` | I'm a field ops. | I'm a field op. |
| `IamCovertOps` | I'm a covert ops. | I'm a covert op. |

### Objectives

| Vsay | Allies | Axis |
|---|---|---|
| `CommandAcknowledged` | 0: Command acknowledged! / 1: Command acknowledged! / 2: Right away! / 3: Right away! | Command acknowledged! |
| `CommandDeclined` | 0: Command declined! / 1: Command declined! / 2: No can do! / 3: No can do! | Command declined! |
| `CommandCompleted` | Command completed! | = |
| `DestroyPrimary` | Destroy primary objective! | = |
| `DestroySecondary` | Destroy secondary objective! | = |
| `DestroyConstruction` | Destroy construction! | = |
| `ConstructionCommencing` | I'm constructing! | = |
| `RepairVehicle` | Repair the vehicle! | = |
| `DestroyVehicle` | Disable the vehicle! | = |
| `EscortVehicle` | Escort the vehicle! | = |

### Fireteam

Sent from the fireteam menu (`mp_fireteammsg`, pages per class). `FTCheckLandmines`: not in any menu.

| Vsay | Allies | Axis |
|---|---|---|
| `FTAttack` | Attack! | = |
| `FTFallBack` | Fall back! | = |
| `FTCoverMe` | Cover me! | = |
| `FTCoveringFire` | Covering fire! | = |
| `FTMortar` | Deploy mortar! | = |
| `FTHealSquad` | Heal the squad! | = |
| `FTHealMe` | Heal me! | = |
| `FTReviveTeamMate` | Revive team mate! | = |
| `FTReviveMe` | Revive me! | = |
| `FTDestroyObjective` | Destroy the objective! | = |
| `FTRepairObjective` | Repair objective! | = |
| `FTConstructObjective` | Construct objective! | = |
| `FTDisarmDynamite` | Disarm the dynamite! | = |
| `FTDeployLandmines` | Deploy landmines! | = |
| `FTDisarmLandmines` | Disarm landmines! | = |
| `FTCallAirStrike` | Call an airstrike! | = |
| `FTCallArtillery` | Call in artillery! | = |
| `FTResupplySquad` | Resupply the squad! | = |
| `FTResupplyMe` | Resupply me! | = |
| `FTExploreArea` | Explore the area! | = |
| `FTSatchelObjective` | Destroy the objective! | = |
| `FTInfiltrate` | Infiltrate! | = |
| `FTGoUndercover` | Go undercover! | = |
| `FTProvideSniperCover` | Provide sniper cover! | = |
| `FTCheckLandmines` | Check for landmines! | = |

# Shortcuts
Is supposed to work at jaymod, etpub, nitmod or noquarter

| Shortcut | Replaced by |
| --- | --- |
| `[A]` | Past person who gave you ammo |
| `[D]` | Last person who killed you |
| `[H]` | Last person who gave you health |
| `[K]` | Last person you killed |
| `[L]` | Your current location (Coordinates) |
| `[N]` | Your nickname |
| `[R]` | Last person who revived you |
| `[P]` | Teammate you are pointing at |
| `[S]` | Your health (HP) |
| `[T]` | Ammo you have in current weapon |
| `[W]` | Weapon you are currently holding |

A name shortcut (`[A]`, `[D]`, `[H]`, `[K]`, `[P]`, `[R]`) whose person is not known (nobody pointed at, nobody gave ammo yet, ...) becomes `*unknown*` (nitmod; tested in game with `[P]`).

## jaymod (probably)
Can be shown with `/textshortcuts` command

| Shortcut | Replaced by |
| --- | --- |
| `[B]` | Last teammate who inflicted damaged to you |
| `[C]` | The amount of damage that the last teammate inflicted to you |

## legacy (not merged)
https://github.com/etlegacy/etlegacy-lua-scripts/pull/17/commits/4b60d5b4c50223d902c2922d1dc2df8c51a4e257

| Shortcut | Replaced by |
| --- | --- |
| `[a]` | Name of the last player who gave ammo to the player |
| `[d]` | Name of the last player who killed the player |
| `[g]` | First 8 characters of player GUID (can be seen in `/players`) |
| `[h]` | Name of the last player who gave health to the player |
| `[k]` | Name of the last player killed by the player |
| `[l]` | Location of the player **(not implemented)** |
| `[n]` | Name of the player |
| `[r]` | Name of the last player who revived the player |
| `[p]` | Name of the last player the player looked at **(not implemented)** |
| `[s]` | Player remaining health |
| `[w]` | Player weapon |
| `[t]` | Player weapon ammo |
| `[c]` | Player class |
| `[o]` | Name of the player receiving the message |
