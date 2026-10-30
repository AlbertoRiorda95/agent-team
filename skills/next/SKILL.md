---
name: next
description: Tell the user where the agent-team project stands and which agent-team command to run next. Use when the user asks what to do next, what they can do, or which skills or commands exist.
argument-hint: "(no arguments)"
---

Tell the user where the project stands and what to do next. Talk to the user in
their language. This skill only reads: it changes no file, issue or workflow,
and it never runs a script with `--apply`.

## 1. Read the state

Run from the project root. Scripts are in `scripts/` of the project if it has
them together with `scripts/agentteam/`, otherwise in
`${CLAUDE_PLUGIN_ROOT}/template/scripts/`.

- The profile: `python3 <scripts>/agent-team.py profile`. If the project has no
  profile or no `docs/design/`, it has no template yet: say so and point to
  `/agent-team:setup`.
- `docs/design/project.md`: is it there, does it have a roadmap, is it `ready`?
- The specs in `docs/design/*.md`: which are `ready: yes` and which are not.
- Only with a tracker in the profile:
  - `python3 <scripts>/tracker.py list`: issues created, open and closed, and
    merge requests waiting for review;
  - `python3 <scripts>/dispatch.py` (without `--apply`): what is running, what
    would start, what waits.

If a script fails (no tracker reachable, missing token), say it in one line and
answer with what you could read.

## 2. Answer in a few lines

1. **State**: design ready or not, issues created or not, tasks running and
   waiting, merge requests to review.
2. **Next**: one or two steps, each with the exact command:
   - design missing or not ready: `/agent-team:design-studio <feature>` (or
     `project` for the project design); with several "Design:" features in
     the same milestone, `/agent-team:design-studio --milestone <M0>` designs
     them in one session; add `--to-issues` to go on to the issues and the
     split, stopping before dispatch;
   - ready specs without issues: `/agent-team:create-issues`;
   - a big issue: `/agent-team:split-issue <n>`;
   - tasks that can start: `/agent-team:dispatch`;
   - merge requests waiting: review them first, then dispatch again;
   - project behind the plugin or profile to change: `/agent-team:upgrade`.
3. **All commands**, in one line: `setup`, `design-studio`, `create-issues`,
   `split-issue`, `dispatch`, `upgrade` (all `/agent-team:<name>`), plus `next`.

Add that the user can type these commands from the Claude app too (Remote
Control), and that each one shows its plan and asks before changing anything.

## In Codex or OpenCode

`${CLAUDE_PLUGIN_ROOT}` is the plugin folder in Claude Code. In Codex or
OpenCode, which load these skills from `~/.agents/skills/`, use the folder where
the agent-team repository is cloned (`$AGENT_TEAM_HOME`) instead.
