#!/usr/bin/env bash
# tests/test_template_sync.sh: install the template into an empty project, change
# both sides, upgrade, and check that every case is handled as documented.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
SYNC="$ROOT/scripts/template_sync.py"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { echo "FAIL: $*" >&2; exit 1; }

cp -rL "$ROOT/template" "$TMP/t1"
mkdir "$TMP/proj" && git -C "$TMP/proj" init -q
echo "# My app" > "$TMP/proj/README.md"

python3 "$SYNC" install --template "$TMP/t1" --project "$TMP/proj" >/dev/null
[ -f "$TMP/proj/.agent-team/manifest.json" ] || fail "no manifest after install"
[ "$(cat "$TMP/proj/README.md")" = "# My app" ] || fail "install overwrote the project's README"
python3 "$SYNC" install --template "$TMP/t1" --project "$TMP/proj" >/dev/null 2>&1 && fail "second install did not refuse"

# a new template version, and changes on the project side
cp -r "$TMP/t1" "$TMP/t2"
sed -i 's/^- Test: `npm test`/- Test: `pnpm test`/' "$TMP/proj/AGENTS.md"             # both change this line
sed -i 's/^- Test: `npm test`/- Test: `npm run test:all`/' "$TMP/t2/AGENTS.md"
sed -i 's/^## Rules for everyone/## Rules for everyone (v2)/' "$TMP/t2/AGENTS.md"        # template only
printf '\n- project rule\n' >> "$TMP/proj/AGENTS.md"                                       # project only
echo "# upstream" >> "$TMP/t2/docs/roles/backend.md"                                       # untouched by project
echo "new" > "$TMP/t2/docs/agents/new.md"                                                  # new file
rm "$TMP/t2/docs/agents/workflow.md"                                                       # removed upstream
rm "$TMP/proj/opencode.json"                                                               # removed by project
echo "upstream" >> "$TMP/t2/README.md"                                                     # owned file

status=$(python3 "$SYNC" status --template "$TMP/t2" --project "$TMP/proj" --json)
kind() { python3 -c "import json,sys; d=json.load(sys.stdin); print({f['path']:f['kind'] for f in d['files']}.get('$1',''))" <<<"$status"; }
[ "$(kind AGENTS.md)" = merge ] || fail "AGENTS.md should be merge"
[ "$(kind docs/roles/backend.md)" = update ] || fail "backend.md should be update"
[ "$(kind docs/agents/new.md)" = add ] || fail "new.md should be add"
[ "$(kind docs/agents/workflow.md)" = removed-upstream ] || fail "workflow.md should be removed-upstream"
[ "$(kind opencode.json)" = removed-by-you ] || fail "opencode.json should be removed-by-you"
[ "$(kind README.md)" = owned ] || fail "README.md should be owned"

set +e
python3 "$SYNC" apply --template "$TMP/t2" --project "$TMP/proj" >/dev/null
rc=$?
set -e
[ $rc -eq 1 ] || fail "apply should report the conflict (exit 1), got $rc"
grep -q '^<<<<<<< project' "$TMP/proj/AGENTS.md" || fail "conflict markers missing"
grep -q '^## Rules for everyone (v2)' "$TMP/proj/AGENTS.md" || fail "template-only change not merged"
grep -q '^- project rule' "$TMP/proj/AGENTS.md" || fail "project-only change lost"
grep -q '^# upstream' "$TMP/proj/docs/roles/backend.md" || fail "safe update not applied"
[ -f "$TMP/proj/docs/agents/new.md" ] || fail "new file not added"
[ -f "$TMP/proj/docs/agents/workflow.md" ] || fail "file removed upstream was deleted"
[ ! -f "$TMP/proj/opencode.json" ] || fail "file removed by the project came back"
[ "$(cat "$TMP/proj/README.md")" = "# My app" ] || fail "owned README was changed"

# after the merge, a later status sees nothing left to do for those files
status=$(python3 "$SYNC" status --template "$TMP/t2" --project "$TMP/proj" --json)
[ "$(kind docs/roles/backend.md)" = unchanged ] || fail "backend.md should now be unchanged"
echo "template_sync: all checks passed"
