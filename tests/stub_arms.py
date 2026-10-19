# SPDX-License-Identifier: Apache-2.0
"""A directory of stub arms for end-to-end tests: Pi-shaped command lines, a tiny Python program as the "harness" that makes one chat-completions request to the mock, and a manifest that installs it
from a file:// URL with its real sha256. No network, no pinned release: the whole of `buffon up` (install, run, report, site) runs against them."""
import hashlib
import json
import os
import stat
import textwrap

from buffon.arms import manifest

SCRIPT = textwrap.dedent('''\
    #!/usr/bin/env python3
    import http.client, json, os, sys, time, urllib.parse
    if "--version" in sys.argv:
        print("stub 1.0")
        sys.exit(0)
    time.sleep(%(delay)s)
    prompt = sys.argv[sys.argv.index("-p") + 1] if "-p" in sys.argv else "hi"
    cfg = json.load(open(os.path.join(os.environ["PI_CODING_AGENT_DIR"], "models.json")))["providers"]["bench"]
    u = urllib.parse.urlparse(cfg["baseUrl"])
    c = http.client.HTTPConnection(u.hostname, u.port)
    for _ in range(%(side)s):   # side requests a real harness adds: a title for the session, with no tools
        c.request("POST", u.path.rstrip("/") + "/chat/completions", json.dumps({"model": "bench-1", "stream": False, "messages": [{"role": "user", "content": "Title this session: " + prompt}]}),
                  {"Content-Type": "application/json", "Authorization": "Bearer x"})
        c.getresponse().read()
    c.request("POST", u.path.rstrip("/") + "/chat/completions", json.dumps({"model": "bench-1", "stream": False, "messages": [{"role": "user", "content": prompt}],
                                                                                      "tools": [{"type": "function", "function": {"name": "read", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}}}}]}),
              {"Content-Type": "application/json", "Authorization": "Bearer x"})
    reply = json.loads(c.getresponse().read())
    print(reply["choices"][0]["message"]["content"])
''')

TOML = textwrap.dedent('''\
    name = "%(name)s"
    label = "Stub %(name)s"
    homepage = "https://example.invalid/%(name)s"
    relation = "pi-compatible"
    licence = "MIT"
    licence_url = "https://example.invalid/LICENSE"
    restrictions = ""
    version = "1.0"
    notes = "a stub harness for tests"

    [artifact.%(platform)s]
    url = "file://%(path)s"
    sha256 = "%(sha)s"
    checksums = "file://%(path)s"
    exe = "%(name)s"

    [endpoint]
    apis = ["openai-completions"]
    writer = "writer.py"

    [env]
    PI_CODING_AGENT_DIR = "{agent_dir}"

    [state]
    dirs = ["$HOME/.agent", "$XDG_CONFIG_HOME", "$XDG_DATA_HOME", "$XDG_CACHE_HOME", "$XDG_STATE_HOME"]

    [modes]
    version = ["--version"]
    print = ["--provider", "bench", "--model", "{model}", "--no-session", "{extensions}", "-p", "{prompt}"]

    [capabilities]
    pi_extensions = "none"
    pi_session_format = false
    exact_requests = %(exact)s
''')


def make(root, delays=(("stub-fast", 0.0), ("stub-slow", 0.03)), side=None):
    """Write the stub arms under root/arms and their programs under root/files; returns the arms directory. `side` maps an arm name to the number of extra (title) requests it sends
    before the scripted one; such an arm does not declare exact_requests."""
    side = side or {}
    arms, files = os.path.join(root, "arms"), os.path.join(root, "files")
    os.makedirs(files, exist_ok=True)
    for name, delay in delays:
        script = os.path.join(files, name)
        with open(script, "w") as f:
            f.write(SCRIPT % {"delay": delay, "side": side.get(name, 0)})
        os.chmod(script, os.stat(script).st_mode | stat.S_IXUSR)
        with open(script, "rb") as f:
            sha = hashlib.sha256(f.read()).hexdigest()
        d = os.path.join(arms, name)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "arm.toml"), "w") as f:
            f.write(TOML % {"name": name, "platform": manifest.host_platform(), "path": script, "sha": sha, "exact": "false" if side.get(name) else "true"})
        with open(os.path.join(d, "writer.py"), "w") as f:
            f.write("from buffon.arms.writers.pi import write  # noqa: F401\n")
    return arms
