# Sample task descriptions — Pac-Man browser game generator

These are representative descriptions of analogous "generate a self-contained browser
game scored by automated Playwright checks" tasks. They are provided so the Meta-Agent
understands the problem class and can draw on similar improvement strategies.

---

## Breakout clone

Generate a single-file HTML5 Breakout clone that:
- Renders a paddle, ball, and brick grid on a `<canvas>` element.
- Keeps score in a DOM element (not canvas text).
- Passes a ball-through-bricks collision test within 10 s.
- Responds to ArrowLeft/ArrowRight without any JS errors.
Score = checks passed / total checks.

---

## Snake game

Generate a single-file HTML5 Snake game that:
- Moves the snake on a grid each frame; snake grows on eating food.
- Displays score in a `<span id="score">` element updated each frame.
- Ends the game (renders a game-over state) on wall or self-collision.
- Exposes `window.snake` (array of {x, y} segments) for automated state inspection.
Score = checks passed / total checks.

---

## Pac-Man clone (this task)

Generate a single-file HTML5 Pac-Man clone. All 14 automated Playwright checks must
pass within 12 seconds of the game starting (Enter key pressed by the test harness).
Score = checks passed / 14.
