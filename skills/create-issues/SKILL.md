---
name: create-issues
description: Use when the roadmap and ready specs in docs/design/ should become issues. Creates the milestones and issues (GitHub, GitLab, local files, Jira, Linear or Redmine) from the roadmap and the ready specs, but only after showing the plan and getting the user's yes; nothing is created before. Idempotent - existing issues and milestones are skipped, "Design:" issues of features now specified become the feature or its task, nothing is closed or labeled - so it can be run again at any stage, for example after every design studio session.
argument-hint: "[--team]"
---

Create the issues of the project's roadmap and ready specs. Talk to the user in
their language.

Every command below is one shell call, and every call re-reads the whole
conversation: keep to the two calls of the plan and the creation.

## 1. Show the plan

At least `docs/design/project.md` with a `## Roadmap`, or one spec with
`ready: yes`, must exist; otherwise suggest `/agent-team:design-studio` and
stop. Then run, from the project root, in one call (the project's scripts if it
has them with `scripts/agentteam/`, else the plugin's; add `--team` if the user
passed it: one `agent:team` issue per ready spec):

```bash
S=scripts; [ -d scripts/agentteam ] || S="${CLAUDE_PLUGIN_ROOT}/template/scripts"; python3 "$S/create-issues.py" --dry-run
```

It reads the tracker itself: by default GitHub or GitLab from the Git remote,
or what `.agent-team/config.json` chooses (`docs/general/trackers.md`). Exit
code 2 means the tracker cannot be reached: say what to do (push the
repository, `gh auth login`, the tracker's variables) and stop; do not run
`tracker.py check` first. Do not compare the project's scripts with the
plugin's: that is `/agent-team:upgrade`'s job.

Summarize the output in a few lines, only what it holds:

- milestones and issues to create, per milestone, with their dependencies;
- issues that exist, or would get a milestone they lack;
- "Design:" issues renamed now that their spec is ready (`rename #81 ...`):
  with one row the issue becomes that task, with several the feature issue,
  with the tasks as its sub-issues;
- issues rewritten from a changed spec row (task not started), and tasks that
  started before their row changed (the user checks the work or stops it);
- issues created earlier that are no longer in the plan (never closed by the
  script: the user decides).

If the output reports milestone issues from the old layout ("M0 · ..." parent
issues), explain that milestones are now native and offer
`--migrate --dry-run` first, then `--migrate` on the user's yes. If there is
nothing to create or change, stop here.

## 2. Create

Only after the user's yes, run the same command without `--dry-run`. Report
in a few lines what was created. No labels are added: an agent starts only
when the user adds `agent:<role>` to a task issue, or with
`/agent-team:dispatch`.

## Without an agent session

The user can do the same in a terminal, with no tokens:
`python3 scripts/create-issues.py --ask` shows the plan and asks y/N before
creating it.

## What this never does

It never closes or relabels an issue. The only changes to existing issues are
giving a milestone to one that has none, rewriting a "Design:" issue whose
spec is now ready into its feature or task, and rewriting a task that has not
started from its changed spec row, as above. Running it twice creates
nothing new.

## In Codex or OpenCode

`${CLAUDE_PLUGIN_ROOT}` is the plugin folder in Claude Code. In Codex or
OpenCode, which load these skills from `~/.agents/skills/`, use the folder where
the agent-team repository is cloned (`$AGENT_TEAM_HOME`) instead.
