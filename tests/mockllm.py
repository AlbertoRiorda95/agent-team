"""A scripted model server for the harness tests: the Anthropic Messages API
(Claude Code), the OpenAI Responses API (Codex) and Chat Completions
(OpenCode, LiteLLM), streaming or not.

The script is in the conversation itself: the first user message holds
`MOCK: [step, ...]`, each step a tool call {"tool": name, "input": {...}}.
The server answers step k after k tool results, then "done". A subagent's
prompt carries its own MOCK script. Requests without a script get "ok".
Every request is kept in `server.requests` for the assertions.
"""
import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MOCK = "MOCK: "


def texts(content):
    if isinstance(content, str):
        return [content]
    out = []
    for b in content or []:
        if isinstance(b, dict):
            for k in ("text", "content"):
                if isinstance(b.get(k), str):
                    out.append(b[k])
                elif isinstance(b.get(k), list):
                    out += texts(b[k])
    return out


def script_of(messages):
    """The MOCK script of the conversation, and how many tool results it has."""
    steps = None
    for m in messages:
        if m.get("role") in ("user", None) and steps is None:
            for t in texts(m.get("content")):
                i = t.find(MOCK)
                if i >= 0:                       # the JSON list after the marker (a subagent's script may be inside)
                    rest = t[i + len(MOCK):]
                    try:
                        steps = json.JSONDecoder().raw_decode(rest)[0]
                    except ValueError:           # opencode run passes the prompt quoted, its quotes escaped
                        steps = json.JSONDecoder().raw_decode(rest.replace('\\"', '"'))[0]
                    break
    return steps


def anthropic_results(messages):
    n = 0
    for m in messages:
        if m.get("role") == "user" and isinstance(m.get("content"), list):
            n += sum(1 for b in m["content"] if isinstance(b, dict) and b.get("type") == "tool_result")
    return n


class Server:
    def __init__(self, host="127.0.0.1"):
        self.requests = []
        self.lock = threading.Lock()
        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def do_GET(self):
                if self.path.rstrip("/").endswith("/models"):
                    return self.json({"object": "list", "data": [{"id": "mock-model", "object": "model"}]})
                self.json({})

            def do_HEAD(self):
                self.send_response(200)
                self.send_header("content-length", "0")
                self.end_headers()

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("content-length") or 0)) or b"{}")
                with outer.lock:
                    outer.requests.append({"path": self.path, "body": body, "headers": dict(self.headers)})
                if self.path.split("?")[0].endswith("/messages/count_tokens"):
                    return self.json({"input_tokens": 10})
                if self.path.split("?")[0].endswith("/messages"):
                    return outer.anthropic(self, body)
                if self.path.split("?")[0].endswith("/responses"):
                    return outer.responses(self, body)
                if self.path.split("?")[0].endswith("/chat/completions"):
                    return outer.chat(self, body)
                self.json({})

            def json(self, obj, code=200):
                data = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def sse(self, events):
                self.send_response(200)
                self.send_header("content-type", "text/event-stream")
                self.send_header("cache-control", "no-cache")
                self.send_header("connection", "close")
                self.end_headers()
                for name, data in events:
                    chunk = (f"event: {name}\n" if name else "") + f"data: {data if isinstance(data, str) else json.dumps(data)}\n\n"
                    self.wfile.write(chunk.encode())
                self.wfile.flush()
                self.close_connection = True

        self.httpd = ThreadingHTTPServer((host, 0), Handler)
        self.port = self.httpd.server_address[1]
        self.url = f"http://127.0.0.1:{self.port}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    # what to answer: the next step of the script, or a final text
    @staticmethod
    def next_step(steps, done):
        if steps is not None and done < len(steps):
            return steps[done]
        return None

    def anthropic(self, h, body):
        messages = body.get("messages", [])
        step = self.next_step(script_of(messages), anthropic_results(messages))
        model = body.get("model", "mock")
        mid = "msg_" + uuid.uuid4().hex[:20]
        if step:
            block = {"type": "tool_use", "id": "toolu_" + uuid.uuid4().hex[:20], "name": step["tool"], "input": {}}
            stop, partial = "tool_use", json.dumps(step["input"])
        else:
            block, stop, partial = {"type": "text", "text": ""}, "end_turn", None
        if not body.get("stream"):
            block = dict(block, input=step["input"]) if step else dict(block, text="done")
            return h.json({"id": mid, "type": "message", "role": "assistant", "model": model, "content": [block],
                           "stop_reason": stop, "stop_sequence": None,
                           "usage": {"input_tokens": 10, "output_tokens": 5}})
        delta = ({"type": "input_json_delta", "partial_json": partial} if step
                 else {"type": "text_delta", "text": "done"})
        h.sse([("message_start", {"type": "message_start", "message": {
                   "id": mid, "type": "message", "role": "assistant", "model": model, "content": [],
                   "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 10, "output_tokens": 1}}}),
               ("content_block_start", {"type": "content_block_start", "index": 0, "content_block": block}),
               ("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": delta}),
               ("content_block_stop", {"type": "content_block_stop", "index": 0}),
               ("message_delta", {"type": "message_delta", "delta": {"stop_reason": stop, "stop_sequence": None},
                                  "usage": {"output_tokens": 5}}),
               ("message_stop", {"type": "message_stop"})])

    def responses(self, h, body):
        items = body.get("input", [])
        items = [{"role": "user", "content": items}] if isinstance(items, str) else items
        users = [i for i in items if i.get("role") == "user" or i.get("type") == "message"]
        done = sum(1 for i in items if i.get("type") in ("function_call_output", "custom_tool_call_output",
                                                          "local_shell_call_output"))
        step = self.next_step(script_of(users), done)
        rid = "resp_" + uuid.uuid4().hex[:20]
        if step:
            args = step["input"] if isinstance(step["input"], str) else json.dumps(step["input"])
            item = {"type": "function_call", "id": "fc_" + uuid.uuid4().hex[:12], "call_id": "call_" + uuid.uuid4().hex[:12],
                    "name": step["tool"], "arguments": args, "status": "completed"}
        else:
            item = {"type": "message", "id": "msg_" + uuid.uuid4().hex[:12], "role": "assistant", "status": "completed",
                    "content": [{"type": "output_text", "text": "done", "annotations": []}]}
        resp = {"id": rid, "object": "response", "status": "completed", "model": body.get("model", "mock"),
                "output": [item], "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15,
                                             "input_tokens_details": {"cached_tokens": 0},
                                             "output_tokens_details": {"reasoning_tokens": 0}}}
        if not body.get("stream"):
            return h.json(resp)
        h.sse([("response.created", {"type": "response.created", "response": dict(resp, status="in_progress", output=[])}),
               ("response.output_item.added", {"type": "response.output_item.added", "output_index": 0, "item": item}),
               ("response.output_item.done", {"type": "response.output_item.done", "output_index": 0, "item": item}),
               ("response.completed", {"type": "response.completed", "response": resp})])

    def chat(self, h, body):
        messages = body.get("messages", [])
        done = sum(1 for m in messages if m.get("role") == "tool")
        step = self.next_step(script_of(messages), done)
        cid = "chatcmpl-" + uuid.uuid4().hex[:20]
        model = body.get("model", "mock")
        if step:
            call = {"index": 0, "id": "call_" + uuid.uuid4().hex[:12], "type": "function",
                    "function": {"name": step["tool"], "arguments": json.dumps(step["input"])}}
            msg, finish = {"role": "assistant", "content": None, "tool_calls": [call]}, "tool_calls"
        else:
            msg, finish = {"role": "assistant", "content": "done"}, "stop"
        usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        if not body.get("stream"):
            return h.json({"id": cid, "object": "chat.completion", "created": 0, "model": model,
                           "choices": [{"index": 0, "message": msg, "finish_reason": finish}], "usage": usage})
        base = {"id": cid, "object": "chat.completion.chunk", "created": 0, "model": model}
        h.sse([(None, dict(base, choices=[{"index": 0, "delta": msg, "finish_reason": None}])),
               (None, dict(base, choices=[{"index": 0, "delta": {}, "finish_reason": finish}], usage=usage)),
               (None, "[DONE]")])

    # assertions
    def tool_results(self):
        """Every tool result the harness sent back, as text, in order (deduplicated)."""
        seen, out = set(), []
        for r in self.requests:
            b = r["body"]
            for m in b.get("messages", []) + (b.get("input") if isinstance(b.get("input"), list) else []):
                blocks = []
                if m.get("role") == "user" and isinstance(m.get("content"), list):
                    blocks = [x for x in m["content"] if isinstance(x, dict) and x.get("type") == "tool_result"]
                elif m.get("role") == "tool":
                    blocks = [{"tool_use_id": m.get("tool_call_id"), "content": m.get("content")}]
                elif m.get("type", "").endswith("_output"):
                    blocks = [{"tool_use_id": m.get("call_id"), "content": m.get("output")}]
                for x in blocks:
                    key = x.get("tool_use_id")
                    if key not in seen:
                        seen.add(key)
                        c = x.get("content")
                        out.append(c if isinstance(c, str) else "\n".join(texts(c)) if isinstance(c, list) else json.dumps(c))
        return out


def script(*steps):
    return "MOCK: " + json.dumps(list(steps)) + " END"
