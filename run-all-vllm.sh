#!/usr/bin/env bash
# Run all three agents against the rpncalc harness sequentially, archiving
# build/ after each run. Each run calls reset_build() internally so the
# archive must happen between runs.
#
# Usage: ./run-all-vllm.sh [--max-steps N] [--max-stalls N]
#
# Logs: build-pi-vllm/run.log, build-opencode-vllm/run.log, build-hermes-vllm/run.log
# Status: build-pi-vllm/harness.status (etc.)

set -euo pipefail

MISE=/home/lance/.local/bin/mise
PI_TEST=/home/lance/git/pi_test
MAX_STEPS="${MAX_STEPS:-20}"
MAX_STALLS="${MAX_STALLS:-8}"

cd "$PI_TEST"

log() { echo "$(date '+%Y-%m-%dT%H:%M:%S') [run-all-vllm] $*"; }

wait_for_vllm() {
    log "waiting for vLLM /health on :61515 ..."
    for i in $(seq 1 120); do
        if curl -sf http://localhost:61515/health >/dev/null 2>&1; then
            log "vLLM is ready (attempt $i)"
            return 0
        fi
        sleep 5
    done
    log "ERROR: vLLM did not become healthy after 600s"
    exit 1
}

archive_build() {
    local dest="$1"
    log "archiving build/ -> $dest"
    rm -rf "$dest"
    cp -a build/ "$dest"
}

wait_for_vllm

# ── pi ────────────────────────────────────────────────────────────────────────
log "=== starting pi run ==="
set +e
$MISE exec -- ./run.py milestones \
    --model koboldcpp/qwen3-coder-next-builder \
    --max-steps "$MAX_STEPS" \
    --max-stalls "$MAX_STALLS"
PI_RC=$?
set -e
archive_build build-pi-vllm
log "pi run finished (rc=$PI_RC)"

# ── opencode ──────────────────────────────────────────────────────────────────
log "=== starting opencode run ==="
set +e
$MISE exec -- ./run.py opencode-milestones \
    --max-steps "$MAX_STEPS" \
    --max-stalls "$MAX_STALLS"
OC_RC=$?
set -e
archive_build build-opencode-vllm
log "opencode run finished (rc=$OC_RC)"

# ── hermes ────────────────────────────────────────────────────────────────────
log "=== starting hermes run ==="
set +e
$MISE exec -- ./run.py hermes-milestones \
    --max-steps "$MAX_STEPS" \
    --max-stalls "$MAX_STALLS"
HM_RC=$?
set -e
archive_build build-hermes-vllm
log "hermes run finished (rc=$HM_RC)"

# ── summary ───────────────────────────────────────────────────────────────────
log "=== all runs complete ==="
echo ""
echo "Results:"
for agent in pi opencode hermes; do
    status_file="build-${agent}-vllm/harness.status"
    if [[ -f "$status_file" ]]; then
        echo "  $agent: $(cat "$status_file")"
    else
        echo "  $agent: no harness.status found"
    fi
done
