# AGENTS.md

This file provides guidance to AI agents when working with code in this repository.

## What this repo is

A **compaction-stress harness** that drives three different AI coding agents (`pi`, `opencode`, `hermes`) through a fixed 18-milestone TDD exercise (`TASK.md`) to measure whether each agent's context-compaction fires before koboldcpp's SmartCache context-shift kicks in. The agent under test builds `rpncalc/` — a small RPN calculator interpreter — inside `build/` using pytest-driven milestones.

## Running the harness

Scripts live in `scripts/` and are abstracted by `taskfile.yml`. `scripts/run.py` is a self-contained `uv run --script`; no venv setup needed.

| Task command | Equivalent script | Notes |
|---|---|---|
| `task run -- milestones` | `./scripts/run.py milestones` | pi, default model |
| `task run -- opencode-milestones` | `./scripts/run.py opencode-milestones` | |
| `task run -- hermes-milestones` | `./scripts/run.py hermes-milestones` | |
| `task run -- milestones --max-steps 10 --max-stalls 3` | `./scripts/run.py milestones --max-steps 10 --max-stalls 3` | |
| `task run -- milestones --model koboldcpp/some-other-model` | `./scripts/run.py milestones --model koboldcpp/some-other-model` | |
| `task run -- observe` | `./scripts/run.py observe` | stream Docker logs for CtxLimit signals |
| `task run -- stress` | `./scripts/run.py stress` | 8 users, ramp 2/s, 5m |
| `task run -- stress --duration 30s --users 2` | `./scripts/run.py stress --duration 30s --users 2` | smoke-test |
| `task run -- pi-pacman` | `./scripts/run.py pi-pacman` | one-shot `pacman.html` via pi |
| `task run -- pacman` | `./scripts/run.py pacman` | one-shot `pacman.html` via hermes |
| `task run -- pi-lol` | `./scripts/run.py pi-lol` | one-shot llmao MOBA build via pi |
| `task run -- lol` | `./scripts/run.py lol` | one-shot llmao MOBA build via hermes |
| `task run-all` | `./scripts/run-all-vllm.sh` | all three agents sequentially |
| `task run-all -- pi` | `./scripts/run-all-vllm.sh pi` | single agent |
| `task run-all -- opencode hermes` | `./scripts/run-all-vllm.sh opencode hermes` | two agents, in order |
| `task run-all -- locust` | `./scripts/run-all-vllm.sh locust` | synthetic load test via shell runner |
| `DURATION=30s task run-all -- locust` | `DURATION=30s ./scripts/run-all-vllm.sh locust` | smoke-test |
| `task swe-bench` | `./scripts/run-swe-bench.sh` | SWE-bench stress run |

Output artifacts land in `build-pi-vllm/`, `build-opencode-vllm/`, `build-hermes-vllm/` after each run: `run.log` and `harness.status`. The load test writes to `build-locust-vllm/` directly.

## Architecture

### `scripts/run.py` — the harness

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

### `scripts/run-all-vllm.sh` — sequential multi-agent runner

Waits for vLLM health on `:61515`, then calls the selected agent commands in sequence, archiving `build/` to `build-{agent}-vllm/` between milestone runs. The `locust` agent is opt-in (`task run-all -- locust`); the default set remains `pi opencode hermes`.

### `scripts/locustfile.py` — synthetic agentic load test

Locust file that simulates concurrent coding-agent traffic against the `:61519` proxy: a fixed system prompt + tool block (exercises prefix caching), multi-turn conversations with growing context, and synthetic tool-call/tool-result turns appended each iteration. This is *complementary* to the milestone harness — it generates realistic traffic shape without actually solving the coding task. `task run -- stress` starts the Docker `CtxLimit` observers before launching Locust headless, so context-shift signals appear alongside Locust's per-request stats. Artifacts land in `build-locust-vllm/`.

### One-shot commands (`pi-pacman`, `pacman`, `pi-lol`, `lol`)

Unlike the milestone loop, these run a single agent invocation against a fixed prompt and produce one artifact — no `TASK.md`, no per-step stall/bail bookkeeping.

- `pi-pacman` / `pacman` — generate `pacman.html` (single-file, dependency-free) via `pi` or `hermes` respectively. Scored against the reference in `pacman.html` (see below).
- `pi-lol` / `lol` — autonomously build **llmao**, a clean-room MOBA (SvelteKit + PixiJS), from a seeded Backlog.md board, via `pi` or `hermes` respectively.

Dispatch lives in `scripts/run.py`:

- `_prompt_config(prompt, ts) -> PromptConfig` — a `match` on `"pacman"` / `"lol"` that returns the prompt-specific system/user prompts, output-dir name, an optional `setup` hook (`_seed_lol_dir`, lol only — git-inits the outdir and seeds its Backlog.md board), and an optional `postprocess` hook (`_pacman_postprocess`, pacman only — confirms `pacman.html` was written, else salvages HTML out of the raw response).
- `cmd_pi(prompt, model)` / `cmd_hermes(prompt, model)` — agent-generic entry points, one per agent, used by all four CLI commands. Agent-specific invocation details live in `PromptConfig.pi_kwargs` / `PromptConfig.hermes_kwargs` rather than in separate functions: `pi_kwargs` carries `thinking` level and whether the call needs `mise`-wrapping (lol only, for its managed node runtime); `hermes_kwargs` carries `mode` (`"library"` — the `AIAgent` Python class, used for pacman — vs `"cli"` — the `hermes chat` binary, used for lol because the Python library ignores `base_url` and can't do provider routing) and `max_turns`.

Artifacts land in `artifacts/{pi,hermes}/<ts>/` (pacman) or `artifacts/{pi,hermes}/lol-<ts>/` (lol), each with `run.log` and `harness.status`; pacman runs also get `pacman.html`, lol runs also get a seeded project (Backlog.md board + `CLAUDE.md` system prompt) committed as the initial commit.

## Key constants (in `scripts/run.py`)

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
