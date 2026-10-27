# 3. Set up a project

Run the setup once per repository, new or existing:

```text
/agent-team:setup                  (Claude Code)
use the setup skill                (Codex, OpenCode)
```

It works on a branch, `chore/agent-team-setup`, shows every change before
making it, and ends with a commit you can review as a merge request.

## The steps

1. **Profile.** A few questions decide which parts of the template the
   project gets: tools, CI, issue tracker, roles, features (below).
2. **Install.** Only the files of the profile are copied. Existing files are
   never overwritten: the ones that differ are shown to you and merged with
   your approval.
3. **Interview.** Project name, stack, commands, folders per role, design
   system, models. If the repository already has code, the agent reads it
   first and turns what it finds into proposals you only confirm.
4. **Edits and checks.** The agent fills in the template with your answers
   and runs the checks: scripts, workflows, hooks, the tools' own validation.
5. **Skills.** It proposes skills for your stack (React, Postgres, GitHub
   Actions...) and installs them only after your yes, in a commit of their own.
6. **Project design.** A [design studio](04-run-the-project.md#design) session
   writes `docs/design/project.md`: goal, users, scope, roadmap by milestone.
   The setup is not finished without it.
7. **Foundations**, in a new repository: the spec of a walking skeleton
   (structure, contract, database, tests, green CI), the first task to build.
8. **Issues**, if you use a tracker: the roadmap becomes milestones and
   issues, after a dry run you approve.

## The profile

The profile says which parts of the template your project uses. It lives in
`.agent-team/config.json`:

```json
{
  "harnesses": ["claude", "codex"],
  "runners": {"optimizer": "codex"},
  "ci": "github",
  "tracker": "github",
  "roles": ["designer", "frontend", "backend", "devops", "optimizer", "security"],
  "features": ["ci-agents", "split", "dispatch"]
}
```

| Key | Values | Meaning |
|---|---|---|
| `harnesses` | `claude`, `codex`, `opencode` | the tools people and CI use; the first one leads and runs every role not listed in `runners` |
| `runners` | role → tool | roles that run on another tool, for example the optimizer on Codex |
| `ci` | `github`, `gitlab`, `both`, `none` | the CI platform of the project |
| `tracker` | `github`, `gitlab`, `local`, `jira`, `linear`, `redmine`, `none` | where the issues live ([4. Run the project](04-run-the-project.md#issues)) |
| `roles` | the six roles | drop the ones you do not need |
| `features` | `ci-agents`, `team-tasks`, `split`, `dispatch`, `litellm` | agents started from issues in CI; one issue run by several roles; split proposals in CI; start ready tasks at every merge; the LiteLLM gateway |

Every template file and section belongs to some part of the profile.
Whatever your profile does not use is removed during setup, so you customize
only what you use and no agent reads instructions for a tool you do not have.
Nothing is lost: change the profile later and the upgrade brings the files
back ([8. Change and upgrade](08-change-and-upgrade.md)).

**Which profile for which scenario:**

| Scenario | Typical profile |
|---|---|
| Local | your tool(s); `ci` for the project's CI; `tracker` `none` or `local`; no features |
| Remote repository | one or more tools; `ci` and `tracker` the same platform; `ci-agents`, plus `split`, `team-tasks`, `dispatch` as you like |
| Custom orchestrator | the tools your orchestrator runs; the tracker of its intake; a `start_command` ([7. Scenario: custom](07-scenario-custom.md)) |

## What you get

| Path | What it is |
|---|---|
| `AGENTS.md` | rules for every agent and tool: boundaries, contract, alignment, merge requests, CI |
| `CLAUDE.md` | Claude Code only: imports `AGENTS.md`, plus a few Claude-specific notes |
| `docs/roles/*.md` | one prompt per role, shared by all tools |
| `docs/design/` | `project.md`, one spec per feature, templates |
| `docs/agents/` | rules by situation (workflow, alignment, merge requests, CI, splitting, team tasks) |
| `docs/alignment/` | one entry per change that other roles rely on |
| `docs/api/` | the API contract, owned by backend |
| `.claude/` | Claude Code: agents, settings with denied commands and hooks, skills |
| `.codex/` | Codex: settings, the role agents, hooks, forbidden commands |
| `.opencode/`, `opencode.json` | OpenCode: the role agents and their permissions |
| `.agents/skills/` | the project skills for Codex (and OpenCode without Claude Code) |
| `scripts/hooks/` | hooks shared by Claude Code and Codex: block commands on real environments, handoff notes, test gate |
| `.github/`, `.gitlab/`, `ci/` | the project CI and, for remote work, the agent workflows |
| `scripts/` | issues, split, dispatch, tracker check, profile |
| `.agent-team/` | the profile, and the record of the installed template that makes upgrades safe |

`SETUP.md` is the setup procedure; delete it when the setup is done.

## After the setup

- Read the open items the setup left you (secrets, labels, branch
  protection): they depend on the scenario.
- Build the foundations task first, then design the first feature with
  `/agent-team:design-studio <feature>`.
- Commit `.agent-team/`: upgrades need it.
