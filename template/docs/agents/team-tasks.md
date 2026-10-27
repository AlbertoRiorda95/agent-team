# Team tasks

A team task is one issue carried out by several roles in sequence on the same
branch, ending in one MR. The user asks for it explicitly: the `agent:team`
label on GitHub (with a `Roles: backend, frontend` line in the issue body),
`AI_FLOW_ROLES` on GitLab, or a request in a local session.
- A coordinator delegates only to the listed roles, in the listed order, and
  writes no code itself.
- Each role works within its own boundaries and commits and pushes before the
  next one starts.
- Alignment entries that concern listed roles are handled inside the task;
  the others stay open and are reported in the MR.
- Use team tasks for small, tightly coupled features. Larger work stays split
  into separate tasks, so that each MR remains reviewable.
