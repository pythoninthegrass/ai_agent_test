#!/usr/bin/env bash
# Usage: hidden/run_trials.sh <tiel|oxcoder|escalate>-<n> ...; escalate runs Tiel through the local/escalate route (judge-driven escalation), the others through local/coding; runs the opencode 18-milestone harness once per label, swapping the efficient-tier engine and Switchyard routes, archiving each build to build-trials/<label> with hidden-suite score and request counts.
set -u
AT=/home/lance/git/ai_agent_test
SW=/home/lance/git/linux_setup/docker/switchyard
OUT=$AT/build-trials
MISE=/home/lance/.local/bin/mise

wait_healthy() {
  for _ in $(seq 1 80); do
    [ "$(docker inspect "$1" --format '{{.State.Health.Status}}' 2>/dev/null)" = healthy ] && return 0
    sleep 15
  done
  return 1
}

use_model() {
  cd "$SW" || exit 1
  case $1 in
    tiel)
      docker stop oxcoder >/dev/null 2>&1
      docker compose up -d tiel && wait_healthy tiel || return 1
      ROUTES_FILE=routes.toml docker compose up -d --force-recreate --no-deps switchyard ;;
    oxcoder)
      docker stop tiel >/dev/null 2>&1
      docker compose --profile oxcoder up -d oxcoder && wait_healthy oxcoder || return 1
      ROUTES_FILE=routes.oxcoder.toml docker compose up -d --force-recreate --no-deps switchyard ;;
  esac
  sleep 10
  curl -s localhost:61521/v1/chat/completions -H 'content-type: application/json' \
    -d '{"model":"local/coding","messages":[{"role":"user","content":"hi"}],"max_tokens":8}' | jq -r .model
}

for label in "$@"; do
  model=${label%-*}
  route=local/coding
  [ "$model" = escalate ] && { model=tiel; route=local/escalate; }
  echo "=== $label: switching engine to $model ($(date -Is))"
  use_model "$model" || { echo "engine switch failed for $label"; exit 1; }
  cd "$AT" || exit 1
  start_iso=$(date -u +%FT%TZ); start_s=$(date +%s)
  timeout 3h "$MISE" exec -- ./scripts/run.py opencode-milestones --model "switchyard/$route" --step-timeout 600 > "$OUT/$label.out" 2>&1
  end_iso=$(date -u +%FT%TZ); wall=$(( $(date +%s) - start_s ))
  rm -rf "${OUT:?}/$label" && cp -a build "$OUT/$label"
  {
    echo "label=$label wall_seconds=$wall start=$start_iso end=$end_iso"
    cat build/harness.status
    echo "--- hidden suite"
    hidden/score.sh "$OUT/$label"
    echo "--- requests"
    hidden/count_requests.sh "$start_iso" "$end_iso"
  } > "$OUT/$label.summary" 2>&1
  echo "=== $label done ($(date -Is)): $(head -2 "$OUT/$label.summary" | tr '\n' ' ')"
done
echo ALL_TRIALS_DONE
