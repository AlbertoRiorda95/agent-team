#!/bin/bash
# scripts/hooks/security-scope.sh
# Lets the security agent reach only the hosts listed in docs/roles/security-scope.txt.
# A guardrail, not a sandbox: for real isolation run the agent where the
# network only reaches local and staging.

INPUT=$(cat)
CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
[ -z "$CMD" ] && exit 0

SCOPE_FILE="${CLAUDE_PROJECT_DIR:-.}/docs/roles/security-scope.txt"
ALLOWED=$(grep -vE '^[[:space:]]*(#|$)' "$SCOPE_FILE" 2>/dev/null | sed -E 's/[[:blank:]]+//g; /^$/d')
[ -z "$ALLOWED" ] && ALLOWED=$(printf 'localhost\n127.0.0.1')

# every host that appears in a URL must be in scope
HOSTS=$(echo "$CMD" | grep -oE '[a-zA-Z][a-zA-Z0-9+.-]*://[^/:?#"'"'"'[:space:]]+' | sed -E 's#^[^:]+://##; s#^.*@##' | sort -u)
for h in $HOSTS; do
  if ! echo "$ALLOWED" | grep -qxF "$h"; then
    echo "Blocked: $h is not in docs/roles/security-scope.txt." >&2
    echo "Test only in-scope hosts (local or staging). Ask the user if another host is needed." >&2
    exit 2
  fi
done

# no port scanners, brute-force tools or remote shells
if echo "$CMD" | grep -qE '(^|[;&|[:space:]])(nmap|masscan|hydra|medusa|nc|ncat|socat|ssh|telnet)([[:space:]]|$)'; then
  echo "Blocked: use HTTP tooling against in-scope URLs; scanners, brute-force tools and remote shells are not allowed." >&2
  exit 2
fi
exit 0
