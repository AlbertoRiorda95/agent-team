#!/bin/bash
# scripts/hooks/block-infra-commands.sh
# Blocks commands that change real environments. PreToolUse hook for Claude Code
# (.claude/settings.json) and Codex (.codex/hooks.json): both pass tool_input.command.

INPUT=$(cat)
CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
[ -z "$CMD" ] && exit 0

FORBIDDEN='terraform[[:space:]]+apply|terraform[[:space:]]+destroy|kubectl[[:space:]]+(apply|delete|patch|rollout)|helm[[:space:]]+(install|upgrade|uninstall|rollback)|docker[[:space:]]+push|podman[[:space:]]+push|aws[[:space:]]+.*[[:space:]](create|delete|update)-|gcloud[[:space:]]+.*deploy'

if echo "$CMD" | grep -qE "$FORBIDDEN"; then
  echo "Blocked: this command changes a real environment." >&2
  echo "Write the configuration and propose it in an MR: the pipeline applies it after the merge." >&2
  exit 2
fi
exit 0
