#!/usr/bin/env python3
"""
Playwright-based evaluator for generated pacman.html files.

Called by the SIA orchestrator as:
    python evaluate.py --gen-dir path/to/gen_N/

Expects `gen_dir/pacman.html` to exist.
Writes `gen_dir/results.json` with score = passed / 14.
"""

import argparse
import json
import sys
from pathlib import Path


def run_checks(html_path: Path) -> dict:
    """Run all 14 Playwright checks on the given HTML file."""
    # Import here so this module can be imported without playwright
    # (playwright is installed by the SIA run venv via reference/requirements.txt)
    from playwright.sync_api import ConsoleMessage, sync_playwright

    results = []
    console_errors = []
    js_errors = []

    def check(label: str, cond: bool, detail: str = "") -> None:
        status = "PASS" if cond else "FAIL"
        line = f"  [{status}]  {label}"
        if detail:
            line += f"  — {detail}"
        print(line, flush=True)
        results.append({"label": label, "passed": cond, "detail": detail})

    html_path = Path(html_path)
    if not html_path.exists():
        check("HTML file exists and non-trivial", False, "file not found")
        return {"score": 0.0, "passed": 0, "failed": 1, "total": 1, "checks": results}

    size = html_path.stat().st_size
    check("HTML file exists and non-trivial", size > 4096, f"{size:,} bytes")
    if size < 512:
        return {"score": 0.0, "passed": 0, "failed": 1, "total": 1, "checks": results}

    first = html_path.read_text(errors="replace")[:200].strip()
    is_html = first.lower().startswith("<!doctype") or first.lower().startswith("<html")
    check("File starts with valid HTML", is_html, first[:60])
    if not is_html:
        return {"score": 1 / 14, "passed": 1, "failed": 13, "total": 14, "checks": results}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
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
            page.goto(f"file://{html_path.resolve()}", wait_until="load")

            canvas = page.query_selector("canvas")
            check("canvas element present", canvas is not None)

            if canvas:
                box = canvas.bounding_box()
                check("canvas width ≈ 560 px", abs(box["width"] - 560) <= 6, f"{box['width']}")
                check("canvas height ≥ 600 px", box["height"] >= 600, f"{box['height']}")
            else:
                check("canvas width ≈ 560 px", False, "no canvas")
                check("canvas height ≥ 600 px", False, "no canvas")

            score_el = page.query_selector("#score, [id*='score'], .score, [class*='score']")
            check("score element in DOM", score_el is not None)

            # Start game
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

            def _parse_score(text):
                if text is None:
                    return None
                import re
                m = re.search(r"\d+", text)
                return int(m.group()) if m else None

            score_3s = page.evaluate(score_js)
            score_3s_val = _parse_score(score_3s)
            check("score readable after 3 s", score_3s is not None, repr(score_3s))
            check("score > 0 after movement (dots eaten)",
                  score_3s_val is not None and score_3s_val > 0,
                  f"score={score_3s}")

            px_count = page.evaluate("""() => {
                const c = document.querySelector('canvas');
                if (!c) return 0;
                const ctx = c.getContext('2d');
                const d = ctx.getImageData(0, 0, c.width, c.height).data;
                let n = 0;
                for (let i = 0; i < d.length; i += 4)
                    if (d[i] > 10 || d[i+1] > 10 || d[i+2] > 10) n++;
                return n;
            }""")
            check("canvas has non-black pixels (rendered)", px_count > 500, f"{px_count} non-black px")

            # Wait for ghost-release window (12 s total)
            print("  … waiting 9 s for ghost release (12 s total) …", flush=True)
            for _ in range(9):
                page.wait_for_timeout(1000)
                page.keyboard.press("ArrowRight")

            score_12s = page.evaluate(score_js)
            check("game alive at 12 s (no crash)", score_12s is not None, f"score={score_12s}")

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
            check("ghost state accessible (window.ghosts)",
                  ghost_state is not None and len(ghost_state) > 0,
                  f"{len(ghost_state) if ghost_state else 0} ghosts")

            if ghost_state:
                out = [g["name"] for g in ghost_state if not g["inHouse"]]
                penned = [g["name"] for g in ghost_state if g["inHouse"]]
                check("all 4 ghosts released by 12 s",
                      len(out) == 4,
                      f"{len(out)}/4 out: {out}" + (f"\n         still in house: {penned}" if penned else ""))
            else:
                check("all 4 ghosts released by 12 s", False, "no ghost state")

            pac_state = page.evaluate("""() => {
                const p = window.pac;
                if (!p) return null;
                return { col: p.col, row: p.row, px: p.px, py: p.py, dir: p.dir };
            }""")
            if pac_state and pac_state.get("col") is not None:
                TILE = 20
                expected_px = pac_state["col"] * TILE + TILE / 2
                drift_x = abs(pac_state["px"] - expected_px)
                check("Pac-Man position/pixel coherent (no tunnel drift)",
                      drift_x <= TILE,
                      f"col={pac_state['col']} px={pac_state['px']:.1f} drift_x={drift_x:.1f}")
            else:
                check("Pac-Man state accessible (window.pac)", False, "not in global scope")

            check("zero console.assert / JS errors",
                  len(console_errors) + len(js_errors) == 0,
                  f"{len(console_errors)} console errors, {len(js_errors)} JS errors")
            for e in console_errors[:5]:
                print(f"         console: {e}", flush=True)
            for e in js_errors[:5]:
                print(f"         JS err:  {e}", flush=True)

        finally:
            page.close()
        browser.close()

    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    failed = total - passed
    score = passed / 14  # always out of 14 regardless of how many checks ran

    return {
        "score": score,
        "passed": passed,
        "failed": failed,
        "total": total,
        "checks": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate pacman.html from a SIA generation dir")
    parser.add_argument("--gen-dir", type=Path, required=True,
                        help="Generation directory containing pacman.html")
    args = parser.parse_args()

    gen_dir = args.gen_dir.resolve()
    html_path = gen_dir / "pacman.html"

    print(f"\n{'='*60}", flush=True)
    print(f"  Evaluating: {html_path}", flush=True)
    print(f"{'='*60}", flush=True)

    metrics = run_checks(html_path)

    print(f"\n{'='*60}", flush=True)
    print(f"  SCORE: {metrics['passed']}/14  ({metrics['score']:.3f})", flush=True)
    print(f"{'='*60}", flush=True)

    results_path = gen_dir / "results.json"
    results_path.write_text(json.dumps(metrics, indent=2))
    print(f"\nResults written to: {results_path}", flush=True)

    return 0 if metrics["score"] >= 1.0 else 1


if __name__ == "__main__":
    sys.exit(main())
