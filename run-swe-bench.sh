#!/usr/bin/env bash
# SWE-bench stress run via sweagent (uv tool, editable from ~/git/swe-agent)
#
# Usage:
#   ./run-swe-bench.sh                        # 8 workers, 50 tasks, lite, fp8
#   WORKERS=4 SLICE=:4 ./run-swe-bench.sh     # quick smoke test
#   SUBSET=verified ./run-swe-bench.sh        # SWE-bench Verified instead of Lite
#
# Env vars (can be set in .env alongside this script):
#   HF_TOKEN            HuggingFace token (avoids rate limits on dataset download)
#   WORKERS             concurrent sweagent workers (default: 8)
#   SUBSET              swe_bench subset: lite or verified (default: lite)
#   SPLIT               dataset split (default: test)
#   SLICE               task slice, e.g. :50 or :10 (default: :50)
#   MAX_INPUT_TOKENS    per-session context cap (default: 65536)
#   CALL_LIMIT          max LLM turns per task, 0=unlimited (default: 75)
#   DELAY_MULTIPLIER    random inter-turn delay multiplier (default: 0)
#   API_BASE            proxy endpoint (default: http://127.0.0.1:61519/v1)
#   API_KEY             API key for the proxy (default: local)
#   MODEL               litellm model name (default: openai/qwen3-coder-next-fp8)
#
# Artifacts land in runs/swe-bench-<subset>-<workers>w-<timestamp>/
# Score with: ~/.local/bin/mise exec -- uv run --with swebench \
#   python -m swebench.harness.run_evaluation ...

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source .env if present (provides HF_TOKEN and other overrides)
if [ -f "${SCRIPT_DIR}/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "${SCRIPT_DIR}/.env"
    set +a
fi

SWEAGENT="${HOME}/.local/bin/sweagent"
CONFIG="${HOME}/git/swe-agent/config/bash_only.yaml"
API_BASE="${API_BASE:-http://127.0.0.1:61519/v1}"
API_KEY="${API_KEY:-local}"
MODEL="${MODEL:-openai/qwen3-coder-next-fp8}"
WORKERS="${WORKERS:-8}"
SUBSET="${SUBSET:-lite}"
SPLIT="${SPLIT:-test}"
SLICE="${SLICE:-:50}"
MAX_INPUT_TOKENS="${MAX_INPUT_TOKENS:-65536}"
CALL_LIMIT="${CALL_LIMIT:-75}"
DELAY_MULTIPLIER="${DELAY_MULTIPLIER:-0}"

TIMESTAMP="$(date +%Y%m%dT%H%M%S)"
OUTDIR="${HOME}/git/ai_agent_test/runs/swe-bench-${SUBSET}-${WORKERS}w-${TIMESTAMP}"

echo "=== SWE-bench run ==="
echo "  model:      ${MODEL}"
echo "  api:        ${API_BASE}"
echo "  subset:     ${SUBSET} / ${SPLIT} / ${SLICE}"
echo "  workers:    ${WORKERS}"
echo "  call_limit: ${CALL_LIMIT}"
echo "  delay_mul:  ${DELAY_MULTIPLIER}"
echo "  outdir:     ${OUTDIR}"
echo ""

"${SWEAGENT}" run-batch \
    --config "${CONFIG}" \
    --agent.model.name "${MODEL}" \
    --agent.model.api_base "${API_BASE}" \
    --agent.model.api_key "${API_KEY}" \
    --agent.model.per_instance_cost_limit 0 \
    --agent.model.total_cost_limit 0 \
    --agent.model.per_instance_call_limit "${CALL_LIMIT}" \
    --agent.model.max_input_tokens "${MAX_INPUT_TOKENS}" \
    --num_workers "${WORKERS}" \
    --random_delay_multiplier "${DELAY_MULTIPLIER}" \
    --instances.type swe_bench \
    --instances.subset "${SUBSET}" \
    --instances.split "${SPLIT}" \
    --instances.slice "${SLICE}" \
    --instances.shuffle true \
    --output_dir "${OUTDIR}"

case "${SUBSET}" in
    lite)     SWE_BENCH_DATASET="princeton-nlp/SWE-bench_Lite" ;;
    verified) SWE_BENCH_DATASET="princeton-nlp/SWE-bench_Verified" ;;
    *)        SWE_BENCH_DATASET="princeton-nlp/SWE-bench_${SUBSET}" ;;
esac

echo ""
echo "=== done: ${OUTDIR} ==="
echo ""
echo "To score:"
echo "  ~/.local/bin/mise exec -- uv run --with swebench \\"
echo "    python -m swebench.harness.run_evaluation \\"
echo "    --predictions_path ${OUTDIR}/preds.json \\"
echo "    --swe_bench_tasks ${SWE_BENCH_DATASET} \\"
echo "    --max_workers 8 \\"
echo "    --run_id swe-bench-${SUBSET}-${WORKERS}w-${TIMESTAMP}"
