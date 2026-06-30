#!/usr/bin/env -S uv run --script

# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = [
#     "locust",
# ]
# [tool.uv]
# exclude-newer = "2026-06-30T23:59:59Z"
# ///

# pyright: reportMissingImports=false

"""
Locust load test that simulates agentic coding traffic against a local
vLLM OpenAI-compatible endpoint.

Unlike one-shot chat benchmarks, this models the traffic shape an actual
coding agent produces:
  - a persistent system prompt + tool definitions (exercises prefix caching)
  - multi-turn trajectories with growing context
  - tool-call / tool-result turns appended each iteration
  - decode-heavy structured output (code, tool args)
  - per-turn think time

Run (with uv managing the locust dependency):
    uv run --with locust locust -f locustfile.py --host http://127.0.0.1:61519

Or invoke locust directly once deps are present:
    locust -f locustfile.py --host http://127.0.0.1:61519

Headless example (8 concurrent agents, ramp 2/s, run 5m):
    uv run --with locust locust -f locustfile.py --host http://127.0.0.1:61519 \
        --headless -u 8 -r 2 -t 5m --csv stress

Tune VLLM_MODEL and the trajectory length to match your serving config.
"""

import os
import random
from locust import HttpUser, task, between, events

MODEL = os.environ.get("VLLM_MODEL", "qwen3-coder-next")
API_KEY = os.environ.get("VLLM_API_KEY", "local")

# A realistic system prompt + tool block. This prefix is identical across
# every request, so it is what vLLM's --enable-prefix-caching should absorb.
SYSTEM_PROMPT = """You are an autonomous software engineering agent operating \
inside a repository. You work in a loop: read context, decide on a single \
tool call, observe the result, and continue until the task is complete. \
Always respond with a single tool call in JSON when acting, or a final \
summary when done. Prefer minimal, correct diffs. Never fabricate file \
contents you have not read."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file in the repository.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Apply a unified diff to a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "diff": {"type": "string"},
                },
                "required": ["path", "diff"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": "Run the test suite and return results.",
            "parameters": {
                "type": "object",
                "properties": {"target": {"type": "string"}},
                "required": [],
            },
        },
    },
]

# Seed tasks an agent might be asked to do. Kept short; the realism comes
# from the multi-turn loop, not the initial prompt.
SEED_TASKS = [
    "The scanner module drops files with unicode names. Find and fix it.",
    "Add a --dry-run flag to the CLI that prints planned changes without writing.",
    "Tests are flaky in test_metadata.py. Diagnose and stabilize them.",
    "Refactor the playlist loader to stream instead of reading the whole file.",
    "There's an off-by-one in the pagination logic. Locate and patch it.",
    "Add retry-with-backoff to the network fetch helper.",
]

# Synthetic tool results to feed back into the conversation, simulating an
# environment responding to the agent. These grow the context each turn.
def synth_tool_result(turn: int) -> str:
    blob = "\n".join(
        f"line {i}: def func_{i}(x): return x * {i} + {turn}"
        for i in range(40 + turn * 10)
    )
    return f"<tool_result turn={turn}>\n{blob}\n</tool_result>"


class AgentSession(HttpUser):
    # Think time between turns within a single agent trajectory.
    wait_time = between(0.5, 2.0)

    def on_start(self):
        # Each simulated agent gets its own conversation that grows over turns.
        self.turn = 0
        self.max_turns = random.randint(6, 14)
        self.messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": random.choice(SEED_TASKS)},
        ]

    @task
    def agent_step(self):
        payload = {
            "model": MODEL,
            "messages": self.messages,
            "tools": TOOLS,
            "max_tokens": 512,
            "temperature": 0.2,
            "stream": False,
        }

        with self.client.post(
            "/v1/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {API_KEY}"},
            name="chat_step",
            catch_response=True,
            timeout=300,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"HTTP {resp.status_code}: {resp.text[:200]}")
                self._reset()
                return
            try:
                data = resp.json()
                msg = data["choices"][0]["message"]
                usage = data.get("usage", {})
            except Exception as e:  # noqa: BLE001
                resp.failure(f"parse error: {e}")
                self._reset()
                return

            # Record token throughput as a custom metric.
            ct = usage.get("completion_tokens", 0)
            events.request.fire(
                request_type="tokens",
                name="completion_tokens",
                response_time=ct,
                response_length=0,
                exception=None,
                context={},
            )
            resp.success()

        # Advance the trajectory: append the assistant turn, then a synthetic
        # tool result, growing context exactly like a real agent loop.
        self.messages.append(
            {"role": "assistant", "content": msg.get("content") or "(tool call)"}
        )
        self.turn += 1
        if self.turn >= self.max_turns:
            self._reset()
            return
        self.messages.append(
            {"role": "user", "content": synth_tool_result(self.turn)}
        )

    def _reset(self):
        self.turn = 0
        self.max_turns = random.randint(6, 14)
        self.messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": random.choice(SEED_TASKS)},
        ]


@events.test_stop.add_listener
def _summary(environment, **_):
    stats = environment.stats.get("chat_step", "POST")
    if stats and stats.num_requests:
        print("\n=== agentic stress summary ===")
        print(f"requests:        {stats.num_requests}")
        print(f"failures:        {stats.num_failures}")
        print(f"median (ms):     {stats.median_response_time}")
        print(f"p95 (ms):        {stats.get_response_time_percentile(0.95)}")
        print(f"p99 (ms):        {stats.get_response_time_percentile(0.99)}")
        print(f"rps:             {stats.total_rps:.2f}")
