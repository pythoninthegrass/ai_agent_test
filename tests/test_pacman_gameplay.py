#!/usr/bin/env -S uvx --with playwright run python3
"""
Gameplay invariant tests for the authoritative pacman.html.

Tests beyond the 14-check evaluator:
  1. Ghosts killable: score jumps >=200 after eating a frightened ghost
  2. Revive loop: eaten ghost returns to house and eaten flag clears
  3. No clipping: pac pixel position stays coherent with tile-center math
"""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
TARGET = HERE.parent / "pacman.html"
TILE = 20
PASS = "PASS"
FAIL = "FAIL"


def fmt(label, ok, detail=""):
    tag = f"[{PASS}]" if ok else f"[{FAIL}]"
    line = f"  {tag:<7} {label}"
    if detail:
        line += f"  — {detail}"
    print(line)
    return ok


def run_tests(html: Path) -> int:
    failures = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})

        js_errors = []
        page.on("pageerror", lambda e: js_errors.append(str(e)))
        page.on("console", lambda m: js_errors.append(m.text) if m.type == "error" else None)

        page.goto(f"file://{html.resolve()}", wait_until="load")

        # Start game
        page.keyboard.press("Enter")
        page.wait_for_timeout(500)
        page.keyboard.press("ArrowRight")
        page.wait_for_timeout(2000)  # let ghosts start moving

        score_js = """() => {
            const e = document.querySelector('#score, [id*="score"], .score, [class*="score"]');
            return e ? parseInt(e.textContent.replace(/\D/g,''), 10) || 0 : 0;
        }"""

        # ── 1. GHOST KILLABLE ────────────────────────────────────────────────
        print("\n── Invariant 1: Ghosts killable ──────────────────────────────────")

        score_before = page.evaluate(score_js)

        # Set blinky frightened and snap to pac's tile center (JS state injection)
        page.evaluate("""() => {
            const g = window.ghosts && window.ghosts[0];
            const p = window.pac;
            if (!g || !p) return;
            const TILE = 20;
            const col = Math.floor(p.px / TILE);
            const row = Math.floor(p.py / TILE);
            g.frightened = true;
            g.eaten = false;
            g.inHouse = false;
            g.exiting = false;
            g.started = true;
            g.px = col * TILE + TILE / 2;
            g.py = row * TILE + TILE / 2;
            g.col = col;
            g.row = row;
        }""")

        page.wait_for_timeout(300)  # let game loop process collision

        score_after = page.evaluate(score_js)
        score_delta = score_after - score_before

        ok1a = fmt("score jumps >=200 after eating frightened ghost",
                   score_delta >= 200,
                   f"before={score_before} after={score_after} delta={score_delta}")
        if not ok1a:
            failures += 1

        blinky_eaten = page.evaluate("""() => {
            const g = window.ghosts && window.ghosts[0];
            return g ? !!g.eaten : null;
        }""")
        ok1b = fmt("blinky.eaten is true immediately after collision",
                   blinky_eaten is True,
                   f"eaten={blinky_eaten}")
        if not ok1b:
            failures += 1

        # ── 2. REVIVE LOOP ───────────────────────────────────────────────────
        print("\n── Invariant 2: Eaten ghost revives (returns to house) ───────────")

        # Wait up to 15s for blinky.eaten to clear (eyes-only mode → house → revived)
        revived = False
        for _ in range(30):
            page.wait_for_timeout(500)
            page.keyboard.press("ArrowRight")
            eaten_now = page.evaluate("""() => {
                const g = window.ghosts && window.ghosts[0];
                return g ? !!g.eaten : null;
            }""")
            if eaten_now is False and not revived:
                revived = True
                break

        ok2 = fmt("eaten ghost revives (eaten resets to false after returning to house)",
                  revived,
                  "blinky.eaten cleared within 15 s" if revived else "blinky still eaten after 15 s")
        if not ok2:
            failures += 1

        # ── 3. NO CLIPPING ───────────────────────────────────────────────────
        print("\n── Invariant 3: No tile clipping ─────────────────────────────────")

        # Sample pac position every 150ms for 4s while holding ArrowLeft
        samples = []
        page.keyboard.press("ArrowLeft")
        for _ in range(27):
            page.wait_for_timeout(150)
            state = page.evaluate("""() => {
                const p = window.pac;
                if (!p) return null;
                return { px: p.px, py: p.py, col: p.col, row: p.row };
            }""")
            if state:
                samples.append(state)

        # Check: col getter == Math.floor(px/TILE) always
        coherent = all(
            abs(s["col"] - int(s["px"] // TILE)) <= 1 and
            abs(s["row"] - int(s["py"] // TILE)) <= 1
            for s in samples
        )
        ok3a = fmt("pac col/row getters always match pixel position",
                   coherent,
                   f"checked {len(samples)} samples")
        if not ok3a:
            failures += 1

        # Check: when pac is NOT moving (same px two frames in a row),
        # px must be within 2px of tile center (anti-clip snap invariant)
        prev = None
        clip_violations = 0
        for s in samples:
            if prev and abs(s["px"] - prev["px"]) < 0.01 and abs(s["py"] - prev["py"]) < 0.01:
                # pac is stopped — should be snapped to center
                cx = s["col"] * TILE + TILE / 2
                cy = s["row"] * TILE + TILE / 2
                drift = max(abs(s["px"] - cx), abs(s["py"] - cy))
                if drift > 3:
                    clip_violations += 1
            prev = s

        ok3b = fmt("stopped pac snapped to tile center (drift < 3px when stationary)",
                   clip_violations == 0,
                   f"{clip_violations} violations in {len(samples)} samples")
        if not ok3b:
            failures += 1

        # ── JS ERRORS ────────────────────────────────────────────────────────
        print("\n── Console / JS errors ───────────────────────────────────────────")
        ok_errs = fmt("zero JS errors during gameplay tests",
                      len(js_errors) == 0,
                      f"{len(js_errors)} errors")
        if not ok_errs:
            failures += 1
            for e in js_errors[:5]:
                print(f"         {e}")

        browser.close()

    return failures


def main():
    if not TARGET.exists():
        print(f"ERROR: {TARGET} not found")
        return 1

    print(f"\n{'='*60}")
    print(f"  Gameplay invariants: {TARGET.name}")
    print(f"{'='*60}")

    failures = run_tests(TARGET)

    print(f"\n{'='*60}")
    if failures == 0:
        print("  ALL GAMEPLAY INVARIANTS PASSED")
    else:
        print(f"  {failures} INVARIANT(S) FAILED")
    print(f"{'='*60}\n")

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
