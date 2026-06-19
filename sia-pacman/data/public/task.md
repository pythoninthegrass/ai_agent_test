# Task: One-shot Pac-Man HTML generator

## Goal

Produce a `target_agent.py` that, when run, generates a single-file `pacman.html`
that passes all 14 automated Playwright checks.

**Score = checks_passed / 14.** A perfect score is 1.0 (14/14).

## What the target agent must do

`target_agent.py` receives two CLI arguments:
- `--dataset_dir <path>` — read-only; contains this `task.md` file.
- `--working_dir <path>` — read-write; write `pacman.html` here.

The agent must call an LLM endpoint with a prompt that instructs the model to write a
complete, single-file Pac-Man clone, then save the HTML to `working_dir/pacman.html`.

## The 14 automated checks (in order)

1. `HTML file exists and non-trivial` — file ≥ 4 KB.
2. `File starts with valid HTML` — `<!DOCTYPE html>` or `<html`.
3. `canvas element present` — `<canvas>` exists in the DOM.
4. `canvas width ≈ 560 px` — canvas bounding box width within 6 px of 560.
5. `canvas height ≥ 600 px` — canvas height at least 600 px.
6. `score element in DOM` — `#score`, `[id*="score"]`, `.score`, or `[class*="score"]` exists.
7. `score readable after 3 s` — the score element's text can be read (not null/empty).
8. `score > 0 after movement (dots eaten)` — after Enter + arrow key presses, score > 0.
9. `canvas has non-black pixels (rendered)` — > 500 non-black pixels in the canvas.
10. `game alive at 12 s (no crash)` — score element still readable 12 s after start.
11. `ghost state accessible (window.ghosts)` — `window.ghosts` is a non-empty array.
12. `all 4 ghosts released by 12 s` — all 4 ghosts have `inHouse: false` at 12 s.
13. `Pac-Man position/pixel coherent (no tunnel drift)` — `window.pac.px` within one tile
    of `window.pac.col * TILE + TILE/2`.
14. `zero console.assert / JS errors` — 0 Playwright console errors, 0 JS page errors.

## Common failure patterns (improve away from these)

- **Score stays 0**: MAP_TEMPLATE row 23 has a wall tile at index 14 (Pac-Man spawns in a
  wall), or dot tiles are coded as '6' (walkable but not scored), or the game loop crashes
  on frame 1 due to a JS error.
- **JS error — `Cannot set property col … only a getter`**: `Object.defineProperty` was
  used to add a getter-only `col` property to a ghost, but the code also does `g.col = …`.
  Use `Object.defineProperty` getters ONLY for `window.pac`; ghost `col`/`row` should be
  plain writable properties.
- **Ghosts never leave pen**: The `RELEASE` constant is referenced in a comment but the
  actual `if (RELEASE[g.name] && frameCount >= RELEASE[g.name] && g.inHouse) { … }` check
  is missing from the live game loop. It must be real executable code, not prose.
- **Game crashes on load**: `const CANVAS_W = canvas.width` before `const canvas = …`
  triggers Temporal Dead Zone error. Use `COLS * TILE` / `ROWS * TILE` instead.
- **Canvas null / TypeError on `setting 'width'`**: Canvas has no `id` or a mismatched
  `id`; JS does `getElementById('canvas')` while HTML has `id="c"`. Use `id="c"` and
  `getElementById('c')`.
- **MAP_TEMPLATE has 30 rows instead of 31**: `MAP[30]` is undefined; drawMap() crashes
  on the first frame. Guard every MAP loop: `if (!MAP[r]) continue;`.
- **Empty output from model**: The model occasionally returns an empty response. Retry the
  API call at least 3 times before giving up.

## LLM endpoint

- Base URL: `http://localhost:13305/api/v1` (lemonade server)
- Model: `Qwen3.6-35B-A3B-MTP-GGUF`
- API key: `os.environ["LEMONADE_API_KEY"]`
- Use the OpenAI Python client (`from openai import OpenAI`).
- Prepend `/think\n\n` to the user message to activate extended reasoning.

## Pac-Man specification (embed this in the prompt)

The following specification should be embedded verbatim as the user prompt sent to the
model (after the `/think\n\n` prefix). The model will generate the HTML based on this.

---

Build a complete, playable Pac-Man clone and write it to `pacman.html` in the current directory.

[MECHANICS] — implement exactly as specified:
- Grid: 28×31 tiles, 20 px each → canvas 560×620 px. The canvas element MUST have
  `id="c"` and explicit width/height attributes: `<canvas id="c" width="560" height="620">`.
  The JS MUST get it with `document.getElementById('c')`. A mismatch (e.g. `id="game"`
  in HTML but `getElementById('canvas')` in JS, or no id at all) returns null and throws
  `Cannot set properties of null (setting 'width')` — the canvas stays 300×150 and the
  script crashes on load.
- Entities move between tile centers. Direction changes only within 1 px of a tile center;
  snap to exact center on arrival before turning.
- Blinky starts outside the pen. Pinky/Inky/Clyde release at frames 200/400/600.
  Release check MUST use >= not ===: `if (frameCount >= 200 && ghost.inHouse)`.
  A skipped frame means === 200 never fires and the ghost stays penned forever.
  In-house ghosts bounce up/down. On release: set started=true, set inHouse=false,
  move to door, exit, then use normal AI. Do NOT gate movement on a flag never set true.
  CRITICAL: Release frames must be keyed by ghost NAME, not by array index.
  Blinky sits at index 0 in the array but is NOT in the house; if you use an array
  like `releaseFrames[i]` where i is the ghost's position in the full ghosts array,
  Blinky consumes slot 0 (200), Pinky gets slot 1 (400), Inky slot 2 (600), Clyde
  slot 3 (800) — Clyde exits at 13 s, after the 12 s test window. Instead key by
  name: `const RELEASE = {pinky:200, inky:400, clyde:600}`.
  The release check MUST be LIVE EXECUTABLE CODE inside `updateGhosts()` (or at the
  top of `updateInHouseGhost()`), not merely written in a comment or self-check prose.
  Exact pattern — this code must appear verbatim in the script body:
    if (RELEASE[g.name] && frameCount >= RELEASE[g.name] && g.inHouse) {
      g.inHouse = false;
      g.exiting = true;  // or begin exit-path logic here
    }
  Writing this only in a `/* SELF-CHECK */` comment does NOT satisfy the requirement.
- After initGhosts() (game start, restart, new level): reassign window.ghosts = ghosts
  and window.pac = pac so globals always reference the live objects.
- Initialize all variables before the game loop reads them. "SCORE: undefined" means
  the score variable was declared but not assigned a starting value (0).
- Initialize pac and ghosts BEFORE the first draw() call and before requestAnimationFrame().
  If pac is null when draw() runs, the game crashes immediately and the loop never starts.
  Call initPac() and initGhosts() at startup (before rAF), not only inside startGame().
- The animation loop MUST be bootstrapped with an explicit initial requestAnimationFrame(loop)
  call in the init/startup block. A self-recursive loop function never runs unless something
  calls it first. Forgetting the initial call leaves the game frozen on one static frame.
- window.pac MUST have col (int) and row (int) properties. Expose them as getters:
    Object.defineProperty(pac, 'col', { get: () => Math.floor(pac.px / TILE), enumerable: true });
    Object.defineProperty(pac, 'row', { get: () => Math.floor(pac.py / TILE), enumerable: true });
  A pac object without these properties fails automated testing even when window.pac is set.
  CRITICAL: Apply Object.defineProperty getters ONLY to window.pac. Do NOT apply
  Object.defineProperty to ghost col/row. Ghost tile position should be computed inline
  with Math.floor(g.px/TILE) or stored as a plain writable property — never as a getter.
  If you use Object.defineProperty to add a getter for g.col but also assign `g.col = ...`
  elsewhere, the assignment throws "Cannot set property col … which has only a getter",
  killing the game loop on the very first frame.
- Entity pixel position must start at the tile CENTER: col * TILE + TILE/2, NOT col * TILE.
  Starting at col * TILE places the entity at the tile corner; the nearCenter threshold
  never fires and dots are never eaten.
- Pac-Man's starting position is col=14, row=23. MAP_TEMPLATE[23] MUST be exactly:
    "1222222222222222222222222221"
  Do not change this row. Index 0 and 27 are '1' (wall); indices 1–26 are '2' (dot).
  A '6' tile is walkable but scores nothing; Pac-Man can move but eats no dots and
  score stays 0. A '1' tile at index 14 means Pac-Man spawns in a wall and can never
  move. Copy this exact string for row 23 — do not redesign it.
- Blinky's initial inHouse value MUST be false and started MUST be true. All other ghosts
  start with inHouse=true and started=false. Blinky must be able to navigate immediately.
- Use Math.floor(px / TILE) for pixel→tile conversion, NOT Math.round.
  Math.round(13.5) = 14 in JS, so an entity at the center of col=13 (px=270) maps to
  col=14 — the wrong tile. Math.floor(270/20) = 13, which is correct.
- Scatter→Chase cycle: 7 s / 20 s, lock to chase after 4 full cycles. Reverse all
  non-frightened, non-eaten ghosts exactly ONCE when the mode CHANGES (scatter→chase or
  chase→scatter). Do NOT reverse on every timer tick or every N frames — only on the
  actual transition frame.
- Ghost targets — Blinky: Pac tile. Pinky: 4 tiles ahead of Pac. Inky: reflect Blinky
  through 2 tiles ahead. Clyde: Pac tile if >8 away, else scatter corner.
  Frightened: random open direction each tile center. Eaten: house entrance.
- Tunnel row: crossing column −1 or COLS wraps BOTH px (pixel X) AND col (tile index)
  in the same step.
- Wall check: before applying any movement delta, verify the target tile is walkable
  via canMove(px, py, dir). Never move into a wall tile unconditionally. Direction is
  a string key ('left','right','up','down'); look up deltas as DIR[dir].dx not dir.dx.
  ALWAYS guard before applying movement: `if (!DIR[g.dir]) return;` — if `open[]`
  is empty (e.g., ghost stuck in a corner), `open[random]` is undefined, `g.dir`
  becomes undefined, and `DIR[undefined].dx` throws, killing the entire game loop.
  Defensive pattern:
    var dirs = getOpenDirs(g);
    if (dirs.length === 0) return;   // no valid move — skip this frame
    g.dir = dirs[Math.floor(Math.random() * dirs.length)];
    g.px += DIR[g.dir].dx; g.py += DIR[g.dir].dy;
- Do NOT invent undefined constants. To clear the canvas use `COLS * TILE` and
  `ROWS * TILE` (preferred) — these are already declared. If you use `canvas.width`/
  `canvas.height`, you MUST declare `const canvas = document.getElementById(...)` BEFORE
  any line that references `canvas`. A `const`/`let` declaration is in the temporal dead
  zone (TDZ) until its line executes: `const CANVAS_W = canvas.width` placed before
  `const canvas = ...` throws `Cannot access 'canvas' before initialization` and kills
  the entire script on load. Use `COLS * TILE` / `ROWS * TILE` everywhere to avoid the
  ordering problem entirely.
- MAP_TEMPLATE MUST have exactly ROWS (31) rows. Count them. A missing row means
  MAP[30] is undefined; any loop over `r < ROWS` crashes at r=30, killing the game
  loop on the very first frame — canvas shows one partial paint then freezes.
  Additionally, guard every MAP row access: `if (!MAP[r]) continue;` at the start of
  any loop body that reads MAP[r][c]. This prevents a single missing or undefined row
  from crashing the entire game loop.

[CONSTRAINTS]
- Single file, all CSS and JS inline, no external dependencies, works offline.
- Start and restart MUST respond to the Enter key. Automated tests press Enter, not Space.
  Accept both if you like, but Enter is required.
- Score MUST be displayed in a DOM element (not only on canvas). Use
  `<span id="score">0</span>` (or id="scoreVal" / class="score") and update it each
  frame with `scoreEl.textContent = score`. Automated tests query the DOM for the score
  element; a score drawn only via ctx.fillText is invisible to them.
- Expose these live objects on window for automated testing:
    window.ghosts — the live ghost array; each element must have:
                    name (string), inHouse (bool), started (bool),
                    col (int), row (int)
    window.pac   — the live Pac-Man object; must have:
                    col (int), row (int), px (float), py (float), dir (string)

[SELF-CHECK] — before finalizing, add a JavaScript block comment `/* SELF-CHECK ... */`
INSIDE the `<script>` block (NOT as an HTML `<!-- -->` comment, which causes a JS syntax
error when placed inside a script tag — `1. MAP_TEMPLATE` parses as `1.` number literal
followed by unexpected identifier). Verify each item in prose:
1. MAP_TEMPLATE[23][14] === '2' (dot, not '1' wall or '6' empty) — Pac-Man spawn has a dot.
2. Row 23 walkable corridor tiles (non-wall) are '2' not '6' — dots present for scoring.
3. initPac() and initGhosts() are called BEFORE requestAnimationFrame() and BEFORE draw().
4. Every ghost has an explicit code path that sets started=true and inHouse=false.
5. frameCount releases use >=, not ===.
6. window.pac and window.ghosts are reassigned after every initPac()/initGhosts() call.
7. draw() uses only declared constants (canvas.width/canvas.height or COLS*TILE/ROWS*TILE)
   to clear the canvas — no CANVAS_W, CANVAS_H, or other invented names.
8. MAP_TEMPLATE has exactly 31 strings (count them — literal count, not estimate).
   Every MAP loop body starts with `if (!MAP[r]) continue;` as a crash guard.
9. The RELEASE check (`if (RELEASE[g.name] && frameCount >= RELEASE[g.name] && g.inHouse)`)
   appears as LIVE CODE in updateGhosts() or updateInHouseGhost() — not only in a comment.
10. No Object.defineProperty with only a getter is applied to ghost col or row. If you use
    Object.defineProperty on ghosts at all, include a setter or use a plain assignment instead.

[DONE WHEN]
- All 4 ghosts leave the pen and navigate the board within 12 s; none stays frozen.
- A non-frightened ghost on Pac-Man's tile costs 1 life; 0 lives ends the game.
- A frightened ghost on Pac-Man's tile is eaten and routes back to the house.
- Left/right tunnel wrap updates the pixel position, not just the tile index.
- Eating all dots advances to the next level.
- Score and lives visible; game restarts after game over.
