#!/usr/bin/env python3
"""End-to-end checks of create-issues.py, dispatch.py and split-issue.py on every
tracker: the local one for real, GitHub (gh CLI), Jira, Linear and Redmine
against the in-memory fakes in tests/fakes.py, and Redmine for real too, in
Docker (RedmineLive; REDMINE_LIVE=0 to skip): the fakes are checked against a
real server.

Run: python3 tests/test_trackers.py
"""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPTS = os.path.join(ROOT, "template", "scripts")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agentteam import config, core  # noqa: E402
import fakes  # noqa: E402

PROJECT = """---
ready: yes
---
# Project

## Roadmap
| Milestone | Features |
|---|---|
| M0 | Walking skeleton |
| M1 | Login |
"""
SPEC = """---
ready: yes
milestone: M0
features: Walking skeleton
---
# Foundations

## Task breakdown
| # | Role | Task | Depends on | Issue |
|---|---|---|---|---|
| 1 | backend | Health endpoint | - | - |
| 2 | frontend | Status page | 1 | - |
| 3 | devops | CI pipeline | - | - |
"""
ROW4 = "| 4 | backend | Database migrations | 3 | - |\n"
PLAN = {"summary": "Contract first, then the UI.", "tasks": [
    {"key": "api", "role": "backend", "title": "Date filter in the API", "task": "Add from and to.",
     "acceptance": ["The list can be filtered by date"], "files": ["src/server/"], "depends_on": []},
    {"key": "ui", "role": "frontend", "title": "Date picker", "task": "Add the picker.",
     "acceptance": ["The picker filters the list"], "files": ["src/ui/"], "depends_on": ["api"]}]}


def script(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), os.path.join(SCRIPTS, name))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def call(name, *argv):
    out = io.StringIO()
    old = sys.argv
    sys.argv = [name, *argv]
    try:
        with contextlib.redirect_stdout(out):
            mod = script(name)
            rc = mod.main(list(argv)) if name == "split-issue.py" else mod.main()
    finally:
        sys.argv = old
    return rc, out.getvalue()


class Scenario:
    """What differs per tracker: configuration, fake, how to close an issue."""

    def __init__(self, name, cfg, fake=None, env=None):
        self.name, self.cfg, self.fake, self.env = name, cfg, fake, env or {}

    def install(self):
        for k, v in self.env.items():
            os.environ[k] = v
        if self.name in ("github", "gitlab"):
            core.sh = self.fake.sh
        elif hasattr(self.fake, "http"):                      # a fake; a live server has none
            core.http_json = self.fake.http

    def close(self, issue, completed=True):
        f = self.fake
        if self.name == "local":
            p = issue.url
            t = open(p, encoding="utf-8").read()
            open(p, "w", encoding="utf-8").write(t.replace('state: "open"', 'state: "done"' if completed else 'state: "dropped"'))
        elif self.name == "github":
            f.close(int(issue.number), "completed" if completed else "not_planned")
        elif self.name == "gitlab":
            f.close(int(issue.number))
        elif self.name == "jira":
            f.done(issue.ref, "Done" if completed else "Won't Do")
        elif self.name == "redmine":
            f.close(int(issue.ref), "Closed" if completed else "Rejected")
        elif self.name == "linear":
            f.done(issue.ref, "completed" if completed else "canceled")


def scenarios():
    return [
        Scenario("local", {"tracker": "local", "starter": "label"}),
        Scenario("github", {"tracker": "github", "starter": "label"}, fakes.FakeGitHub(), {"GITHUB_REPOSITORY": "o/r"}),
        Scenario("jira", {"tracker": "jira", "starter": "label", "jira": {"url": fakes.FakeJira.BASE, "project": "PROJ"}},
                 fakes.FakeJira(), {"JIRA_EMAIL": "a@b.c", "JIRA_API_TOKEN": "t"}),
        Scenario("redmine", {"tracker": "redmine", "starter": "label",
                             "redmine": {"url": fakes.FakeRedmine.BASE, "project": "app"}},
                 fakes.FakeRedmine(), {"REDMINE_API_KEY": "k"}),
        Scenario("gitlab", {"tracker": "gitlab"}, fakes.FakeGitLab()),
        Scenario("linear", {"tracker": "linear", "starter": "label", "linear": {"team": "ENG", "project": "App"}},
                 fakes.FakeLinear(), {"LINEAR_API_KEY": "lin_key"}),
    ]


class TrackerFlow(unittest.TestCase):
    def setUp(self):
        self.cwd = os.getcwd()
        self.tmp = tempfile.mkdtemp()
        os.chdir(self.tmp)
        os.makedirs("docs/design")
        os.makedirs(".agent-team")
        open("docs/design/project.md", "w").write(PROJECT)
        open("docs/design/foundations.md", "w").write(SPEC)
        self.saved = (core.sh, core.http_json, dict(os.environ))

    def tearDown(self):
        core.sh, core.http_json = self.saved[0], self.saved[1]
        os.environ.clear()
        os.environ.update(self.saved[2])
        os.chdir(self.cwd)
        shutil.rmtree(self.tmp)

    def run_flow(self, sc):
        json.dump(sc.cfg, open(".agent-team/config.json", "w"))
        sc.install()
        trk = lambda: config.tracker(config.load())  # noqa: E731
        by = lambda t: {i.title: i for i in t.issues()}  # noqa: E731

        # create: dry run, then for real
        rc, out = call("create-issues.py", "--dry-run")
        self.assertEqual(rc, 0, out)
        self.assertIn("milestone create   M0 · Walking skeleton", out)
        rc, out = call("create-issues.py")
        self.assertEqual(rc, 0, out)
        issues = by(trk())
        t1 = issues["Foundations · 1/3 · backend: Health endpoint"]
        t2 = issues["Foundations · 2/3 · frontend: Status page"]
        t3 = issues["Foundations · 3/3 · devops: CI pipeline"]
        self.assertIn("Design: Login (M1)", issues)
        self.assertEqual(core.code(t1.milestone), "M0")
        self.assertEqual(core.code(issues["Design: Login (M1)"].milestone), "M1")
        self.assertEqual(core.role_of(t2), "frontend")
        self.assertIn(t1.id, core.deps_of(t2)[0] + [f"#{d}" for d in core.deps_of(t2)[0]] + core.deps_of(t2)[0])
        self.assertIn(t1.ref, [str(b) for b in trk().blockers(t2)])          # native dependency
        self.assertEqual(len(trk().milestones()), 2)

        # again: nothing new; with a fourth row: one new issue, no duplicates
        rc, out = call("create-issues.py")
        self.assertIn("0 issue(s) and 0 milestone(s) created", out)
        open("docs/design/foundations.md", "a").write(ROW4)
        rc, out = call("create-issues.py")
        self.assertIn("1 issue(s) and 0 milestone(s) created", out)
        issues = by(trk())
        self.assertEqual(sum(1 for t in issues if t.startswith("Foundations ·")), 4)
        t4 = issues["Foundations · 4/4 · backend: Database migrations"]

        # dispatch: backend 1 and devops 3 start; frontend 2 waits for 1, backend 4 for 3
        rc, out = call("dispatch.py")
        self.assertIn("Would start (2)", out)
        rc, out = call("dispatch.py", "--apply")
        self.assertEqual(rc, 0, out)
        cur = {i.ref: i for i in trk().issues()}
        self.assertTrue(core.started(cur[t1.ref]) and core.started(cur[t3.ref]))
        self.assertFalse(core.started(cur[t2.ref]) or core.started(cur[t4.ref]))
        rc, out = call("dispatch.py", "--apply")
        self.assertIn("Nothing to start", out)

        # task 1 done: frontend 2 starts; backend 4 still waits for 3
        sc.close(cur[t1.ref])
        rc, out = call("dispatch.py", "--apply")
        cur = {i.ref: i for i in trk().issues()}
        self.assertTrue(core.started(cur[t2.ref]), out)
        self.assertFalse(core.started(cur[t4.ref]), out)
        # task 3 dropped (not completed): 4 keeps waiting
        if sc.name != "gitlab":                       # GitLab has no "closed as not planned"
            sc.close(cur[t3.ref], completed=False)
            rc, out = call("dispatch.py", "--apply")
            self.assertFalse(core.started({i.ref: i for i in trk().issues()}[t4.ref]), out)

        # split a hand-written issue: propose, create, create again
        t = trk()
        parent = t.create_issue("Orders: filter by date", "Hand written request.")
        plan = dict(PLAN, parent=parent.number)
        json.dump(plan, open("plan.json", "w"))
        rc, out = call("split-issue.py", "check", "plan.json")
        self.assertEqual(rc, 0, out)
        rc, out = call("split-issue.py", "propose", parent.number, "plan.json")
        self.assertEqual(rc, 0, out)
        rc, out = call("split-issue.py", "create", parent.number)
        self.assertIn("2 issue(s) created", out)
        kids = trk().children(trk().get(parent.ref))
        self.assertEqual(sorted(core.role_of(k) for k in kids), ["backend", "frontend"])
        ui = next(k for k in kids if core.role_of(k) == "frontend")
        api = next(k for k in kids if core.role_of(k) == "backend")
        self.assertIn(api.ref, [str(b) for b in trk().blockers(ui)])
        rc, out = call("split-issue.py", "create", parent.number)
        self.assertIn("0 issue(s) created", out)
        with self.assertRaises(SystemExit):
            call("split-issue.py", "create", parent.number, "--team")

    def run_cross_issue(self, sc):
        """Two hand-written issues: the frontend task of the second waits for the backend task of the first."""
        json.dump(sc.cfg, open(".agent-team/config.json", "w"))
        sc.install()
        trk = lambda: config.tracker(config.load())  # noqa: E731
        first = trk().create_issue("Orders: filter by date", "Hand written request.")
        second = trk().create_issue("Orders page: date picker", "Hand written request.")
        backend = {"parent": first.number, "summary": "The API.", "tasks": [dict(PLAN["tasks"][0])]}
        frontend = {"parent": second.number, "summary": "The UI.", "tasks": [
            dict(PLAN["tasks"][1], depends_on=[f"{first.number}:api"])]}
        for name, plan in (("backend.json", backend), ("frontend.json", frontend)):
            json.dump(plan, open(name, "w"))
            rc, out = call("split-issue.py", "check", name)
            self.assertEqual(rc, 0, out)
        for issue, name in ((first, "backend.json"), (second, "frontend.json")):
            rc, out = call("split-issue.py", "propose", issue.number, name)
            self.assertEqual(rc, 0, out)
        kids = lambda i: trk().children(trk().get(i.ref))  # noqa: E731

        # the second before the first: refused, nothing created
        with self.assertRaises(SystemExit) as refused:
            call("split-issue.py", "create", second.number)
        self.assertIn(f"{first.number}:api", str(refused.exception))
        self.assertEqual(kids(second), [])

        # in order: the dependency is in the text and a native relation
        rc, out = call("split-issue.py", "create", first.number)
        self.assertIn("1 issue(s) created", out)
        rc, out = call("split-issue.py", "create", second.number)
        self.assertIn("1 issue(s) created", out)
        api, ui = kids(first)[0], kids(second)[0]
        self.assertEqual(core.role_of(ui), "frontend")
        self.assertIn(api.ref, [r.lstrip("#") for r in core.deps_of(ui)[0]])
        self.assertIn(api.ref, [str(b) for b in trk().blockers(ui)])
        self.assertIn(api.id, core.section(ui.body, "Depends on"))

        # again: nothing new
        rc, out = call("split-issue.py", "create", second.number)
        self.assertIn("0 issue(s) created", out)
        self.assertEqual(len(kids(second)), 1)

    def run_design_to_tasks(self, sc):
        """Design: issues first; then a two-row spec makes its issue the feature, a one-row spec makes it the task."""
        open("docs/design/project.md", "w").write(
            "# P\n\n## Roadmap\n| Milestone | Features |\n|---|---|\n| M1 Studio | `shell` (navigation, theme), `auth` |\n")
        os.remove("docs/design/foundations.md")
        json.dump(sc.cfg, open(".agent-team/config.json", "w"))
        sc.install()
        trk = lambda: config.tracker(config.load())  # noqa: E731
        rc, out = call("create-issues.py")
        self.assertEqual(rc, 0, out)
        by = {i.title: i for i in trk().issues()}
        shell, auth = by["Design: shell (M1 Studio)"], by["Design: auth (M1 Studio)"]

        row = "---\nready: yes\n---\n# {t}\n\n## Task breakdown\n| # | Role | Task | Depends on | Issue |\n|---|---|---|---|---|\n{r}"
        open("docs/design/shell.md", "w").write(row.format(
            t="Shell", r="| 1 | backend | Menu endpoint | - | - |\n| 2 | frontend | Navigation bar | 1 | - |\n"))
        open("docs/design/auth.md", "w").write(row.format(t="Auth", r="| 1 | backend | Login endpoint | - | - |\n"))
        rc, out = call("create-issues.py", "--dry-run")
        self.assertIn(f"rename  {shell.id}  Design: shell (M1 Studio)  ->  Shell (M1 Studio)", out)
        self.assertIn(f"(sub-issue of {shell.id})", out)
        rc, out = call("create-issues.py")
        self.assertEqual(rc, 0, out)
        self.assertIn("2 issue(s) and 0 milestone(s) created, 2 Design: issue(s) turned into features or tasks", out)
        self.assertNotIn("no longer in the plan", out)

        feature, task = trk().get(shell.ref), trk().get(auth.ref)
        self.assertEqual(feature.title, "Shell (M1 Studio)")
        self.assertTrue(core.key_of(feature).endswith("shell.md#feature"))
        kids = trk().children(feature)
        self.assertEqual(sorted(core.role_of(k) for k in kids), ["backend", "frontend"])
        self.assertEqual(task.title, "Auth · 1/1 · backend: Login endpoint")
        self.assertEqual(core.role_of(task), "backend")
        self.assertEqual(core.code(task.milestone), "M1 Studio")

        rc, out = call("create-issues.py")
        self.assertIn("0 issue(s) and 0 milestone(s) created, 0 Design: issue(s)", out)
        rc, out = call("dispatch.py")
        self.assertNotIn("Issues without a role", out)
        self.assertIn("Login endpoint", out)
        if sc.name == "jira":                                  # one level of sub-tasks: the feature's tasks are Tasks
            self.assertEqual({sc.fake.issues[k.ref]["fields"]["issuetype"]["name"] for k in kids}, {"Task"})

        # a task of the feature can still be split
        menu = next(k for k in kids if core.role_of(k) == "backend")
        json.dump(dict(PLAN, parent=menu.number), open("plan.json", "w"))
        call("split-issue.py", "propose", menu.number, "plan.json")
        rc, out = call("split-issue.py", "create", menu.number)
        self.assertIn("2 issue(s) created", out)
        self.assertEqual(len(trk().children(trk().get(menu.ref))), 2)

    def test_design_to_tasks_local(self):
        self.run_design_to_tasks(scenarios()[0])

    def test_design_to_tasks_github(self):
        self.run_design_to_tasks(scenarios()[1])

    def test_design_to_tasks_jira(self):
        self.run_design_to_tasks(scenarios()[2])

    def test_design_to_tasks_redmine(self):
        self.run_design_to_tasks(scenarios()[3])

    def test_design_to_tasks_gitlab(self):
        self.run_design_to_tasks(scenarios()[4])

    def test_design_to_tasks_linear(self):
        self.run_design_to_tasks(scenarios()[5])

    @unittest.skipUnless(shutil.which("git"), "git not installed")
    def test_dispatch_follows_the_spec_on_main(self):
        """Issues from a design branch wait for its merge; a row changed on main rewrites them; a removed one waits."""
        env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
               "GIT_COMMITTER_EMAIL": "t@t", "GIT_CONFIG_GLOBAL": os.devnull}
        os.environ.update(env)                                   # tearDown restores the environment
        git = lambda *a: subprocess.run(["git", *a], check=True, capture_output=True)  # noqa: E731
        open("docs/design/project.md", "w").write(
            "# P\n\n## Roadmap\n| Milestone | Features |\n|---|---|\n| M0 Base | `shell` |\n")
        os.remove("docs/design/foundations.md")
        json.dump({"tracker": "local", "starter": "label"}, open(".agent-team/config.json", "w"))
        open(".gitignore", "w").write("docs/tasks/\norigin.git/\n")
        git("init", "--bare", "-b", "main", "origin.git")
        git("init", "-b", "main")
        git("remote", "add", "origin", os.path.abspath("origin.git"))
        git("add", ".")
        git("commit", "-m", "project")
        git("push", "origin", "main")
        spec = ("---\nready: yes\n---\n# Shell\n\n## Task breakdown\n| # | Role | Task | Depends on | Issue |\n"
                "|---|---|---|---|---|\n| 1 | backend | {t} | - | - |\n{more}")
        git("checkout", "-b", "design/m0")
        open("docs/design/shell.md", "w").write(spec.format(t="Menu endpoint", more="| 2 | frontend | Menu | 1 | - |\n"))
        git("add", ".")
        git("commit", "-m", "design: shell")

        rc, out = call("create-issues.py")                        # from the design branch, before the merge
        self.assertIn("2 issue(s) and 1 milestone(s) created", out)
        rc, out = call("dispatch.py")
        self.assertIn("spec docs/design/shell.md not merged into origin/main yet", out)
        self.assertIn("Nothing to start", out)

        git("checkout", "main")
        git("merge", "--ff-only", "design/m0")
        git("push", "origin", "main")
        rc, out = call("dispatch.py")
        self.assertIn("Would start (1)", out)
        self.assertNotIn("Would update", out)

        # the review changes row 1 on main: the issue is rewritten before it starts
        open("docs/design/shell.md", "w").write(spec.format(t="Menu endpoint with paging", more="| 2 | frontend | Menu | 1 | - |\n"))
        git("commit", "-am", "review: paging")
        git("push", "origin", "main")
        rc, out = call("dispatch.py", "--apply")
        self.assertIn("Updating from the spec on origin/main (1)", out)
        t = config.tracker(config.load())
        api = next(i for i in t.issues() if core.key_of(i) == "docs/design/shell.md#1")
        self.assertIn("Menu endpoint with paging", api.title)
        self.assertTrue(core.started(api))
        rc, out = call("create-issues.py")
        self.assertIn("0 updated from their spec row", out)

        # row 2 removed: its task waits, and create-issues lists it
        open("docs/design/shell.md", "w").write(spec.format(t="Menu endpoint with paging", more=""))
        git("commit", "-am", "review: no frontend")
        git("push", "origin", "main")
        rc, out = call("dispatch.py")
        self.assertIn("its row is no longer in docs/design/shell.md on origin/main", out)
        rc, out = call("create-issues.py")
        self.assertIn("no longer in the plan", out)

        # spec-sync hook: a commit on main that adds a row creates its issue by itself
        os.symlink(SCRIPTS, "scripts")
        os.symlink("../../scripts/git-hooks/spec-sync.sh", ".git/hooks/post-commit")
        open("docs/design/shell.md", "w").write(spec.format(t="Menu endpoint with paging", more="| 3 | devops | Deploy | 1 | - |\n"))
        r = subprocess.run(["git", "commit", "-am", "review: deploy"], capture_output=True, text=True)
        self.assertIn("spec-sync: docs/design/ changed on main", r.stdout + r.stderr)
        self.assertTrue(any(core.key_of(i) == "docs/design/shell.md#3" for i in t.issues()), r.stdout + r.stderr)

    def test_dependency_on_another_spec(self):
        """Roadmap order "shell, auth"; a row of shell waits for row 1 of auth: auth is created first."""
        open("docs/design/project.md", "w").write(
            "# P\n\n## Roadmap\n| Milestone | Features |\n|---|---|\n| M0 Foundations | `shell` (navigation), `auth` |\n")
        os.remove("docs/design/foundations.md")
        row = "---\nready: yes\n---\n# {t}\n\n## Task breakdown\n| # | Role | Task | Depends on | Issue |\n|---|---|---|---|---|\n{r}"
        open("docs/design/shell.md", "w").write(row.format(t="Shell", r="| 1 | frontend | Login page | auth#1 | - |\n"))
        open("docs/design/auth.md", "w").write(row.format(t="Auth", r="| 1 | backend | Login endpoint | - | - |\n"))
        sc = scenarios()[0]
        json.dump(sc.cfg, open(".agent-team/config.json", "w"))
        rc, out = call("create-issues.py")
        self.assertEqual(rc, 0, out)
        self.assertLess(out.index("Login endpoint"), out.index("Login page"), out)
        t = config.tracker(config.load())
        by = {i.title: i for i in t.issues()}
        api, page = by["Auth · 1/1 · backend: Login endpoint"], by["Shell · 1/1 · frontend: Login page"]
        self.assertIn(api.id, core.section(page.body, "Depends on"))
        self.assertIn(api.ref, [str(b) for b in t.blockers(page)])
        self.assertEqual(core.code(page.milestone), "M0 Foundations")
        rc, out = call("create-issues.py")
        self.assertIn("0 issue(s) and 0 milestone(s) created", out)

    def test_cross_issue_local(self):
        self.run_cross_issue(scenarios()[0])

    def test_cross_issue_github(self):
        self.run_cross_issue(scenarios()[1])

    def test_cross_issue_jira(self):
        self.run_cross_issue(scenarios()[2])

    def test_local(self):
        self.run_flow(scenarios()[0])
        self.assertTrue(os.path.exists("docs/tasks/_milestones.json"))

    def test_github(self):
        self.run_flow(scenarios()[1])

    def test_jira(self):
        self.run_flow(scenarios()[2])

    def test_redmine(self):
        self.run_flow(scenarios()[3])

    def test_linear(self):
        self.run_flow(scenarios()[5])

    def test_gitlab(self):
        sc = scenarios()[4]
        self.run_flow(sc)
        self.assertEqual(len(sc.fake.pipelines), 3)                       # tasks 1, 3, then 2
        self.assertTrue(all(p["ref"] == "main" for p in sc.fake.pipelines))


class Units(unittest.TestCase):
    def test_dispatch_explains_milestones_without_tasks(self):
        d = script("dispatch.py")
        task = "## Task\nx\n\nTo start it: add `agent:backend`."
        design = [core.Issue(n, f"#{n}", f"Design: f{n} ({m})", milestone=f"{m} · x") for n, m in ((1, "M0"), (2, "M6"))]
        label, _, start, _, _ = d.plan(design, core.Tracker({}), 1, 3)
        self.assertEqual((label, start), ("no task issues", []))
        self.assertIn("M0 (1), M6 (1)", d.not_tasks(design, label)[0])
        # M6 has a task, M0 only a design issue: the plan says M0 is not designed yet
        issues = design + [core.Issue(3, "#3", "Task", task, milestone="M6 · x")]
        label, _, start, _, _ = d.plan(issues, core.Tracker({}), 1, 3)
        self.assertEqual(label, "milestone M6 · x")
        self.assertIn("M0 (1)", d.not_tasks(issues, label)[0])

    def test_dispatch_slots_per_service(self):
        d = script("dispatch.py")
        mk = lambda n, svc, labels=(): core.Issue(  # noqa: E731
            n, f"#{n}", f"F · {n}/9 · backend: {'[' + svc + '] ' if svc else ''}task {n}",
            "## Task\nx\n\nTo start it: add `agent:backend`.", labels=list(labels), milestone="M1 · x")
        self.assertEqual(core.service_of(mk(1, "orders")), "orders")
        self.assertIsNone(core.service_of(mk(1, None)))
        # one backend task per service; the task without a service waits for both
        issues = [mk(1, "orders", ["agent:backend"]), mk(2, "orders"), mk(3, "billing"), mk(4, None)]
        _, _, start, waiting, _ = d.plan(issues, core.Tracker({}), 1, 5)
        self.assertEqual([i.number for i, _ in start], ["3"])
        self.assertEqual(sorted(i.number for i, _ in waiting), ["2", "4"])

    def test_key_with_spaces(self):
        for marker in ("<!-- key: design:M0 Foundations:foundations -->", "[agent-team] key: design:M0 Foundations:foundations"):
            self.assertEqual(core.key_of(core.Issue(1, "#1", "t", f"x\n\n{marker}\n")), "design:M0 Foundations:foundations")

    def test_roadmap_features_with_commas_in_parentheses(self):
        from agentteam import specs
        row = ("`foundations` (Makefile, compose, FastAPI skeleton with `/health`), "
               "`app-shell` (navigation, theme); `alignment-control` (`ask`, then `auto`), Login screen (web, mobile)")
        self.assertEqual([specs.feature_name(f) for f in specs.items(row)],
                         ["foundations", "app-shell", "alignment-control", "Login screen"])
        self.assertEqual(specs.items("[a, b; c]"), ["a", "b", "c"])

    def test_cross_issue_dependency_format(self):
        from agentteam import plans

        def check(dep, number="13"):
            task = dict(PLAN["tasks"][1], depends_on=[dep])
            return plans.validate({"parent": number, "summary": "s", "tasks": [task]}, number)

        for ok in ("12:api", "#12:api", "PROJ-12:api-2"):
            self.assertEqual(check(ok), [], ok)
        for bad in ("12:", ":api", "12:API", "12 api", "12:api:x", "nokey"):
            self.assertTrue(check(bad), bad)
        self.assertTrue(check("13:api"))                       # its own issue: use the key alone

    def test_auto_starter_needs_agents_in_ci(self):
        from agentteam import starters
        gh = core.Tracker({})
        gh.name = "github"
        self.assertEqual(starters.make({"features": ["ci-agents"]}, gh).name, "label")
        self.assertEqual(starters.make({}, gh).name, "label")                       # full template
        self.assertEqual(starters.make({"features": []}, gh).name, "print")         # local scenario, GitHub issues
        self.assertEqual(starters.make({"features": [], "start_command": "x {id}"}, gh).name, "command")

    def test_jira_markup(self):
        from agentteam.trackers.jira import md_to_jira
        out = md_to_jira("## Task\n- one\n`agent:backend`\n```json\n{}\n```\n| a | b |\n|---|---|\n| 1 | 2 |")
        self.assertIn("h2. Task", out)
        self.assertIn("* one", out)
        self.assertIn("{{agent:backend}}", out)
        self.assertIn("{code:json}", out)
        self.assertIn("|| a || b ||", out)

    def test_command_starter_has_no_shell(self):
        from agentteam import starters
        issue = core.Issue("12", "#12", "x; touch /tmp/pwned", "To start it, add the label `agent:backend`")

        class T(core.Tracker):
            name = "t"
            def add_label(self, i, l):
                i.labels.append(l)
        st = starters.make({"starter": "command", "start_command": "echo {role} {title}"}, T({}))
        self.assertEqual(st.start(issue, "backend"), "ran echo")
        self.assertFalse(os.path.exists("/tmp/pwned"))



def docker_ok():
    return shutil.which("docker") and subprocess.run(["docker", "info"], capture_output=True).returncode == 0


REDMINE_SETUP = """
Setting.rest_api_enabled = '1'
IssueStatus.find_or_create_by!(name: 'On hold') { |s| s.is_closed = false }
Role.all.each { |r| Tracker.all.each { |t| IssueStatus.all.each { |a| IssueStatus.all.each { |b|
  WorkflowTransition.find_or_create_by!(role: r, tracker: t, old_status: a, new_status: b) unless a == b } } } }
puts 'KEY=' + User.find_by_login('admin').api_key
"""


class RealRedmine:
    """A Redmine server in Docker, with its default data, an "On hold" status and the REST API on."""

    def __init__(self):
        with socket_free() as port:
            self.url = f"http://127.0.0.1:{port}"
        self.id = subprocess.run(["docker", "run", "-d", "--rm", "-p", f"127.0.0.1:{port}:3000", "redmine:6"],
                                 capture_output=True, text=True, check=True).stdout.strip()
        end = time.time() + 300
        while time.time() < end:
            try:
                urllib.request.urlopen(self.url + "/", timeout=5).close()
                break
            except OSError:
                time.sleep(3)
        r = subprocess.run(["docker", "exec", self.id, "bash", "-c",
                            "cd /usr/src/redmine && REDMINE_LANG=en bundle exec rake redmine:load_default_data "
                            f">/dev/null && bundle exec rails runner \"$0\"", REDMINE_SETUP],
                           capture_output=True, text=True, timeout=600)
        keys = [line[4:] for line in r.stdout.splitlines() if line.startswith("KEY=")]
        if not keys:
            self.stop()
            raise RuntimeError(r.stdout[-2000:] + r.stderr[-2000:])
        self.key = keys[0]
        self.n = 0

    def stop(self):
        subprocess.run(["docker", "rm", "-f", self.id], capture_output=True)

    def api(self, method, path, body=None):
        req = urllib.request.Request(self.url + path, method=method, data=json.dumps(body).encode() if body else None,
                                     headers={"X-Redmine-API-Key": self.key, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        return json.loads(data) if data.strip() else {}

    def project(self):
        """A new empty project for each test."""
        self.n += 1
        ident = f"app{self.n}"
        self.api("POST", "/projects.json", {"project": {"name": f"App {self.n}", "identifier": ident, "is_public": True,
                                                        "enabled_module_names": ["issue_tracking"]}})
        return ident

    def close(self, n, name="Closed"):
        statuses = {s["name"]: s["id"] for s in self.api("GET", "/issue_statuses.json")["issue_statuses"]}
        self.api("PUT", f"/issues/{n}.json", {"issue": {"status_id": statuses[name]}})


@contextlib.contextmanager
def socket_free():
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    yield port


@unittest.skipUnless(os.environ.get("REDMINE_LIVE", "1") != "0" and docker_ok(), "Docker not available (or REDMINE_LIVE=0)")
class RedmineLive(TrackerFlow):
    """The same flows as the fake Redmine, against a real one."""

    @classmethod
    def setUpClass(cls):
        cls.server = RealRedmine()

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def scenario(self):
        return Scenario("redmine", {"tracker": "redmine", "starter": "label",
                                    "redmine": {"url": self.server.url, "project": self.server.project()}},
                        self.server, {"REDMINE_API_KEY": self.server.key})

    def test_flow(self):
        self.run_flow(self.scenario())

    def test_design_to_tasks(self):
        self.run_design_to_tasks(self.scenario())

    def test_check(self):
        sc = self.scenario()
        json.dump(sc.cfg, open(".agent-team/config.json", "w"))
        sc.install()
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "tracker.py"), "check"], capture_output=True,
                           text=True, env=os.environ.copy())
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("as admin", r.stdout)


for _name in [n for n in vars(TrackerFlow) if n.startswith("test_")]:   # only the flows above, not the fakes' tests
    setattr(RedmineLive, _name, None)

if __name__ == "__main__":
    unittest.main(verbosity=2)
