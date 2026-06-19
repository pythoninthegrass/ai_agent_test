#!/usr/bin/env python3
"""
Pac-Man HTML generator — hermes seed target agent for SIA.

Invokes the hermes AIAgent (via its Python library) to generate a single-file
pacman.html that passes all 14 Playwright checks.

Usage (SIA contract):
    python reference_target_agent.py --dataset_dir <path> --working_dir <path>

Output:
    <working_dir>/pacman.html
    <working_dir>/agent_execution.json
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

# ── constants ────────────────────────────────────────────────────────────────

HERMES_PYTHON = "/home/lance/.hermes/hermes-agent/venv/bin/python"
HERMES_MODEL = "Qwen3.6-35B-A3B-MTP-GGUF"
MAX_RETRIES = 3

SYSTEM_PROMPT = (
    "You are an expert vanilla web developer. "
    "Build single-file HTML5 applications with inline CSS and JavaScript and no external dependencies."
)

# /pacman loads the hermes skill at ~/.hermes/skills/game-dev/pacman/SKILL.md —
# the same prompt that produces 14/14 in standalone runs. Keeping this as the
# default user prompt means the meta-agent starts from a proven 14/14 baseline
# and can improve from there (e.g. tighter retry logic, different instructions).
USER_PROMPT = "/pacman"

# Inline script executed inside the hermes venv. Reads prompt from env vars and
# calls AIAgent, which writes pacman.html directly via its file tools.
_AGENT_SCRIPT = """\
import os, sys
from run_agent import AIAgent

agent = AIAgent(
    model=os.environ["HERMES_MODEL"],
    ephemeral_system_prompt=os.environ["HERMES_SYSTEM_PROMPT"],
    quiet_mode=True,
    skip_memory=True,
    save_trajectories=False,
)
response = agent.chat(os.environ["HERMES_USER_PROMPT"])
print(response)
"""




def run_hermes(user_prompt: str, working_dir: str) -> tuple[bool, str, float]:
    """Run hermes AIAgent. Returns (success, stdout, duration_seconds)."""
    env_extra = {
        "HERMES_MODEL": HERMES_MODEL,
        "HERMES_SYSTEM_PROMPT": SYSTEM_PROMPT,
        "HERMES_USER_PROMPT": user_prompt,
    }
    import os
    env = {**os.environ, **env_extra}

    start = time.time()
    try:
        result = subprocess.run(
            [HERMES_PYTHON, "-c", _AGENT_SCRIPT],
            cwd=working_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )
        duration = time.time() - start
        stdout = result.stdout + result.stderr
        return result.returncode == 0, stdout, duration
    except subprocess.TimeoutExpired:
        duration = time.time() - start
        return False, "[TIMEOUT] hermes exceeded 300 s", duration
    except Exception as exc:
        duration = time.time() - start
        return False, f"[ERROR] subprocess failed: {exc}", duration


def main():
    parser = argparse.ArgumentParser(description="Pac-Man HTML generator (hermes SIA target agent)")
    parser.add_argument("--dataset_dir", type=Path, required=True)
    parser.add_argument("--working_dir", type=Path, required=True)
    args = parser.parse_args()

    working_dir = args.working_dir.resolve()
    working_dir.mkdir(parents=True, exist_ok=True)

    user_prompt = USER_PROMPT

    html_path = working_dir / "pacman.html"
    trajectory_path = working_dir / "agent_execution.json"
    trajectory = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    success = False
    last_stdout = ""
    total_duration = 0.0

    for attempt in range(1, MAX_RETRIES + 1):
        print(f"\n[Attempt {attempt}/{MAX_RETRIES}] Running hermes ({HERMES_MODEL}) …", flush=True)
        ok, stdout, duration = run_hermes(user_prompt, str(working_dir))
        total_duration += duration
        last_stdout = stdout

        if html_path.exists() and html_path.stat().st_size >= 4096:
            size = html_path.stat().st_size
            print(f"  [OK] pacman.html written ({size:,} bytes) → {html_path}", flush=True)
            trajectory.append({
                "role": "assistant",
                "content": f"Generated pacman.html ({size:,} bytes) on attempt {attempt}",
            })
            success = True
            break

        print(f"  [WARN] pacman.html missing or too small after attempt {attempt}", flush=True)
        if stdout:
            print(f"  [OUTPUT] {stdout[:300]}", flush=True)

    trajectory.append({
        "role": "assistant",
        "content": f"Total duration: {total_duration:.1f}s, success: {success}",
    })
    trajectory_path.write_text(json.dumps(trajectory, indent=2, ensure_ascii=False))
    print(f"\nTrajectory saved to {trajectory_path}", flush=True)

    if not success:
        print(f"\n[FAIL] pacman.html not generated after {MAX_RETRIES} attempts.", flush=True)
        sys.exit(1)

    print(f"\n[SUCCESS] pacman.html generated successfully.", flush=True)
    sys.exit(0)


if __name__ == "__main__":
    main()
