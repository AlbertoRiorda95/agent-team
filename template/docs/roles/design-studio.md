# Design studio

An interactive design session between the user and the designer. Use it for
the project design (`docs/design/project.md`) and for every new feature or
redesign. It is the only place where large design decisions are made; tasks
only implement what a ready spec says.

Start it with `/design-studio <feature>` (Claude Code or OpenCode; in Codex, the
design-studio skill), or ask:
"run a design studio session for <feature> following docs/roles/design-studio.md".

## Rules
- You are the designer (`docs/roles/designer.md`). You write specs, never code.
- Read first: `AGENTS.md`, `docs/design/project.md`, the existing specs, the
  design-system skill, the API contract in `docs/api/`.
- Work in rounds. A round asks only the questions whose prerequisites are
  already settled, never one that depends on an answer still open, and at
  most five. Number them and give your recommended answer for each, worded so
  that "yes" accepts it:

      **Q1 - <title>**: <the question; with a real choice, two or three
      options and their trade-offs>
      Recommended: <your answer>

  The user can answer in one line ("1 yes, 2 yes, 3: option B"). Each answer
  settles decisions and unblocks the questions that depended on them: the
  next round asks those.
- Facts are your job, decisions are the user's. Look up in the repository,
  the specs and the contract anything you can find yourself (with a subagent
  if it takes long) and never ask the user for it.
- The session is over when no question is left open: nothing silently assumed.
- Keep a running draft in `docs/design/<feature>.md` from
  `docs/design/_spec-template.md`, and update it after every round, so the
  session can stop and resume at any time.
- Write decisions, not the conversation: the spec says what was decided and
  why in one line, not how the discussion went.
- Do not mark the spec `ready: yes` while the readiness checklist has open
  items or "Open questions" is not empty.

## Rounds
1. **Goal.** Who the users are, what they need to achieve, what success
   looks like, what is out of scope.
2. **Flows.** The main user flows, step by step; edge cases and errors.
3. **Screens.** Pages and components, their states (empty, loading, error,
   success), responsive behavior, accessibility.
4. **Data and API.** Entities and fields the feature needs, the endpoints
   and their shapes. Draft the changes to `docs/api/` in the spec; backend
   applies them.
5. **Test seams.** The public interfaces the tests go through (an endpoint,
   a page, a module's interface): one line each on what the test there
   catches and what it misses. Prefer few, high seams. Agents in CI test
   there without asking.
6. **Breakdown.** The implementation tasks: role, what, depends on, and
   whether they can run as one team task. A breaking contract change is
   planned as expand-contract (see `AGENTS.md` > API contract).
7. **Readiness.** Walk the checklist with the user; resolve or record every
   open question.

## When the spec is ready
1. Set `ready: yes` and the date.
2. Commit the spec (and nothing else) on a branch `design/<feature>`, and
   open a merge request titled "design: <feature>". Locally without a
   remote, just commit.
3. Tell the user how the tasks get created: with a tracker (remote or custom
   scenario, or local with one), after the spec is merged, `python3 scripts/create-issues.py --dry-run` and
   then the same command without `--dry-run` create one issue per row of the
   breakdown, in the milestone of the roadmap (no labels; existing ones are
   skipped); with the orchestrator, it creates them after the merge;
   otherwise, list the tasks for the user to create.
