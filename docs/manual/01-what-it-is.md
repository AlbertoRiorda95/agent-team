# 1. What Agent team is

Agent team is a way to run a software project as if you led a development
team, where the developers are AI agents. It is a plugin for Claude Code and a
set of skills for Codex and OpenCode, plus a project template that the plugin
installs and keeps up to date.

## You are the lead

You keep the decisions that a lead keeps, and you hand off the work:

| You | The team |
|---|---|
| decide what to build, in a design session with the designer | asks the questions, writes the spec and the task breakdown |
| approve the plan: which tasks, in which order, who does what | turns the plan into issues, one per role and task |
| choose what starts and when | implements each task on its own branch and opens a merge request |
| review and merge | describes every change: evidence, risk, what it did not do |
| settle conflicts between roles | flags every change other roles rely on, instead of patching their code |

Nothing reaches `main` without your merge, and agents never merge, push to
`main` or change real environments: the template blocks it in every tool it
supports.

## The team

| Role | Works on | When |
|---|---|---|
| designer | specs, design system, UI review | every feature |
| frontend | interface, client state, styles, component tests | every feature with a UI |
| backend | server, API contract, data model, migrations | every feature with data |
| devops | CI/CD, containers, infrastructure as code (never applies it) | when the feature needs it |
| optimizer | faster code with the same behavior, measured | only when you ask |
| security | assessment of the running app, local or staging only | only when you ask |

Work is split by file boundary: two agents never edit the same files in the
same round. A role prompt is written once in `docs/roles/<role>.md` and used
by every tool. You can drop roles the project does not need.

## How work flows

The same loop runs in every scenario:

1. **Design.** A design studio session with you produces a spec marked
   `ready: yes`, with its task breakdown ([4. Run the project](04-run-the-project.md#design)).
2. **Plan.** The breakdown becomes issues in your tracker, grouped by
   milestone; you can split any issue into one task per role.
3. **Start.** You start the tasks whose dependencies are done, by hand or
   automatically.
4. **Build.** Each agent works on its branch and opens a merge request.
5. **Review and merge.** You review, merge, and the next tasks can start.

What changes between scenarios is where the agents run and how a task starts.

## Three scenarios

| | Local | Remote repository | Custom orchestrator |
|---|---|---|---|
| Agents run | on your computer, in your session | in GitHub Actions or GitLab CI | where your orchestrator runs them |
| Tools | Claude Code, Codex or OpenCode | Claude Code, Codex, OpenCode, also mixed per role | any of the three |
| A task starts when | you ask in the session | you add a label or run a pipeline, or a merge frees it | your tracker or queue says so |
| Issues | optional: none, files in the repo, or any tracker | GitHub or GitLab issues | Jira, Linear, Redmine, files, or GitHub/GitLab |
| You need to be there | yes, while it works | no: you come back to merge requests | no |
| Set-up effort | minutes | an hour: secrets, labels, branch protection | days: your service to run |

- **[Local](05-scenario-local.md)**: the fastest start and the tightest
  feedback loop. Good for one person, small features and exploring.
- **[Remote repository](06-scenario-remote.md)**: the team works while you
  are away and everything leaves a trail of issues, branches and merge
  requests. Good once the project has a backlog.
- **[Custom orchestrator](07-scenario-custom.md)**: for a tracker other than
  GitHub or GitLab, your own infrastructure, queues and priorities. Good when
  the first two are not enough for a concrete reason.

You can move between them: the design, the specs and the issues stay the
same, and a profile change plus an upgrade adds or removes the files of each
scenario ([8. Change and upgrade](08-change-and-upgrade.md)).

## What you get in the repository

The plugin installs a template, then keeps only what your project uses:

- `AGENTS.md`: the rules every agent reads, in every tool;
- `docs/roles/`: one prompt per role; `docs/design/`: the project design and
  one spec per feature; `docs/agents/`: rules read only when they apply;
- the agents for your tools: `.claude/`, `.codex/`, `.opencode/`;
- CI that checks every merge request, whoever wrote it: build, tests, static
  analysis, licenses, vulnerabilities, secrets;
- for remote work, the workflows that start the agents from issues;
- `scripts/`: issues from specs, splits, starting ready tasks, the profile.

The project profile, in `.agent-team/config.json`, records which tools,
CI, tracker, roles and features you use ([3. Set up a project](03-set-up-a-project.md#the-profile)).
