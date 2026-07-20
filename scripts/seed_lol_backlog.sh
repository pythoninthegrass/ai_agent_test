#!/usr/bin/env bash
# seed_lol_backlog.sh <target-dir>
# Git-init and seed a Backlog.md board in <target-dir> with the llmao MVP task list.
# All champion/item/map names are original clean-room analogues — no Riot IP.
# Backlog invoked via mise exec node so it works in non-login shells on mf.

set -euo pipefail

TARGET="${1:?Usage: $0 <target-dir>}"
cd "$TARGET"

BACKLOG="$HOME/.local/bin/mise exec node -- backlog"

# -- git init ----------------------------------------------------------------
if [ ! -d .git ]; then
  git init -b main
  git config user.name  "pythoninthegrass"
  git config user.email "lance@greyhaven.ai"
fi

# -- backlog init ------------------------------------------------------------
$BACKLOG init "llmao" --defaults --backlog-dir .backlog --no-git

# -- MVP tasks ---------------------------------------------------------------

$BACKLOG task create "Project scaffold: SvelteKit + PixiJS" \
  --type feature --priority High \
  -d "Bootstrap the llmao monorepo. Decide what 'llmao' stands for (branding/tagline). Set up SvelteKit for the shell (portal, lobby, room-join, shop) and install PixiJS as the in-game renderer. Configure Vite, TypeScript, and a WebSocket server entry point." \
  --ac "sveltekit dev server starts without errors" \
  --ac "pixi application initialises and renders a blank canvas on the game route" \
  --ac "project name and tagline appear on the landing page" \
  --plain

$BACKLOG task create "Portal: landing page and authentication stub" \
  --type feature --priority High \
  -d "Build the public-facing landing page: game title, tagline, play button. Add a lightweight username/session flow (no full OAuth required — a nickname + local session token is sufficient for the first build)." \
  --ac "visiting / renders the landing page with game name and tagline" \
  --ac "user can enter a nickname and proceed to the lobby" \
  --ac "session persists across page reloads (localStorage or cookie)" \
  --plain

$BACKLOG task create "Lobby: room creation and join-by-code" \
  --type feature --priority High \
  -d "Build the multiplayer lobby. A host creates a room and receives a short alphanumeric room code. Others enter the code to join the same room. List connected players. Provide a 'Start Game' button visible to the host once at least 2 players are present. Authoritative WebSocket server handles room state." \
  --ac "host can create a room and see a room code" \
  --ac "second player can join the room by entering the code" \
  --ac "both players see each other in the player list" \
  --ac "host can start the game; all clients transition to the game view" \
  --plain

$BACKLOG task create "Game map: 3-lane arena with jungle" \
  --type feature --priority High \
  -d "Render the classic 3-lane MOBA map in PixiJS. Three lanes (top, mid, bot) connect two bases. The jungle between lanes contains three camp types: shades (wraith analogue), pack-wolves (wolf analogue), and stone-golems (golem analogue). Include baron-equivalent and dragon-equivalent objective pits. Bases contain a Nexus structure. Use tile-based or polygon collision for walls/terrain." \
  --ac "map renders in the PixiJS canvas with three visible lanes" \
  --ac "jungle contains three distinct camp spawn points" \
  --ac "two base structures (one per team) with nexus visuals are present" \
  --ac "baron and dragon pit locations are marked on the map" \
  --plain

$BACKLOG task create "Champion framework: base entity system" \
  --type feature --priority High \
  -d "Implement the base champion entity: stats (HP, mana, AD, AP, armor, MR, move speed, attack range, attack speed), passive, four abilities (Q/W/E/R) with cooldowns and mana costs, basic autoattack, level-up (1–18) with stat growth, and XP gain from kills/minions. Abilities are stubs — concrete kits are added in champion tasks." \
  --ac "a champion entity can be instantiated with a stat block and ability stubs" \
  --ac "autoattack fires projectile toward target and deals AD damage" \
  --ac "leveling up increments stats per the stat-growth config" \
  --ac "ability slots have cooldown timers that tick down each frame" \
  --plain

$BACKLOG task create "Champion: Ironclad (tank/bruiser top — Garen analogue)" \
  --type feature --priority Medium \
  -d "Implement Ironclad: a melee tank/bruiser for the top lane. Classic Season 2/3 archetype — durable, straightforward, high base damage. Kit: passive (HP regen out-of-combat), Q (silence + speed burst), W (damage reduction shield), E (spin dealing AoE physical damage), R (execute on low-HP targets). Mirror the Garen/top-bruiser feel from 2010-2013." \
  --ac "Ironclad can be selected and spawns on the map" \
  --ac "all four abilities are functional with correct cooldowns and mana costs" \
  --ac "R only triggers the execute effect below 25% target HP" \
  --plain

$BACKLOG task create "Champion: Hex (AP burst mid — Lux/Annie analogue)" \
  --type feature --priority Medium \
  -d "Implement Hex: a ranged AP mage for the mid lane. Classic 2009-2013 glass-cannon AP archetype — high burst, skill-shot reliant, squishy. Kit: passive (ability mark for bonus magic damage), Q (root skill-shot), W (shield), E (AoE slow zone), R (long-range laser/beam ult). Mirror the Lux/Annie feel." \
  --ac "Hex can be selected and spawns on the map" \
  --ac "Q root skill-shot requires aim and travels as a projectile" \
  --ac "R fires a long-range beam dealing burst magic damage" \
  --plain

$BACKLOG task create "Champion: Bolt (ADC crit carry — Ashe/Caitlyn analogue)" \
  --type feature --priority Medium \
  -d "Implement Bolt: a ranged ADC for the bot lane. Classic Season 2/3 crit-carry archetype — scales hard with crit items, low base damage. Kit: passive (crit on first attack after standing still), Q (empowered attack with slow), W (volley fan of arrows), E (escape/reposition dash), R (global skill-shot stun). Mirror the Ashe/Caitlyn crit-ADC feel." \
  --ac "Bolt can be selected and spawns on the map" \
  --ac "passive crit only activates after standing still for 1.5s" \
  --ac "R travels globally and stuns the first champion hit" \
  --plain

$BACKLOG task create "Champion: Warden (enchanter/tank support — Soraka/Taric analogue)" \
  --type feature --priority Medium \
  -d "Implement Warden: a melee support/tank for the bot lane. Classic Season 2/3 peel/heal support archetype. Kit: passive (nearby allies gain bonus armor), Q (targeted heal), W (AoE taunt/stun), E (shield on ally), R (global heal on all allied champions). Mirror the Soraka/Taric support feel." \
  --ac "Warden can be selected and spawns on the map" \
  --ac "R applies a heal to all living allied champions regardless of distance" \
  --ac "W forces nearby enemies to attack Warden for 1.5s" \
  --plain

$BACKLOG task create "Champion: Shade (ganking jungler — Shaco/Nocturne analogue)" \
  --type feature --priority Medium \
  -d "Implement Shade: a mobile assassin jungler. Classic Season 2/3 gank-heavy jungler archetype. Kit: passive (bonus damage from behind), Q (blink to a target location leaving a decoy), W (fear on-hit), E (damage trap), R (global dash to target champion). Mirror the Shaco/Nocturne gank-assassin feel." \
  --ac "Shade can be selected and spawns on the map" \
  --ac "Q blink places a visible decoy at the origin for 3s" \
  --ac "R can target any visible enemy champion on the map" \
  --plain

$BACKLOG task create "Item shop: classic item archetypes" \
  --type feature --priority High \
  -d "Implement the in-game item shop UI (SvelteKit panel over the PixiJS canvas) and the following classic Season 3-inspired items (original names, no Riot IP): Titan's Plate (huge HP, +800 HP — Warmog's analogue), Thorn Buckle (crit+armor synergy, +40 armor +15% crit — Atma's analogue), Frozen Grip (HP+slow on-hit, +500 HP +25 AD — Frozen Mallet analogue), Shredder's Edge (armor reduction stacks, +55 AD +10 ArPen — Black Cleaver analogue), Swift Strike (AS+crit+MS, +25% AS +20% crit +5% MS — Phantom Dancer analogue), Sage's Stone (HP/mana regen, +10 HP/5s +7 MP/5s — Philosopher's Stone analogue), Gold Sigil (HP regen + gold income, +150 HP +3 gold/10s — Heart of Gold analogue). Purchases deduct gold; stats apply to champion immediately." \
  --ac "shop UI opens/closes with a keybind during a game session" \
  --ac "purchasing an item deducts its gold cost from the player's total" \
  --ac "item stats are reflected in the champion's stat block on purchase" \
  --ac "all seven items are purchasable with correct costs and stats" \
  --plain

$BACKLOG task create "Minions, turrets, gold, and win condition" \
  --type feature --priority High \
  -d "Implement lane minion waves (melee and ranged minions spawning from each base every 30s), turrets on each lane (outer/inner/inhibitor/nexus turrets), last-hit gold, and the win condition (destroy the enemy Nexus). Five-role assignment in the lobby (top/jungle/mid/ADC/support). Minions and turrets attack the nearest valid target automatically." \
  --ac "minion waves spawn from both bases every 30s and march down all three lanes" \
  --ac "last-hitting a minion grants gold to the killing player" \
  --ac "turrets attack the nearest enemy champion or minion within range" \
  --ac "destroying the enemy Nexus ends the game and shows a victory screen" \
  --ac "lobby role selection assigns each player one of the five roles" \
  --plain

$BACKLOG task create "Runes and Masteries: simplified classic pages" \
  --type feature --priority Low \
  -d "Implement a simplified classic rune/mastery page system in the pre-game lobby. Each player selects one of three preset rune pages (Offense: +AD/AP; Defense: +armor/MR/HP; Utility: +gold/CDR/mana) and one of three preset mastery trees (Offense/Defense/Utility). Stats from the selected pages apply to the champion at game start. No per-rune customisation needed — preset pages only." \
  --ac "rune/mastery page selection appears in the pre-game lobby before champion select" \
  --ac "selecting an offense page grants visible stat bonuses to the champion" \
  --ac "stats from both rune and mastery pages are combined and applied at game start" \
  --plain

$BACKLOG task create "Project cleanup: stop servers and finalize build" \
  --type chore --priority High \
  -d "Final task: stop all dev servers and background node processes, verify all tasks are Done, and leave the repo in a clean committed state." \
  --ac "no vite or node dev-server processes are running" \
  --ac "all backlog tasks are in Done status" \
  --ac "git status shows a clean working tree" \
  --dod "kill any process listening on ports 5173 or 6420 before marking Done" \
  --plain


echo ""
echo "=== llmao backlog seeded in $TARGET ==="
$BACKLOG board --plain 2>/dev/null || true
