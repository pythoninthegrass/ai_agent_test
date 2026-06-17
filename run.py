#!/usr/bin/env -S uv run --script

# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = [
#     "docker>=7.1.0",
#     "GitPython>=3.1.43",
#     "sh>=2.2.2",
# ]
# [tool.uv]
# exclude-newer = "2026-06-02T00:00:00Z"
# ///

# pyright: reportMissingImports=false

"""
rpncalc compaction-stress harness.

Drives a long, irreducible agentic loop (TASK.md) and watches whether pi
compacts before koboldcpp SmartCache-shifts. Each builder request logs
`CtxLimit:<used>/131072`:
    PASS : <used> climbs, then DROPS sharply when pi compacts; never nears 131072.
    FAIL : <used> creeps toward 131072 and koboldcpp shifts (silent turn drop)
           -> pi never compacted. The compose runs `--smartcache 5` with no
           `--noshift`, so this is SILENT in kobold; CtxLimit is the only tell.

Usage:
    run.py observe                  Stream builder+proxy logs, flag compaction signals.
    run.py loop                     Reset build/, launch INTERACTIVE pi (watch in 2nd term).
    run.py watch                    Reset build/, headless pi + live log alarms in ONE term.
    run.py milestones               Reset build/, drive ONE milestone per pi invocation in a
                                    shared session so pi compacts between milestones.
    run.py opencode-milestones      Same as milestones but drives opencode instead of pi.
                                    Default model: local-builder/qwen3-coder-next (proxy 61519).
    run.py hermes-milestones        Same as milestones but drives hermes-agent instead of pi.
                                    Default model: qwen3-coder-next (proxy 61519 via config.yaml).
                                    Requires the hermes server to already be running if using
                                    the API server mode; CLI mode starts hermes per-step.
    run.py pi-pacman               One-shot pacman.html generation via pi with --system-prompt.
                                    Artifacts in artifacts/pi/.
    run.py pacman                  One-shot pacman.html generation via hermes Python library with
                                    a custom ephemeral system prompt (vanilla web dev expert).
                                    Artifacts in artifacts/hermes/.
    run.py stress                   Synthetic agentic-load test via Locust against the :61519
                                    proxy: concurrent agent sessions, growing multi-turn
                                    context, tool-call/tool-result turns. Streams the same
                                    CtxLimit/context-shift Docker signals as the milestone
                                    commands. Artifacts in build-locust-vllm/.
    run.py                          Show this help.

Flags (observe / watch / milestones):
    --tail N      Replay N history lines before following (default 0).
    --warn-at N   CtxLimit value that turns red (default 118000).
    --match S     Container name filter (default: coder-next).

Flags (milestones):
    --model M       provider/id passed to `pi --model` (default: koboldcpp/qwen3-coder-next-builder).
    --total N       Milestone count that means "done" (default 18).
    --max-steps N   Max pi invocations before giving up (default 40).
    --max-stalls N  Consecutive invocations with no new milestone commit before bailing (default 4).
    --step-timeout N  Wall-clock seconds before a single pi invocation is force-killed
                      (default 600). A livelocked invocation never ends its agent run on its
                      own; the watchdog kills its process group, counts the step as a stall,
                      and re-prompts in the same session (a fresh agent run, so pi's
                      pre-prompt compaction check fires). 0 disables the cap.

Flags (stress):
    --host URL      vLLM/proxy base URL (default: http://127.0.0.1:61519).
    --api-key K     Bearer token for the endpoint (default: local).
    --users N       Concurrent virtual agents (default: 8).
    --rate N        Users to spawn per second during ramp-up (default: 2).
    --duration S    Total run time, e.g. 5m, 30s (default: 5m).

Why this mode exists: pi only checks auto-compaction when an agent run ENDS (at agent_end)
or before a new prompt — never inside one continuous tool loop. A single `pi -p` that drives
all 18 milestones is one unbroken loop, so compaction never fires and context climbs to the
131072 ceiling. Driving ONE milestone per `pi -p --session-id <id>` invocation creates an
agent-run boundary per milestone: pi's pre-prompt + post-run compaction checks fire between
them, keeping context bounded while the shared session preserves continuity.
"""

import argparse
import json
import os
import re
import shutil
import sys
import threading
import uuid
from pathlib import Path

import docker
import sh
from git import Repo
from sh import ErrorReturnCode

HERE = Path(__file__).resolve().parent
BUILD = HERE / "build"
TASK = HERE / "TASK.md"
PROMPT = (
    "Read TASK.md and complete ALL 18 milestones in full, following every working rule. "
    "Work autonomously and do not stop until milestone 18 is committed: after finishing "
    "each milestone, IMMEDIATELY start the next one by issuing the next tool call. Never "
    "end your turn with prose that merely announces what you will do next (e.g. 'now "
    "proceeding to milestone N') — instead, actually issue that next action. Do not pause "
    "for confirmation. Only produce a final text summary after milestone 18 is done. "
    "Begin with milestone 1 now."
)

SESSION_MODEL = "koboldcpp/qwen3-coder-next-builder"
OPENCODE_MODEL = "local-builder/qwen3-coder-next"
OPENCODE_BIN = shutil.which("opencode") or "/home/lance/.opencode/bin/opencode"
HERMES_MODEL = "Qwen3.6-35B-A3B-MTP-GGUF"
HERMES_BIN = shutil.which("hermes") or "/home/lance/.local/bin/hermes"
HERMES_PYTHON = "/home/lance/.hermes/hermes-agent/venv/bin/python"
STRESS_HOST = "http://127.0.0.1:61519"
STRESS_MODEL = "qwen3-coder-next"
MILESTONE_PROMPT = (
    "Read TASK.md. Run `git log --oneline` to see which milestones are already "
    "committed. Complete the NEXT not-yet-committed milestone using TDD (write the "
    "failing test, make it pass, refactor), then `git commit` it with the message "
    "`milestone N: <slug>` where N is the milestone number. Do EXACTLY ONE milestone "
    "this turn. After committing, run `git log --oneline` to confirm the commit "
    "appears — do NOT declare a milestone complete unless you can see its commit in "
    "the log. Then STOP and end your turn — do NOT start the following milestone. "
    "The harness re-invokes you in this same session to continue."
)

PACMAN_SYSTEM_PROMPT = (
    "You are the world's leading expert in vanilla web development, specifically in creating "
    "high-performance, single-file web applications using only HTML5, CSS3, and ES6+ JavaScript. "
    "You reject frameworks in favor of clean, efficient, and semantic code.\n\n"
    "Your goal is to receive a requirement and produce a single, self-contained HTML file that "
    "functions perfectly without external dependencies (no CDNs, no images, no libraries).\n\n"
    "Because you must complete this task in a \"one-shot\" continuous generation, you must think "
    "before you code. You will follow a strict \"Chain of Thought\" protocol to ensure correctness.\n\n"
    "Follow this specific execution format for every response:\n\n"
    "<analysis>\n"
    "1. REQUIREMENTS BREAKDOWN:\n"
    "   - List every functional and non-functional requirement.\n"
    "   - Identify potential edge cases.\n\n"
    "2. ARCHITECTURAL PLAN:\n"
    "   - CSS Strategy: Define the variable system, layout approach (Flexbox/Grid), and responsive breakpoints.\n"
    "   - JS Architecture: Define state management, event listeners, and core logic functions.\n"
    "   - HTML Structure: specific semantic tags to be used.\n\n"
    "3. PRE-MORTEM & STRATEGY:\n"
    "   - Identify the most likely point of failure.\n"
    "   - Define the solution for that specific failure point before writing code.\n"
    "</analysis>\n\n"
    "<implementation>\n"
    "(Provide the complete, valid HTML string here. Include CSS in <style> and JS in <script> tags. "
    "The code must be production-ready, accessible, and clean.)\n"
    "</implementation>\n\n"
    "<code_review>\n"
    "Self-Correction and Validation Report:\n"
    "1. Does the code meet all requirements listed in the analysis? [Yes/No]\n"
    "2. Are there any distinct accessibility (a11y) violations?\n"
    "3. Verify that no external libraries were used.\n"
    "</code_review>"
)

PACMAN_USER_PROMPT = (
    "[INTENT] Build a complete, playable Pac-Man clone as a self-contained HTML page that runs "
    "by double-clicking the file.\n\n"
    "[SCOPE]\n"
    "  - Classic Pac-Man gameplay: navigate maze, eat dots, avoid ghosts\n"
    "  - Core mechanics: maze with walls, dot collection, score, lives, 4 ghosts, power pellets "
    "with frightened-ghost mode\n"
    "  - Standard arcade elements: 4 ghosts with distinct AI personalities, wrap-around tunnel, "
    "multiple levels\n\n"
    "[APPROACH]\n"
    "  - Single pacman.html file with inline <style> and <script>\n"
    "  - HTML5 Canvas for rendering (grid-based maze, ~28x31 tiles like the original)\n"
    "  - Vanilla JavaScript, no frameworks\n"
    "  - Keyboard controls: arrow keys + WASD\n\n"
    "[CONSTRAINTS]\n"
    "  - Must work offline by opening the file directly in a browser\n"
    "  - No external dependencies, CDNs, or asset files\n"
    "  - No build step\n\n"
    "[DELIVERABLE]\n"
    "  - One complete pacman.html file\n\n"
    "[DONE WHEN]\n"
    "  - Game launches by double-clicking the file\n"
    "  - Pac-Man moves with keyboard and respects maze walls\n"
    "  - Dots are eatable; score increments\n"
    "  - 4 ghosts move with distinct behaviors and chase Pac-Man\n"
    "  - Power pellets turn ghosts vulnerable; eating a vulnerable ghost resets that ghost\n"
    "  - Pac-Man loses a life on ghost contact when not powered\n"
    "  - Game ends at 0 lives; restart works\n"
    "  - Score and lives visible on screen"
)

_PACMAN_SCRIPT = """\
import os, sys
from run_agent import AIAgent

agent = AIAgent(
    model=os.environ["HERMES_MODEL"],
    ephemeral_system_prompt=os.environ["HERMES_SYSTEM_PROMPT"],
    quiet_mode=True,
    skip_memory=True,
    save_trajectories=False,
)
response = agent.chat(os.environ["HERMES_USER_PROMPT"])
print(response)
"""

CTX = re.compile(r"CtxLimit:(\d+)/(\d+)")
# Real runtime shift events only — NOT the "SmartCache will be enabled" startup banner.
SHIFT = re.compile(r"Context Shift|ContextShift|Erased \d+ tokens|Trimming|context-shift", re.I)
PROXY = re.compile(r"finish=length|truncated|livelock|WARNING", re.I)

R = "\033[31m"; Y = "\033[33m"; G = "\033[32m"; B = "\033[1m"; D = "\033[2m"; X = "\033[0m"
PREFIX_COLORS = ["\033[36m", "\033[35m", "\033[34m", "\033[33m"]


# ── log observing ────────────────────────────────────────────────────────────

def classify(line: str, warn_at: int) -> str:
    """Return the line colorized by severity, or '' to drop it as noise."""
    if SHIFT.search(line):
        return f"{B}{R}{line}{X}"
    m = CTX.search(line)
    if m:
        used = int(m.group(1))
        return f"{B}{R}{line}{X}" if used >= warn_at else f"{G}{line}{X}"
    if PROXY.search(line):
        return f"{Y}{line}{X}"
    return ""


def stream(container, prefix, color, tail, warn_at):
    label = f"{color}{prefix:>8}{X} {D}|{X} "
    buf = b""
    for chunk in container.logs(stream=True, follow=True, timestamps=True, tail=tail):
        buf += chunk
        while b"\n" in buf:
            raw, buf = buf.split(b"\n", 1)
            line = raw.decode("utf-8", "replace").rstrip()
            if not line:
                continue
            out = classify(line, warn_at)
            if out:
                print(label + out, flush=True)


def start_observers(match, tail, warn_at):
    """Discover containers and spawn a daemon log-stream thread per container."""
    client = docker.from_env()
    containers = [c for c in client.containers.list() if match in c.name]
    if not containers:
        print(f"no running containers match '{match}'", file=sys.stderr)
        return []
    print("== watching:", ", ".join(c.name for c in containers), "==")
    print(f"   {G}GRN CtxLimit{X}  used/131072 -> climbs, then DROPS on compaction")
    print(f"   {B}{R}RED CtxLimit{X}  >= {warn_at} (danger; SmartCache shift near)")
    print(f"   {B}{R}RED shift{X}     explicit context-shift (compaction FAILED)")
    print(f"   {Y}YEL proxy{X}     finish=length / truncated / livelock\n")
    threads = []
    for i, c in enumerate(containers):
        prefix = c.name.split("-")[-1]
        color = PREFIX_COLORS[i % len(PREFIX_COLORS)]
        t = threading.Thread(target=stream, args=(c, prefix, color, tail, warn_at), daemon=True)
        t.start()
        threads.append(t)
    return threads


# ── build loop ───────────────────────────────────────────────────────────────

def reset_build():
    """Wipe build/, seed TASK.md + pytest.ini, git-init with a harness commit."""
    print(f"== resetting {BUILD} ==")
    if BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.mkdir(parents=True)
    (BUILD / "TASK.md").write_text(TASK.read_text())
    (BUILD / "pytest.ini").write_text("[pytest]\naddopts = -v\n")
    repo = Repo.init(BUILD)
    repo.git.add(A=True)
    repo.index.commit("milestone 00: harness")


def cmd_loop():
    reset_build()
    print(f"== launching interactive pi in {BUILD} ==")
    print(f"   paste when it opens:\n   {PROMPT}\n")
    os.chdir(BUILD)
    os.execvp("pi", ["pi"])  # replace this process; pi takes over the TTY


def cmd_watch(match, tail, warn_at):
    reset_build()
    start_observers(match, tail, warn_at)
    logfile = BUILD / "run.log"
    print(f"== headless pi in {BUILD} (tee -> {logfile}) ==\n")
    try:
        run = sh.pi("-p", PROMPT, _cwd=str(BUILD), _iter=True, _err_to_out=True)
        with logfile.open("w") as f:
            for line in run:
                sys.stdout.write(line)
                sys.stdout.flush()
                f.write(line)
    except ErrorReturnCode as e:
        print(f"pi exited non-zero ({e.exit_code})", file=sys.stderr)
        return e.exit_code
    return 0


def cmd_observe(match, tail, warn_at):
    threads = start_observers(match, tail, warn_at)
    if not threads:
        return 1
    try:
        while any(t.is_alive() for t in threads):
            for t in threads:
                t.join(timeout=0.5)
    except KeyboardInterrupt:
        print("\nstopped.")
    return 0


# ── milestone-driven loop ──────────────────────────────────────────────────────

MILESTONE_COMMIT = re.compile(r"milestone\s+(\d+)\b", re.I)


def milestone_count(repo) -> int:
    """Highest committed milestone number (>0); 0 if only the '00: harness' commit."""
    best = 0
    for commit in repo.iter_commits():
        m = MILESTONE_COMMIT.search(commit.message.splitlines()[0])
        if m:
            best = max(best, int(m.group(1)))
    return best


def _kill_run(run):
    """Best-effort terminate a sh RunningCommand and its whole process group."""
    for method in ("kill_group", "terminate", "kill"):
        try:
            getattr(run, method)()
            return
        except Exception:
            continue


def _harness_exit(status: str, reason: str, done: int, total: int, step: int, logfile) -> int:
    """Emit a grep-safe terminal marker, write it to the logfile, and touch build/harness.status.

    status is 'DONE' or 'BAIL'. A monitor watching stdout or build/harness.status will catch it.
    """
    msg = f"=== HARNESS:{status} reason={reason} milestones={done}/{total} steps={step} ==="
    print(msg, flush=True)
    logfile.write(msg + "\n")
    logfile.flush()
    (BUILD / "harness.status").write_text(msg + "\n")
    return 0 if status == "DONE" else 1


def _find_pi_session(build_dir: Path) -> str | None:
    """Return the UUID of the most recently created pi session for the given CWD."""
    cwd_key = str(build_dir).lstrip("/").replace("/", "-")
    session_dir = Path.home() / ".pi" / "agent" / "sessions" / f"--{cwd_key}--"
    files = sorted(session_dir.glob("*.jsonl"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        return None
    stem = files[0].stem  # e.g. "2026-06-13T05-27-22-454Z_019ebf72-f455-747b-9b85-..."
    return stem.split("_", 1)[1] if "_" in stem else stem


def cmd_milestones(match, tail, warn_at, model, total, max_steps, max_stalls, step_timeout):
    reset_build()
    start_observers(match, tail, warn_at)
    repo = Repo(BUILD)
    sid = None  # captured from pi session file after step 1; passed as --session on subsequent steps
    logfile = BUILD / "run.log"
    print(f"== milestone loop in {BUILD} ==")
    print(f"   model={model}  target={total} milestones")
    cap = f"{step_timeout}s" if step_timeout else "disabled"
    print(f"   step-timeout={cap}  tee -> {logfile}\n")

    done = milestone_count(repo)
    stalls = 0
    with logfile.open("w") as f:
        for step in range(1, max_steps + 1):
            print(f"\n{B}-- step {step}/{max_steps}  (milestones {done}/{total}) --{X}",
                  flush=True)
            f.write(f"\n-- step {step}  milestones={done}/{total}  sid={sid} --\n")
            f.flush()
            timed_out = threading.Event()
            cmd_args = ["-p", "--model", model]
            if sid is not None:
                cmd_args += ["--session", sid]
            cmd_args.append(MILESTONE_PROMPT)
            run = sh.pi(*cmd_args, _cwd=str(BUILD), _iter=True,
                        _err_to_out=True, _new_session=True, _bg_exc=False)
            timer = None
            if step_timeout:
                def _watchdog(r=run):
                    timed_out.set()
                    _kill_run(r)
                timer = threading.Timer(step_timeout, _watchdog)
                timer.start()
            try:
                for line in run:
                    sys.stdout.write(line)
                    sys.stdout.flush()
                    f.write(line)
                    f.flush()
            except ErrorReturnCode as e:
                if not timed_out.is_set():
                    print(f"{R}pi exited non-zero ({e.exit_code}) on step {step}{X}",
                          file=sys.stderr)
            except Exception as e:
                # A watchdog kill surfaces as a sh SignalException here; only the
                # timeout path is expected — re-raise anything else.
                if not timed_out.is_set():
                    raise
            finally:
                if timer is not None:
                    timer.cancel()

            if timed_out.is_set():
                msg = f"-- step {step}: TIMED OUT after {step_timeout}s, killed process group --"
                print(f"{B}{R}{msg}{X}", flush=True)
                f.write(msg + "\n")
                f.flush()

            if sid is None:
                sid = _find_pi_session(BUILD)
                if sid:
                    print(f"{D}   pi session-id={sid}{X}", flush=True)

            now = milestone_count(repo)
            if now > done:
                gained = now - done
                done = now
                stalls = 0
                print(f"{G}-- step {step}: +{gained} milestone(s) -> {done}/{total} --{X}",
                      flush=True)
            else:
                stalls += 1
                print(f"{Y}-- step {step}: no new milestone (stall {stalls}/{max_stalls}) --{X}",
                      flush=True)

            if done >= total:
                print(f"\n{B}{G}== DONE: {done}/{total} milestones committed in {step} steps =={X}")
                return _harness_exit("DONE", "complete", done, total, step, f)
            if stalls >= max_stalls:
                print(f"\n{B}{R}== BAIL: {max_stalls} consecutive stalls at {done}/{total} =={X}")
                return _harness_exit("BAIL", f"stalls={stalls}", done, total, step, f)

    print(f"\n{B}{R}== BAIL: hit max-steps ({max_steps}) at {done}/{total} =={X}")
    with logfile.open("a") as f:
        return _harness_exit("BAIL", f"max-steps={max_steps}", done, total, max_steps, f)


def cmd_milestones_opencode(match, tail, warn_at, model, total, max_steps, max_stalls, step_timeout):
    reset_build()
    start_observers(match, tail, warn_at)
    repo = Repo(BUILD)
    sid = None  # captured from first JSON event; passed as --session on subsequent steps
    logfile = BUILD / "run.log"
    print(f"== opencode milestone loop in {BUILD} ==")
    print(f"   model={model}  target={total} milestones")
    cap = f"{step_timeout}s" if step_timeout else "disabled"
    print(f"   step-timeout={cap}  tee -> {logfile}\n")

    done = milestone_count(repo)
    stalls = 0
    with logfile.open("w") as f:
        for step in range(1, max_steps + 1):
            print(f"\n{B}-- step {step}/{max_steps}  (milestones {done}/{total}) --{X}",
                  flush=True)
            f.write(f"\n-- step {step}  milestones={done}/{total}  sid={sid or 'new'} --\n")
            f.flush()

            cmd_args = [
                "run", "--dir", str(BUILD), "--format", "json",
                "-m", model,
            ]
            if sid:
                cmd_args += ["--session", sid]
            cmd_args.append(MILESTONE_PROMPT)

            timed_out = threading.Event()
            run = sh.Command(OPENCODE_BIN)(
                *cmd_args, _iter=True, _err_to_out=True,
                _new_session=True, _bg_exc=False,
                _env={**os.environ, "OPENCODE_CONFIG": str(HERE / "opencode.json")},
            )
            timer = None
            if step_timeout:
                def _watchdog(r=run):
                    timed_out.set()
                    _kill_run(r)
                timer = threading.Timer(step_timeout, _watchdog)
                timer.start()
            try:
                for line in run:
                    sys.stdout.write(line)
                    sys.stdout.flush()
                    f.write(line)
                    f.flush()
                    try:
                        ev = json.loads(line)
                        if sid is None and "sessionID" in ev:
                            sid = ev["sessionID"]
                            print(f"{D}   opencode session-id={sid}{X}", flush=True)
                        if ev.get("type") == "step_finish":
                            part = ev.get("part", {})
                            tokens = part.get("tokens", {})
                            reason = part.get("reason", "?")
                            inp = tokens.get("input", 0)
                            out = tokens.get("output", 0)
                            total_tok = tokens.get("total", 0)
                            flag = f" {R}finish=length{X}" if reason == "length" else ""
                            print(
                                f"{D}   tokens: input={inp} output={out} "
                                f"total={total_tok} reason={reason}{flag}{X}",
                                flush=True,
                            )
                    except (json.JSONDecodeError, AttributeError):
                        pass
            except ErrorReturnCode as e:
                if not timed_out.is_set():
                    print(f"{R}opencode exited non-zero ({e.exit_code}) on step {step}{X}",
                          file=sys.stderr)
            except Exception:
                if not timed_out.is_set():
                    raise
            finally:
                if timer is not None:
                    timer.cancel()

            if timed_out.is_set():
                msg = f"-- step {step}: TIMED OUT after {step_timeout}s, killed process group --"
                print(f"{B}{R}{msg}{X}", flush=True)
                f.write(msg + "\n")
                f.flush()

            now = milestone_count(repo)
            if now > done:
                gained = now - done
                done = now
                stalls = 0
                print(f"{G}-- step {step}: +{gained} milestone(s) -> {done}/{total} --{X}",
                      flush=True)
            else:
                stalls += 1
                print(f"{Y}-- step {step}: no new milestone (stall {stalls}/{max_stalls}) --{X}",
                      flush=True)

            if done >= total:
                print(f"\n{B}{G}== DONE: {done}/{total} milestones committed in {step} steps =={X}")
                return _harness_exit("DONE", "complete", done, total, step, f)
            if stalls >= max_stalls:
                print(f"\n{B}{R}== BAIL: {max_stalls} consecutive stalls at {done}/{total} =={X}")
                return _harness_exit("BAIL", f"stalls={stalls}", done, total, step, f)

    print(f"\n{B}{R}== BAIL: hit max-steps ({max_steps}) at {done}/{total} =={X}")
    with logfile.open("a") as f:
        return _harness_exit("BAIL", f"max-steps={max_steps}", done, total, max_steps, f)


HERMES_SID = re.compile(r"^session_id:\s*(\S+)", re.M)


def cmd_milestones_hermes(match, tail, warn_at, model, total, max_steps, max_stalls, step_timeout):
    reset_build()
    start_observers(match, tail, warn_at)
    repo = Repo(BUILD)
    sid = None   # captured from first step's `session_id: <id>` line; --resume on subsequent steps
    logfile = BUILD / "run.log"
    print(f"== hermes milestone loop in {BUILD} ==")
    print(f"   model={model}  target={total} milestones")
    cap = f"{step_timeout}s" if step_timeout else "disabled"
    print(f"   step-timeout={cap}  tee -> {logfile}")
    print(f"   NOTE: hermes server must be running before starting this loop\n")

    done = milestone_count(repo)
    stalls = 0
    with logfile.open("w") as f:
        for step in range(1, max_steps + 1):
            print(f"\n{B}-- step {step}/{max_steps}  (milestones {done}/{total}) --{X}",
                  flush=True)
            f.write(f"\n-- step {step}  milestones={done}/{total}  sid={sid or 'new'} --\n")
            f.flush()

            cmd_args = ["chat", "-q", MILESTONE_PROMPT, "--model", model, "--yolo", "-Q"]
            if sid:
                cmd_args += ["--resume", sid]

            timed_out = threading.Event()
            output_buf = []
            run = sh.Command(HERMES_BIN)(
                *cmd_args, _cwd=str(BUILD), _iter=True,
                _err_to_out=True, _new_session=True, _bg_exc=False,
            )
            timer = None
            if step_timeout:
                def _watchdog(r=run):
                    timed_out.set()
                    _kill_run(r)
                timer = threading.Timer(step_timeout, _watchdog)
                timer.start()
            try:
                for line in run:
                    sys.stdout.write(line)
                    sys.stdout.flush()
                    f.write(line)
                    f.flush()
                    output_buf.append(line)
            except ErrorReturnCode as e:
                if not timed_out.is_set():
                    print(f"{R}hermes exited non-zero ({e.exit_code}) on step {step}{X}",
                          file=sys.stderr)
            except Exception as e:
                if not timed_out.is_set():
                    raise
            finally:
                if timer is not None:
                    timer.cancel()

            if timed_out.is_set():
                msg = f"-- step {step}: TIMED OUT after {step_timeout}s, killed process group --"
                print(f"{B}{R}{msg}{X}", flush=True)
                f.write(msg + "\n")
                f.flush()

            # capture session ID from the first step's output (appears as `session_id: <id>`)
            if sid is None:
                full_output = "".join(output_buf)
                m = HERMES_SID.search(full_output)
                if m:
                    sid = m.group(1)
                    print(f"{D}   hermes session-id={sid}{X}", flush=True)

            now = milestone_count(repo)
            if now > done:
                gained = now - done
                done = now
                stalls = 0
                print(f"{G}-- step {step}: +{gained} milestone(s) -> {done}/{total} --{X}",
                      flush=True)
            else:
                stalls += 1
                print(f"{Y}-- step {step}: no new milestone (stall {stalls}/{max_stalls}) --{X}",
                      flush=True)

            if done >= total:
                print(f"\n{B}{G}== DONE: {done}/{total} milestones committed in {step} steps =={X}")
                return _harness_exit("DONE", "complete", done, total, step, f)
            if stalls >= max_stalls:
                print(f"\n{B}{R}== BAIL: {max_stalls} consecutive stalls at {done}/{total} =={X}")
                return _harness_exit("BAIL", f"stalls={stalls}", done, total, step, f)

    print(f"\n{B}{R}== BAIL: hit max-steps ({max_steps}) at {done}/{total} =={X}")
    with logfile.open("a") as f:
        return _harness_exit("BAIL", f"max-steps={max_steps}", done, total, max_steps, f)


def cmd_pi_pacman(model):
    outdir = HERE / "artifacts" / "pi"
    outdir.mkdir(parents=True, exist_ok=True)
    logfile = outdir / "run.log"
    htmlfile = outdir / "pacman.html"

    print(f"== pi pacman ==")
    print(f"   model={model}  out={outdir}\n")

    output_lines = []
    status = "DONE"
    reason = "complete"

    with logfile.open("w") as f:
        try:
            run = sh.pi(
                "-p", "--model", model,
                "--system-prompt", PACMAN_SYSTEM_PROMPT,
                PACMAN_USER_PROMPT,
                _cwd=str(outdir), _iter=True,
                _err_to_out=True, _new_session=True, _bg_exc=False,
            )
            for line in run:
                sys.stdout.write(line)
                sys.stdout.flush()
                f.write(line)
                f.flush()
                output_lines.append(line)
        except ErrorReturnCode as e:
            print(f"{R}pi pacman exited non-zero ({e.exit_code}){X}", file=sys.stderr)
            status = "BAIL"
            reason = f"rc={e.exit_code}"

        full_output = "".join(output_lines)
        m = re.search(r"<implementation>(.*?)</implementation>", full_output, re.DOTALL)
        if m:
            html = m.group(1).strip()
            htmlfile.write_text(html)
            print(f"\n{G}pacman.html written ({len(html):,} bytes) -> {htmlfile}{X}")
        else:
            htmlfile.write_text(full_output)
            print(f"\n{Y}no <implementation> tags found; saved full response -> {htmlfile}{X}")

        msg = f"=== HARNESS:{status} reason={reason} html={htmlfile.name} ==="
        print(msg, flush=True)
        f.write(msg + "\n")

    (outdir / "harness.status").write_text(msg + "\n")
    return 0 if status == "DONE" else 1


def cmd_hermes_pacman(model):
    outdir = HERE / "artifacts" / "hermes"
    outdir.mkdir(exist_ok=True)
    logfile = outdir / "run.log"
    htmlfile = outdir / "pacman.html"

    print(f"== hermes pacman (python library) ==")
    print(f"   model={model}  out={outdir}\n")

    output_lines = []
    env = {
        **os.environ,
        "HERMES_MODEL": model,
        "HERMES_SYSTEM_PROMPT": PACMAN_SYSTEM_PROMPT,
        "HERMES_USER_PROMPT": PACMAN_USER_PROMPT,
    }
    status = "DONE"
    reason = "complete"

    with logfile.open("w") as f:
        try:
            run = sh.Command(HERMES_PYTHON)(
                "-c", _PACMAN_SCRIPT,
                _iter=True, _err_to_out=True, _env=env,
            )
            for line in run:
                sys.stdout.write(line)
                sys.stdout.flush()
                f.write(line)
                f.flush()
                output_lines.append(line)
        except ErrorReturnCode as e:
            print(f"{R}hermes pacman exited non-zero ({e.exit_code}){X}", file=sys.stderr)
            status = "BAIL"
            reason = f"rc={e.exit_code}"

        full_output = "".join(output_lines)
        m = re.search(r"<implementation>(.*?)</implementation>", full_output, re.DOTALL)
        if m:
            html = m.group(1).strip()
            htmlfile.write_text(html)
            print(f"\n{G}pacman.html written ({len(html):,} bytes) -> {htmlfile}{X}")
        else:
            htmlfile.write_text(full_output)
            print(f"\n{Y}no <implementation> tags found; saved full response -> {htmlfile}{X}")

        msg = f"=== HARNESS:{status} reason={reason} html={htmlfile.name} ==="
        print(msg, flush=True)
        f.write(msg + "\n")

    (outdir / "harness.status").write_text(msg + "\n")
    return 0 if status == "DONE" else 1


def cmd_stress(match, tail, warn_at, host, model, api_key, users, rate, duration):
    outdir = HERE / "build-locust-vllm"
    outdir.mkdir(exist_ok=True)
    logfile = outdir / "run.log"
    csv_prefix = str(outdir / "stress")
    locustfile = HERE / "locustfile.py"

    print(f"== locust stress run ==")
    print(f"   host={host}  model={model}  users={users}  rate={rate}  duration={duration}")
    print(f"   tee -> {logfile}\n")

    start_observers(match, tail, warn_at)

    status = "DONE"
    reason = "stress-complete"
    with logfile.open("w") as f:
        try:
            run = sh.uv(
                "run", "--with", "locust",
                "locust", "-f", str(locustfile),
                "--host", host,
                "--headless",
                "-u", str(users),
                "-r", str(rate),
                "-t", str(duration),
                "--csv", csv_prefix,
                _iter=True, _err_to_out=True,
                _env={**os.environ, "VLLM_MODEL": model, "VLLM_API_KEY": api_key},
            )
            for line in run:
                sys.stdout.write(line)
                sys.stdout.flush()
                f.write(line)
                f.flush()
        except ErrorReturnCode as e:
            print(f"{R}locust exited non-zero ({e.exit_code}){X}", file=sys.stderr)
            status = "BAIL"
            reason = f"locust-rc={e.exit_code}"

    msg = (f"=== HARNESS:{status} reason={reason} "
           f"users={users} rate={rate} duration={duration} ===")
    print(msg, flush=True)
    with logfile.open("a") as f:
        f.write(msg + "\n")
    (outdir / "harness.status").write_text(msg + "\n")
    return 0 if status == "DONE" else 1


def main() -> int:
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("cmd", nargs="?", default="help",
                    choices=["observe", "loop", "watch", "milestones",
                             "opencode-milestones", "hermes-milestones", "pi-pacman", "pacman",
                             "stress", "help"])
    ap.add_argument("--match", default="coder-next")
    ap.add_argument("--tail", default="0")
    ap.add_argument("--warn-at", type=int, default=118000)
    ap.add_argument("--model", default=SESSION_MODEL)
    ap.add_argument("--total", type=int, default=18)
    ap.add_argument("--max-steps", type=int, default=40)
    ap.add_argument("--max-stalls", type=int, default=4)
    ap.add_argument("--step-timeout", type=int, default=600)
    # stress flags
    ap.add_argument("--host", default=STRESS_HOST)
    ap.add_argument("--api-key", default="local")
    ap.add_argument("--users", type=int, default=8)
    ap.add_argument("--rate", type=int, default=2)
    ap.add_argument("--duration", default="5m")
    args = ap.parse_args()
    tail = args.tail if args.tail == "all" else int(args.tail)

    match args.cmd:
        case "observe":
            return cmd_observe(args.match, tail, args.warn_at)
        case "watch":
            return cmd_watch(args.match, tail, args.warn_at)
        case "milestones":
            return cmd_milestones(args.match, tail, args.warn_at, args.model,
                                  args.total, args.max_steps, args.max_stalls,
                                  args.step_timeout)
        case "opencode-milestones":
            model = args.model if args.model != SESSION_MODEL else OPENCODE_MODEL
            return cmd_milestones_opencode(args.match, tail, args.warn_at, model,
                                           args.total, args.max_steps, args.max_stalls,
                                           args.step_timeout)
        case "hermes-milestones":
            model = args.model if args.model != SESSION_MODEL else HERMES_MODEL
            return cmd_milestones_hermes(args.match, tail, args.warn_at, model,
                                         args.total, args.max_steps, args.max_stalls,
                                         args.step_timeout)
        case "pi-pacman":
            return cmd_pi_pacman(args.model)
        case "pacman":
            model = args.model if args.model != SESSION_MODEL else HERMES_MODEL
            return cmd_hermes_pacman(model)
        case "stress":
            model = args.model if args.model != SESSION_MODEL else STRESS_MODEL
            return cmd_stress(args.match, tail, args.warn_at, args.host, model,
                              args.api_key, args.users, args.rate, args.duration)
        case "loop":
            return cmd_loop()
        case _:
            print(__doc__)
            return 0


if __name__ == "__main__":
    sys.exit(main())
