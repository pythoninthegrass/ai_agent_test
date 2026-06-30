# AGENTS.md

This file provides guidance to AI agents when working with code in this repository.

## What this repo is

A **compaction-stress harness** that drives three different AI coding agents (`pi`, `opencode`, `hermes`) through a fixed 18-milestone TDD exercise (`TASK.md`) to measure whether each agent's context-compaction fires before koboldcpp's SmartCache context-shift kicks in. The agent under test builds `rpncalc/` — a small RPN calculator interpreter — inside `build/` using pytest-driven milestones.

## Running the harness

`run.py` is a self-contained `uv run --script`; no venv setup needed:

```bash
# Drive all three agents sequentially (waits for vLLM on :61515 first)
./run-all-vllm.sh

# Run a single agent
./run-all-vllm.sh pi
./run-all-vllm.sh opencode hermes   # two agents, in order

# Drive one agent directly
./run.py milestones                 # pi (default model)
./run.py opencode-milestones
./run.py hermes-milestones

# Common flags
./run.py milestones --max-steps 10 --max-stalls 3
./run.py milestones --model koboldcpp/some-other-model

# Just watch Docker container logs for CtxLimit signals
./run.py observe

# Synthetic agentic load test (locust, targets :61519 proxy)
./run.py stress                              # 8 users, ramp 2/s, 5m
./run.py stress --duration 30s --users 2    # smoke-test
./run-all-vllm.sh locust                    # same, via the shell runner
DURATION=30s ./run-all-vllm.sh locust       # smoke-test via shell runner
```

Output artifacts land in `build-pi-vllm/`, `build-opencode-vllm/`, `build-hermes-vllm/` after each run: `run.log` and `harness.status`. The load test writes to `build-locust-vllm/` directly.

## Architecture

### `run.py` — the harness

The core loop (`cmd_milestones` / `cmd_milestones_opencode` / `cmd_milestones_hermes`) follows the same pattern for all three agents:

1. `reset_build()` — wipes `build/`, seeds `TASK.md` + `pytest.ini`, creates an initial `milestone 00: harness` git commit.
2. Outer `for step in range(max_steps)` loop — one agent invocation per step, each passed `MILESTONE_PROMPT` (do exactly one milestone then stop).
3. After each step, `milestone_count(repo)` counts the highest `milestone N:` commit to detect progress. No progress → stall counter; too many stalls → `BAIL`.
4. Compaction signal is detected by watching Docker container logs for `CtxLimit:<used>/<max>` lines (via `start_observers` / `stream` threads).

**Why one invocation per milestone**: `pi` only runs its auto-compaction check at agent-run boundaries (`agent_end` / pre-prompt). One continuous `pi -p` run for all 18 milestones never hits that boundary, so context climbs to the 131072 ceiling. Splitting into per-milestone invocations with a shared `--session-id` creates the boundary while preserving session continuity.

### Agent differences

| Agent | Binary | Session continuity | Config |
|---|---|---|---|
| `pi` | `pi` (Claude Code CLI) | `--session-id <uuid>` flag | inline flags |
| `opencode` | `~/.opencode/bin/opencode` | `--session <id>` (captured from first JSON `sessionID` event) | `opencode.json` |
| `hermes` | `~/.local/bin/hermes` | `--resume <id>` (captured from `session_id: <id>` line in output) | CLI flags |

### `build/` — the agent's working directory

The agent builds here from scratch each run. It is a git repo (seeded by `reset_build()`). The harness never modifies `build/` directly after seeding — only the agent does. Milestone progress is measured by reading the git log of `build/`.

### `run-all-vllm.sh` — sequential multi-agent runner

Waits for vLLM health on `:61515`, then calls the selected agent commands in sequence, archiving `build/` to `build-{agent}-vllm/` between milestone runs. The `locust` agent is opt-in (`./run-all-vllm.sh locust`); the default set remains `pi opencode hermes`.

### `locustfile.py` — synthetic agentic load test

Locust file that simulates concurrent coding-agent traffic against the `:61519` proxy: a fixed system prompt + tool block (exercises prefix caching), multi-turn conversations with growing context, and synthetic tool-call/tool-result turns appended each iteration. This is *complementary* to the milestone harness — it generates realistic traffic shape without actually solving the coding task. `run.py stress` starts the Docker `CtxLimit` observers before launching Locust headless, so context-shift signals appear alongside Locust's per-request stats. Artifacts land in `build-locust-vllm/`.

## Key constants (in `run.py`)

- `SESSION_MODEL` — default pi model: `koboldcpp/qwen3-coder-next-builder`
- `OPENCODE_MODEL` — default opencode model: `local-builder/qwen3-coder-next` (proxy on `:61519`)
- `HERMES_MODEL` — default hermes model: `qwen3-coder-next`
- `STRESS_HOST` — default locust target: `http://127.0.0.1:61519`
- `STRESS_MODEL` — default locust model name: `qwen3-coder-next`
- vLLM endpoint: `:61515`; opencode/hermes/locust proxy: `:61519`

## The task being graded (`TASK.md`)

18 milestones building `rpncalc/` (scaffold → lexer → evaluator → errors → variables → comparisons → conditionals → comments → stack-ops → functions → repl → file runner → line-number errors). The agent must follow strict TDD: test first, full `pytest -v` between each milestone, one commit per milestone with message `milestone N: <slug>`.

## Authoritative Pac-Man reference (`pacman.html`)

The repo root contains `pacman.html` — a single-file, dependency-free Pac-Man clone that serves as the **answer key** for SIA runs that test local LLMs on game-building tasks. Agents are scored against it via the 14-check Playwright evaluator.

### What it implements

- **Maze + movement** — 28×31 grid, `TILE=20`, center-gated anti-clip model (direction changes and wall checks only at tile centers; hard-snap to center before turning). Pixel positions only; `Math.floor(px/TILE)` for tile lookup.
- **Ghost AI** — Blinky (direct chase), Pinky (4 ahead), Inky (reflect Blinky through 2 ahead), Clyde (chase if >8 tiles away, else scatter). Scatter/Chase cycle: 7 s / 20 s, lock to chase after 4 cycles, reverse on phase transition.
- **Release** — name-keyed `RELEASE = {pinky:200, inky:400, clyde:600}`, live `>=` check, ghosts walk out through the door. Blinky starts outside.
- **Frightened + revive** — power pellet → 6 s frightened, escalating 200/400/800/1600 ghost-eat score, eaten ghosts float (eyes-only) directly back to house, revive and re-exit.
- **Visuals** — hermes-style beveled walls (#2121DE/#5959FF), animated pac mouth + eye, domed wavy-skirt ghosts, pulsing power pellets, ♥ HUD, blink overlays.
- **Spec globals** — `window.pac` with `col`/`row` `Object.defineProperty` getters (pac only); `window.ghosts` plain writable array; Enter key starts/restarts; score in `#score` DOM span.

### Running the evaluator

```bash
# 14-check Playwright evaluator (must score 14/14)
mkdir -p /tmp/pacman-ref && cp pacman.html /tmp/pacman-ref/
uvx --with playwright python3 sia-pacman/data/public/evaluate.py --gen-dir /tmp/pacman-ref
cat /tmp/pacman-ref/results.json   # score: 1.0 = 14/14

# Gameplay invariant tests (ghost-kill, revive loop, no clipping)
uvx --with playwright python3 tests/test_pacman_gameplay.py

# Smoke-test the latest timestamped artifacts (pi + hermes)
uvx --with playwright python3 tests/verify_pacman.py
```

### Test files

| File | What it checks |
|---|---|
| `sia-pacman/data/public/evaluate.py` | 14-check canonical evaluator: HTML validity, canvas dimensions, score in DOM, dots eaten, non-black pixels, alive at 12 s, all 4 ghosts released, pac position coherent, zero JS errors |
| `tests/test_pacman_gameplay.py` | Gameplay invariants: score jumps ≥200 on ghost eat, `eaten` flag clears after revive, pac snaps to tile center when stopped |
| `tests/verify_pacman.py` | Smoke-test for the latest `artifacts/pi/` and `artifacts/hermes/` timestamped runs (structural + 12 s ghost-release check) |

## Context7

Always use Context7 when I need library/API documentation, code generation, setup or configuration steps without me having to explicitly ask.

### Libraries

- astral-sh/ruff
- astral-sh/uv
- hbnetwork/python-decouple
- hypothesisworks/hypothesis
- jdx/mise
- mostlygeek/llama-swap
- mrlesk/backlog.md
