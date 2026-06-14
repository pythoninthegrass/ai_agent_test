#!/usr/bin/env bash
# SWE-bench stress run via sweagent (uv tool, editable from ~/git/swe-agent)
#
# Usage:
#   ./run-swe-bench.sh                        # 16 workers, 50 tasks, verified
#   WORKERS=4 SLICE=:10 ./run-swe-bench.sh    # quick smoke test
#   SUBSET=lite ./run-swe-bench.sh            # SWE-bench Lite instead of Verified
#
# Artifacts land in runs/swe-bench-<subset>-<workers>w-<timestamp>/
# Score with: sweagent merge-preds + swebench evaluate (see bottom of file)

set -euo pipefail

SWEAGENT="${HOME}/.local/bin/sweagent"
CONFIG="${HOME}/git/swe-agent/config/bash_only.yaml"
API_BASE="${API_BASE:-http://127.0.0.1:61519/v1}"
API_KEY="${API_KEY:-local}"
MODEL="${MODEL:-openai/qwen3-coder-next}"
WORKERS="${WORKERS:-16}"
SUBSET="${SUBSET:-verified}"
SPLIT="${SPLIT:-test}"
SLICE="${SLICE:-:50}"
MAX_INPUT_TOKENS="${MAX_INPUT_TOKENS:-30000}"

TIMESTAMP="$(date +%Y%m%dT%H%M%S)"
OUTDIR="${HOME}/git/ai_agent_test/runs/swe-bench-${SUBSET}-${WORKERS}w-${TIMESTAMP}"

echo "=== SWE-bench run ==="
echo "  model:   ${MODEL}"
echo "  api:     ${API_BASE}"
echo "  subset:  ${SUBSET} / ${SPLIT} / ${SLICE}"
echo "  workers: ${WORKERS}"
echo "  outdir:  ${OUTDIR}"
echo ""

"${SWEAGENT}" run-batch \
    --config "${CONFIG}" \
    --agent.model.name "${MODEL}" \
    --agent.model.api_base "${API_BASE}" \
    --agent.model.api_key "${API_KEY}" \
    --agent.model.per_instance_cost_limit 0 \
    --agent.model.total_cost_limit 0 \
    --agent.model.per_instance_call_limit 0 \
    --agent.model.max_input_tokens "${MAX_INPUT_TOKENS}" \
    --num_workers "${WORKERS}" \
    --random_delay_multiplier 2 \
    --instances.type swe_bench \
    --instances.subset "${SUBSET}" \
    --instances.split "${SPLIT}" \
    --instances.slice "${SLICE}" \
    --instances.shuffle true \
    --output_dir "${OUTDIR}"

echo ""
echo "=== done: ${OUTDIR} ==="
echo ""
echo "To score:"
echo "  pip install swebench"
echo "  python -m swebench.harness.run_evaluation \\"
echo "    --predictions_path ${OUTDIR}/preds.jsonl \\"
echo "    --swe_bench_tasks princeton-nlp/SWE-bench_Verified \\"
echo "    --max_workers 8 \\"
echo "    --run_id swe-bench-${SUBSET}-${WORKERS}w-${TIMESTAMP}"
