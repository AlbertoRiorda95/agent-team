---
name: create-issues
description: Create the milestones and issues (GitHub, GitLab, local files, Jira, Linear or Redmine) from the roadmap and the ready specs in docs/design/, after showing the plan. Idempotent - existing issues and milestones are skipped, nothing is closed or labeled - so it can be run again at any stage, for example after every design studio session.
argument-hint: "[--team]"
disable-model-invocation: true
---

Create the issues of the project's roadmap and ready specs. Talk to the user in
their language.

## 1. Preconditions

- A reachable tracker: run `python3 <scripts>/tracker.py check` (scripts
  folder chosen as in step 2). By default the tracker is GitHub or GitLab, from
  the Git remote, with an authenticated `gh` or `glab`; `.agent-team/config.json`
  can choose local files, Jira, Linear or Redmine (see `docs/general/trackers.md`,
  or `${CLAUDE_PLUGIN_ROOT}/template/docs/general/trackers.md`). If the check
  fails, say what to do (push the repository, `gh auth login`, set the
  tracker's environment variables) and stop.
- At least `docs/design/project.md` with a `## Roadmap`, or one spec with
  `ready: yes`. Otherwise there is nothing to create: suggest
  `/agent-team:design-studio`.

## 2. Pick the script

Use `scripts/create-issues.py` from the project if it exists together with
`scripts/agentteam/`, otherwise the plugin's copy
`${CLAUDE_PLUGIN_ROOT}/template/scripts/create-issues.py`. Run it
from the project root. If the project's copy differs from the plugin's, the
project may be on an older template: mention `/agent-team:upgrade`, but use the
project's copy unless the user says otherwise.

## 3. Show the plan

Run `python3 <script> --dry-run` (add `--team` if the user passed it) and
summarize the output for the user:

- milestones to create and those that exist;
- issues to create, per milestone, with their dependencies;
- issues that exist or are tracked by the `Issue` column, and those that would
  get a milestone they do not have;
- issues created earlier that are no longer in the plan (the script never
  closes them: the user decides).

If a spec says "Team task possible: yes", ask whether the user wants one
`agent:team` issue for it (`--team`, one PR) or one issue per task.

If the output reports milestone issues from the old layout ("M0 · ..." parent
issues), explain that milestones are now native and offer
`python3 <script> --migrate --dry-run` first, then `--migrate` on the user's yes.

## 4. Create

Only after the user says yes, run the same command without `--dry-run`. Report
what was created and linked. Remind the user that no labels were added: an
agent starts only when they add `agent:<role>` to a task issue, in the order
of the dependencies, or with `/agent-team:dispatch`.

## What this never does

It never closes, relabels or rewrites an issue; the only change to an existing
issue is giving a milestone to one that has none. Running it twice creates
nothing new.

## In Codex or OpenCode

`${CLAUDE_PLUGIN_ROOT}` is the plugin folder in Claude Code. In Codex or
OpenCode, which load these skills from `~/.agents/skills/`, use the folder where
the agent-team repository is cloned (`$AGENT_TEAM_HOME`) instead.
