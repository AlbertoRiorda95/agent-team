#!/usr/bin/env python3
"""The guardrails as the tools apply them: the hooks with the JSON the tools
send, Codex's rules with `codex execpolicy`, OpenCode's permissions as
`opencode agent list` resolves them, and the GitLab pipeline merged from its
includes and checked against GitLab's schema.

The Codex, OpenCode and schema checks are skipped when their tool is missing
(validate.yml installs them). Run: python3 tests/test_tools.py
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEMPLATE = os.path.join(ROOT, "template")
HOOKS = os.path.join(TEMPLATE, "scripts", "hooks")
sys.path.insert(0, os.path.join(TEMPLATE, "scripts"))
from agentteam import profile  # noqa: E402

# what an agent must never run, and what it must still be able to run
FORBIDDEN = [
    "terraform apply", "terraform -chdir=infra apply", "kubectl -n prod apply -f x.yaml", "kubectl delete pod x",
    "helm upgrade app ./chart", "helm push chart.tgz oci://r", "docker push r/app:1", "docker --context x push r/app",
    "npm publish", "npm --registry https://r publish", "pnpm publish", "yarn publish", "twine upload dist/*",
    "python3 -m twine upload dist/*", "poetry publish --build", "uv publish", "cargo publish", "gem push a.gem",
    "mvn -B deploy", "./mvnw deploy -DskipTests", "./gradlew publish", "conan upload hello/1.0 -r team",
    "dotnet nuget push a.nupkg", "gh release create v1.0.0", "./ci/registry.sh publish",
    "git push --tags", "git push origin v1.2.0", "git push --follow-tags", "git push origin tag v1",
    "git push origin HEAD:refs/tags/v1", "echo ok && npm publish",
]
ALLOWED = [
    "npm ci", "npm test", "npm pack", "uv sync", "poetry install", "pip install -r requirements.txt",
    "mvn -B verify", "mvn install", "./gradlew build", "conan create .", "conan install .", "cargo build",
    "terraform plan", "kubectl get pods", "helm template .", "docker build .", "gh release view",
    "git push -u origin feat/v2-ui", "git status", "./ci/registry.sh login", "./ci/registry.sh local",
    "cat .npmrc",
]
SECRET_READS = [
    "cat ~/.npmrc", "cat $HOME/.m2/settings.xml", "grep token /home/me/.gradle/gradle.properties",
    "ls ~/.conan2", "cat ~/.cargo/credentials.toml", "cat ~/.pypirc", "pip config list",
    "python3 -m pip config list", "cat ~/.docker/config.json",
]


def run(cmd, inp=None, env=None, cwd=None, timeout=120):
    return subprocess.run(cmd, input=inp, capture_output=True, text=True, env=env, cwd=cwd, timeout=timeout)


def hook(name, tool_input, env=None, cwd=None):
    e = dict(os.environ, **(env or {}))
    return run(["bash", os.path.join(HOOKS, name)], json.dumps({"tool_input": tool_input}), e, cwd).returncode


def put(path, text):
    with open(path, "w") as f:
        f.write(text)


def tool(env_name, *names):
    for n in (os.environ.get(env_name), *names):
        if n and shutil.which(n):
            return shutil.which(n)
    return None


@unittest.skipUnless(shutil.which("jq"), "jq not installed")
class Hooks(unittest.TestCase):
    def test_block_infra_commands(self):
        for c in FORBIDDEN + SECRET_READS:
            with self.subTest(blocked=c):
                self.assertEqual(hook("block-infra-commands.sh", {"command": c}), 2)
        for c in ALLOWED:
            with self.subTest(allowed=c):
                self.assertEqual(hook("block-infra-commands.sh", {"command": c}), 0)
        self.assertEqual(hook("block-infra-commands.sh", {}), 0)

    def test_security_scope(self):
        env = {"CLAUDE_PROJECT_DIR": TEMPLATE}          # its scope file: localhost and 127.0.0.1
        for c in ["curl https://example.com", "curl example.com", "curl -s evil.com/path", "wget 10.0.0.5:8080/x",
                  "curl http://user@evil.com/", "nmap localhost", "ssh host", "nc -l 80"]:
            with self.subTest(blocked=c):
                self.assertEqual(hook("security-scope.sh", {"command": c}, env), 2)
        for c in ["curl -s http://localhost:3000/api", "curl localhost:3000/api", "curl -o out.json http://127.0.0.1:8080/x",
                  "curl -d @body.json http://localhost:3000", "jq . results.json", "npm test", "cat report.json"]:
            with self.subTest(allowed=c):
                self.assertEqual(hook("security-scope.sh", {"command": c}, env), 0)

    def test_security_writes(self):
        for f in ["docs/security/report.md", "/p/docs/security/2026-10-30.md"]:
            with self.subTest(allowed=f):
                self.assertEqual(hook("security-writes.sh", {"file_path": f}), 0)
        for f in ["src/app.ts", "/p/docs/design/x.md", "docs/securityx/a.md"]:
            with self.subTest(blocked=f):
                self.assertEqual(hook("security-writes.sh", {"file_path": f}), 2)

    def test_writer_writes(self):
        env = {"CLAUDE_PROJECT_DIR": "/p"}
        for f in ["docs/software/user-manual.md", "/p/docs/software/icd.md", "README.md", "/p/README.md"]:
            with self.subTest(allowed=f):
                self.assertEqual(hook("writer-writes.sh", {"file_path": f}, env), 0)
        for f in ["src/app.ts", "/p/docs/design/x.md", "/p/src/README.md", "docs/agents/README.md"]:
            with self.subTest(blocked=f):
                self.assertEqual(hook("writer-writes.sh", {"file_path": f}, env), 2)

    def test_alignment_check(self):
        with tempfile.TemporaryDirectory() as d:
            env = {"CLAUDE_PROJECT_DIR": d}
            self.assertEqual(hook("alignment-check.sh", {}, env), 0)       # no docs/alignment
            os.makedirs(os.path.join(d, "docs", "alignment"))
            for n in ("_template.md", "README.md"):
                put(os.path.join(d, "docs", "alignment", n), "status: open\n")
            put(os.path.join(d, "docs", "alignment", "done.md"), "status: resolved\n")
            self.assertEqual(hook("alignment-check.sh", {}, env), 0)
            put(os.path.join(d, "docs", "alignment", "api.md"), "---\nstatus: open\n---\n")
            self.assertEqual(hook("alignment-check.sh", {}, env), 2)

    def test_handoff_pointer(self):
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, CLAUDE_PROJECT_DIR=d)
            p = lambda: run(["bash", os.path.join(HOOKS, "handoff-pointer.sh")], "", env)  # noqa: E731
            self.assertEqual(p().stdout, "")
            os.makedirs(os.path.join(d, ".handoff"))
            note = os.path.join(d, ".handoff", "2026-10-30.md")
            put(note, '# Payments "v2" API\n\nnext steps\n')
            out = json.loads(p().stdout)["hookSpecificOutput"]
            self.assertEqual(out["hookEventName"], "SessionStart")
            self.assertIn(".handoff/2026-10-30.md", out["additionalContext"])
            old = time.time() - 8 * 86400
            os.utime(note, (old, old))
            self.assertEqual(p().stdout, "")

    def test_lint_frontend_ignores_other_files(self):
        self.assertEqual(hook("lint-frontend.sh", {"file_path": "README.md"}), 0)

    def test_role_hooks(self):
        """The role's checks for its own agent only; the lead session (no agent_type) is never limited."""
        def call(event, agent, tool, tool_input, scripts=HOOKS):
            data = {"tool_name": tool, "tool_input": tool_input, **({"agent_type": agent} if agent else {})}
            e = dict(os.environ, CLAUDE_PROJECT_DIR=TEMPLATE)
            return run(["bash", os.path.join(scripts, "role-hooks.sh"), event], json.dumps(data), e).returncode
        code, doc = {"file_path": "src/app.ts"}, {"file_path": "docs/software/guide.md"}
        cases = [("pre", "writer", "Write", code, 2), ("pre", "writer", "Edit", code, 2),
                 ("pre", "writer", "Write", doc, 0), ("pre", None, "Write", code, 0), ("pre", "backend", "Write", code, 0),
                 ("pre", "security", "Write", code, 2), ("pre", "security", "Write", {"file_path": "docs/security/r.md"}, 0),
                 ("pre", "security", "Bash", {"command": "curl https://evil.example.com"}, 2),
                 ("pre", "security", "Bash", {"command": "curl http://localhost:3000"}, 0),
                 ("pre", "backend", "Bash", {"command": "curl https://evil.example.com"}, 0),
                 ("post", "frontend", "Write", {"file_path": "README.md"}, 0), ("post", "writer", "Write", code, 0)]
        for event, agent, tool_name, tool_input, rc in cases:
            with self.subTest(event=event, agent=agent, tool=tool_name, input=tool_input):
                self.assertEqual(call(event, agent, tool_name, tool_input), rc)
        with tempfile.TemporaryDirectory() as d:          # a project without the writer role: nothing to run
            shutil.copy(os.path.join(HOOKS, "role-hooks.sh"), d)
            self.assertEqual(call("pre", "writer", "Write", code, d), 0)

    def test_never_fail_open_without_jq(self):
        with tempfile.TemporaryDirectory() as d:          # every command of the system but jq
            for p in ("/usr/bin", "/bin"):
                for n in os.listdir(p):
                    if n != "jq" and not os.path.lexists(os.path.join(d, n)):
                        os.symlink(os.path.join(p, n), os.path.join(d, n))
            env = {"PATH": d}
            for name, tool_input in (("block-infra-commands.sh", {"command": "npm publish"}),
                                     ("security-scope.sh", {"command": "curl https://evil.example.com"}),
                                     ("security-writes.sh", {"file_path": "src/a.ts"}),
                                     ("writer-writes.sh", {"file_path": "src/a.ts"})):
                with self.subTest(hook=name):
                    self.assertEqual(hook(name, tool_input, env), 2)

    @unittest.skipUnless(shutil.which("npm"), "npm not installed")
    def test_gate_test(self):
        with tempfile.TemporaryDirectory() as d:
            for script, rc in (("exit 0", 0), ("exit 1", 2)):
                put(os.path.join(d, "package.json"), json.dumps({"name": "x", "scripts": {"test": script}}))
                with self.subTest(test=script):
                    self.assertEqual(run(["bash", os.path.join(HOOKS, "gate-test.sh")], "", cwd=d).returncode, rc)


CODEX = tool("CODEX_BIN", "codex")


@unittest.skipUnless(CODEX, "codex not installed")
class CodexRules(unittest.TestCase):
    """codex loads the rules (it checks every rule's match/not_match examples) and decides like the hook."""

    def decide(self, cmd):
        r = run([CODEX, "execpolicy", "check", "--rules", os.path.join(TEMPLATE, ".codex/rules/agent-team.rules"),
                 "--", *cmd.split()])
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout).get("decision")

    def test_rules(self):
        for c in ["git push --force", "git push origin main", "gh pr merge 3", "terraform apply", "npm publish",
                  "twine upload dist/*", "poetry publish", "uv publish", "conan upload hello/1.0 -r team",
                  "dotnet nuget push a.nupkg", "gh release create v1.0.0", "git push --tags", "docker push r/app:1"]:
            with self.subTest(forbidden=c):
                self.assertEqual(self.decide(c), "forbidden")
        for c in ["npm ci", "npm test", "git status", "conan create .", "uv sync", "gh release view"]:
            with self.subTest(allowed=c):
                self.assertNotEqual(self.decide(c), "forbidden")


OPENCODE = tool("OPENCODE_BIN", "opencode")


def oc_match(pattern, text):
    rx = "".join(".*" if ch == "*" else "." if ch == "?" else re.escape(ch) for ch in pattern)
    return re.fullmatch(rx, text, re.S) is not None


@unittest.skipUnless(OPENCODE, "opencode not installed")
class OpenCodePermissions(unittest.TestCase):
    """The permissions `opencode agent list` resolves for each role; the last matching rule wins."""

    @classmethod
    def setUpClass(cls):
        home = tempfile.mkdtemp()
        env = dict(os.environ, HOME=home, XDG_CONFIG_HOME=f"{home}/.config", XDG_DATA_HOME=f"{home}/.local/share",
                   XDG_CACHE_HOME=f"{home}/.cache", XDG_STATE_HOME=f"{home}/.local/state")
        r = run([OPENCODE, "agent", "list"], env=env, cwd=TEMPLATE, timeout=180)
        shutil.rmtree(home, ignore_errors=True)
        assert r.returncode == 0, r.stderr
        parts = re.split(r"^(\S+) \((\w+)\)\n", r.stdout, flags=re.M)
        cls.agents = {parts[i]: (parts[i + 1], json.loads(parts[i + 2])) for i in range(1, len(parts), 3)}

    def action(self, agent, permission, text):
        rules = [r for r in self.agents[agent][1] if r["permission"] == permission and oc_match(r["pattern"], text)]
        return rules[-1]["action"] if rules else None

    def test_roles_load(self):
        for role in ("backend", "designer", "devops", "frontend", "optimizer", "security", "writer"):
            with self.subTest(role=role):
                self.assertIn(role, self.agents)
                self.assertEqual(self.agents[role][0], "all")

    def test_bash_denied(self):
        for role in ("backend", "frontend", "devops", "writer", "security"):
            for c in ["npm publish", "git push --tags", "git push --force origin x", "gh pr merge 1",
                      "terraform apply", "conan upload x -r t", "uv publish", "gh release create v1"]:
                with self.subTest(role=role, command=c):
                    self.assertEqual(self.action(role, "bash", c), "deny")
            with self.subTest(role=role, command="git status"):
                self.assertNotEqual(self.action(role, "bash", "git status"), "deny")

    def test_writer_edits(self):
        for f in ["docs/software/user-manual.md", "README.md"]:
            with self.subTest(allowed=f):
                self.assertEqual(self.action("writer", "edit", f), "allow")
        for f in ["src/app.ts", "docs/design/x.md"]:
            with self.subTest(denied=f):
                self.assertEqual(self.action("writer", "edit", f), "deny")

    def test_secrets_not_read(self):
        for f in [".env", ".env.local", "secrets/key.pem"]:
            with self.subTest(file=f):
                self.assertNotEqual(self.action("backend", "read", f), "allow")


def load_yaml():
    try:
        import yaml
        return yaml
    except ImportError:
        return None


YAML = load_yaml()
SCHEMA = tool("CHECK_JSONSCHEMA_BIN", "check-jsonschema")


@unittest.skipUnless(YAML, "PyYAML not installed")
class GitLabPipeline(unittest.TestCase):
    """The GitLab pipeline of a full profile, merged from its includes as GitLab does."""

    KEYWORDS = {"default", "include", "stages", "variables", "workflow", "image", "services", "cache",
                "before_script", "after_script"}

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        profile.render_tree(TEMPLATE, cls.tmp, {"ci": "gitlab", "tracker": "gitlab",
                                                "features": ["ci-agents", "split", "spec-sync", "team-tasks"]})
        def load(rel):
            with open(os.path.join(cls.tmp, rel)) as f:
                return YAML.safe_load(f) or {}
        root = load(".gitlab-ci.yml.example")
        cls.merged = {}
        for inc in root.get("include", []):
            cls.merged.update(load(inc["local"]))
        cls.merged.update({k: v for k, v in root.items() if k != "include"})
        cls.jobs = {k: v for k, v in cls.merged.items() if k not in cls.KEYWORDS}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def test_references(self):
        stages = set(self.merged.get("stages", [])) | {".pre", ".post"}
        for name, job in self.jobs.items():
            if not isinstance(job, dict):
                continue
            ext = job.get("extends", [])
            for e in [ext] if isinstance(ext, str) else ext:
                with self.subTest(job=name, extends=e):
                    self.assertIn(e, self.jobs)
            for n in job.get("needs", []):
                n = n["job"] if isinstance(n, dict) else n
                with self.subTest(job=name, needs=n):
                    self.assertIn(n, self.jobs)
            if not name.startswith(".") and "stage" in job:
                with self.subTest(job=name, stage=job["stage"]):
                    self.assertIn(job["stage"], stages)

    def test_registry_login_before_install(self):
        for name, job in self.jobs.items():
            script = job.get("script", []) if isinstance(job, dict) else []
            script = [script] if isinstance(script, str) else script
            installs = [i for i, s in enumerate(script) if re.match(r"(npm ci|pip install|mvn|conan install)", str(s))]
            if installs and not name.startswith("."):
                before = [s for s in (job.get("before_script") or []) + script[:installs[0]]]
                with self.subTest(job=name):
                    self.assertTrue(any("registry.sh login" in str(s) for s in before), f"{name}: no login before install")

    @unittest.skipUnless(SCHEMA, "check-jsonschema not installed")
    def test_schema(self):
        p = os.path.join(self.tmp, "merged-gitlab-ci.yml")
        put(p, YAML.safe_dump(self.merged, sort_keys=False))
        r = run([SCHEMA, "--builtin-schema", "vendor.gitlab-ci", p])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
