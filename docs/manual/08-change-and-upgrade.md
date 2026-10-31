# 8. Change and upgrade

<!-- nav -->
[← 7. Scenario: custom orchestrator](07-scenario-custom.md) · [Manual index](README.md) · [9. Reference →](09-reference.md)
<!-- /nav -->

Two things change over a project's life: the plugin gets new versions, and
your setup changes (another tracker, Codex next to Claude Code, a role back,
the move from local to remote). Both go through the same command:

```text
/agent-team:upgrade        (Claude Code)
use the upgrade skill      (Codex, OpenCode)
```

## Change the profile

Tell the upgrade what changes ("move the issues to Linear", "add Codex for
the optimizer", "we no longer need the designer") or edit
`.agent-team/config.json` yourself, then run the upgrade. It renders the
template for the new profile and shows a plan:

| Kind | What happens |
|---|---|
| `add` | a file the new profile includes: added |
| `update` | a template file you never changed: replaced with the new version |
| `merge` | changed by both you and the template: three-way merge that keeps your changes |
| `prune` | a file the profile no longer includes, never changed by you: removed |
| `out-of-profile` | a file the profile no longer includes, changed by you: kept, you decide |
| `removed-by-you` | a file you deleted: not added back |

Sections follow the same rule: drop `split` and its section leaves
`AGENTS.md`; add Codex back and its lines return, merged with your edits.
Conflicts, if any, are left marked and resolved with you. The upgrade works
on a branch and ends with a commit for you to review.

Examples:

| You want | Profile change | What the upgrade does |
|---|---|---|
| From local to remote on GitHub | `"tracker": "github"`, `"features": ["ci-agents", "dispatch"]` | adds the agent workflows, labels script, issue scripts; then the remote set-up of [chapter 6](06-scenario-remote.md#set-up-once) |
| Codex instead of Claude Code | `"harnesses": ["codex"]` | adds `.codex/` and `.agents/skills/`, removes `.claude/` and `CLAUDE.md` if unchanged, switches the CI jobs |
| Jira instead of GitHub issues | `"tracker": "jira"` plus its settings | adds the Jira adapter, removes the GitHub workflows that need GitHub issues |
| Security back | add `"security"` to `roles` | adds its prompt, agents and scope file |

After a tool change, the upgrade lists what that tool needs once: trust and
hooks for Codex, new CI secrets and variables.

Without the plugin, `python3 scripts/agent-team.py prune` removes what left
the profile, but only the upgrade can add things back.

## Upgrade to a new plugin version

1. Update the plugin ([2. Install](02-install.md#updating-the-plugin)).
2. Run `/agent-team:upgrade` in the project. It reads the release notes of
   the versions in between and explains each change, not just the file names.
3. Review the plan, exclude what you do not want, apply.
4. Do the steps listed in the release notes' "Upgrade notes": they are the
   ones a file change cannot do (new secrets, labels, required checks).

Every project stays on the template version it installed until you upgrade
it: updating the plugin changes nothing by itself.

## How your changes are kept

The setup stores a copy of every installed template file in
`.agent-team/base/`. The upgrade compares three versions of each file: that
copy, your file, and the new template file. If only the template changed,
your file is replaced; if only you changed it, nothing happens; if both
changed, `git merge-file` merges them and marks the lines it cannot decide.

`README.md`, `docs/design-decisions.md` (the decision log), `.mcp.json` (the
MCP servers the agents may use) and `docs/roles/security-scope.txt` are yours
after setup: they are never upgraded ([3. What you get](03-set-up-a-project.md#what-you-get)).

## A project set up by hand

A project copied from the template without the plugin, or set up before the
plugin existed, has no `.agent-team/base/`. The first upgrade proposes a
profile from what the project has, then compares each file that differs with
you and records the result; later upgrades are automatic. Without Claude
Code, run it from a clone:

```bash
python3 ~/agent-team/scripts/template_sync.py status --template ~/agent-team/template --project .
python3 ~/agent-team/scripts/template_sync.py apply  --template ~/agent-team/template --project .
```

---

<!-- nav -->
[← 7. Scenario: custom orchestrator](07-scenario-custom.md) · [Manual index](README.md) · [9. Reference →](09-reference.md)
<!-- /nav -->
