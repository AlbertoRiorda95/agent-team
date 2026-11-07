---
name: dispatch
description: Use when the user wants work to begin or to move on after a merge. Starts the task issues that are ready - no open dependency, a free slot for their role - with the project's starter (agent:<role> label on GitHub, pipeline on GitLab, a configured command such as an orchestrator, on any tracker), but only after showing the plan and getting the user's yes. Safe at any time - it never starts what is running, blocked, on hold or on-demand.
argument-hint: "[--per-role N] [--max N] [--milestone M1 | --all]"
---

Start the task issues that can run now. Talk to the user in their language.

Every command below is one shell call, and every call re-reads the whole
conversation: keep to the two calls of the plan and the start, and do not
re-run them to check what they printed.

## 1. Show the plan

Run, from the project root, in one call (the project's scripts if it has them
with `scripts/agentteam/`, else the plugin's):

```bash
S=scripts; [ -d scripts/agentteam ] || S="${CLAUDE_PLUGIN_ROOT}/template/scripts"; python3 "$S/dispatch.py" $ARGUMENTS
```

It reads the tracker itself and prints the tracker and the *starter* (what
"start" means: the `agent:<role>` label on GitHub, the agent pipeline on GitLab,
the project's `start_command`, or a printed instruction). If it fails with a
tracker error, say what to do (`gh auth login`, the tracker's variables in
`docs/general/trackers.md`) and stop: do not run `tracker.py check` first.

Tell the user, briefly and only what the output holds:

- the starter, and the scope (by default the first open milestone with tasks);
- what is running, and what would start;
- what waits and why: an open dependency, a role already busy, a spec not
  merged into the main branch yet (merge the design merge request), a row
  removed from its spec (offer to close the issue; never close it yourself);
- what would be rewritten from a changed spec row before it starts;
- what is never started automatically (optimizer, security, writer, `hold`,
  "Design:" issues), only if the output lists any.

Each start is an agent run and costs tokens or quota. The defaults are one
task per role and three in total (`--per-role`, `--max`). If nothing would
start or be updated, stop here.

## 2. Start

Only after the user's yes, run the same command with `--apply --expect <id>`,
where `<id>` is the `Plan:` line of the output. If the plan changed in the
meantime it starts nothing and exits 3: show the new plan and ask again. If a
start fails because the `agent:<role>` label does not exist (GitHub), offer
`scripts/create-labels.sh`. Report in a few lines what started.

To make this happen by itself on GitHub every time an issue closes, point the
user to `.github/workflows/dispatch.yml` (`AGENT_AUTODISPATCH` and
`AGENT_DISPATCH_TOKEN`, described at its top).

## Without an agent session

The user can do the same in a terminal, with no tokens:
`python3 scripts/dispatch.py --ask` shows the plan and asks y/N before
starting it. Mention it when the user only wants the plan carried out.

## In Codex or OpenCode

`${CLAUDE_PLUGIN_ROOT}` is the plugin folder in Claude Code. In Codex or
OpenCode, which load these skills from `~/.agents/skills/`, use the folder where
the agent-team repository is cloned (`$AGENT_TEAM_HOME`) instead.
