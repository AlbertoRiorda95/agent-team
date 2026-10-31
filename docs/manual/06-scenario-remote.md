# 6. Scenario: remote repository

<!-- nav -->
[← 5. Scenario: local](05-scenario-local.md) · [Manual index](README.md) · [7. Scenario: custom orchestrator →](07-scenario-custom.md)
<!-- /nav -->

The team works in your GitHub or GitLab CI. A task is an issue; you start it
with a label (GitHub) or a pipeline (GitLab); the agent runs in a job, pushes
a branch and opens a merge request. You come back to review and merge.
Everything in [4. Run the project](04-run-the-project.md) applies.

## Why use it

| Good for | Watch out |
|---|---|
| You do not need to be there: start tasks, close the laptop, review the merge requests later | Slower feedback: a mistake shows up in the merge request, not while it happens |
| Several tasks in parallel, each in a clean environment | Every run costs tokens (or subscription quota) and CI minutes |
| A full trail: issue, plan comment, branch, merge request, CI results | An hour of set-up: secrets, labels, branch protection, required checks |
| The whole team (people too) sees the same board: issues, milestones, merge requests | Agents in CI never start other agents: alignment follow-ups are yours to create |
| Merges can start the next tasks automatically | Untrusted text: issues are read as task descriptions, and only members can start agents |
| Several tools in one project, chosen per role | A Codex or OpenCode job on GitLab is not yet proven on real runners: try it on a test task |

Choose it once the project has a backlog, when you want work to continue
while you are away, or when several people review the team's work.

## Profile

```json
{"harnesses": ["claude"], "ci": "github", "tracker": "github",
 "features": ["ci-agents", "team-tasks", "split", "dispatch"]}
```

With several tools, list them and assign roles to the others:
`"harnesses": ["claude", "codex"], "runners": {"optimizer": "codex"}`. The
workflows cannot read this file, so on GitHub the same routing goes in the
`AGENT_RUNNERS` variable too (step 4 below).

## GitHub

### Set up once

1. **Secrets** (Settings → Secrets and variables → Actions), for the tools
   in your profile:

   | Tool | Secrets | Variables |
   |---|---|---|
   | Claude Code | `ANTHROPIC_API_KEY`, or `CLAUDE_CODE_OAUTH_TOKEN` for a subscription (`claude setup-token`) | |
   | Codex | `OPENAI_API_KEY`; `AGENT_PR_TOKEN` (optional, see below) | `CODEX_MODEL` (optional) |
   | OpenCode | the keys of your providers, or the LiteLLM key | `OPENCODE_MODEL` (`provider/model`) |

   For Claude Code, also install the GitHub app: `/install-github-app` in a
   Claude Code session. With a subscription token, edit the workflows that run
   Claude (`agents.yml`, `claude.yml`, `claude-review.yml`, `split.yml`): in
   each, comment out the `anthropic_api_key:` line and uncomment the
   `claude_code_oauth_token:` line next to it.
2. **Labels**: `./scripts/create-labels.sh` creates `agent:<role>` for your
   roles, `agent:team`, `agent:split`, `hold`, `alignment-needed`, `ai-review`.
3. **Branch protection** on `main`: pull requests only, the CI checks
   required, "Require branches to be up to date before merging".
4. **Routing**, with more than one tool: the `AGENT_RUNNERS` repository
   variable says which role runs where, keyed by label, for example
   `{"agent:frontend":"opencode","agent:optimizer":"codex"}`. Keep it in line
   with `runners` in the profile: the workflows read only the variable. The
   other roles run on the first tool of the profile (`AGENT_DEFAULT_RUNNER`
   changes it).

### Start a task

Add the label `agent:<role>` to a task issue (or run dispatch, which adds
them for you). The workflow `agents.yml` starts the agent of that role:

- **Claude Code**: the agent comments its plan on the issue (for you to
  read; it does not wait for an answer), works on a branch, runs the tests,
  opens the pull request and comments its link.
- **Codex**: runs on a checkout with the dependencies already installed,
  without network access and without any token or secret in its environment; a second job commits its change, pushes the branch
  and opens the pull request with Codex's summary as the description. Pull
  requests opened with the default token do not trigger other workflows: set
  `AGENT_PR_TOKEN` (a fine-grained token with contents and pull requests
  write) so the CI checks them. In CI nobody approves Codex's hooks, so they
  do not run: the forbidden commands of `.codex/rules/agent-team.rules` (the
  same as the hook's, in their usual form), the missing network and the
  missing secrets are what limit it there.
- **OpenCode**: its GitHub action runs the role agent and opens the pull request.

Only issues opened by the owner, members, collaborators or the repository's
own workflows can start agents. The issue text is read as a description of
the task, never as instructions that override the project rules.

A run ends with a pull request, or with a comment on the issue saying why it
could not finish. Iterate on the pull request, stop, retry or reject the work
as in [4. While a task runs](04-run-the-project.md#while-a-task-runs).

### Start the next tasks at every merge

`dispatch.yml` runs dispatch every time an issue closes, so the tasks that
were waiting start as soon as you merge what they depend on. It is off until
you set the variable `AGENT_AUTODISPATCH` to `true` and the secret
`AGENT_DISPATCH_TOKEN` (a fine-grained token with issues read and write:
labels added with the default token do not start other workflows). Limits:
`AGENT_DISPATCH_PER_ROLE` (default 1) and `AGENT_DISPATCH_MAX` (default 3).
Keep them low at first: every start is an agent run.

### Update the issues when a spec changes

With the `spec-sync` feature, `.github/workflows/spec-sync.yml` runs
`scripts/create-issues.py` every time a change to `docs/design/` reaches the
default branch, usually the merge of a design pull request after its review:
issues for new rows, and a rewrite of the issues whose row changed while their
task has not started. It never closes or starts an issue; the run summary
lists what it did and the issues of removed rows. It uses the workflow token
for GitHub issues; with Jira, Linear or Redmine add their secrets
([9. Reference](09-reference.md#ci-secrets-and-variables)).

### Split from the issue

Add `agent:split` to an issue. Claude reads it with the specs and posts a
proposed split as a comment; nothing is created. Then reply on the issue:

| Reply | Result |
|---|---|
| `@claude ok` | the proposed issues are created as sub-issues, without labels |
| `@claude <your changes>` | a new proposal |

A script creates exactly the plan you approved; the model creates nothing.

### Team tasks

Add `agent:team` to an issue: one session of the `team` agent does the whole
issue, every role it touches, and opens one pull request with a section per
role. It runs on any tool, routed like a role (`AGENT_RUNNERS`:
`{"agent:team":"codex"}`), with the same limits as any task.

### Ask and review

- `@claude <request>` in a comment on an issue or a pull request, or on a
  line of its diff: Claude answers or makes the change on that branch. This
  is how you iterate with the agent on its pull request; comments without
  `@claude` start nothing. Each mention is one run (up to 15 turns).
- Label a pull request `ai-review` for two reviews in parallel: one against
  the project's rules (inline comments), one against the issue and the spec.
  They never approve or block. Remove and re-add the label to review again.

Mentions, reviews and splits use Claude Code. With only Codex or
OpenCode, split locally with `/agent-team:split-issue` and review in your tool.

## GitLab

### Set up once

1. **The pipeline.** Rename the template's `.gitlab-ci.yml.example` to
   `.gitlab-ci.yml`. If the project already has one, copy the `include:`
   entries of the example into it (`.gitlab/ci/ci.yml`, `.gitlab/ci/agents.yml`
   and, with `spec-sync`, `.gitlab/ci/spec-sync.yml`), and the `ai` stage.
2. **Masked variables** (Settings → CI/CD → Variables), for the tools in your
   profile: `ANTHROPIC_API_KEY` (or the subscription token),
   `OPENAI_API_KEY` for Codex, the provider keys and `OPENCODE_MODEL` for
   OpenCode, and `GITLAB_ACCESS_TOKEN`, a project access token with `api` and
   `write_repository`, for splits, `spec-sync` and the Codex and OpenCode
   jobs, which push and open the merge request after the agent has finished.
3. **Labels.** GitLab creates `agent:<role>` the first time dispatch adds it;
   create `alignment-needed` and `hold` yourself (Manage → Labels).
4. **Protect `main`** and require the pipeline to pass before merging. GitLab
   reads the code owners from `.gitlab/CODEOWNERS`.

### Start a task

Agents run as jobs of `.gitlab/ci/agents.yml`. They start only when you run a
pipeline with variables, never on pushes:

| Variable | Meaning |
|---|---|
| `AI_FLOW_INPUT` | the task, or "carry out issue 14 following docs/roles/backend.md" |
| `TASK_ID` | the issue number: jobs for the same task queue instead of running together |
| `AI_FLOW_ROLE` | the role (needed by Codex and OpenCode); `team` for a [team task](04-run-the-project.md#team-tasks) |
| `AI_FLOW_HARNESS` | `claude`, `codex` or `opencode`; default: the first tool of the profile |
| `SPLIT_ISSUE`, `SPLIT_CONFIRM`, `SPLIT_FEEDBACK` | the split (below) |

Run them from Build → Pipelines → Run pipeline, or let dispatch do it: on
GitLab its starter adds the label and runs the pipeline with these variables.

### Iterate, split, and what GitLab does not have

- **Iterate on a merge request**: GitLab has no `@claude` mentions. Run the
  agent pipeline on the merge request's branch (choose it in "Run pipeline"),
  with `AI_FLOW_INPUT` saying what to change ("apply the review comments of
  !12") and the same `TASK_ID`.
- **Split from the issue**, in three runs: first `SPLIT_ISSUE=<n>` alone, and
  Claude posts the proposal as a note on the issue; then, to change it,
  `SPLIT_ISSUE=<n>` with `SPLIT_FEEDBACK` saying what to change, which posts a
  new proposal; finally `SPLIT_ISSUE=<n>` with `SPLIT_CONFIRM=ok`,
  which creates the issues.
- **Not on GitLab**: dispatch at every merge (run `/agent-team:dispatch`
  yourself after merging) and the `ai-review` reviews.

With the `spec-sync` feature, the `spec-sync` job (`.gitlab/ci/spec-sync.yml`)
runs `scripts/create-issues.py` on every push to the default branch that
touches `docs/design/`, as on GitHub; it needs `GITLAB_ACCESS_TOKEN`.

## The skills by example

A short example of each skill on GitHub (profile above). The skills run in your
session, the agents run in GitHub Actions. Replies are in one line.

**setup** - once; it ends with the list of secrets, labels and branch
protection that are left to you (see [Set up once](#set-up-once)):

```text
> /agent-team:setup
  (it asks harnesses, tracker "github", features ci-agents, split, dispatch)
```

**next** - where the project stands, including pull requests to review:

```text
> /agent-team:next
  Issues: 6 created. Running: #4 backend. Waiting: #5 (needs #4). PRs to review: 1.
  Next: review the pull request, then /agent-team:dispatch
```

**design-studio** - the spec is committed to the repository like any file:

```text
> /agent-team:design-studio orders
> 1 yes, 2 by date and status, 3: option B
```

**create-issues** - milestones and issues in GitHub, no labels, so nothing
starts:

```text
> /agent-team:create-issues
  milestone create   M0 · Walking skeleton
      create        Foundations · 1/3 · backend: Health endpoint
      ...
> yes
```

**split-issue** - in the session, or from the issue itself with `agent:split`
and a reply (see [Split from the issue](#split-from-the-issue)):

```text
> /agent-team:split-issue 12 15
  (one overview, then)
> ok 12; 15: merge the two frontend tasks
```

On the issue: add the label `agent:split`, read Claude's comment, reply
`@claude ok`.

**dispatch** - adds `agent:<role>` to the ready tasks, so `agents.yml` starts
them:

```text
> /agent-team:dispatch --per-role 1
  Would start (2): #4 backend, #6 devops. Waits: #5 (needs #4)
> yes
```

To start one task by hand, add the label `agent:backend` to its issue.

**The two flows in one go** - with `--to-issues` each flow runs to the issues
and stops before dispatch ([4. The workflow](04-run-the-project.md#the-workflow)).
On GitHub the design lands as a pull request. The issues are created from its
branch right away; dispatch starts them only once the specs are on `main`,
where the agents in Actions read them.

```text
> /agent-team:design-studio --milestone M1 --to-issues
  ... one round of questions for projects and providers-and-models ...
> ok projects; ok providers-and-models
  Pull request "design: M1 (projects, providers-and-models)" opened.
  create-issues: #82 becomes "Projects (M1 Studio)" with 3 sub-issues,
  #83 becomes the providers task. Create?
> yes
  Split: none needed. Merge the pull request, then /agent-team:dispatch
  (it adds agent:<role> to #103, #105, #83; before the merge they wait).
```

**upgrade** - brings in new workflows and scripts as pull-request-sized
changes on a branch:

```text
> /agent-team:upgrade
  update 4 files, add 1 workflow. Work on a branch, one commit.
> yes
```

## Costs and safety

- Each task is one agent run, and each `@claude` mention one more. The CI minutes are those of your plan. What a run costs:
  [9. What a run costs](09-reference.md#what-a-run-costs).
- Agents in CI use `--max-turns` limits, compact at 200,000 tokens and never
  run in the background, so a run ends with a merge request or a comment
  saying why it could not.
- Agents never merge, never push to `main`, never apply infrastructure. The
  CI checks their merge requests like anyone else's, and the actions in the
  workflows are pinned to commits, with Dependabot proposing updates.

---

<!-- nav -->
[← 5. Scenario: local](05-scenario-local.md) · [Manual index](README.md) · [7. Scenario: custom orchestrator →](07-scenario-custom.md)
<!-- /nav -->
