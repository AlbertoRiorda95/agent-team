# 10. Integrations not yet validated

<!-- nav -->
[← 9. Reference](09-reference.md) · [Manual index](README.md)
<!-- /nav -->

The integrations below exist, and the plugin's tests check them against
simulated services: the trackers' APIs, GitLab's pipeline schema, the
connection points of the custom scenario that Multica uses. None of them has
been used yet with a real instance of the system. Expect them to work as this
manual describes, and report anything that does not.

| Integration | What exists | Where it is described |
|---|---|---|
| **Jira** (Cloud and Data Center) | the issue tracker: milestones as versions, issues and sub-tasks, "blocks" links, labels, comments; `create-issues`, `split-issue`, `dispatch` and `spec-sync` on it | [9. Reference](09-reference.md#configuration) |
| **Linear** | the issue tracker: project milestones, issues and sub-issues, "blocked by" relations, labels, comments; the same scripts | [9. Reference](09-reference.md#configuration) |
| **GitLab** | the issue tracker, and the CI: the agent jobs, the split jobs, `spec-sync`, the project's CI with the vulnerability checks and the publish job, the pipeline starter of dispatch | [6. Scenario: remote repository](06-scenario-remote.md#gitlab) |
| **Multica** | the custom scenario with Multica as the board and runner of the agents | [7. Option A: Multica](07-scenario-custom.md#option-a-multica-a-board-with-agents-as-team-members) |

---

<!-- nav -->
[← 9. Reference](09-reference.md) · [Manual index](README.md)
<!-- /nav -->
