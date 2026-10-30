# 1. What Agent team is

<!-- nav -->
[← Manual index](README.md) · [2. Install →](02-install.md)
<!-- /nav -->

Agent team is a way to run a software project as if you led a development
team, where the developers are AI agents. It is a plugin for Claude Code and a
set of skills for Codex and OpenCode, plus a project template that the plugin
installs and keeps up to date.

This manual says **merge request** for both GitLab merge requests and GitHub
pull requests: they are the same thing. The words in **bold** below, and a few
more, are defined in [Words used in this manual](#words-used-in-this-manual).

## You are the lead

You keep the decisions that a lead keeps, and you hand off the work:

| You | The team |
|---|---|
| decide what to build, in a design session with the designer | asks the questions, writes the **spec** and its **task breakdown** |
| approve the plan: which tasks, in which order, who does what | turns the plan into issues, one per role and task |
| choose what starts and when | implements each task on its own branch and opens a merge request |
| review and merge | describes every change: evidence, risk, what it did not do |
| decide when roles disagree | flags every change other roles rely on (an **alignment** entry), instead of patching their code; you see it in the merge request ([4. Alignment](04-run-the-project.md#alignment)) |

Nothing reaches `main` without your merge, and agents never merge, push to
`main` or change real environments (deploy, apply infrastructure, push
images): the template denies those commands in Claude Code, Codex and
OpenCode, each with its own mechanism ([5. Scenario: local](05-scenario-local.md)).

## The team

| Role | Works on | When |
|---|---|---|
| designer | specs, design system, UI review | every feature |
| frontend | interface, client state, styles, component tests | every feature with a UI |
| backend | server, API contract, data model, migrations | every feature with data |
| devops | CI/CD, containers, infrastructure as code (never applies it) | when the feature needs it |
| optimizer | faster code with the same behavior, measured | only when you ask |
| security | assessment of the running app, local or staging only | only when you ask |
| writer | the software documentation: design document, ICD, user manual, install and API guides; only in `docs/software/` and the README | only when you ask |

Work is split by file boundary: each role owns some folders (you confirm
them during the setup; they are listed in `AGENTS.md`), and a task that
crosses a boundary becomes two tasks with a dependency. Dispatch runs at most
one task per role at a time by default, so two agents do not edit the same
files at once. A role prompt is written once in `docs/roles/<role>.md` and
used by every tool. You can drop roles the project does not need.

## How work flows

The same loop runs in every scenario:

1. **Design.** A design studio session with you produces a spec: a Markdown
   file in `docs/design/`, whose first lines say `ready: yes` once no question
   is left open. The designer sets it, with your approval
   ([4. Run the project](04-run-the-project.md#design)).
2. **Plan.** The task breakdown becomes issues in your tracker, grouped by
   **milestone**; you can **split** any issue into one task per role.
3. **Start.** You start the tasks whose dependencies are done, by hand or
   with **dispatch**.
4. **Build.** Each agent works on its branch and opens a merge request.
5. **Review and merge.** You review and merge; the merge closes the task's
   issue, and the tasks that waited for it can start.

What changes between scenarios is where the agents run and how a task starts.

## How the team develops

The agents do not improvise a way of working: the template builds in
established development practice, and checks it in the same way for the
agents' work as for yours.

| Practice | What it means here |
|---|---|
| **Design before code** | a feature starts as a spec you approved, with its acceptance criteria and its **test seams** (the points where the behavior is checked), not as a vague request |
| **Test-driven development** | frontend and backend preload the `tdd` skill: a failing test first, then the code that passes it, through the seams of the spec. Every new endpoint has a happy-path and an error-path test. A role agent cannot report a task finished while the suite fails (the test gate; in Codex it is a rule) |
| **Clean architecture, when it fits** | if the backend's language and framework allow it and the service has real business rules, the backend preloads the `clean-architecture` skill: business rules in the domain and use cases, dependencies pointing inward, tests that need no database. `setup` asks and removes it for a script or a thin CRUD, where layers only add weight. The frontend has its own rules: a design system, tokens, UI tests per viewport |
| **Software reuse** | before writing, the agents look for what already exists: the project's own code, then the team's libraries (listed in `docs/general/libraries.md`, consumed from a package registry), then a trusted third-party library that passes a checklist (it really exists under that name, license, maintenance, known vulnerabilities, weight). The spec records what is reused; a new dependency needs your yes and is justified in the merge request. The optimizer proposes an issue when it finds code worth sharing |
| **Small, reviewable changes** | one task per role, one branch and one merge request each, with a description that says what changed, the evidence, how dangerous the merge is and what was not done |
| **Contracts and alignment** | the API contract changes before or with the code, and a change other roles rely on is recorded and reviewed ([4. Alignment](04-run-the-project.md#alignment)) |
| **Continuous integration** | every merge request, yours or an agent's, goes through the same CI: build, type check, tests, static analysis, SBOM and licenses, vulnerabilities, secrets, misconfigurations, UI tests. A red CI is part of the task: the agent fixes the cause and never weakens the check. The `/local-ci` skill runs the same checks on your computer and fixes the failures, for convenience or when there is no real CI |
| **Security in the loop** | the agent runs a security review on its diff before opening the merge request; the CI scanners run on every change; the security role, when you add it, attacks the running application within a scope you set |
| **Humans decide** | agents never push to `main` and never merge; you review and merge, and branch protection makes the CI result binding |

These are defaults, not walls: the rules are in `AGENTS.md` and
`docs/roles/*.md`, and you can adapt them to your project. The CI is only as
good as where it runs: see
[5. Where the CI runs](05-scenario-local.md#where-the-ci-runs).

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
same, and a **profile** change plus an upgrade adds or removes the files of
each scenario ([8. Change and upgrade](08-change-and-upgrade.md)).

## What you get in the repository

The plugin installs a template, then keeps only what your project uses:

- `AGENTS.md`: the rules every agent reads, in every tool;
- `docs/roles/`: one prompt per role; `docs/design/`: the project design and
  one spec per feature; `docs/agents/`: rules for particular situations (a
  failing CI, an alignment change, a split), which `AGENTS.md` tells the
  agent to read when the situation arises;
- the agents for your tools: `.claude/`, `.codex/`, `.opencode/`;
- CI that checks every merge request, whoever wrote it: build, tests, static
  analysis, licenses, vulnerabilities, secrets;
- for remote work, the workflows that start the agents from issues;
- `scripts/`: issues from specs, splits, starting ready tasks, the profile.

The full list is in [3. What you get](03-set-up-a-project.md#what-you-get).

## Words used in this manual

| Word | Meaning |
|---|---|
| **lead** | you. The agent session you talk to in the local scenario is the **main session**: it hands each task to the role agent and reports back |
| **role agent** | an agent with one role's prompt and permissions (designer, backend...) |
| **tool**, **harness** | Claude Code, Codex or OpenCode. The profile key is `harnesses`; the first one listed is the **lead tool**, which runs every role not assigned elsewhere |
| **runner** | the tool a role runs on, when not the lead tool (`runners` in the profile) |
| **merge request** | a GitLab merge request or a GitHub pull request |
| **spec** | `docs/design/<feature>.md`: what a feature does, decided with you; `ready: yes` in its first lines when complete |
| **task breakdown** | the table at the end of a spec: one row per task, with its role and the rows it depends on |
| **project design**, **roadmap** | `docs/design/project.md`: goal, users, decisions, and the roadmap, a table of milestones and the features in each |
| **milestone** | a group of features delivered together. Its name starts with a code (`M0`, `M1`...) that commands use: "M1 Studio" is milestone `M1`, named "Studio". `M0` is usually the **foundations** |
| **feature** (of the roadmap) | one line item of a milestone, designed in one spec. Not to be confused with the **profile features** below |
| **foundations**, **walking skeleton** | the first spec of a new repository: folders, services that start, the API served, database, tests and CI green, with no product feature yet |
| **API contract** | `docs/api/openapi.yaml` (or similar): the API as agreed, owned by backend; frontend builds against it |
| **issue**, **task** | an issue in your tracker. A **task** is an issue with one role, ready to be started; most issues created from a spec are tasks |
| **"Design:" issue** | a placeholder issue, `Design: <feature> (M1 ...)`, for a roadmap feature that has no spec yet. It is not a task: the work it stands for is a design session with you. When the spec is ready, it becomes the feature's issue or its only task |
| **feature issue** | a former "Design:" issue whose spec has several tasks: the tasks are its sub-issues |
| **split** | turning one issue into one task per role, after your approval |
| **dispatch** | the command that starts the tasks that are ready: dependencies done, a free slot for the role, spec merged |
| **starter** | what "start" means for dispatch: add a label, run a pipeline, call your orchestrator, or print what to do |
| **team task** | one issue done by several roles in a row, on one branch, with one merge request |
| **alignment** | a change other roles rely on (API, data model, shared component, route, variable): recorded in `docs/alignment/` and flagged on the merge request |
| **handoff** | a short note an agent writes so a fresh session can continue without the whole history |
| **profile** | `.agent-team/config.json`: which tools, CI, tracker, roles and **profile features** (optional parts such as `ci-agents` or `dispatch`) the project uses |
| **scenario** | local, remote repository or custom orchestrator: where agents run and how tasks start |

---

<!-- nav -->
[← Manual index](README.md) · [2. Install →](02-install.md)
<!-- /nav -->
