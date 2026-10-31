# 3. Set up a project

<!-- nav -->
[← 2. Install](02-install.md) · [Manual index](README.md) · [4. Run the project →](04-run-the-project.md)
<!-- /nav -->

Run the setup once per repository, new or existing, in a session started in
the repository's folder:

```text
/agent-team:setup                  (Claude Code)
/agent-team:setup --to-issues      (Claude Code: also creates the issues, see below)
use the setup skill                (Codex, OpenCode)
```

It works on a new branch, `chore/agent-team-setup`, shows every change before
making it, and commits everything there, `.agent-team/` included. At the end
it offers to push the branch and open a merge request, so you can review the
setup like any other change; without a remote, the commit stays on the
branch and you merge it yourself (`git merge chore/agent-team-setup`).

## The steps

1. **Profile.** A few questions decide which parts of the template the
   project gets: tools, CI, issue tracker, roles, profile features (below).
2. **Install.** Only the files of the profile are copied. Existing files are
   never overwritten: the ones that differ are shown to you and merged with
   your approval.
3. **Interview.** Project name, stack and its commands (test, lint, build),
   the folders each role owns (for example `src/server/` for backend), whether
   the repository holds several services (a monorepo,
   [4. Monorepo](04-run-the-project.md#several-services-in-one-repository)),
   the team's own libraries to reuse and how to get them, whether this
   project is itself a package and how it is published or installed locally
   ([4. Reuse](04-run-the-project.md#reuse)), the design system, and the model and reasoning effort of each role (stronger
   models cost more per task; the setup proposes defaults). If the repository
   already has code, the agent reads it first and turns what it finds into
   proposals you only confirm.
4. **Edits and checks.** The agent fills in the template with your answers
   and runs the checks: scripts, workflows, hooks, the tools' own validation.
5. **Skills.** It proposes public skills for your stack (React, Postgres,
   GitHub Actions...), installed with `npx skills add` from their GitHub
   repositories (listed in `scripts/install-skills.sh`, which you can edit),
   only after your yes and in a commit of their own.
6. **Project design.** A [design studio](04-run-the-project.md#design) session
   writes `docs/design/project.md`: goal, users, scope, and the roadmap, a
   table of milestones (`M0`, `M1`...) and the features in each. The setup is
   not finished without it.
7. **Foundations**, in a new repository only: the spec of the walking
   skeleton (folders, services that start, the API contract served, database,
   tests, green CI, no product feature), the first task to build. In a
   repository that already builds and passes its tests there is no
   foundations spec: the setup checks the CI commands and the contract and
   lists the gaps as open items.
8. **Issues.** In the remote and custom scenarios the roadmap becomes
   milestones and issues, after a dry run you approve. With `--to-issues`
   this happens with any tracker, the local one included
   ([After the setup](#after-the-setup)).
9. **Report.** It ends with the open items, in the session: what only you
   can do (secrets, labels, branch protection, required checks), the
   foundations as the first task, the next command to run. It then asks
   whether to delete `SETUP.md`, the setup procedure, which is no longer
   needed and would otherwise be read by every agent session.

## The profile

The profile says which parts of the template your project uses. It lives in
`.agent-team/config.json`:

```json
{
  "harnesses": ["claude", "codex"],
  "runners": {"optimizer": "codex"},
  "ci": "github",
  "tracker": "github",
  "roles": ["designer", "frontend", "backend", "devops", "optimizer", "security", "writer"],
  "features": ["ci-agents", "split", "dispatch"]
}
```

| Key | Values | Meaning |
|---|---|---|
| `harnesses` | `claude`, `codex`, `opencode` | the tools people and CI use. The first one is the lead tool: it runs every role not listed in `runners` |
| `runners` | role → tool | roles that run on another tool, for example the optimizer on Codex |
| `ci` | `github`, `gitlab`, `both`, `none` | the CI platform of the project |
| `tracker` | `auto`, `github`, `gitlab`, `local`, `jira`, `linear`, `redmine`, `none` | where the issues live ([4. Issues](04-run-the-project.md#issues)); `auto` means GitHub or GitLab from the Git remote, `local` without one |
| `roles` | the six roles | drop the ones you do not need |
| `features` | see below | optional parts |

**Profile features** add files for things that happen *automatically or in
CI*. They do not gate the commands: `/agent-team:split-issue`,
`/agent-team:dispatch` and the others work in any profile with a tracker.

| Feature | What it adds |
|---|---|
| `ci-agents` | the workflows (GitHub) or jobs (GitLab) that run an agent when a task starts: the remote scenario |
| `team-tasks` | [team tasks](04-run-the-project.md#team-tasks): one agent does a whole issue across several roles, without subagents |
| `split` | the split proposed on the issue itself in CI, when you add the `agent:split` label |
| `dispatch` | GitHub: dispatch runs by itself every time an issue closes |
| `spec-sync` | the issues are updated by themselves every time a spec change is merged ([4. When a spec changes](04-run-the-project.md#when-a-spec-changes-after-its-issues-exist)) |
| `litellm` | a LiteLLM gateway, to reach many model providers with a budget per role ([7. LiteLLM](07-scenario-custom.md#litellm-one-gateway-for-many-providers)) |

Every template file and section belongs to some part of the profile.
Whatever your profile does not use is removed during setup, so you customize
only what you use and no agent reads instructions for a tool you do not have.
Nothing is lost: change the profile later and the upgrade brings the files
back ([8. Change and upgrade](08-change-and-upgrade.md)).

**Which profile for which scenario:**

| Scenario | Typical profile |
|---|---|
| Local | your tool(s); `ci` for the project's CI; `tracker` `none`, `local` or the one you already use; `spec-sync` with a tracker, if you like |
| Remote repository | one or more tools; `ci` and `tracker` the same platform; `ci-agents`, plus `team-tasks`, `split`, `dispatch`, `spec-sync` as you like |
| Custom orchestrator | the tools your orchestrator runs; the tracker of its intake; a `start_command` ([7. Scenario: custom](07-scenario-custom.md)) |

## What you get

| Path | What it is |
|---|---|
| `AGENTS.md` | rules for every agent and tool: folders per role, API contract, alignment, merge requests, CI |
| `CLAUDE.md` | Claude Code only: imports `AGENTS.md`, plus a few Claude-specific notes |
| `docs/roles/*.md` | one prompt per role, shared by all tools |
| `docs/design/` | `project.md`, one spec per feature, the templates of both |
| `docs/agents/` | rules by situation (workflow, alignment, merge requests, CI, splitting) |
| `docs/alignment/` | one entry per change that other roles rely on |
| `docs/api/` | the API contract, owned by backend |
| `docs/design-decisions.md` | a log of decisions, one entry each (date, decision, reason), written by agents and people |
| `.claude/` | Claude Code: agents, settings with denied commands and hooks, skills |
| `.codex/` | Codex: settings, the role agents, hooks, forbidden commands |
| `.opencode/`, `opencode.json` | OpenCode: the role agents and their permissions |
| `.agents/skills/` | the project skills for Codex (and OpenCode without Claude Code) |
| `.mcp.json` | the MCP servers the agents may use: empty, yours to fill |
| `scripts/hooks/` | hooks run by Claude Code and Codex at fixed moments: block commands on real environments, point a new session to the latest handoff note, refuse to end a task while the tests fail (the **test gate**); with Claude Code, keep each role's agent within its limits (the writer writes only documentation, the security agent reaches only the hosts in its scope) |
| `.github/`, `.gitlab/` | the CI of the project and, for remote work, the agent workflows |
| `ci/` | scripts the CI of both platforms calls: the security scanners and their versions, the merge request of a Codex or OpenCode job |
| `scripts/` | issues, split, dispatch, tracker check, profile |
| `.agent-team/` | the profile, and a copy of the installed template that makes upgrades safe: keep it committed |

## After the setup

- Do the open items the setup listed (secrets, labels, branch protection):
  they depend on the scenario, and chapters 5 to 7 explain each one.
- Build the foundations first. With a tracker, its tasks are issues: start
  them with `/agent-team:dispatch`. Without one, ask the main session:
  "implement docs/design/foundations.md".
- Then design the next features: `/agent-team:design-studio --milestone M1`
  for all the features of milestone M1, or `/agent-team:design-studio <feature>`
  for one.
- With `--to-issues` the setup does not stop at the design: it creates the
  issues right away, with any tracker, the local one included, without
  waiting for the merge of the setup merge request. The foundations tasks are
  ready to start; every other feature of the roadmap gets a
  `Design: <feature>` issue in its milestone (a placeholder for its design
  session). It stops there: merge the setup merge request, then start the
  foundations with `/agent-team:dispatch`, which waits for that merge anyway
  ([4. The workflow](04-run-the-project.md#the-workflow)).

---

<!-- nav -->
[← 2. Install](02-install.md) · [Manual index](README.md) · [4. Run the project →](04-run-the-project.md)
<!-- /nav -->
