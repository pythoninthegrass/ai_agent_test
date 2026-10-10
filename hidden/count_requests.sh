#!/usr/bin/env bash
# Usage: hidden/count_requests.sh <since-iso> <until-iso>; per-model Switchyard request counts (and non-200s) in that window.
LOGS=$(docker logs switchyard --since "$1" --until "$2" 2>&1 | rg 'LLM request handled')
echo "total: $(printf '%s\n' "$LOGS" | rg -c .)"
printf '%s\n' "$LOGS" | rg -o 'selected_model="[^"]*"' | sort | uniq -c
echo "non-200: $(printf '%s\n' "$LOGS" | grep -vc "status=200")"
