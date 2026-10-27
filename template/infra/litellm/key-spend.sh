#!/bin/bash
# Prints the spend recorded by LiteLLM for one or more virtual keys.
# Usage: ./key-spend.sh <virtual-key> [<virtual-key>...]
# Run it before and after a task: the difference is the cost of the task.
# CUSTOMIZE: LITELLM_URL if LiteLLM is not on localhost.
set -euo pipefail
URL=${LITELLM_URL:-http://localhost:4000}
for KEY in "$@"; do
  curl -s "$URL/key/info?key=$KEY" -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
    | jq -r '.info | "\(.key_alias // "?")\t$\(.spend)"'
done
