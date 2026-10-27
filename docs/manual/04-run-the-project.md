# 4. Run the project

This chapter is the same in every scenario: how you design, plan, start,
review and keep the team aligned. The scenario chapters only add how agents
run and how a task starts.

## Design

Large decisions are made in a design studio session between you and the
designer, never in the middle of a task:

```text
/agent-team:design-studio login        (Claude Code, with the plugin)
/design-studio login                   (Claude Code or OpenCode, in the project)
use the design-studio skill for login  (Codex)
```

The designer asks in rounds of at most five numbered questions, each with a
recommended answer, so you can reply in one line ("1 yes, 2 yes, 3: option B").
Facts it can find in the repository, it looks up instead of asking. The rounds
go from goal and user flows to screens, data and API, **test seams** (the
interfaces the tests go through), the **task breakdown** and a readiness check.

The result is a spec, `docs/design/<feature>.md`, written as the session goes,
so you can stop and resume. It is marked `ready: yes` only when no question is
left open. Its task breakdown lists one row per task: role, what, dependencies.
The first session of a project writes `docs/design/project.md`, whose roadmap
lists the milestones (`M0`, `M1`...) and the features in each.

Agents implement only what a ready spec says: a task without one stops and
asks. Run the design studio again to revise a spec: past decisions are kept,
and rows that already have an issue are not rewritten.

## Issues

With a tracker, the roadmap and the ready specs become issues:

```text
/agent-team:create-issues       or      python3 scripts/create-issues.py --dry-run
                                         python3 scripts/create-issues.py
```

- one **milestone** per roadmap milestone (a version in Jira and Redmine, a
  project milestone in Linear);
- in it, one **issue per row** of every ready spec's breakdown, with the
  role, the spec, the acceptance criteria and the dependencies;
- one **"Design: <feature>"** issue for every feature that has no spec yet.

It shows the plan first and creates only on your yes. It adds no labels, so
nothing starts on its own. Running it again creates only what is missing, so
run it after every design session. With `--team`, a spec that allows it
becomes one team issue instead of one issue per task.

Supported trackers: GitHub, GitLab, Jira, Linear, Redmine, and plain Markdown
files in `docs/tasks/` for a project without a tracker. Check the connection
before the first run:

```bash
python3 scripts/tracker.py check     # which tracker, authenticated, readable; writes nothing
python3 scripts/tracker.py list      # open issues: role, milestone, dependencies, started or not
```

Credentials come from environment variables, never from files:
`JIRA_EMAIL` and `JIRA_API_TOKEN` (or `JIRA_PAT`), `LINEAR_API_KEY`,
`REDMINE_API_KEY`; `gh` or `glab` must be logged in for GitHub and GitLab.

## Split

An issue written by hand ("orders: filter by date") often needs several
roles. Splitting turns it into one task issue per role, as sub-issues in the
same milestone:

```text
/agent-team:split-issue 42
```

The agent reads the issue, the spec and the existing sub-issues, and proposes
a plan: a table of tasks with role, dependencies, acceptance criteria and the
folders each one touches. You change it in the conversation until it is right.
Only after your yes, the plan is posted on the issue and a script creates
exactly those issues: the model does not create anything itself. Running it
again creates nothing new.

In the remote scenario you can also split from the issue itself
([6. Scenario: remote](06-scenario-remote.md#split-from-the-issue)).

## Start

A task starts when its dependencies are merged. You can start tasks one by
one, or let dispatch pick the ready ones:

```text
/agent-team:dispatch        or      python3 scripts/dispatch.py           (the plan)
                                     python3 scripts/dispatch.py --apply   (start it)
```

Dispatch takes the first open milestone, counts what is running, and starts
the tasks whose dependencies are all closed as completed: by default one per
role and three in total (`--per-role`, `--max`). It never starts optimizer or
security, "Design:" issues, or issues marked `hold`.

What "start" means depends on the scenario: a label that starts a CI job, a
GitLab pipeline, a command of your orchestrator, or a printed instruction for
a local session. That is the *starter* ([9. Reference](09-reference.md#starters)).

## Review and merge

Every merge request describes itself in the same sections:

- **Summary**: what changed and why.
- **Evidence**: before and after; screenshots for UI changes.
- **Merge danger**: can it simply be reverted, or does it migrate data or
  break a client; who feels it.
- **Not done**: what the agent decided not to do.
- **Reviewer checks**: what to look at.
- **Alignment impact**: the alignment entry, or "none".

The CI checks every merge request the same way, yours or an agent's: build,
type check, tests, UI screenshots per viewport (once you turn on the UI tests), static analysis (only the
findings the change introduces fail it), licenses, vulnerabilities, secrets.
Turn on branch protection so `main` only moves through merge requests that
are up to date and green.

You merge. Closing the issue frees the role's slot and its dependents can start.

## Alignment

When an agent changes something other roles rely on (the API contract, the
data model, a shared component, a route, an environment variable), it does not
fix their code. It writes an entry in `docs/alignment/` and flags the merge
request with an "Alignment impact" section and, in CI, the `alignment-needed`
label.

- **In a local session** the lead handles it right away: designer reviews the
  change against the specs and writes the follow-up per role, the lead
  delegates them, the entry is closed. You are asked only when designer marks
  a decision as yours (a breaking API change, a visible UX change).
- **In CI** agents never start other agents. The label is your signal: create
  the follow-up tasks, designer first.

Breaking contract changes are planned as expand-contract: add the new form,
move the callers, remove the old form last, with `main` green at every step.

## Team tasks

A small, tightly coupled feature can be one task for several roles: one
issue, one branch, one merge request. A coordinator runs the roles in order,
each one committing before the next starts. Use it when separate merge
requests would only wait on each other; prefer separate tasks otherwise.
Team tasks need the `team-tasks` feature and, in CI, Claude Code.

## On-demand roles

- **optimizer**: "use optimizer on the orders list" when a measurement shows a
  problem. It works only with green tests, and shows timings before and after.
- **security**: "run a security assessment" once the app runs, typically
  before a release. It attacks only the hosts listed in
  `docs/roles/security-scope.txt` (local or staging, never production) and
  writes a report in `docs/security/`, kept out of Git. The owning roles fix
  the findings as separate tasks.

## Long sessions

Claude Code and Codex sessions are compacted at 200,000 tokens instead of near the model's limit:
every turn re-reads the whole context, so a long session costs more and
forgets distant instructions. When a session has grown long or changes phase
(design to implementation, one task to the next), ask for a **handoff**:
`/handoff` in Claude Code and OpenCode, the handoff skill in Codex. It writes
a short note in `.handoff/`; start a new session and it continues from the
note with a small context.
