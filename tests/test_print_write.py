# SPDX-License-Identifier: Apache-2.0
"""overhead/print-write against a fake harness: a small Python program that makes the streamed `write` call's two requests the way a harness does."""
import os
import pathlib
import sys
import tempfile
import textwrap
import unittest

from buffon import mock, workloads
from buffon.workloads import overhead

FAKE = textwrap.dedent('''\
    import http.client, json, os, sys, urllib.parse
    mode = os.environ["FAKE_MODE"]
    u = urllib.parse.urlparse(os.environ["FAKE_URL"])
    tools = [{"type": "function", "function": {"name": "write", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}}}}]
    if mode == "no-write-tool":
        tools = [{"type": "function", "function": {"name": "apply_patch", "parameters": {"type": "object", "properties": {"input": {"type": "string"}}}}}]

    def ask(messages):
        c = http.client.HTTPConnection(u.hostname, u.port)
        c.request("POST", "/v1/chat/completions", json.dumps({"model": "bench-1", "stream": True, "messages": messages, "tools": tools}), {"Content-Type": "application/json"})
        data = c.getresponse().read().decode()
        events = [json.loads(b[6:]) for b in data.split("\\n\\n") if b.startswith("data: {")]
        text, args = "", ""
        for e in events:
            for ch in e["choices"]:
                text += ch["delta"].get("content") or ""
                for call in ch["delta"].get("tool_calls", []):
                    args += call.get("function", {}).get("arguments", "")
        return text, args

    messages = [{"role": "user", "content": sys.argv[-1]}]
    text, args = ask(messages)
    if args:
        call = json.loads(args)
        body = call["content"]
        if mode == "short":
            body = body[:-1]
        elif mode == "flip":
            body = body[:100] + ("Z" if body[100] != "Z" else "Y") + body[101:]
        if mode != "missing":
            os.makedirs(os.path.dirname(call["path"]), exist_ok=True)
            with open(call["path"], "wb") as f:
                f.write(body.encode())
        messages += [{"role": "assistant", "content": None, "tool_calls": [{"id": "c", "type": "function", "function": {"name": "write", "arguments": args}}]}, {"role": "tool", "tool_call_id": "c", "content": "ok"}]
        text, _ = ask(messages)
    print(text)
''')


class FakeHarness:
    def __init__(self, work, server, mode):
        self.cwd = tempfile.mkdtemp(dir=work)
        self.env = dict(os.environ, FAKE_MODE=mode, FAKE_URL=f"http://127.0.0.1:{server.port}")
        self.script = os.path.join(work, "fake.py")
        with open(self.script, "w") as f:
            f.write(FAKE)

    def print_argv(self, prompt):
        return [sys.executable, self.script, prompt]


class FakeArm:
    id = "fake"
    capabilities = {"exact_requests": True}
    cannot_run = {}

    def __init__(self, mode):
        self.mode = mode

    def supports_mode(self, mode):
        return mode == "print"

    def supports_api(self, api):
        return True


class FakeCtx:
    def __init__(self, work, server, mode, **params):
        self.work, self.server, self.mode = work, server, mode
        self.opts = type("O", (), {"timeout": 60, "api": "openai-completions", "params": params})()

    def harness(self, arm, scenario, **kwargs):
        return FakeHarness(self.work, self.server, self.mode)

    def main_requests(self, arm):
        return overhead.Ctx.main_requests(self, arm)


class PrintWrite(unittest.TestCase):
    def run_one(self, mode, **params):
        with tempfile.TemporaryDirectory() as work, mock.MockServer(policy=mock.scripted_policy([mock.Step(text="x")])) as srv:
            return overhead.one_write(FakeCtx(work, srv, mode, **params), FakeArm(mode))

    def test_it_is_registered_as_an_overhead_workload(self):
        w = workloads.load_all()["overhead/print-write"]
        self.assertEqual(w.family, "overhead")
        self.assertIn("openai-responses", w.apis)

    def test_a_correct_write_gives_both_sizes_with_their_metrics(self):
        sample = self.run_one("good", write_kb="1,2")
        self.assertNotIn("failure", sample)
        for label in ("kb1", "kb2"):
            for key in ("wall_ms", "cpu_ms", "peak_mem_mib", "peak_rss_mib", "bytes_out", "call_to_result_ms", "after_stream_ms"):
                self.assertIn(f"{label}_{key}", sample)
            self.assertGreater(sample[f"{label}_wall_ms"], 0)
            self.assertGreaterEqual(sample[f"{label}_call_to_result_ms"], sample[f"{label}_after_stream_ms"])
        self.assertEqual(sample["write_chunk"], 16)

    def test_the_default_sizes_are_50_and_200_kb(self):
        ctx = FakeCtx("/nonexistent", None, "good")
        self.assertEqual(overhead.write_sizes(ctx), (("kb50", 50), ("kb200", 200)))
        self.assertEqual(overhead.write_sizes(FakeCtx("/nonexistent", None, "good", write_kb=100)), (("kb100", 100),))

    def test_a_file_one_byte_short_fails_the_sample_with_the_reason(self):
        sample = self.run_one("short", write_kb=1)
        self.assertEqual(list(sample), ["failure"])
        self.assertIn("kb1: the file holds 1023 bytes, expected 1024", sample["failure"])

    def test_a_file_with_one_changed_byte_fails_at_its_offset(self):
        sample = self.run_one("flip", write_kb=1)
        self.assertEqual(sample, {"failure": "kb1: the file differs from the expected bytes at offset 100"})

    def test_no_file_fails_the_sample(self):
        sample = self.run_one("missing", write_kb=1)
        self.assertIn("the file was not written", sample["failure"])

    def test_a_harness_with_no_write_tool_is_skipped_with_the_tools_it_declared(self):
        with self.assertRaises(overhead.Skip) as why:
            self.run_one("no-write-tool", write_kb=1)
        self.assertIn("declared no write tool (it declared apply_patch)", str(why.exception))

    def test_a_manifest_reason_skips_before_anything_runs(self):
        arm = FakeArm("good")
        arm.cannot_run = {"print-write": "its write tool refuses files over 100 KB"}
        with self.assertRaises(overhead.Skip) as why:
            overhead.one_write(FakeCtx("/nonexistent", None, "good"), arm)
        self.assertEqual(str(why.exception), "its write tool refuses files over 100 KB")

    def test_wrong_file_reports_missing_short_and_changed_files(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "f")
            self.assertIn("not written", overhead.wrong_file(path, b"abc"))
            pathlib.Path(path).write_bytes(b"abd")
            self.assertEqual(overhead.wrong_file(path, b"abc"), "the file differs from the expected bytes at offset 2")
            pathlib.Path(path).write_bytes(b"abc")
            self.assertIsNone(overhead.wrong_file(path, b"abc"))


if __name__ == "__main__":
    unittest.main()
