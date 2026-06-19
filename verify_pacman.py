#!/usr/bin/env -S uvx --with playwright run python3
"""
Playwright smoke-test for generated pacman.html files.

Checks per file:
  - Page loads, canvas exists at correct dimensions
  - Game starts on Enter, score element present
  - Canvas renders non-trivial pixel data
  - Score increments (Pac-Man eats dots under autonomous key presses)
  - Game survives 12 seconds without crashing (ghost-release window)
  - Ghosts are outside the house by 12 s (JS state inspection)
  - Pac-Man position and pixel position stay coherent (no tunnel drift)
  - Zero console.assert failures (our INVARIANT_CHECK block)
  - Screenshots saved alongside the HTML
"""

import re
import sys
from pathlib import Path

from playwright.sync_api import ConsoleMessage, sync_playwright


def _parse_score(text: str | None) -> int | None:
    """Extract first integer from a score element's text content."""
    if text is None:
        return None
    m = re.search(r"\d+", text)
    return int(m.group()) if m else None

HERE = Path(__file__).resolve().parent

try:
    TARGETS = {
        "pi": sorted((HERE / "artifacts" / "pi").glob("*/pacman.html"))[-1],
        "hermes": sorted((HERE / "artifacts" / "hermes").glob("*/pacman.html"), key=lambda p: p.parent.name)[-1],
    }
except (IndexError, StopIteration):
    TARGETS = {}


def check(results, label, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    tag = f"[{status}]"
    line = f"  {tag:<7} {label}"
    if detail:
        line += f"  — {detail}"
    print(line)
    results.append((label, cond))


def verify(name: str, html: Path, browser) -> list[tuple[str, bool]]:
    results: list[tuple[str, bool]] = []
    console_errors: list[str] = []
    js_errors: list[str] = []

    print(f"\n{'='*60}")
    print(f"  {name.upper()}  →  {html}")
    print(f"{'='*60}")

    outdir = html.parent
    size = html.stat().st_size

    check(results, "HTML file exists and non-trivial", size > 4096, f"{size:,} bytes")
    if size < 512:
        print("  (skipping — file too small to be valid HTML)")
        return results

    # Sniff first bytes for valid HTML
    first = html.read_text(errors="replace")[:200].strip()
    check(results, "File starts with valid HTML", first.lower().startswith("<!doctype") or first.lower().startswith("<html"), first[:60])
    if not (first.lower().startswith("<!doctype") or first.lower().startswith("<html")):
        print("  (skipping page load — not valid HTML)")
        return results

    page = browser.new_page(viewport={"width": 1280, "height": 900})

    def on_console(msg: ConsoleMessage):
        if msg.type == "error":
            console_errors.append(msg.text)
        elif msg.type == "assert":
            console_errors.append(f"[assert] {msg.text}")

    def on_pageerror(exc):
        js_errors.append(str(exc))

    page.on("console", on_console)
    page.on("pageerror", on_pageerror)

    try:
        page.goto(f"file://{html}", wait_until="load")

        # ── structural checks ─────────────────────────────────────────────────
        canvas = page.query_selector("canvas")
        check(results, "canvas element present", canvas is not None)

        if canvas:
            box = canvas.bounding_box()
            check(results, "canvas width ≈ 560 px", abs(box["width"] - 560) <= 6, f"{box['width']}")
            check(results, "canvas height ≥ 600 px", box["height"] >= 600, f"{box['height']}")

        score_el = page.query_selector("#score, [id*='score'], .score, [class*='score']")
        check(results, "score element in DOM", score_el is not None)

        page.screenshot(path=str(outdir / "shot_0_start_screen.png"))

        # ── start game ────────────────────────────────────────────────────────
        page.keyboard.press("Enter")
        page.wait_for_timeout(300)

        # Pump movement keys so Pac-Man eats dots
        for key in ["ArrowRight"] * 6 + ["ArrowDown"] * 3 + ["ArrowLeft"] * 4:
            page.keyboard.press(key)
            page.wait_for_timeout(150)

        page.wait_for_timeout(1500)

        score_js = """() => {
            const e = document.querySelector('#score, [id*="score"], .score, [class*="score"]');
            return e ? e.textContent.trim() : null;
        }"""
        score_3s = page.evaluate(score_js)
        score_3s_val = _parse_score(score_3s)
        check(results, "score readable after 3 s", score_3s is not None, repr(score_3s))
        check(results, "score > 0 after movement (dots eaten)", score_3s_val is not None and score_3s_val > 0, f"score={score_3s}")

        page.screenshot(path=str(outdir / "shot_3s.png"))

        # ── canvas is rendering ───────────────────────────────────────────────
        px_count = page.evaluate("""() => {
            const c = document.querySelector('canvas');
            if (!c) return 0;
            const ctx = c.getContext('2d');
            const d = ctx.getImageData(0, 0, c.width, c.height).data;
            let nonBlack = 0;
            for (let i = 0; i < d.length; i += 4)
                if (d[i] > 10 || d[i+1] > 10 || d[i+2] > 10) nonBlack++;
            return nonBlack;
        }""")
        check(results, "canvas has non-black pixels (rendered)", px_count > 500, f"{px_count} non-black px")

        # ── wait for ghost release window (12 s) ──────────────────────────────
        print("  … waiting 9 s for ghost release (12 s total) …")
        for _ in range(9):
            page.wait_for_timeout(1000)
            page.keyboard.press("ArrowRight")

        page.screenshot(path=str(outdir / "shot_12s.png"))

        score_12s = page.evaluate(score_js)
        check(results, "game alive at 12 s (no crash)", score_12s is not None, f"score={score_12s}")

        # ── JS state: ghost release ───────────────────────────────────────────
        ghost_state = page.evaluate("""() => {
            const g = window.ghosts;
            if (!g || !Array.isArray(g)) return null;
            return g.map(gh => ({
                name: gh.name || gh.id,
                inHouse: !!(gh.inHouse),
                started: !!(gh.started),
                col: gh.col,
                row: gh.row,
            }));
        }""")

        if ghost_state is None:
            check(results, "ghost state accessible (window.ghosts)", False, "not found in global scope")
        else:
            check(results, "ghost state accessible (window.ghosts)", True, f"{len(ghost_state)} ghosts")
            released = [g for g in ghost_state if not g["inHouse"]]
            check(results, "all 4 ghosts released by 12 s", len(released) == 4,
                  f"{len(released)}/4 out: {[g['name'] for g in released]}")
            still_penned = [g for g in ghost_state if g["inHouse"]]
            if still_penned:
                print(f"         still in house: {[g['name'] for g in still_penned]}")

        # ── JS state: pac position coherence ─────────────────────────────────
        pac_state = page.evaluate("""() => {
            const p = window.pac;
            if (!p) return null;
            return { col: p.col, row: p.row, px: p.px, py: p.py, dir: p.dir };
        }""")

        if pac_state and pac_state.get("col") is not None:
            TILE = 20
            expected_px = pac_state["col"] * TILE + TILE / 2
            expected_py = pac_state["row"] * TILE + TILE / 2
            drift_x = abs(pac_state["px"] - expected_px)
            drift_y = abs(pac_state["py"] - expected_py)
            # Allow up to half-tile drift (entity in transit between centers)
            check(results, "Pac-Man position/pixel coherent (no tunnel drift)",
                  drift_x <= TILE and drift_y <= TILE,
                  f"col={pac_state['col']} px={pac_state['px']:.1f} drift_x={drift_x:.1f}")
        else:
            check(results, "Pac-Man state accessible (window.pac)", False, "not in global scope")

        # ── console assert failures ───────────────────────────────────────────
        check(results, "zero console.assert / JS errors", len(console_errors) + len(js_errors) == 0,
              f"{len(console_errors)} console errors, {len(js_errors)} JS errors")
        for e in console_errors[:5]:
            print(f"         console: {e}")
        for e in js_errors[:5]:
            print(f"         JS err:  {e}")

    finally:
        page.close()

    return results


def verify_file(html_path: Path) -> dict:
    """Run all checks on a single HTML file. Returns a metrics dict for SIA evaluate.py."""
    html_path = Path(html_path).resolve()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        results = verify("target", html_path, browser)
        browser.close()
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    failed = total - passed
    return {
        "score": passed / total if total else 0.0,
        "passed": passed,
        "failed": failed,
        "total": total,
        "checks": [{"label": lbl, "passed": ok} for lbl, ok in results],
    }


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        all_results: dict[str, list[tuple[str, bool]]] = {}
        for name, html in TARGETS.items():
            all_results[name] = verify(name, html, browser)
        browser.close()

    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")
    grand_pass = grand_fail = 0
    for name, results in all_results.items():
        passed = sum(1 for _, ok in results if ok)
        failed = sum(1 for _, ok in results if not ok)
        grand_pass += passed
        grand_fail += failed
        status = "ALL PASS" if failed == 0 else f"{failed} FAILED"
        print(f"  {name:<10} {passed:>2} passed  {failed:>2} failed  [{status}]")
    print(f"  {'TOTAL':<10} {grand_pass:>2} passed  {grand_fail:>2} failed")

    return 0 if grand_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
