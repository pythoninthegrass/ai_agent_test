#!/usr/bin/env python3
"""
Pac-Man HTML generator — seed target agent for SIA.

Calls the local lemonade (Qwen3.6-35B-A3B-MTP-GGUF) endpoint to generate a
single-file pacman.html that passes all 14 Playwright checks.

Usage (SIA contract):
    python reference_target_agent.py --dataset_dir <task/data/public> --working_dir <gen_dir>

Output:
    <working_dir>/pacman.html
"""

import argparse
import os
import re
import sys
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
    "Build single-file HTML5 applications with inline CSS and JavaScript and no external dependencies."
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
    # Try <implementation> tags first (model sometimes wraps output)
    impls = re.findall(r"<implementation>(.*?)</implementation>", text, re.DOTALL)
    if impls:
        html = _strip_code_fence(impls[-1])
        if html.lower().startswith("<!doctype") or html.lower().startswith("<html"):
            return html

    # Fall back to bare HTML
    starts = [m.start() for m in re.finditer(r"(<!DOCTYPE\s+html|<html[\s>])", text, re.IGNORECASE)]
    if starts:
        html = text[starts[-1]:]
        end = html.lower().rfind("</html>")
        if end != -1:
            html = _strip_code_fence(html[:end + len("</html>")])
        return html

    return None


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


def main():
    parser = argparse.ArgumentParser(description="Pac-Man HTML generator (SIA target agent)")
    parser.add_argument("--dataset_dir", type=Path, required=True,
                        help="Path to task data/public/ directory")
    parser.add_argument("--working_dir", type=Path, required=True,
                        help="Directory to write pacman.html into")
    args = parser.parse_args()

    dataset_dir = args.dataset_dir.resolve()
    working_dir = args.working_dir.resolve()
    working_dir.mkdir(parents=True, exist_ok=True)

    # Read spec from task.md (strips the header down to the spec body)
    task_md = dataset_dir / "task.md"
    if not task_md.exists():
        print(f"[ERROR] task.md not found at {task_md}", flush=True)
        sys.exit(1)

    spec_raw = task_md.read_text(encoding="utf-8")
    # Extract just the Pac-Man specification section (after the Pac-Man specification heading)
    spec_match = re.search(
        r"## Pac-Man specification.*?---\s*\n(.*)",
        spec_raw,
        re.DOTALL,
    )
    if spec_match:
        spec_body = spec_match.group(1).strip()
    else:
        # Fall back to using the whole file minus the YAML-ish header
        spec_body = re.sub(r"^#.*?\n", "", spec_raw, count=5, flags=re.MULTILINE).strip()

    # Activate Qwen3 extended reasoning
    user_prompt = "/think\n\n" + spec_body

    api_key = os.environ.get("LEMONADE_API_KEY", "whenlifegivesyoulemons")
    client = OpenAI(base_url=LEMONADE_BASE_URL, api_key=api_key)

    html_path = working_dir / "pacman.html"

    for attempt in range(1, MAX_RETRIES + 1):
        print(f"\n[Attempt {attempt}/{MAX_RETRIES}] Calling {MODEL} …", flush=True)
        raw = call_lemonade(client, user_prompt)
        if raw is None:
            print(f"  [WARN] No response on attempt {attempt}", flush=True)
            continue

        html = extract_html(raw)
        if html is None:
            print(f"  [WARN] No HTML found in response on attempt {attempt} "
                  f"({len(raw):,} chars)", flush=True)
            # Save raw for debugging
            (working_dir / f"raw_attempt_{attempt}.txt").write_text(raw, encoding="utf-8")
            continue

        html_path.write_text(html, encoding="utf-8")
        print(f"\n  [OK] pacman.html written ({len(html):,} bytes) → {html_path}", flush=True)
        sys.exit(0)

    print(f"\n[FAIL] Could not generate valid HTML after {MAX_RETRIES} attempts.", flush=True)
    sys.exit(1)


if __name__ == "__main__":
    main()
