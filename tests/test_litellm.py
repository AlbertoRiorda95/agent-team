#!/usr/bin/env python3
"""The LiteLLM gateway of infra/litellm/ as chapter 7 runs it on a PC
(docker-compose.yml + docker-compose.local.yml, LiteLLM and Postgres), with
one more model that points to the scripted model (tests/mockllm.py) instead
of a provider: create-key.sh makes a role's key, a call with that key goes
through, a model outside the key is refused, key-spend.sh reads the spend,
and OpenCode's litellm provider (opencode.json) reaches the gateway.

Needs Docker and port 4000 free; skipped otherwise (or with LITELLM_LIVE=0).
Run: python3 tests/test_litellm.py
"""
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEMPLATE = os.path.join(ROOT, "template")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mockllm  # noqa: E402

IMAGE = "ghcr.io/berriai/litellm:v1.82.0-stable"
MASTER = "sk-master-test-0123456789"
URL = "http://127.0.0.1:4000"


def docker_ok():
    return shutil.which("docker") and subprocess.run(["docker", "compose", "version"], capture_output=True).returncode == 0


def port_free(port):
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


LIVE = os.environ.get("LITELLM_LIVE", "1") != "0" and docker_ok() and port_free(4000)


def call(path, key, body=None):
    req = urllib.request.Request(URL + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, {}


@unittest.skipUnless(LIVE, "Docker compose not available, port 4000 busy, or LITELLM_LIVE=0")
class Gateway(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mock = mockllm.Server(host="0.0.0.0")
        cls.tmp = tempfile.mkdtemp()
        cls.dir = os.path.join(cls.tmp, "litellm")
        shutil.copytree(os.path.join(TEMPLATE, "infra", "litellm"), cls.dir)
        with open(os.path.join(cls.dir, "litellm-config.yaml"), "a") as f:
            f.write(f"""  - model_name: mock
    litellm_params:
      model: openai/mock-model
      api_base: http://host.docker.internal:{cls.mock.port}/v1
      api_key: mock
""")
        env = open(os.path.join(cls.dir, ".env.example")).read()
        env = env.replace("PG_PASSWORD=", "PG_PASSWORD=pg-test").replace("LITELLM_MASTER_KEY=", f"LITELLM_MASTER_KEY={MASTER}")
        with open(os.path.join(cls.dir, ".env"), "w") as f:
            f.write(env)
        # the image of the test; the host, for the scripted model
        with open(os.path.join(cls.dir, "docker-compose.test.yml"), "w") as f:
            f.write(f'services:\n  litellm:\n    image: {IMAGE}\n    extra_hosts: ["host.docker.internal:host-gateway"]\n')
        cls.compose = ["docker", "compose", "-p", f"agentteam-litellm-{os.getpid()}", "-f", "docker-compose.yml",
                       "-f", "docker-compose.local.yml", "-f", "docker-compose.test.yml"]
        r = subprocess.run(cls.compose + ["up", "-d", "litellm", "db"], cwd=cls.dir, capture_output=True, text=True,
                           timeout=900)
        if r.returncode != 0:
            cls.tearDownClass()
            raise RuntimeError(r.stdout + r.stderr)
        end = time.time() + 300
        while time.time() < end:
            try:
                if call("/health/liveliness", MASTER)[0] == 200 and call("/key/list", MASTER)[0] == 200:
                    break
            except OSError:
                pass
            time.sleep(3)
        else:
            logs = subprocess.run(cls.compose + ["logs", "--tail", "60", "litellm"], cwd=cls.dir, capture_output=True,
                                  text=True).stdout
            cls.tearDownClass()
            raise RuntimeError("LiteLLM did not start:\n" + logs)
        cls.env = dict(os.environ, LITELLM_URL=URL, LITELLM_MASTER_KEY=MASTER)
        r = subprocess.run(["bash", "create-key.sh", "optimizer", "mock", "30"], cwd=cls.dir, capture_output=True,
                           text=True, env=cls.env)
        assert r.returncode == 0, r.stderr
        cls.key = json.loads(r.stdout)["key"]

    @classmethod
    def tearDownClass(cls):
        subprocess.run(cls.compose + ["down", "-v"], cwd=cls.dir, capture_output=True)
        cls.mock.close()
        shutil.rmtree(cls.tmp, True)

    def test_role_key_reaches_its_model(self):
        before = len(self.mock.requests)
        code, out = call("/v1/chat/completions", self.key, {"model": "mock", "messages": [{"role": "user", "content": "hi"}]})
        self.assertEqual(code, 200, out)
        self.assertEqual(out["choices"][0]["message"]["content"], "done")
        self.assertEqual(len(self.mock.requests), before + 1)

    def test_role_key_cannot_use_other_models(self):
        code, _ = call("/v1/chat/completions", self.key, {"model": "gpt", "messages": [{"role": "user", "content": "hi"}]})
        self.assertIn(code, (401, 403))

    def test_key_spend(self):
        call("/v1/chat/completions", self.key, {"model": "mock", "messages": [{"role": "user", "content": "hi"}]})
        r = subprocess.run(["bash", "key-spend.sh", self.key], cwd=self.dir, capture_output=True, text=True, env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stdout, r"^optimizer\t\$[0-9.e-]+$")

    @unittest.skipUnless(shutil.which(os.environ.get("OPENCODE_BIN") or "opencode"), "opencode not installed")
    def test_opencode_through_the_gateway(self):
        """opencode.json's litellm provider, its address and the role's key changed as chapter 7 says."""
        sys.path.insert(0, os.path.join(TEMPLATE, "scripts"))
        from agentteam import profile
        proj = os.path.join(self.tmp, "proj")
        home = os.path.join(self.tmp, "home")
        profile.render_tree(TEMPLATE, proj, {"harnesses": ["opencode"], "ci": "none", "tracker": "local",
                                             "features": ["litellm"]})
        cfg_path = os.path.join(proj, "opencode.json")
        with open(cfg_path) as f:
            cfg = json.load(f)
        lite = cfg["provider"]["litellm"]
        lite["options"]["baseURL"] = URL + "/v1"
        lite["options"]["apiKey"] = "{env:LITELLM_API_KEY}"
        lite["models"]["mock"] = {"name": "Mock via LiteLLM"}
        with open(cfg_path, "w") as f:
            json.dump(cfg, f)
        subprocess.run(["git", "init", "-q"], cwd=proj, check=True)
        env = {k: v for k, v in os.environ.items() if not k.startswith(("OPENCODE", "OPENAI"))}
        env.update(HOME=home, PWD=proj, LITELLM_API_KEY=self.key, XDG_CONFIG_HOME=f"{home}/.config",
                   XDG_DATA_HOME=f"{home}/.local/share", XDG_CACHE_HOME=f"{home}/.cache", XDG_STATE_HOME=f"{home}/.local/state")
        before = len(self.mock.requests)
        r = subprocess.run([os.environ.get("OPENCODE_BIN") or "opencode", "run", "--agent", "optimizer",
                            "-m", "litellm/mock", "say hi"], cwd=proj, env=env, capture_output=True, text=True,
                           timeout=240, stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 0, r.stdout[-2000:] + r.stderr[-2000:])
        self.assertIn("done", r.stdout)
        through = [q for q in self.mock.requests[before:] if q["body"].get("model") == "mock-model"]
        self.assertTrue(through, "no request reached the model through the gateway")
        self.assertTrue(any("docs/roles/optimizer.md" in json.dumps(q["body"]) for q in through))


if __name__ == "__main__":
    unittest.main()
