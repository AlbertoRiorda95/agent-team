#!/bin/bash
# Creates a LiteLLM virtual key for a role, with a monthly budget.
# Usage: ./create-key.sh optimizer deepseek 30   (or: optimizer mistral 30)
set -euo pipefail
ROLE=$1; MODEL=$2; BUDGET=$3
URL=${LITELLM_URL:-https://llm.your-domain.com}   # CUSTOMIZE
curl -s "$URL/key/generate" \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"key_alias\": \"$ROLE\", \"models\": [\"$MODEL\"], \"max_budget\": $BUDGET, \"budget_duration\": \"30d\"}"
echo
