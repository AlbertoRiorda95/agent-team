---
name: dispatch
description: Start the task issues that are ready - no open dependency, a free slot for their role - with the project's starter (agent:<role> label on GitHub, pipeline on GitLab, a configured command such as an orchestrator, on any tracker), after showing the plan. Safe at any time - it never starts what is running, blocked, on hold or on-demand.
argument-hint: "[--per-role N] [--max N] [--milestone M1 | --all]"
disable-model-invocation: true
---

Start the task issues that can run now. Talk to the user in their language.

## 1. Preconditions

- The script: `scripts/dispatch.py` in the project if it exists together
  with `scripts/agentteam/`, otherwise
  `${CLAUDE_PLUGIN_ROOT}/template/scripts/dispatch.py`. Run it from the
  project root.
- A reachable tracker: `python3 <scripts>/tracker.py check`. It also prints
  the *starter*, which decides what "start" means: the `agent:<role>` label
  (GitHub), the agent pipeline (GitLab), the project's `start_command` (for
  example an orchestrator) or a printed instruction. Tell the user which one
  applies before anything starts.
- On GitHub the `agent:<role>` labels must exist (`gh label list`); if they
  do not, offer to run `scripts/create-labels.sh` first.

## 2. Show the plan

Run `python3 <script> $ARGUMENTS` (without `--apply`) and explain the output:

- the scope (by default the first open milestone that still has tasks);
- what is running now, and what would start;
- what waits, and for what: an open dependency, or a role already busy;
- what is never started automatically: optimizer and security (on-demand),
  issues with the `hold` label, "Design:" issues.

Each start is an agent run, so it costs tokens or subscription quota. The
defaults are one task per role and three in total; the user can change them
with `--per-role` and `--max`.

## 3. Start

Only after the user's yes, run the same command with `--apply`. Report what
started and what will start next, as the running tasks are merged.

To make this happen by itself on GitHub every time an issue closes, point the
user to `.github/workflows/dispatch.yml`: it needs the `AGENT_AUTODISPATCH`
variable and the `AGENT_DISPATCH_TOKEN` secret described at its top.

## In Codex or OpenCode

`${CLAUDE_PLUGIN_ROOT}` is the plugin folder in Claude Code. In Codex or
OpenCode, which load these skills from `~/.agents/skills/`, use the folder where
the agent-team repository is cloned (`$AGENT_TEAM_HOME`) instead.
