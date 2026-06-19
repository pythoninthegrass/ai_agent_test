#!/usr/bin/env python3
"""
Pac-Man HTML generator — seed target agent for SIA.

Calls the local lemonade (Qwen3.6-35B-A3B-MTP-GGUF) endpoint to generate a
single-file pacman.html that passes all 14 Playwright checks.

Usage (SIA contract):
    python target_agent.py --dataset_dir <path> --working_dir <path>

Output:
    <working_dir>/pacman.html
    <working_dir>/agent_execution.json
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

from openai import OpenAI

# ── constants ────────────────────────────────────────────────────────────────

LEMONADE_BASE_URL = "http://localhost:13305/api/v1"
MODEL = "Qwen3.6-35B-A3B-MTP-GGUF"
MAX_TOKENS = 20480
TEMPERATURE = 0.2
MAX_RETRIES = 3

SYSTEM_PROMPT = (
    "You are an expert vanilla web developer. "
    "Build single-file HTML5 applications with inline CSS and JavaScript and no external dependencies. "
    "You produce COMPLETE, WORKING HTML files — nothing placeholder, nothing abbreviated."
)

# ── helpers ──────────────────────────────────────────────────────────────────


def _strip_code_fence(text: str) -> str:
    """Remove leading/trailing ``` fences if present."""
    text = text.strip()
    if text.startswith("```"):
        first_nl = text.find("\n")
        text = text[first_nl + 1:] if first_nl != -1 else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def extract_html(text: str) -> str | None:
    """Extract the last complete HTML document from model output."""
    # Try <implementation> tags first
    impls = re.findall(r"<implementation>(.*?)</implementation>", text, re.DOTALL)
    if impls:
        html = _strip_code_fence(impls[-1])
        if html.lower().startswith("<!doctype") or html.lower().startswith("<html"):
            return html

    # Try fenced ```html blocks
    fences = re.findall(r"```[hH][tT][mM][lL]?(.*?)```", text, re.DOTALL)
    if fences:
        html = _strip_code_fence(fences[-1])
        if html.lower().startswith("<!doctype") or html.lower().startswith("<html"):
            return html

    # Fall back to bare HTML
    starts = [m.start() for m in re.finditer(
        r"(<!DOCTYPE\s+html|<html[\s>])", text, re.IGNORECASE
    )]
    if starts:
        html = text[starts[-1]:]
        end = html.lower().rfind("</html>")
        if end != -1:
            html = html[:end + len("</html>")]
        html = html.strip()
        if html:
            return html

    return None


def extract_spec(spec_raw: str) -> str:
    """Extract the Pac-Man specification body from task.md content.

    The spec is the text between the first two '---' markers that appear
    after the '## Pac-Man specification' heading.
    """
    # Find the specification heading
    spec_heading = "## Pac-Man specification"
    heading_idx = spec_raw.find(spec_heading)

    if heading_idx > 0:
        # Find the first --- after the heading
        first_dash = spec_raw.find("---", heading_idx)
        if first_dash > 0:
            # Find the second --- after the first one
            second_dash = spec_raw.find("---", first_dash + 3)
            if second_dash > 0:
                # Extract text between the first --- and the second ---
                # Strip the leading --- and trailing ---
                body = spec_raw[first_dash + 3:second_dash].strip()
                # The first section ends at the NEXT --- (which starts the sample tasks)
                # But we want the ENTIRE spec including samples, so take first two ---
                if body and ("Pac-Man clone" in body or "MECHANICS" in body):
                    return body

    # Fallback: use the whole file minus the initial header lines
    lines = spec_raw.split("\n")
    # Skip the first few header lines (starting with #)
    body_lines = []
    for line in lines:
        if line.startswith("#"):
            if body_lines:  # stop at the second header block
                break
        else:
            body_lines.append(line)
    body = "\n".join(body_lines).strip()
    return body if body else spec_raw


def call_lemonade(client: OpenAI, user_prompt: str) -> str | None:
    """Call the lemonade endpoint and return the response text (or None on failure)."""
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
        )
        if not response.choices:
            print("  [WARN] empty choices in response", flush=True)
            return None
        content = response.choices[0].message.content or ""
        if not content.strip():
            print("  [WARN] empty content in response", flush=True)
            return None
        return content
    except Exception as exc:
        print(f"  [ERROR] API call failed: {exc}", flush=True)
        return None


def build_user_prompt(dataset_dir: str, working_dir: str, spec_body: str) -> str:
    """Build the complete user prompt with filesystem paths and the spec."""
    prompt = f"""You are building a complete Pac-Man clone as a single HTML file.

## Filesystem access

- **Dataset directory**: `{dataset_dir}` — READ-ONLY. Contains `task.md` with additional context if needed.
- **Working directory**: `{working_dir}` — READ-WRITE. You must write your output here.

**CRITICAL**: Write the final HTML file to `{working_dir}/pacman.html`. Do NOT write to any other location.
Only read from `{dataset_dir}` and only write to `{working_dir}`.

---

{spec_body}

---

**OUTPUT**: Produce ONLY the complete `pacman.html` file. Do not include any prose before or after the HTML.
The file must start with `<!DOCTYPE html>` or `<html`.
"""
    return prompt


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Pac-Man HTML generator (SIA target agent)")
    parser.add_argument("--dataset_dir", type=Path, required=True,
                        help="Path to task data/public/ directory (READ-ONLY)")
    parser.add_argument("--working_dir", type=Path, required=True,
                        help="Directory to write pacman.html into (READ-WRITE)")
    args = parser.parse_args()

    dataset_dir = args.dataset_dir.resolve()
    working_dir = args.working_dir.resolve()
    working_dir.mkdir(parents=True, exist_ok=True)

    # ── Read spec from task.md ──────────────────────────────────────────────
    task_md = dataset_dir / "task.md"
    if not task_md.exists():
        print(f"[ERROR] task.md not found at {task_md}", flush=True)
        sys.exit(1)

    spec_raw = task_md.read_text(encoding="utf-8")
    spec_body = extract_spec(spec_raw)

    dataset_str = str(dataset_dir)
    working_str = str(working_dir)

    # Build the user prompt with paths + spec
    user_prompt = "/think\n\n" + build_user_prompt(dataset_str, working_str, spec_body)

    api_key = os.environ.get("LEMONADE_API_KEY", "whenlifegivesyoulemons")
    client = OpenAI(base_url=LEMONADE_BASE_URL, api_key=api_key)

    html_path = working_dir / "pacman.html"
    trajectory_path = working_dir / "agent_execution.json"

    # ── Execution trajectory (single JSON file for this single-execution task) ──
    trajectory = []

    # Record system message
    trajectory.append({
        "role": "system",
        "content": SYSTEM_PROMPT
    })

    # Try multiple times until we get valid HTML
    best_html = None
    last_error = None
    last_response = None
    api_duration = 0.0

    for attempt in range(1, MAX_RETRIES + 1):
        print(f"\n[Attempt {attempt}/{MAX_RETRIES}] Calling {MODEL} …", flush=True)

        # Record the user message
        trajectory.append({
            "role": "user",
            "content": user_prompt
        })

        start_time = time.time()
        raw = call_lemonade(client, user_prompt)
        duration = time.time() - start_time
        api_duration += duration

        if raw is None:
            print(f"  [WARN] No response on attempt {attempt}", flush=True)
            last_error = f"No API response on attempt {attempt}"
            continue

        last_response = raw
        html = extract_html(raw)
        if html is None:
            print(f"  [WARN] No HTML found in response on attempt {attempt} "
                  f"({len(raw):,} chars)", flush=True)
            last_error = f"No HTML extracted on attempt {attempt}"
            # Save raw for debugging
            (working_dir / f"raw_attempt_{attempt}.txt").write_text(raw, encoding="utf-8")
            continue

        # Validate minimum size (check ≥ 4 KB for check 1)
        if len(html) < 4096:
            print(f"  [WARN] HTML too small ({len(html)} bytes) on attempt {attempt}", flush=True)
            last_error = f"HTML too small: {len(html)} bytes on attempt {attempt}"
            continue

        print(f"\n  [OK] pacman.html written ({len(html):,} bytes) → {html_path}", flush=True)
        html_path.write_text(html, encoding="utf-8")
        best_html = html
        last_error = None
        break  # success — exit loop

    # Record assistant response
    if last_response is not None:
        trajectory.append({
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": f"Generated pacman.html ({len(last_response):,} chars)"
                }
            ]
        })

    # Record timing info as a tool-like result
    if best_html is not None:
        trajectory.append({
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": f"Success: pacman.html written ({len(best_html):,} bytes) to {html_path}"
                }
            ]
        })
    else:
        trajectory.append({
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": f"Failure: {last_error}"
                }
            ]
        })

    # Write trajectory
    trajectory.append({
        "role": "assistant",
        "content": [
            {
                "type": "text",
                "text": f"API call duration: {api_duration:.2f}s, Attempts: {3 if best_html is None else 1}"
            }
        ]
    })

    trajectory_path.write_text(json.dumps(trajectory, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nTrajectory saved to {trajectory_path}", flush=True)

    if best_html is None:
        print(f"\n[FAIL] Could not generate valid HTML after {MAX_RETRIES} attempts.", flush=True)
        print(f"Last error: {last_error}", flush=True)
        sys.exit(1)

    print(f"\n[SUCCESS] pacman.html generated successfully.", flush=True)
    sys.exit(0)


if __name__ == "__main__":
    main()
