# sia-pacman

SIA task package for the Pac-Man HTML benchmark. Uses the
[hexo-ai/SIA](https://github.com/hexo-ai/sia) self-improving agent framework to
iteratively rewrite `target_agent.py` until it reliably generates a single-file
`pacman.html` that passes all 14 automated Playwright checks.

## Prerequisites

```bash
uv tool install 'sia-agent[pydantic-ai]'
uvx --with playwright python3 -m playwright install chromium
```

Requires a running [lemonade](https://github.com/lemonade-hq/lemonade) server on
`http://localhost:13305` with `Qwen3.6-35B-A3B-MTP-GGUF` loaded, and
`LEMONADE_API_KEY` set in `.env`.

## Running

```bash
source .env   # exports LEMONADE_API_KEY, SIA_MAX_TURNS=100
sia run \
  --task_dir sia-pacman \
  --meta-agent-profile lemonade-meta \
  --target-agent-profile lemonade-target \
  --max_gen 5 \
  --run_id <N> \
  --no-web
```

Output lands in `runs/run_<N>/gen_<k>/` (gitignored). Each generation contains
`target_agent.py`, `pacman.html`, `results.json`, and `evaluation.log`.

## Layout

```
sia-pacman/
  data/public/
    task.md          # task spec + 14-check list seen by the meta-agent
    evaluate.py      # Playwright evaluator; writes results.json, always exits 0
  reference/
    reference_target_agent.py   # seed agent (promoted from run_1/gen_1, scores 14/14)
    requirements.txt            # playwright + openai — installed into each gen venv
    SAMPLE_TASK_DESCRIPTIONS.md
```

Provider/profile JSON live at the repo root:

```
providers/lemonade.json         # lemonade OpenAI-compatible endpoint
profiles/lemonade-meta.json     # meta-agent: pydantic-ai + Qwen3.6
profiles/lemonade-target.json   # target-agent: Qwen3.6 via lemonade
```

## Evaluation contract

`evaluate.py` is called by SIA as:

```bash
python evaluate.py --gen-dir <generation_directory>
```

It runs 14 Playwright checks against `pacman.html` in that directory, writes
`results.json` with `{"score": 0–1.0, "passed": N, "failed": N, "total": 14}`,
and exits 0. Score is communicated via `results.json`; exit code is always 0 so
SIA reads the file regardless of partial scores.

## The 14 checks

1. HTML file ≥ 4 KB
2. Starts with valid HTML
3. `<canvas>` present
4. Canvas width ≈ 560 px
5. Canvas height ≥ 600 px
6. Score element in DOM
7. Score readable after 3 s
8. Score > 0 after movement
9. Canvas has non-black pixels
10. Game alive at 12 s
11. `window.ghosts` accessible
12. All 4 ghosts released by 12 s
13. `window.pac` position coherent (no tunnel drift)
14. Zero JS errors

## Results across runs

| Run | Peak score | Lines (final) | Notes |
|-----|-----------|---------------|-------|
| run_1 | 14/14 | 323 | Perfect on gen_1 |
| run_2 | 12/14 | — | Crashed at gen_3 (pre-size-cap) |
| run_3 | 14/14 | 1143 | Bloated; gen_5 crashed |
| run_4 | 14/14 | 341 | First run with size cap |
| run_5 | 14/14 | 381 | Stable; all 5 gens completed |

## Known issues

- **Intermittent empty lemonade response**: lemonade occasionally returns HTTP 200
  with empty content. When this hits the meta-agent, the generation produces a
  zero-byte `target_agent.py` and fails immediately. Delete the run directory and
  re-run with the same `--run_id`.
- **Meta-agent regresses from 14/14**: when the previous generation is already
  perfect, the meta-agent still attempts "improvements" and may introduce bugs.
  Scores typically recover within 1–2 further generations.
