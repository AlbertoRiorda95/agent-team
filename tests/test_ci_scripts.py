#!/usr/bin/env python3
"""The CI's own scripts, run as the CI runs them, on small sample projects:
ci/install-scanners.sh, ci/scan.sh (sbom-licenses, vulnerabilities, static)
and ci/reference.sh. Each check must pass on a clean project and fail on one
with the problem it looks for: a vulnerable dependency, a committed secret, a
static-analysis finding introduced by a change.

Versions: every version in ci/scanners.env exists where install-scanners.sh
and reference.sh download it from.

Needs the network, Linux amd64, jq, npm and a working `python3 -m venv`;
skipped otherwise (or with CI_SCRIPTS_LIVE=0). The scanners go to a temporary
directory, never to ~/.local/bin.
Run: python3 tests/test_ci_scripts.py
"""
import glob
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
import unittest
import urllib.error
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEMPLATE = os.path.join(ROOT, "template")


def scanners_env():
    env = {}
    with open(os.path.join(TEMPLATE, "ci", "scanners.env")) as f:
        for line in f:
            m = re.match(r'^([A-Z_]+)=("?)(.*)\2\s*$', line.strip())
            if m:
                env[m.group(1)] = m.group(3)
    return env


V = scanners_env()


def answers(url, method="HEAD"):
    req = urllib.request.Request(url, method=method, headers={"User-Agent": "agent-team-tests"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status < 400
    except urllib.error.HTTPError as e:
        return e.code < 400


def online():
    try:
        return answers("https://github.com")
    except OSError:
        return False


def venv_works():
    with tempfile.TemporaryDirectory() as d:
        return subprocess.run(["python3", "-m", "venv", d], capture_output=True).returncode == 0


ONLINE = os.environ.get("CI_SCRIPTS_LIVE") != "0" and online()
LIVE = (ONLINE and platform.system() == "Linux" and platform.machine() in ("x86_64", "AMD64")
        and shutil.which("jq") and shutil.which("npm") and venv_works())


@unittest.skipUnless(ONLINE, "no network (or CI_SCRIPTS_LIVE=0)")
class Versions(unittest.TestCase):
    def test_release_assets(self):
        gh = "https://github.com/{}/releases/download/v{}/{}"
        assets = [("anchore/syft", V["SYFT_VERSION"], "syft_{}_linux_amd64.tar.gz"),
                  ("anchore/syft", V["SYFT_VERSION"], "syft_{}_checksums.txt"),
                  ("anchore/grype", V["GRYPE_VERSION"], "grype_{}_linux_amd64.tar.gz"),
                  ("anchore/grype", V["GRYPE_VERSION"], "grype_{}_checksums.txt"),
                  ("aquasecurity/trivy", V["TRIVY_VERSION"], "trivy_{}_Linux-64bit.tar.gz"),
                  ("aquasecurity/trivy", V["TRIVY_VERSION"], "trivy_{}_checksums.txt"),
                  ("rhysd/actionlint", V["ACTIONLINT_VERSION"], "actionlint_{}_linux_amd64.tar.gz"),
                  ("rhysd/actionlint", V["ACTIONLINT_VERSION"], "actionlint_{}_checksums.txt")]
        for repo, version, asset in assets:
            url = gh.format(repo, version, asset.format(version))
            with self.subTest(url=url):
                self.assertTrue(answers(url), url)

    def test_packages(self):
        for url in (f"https://pypi.org/pypi/semgrep/{V['SEMGREP_VERSION']}/json",
                    f"https://pypi.org/pypi/pdoc/{V['PDOC_VERSION']}/json",
                    f"https://registry.npmjs.org/@redocly/cli/{V['REDOCLY_VERSION']}",
                    f"https://registry.npmjs.org/typedoc/{V['TYPEDOC_VERSION']}"):
            with self.subTest(url=url):
                self.assertTrue(answers(url, "GET"), url)


def put(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def git(cwd, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd, check=True,
                   capture_output=True)


class Sample:
    """A Git repository with the template's ci/ folder."""

    def __init__(self, test, scanners_bin=None, **settings):
        self.dir = tempfile.mkdtemp()
        test.addCleanup(shutil.rmtree, self.dir, True)
        shutil.copytree(os.path.join(TEMPLATE, "ci"), os.path.join(self.dir, "ci"))
        path = os.path.join(self.dir, "ci", "scanners.env")
        with open(path) as f:
            text = f.read()
        for k, v in settings.items():
            text, n = re.subn(rf"^{k}=.*$", lambda _: f"{k}={v}", text, flags=re.M)
            assert n == 1, k
        put(path, text)
        put(os.path.join(self.dir, ".gitignore"), "node_modules/\nreports/\n")
        self.env = dict(os.environ, SCANNERS_BIN=scanners_bin or "")
        git(self.dir, "init", "-q", "-b", "main")

    def path(self, *p):
        return os.path.join(self.dir, *p)

    def commit(self, msg="c"):
        git(self.dir, "add", "-A")
        git(self.dir, "commit", "-q", "-m", msg)

    def run(self, *cmd, timeout=1800, **env):
        r = subprocess.run(list(cmd), cwd=self.dir, capture_output=True, text=True, env=dict(self.env, **env),
                           timeout=timeout)
        return r.returncode, r.stdout + r.stderr

    def npm_app(self, deps):
        put(self.path("package.json"), json.dumps({"name": "app", "version": "0.0.0", "license": "MIT",
                                                   "dependencies": deps}))
        rc, out = self.run("npm", "install", "--ignore-scripts", "--no-audit", "--no-fund")
        assert rc == 0, out


@unittest.skipUnless(LIVE, "needs the network, Linux amd64, jq, npm and python3 -m venv (or CI_SCRIPTS_LIVE=0)")
class Scan(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.bin = os.path.join(cls.tmp, "bin")
        cls.home = os.path.join(cls.tmp, "home")             # semgrep's venv goes under $HOME/.local
        os.makedirs(cls.home)
        env = dict(os.environ, SCANNERS_BIN=cls.bin, HOME=cls.home)
        env.pop("GITHUB_PATH", None)
        for tools in ([], ["semgrep"]):
            r = subprocess.run(["bash", os.path.join(TEMPLATE, "ci", "install-scanners.sh"), *tools],
                               capture_output=True, text=True, env=env, timeout=1800)
            assert r.returncode == 0, r.stdout + r.stderr
        cls.installed = r.stdout

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, True)

    def sample(self, **settings):
        s = Sample(self, self.bin, **settings)
        s.env["HOME"] = self.home
        return s

    def test_installed_at_the_pinned_versions(self):
        for tool in ("syft", "grype", "trivy", "semgrep"):
            r = subprocess.run([os.path.join(self.bin, tool), "--version"], capture_output=True, text=True)
            version = V[tool.upper() + "_VERSION"]
            with self.subTest(tool=tool):
                self.assertIn(version, r.stdout + r.stderr)

    def test_clean_project_passes(self):
        s = self.sample()
        s.npm_app({"ms": "2.1.3"})
        rc, out = s.run("./ci/scan.sh", "sbom-licenses")
        self.assertEqual(rc, 0, out[-3000:])
        for f in ("sbom.cdx.json", "sbom.spdx.json", "licenses.csv", "licenses.txt", "licenses-trivy.json"):
            self.assertTrue(os.path.exists(s.path("reports", f)), f)
        with open(s.path("reports", "licenses.csv")) as f:
            self.assertIn('"ms","2.1.3","MIT"', f.read())
        rc, out = s.run("./ci/scan.sh", "vulnerabilities")
        self.assertEqual(rc, 0, out[-3000:])
        self.assertTrue(os.path.exists(s.path("reports", "grype.sarif")))

    def test_vulnerable_dependency_fails(self):
        s = self.sample()
        s.npm_app({"lodash": "4.17.15"})                      # prototype pollution, critical
        self.assertEqual(s.run("./ci/scan.sh", "sbom-licenses")[0], 0)
        rc, out = s.run("./ci/scan.sh", "vulnerabilities")
        self.assertEqual(rc, 1, out[-3000:])
        self.assertIn("lodash", out)

    def test_committed_secret_fails(self):
        s = self.sample()
        s.npm_app({})
        # built at run time, so that this source is not itself a committed secret
        put(s.path("config", "deploy.env"), "AWS_ACCESS_KEY_ID=" + "AKIA" + "QWERTYUIOPASDFGH\n"
            "AWS_SECRET_ACCESS_KEY=" + "Zm9vYmFyYmF6cXV4" + "cXV1eHF1dXgxMjM0NTY3ODkwYWJj\n")
        self.assertEqual(s.run("./ci/scan.sh", "sbom-licenses")[0], 0)
        rc, out = s.run("./ci/scan.sh", "vulnerabilities")
        self.assertEqual(rc, 1, out[-3000:])
        self.assertIn("deploy.env", out)

    def test_static_counts_only_what_the_change_introduces(self):
        rule = ("rules:\n- id: no-eval\n  languages: [javascript]\n  severity: ERROR\n"
                "  message: eval of a variable\n  pattern: eval($X)\n")
        s = self.sample(SEMGREP_CONFIG='"ci/rules.yml"')
        put(s.path("ci", "rules.yml"), rule)
        put(s.path("old.js"), "eval(process.argv[2])\n")       # already on main
        s.commit("main")
        rc, out = s.run("./ci/scan.sh", "static")
        self.assertEqual(rc, 0, out[-3000:])                   # full scan: reported, not failed
        self.assertIn("1 finding(s)", out)
        git(s.dir, "checkout", "-q", "-b", "change")
        put(s.path("ok.js"), "console.log(1)\n")
        s.commit("clean change")
        rc, out = s.run("./ci/scan.sh", "static", BASELINE_REF="main")
        self.assertEqual(rc, 0, out[-3000:])
        self.assertIn("0 finding(s)", out)
        put(s.path("new.js"), "eval(process.env.X)\n")
        s.commit("bad change")
        rc, out = s.run("./ci/scan.sh", "static", BASELINE_REF="main")
        self.assertEqual(rc, 1, out[-3000:])
        self.assertIn("1 finding(s)", out)

    def test_static_default_rules(self):
        s = self.sample()
        put(s.path("app.js"), "console.log(1)\n")
        s.commit()
        rc, out = s.run("./ci/scan.sh", "static")
        self.assertEqual(rc, 0, out[-3000:])
        self.assertTrue(os.path.exists(s.path("reports", "semgrep.sarif")))


@unittest.skipUnless(LIVE, "needs the network, Linux amd64, jq, npm and python3 -m venv (or CI_SCRIPTS_LIVE=0)")
class Reference(unittest.TestCase):
    def test_nothing_applies(self):
        s = Sample(self)
        rc, out = s.run("./ci/reference.sh")
        self.assertEqual(rc, 0, out)
        self.assertIn("no generator applies", out)

    def test_every_generator(self):
        s = Sample(self)
        put(s.path("docs/api/openapi.yaml"), OPENAPI)
        put(s.path("tsconfig.json"), json.dumps({"compilerOptions": {"strict": True, "target": "ES2022"},
                                                 "include": ["src"]}))
        put(s.path("src/greet.ts"), "/** Says hello. */\nexport function greet(name: string): string {\n"
                                    "  return `hello ${name}`\n}\n")
        put(s.path("pyproject.toml"), '[project]\nname = "shop"\nversion = "0.1.0"\n')
        put(s.path("src/shop/__init__.py"), '"""The shop."""\n\n\ndef total(prices):\n'
                                            '    """Sum of the prices."""\n    return sum(prices)\n')
        put(s.path("package.json"), json.dumps({"name": "app", "version": "0.0.0", "private": True,
                                                "devDependencies": {"typescript": "5.9.3"}}))
        rc, out = s.run("npm", "install", "--ignore-scripts", "--no-audit", "--no-fund")
        self.assertEqual(rc, 0, out)
        rc, out = s.run("./ci/reference.sh")
        self.assertEqual(rc, 0, out[-3000:])
        ref = s.path("reports", "reference")
        with open(os.path.join(ref, "api", "index.html")) as f:
            self.assertIn("Shop API", f.read())
        self.assertTrue(glob.glob(os.path.join(ref, "typescript", "**", "greet*.html"), recursive=True))
        with open(os.path.join(ref, "python", "shop.html")) as f:
            self.assertIn("Sum of the prices", f.read())
        self.assertFalse(os.path.exists(os.path.join(ref, ".pdoc-venv")))

    def test_failing_generator_fails(self):
        s = Sample(self)
        put(s.path("docs/api/openapi.yaml"), "openapi: 3.1.0\ninfo: {}\npaths: 7\n")
        rc, out = s.run("./ci/reference.sh")
        self.assertNotEqual(rc, 0, out[-3000:])


OPENAPI = """openapi: 3.1.0
info:
  title: Shop API
  version: 0.1.0
paths:
  /orders:
    get:
      summary: List the orders
      operationId: listOrders
      responses:
        "200":
          description: The orders
"""

if __name__ == "__main__":
    unittest.main()
