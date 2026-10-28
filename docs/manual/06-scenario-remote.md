# 6. Scenario: remote repository

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
 "features": ["ci-agents", "split", "team-tasks", "dispatch"]}
```

With several tools, list them and assign roles to the others:
`"harnesses": ["claude", "codex"], "runners": {"optimizer": "codex"}`.

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
   Claude Code session. With a subscription token, switch the workflows from
   `anthropic_api_key` to `claude_code_oauth_token`.
2. **Labels**: `./scripts/create-labels.sh` creates `agent:<role>` for your
   roles, `agent:team`, `agent:split`, `hold`, `alignment-needed`, `ai-review`.
3. **Branch protection** on `main`: pull requests only, the CI checks
   required, "Require branches to be up to date before merging".
4. **Routing**, with more than one tool: the `AGENT_RUNNERS` repository
   variable says which role runs where, for example
   `{"agent:frontend":"opencode","agent:optimizer":"codex"}`. The other roles
   run on the first tool of the profile (`AGENT_DEFAULT_RUNNER` changes it).

### Start a task

Add the label `agent:<role>` to a task issue (or run dispatch, which adds
them for you). The workflow `agents.yml` starts the agent of that role:

- **Claude Code**: the agent comments its plan on the issue, works on a
  branch, runs the tests, opens the pull request and comments its link.
- **Codex**: runs without network or tokens on a checkout with the
  dependencies installed; a second job commits its change, pushes the branch
  and opens the pull request with Codex's summary as the description. Pull
  requests opened with the default token do not trigger other workflows: set
  `AGENT_PR_TOKEN` (a fine-grained token with contents and pull requests
  write) so the CI checks them.
- **OpenCode**: its GitHub action runs the role agent and opens the pull request.

Only issues opened by the owner, members, collaborators or the repository's
own workflows can start agents. The issue text is read as a description of
the task, never as instructions that override the project rules.

### Start the next tasks at every merge

`dispatch.yml` runs dispatch every time an issue closes, so the tasks that
were waiting start as soon as you merge what they depend on. It is off until
you set the variable `AGENT_AUTODISPATCH` to `true` and the secret
`AGENT_DISPATCH_TOKEN` (a fine-grained token with issues read and write:
labels added with the default token do not start other workflows). Limits:
`AGENT_DISPATCH_PER_ROLE` (default 1) and `AGENT_DISPATCH_MAX` (default 3).
Keep them low at first: every start is an agent run.

### Split from the issue

Add `agent:split` to an issue. Claude reads it with the specs and posts a
proposed split as a comment; nothing is created. Then reply on the issue:

| Reply | Result |
|---|---|
| `@claude ok` | the proposed issues are created as sub-issues, without labels |
| `@claude ok team` | one team issue instead, when the proposal suggests it |
| `@claude <your changes>` | a new proposal |

A script creates exactly the plan you approved; the model creates nothing.

### Team tasks

Add `agent:team` to an issue with a line `Roles: backend, frontend`. A
coordinator runs the listed roles in order on one branch and opens one pull
request with a section per role. Needs Claude Code.

### Ask and review

- `@claude <request>` in a comment on an issue or a pull request: Claude
  answers or makes the change on that branch.
- Label a pull request `ai-review` for two reviews in parallel: one against
  the project's rules (inline comments), one against the issue and the spec.
  They never approve or block. Remove and re-add the label to review again.

Mentions, reviews, splits and team tasks use Claude Code. With only Codex or
OpenCode, split locally with `/agent-team:split-issue` and review in your tool.

## GitLab

Agents run as jobs of `.gitlab/ci/agents.yml`, included by `.gitlab-ci.yml`
(rename the template's `.gitlab-ci.yml.example`). They start only when you
run a pipeline with variables, never on pushes:

| Variable | Meaning |
|---|---|
| `AI_FLOW_INPUT` | the task, or "carry out issue 14 following docs/roles/backend.md" |
| `TASK_ID` | the issue number: jobs for the same task queue instead of running together |
| `AI_FLOW_ROLE` | the role (needed by Codex and OpenCode) |
| `AI_FLOW_HARNESS` | `claude`, `codex` or `opencode`; default: the first tool of the profile |
| `AI_FLOW_ROLES` | a team task: the roles in order, for example `backend, frontend` |
| `SPLIT_ISSUE`, `SPLIT_CONFIRM`, `SPLIT_FEEDBACK` | the split: proposal, then `ok` or `team` |

Run them from CI/CD → Pipelines → Run pipeline, or let dispatch do it: on
GitLab its starter adds the label and runs the pipeline with these variables.

Masked variables: `ANTHROPIC_API_KEY` (or the subscription token),
`OPENAI_API_KEY` for Codex, the provider keys and `OPENCODE_MODEL` for
OpenCode, and `GITLAB_ACCESS_TOKEN` (a project access token with `api` and
`write_repository`) for splits and for the Codex and OpenCode jobs, which
push and open the merge request after the agent has finished. Protect `main`
and require the pipeline to pass before merging. GitLab reads the code owners
from `.gitlab/CODEOWNERS`.

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
  milestone create   M0 · Walking skeleton ... (dry run shown)
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

**upgrade** - brings in new workflows and scripts as pull-request-sized
changes on a branch:

```text
> /agent-team:upgrade
  update 4 files, add 1 workflow. Work on a branch, one commit.
> yes
```

## Costs and safety

- Each task is one agent run; a team task is several. The CI minutes are
  those of your plan.
- Agents in CI use `--max-turns` limits, compact at 200,000 tokens and never
  run in the background, so a run ends with a merge request or a comment
  saying why it could not.
- Agents never merge, never push to `main`, never apply infrastructure. The
  CI checks their merge requests like anyone else's, and the actions in the
  workflows are pinned to commits, with Dependabot proposing updates.
