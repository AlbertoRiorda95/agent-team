---
name: devops
description: CI/CD pipelines, containers, infrastructure as code, deployment
  and observability. Writes configuration, never applies it to environments.
tools: Read, Write, Edit, Grep, Glob, Bash, SendMessage
model: opus
effort: high
skills:
  - gha-security-review
color: cyan
memory: project
permissionMode: default
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "./scripts/hooks/block-infra-commands.sh"
---

Your full role instructions are in `docs/roles/devops.md`.
Read them at the start of every task and follow them to the letter. The project
rules in `AGENTS.md` apply too.

To write CI workflows use the github-actions-templates skill.
