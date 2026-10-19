# SPDX-License-Identifier: Apache-2.0
"""The mock speaks both wire APIs Buffon requires (OpenAI Chat Completions and Anthropic Messages) plus OpenAI Responses, deterministically."""
import http.client
import json
import os
import unittest

from buffon import mock
from buffon.mock import shapes

CHAT = {"model": "bench-1", "stream": True, "messages": [{"role": "user", "content": "hi"}]}
ANTH = {"model": "bench-1", "stream": True, "max_tokens": 64, "messages": [{"role": "user", "content": "hi"}]}
RESP = {"model": "bench-1", "stream": True, "input": [{"role": "user", "content": "hi"}]}
PATHS = {"openai-completions": ("/v1/chat/completions", CHAT), "anthropic-messages": ("/v1/messages", ANTH), "openai-responses": ("/v1/responses", RESP)}


def call(server, path, body, method="POST"):
    conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
    conn.request(method, path, json.dumps(body) if body is not None else None, {"Content-Type": "application/json"})
    resp = conn.getresponse()
    try:
        data = resp.read()
    except http.client.IncompleteRead as cut:  # a stream the mock closes without its terminating chunk (keepalive fault)
        data = cut.partial
    conn.close()
    return resp, data


def sse(data):
    """[(event name or None, parsed data)] from a raw SSE body."""
    out = []
    for block in data.decode().split("\n\n"):
        name, payload = None, None
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: "):
                payload = line[6:]
        if payload is not None:
            out.append((name, payload if payload == "[DONE]" else json.loads(payload)))
    return out


def stream(api, steps, request_count=1):
    path, body = PATHS[api]
    with mock.MockServer(policy=mock.scripted_policy(steps)) as srv:
        results = [call(srv, path, body) for _ in range(request_count)]
    return results


def text_of(api, events):
    if api == "openai-completions":
        return "".join(d["choices"][0]["delta"].get("content", "") for _, d in events if d != "[DONE]" and d["choices"])
    if api == "anthropic-messages":
        return "".join(d["delta"]["text"] for n, d in events if n == "content_block_delta" and d["delta"]["type"] == "text_delta")
    return "".join(d["delta"] for n, d in events if n == "response.output_text.delta")


class BothApis(unittest.TestCase):
    def test_the_same_scripted_text_streams_identically_through_every_wire_api(self):
        for api in PATHS:
            (resp, data), = stream(api, [mock.Step(text="alpha beta gamma")])
            self.assertEqual(resp.status, 200, api)
            self.assertEqual(resp.getheader("Content-Type"), "text/event-stream")
            self.assertEqual(text_of(api, sse(data)), "alpha beta gamma", api)

    def test_replies_are_byte_identical_across_servers_and_runs(self):
        for api in PATHS:
            a = stream(api, [mock.Step(text="one two three"), mock.Step(text="four five")], request_count=2)
            b = stream(api, [mock.Step(text="one two three"), mock.Step(text="four five")], request_count=2)
            self.assertEqual([d for _, d in a], [d for _, d in b], api)
            self.assertNotEqual(a[0][1], a[1][1])

    def test_chat_completions_golden_bytes(self):
        (resp, data), = stream("openai-completions", [mock.Step(text="a b")])
        lines = data.decode().split("\n\n")
        first = json.loads(lines[0][6:])
        self.assertEqual(first["choices"][0]["delta"], {"content": "a ", "role": "assistant"})
        self.assertEqual(lines[-2], "data: [DONE]")
        last = json.loads(lines[-3][6:])
        self.assertEqual(last["usage"], {"prompt_tokens": last["usage"]["prompt_tokens"], "completion_tokens": 2, "total_tokens": last["usage"]["prompt_tokens"] + 2})
        self.assertEqual(json.loads(lines[-4][6:])["choices"][0]["finish_reason"], "stop")

    def test_anthropic_event_order_and_usage(self):
        (resp, data), = stream("anthropic-messages", [mock.Step(text="a b c")])
        events = sse(data)
        names = [n for n, _ in events]
        self.assertEqual(names[:2], ["message_start", "content_block_start"])
        self.assertEqual(names[-3:], ["content_block_stop", "message_delta", "message_stop"])
        self.assertEqual(events[-2][1]["delta"]["stop_reason"], "end_turn")
        self.assertEqual(events[-2][1]["usage"]["output_tokens"], 3)
        self.assertGreater(events[0][1]["message"]["usage"]["input_tokens"], 0)

    def test_responses_event_sequence_ends_completed(self):
        (resp, data), = stream("openai-responses", [mock.Step(text="x y")])
        names = [n for n, _ in sse(data)]
        self.assertEqual(names[0], "response.created")
        self.assertEqual(names[-1], "response.completed")
        self.assertIn("response.output_text.done", names)

    def test_tool_calls_stream_as_partial_json_on_every_api(self):
        step = mock.Step(tool_calls=[("read", {"path": "/p/README.md"})])
        (_, chat), = stream("openai-completions", [step])
        args = "".join(c["function"].get("arguments", "") for _, d in sse(chat) if d != "[DONE]" for ch in d["choices"] for c in ch["delta"].get("tool_calls", []))
        self.assertEqual(json.loads(args), {"path": "/p/README.md"})
        (_, anth), = stream("anthropic-messages", [step])
        partial = "".join(d["delta"]["partial_json"] for n, d in sse(anth) if n == "content_block_delta" and d["delta"]["type"] == "input_json_delta")
        self.assertEqual(json.loads(partial), {"path": "/p/README.md"})
        self.assertEqual([d for n, d in sse(anth) if n == "message_delta"][0]["delta"]["stop_reason"], "tool_use")

    def test_usage_reports_the_request_size_honestly(self):
        path, body = PATHS["openai-completions"]
        raw_len = len(json.dumps(body))
        (_, data), = stream("openai-completions", [mock.Step(text="x")])
        usage = sse(data)[-2][1]["usage"]
        self.assertEqual(usage["prompt_tokens"], raw_len // 4)

    def test_chunk_chars_streams_fixed_size_chunks_including_markdown_whitespace(self):
        text = shapes.body("tables", 100)
        (_, data), = stream("openai-completions", [mock.Step(text=text, chunk_chars=24)])
        chunks = [d["choices"][0]["delta"]["content"] for _, d in sse(data) if d != "[DONE]" and d["choices"] and d["choices"][0]["delta"].get("content")]
        self.assertEqual([len(c) for c in chunks], [24, 24, 24, 24, 4])
        self.assertEqual("".join(chunks), text)

    def test_count_tokens_and_models(self):
        with mock.MockServer() as srv:
            resp, data = call(srv, "/v1/messages/count_tokens", {"model": "bench-1", "messages": [{"role": "user", "content": "hello"}]})
            self.assertEqual(resp.status, 200)
            self.assertGreater(json.loads(data)["input_tokens"], 0)
            resp, data = call(srv, "/v1/models", None, "GET")
            self.assertEqual(json.loads(data)["data"][0]["id"], "bench-1")
            resp, _ = call(srv, "/v1/unknown", {})
            self.assertEqual(resp.status, 404)

    def test_the_mock_records_every_request_with_timing_and_the_credential(self):
        with mock.MockServer(policy=mock.scripted_policy([mock.Step(text="x")])) as srv:
            conn = http.client.HTTPConnection("127.0.0.1", srv.port, timeout=10)
            conn.request("POST", "/v1/messages", json.dumps(ANTH), {"x-api-key": "dummy"})
            conn.getresponse().read()
            conn.close()
            r = srv.requests[0]
        self.assertEqual((r.protocol, r.auth, r.fault), ("anthropic-messages", "dummy", None))
        self.assertLessEqual(r.t_recv, r.t_start)
        self.assertLessEqual(r.t_start, r.t_end)


class Faults(unittest.TestCase):
    def test_a_keepalive_only_stream_carries_comments_and_no_events(self):
        for api in ("openai-completions", "anthropic-messages"):
            path, body = PATHS[api]
            with mock.MockServer(faults={0: mock.Fault(keepalives=3, keepalive_ms=1)}) as srv:
                resp, data = call(srv, path, body)
            self.assertEqual(resp.status, 200)
            self.assertEqual(data.count(b": keepalive"), 3, api)
            self.assertNotIn(b"data:", data)

    def test_every_status_fault_has_the_apis_error_shape(self):
        for api, key in (("openai-completions", "error"), ("anthropic-messages", "type")):
            path, body = PATHS[api]
            with mock.MockServer(faults={0: mock.Fault(status=500)}) as srv:
                resp, data = call(srv, path, body)
            self.assertEqual(resp.status, 500)
            self.assertIn(key, json.loads(data))


class Transcripts(unittest.TestCase):
    DATA = {"name": "t", "steps": [{"text": "first reply"}, {"tool_calls": [["read", {"path": "{cwd}/README.md"}]]}, {"shape": "lists", "chars": 120, "chunk_chars": 10}]}

    def test_step_i_answers_request_i_and_the_last_step_repeats(self):
        t = mock.Transcript(self.DATA, cwd="/w")
        policy = t.policy()
        req = lambda i: mock.Request(i, "openai-completions", {"messages": []}, 1, 0)  # noqa: E731
        self.assertEqual(policy(req(0)).text, "first reply")
        self.assertEqual(policy(req(1)).tool_calls, [("read", {"path": "/w/README.md"})])
        self.assertEqual(len(policy(req(2)).text), 120)
        self.assertEqual(policy(req(99)).text, policy(req(2)).text)

    def test_a_transcript_replays_to_identical_bytes_on_each_api(self):
        for api in ("openai-completions", "anthropic-messages"):
            path, body = PATHS[api]
            runs = []
            for _ in range(2):
                with mock.MockServer(policy=mock.Transcript(self.DATA, cwd="/w").policy()) as srv:
                    runs.append([call(srv, path, body)[1] for _ in range(3)])
            self.assertEqual(runs[0], runs[1], api)

    def test_shapes_have_exact_length_and_are_deterministic(self):
        for name in shapes.SHAPES:
            for size in (1, 100, 6000):
                text = shapes.body(name, size)
                self.assertEqual(len(text), size)
                self.assertEqual(text, shapes.body(name, size))
        self.assertIn("```", shapes.body("code", 300))
        self.assertIn("|---|", shapes.body("tables", 300))
        self.assertIn("\n- ", shapes.body("lists", 300))

    def test_malformed_transcripts_are_errors(self):
        for data in ({"steps": []}, {"steps": [{"bogus": 1}]}, {"steps": [{}]}, {"steps": [{"shape": "nope", "chars": 5}]}, {"steps": [{"shape": "prose"}]}, {"name": "x", "steps": [{"text": "a"}], "extra": 1}):
            with self.assertRaises(mock.TranscriptError, msg=data):
                mock.Transcript(data)


if __name__ == "__main__":
    unittest.main()


class ReviewGuards(unittest.TestCase):
    """Mutants of the mock that the tests above let through (review of milestone 3)."""

    STEP = mock.Step(tool_calls=[("read", {"path": "/p/README.md"})])

    def test_tool_call_arguments_arrive_in_more_than_one_delta_on_every_api(self):
        # A harness that only handles whole-argument deltas must not pass: the arguments are cut in two.
        (_, chat), = stream("openai-completions", [self.STEP])
        pieces = [c["function"]["arguments"] for _, d in sse(chat) if d != "[DONE]" for ch in d["choices"] for c in ch["delta"].get("tool_calls", [])
                  if c.get("function", {}).get("arguments")]
        (_, anth), = stream("anthropic-messages", [self.STEP])
        partial = [d["delta"]["partial_json"] for n, d in sse(anth) if n == "content_block_delta" and d["delta"]["type"] == "input_json_delta"]
        (_, resp), = stream("openai-responses", [self.STEP])
        deltas = [d["delta"] for n, d in sse(resp) if n == "response.function_call_arguments.delta"]
        for api, parts in (("chat", pieces), ("anthropic", partial), ("responses", deltas)):
            self.assertGreaterEqual(len(parts), 2, api)
            self.assertTrue(all(parts), api)
            self.assertEqual(json.loads("".join(parts)), {"path": "/p/README.md"}, api)
            with self.assertRaises(ValueError, msg=api):
                json.loads(parts[0])

    def test_scripted_steps_answer_requests_in_order(self):
        results = stream("openai-completions", [mock.Step(text="first"), mock.Step(text="second"), mock.Step(text="third")], request_count=4)
        self.assertEqual([text_of("openai-completions", sse(d)) for _, d in results], ["first", "second", "third", "third"])

    def test_responses_sequence_numbers_start_at_zero_and_are_contiguous(self):
        (_, data), = stream("openai-responses", [mock.Step(text="a b c")])
        seq = [d["sequence_number"] for _, d in sse(data)]
        self.assertEqual(seq, list(range(len(seq))))

    def test_usage_is_the_same_in_the_stream_and_in_a_plain_reply_and_counts_tool_calls(self):
        # Completion tokens: one per streamed text part plus 12 per tool call, on every API, streamed or not.
        for api, path_body in PATHS.items():
            path, body = path_body
            plain = dict(body, stream=False)
            with mock.MockServer(policy=mock.scripted_policy([self.STEP])) as srv:
                _, data = call(srv, path, plain)
            final = json.loads(data)
            out = {"openai-completions": lambda f: f["usage"]["completion_tokens"], "anthropic-messages": lambda f: f["usage"]["output_tokens"],
                   "openai-responses": lambda f: f["usage"]["output_tokens"]}[api](final)
            self.assertEqual(out, 12, api)
        (_, chat), = stream("openai-completions", [self.STEP])
        self.assertEqual([d["usage"]["completion_tokens"] for _, d in sse(chat) if d != "[DONE]" and "usage" in d], [12])
        (_, anth), = stream("anthropic-messages", [self.STEP])
        self.assertEqual([d["usage"]["output_tokens"] for n, d in sse(anth) if n == "message_delta"], [12])


class LargeWriteStream(unittest.TestCase):
    """A tool call's arguments stream in fixed-size pieces (`arg_chunk_chars`) in each API's own delta format."""

    BODY = shapes.source(1000)
    ARGS = {"path": "/p/big/source.ts", "content": BODY}

    def pieces(self, api, chunk):
        (_, data), = stream(api, [mock.Step(tool_calls=[("write", self.ARGS)], arg_chunk_chars=chunk)])
        events = sse(data)
        if api == "openai-completions":
            return [c["function"]["arguments"] for _, d in events if d != "[DONE]" for ch in d["choices"] for c in ch["delta"].get("tool_calls", []) if c.get("function", {}).get("arguments")]
        if api == "anthropic-messages":
            return [d["delta"]["partial_json"] for n, d in events if n == "content_block_delta" and d["delta"]["type"] == "input_json_delta"]
        return [d["delta"] for n, d in events if n == "response.function_call_arguments.delta"]

    def test_every_api_streams_the_arguments_in_chunks_of_the_requested_size(self):
        text = json.dumps(self.ARGS)
        for api in PATHS:
            parts = self.pieces(api, 16)
            self.assertEqual([len(p) for p in parts[:-1]], [16] * (len(parts) - 1), api)
            self.assertTrue(0 < len(parts[-1]) <= 16, api)
            self.assertEqual(len(parts), -(-len(text) // 16), api)
            self.assertEqual("".join(parts), text, api)
            self.assertEqual(json.loads("".join(parts)), self.ARGS, api)

    def test_without_the_option_the_arguments_still_come_in_two_halves(self):
        for api in PATHS:
            self.assertEqual(len(self.pieces(api, 0)), 2, api)

    def test_the_responses_stream_ends_with_the_whole_arguments_and_the_function_call_item(self):
        (_, data), = stream("openai-responses", [mock.Step(tool_calls=[("write", self.ARGS)], arg_chunk_chars=16)])
        done = [d for n, d in sse(data) if n == "response.function_call_arguments.done"][0]
        self.assertEqual(json.loads(done["arguments"]), self.ARGS)

    def test_the_source_body_has_the_exact_size_and_is_deterministic(self):
        for size in (1, 100, 51200, 204800):
            self.assertEqual(len(shapes.source(size)), size)
        self.assertEqual(shapes.source(5000), shapes.source(5000))
        self.assertTrue(shapes.source(200).startswith("export function step0(input: number[]): number { return input.reduce((a, b) => a + b * 0, 0); }\n"))

    def test_the_write_call_takes_each_tools_own_argument_names(self):
        def req(name, props):
            return type("R", (), {"schemas": {name: {"properties": {k: {} for k in props}}}})()
        self.assertEqual(mock.write_call(req("write", ["path", "content"]), "/a", "x"), ("write", {"path": "/a", "content": "x"}))
        self.assertEqual(mock.write_call(req("Write", ["file_path", "content"]), "/a", "x"), ("Write", {"file_path": "/a", "content": "x"}))
        self.assertEqual(mock.write_call(req("write", ["filePath", "content"]), "/a", "x"), ("write", {"filePath": "/a", "content": "x"}))
        self.assertIsNone(mock.write_call(req("read", ["path"]), "/a", "x"))
        self.assertIsNone(mock.write_call(req("write", ["path"]), "/a", "x"))


class RequestLogTest(unittest.TestCase):
    def post(self, srv, body):
        conn = http.client.HTTPConnection("127.0.0.1", srv.port, timeout=10)
        conn.request("POST", "/v1/chat/completions", json.dumps(body))
        conn.getresponse().read()
        conn.close()

    def test_every_request_of_a_sample_is_logged_with_times_bytes_and_a_body_that_expands_exactly(self):
        import tempfile
        from buffon.mock import reqlog
        directory = tempfile.mkdtemp()
        msgs = [{"role": "user", "content": "q"}]
        bodies = [{"model": "m", "stream": False, "messages": list(msgs)}]
        msgs2 = msgs + [{"role": "assistant", "content": "a"}, {"role": "user", "content": "q2"}]
        bodies.append({"model": "m", "stream": False, "messages": msgs2})
        bodies.append({"model": "m", "stream": False, "messages": [{"role": "user", "content": "unrelated"}] + msgs2[1:] + [{"role": "assistant", "content": "z"}]})  # as long, other prefix
        with mock.MockServer(sink=reqlog.RequestLog(directory)) as srv:
            srv.context = {"arm": "pi-node", "scenario": "overhead/print", "api": "openai-completions", "round": 4, "warmup": False}
            for b in bodies:
                self.post(srv, b)
            srv.flush_log()
            srv.flush_log()  # nothing new: no second file
        files = sorted(os.listdir(directory))
        self.assertEqual(len(files), 1)
        self.assertIn("pi-node-overhead_print-openai-completions-r4", files[0])
        records = reqlog.read(os.path.join(directory, files[0]))
        self.assertEqual([r["body"] for r in records], bodies)
        self.assertEqual([r["index"] for r in records], [0, 1, 2])
        for r in records:
            self.assertEqual(r["context"]["round"], 4)
            self.assertGreater(r["wire_bytes"], 0)
            self.assertLessEqual(r["t_recv_ns"], r["t_reply_start_ns"])
            self.assertLessEqual(r["t_reply_start_ns"], r["t_reply_end_ns"])

    def test_a_history_that_extends_the_previous_request_is_stored_as_its_tail(self):
        import gzip
        import tempfile
        from buffon.mock import reqlog
        directory = tempfile.mkdtemp()
        history = [{"role": "user", "content": "x" * 5000}]
        with mock.MockServer(sink=reqlog.RequestLog(directory)) as srv:
            for i in range(3):
                self.post(srv, {"stream": False, "messages": list(history)})
                history = history + [{"role": "assistant", "content": f"a{i}"}, {"role": "user", "content": f"u{i}"}]
            srv.flush_log()
        path = os.path.join(directory, os.listdir(directory)[0])
        with gzip.open(path, "rt") as f:
            stored = [json.loads(line)["body"] for line in f]
        self.assertIn("messages", stored[0])
        self.assertEqual(stored[1]["extends_previous"]["shared"], 1)
        self.assertEqual(len(stored[1]["extends_previous"]["tail"]), 2)
        self.assertEqual(stored[2]["extends_previous"]["shared"], 3)
        self.assertNotIn("x" * 5000, json.dumps(stored[1:]))
        self.assertEqual(reqlog.read(path)[2]["body"]["messages"], history[:5])

    def test_reset_flushes_what_is_pending_under_the_context_it_was_received_in(self):
        import tempfile
        from buffon.mock import reqlog
        directory = tempfile.mkdtemp()
        with mock.MockServer(sink=reqlog.RequestLog(directory)) as srv:
            srv.context = {"arm": "a", "scenario": "s", "api": "openai-completions", "round": 1}
            self.post(srv, {"stream": False, "messages": []})
            srv.reset()
            srv.context = {"arm": "b", "scenario": "s", "api": "openai-completions", "round": 2}
            self.post(srv, {"stream": False, "messages": []})
            srv.flush_log()
        files = sorted(os.listdir(directory))
        self.assertEqual(len(files), 2)
        self.assertIn("-a-s-openai-completions-r1", files[0])
        self.assertIn("-b-s-openai-completions-r2", files[1])


class TranscriptCwd(unittest.TestCase):
    def test_a_directory_with_quotes_and_backslashes_reaches_the_tool_call_as_is(self):
        from buffon.mock import transcript
        cwd = 'C:\\Users\\a "b"\\proj'
        step = transcript.step_from({"tool_calls": [["read", {"path": "{cwd}/README.md", "nested": ["{cwd}", {"k": "x{cwd}y"}], "n": 3}]]}, cwd)
        (name, args), = step.tool_calls
        self.assertEqual(args, {"path": cwd + "/README.md", "nested": [cwd, {"k": "x" + cwd + "y"}], "n": 3})
