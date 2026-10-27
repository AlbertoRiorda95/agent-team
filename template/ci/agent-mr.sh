#!/bin/bash
# ci/agent-mr.sh <harness>: after a Codex or OpenCode job on GitLab, commit the
# agent's change on a branch, push it and open the merge request. The agent's
# final message (/tmp/agent-summary.md) becomes the description. Claude jobs open
# their MR themselves. Needs GITLAB_ACCESS_TOKEN (api, write_repository).
set -euo pipefail
H="${1:-agent}"
SUMMARY=/tmp/agent-summary.md
if [ -z "$(git status --porcelain)" ]; then
  echo "The $H agent changed nothing."
  [ -s "$SUMMARY" ] && cat "$SUMMARY"
  exit 0
fi
ROLE="${AI_FLOW_ROLE:-agent}"
BRANCH="agent/$ROLE-${TASK_ID:-$CI_PIPELINE_ID}"
git config user.name "$H agent"
git config user.email "$H-agent@$CI_SERVER_HOST"
git checkout -B "$BRANCH"
git add -A
git commit -q -m "$ROLE: task ${TASK_ID:-$CI_PIPELINE_ID}"
git push -q "https://oauth2:${GITLAB_ACCESS_TOKEN}@${CI_SERVER_HOST}/${CI_PROJECT_PATH}.git" "HEAD:refs/heads/$BRANCH"
{ cat "$SUMMARY" 2>/dev/null || true; [ -n "${TASK_ID:-}" ] && printf '\n\nCloses #%s\n' "$TASK_ID"; } > /tmp/mr.md
glab mr create --source-branch "$BRANCH" --target-branch "$CI_DEFAULT_BRANCH" \
  --title "$ROLE: task ${TASK_ID:-$CI_PIPELINE_ID}" --description "$(cat /tmp/mr.md)" --yes
impact=$(awk '/^## Alignment impact/{f=1;next} /^## /{f=0} f && NF' /tmp/mr.md | head -1)
if [ -n "$impact" ] && ! printf '%s' "$impact" | grep -qi '^none'; then
  glab mr update "$BRANCH" --label alignment-needed || true
fi
