# Changelog

Every release has **Upgrade notes**: the steps `/agent-team:upgrade` cannot do
by changing files, because they need your hands on the platform or a decision.

Versions: the patch for documentation and small fixes, the minor for new
features, the major for changes that break existing projects.

## Unreleased

### Template
- `clean-architecture` skill for the backend, preloaded by `backend`. `setup`
  keeps it when the stack and the project allow layering and removes it for a
  script or a thin CRUD.

- `writer` role (on demand) and `/document` skill: design document, ICD, user
  manual, install and operations guide and API guide in `docs/software/`, and
  a short `README.md` that points to them. The writer cannot write anywhere
  else (a hook in Claude Code, permissions in OpenCode, a rule in Codex), so
  it never collides with the designer's `docs/design/`.
- The CI builds the reference documentation from the code (`reference-docs`
  job, `ci/reference.sh`: OpenAPI with Redocly, typedoc, pdoc; other stacks
  are added in the script) and keeps it as an artifact.
- Software reuse: specs have a `## Reuse` section (and a readiness item);
  `docs/agents/dependencies.md` gives the order (the project's code, the
  team's libraries, a trusted library, own code) and the checklist for a
  third-party library, starting with checking that the package really exists;
  merge requests list **Dependencies**. The team's libraries are listed in
  `docs/general/libraries.md` (setup asks for them, with their registry); an
  agent never changes one from the project and proposes an issue for it.
- `ci/registry.sh` (settings in `ci/registry.env`): the connection to the
  team's package registry, the same in every CI job, in the agent jobs and
  on a laptop. Package managers: npm, PyPI, Maven, Gradle, Conan 2, and
  `custom` with your own commands for any other. Tokens come from the environment, never
  from a committed file: the job token on GitHub Packages and GitLab,
  otherwise a read-only `REGISTRY_TOKEN`.
- Publishing: `publish.yml` (GitHub) and the `publish` job (GitLab) publish
  the project's package on a `v*` tag, in the `release` environment, with
  `REGISTRY_PUBLISH_TOKEN` stored only there. Agents cannot publish or push
  tags (hooks and permission rules of every tool). `ci/registry.sh local`
  installs the package in the machine's local repository (`mvn install`,
  `gradle publishToMavenLocal`, `conan create`, `npm pack`, a wheel): the
  release of the local scenario. Setup step D4 sets up publishing for any
  stack.
- optimizer proposes an issue for code that can be shared; it never merges
  it by itself.
- Monorepo: setup lists the services in `AGENTS.md` and makes role
  boundaries, CODEOWNERS and CI per service; a task names its service
  (`[orders] ...`), and dispatch runs one task per role and per service.
- `local-ci` skill: runs the CI's checks on your computer and fixes the
  failures, for convenience before a push or instead of the CI when the
  project has none.

- `AGENTS.md` and `CLAUDE.md`: when a session is long or changes phase, the
  agent suggests `/handoff` and then `/clear`; it never runs it, and does not
  suggest it after a short session.

### Documentation
- The manual explains the development approach (design first, TDD, clean
  architecture when it fits, CI with tests and vulnerability checks, human
  review) and where the CI runs in the local scenario, with or without a
  remote.

### Upgrade notes
- A project whose profile has no `roles` key gets the `writer` role on upgrade
  (it only acts when asked); list `roles` without it to opt out.
- With a private registry: fill in `ci/registry.env`, add `REGISTRY_TOKEN`
  if the job token is not enough, and to publish create the `release`
  environment with `REGISTRY_PUBLISH_TOKEN`, a required reviewer and protected
  `v*` tags. Set the toolchain of `publish.yml` (or the GitLab `publish` job)
  to your stack's.
- Set the toolchain of the `reference-docs` job in your CI file and check
  `ci/reference.sh` keeps the generators of your stack. The tool versions
  were checked against the registries but not run on a real project.

## 1.5.0 - 2026-10-28

### Skills
- `design-studio --milestone M0`: designs every feature of a roadmap milestone
  in one session. It drafts the specs from what is already decided, asks one
  round of questions for all of them, plans the breakdowns together and
  approves each spec on its own. Ready specs are committed together on
  `design/<milestone>`.
- `--to-issues` runs a whole flow, each step still with its own plan and yes,
  and stops before dispatch:
  - `setup --to-issues`: setup, project design and foundations, then the
    issues, with any tracker: foundations tasks ready, the other features as
    "Design:" issues;
  - `design-studio <feature> | --milestone M1 --to-issues`: the specs, then
    the issues, then a split of the tasks that still need one.
  Neither waits for the merge of the design or setup merge request: the
  issues are created from its branch, and dispatch waits for the merge.
- `next` suggests `--milestone` when a milestone has several "Design:" issues.

### Template
- `create-issues` no longer leaves "Design:" issues behind. When a feature's
  spec is ready, its "Design:" issue becomes the task (one row in the
  breakdown) or the feature issue, with the tasks created as its sub-issues
  (several rows). The feature issue is not a task: dispatch skips it.
- `dispatch` keeps a task waiting while its spec is not ready on the main
  branch ("spec ... not merged"): the remote's default branch after a fetch,
  or the current commit without a remote.
- Every task issue carries a fingerprint of its spec row. When the row changes
  (a review of the design merge request), `create-issues` and `dispatch`
  rewrite the issue if its task has not started, and list it if it has;
  dispatch keeps a task whose row was removed waiting. No task starts on an
  outdated spec.
- New feature `spec-sync`: create-issues runs by itself when a change to
  `docs/design/` reaches the main branch - `.github/workflows/spec-sync.yml`,
  the `spec-sync` job in `.gitlab/ci/spec-sync.yml`, or the Git hook
  `scripts/git-hooks/spec-sync.sh` in the local scenario.
- Jira has one level of sub-tasks: the tasks of a feature issue, and the parts
  of a sub-task, are Tasks with a "Relates" link to their parent, so a task of
  a feature can still be split into sub-tasks.
- GitLab: the issue a task belongs to (the feature, or the issue it was split
  from) is no longer listed among its children.
- Trackers can edit an issue's title and description (`edit_issue`, all six).
- A breakdown row can depend on a row of another spec: `app-shell#2` in
  "Depends on". `create-issues` creates the other spec's issue first, even
  when the roadmap lists the features the other way round, and links the two
  in the text and natively.
- The design studio procedure (`docs/roles/design-studio.md`) has a
  "Milestone session" section; the spec template documents `<feature>#<n>`.

### Fixes
- `dispatch` in a local project with GitHub or GitLab issues no longer adds
  `agent:<role>` labels that start nothing: without the `ci-agents` feature
  the default starter prints what to run.
- Merge requests of a task with a GitHub or GitLab issue end with
  `Closes #<issue>` (`docs/agents/merge-requests.md`), so the merge closes the
  issue on GitLab too and its dependents can start.

### Documentation
- The manual reviewed by a first-time reader: a glossary at the end of
  chapter 1, terms explained before they are used, "While a task runs"
  (follow, iterate on the merge request, stop, retry, reject) and "Change the
  plan" in chapter 4, when an issue counts as done and who closes it, what a
  local task produces, the GitLab set-up and iteration, what a run costs.
- "The workflow" in "Run the project": the two flows as diagrams, with
  `--to-issues` and a full example; the flows in the local and remote
  scenarios. The HTML manual draws Mermaid diagrams (loaded from a CDN).

### Upgrade notes
- Task issues created before 1.5.0 have no row fingerprint: the first
  `create-issues` or `dispatch` after the upgrade adds it, rewriting each
  open task that has not started from its current row (shown as "update" in
  the dry run). Started tasks are left as they are.
- `spec-sync` is off until you add it to `features` and run the upgrade; in
  the local scenario, link the hook as `docs/manual` chapter 5 says.
- After the upgrade, `/agent-team:design-studio --milestone <code>`
  replaces one session per "Design:" issue, and `create-issues` reuses the
  "Design:" issues of the features you specify from now on.

## 1.4.0 - 2026-10-28

### Fixes
- `create-issues`: a roadmap feature with commas inside parentheses or
  backticks (`` `foundations` (Makefile, compose) ``) was split into several
  broken "Design:" issues. The feature name is now the name in backticks, or
  the text before the parenthesis; the rest goes in the issue body.
- Issue keys with spaces (milestone codes like `M0 Foundations`) were not read
  back, so `create-issues` did not recognize its own issues by key.
- `dispatch`: with no task issues it said "issues without a milestone"; it now
  says "no task issues" and, under "Not tasks yet", counts the open "Design:"
  issues and issues without a role up to the milestone in scope, with the
  command that turns them into tasks. A milestone without tasks is no longer
  skipped silently.

### Skills
- `split-issue` takes several issues (`12 15 18`) or `--milestone M1`: one
  overview, one approval per issue, creation in dependency order.

### Template
- Split plans: `depends_on` accepts `"<issue>:<key>"`, a task of another
  issue's plan. `split-issue.py create` writes it in "Depends on" and as the
  native "blocked by" relation, and refuses while that task does not exist.
  `split.yml` is unchanged.

### Documentation
- Every skill by example in the local and remote scenarios; several-issue
  split and cross-issue dependencies in "Run the project".

### Upgrade notes
- If your roadmap has commas inside parentheses, `create-issues` made broken
  "Design:" issues. After the upgrade, `create-issues` lists them under
  "Created by this script but no longer in the plan": close them, then let it
  create the right ones.

## 1.3.0 - 2026-10-27

### Skills
- New `/agent-team:next`: reads the profile, the design, the specs and the
  tracker, says where the project stands and which command to run next.
  Read-only.
- `design-studio`, `create-issues`, `split-issue` and `dispatch` can now be
  proposed by Claude itself (no more `disable-model-invocation`), so they are
  found from the Claude app or Remote Control, where slash commands cannot be
  browsed. Each shows its plan and asks before changing anything; their
  descriptions say when to use them. `setup` and `upgrade` stay manual.

### Documentation
- Commands tables updated; new "From your phone" section in the local scenario.

### Upgrade notes
- None.

## 1.2.0 - 2026-10-27

### Documentation
- The guide is replaced by a user manual for the plugin, in English, in
  `docs/manual/` (Markdown, one file per chapter) and `docs/manual.html`
  (generated by `scripts/build_manual.py`; CI fails if it is stale). It is
  organized by scenario: local, remote repository, custom orchestrator.
- No PDF and no Italian edition any more.

### Template
- `docs/general/guide.md` is gone, with the `guide` feature of the profile
  (still accepted in old profiles, and ignored). Comments no longer point to
  guide sections.
- `SETUP.md` asks for the scenario (local, remote, custom) instead of the
  architectures A-F; the profiles table follows the scenarios.

### Upgrade notes
- `docs/general/guide.md` shows up as `removed-upstream` and is kept: delete
  it unless you want it (about 65,000 tokens an agent may find by searching).

## 1.1.0 - 2026-10-27

### Template
- Claude Code, OpenCode and Codex on the same roles: `.codex/` (config, the six
  role agents, hooks, command rules), six OpenCode agents with permissions,
  shared skills in `.agents/skills/`. The lead rules moved from `CLAUDE.md` to
  `AGENTS.md` ("Leading a session").
- Hooks are shared by Claude Code and Codex: `.claude/hooks/` moved to
  `scripts/hooks/`; handoff notes moved from `.claude/handoff/` to `.handoff/`;
  the security scope from `.claude/security-scope` to `docs/roles/security-scope.txt`.
- Agents in CI per harness: `agents.yml` has Claude Code, OpenCode and Codex
  jobs, routed per role by `AGENT_RUNNERS` (replaces `OPENCODE_ROLES`); Codex
  works offline and a second job opens the PR. GitLab: `codex` and `opencode`
  jobs and `ci/agent-mr.sh` (not yet run on a real runner).
- Project profile in `.agent-team/config.json` (harnesses, CI, tracker, roles,
  features) and `scripts/agent-team.py prune`: setup removes what the project
  does not use, files and sections.

### Plugin
- `template_sync.py` renders the template for the profile: install only what
  the profile uses, and on upgrade remove unchanged files that left the profile
  (`prune`) and bring back what re-enters it.
- `setup` asks the profile before installing; `upgrade` proposes a profile for
  older projects and changes it on request.
- The skills work from Codex and OpenCode too (`$AGENT_TEAM_HOME`).

### Upgrade notes
- Before the first upgrade, let `/agent-team:upgrade` write your profile:
  without one, the upgrade would add every harness, CI platform and tracker.
- Hooks, handoff notes and the security scope moved (see above): the upgrade
  updates `.claude/settings.json` and the agents; delete the old
  `.claude/hooks/` folder and move your `.claude/security-scope` hosts to
  `docs/roles/security-scope.txt` (it is yours: the upgrade does not copy it).
- GitHub: replace the `OPENCODE_ROLES` variable with `AGENT_RUNNERS`, for
  example `{"agent:frontend":"opencode"}`, and set `OPENCODE_MODEL`.
- With Codex: the `OPENAI_API_KEY` secret, optionally `CODEX_MODEL` and
  `AGENT_PR_TOKEN`; trust the project in Codex and approve its hooks (`/hooks`).

## 1.0.0 - 2026-10-26

First release as a plugin. Projects created from earlier copies of the template
have no `.agent-team/` folder: the first `/agent-team:upgrade` compares the
files that differ with you and records them, after that upgrades are automatic.

### Template
- Issue split: `agent:split` label and `split.yml` (GitHub), `claude-split` and
  `split-create` jobs (GitLab), `scripts/split-issue.py`; proposal first,
  creation only after `@claude ok`.
- Native milestones: `create-issues.py` creates one milestone per roadmap row
  and puts the task issues in it; `--migrate` moves projects off the old
  "M0 · ..." parent issues.
- Static analysis in CI: type check step, `static-analysis` job (semgrep, only
  the findings a PR introduces fail it), `workflow-lint.yml` (actionlint).
- Playwright UI tests: `ui` job, `ui-report` artifact with screenshots per
  viewport.
- Review on request (`ai-review`) runs two jobs: `standards` and `spec`.
- Design studio interviews in rounds with recommended answers; specs have a
  `## Test seams` section; expand-contract for breaking contract changes; MR
  descriptions with Evidence and Merge danger.
- Any issue tracker: `scripts/agentteam/` puts creation, split and dispatch
  behind one interface, with adapters for GitHub, GitLab, local Markdown files
  (`docs/tasks/`), Jira, Linear and Redmine. Starting a task is a separate
  *starter*: label, GitLab pipeline, a configured command (an orchestrator,
  the custom scenario) or a printed instruction. Configuration in
  `.agent-team/config.json`, check with `scripts/tracker.py check`; see
  `docs/general/trackers.md`. Jira, Linear and Redmine are tested against
  simulated APIs: run the check on your instance first.
- Ready tasks: `scripts/dispatch.py` starts the task issues with no open
  dependency, one per role and three in total by default; optional
  `dispatch.yml` does it at every merge; `hold` label to keep a task back.
- Context: sessions compact at 200K tokens (`autoCompactWindow`, and
  `CLAUDE_CODE_AUTO_COMPACT_WINDOW` in CI) instead of near the 1M window;
  "Compact instructions" in `CLAUDE.md`; `/handoff` skill and a SessionStart
  hook that points a new session to the latest note.
- Agents start also on issues created by `github-actions[bot]` (the split).
- `AGENTS.md` keeps what every task needs and points to `docs/agents/` for the
  rest.
- Agent workflows: actions pinned to a commit, issue text read with `gh` and
  never placed in the prompt, author filter, foreground subagents in CI.

### Plugin
- Skills: `setup`, `design-studio`, `create-issues`, `split-issue`, `dispatch`, `upgrade`.
- `scripts/template_sync.py`: install and three-way upgrade of the template.

### Upgrade notes
- GitHub: create the `agent:split` label
  (`gh label create "agent:split" --color 5319e7`) or rerun `scripts/create-labels.sh`.
- GitHub: add `actionlint`, `static-analysis` and `ui` to the required checks
  of `main`.
- GitLab: add the masked variable `GITLAB_ACCESS_TOKEN` (project token, `api`
  scope) for the split jobs.
- If your issues use the old "M0 · ..." parent issues:
  `python3 scripts/create-issues.py --migrate --dry-run`, then without
  `--dry-run`, then close the old parent issues it lists.
- GitHub, optional: to start ready tasks at every merge, set the variable
  `AGENT_AUTODISPATCH=true` and the secret `AGENT_DISPATCH_TOKEN`
  (fine-grained token, Issues read and write); create the `hold` label.
- Add a `## Test seams` section to the specs you already wrote.
- Rerun `scripts/install-skills.sh` (adds `retro` and `writing-for-agents`).
- Workflows using the subscription: keep `claude_code_oauth_token` in the new
  `split.yml` and `claude-review.yml` jobs.
