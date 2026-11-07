#!/bin/bash
# ci/agent-mr.sh <harness>: after a Codex or OpenCode job on GitLab, commit the
# agent's change on a branch, push it and open the merge request. The agent's
# final message (/tmp/agent-summary.md) becomes the description. A pipeline run
# on the branch of an open merge request (iterating on it) pushes there and adds
# the message as a note instead. Claude jobs open their MR themselves. Needs
# GITLAB_ACCESS_TOKEN (api, write_repository).
set -euo pipefail
H="${1:-agent}"
SUMMARY=/tmp/agent-summary.md
if [ -z "$(git status --porcelain)" ]; then
  echo "The $H agent changed nothing."
  [ -s "$SUMMARY" ] && cat "$SUMMARY"
  # a request that was only a check: the answer goes to the issue
  [ -n "${TASK_ID:-}" ] && [ -s "$SUMMARY" ] && glab issue note "$TASK_ID" --message "$(cat "$SUMMARY")"
  exit 0
fi
ROLE="${AI_FLOW_ROLE:-agent}"
BRANCH="agent/$ROLE-${TASK_ID:-$CI_PIPELINE_ID}"
MR=""
if [ -n "${CI_COMMIT_BRANCH:-}" ] && [ "$CI_COMMIT_BRANCH" != "$CI_DEFAULT_BRANCH" ]; then
  MR=$(glab mr list --source-branch "$CI_COMMIT_BRANCH" --output json | jq -r '.[0].iid // empty')
  [ -n "$MR" ] && BRANCH="$CI_COMMIT_BRANCH"
fi
git config user.name "$H agent"
git config user.email "$H-agent@$CI_SERVER_HOST"
git checkout -B "$BRANCH"
git add -A
git commit -q -m "$ROLE: task ${TASK_ID:-$CI_PIPELINE_ID}"
git push -q "https://oauth2:${GITLAB_ACCESS_TOKEN}@${CI_SERVER_HOST}/${CI_PROJECT_PATH}.git" "HEAD:refs/heads/$BRANCH"
if [ -n "$MR" ]; then
  glab mr note "$MR" --message "$(cat "$SUMMARY" 2>/dev/null || echo "The $H agent ($ROLE) pushed a change.")"
  exit 0
fi
{ cat "$SUMMARY" 2>/dev/null || true; [ -n "${TASK_ID:-}" ] && printf '\n\nCloses #%s\n' "$TASK_ID"; } > /tmp/mr.md
glab mr create --source-branch "$BRANCH" --target-branch "$CI_DEFAULT_BRANCH" \
  --title "$ROLE: task ${TASK_ID:-$CI_PIPELINE_ID}" --description "$(cat /tmp/mr.md)" --yes
impact=$(awk '/^## Alignment impact/{f=1;next} /^## /{f=0} f && NF' /tmp/mr.md | head -1)
if [ -n "$impact" ] && ! printf '%s' "$impact" | grep -qi '^none'; then
  glab mr update "$BRANCH" --label alignment-needed || true
fi
