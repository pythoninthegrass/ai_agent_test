#!/usr/bin/env bash
# Run one or more agents against the rpncalc harness sequentially, archiving
# build/ after each run. Each run calls reset_build() internally so the
# archive must happen between runs.
#
# Usage: ./run-all-vllm.sh [--max-steps N] [--max-stalls N] [agent ...]
#
# Agents: pi, opencode, hermes (default: all three), locust (opt-in)
#
# Examples:
#   ./run-all-vllm.sh                        # run all three coding agents
#   ./run-all-vllm.sh pi                     # run only pi
#   ./run-all-vllm.sh pi hermes              # run pi then hermes
#   ./run-all-vllm.sh --max-steps 10 pi      # pi with custom step limit
#   ./run-all-vllm.sh locust                 # synthetic agentic load test only
#   DURATION=30s ./run-all-vllm.sh locust    # short smoke-test of the wiring
#
# Logs: build-pi-vllm/run.log, build-opencode-vllm/run.log, build-hermes-vllm/run.log
#       build-locust-vllm/run.log
# Status: build-pi-vllm/harness.status (etc.)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MISE="${MISE:-$HOME/.local/bin/mise}"
AGENT_TEST="${AGENT_TEST:-$(dirname "$SCRIPT_DIR")}"
MAX_STEPS="${MAX_STEPS:-20}"
MAX_STALLS="${MAX_STALLS:-8}"
VLLM_HOST="${VLLM_HOST:-localhost}"
VLLM_PORT="${VLLM_PORT:-61515}"
VLLM_HEALTH_RETRIES="${VLLM_HEALTH_RETRIES:-240}"
USERS="${USERS:-8}"
RATE="${RATE:-2}"
DURATION="${DURATION:-5m}"

cd "$AGENT_TEST"

log() { echo "$(date '+%Y-%m-%dT%H:%M:%S') [run-all-vllm] $*"; }

wait_for_vllm() {
    log "waiting for vLLM /health on ${VLLM_HOST}:${VLLM_PORT} ..."
    for i in $(seq 1 "$VLLM_HEALTH_RETRIES"); do
        if curl -sf "http://${VLLM_HOST}:${VLLM_PORT}/health" >/dev/null 2>&1; then
            log "vLLM is ready (attempt $i)"
            return 0
        fi
        sleep 5
    done
    log "ERROR: vLLM did not become healthy after $((VLLM_HEALTH_RETRIES * 5))s"
    exit 1
}

archive_build() {
    local dest="$1"
    log "archiving build/ -> $dest"
    rm -rf "$dest"
    cp -a build/ "$dest"
}

run_pi() {
    log "=== starting pi run ==="
    set +e
    $MISE exec -- ./scripts/run.py milestones \
        --model koboldcpp/qwen3-coder-next-builder \
        --max-steps "$MAX_STEPS" \
        --max-stalls "$MAX_STALLS"
    local rc=$?
    set -e
    archive_build build-pi-vllm
    log "pi run finished (rc=$rc)"
}

run_opencode() {
    log "=== starting opencode run ==="
    set +e
    $MISE exec -- ./scripts/run.py opencode-milestones \
        --max-steps "$MAX_STEPS" \
        --max-stalls "$MAX_STALLS"
    local rc=$?
    set -e
    archive_build build-opencode-vllm
    log "opencode run finished (rc=$rc)"
}

run_hermes() {
    log "=== starting hermes run ==="
    set +e
    $MISE exec -- ./scripts/run.py hermes-milestones \
        --max-steps "$MAX_STEPS" \
        --max-stalls "$MAX_STALLS"
    local rc=$?
    set -e
    archive_build build-hermes-vllm
    log "hermes run finished (rc=$rc)"
}

run_locust() {
    log "=== starting locust stress run ==="
    set +e
    $MISE exec -- ./scripts/run.py stress \
        --users "$USERS" \
        --rate "$RATE" \
        --duration "$DURATION"
    local rc=$?
    set -e
    # build-locust-vllm/ is created by run.py stress directly; nothing to archive.
    log "locust run finished (rc=$rc)"
}

print_summary() {
    local agents=("$@")
    log "=== all runs complete ==="
    echo ""
    echo "Results:"
    for agent in "${agents[@]}"; do
        local status_file="build-${agent}-vllm/harness.status"
        if [[ -f "$status_file" ]]; then
            echo "  $agent: $(cat "$status_file")"
        else
            echo "  $agent: no harness.status found"
        fi
    done
}

main() {
    # Parse options
    while [[ $# -gt 0 && "$1" == --* ]]; do
        case "$1" in
            --max-steps) MAX_STEPS="$2"; shift 2 ;;
            --max-stalls) MAX_STALLS="$2"; shift 2 ;;
            *) echo "Unknown option: $1" >&2; exit 1 ;;
        esac
    done

    # Remaining positional args are agent names; default to all three
    local agents=("${@:-pi opencode hermes}")
    if [[ $# -eq 0 ]]; then
        agents=(pi opencode hermes)
    else
        agents=("$@")
    fi

    wait_for_vllm

    for agent in "${agents[@]}"; do
        case "$agent" in
            pi)       run_pi ;;
            opencode) run_opencode ;;
            hermes)   run_hermes ;;
            locust)   run_locust ;;
            *) echo "Unknown agent: $agent (choose from: pi, opencode, hermes, locust)" >&2; exit 1 ;;
        esac
    done

    print_summary "${agents[@]}"
}

main "$@"
