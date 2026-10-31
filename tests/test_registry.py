#!/usr/bin/env python3
"""ci/registry.sh: login, publish and local for each package manager.

Offline: what the script writes (the token only in user-level configuration,
never on stdout), what it refuses, the local repository. Live, when Docker and
the package manager are there: a real upload to Verdaccio (npm), pypiserver
(PyPI), Reposilite (Maven, Gradle) and conan_server (Conan), and a read back.

Every run uses a temporary HOME. Run: python3 tests/test_registry.py
"""
import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEMPLATE = os.path.join(ROOT, "template")
TOKEN = "s3cr&t<token>"
CI_VARS = ("CI", "GITHUB_ACTIONS", "GITHUB_TOKEN", "CI_JOB_TOKEN", "REGISTRY_TOKEN", "REGISTRY_PUBLISH_TOKEN",
           "GRADLE_USER_HOME", "CONAN_HOME", "MAVEN_OPTS", "PIP_CONFIG_FILE", "XDG_CONFIG_HOME", "NPM_CONFIG_USERCONFIG")


def put(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def read(path):
    with open(path) as f:
        return f.read()


def venv_works():
    with tempfile.TemporaryDirectory() as d:
        return subprocess.run(["python3", "-m", "venv", d], capture_output=True).returncode == 0


class Project:
    """A project with ci/registry.sh, its settings, and a HOME of its own."""

    def __init__(self, test, **settings):
        self.dir = tempfile.mkdtemp()
        test.addCleanup(shutil.rmtree, self.dir, True)
        self.home = os.path.join(self.dir, "home")
        os.makedirs(os.path.join(self.dir, "ci"))
        os.makedirs(self.home)
        shutil.copy(os.path.join(TEMPLATE, "ci", "registry.sh"), os.path.join(self.dir, "ci"))
        env = read(os.path.join(TEMPLATE, "ci", "registry.env"))
        for k, v in settings.items():
            env, n = re.subn(rf"^{k}=.*$", lambda _: f"{k}={v}", env, flags=re.M)
            assert n == 1, k
        put(os.path.join(self.dir, "ci", "registry.env"), env)
        self.env = {k: v for k, v in os.environ.items() if k not in CI_VARS}
        self.env.update(HOME=self.home, XDG_CONFIG_HOME=os.path.join(self.home, ".config"),
                        MAVEN_OPTS=f"-Duser.home={self.home}", GRADLE_USER_HOME=os.path.join(self.home, ".gradle"),
                        CONAN_HOME=os.path.join(self.home, ".conan2"))

    def path(self, *p):
        return os.path.join(self.dir, *p)

    def run(self, action, timeout=600, **env):
        r = subprocess.run(["bash", "ci/registry.sh", action], cwd=self.dir, capture_output=True, text=True,
                           env=dict(self.env, **env), timeout=timeout)
        return r.returncode, r.stdout + r.stderr


class Offline(unittest.TestCase):
    def test_nothing_configured(self):
        p = Project(self)
        for a in ("login", "publish", "local"):
            self.assertEqual(p.run(a)[0], 0)
        self.assertEqual(p.run("deploy")[0], 2)

    def test_not_a_package(self):
        p = Project(self, REGISTRY_KIND="npm", REGISTRY_URL="https://r.example/")
        for a in ("publish", "local"):
            rc, out = p.run(a, REGISTRY_PUBLISH_TOKEN=TOKEN)
            self.assertEqual(rc, 0)
            self.assertIn("not a package", out)

    def test_without_registry(self):
        p = Project(self, REGISTRY_KIND="maven", PUBLISH_PACKAGE="yes")
        self.assertEqual(p.run("login", REGISTRY_TOKEN=TOKEN)[0], 0)
        rc, out = p.run("publish", REGISTRY_PUBLISH_TOKEN=TOKEN)
        self.assertEqual(rc, 1)
        self.assertIn("registry.sh local", out)

    def test_no_token(self):
        p = Project(self, REGISTRY_KIND="npm", REGISTRY_URL="https://r.example/", PUBLISH_PACKAGE="yes")
        for a in ("login", "publish"):
            self.assertEqual(p.run(a)[0], 1)

    def test_unknown_kind(self):
        p = Project(self, REGISTRY_KIND="nuget", REGISTRY_URL="https://r.example/", PUBLISH_PACKAGE="yes")
        self.assertEqual(p.run("login", REGISTRY_TOKEN=TOKEN)[0], 2)
        self.assertEqual(p.run("local")[0], 2)

    def test_token_sources(self):
        p = Project(self, REGISTRY_KIND="custom", REGISTRY_URL="https://r.example/", PUBLISH_PACKAGE="yes",
                    LOGIN_COMMAND="'echo \"$REGISTRY_AUTH_USER:$REGISTRY_AUTH_TOKEN\" > \"$HOME/creds\"'",
                    PUBLISH_COMMAND="'echo \"$REGISTRY_AUTH_USER:$REGISTRY_AUTH_TOKEN\" > \"$HOME/creds\"'")
        creds = lambda: read(os.path.join(p.home, "creds")).strip()  # noqa: E731
        cases = [("login", {"REGISTRY_TOKEN": "r", "GITHUB_TOKEN": "g"}, "token:r"),
                 ("login", {"CI_JOB_TOKEN": "j"}, "gitlab-ci-token:j"),
                 ("login", {"GITHUB_TOKEN": "g"}, "x-access-token:g"),
                 ("publish", {"REGISTRY_TOKEN": "r", "REGISTRY_PUBLISH_TOKEN": "w"}, "token:w"),
                 ("publish", {"REGISTRY_TOKEN": "r", "GITHUB_TOKEN": "g"}, "x-access-token:g")]
        for action, env, want in cases:
            with self.subTest(action=action, env=env):
                rc, out = p.run(action, **env)
                self.assertEqual(rc, 0, out)
                self.assertEqual(creds(), want)
                self.assertNotIn(want.split(":")[1] + "\n", out)

    def test_github_masks_the_token(self):
        p = Project(self, REGISTRY_KIND="custom", REGISTRY_URL="https://r.example/", LOGIN_COMMAND="true")
        rc, out = p.run("login", REGISTRY_TOKEN=TOKEN, GITHUB_ACTIONS="true")
        self.assertEqual(rc, 0)
        self.assertIn(f"::add-mask::{TOKEN}", out)
        self.assertEqual(out.count(TOKEN), 1)

    @unittest.skipUnless(shutil.which("npm"), "npm not installed")
    def test_npm_login(self):
        p = Project(self, REGISTRY_KIND="npm", REGISTRY_URL="https://npm.pkg.github.com/", REGISTRY_SCOPE="@team")
        rc, out = p.run("login", REGISTRY_TOKEN=TOKEN)
        self.assertEqual(rc, 0, out)
        self.assertNotIn(TOKEN, out)
        rc_file = read(os.path.join(p.home, ".npmrc"))
        self.assertIn("@team:registry=https://npm.pkg.github.com/", rc_file)
        self.assertIn("//npm.pkg.github.com/:_authToken=", rc_file)
        self.assertFalse(os.path.exists(p.path(".npmrc")))      # nothing in the repository

    def test_maven_login(self):
        p = Project(self, REGISTRY_KIND="maven", REGISTRY_URL="https://maven.example/")
        settings = os.path.join(p.home, ".m2", "settings.xml")
        self.assertEqual(p.run("login", REGISTRY_TOKEN=TOKEN)[0], 0)
        self.assertIn("<password>s3cr&amp;t&lt;token&gt;</password>", read(settings))
        self.assertEqual(oct(os.stat(settings).st_mode & 0o777), "0o600")
        put(settings, "<settings><!-- mine --></settings>")
        rc, out = p.run("login", REGISTRY_TOKEN=TOKEN)
        self.assertEqual(rc, 1)
        self.assertIn("${env.REGISTRY_TOKEN}", out)
        self.assertIn("mine", read(settings))                    # a file of yours is left alone
        self.assertEqual(p.run("login", REGISTRY_TOKEN=TOKEN, CI="true")[0], 0)
        self.assertIn("written by ci/registry.sh", read(settings))   # setup-java's file, on a runner

    def test_gradle_login(self):
        p = Project(self, REGISTRY_KIND="gradle", REGISTRY_URL="https://maven.example/")
        props = os.path.join(p.home, ".gradle", "gradle.properties")
        put(props, "org.gradle.jvmargs=-Xmx2g\nteamPassword=old\n")
        self.assertEqual(p.run("login", REGISTRY_TOKEN=TOKEN)[0], 0)
        text = read(props)
        self.assertIn("org.gradle.jvmargs=-Xmx2g", text)
        self.assertEqual(text.count("teamPassword="), 1)
        self.assertIn(f"teamPassword={TOKEN}", text)
        self.assertIn("teamUsername=token", text)

    def test_pypi_login(self):
        for url, want in (("https://pypi.example/simple/", "https://token:a%40b%3Ac%2F@pypi.example/simple/"),
                          ("http://127.0.0.1:8080/simple/", "http://token:a%40b%3Ac%2F@127.0.0.1:8080/simple/")):
            p = Project(self, REGISTRY_KIND="pypi", REGISTRY_URL=url)
            rc, out = p.run("login", REGISTRY_TOKEN="a@b:c/")
            self.assertEqual(rc, 0, out)
            self.assertIn(f"extra-index-url = {want}", read(os.path.join(p.home, ".config", "pip", "pip.conf")))

    @unittest.skipUnless(shutil.which("npm"), "npm not installed")
    def test_npm_local(self):
        p = Project(self, REGISTRY_KIND="npm", PUBLISH_PACKAGE="yes", LOCAL_REPOSITORY="$HOME/pkgs")
        put(p.path("package.json"), json.dumps({"name": "@team/lib", "version": "1.2.0"}))
        rc, out = p.run("local")
        self.assertEqual(rc, 0, out)
        self.assertEqual(os.listdir(os.path.join(p.home, "pkgs")), ["team-lib-1.2.0.tgz"])
        # another project installs it from the file (chapter 5)
        app = Project(self)
        put(app.path("package.json"), json.dumps({"name": "app", "version": "0.0.0"}))
        r = subprocess.run(["npm", "install", "--offline", os.path.join(p.home, "pkgs", "team-lib-1.2.0.tgz")],
                           cwd=app.dir, capture_output=True, text=True, env=app.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(read(app.path("node_modules/@team/lib/package.json")))["version"], "1.2.0")

    @unittest.skipUnless(venv_works(), "python3 -m venv does not work here (python3-venv)")
    def test_pypi_local(self):
        p = Project(self, REGISTRY_KIND="pypi", PUBLISH_PACKAGE="yes", LOCAL_REPOSITORY="$HOME/pkgs")
        put(p.path("pyproject.toml"), PYPROJECT)
        put(p.path("src", "team_lib", "__init__.py"), "VERSION = '1.2.0'\n")
        rc, out = p.run("local")
        self.assertEqual(rc, 0, out[-2000:])
        pkgs = os.path.join(p.home, "pkgs")
        self.assertEqual(sorted(os.listdir(pkgs)), ["team_lib-1.2.0-py3-none-any.whl", "team_lib-1.2.0.tar.gz"])
        # another project installs it from the directory, without an index (chapter 5)
        venv = os.path.join(p.dir, "consumer")
        subprocess.run(["python3", "-m", "venv", venv], check=True)
        r = subprocess.run([os.path.join(venv, "bin", "pip"), "install", "--no-index", "--find-links", pkgs, "team-lib"],
                           capture_output=True, text=True, env=p.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = subprocess.run([os.path.join(venv, "bin", "python"), "-c", "import team_lib; print(team_lib.VERSION)"],
                           capture_output=True, text=True, cwd=p.home)
        self.assertEqual(r.stdout.strip(), "1.2.0", r.stderr)

    @unittest.skipUnless(shutil.which("mvn"), "maven not installed")
    def test_maven_local(self):
        p = Project(self, REGISTRY_KIND="maven", PUBLISH_PACKAGE="yes")
        put(p.path("pom.xml"), POM.format(dist=""))
        rc, out = p.run("local")
        self.assertEqual(rc, 0, out)
        self.assertTrue(os.path.exists(os.path.join(p.home, ".m2/repository/team/lib/1.2.0/lib-1.2.0.pom")))
        # another project declares the dependency: Maven reads ~/.m2 first (chapter 5)
        app = Project(self)
        app.env = p.env
        put(app.path("pom.xml"), CONSUMER_POM)
        r = subprocess.run(["mvn", "-B", "-q", "dependency:tree"], cwd=app.dir, capture_output=True, text=True,
                           env=app.env, timeout=600)
        self.assertEqual(r.returncode, 0, r.stdout[-3000:])

    @unittest.skipUnless(shutil.which("gradle"), "gradle not installed")
    def test_gradle_local(self):
        p = Project(self, REGISTRY_KIND="gradle", PUBLISH_PACKAGE="yes")
        put(p.path("settings.gradle"), 'rootProject.name = "lib"\n')
        put(p.path("build.gradle"), GRADLE_LIB.format(repo=""))
        put(p.path("src/main/java/team/Lib.java"), "package team; public class Lib { public static int one() { return 1; } }\n")
        rc, out = p.run("local")
        self.assertEqual(rc, 0, out[-3000:])
        # another project reads mavenLocal() (chapter 5)
        app = Project(self)
        app.env = p.env
        put(app.path("settings.gradle"), 'rootProject.name = "app"\n')
        put(app.path("build.gradle"), "plugins { id 'java' }\nrepositories { mavenLocal() }\n"
                                      "dependencies { implementation 'team:lib:1.2.0' }\n")
        put(app.path("src/main/java/app/App.java"), "package app; public class App { int x = team.Lib.one(); }\n")
        r = subprocess.run(["gradle", "-q", "compileJava"], cwd=app.dir, capture_output=True, text=True,
                           env=app.env, timeout=600)
        self.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr[-3000:])

    @unittest.skipUnless(shutil.which("conan"), "conan not installed")
    def test_conan_local(self):
        p = Project(self, REGISTRY_KIND="conan", PUBLISH_PACKAGE="yes")
        put(p.path("conanfile.py"), CONANFILE)
        put(p.path("hello.h"), "#pragma once\n")
        rc, out = p.run("local")
        self.assertEqual(rc, 0, out)
        r = subprocess.run(["conan", "list", "hello/*"], capture_output=True, text=True, env=p.env)
        self.assertIn("hello/1.2.0", r.stdout)
        # another project requires it: Conan finds it in its local cache, no remote (chapter 5)
        app = Project(self)
        app.env = p.env
        put(app.path("conanfile.txt"), "[requires]\nhello/1.2.0\n")
        r = subprocess.run(["conan", "install", ".", "--no-remote", "--build=never"], cwd=app.dir,
                           capture_output=True, text=True, env=app.env)
        self.assertEqual(r.returncode, 0, r.stdout[-2000:] + r.stderr[-2000:])

    def test_custom_local(self):
        p = Project(self, REGISTRY_KIND="custom", PUBLISH_PACKAGE="yes", LOCAL_COMMAND="'touch \"$HOME/installed\"'")
        self.assertEqual(p.run("local")[0], 0)
        self.assertTrue(os.path.exists(os.path.join(p.home, "installed")))
        q = Project(self, REGISTRY_KIND="custom", PUBLISH_PACKAGE="yes", REGISTRY_URL="https://r.example/")
        self.assertEqual(q.run("publish", REGISTRY_PUBLISH_TOKEN=TOKEN)[0], 1)   # empty PUBLISH_COMMAND


POM = """<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>team</groupId><artifactId>lib</artifactId><version>1.2.0</version><packaging>pom</packaging>
  {dist}
</project>
"""
CONSUMER_POM = """<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>team</groupId><artifactId>app</artifactId><version>0.0.0</version><packaging>pom</packaging>
  <dependencies><dependency><groupId>team</groupId><artifactId>lib</artifactId><version>1.2.0</version>
    <type>pom</type></dependency></dependencies>
</project>
"""
PYPROJECT = ('[project]\nname = "team-lib"\nversion = "1.2.0"\n\n'
             '[build-system]\nrequires = ["setuptools>=61"]\nbuild-backend = "setuptools.build_meta"\n')
GRADLE_LIB = """plugins {{ id 'java-library'; id 'maven-publish' }}
group = 'team'
version = '1.2.0'
repositories {{ mavenCentral() }}
publishing {{
  publications {{ lib(MavenPublication) {{ from components.java }} }}
  {repo}
}}
"""
CONANFILE = """from conan import ConanFile
from conan.tools.files import copy


class Hello(ConanFile):
    name = "hello"
    exports_sources = "hello.h"

    def set_version(self):
        self.version = "1.2.0"

    def package(self):
        copy(self, "hello.h", self.source_folder, self.package_folder)
"""


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait(url, ok=(200, 401, 404), seconds=90):
    end = time.time() + seconds
    while time.time() < end:
        try:
            urllib.request.urlopen(url, timeout=3)
            return
        except urllib.error.HTTPError as e:
            e.close()
            if e.code in ok:
                return
        except OSError:
            pass
        time.sleep(1)
    raise RuntimeError(f"{url} did not start")


def docker_ok():
    return shutil.which("docker") and subprocess.run(["docker", "info"], capture_output=True).returncode == 0


LIVE = os.environ.get("REGISTRY_LIVE", "1") != "0" and docker_ok()


class Container:
    def __init__(self, test, image, port, *args, env=()):
        self.port = free_port()
        cmd = ["docker", "run", "-d", "--rm", "-p", f"127.0.0.1:{self.port}:{port}"]
        for e in env:
            cmd += ["-e", e]
        self.id = subprocess.run(cmd + [image, *args], capture_output=True, text=True, check=True).stdout.strip()
        test.addClassCleanup(subprocess.run, ["docker", "rm", "-f", self.id], capture_output=True)
        self.url = f"http://127.0.0.1:{self.port}"


@unittest.skipUnless(LIVE, "Docker not available (or REGISTRY_LIVE=0)")
class Live(unittest.TestCase):
    """A real upload with the publish token, and a read back with the read token."""

    @unittest.skipUnless(shutil.which("npm"), "npm not installed")
    def test_npm(self):
        c = Container(Live, "verdaccio/verdaccio:6", 4873)
        wait(c.url + "/-/ping")
        req = urllib.request.Request(c.url + "/-/user/org.couchdb.user:ci", method="PUT",
                                     data=json.dumps({"name": "ci", "password": "ci-pass-123"}).encode(),
                                     headers={"content-type": "application/json"})
        token = json.load(urllib.request.urlopen(req))["token"]
        name = f"@atest/lib-{os.getpid()}"                       # Verdaccio proxies npmjs: a name only it has
        p = Project(self, REGISTRY_KIND="npm", REGISTRY_URL=c.url + "/", REGISTRY_SCOPE="@atest", PUBLISH_PACKAGE="yes")
        put(p.path("package.json"), json.dumps({"name": name, "version": "1.2.0"}))
        rc, out = p.run("publish", REGISTRY_PUBLISH_TOKEN=token)
        self.assertEqual(rc, 0, out)
        self.assertNotIn(token, out)
        r = subprocess.run(["npm", "view", name, "version"],
                           capture_output=True, text=True, env=p.env)
        self.assertEqual(r.stdout.strip(), "1.2.0", r.stderr)

    @unittest.skipUnless(venv_works(), "python3 -m venv does not work here (python3-venv)")
    def test_pypi(self):
        c = Container(Live, "pypiserver/pypiserver:v2.3.2", 8080, "run", "-a", ".", "-P", ".", "/data/packages")
        wait(c.url + "/simple/")
        p = Project(self, REGISTRY_KIND="pypi", REGISTRY_URL=c.url + "/simple/", REGISTRY_UPLOAD_URL=c.url + "/",
                    PUBLISH_PACKAGE="yes")
        put(p.path("pyproject.toml"), PYPROJECT)
        put(p.path("src", "team_lib", "__init__.py"), "")
        rc, out = p.run("publish", REGISTRY_PUBLISH_TOKEN="w")
        self.assertEqual(rc, 0, out)
        self.assertEqual(p.run("login", REGISTRY_TOKEN="r")[0], 0)
        r = subprocess.run(["python3", "-m", "pip", "download", "--no-deps", "-d", p.path("dl"), "team-lib==1.2.0"],
                           capture_output=True, text=True, env=p.env)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])

    def reposilite(self):
        c = Container(Live, "dzikoysk/reposilite:3.5.26", 8080, env=["REPOSILITE_OPTS=--token ci:ci-secret"])
        wait(c.url + "/api/status/instance")
        return c

    def read_back(self, c, path):
        req = urllib.request.Request(c.url + "/releases/" + path)
        req.add_header("Authorization", "Basic Y2k6Y2ktc2VjcmV0")      # ci:ci-secret
        return urllib.request.urlopen(req).status

    @unittest.skipUnless(shutil.which("mvn"), "maven not installed")
    def test_maven(self):
        c = self.reposilite()
        p = Project(self, REGISTRY_KIND="maven", REGISTRY_URL=c.url + "/releases", REGISTRY_USER="ci",
                    PUBLISH_PACKAGE="yes")
        put(p.path("pom.xml"), POM.format(dist="<distributionManagement><repository><id>team</id>"
                                          f"<url>{c.url}/releases</url></repository></distributionManagement>"))
        rc, out = p.run("publish", REGISTRY_PUBLISH_TOKEN="ci-secret")
        self.assertEqual(rc, 0, out[-3000:])
        self.assertEqual(self.read_back(c, "team/lib/1.2.0/lib-1.2.0.pom"), 200)

    @unittest.skipUnless(shutil.which("gradle"), "gradle not installed")
    def test_gradle(self):
        c = self.reposilite()
        p = Project(self, REGISTRY_KIND="gradle", REGISTRY_URL=c.url + "/releases", REGISTRY_USER="ci",
                    PUBLISH_PACKAGE="yes")
        put(p.path("settings.gradle"), 'rootProject.name = "lib"\n')
        put(p.path("build.gradle"), GRADLE_LIB.format(
            repo=f"repositories {{ maven {{ name = 'team'; url = '{c.url}/releases'; allowInsecureProtocol = true\n"
                 "    credentials(PasswordCredentials) } }"))
        rc, out = p.run("publish", REGISTRY_PUBLISH_TOKEN="ci-secret")
        self.assertEqual(rc, 0, out[-3000:])
        self.assertEqual(self.read_back(c, "team/lib/1.2.0/lib-1.2.0.pom"), 200)

    @unittest.skipUnless(shutil.which("conan") and shutil.which("conan_server"), "conan or conan_server not installed")
    def test_conan(self):
        port = free_port()
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home, True)
        put(os.path.join(home, "server.conf"), f"""[server]
jwt_secret: test-secret
jwt_expire_minutes: 120
ssl_enabled: False
port: {port}
host_name: 127.0.0.1
disk_storage_path: ./data
updown_secret: test-updown
[write_permissions]
*/*@*/*: ci
[read_permissions]
*/*@*/*: *
[users]
ci: ci-secret
""")
        srv = subprocess.Popen(["conan_server"], env=dict(os.environ, CONAN_SERVER_HOME=home, HOME=home),
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(srv.wait)
        self.addCleanup(srv.terminate)
        wait(f"http://127.0.0.1:{port}/v2/ping")
        p = Project(self, REGISTRY_KIND="conan", REGISTRY_URL=f"http://127.0.0.1:{port}", REGISTRY_USER="ci",
                    PUBLISH_PACKAGE="yes")
        put(p.path("conanfile.py"), CONANFILE)
        put(p.path("hello.h"), "#pragma once\n")
        rc, out = p.run("publish", REGISTRY_PUBLISH_TOKEN="ci-secret")
        self.assertEqual(rc, 0, out[-3000:])
        self.assertNotIn("ci-secret", out)
        r = subprocess.run(["conan", "list", "hello/*", "-r", "team"], capture_output=True, text=True, env=p.env)
        self.assertIn("hello/1.2.0", r.stdout, r.stderr)


if __name__ == "__main__":
    unittest.main()
