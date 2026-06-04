"""Session 8 — growing-graph orchestrator.

The agent's loop becomes a NetworkX DiGraph. Each node is a skill; edges
carry typed AgentResult payloads. The graph GROWS at runtime via five
actors: the Planner's seed plan, dynamic successors from any skill,
static `internal_successors` from the yaml, Critic auto-insertion on
edges out of `critic:true` skills, and Planner re-invocation on node
failure (gated by `recovery.plan_recovery`). Perception's tool-blindness
contract from S7 is preserved — Planner names skills, never tools.

Persistence lives in persistence.py; skill execution in skills.py;
failure-policy in recovery.py; sandbox in sandbox.py.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
import uuid

import networkx as nx

import memory as memory_svc
from gateway import ensure_gateway
from persistence import SessionStore
from recovery import handle_critic_verdict, plan_recovery
from schemas import AgentResult, NodeState
from skills import SkillRegistry, run_skill

MAX_NODES = 60  # hard cap so a Planner loop cannot grow forever


# ── Graph ────────────────────────────────────────────────────────────────────

class Graph:
    """NetworkX DiGraph wrapper. Nodes are str ids `n:<i>`; each node carries
    `skill`, `inputs` (list of str), and `status`."""

    def __init__(self):
        self.g = nx.DiGraph()
        self._counter = 0

    def add_node(self, skill: str, inputs: list[str], metadata: dict | None = None) -> str:
        self._counter += 1
        nid = f"n:{self._counter}"
        self.g.add_node(nid, skill=skill, inputs=list(inputs),
                        metadata=dict(metadata or {}), status="pending")
        for inp in inputs:
            if inp.startswith("n:") and inp in self.g.nodes:
                self.g.add_edge(inp, nid)
        return nid

    def mark(self, nid: str, status: str) -> None:
        self.g.nodes[nid]["status"] = status

    def ready_nodes(self) -> list[str]:
        # A predecessor counts as "satisfied" when it is either complete or
        # skipped (the latter is how a Critic-fail removes a child from the
        # critical path without blocking unrelated branches downstream).
        out = []
        for nid, d in self.g.nodes(data=True):
            if d["status"] != "pending":
                continue
            preds = list(self.g.predecessors(nid))
            if all(self.g.nodes[p]["status"] in ("complete", "skipped") for p in preds):
                out.append(nid)
        return out

    def has_running(self) -> bool:
        return any(d["status"] == "running" for _, d in self.g.nodes(data=True))

    def extend_from(self, src_nid: str, result: AgentResult,
                    *, registry: SkillRegistry) -> list[str]:
        """Splice in dynamic successors, static internal_successors, and
        critic auto-insertion. Returns the list of new node ids.

        Resolves label-based input references (`n:<label>`) against the
        `metadata.label` of nodes added in the same batch. The Planner is
        encouraged to name its nodes by label so it can reference them
        without knowing the integer ids the orchestrator will hand out."""
        parent_meta = self.g.nodes[src_nid].get("metadata") or {}
        recovery_depth = parent_meta.get("recovery_depth", 0)
        added: list[str] = []
        src_def = registry.get(self.g.nodes[src_nid]["skill"])

        # Pass 1: add the new nodes; build a label → assigned-id map.
        label_to_id: dict[str, str] = {}
        pending: list[tuple[str, list[str]]] = []
        for spec in result.successors:
            label = (spec.metadata or {}).get("label")
            new_metadata = dict(spec.metadata or {})
            if recovery_depth > 0:
                new_metadata["recovery_depth"] = recovery_depth
            new_id = self.add_node(spec.skill, inputs=[],
                                   metadata=new_metadata)
            added.append(new_id)
            if isinstance(label, str) and label:
                label_to_id[label] = new_id
            pending.append((new_id, list(spec.inputs)))

        # Pass 2: resolve inputs now that every sibling has an id. Translate
        # `n:<label>` to `n:<assigned-id>` if the label matches; pass numeric
        # `n:<i>` references through; pass anything else through unchanged.
        # NOTE: an empty `raw_inputs` is now a legitimate Planner signal for
        # a fan-out worker scoped via `metadata.question` (see planner.md).
        # We do NOT substitute the parent in that case — doing so would dump
        # the parent's full output (which for the Planner contains every
        # sibling's question) back into the worker's INPUTS block and undo
        # the scoping. The structural parent edge is preserved separately
        # below so the graph topology is still correct.
        for new_id, raw_inputs in pending:
            resolved: list[str] = []
            for inp in raw_inputs:
                # `n:<label>` or `n:<int>` form (preferred).
                if inp.startswith("n:"):
                    suffix = inp[2:]
                    if suffix in label_to_id:
                        resolved.append(label_to_id[suffix])
                        continue
                    if suffix.isdigit() and inp in self.g.nodes:
                        resolved.append(inp)
                        continue
                # Bare label form — the Planner sometimes drops the n: prefix.
                elif inp in label_to_id:
                    resolved.append(label_to_id[inp])
                    continue
                # Special literal — the user query is always available.
                elif inp == "USER_QUERY":
                    resolved.append(inp)
                    continue
                # Artifact handle — pass through, the input renderer handles it.
                elif inp.startswith("art:"):
                    resolved.append(inp)
                    continue
                # Unresolvable input — fall back to the parent so the child
                # has at least one upstream dependency to wait on. This still
                # leaks the parent's output into INPUTS, but only when the
                # Planner emitted a bad input name; it is not the fan-out
                # path. A future round may want to fail loudly here instead.
                else:
                    resolved.append(src_nid)
            self.g.nodes[new_id]["inputs"] = resolved
            for inp in resolved:
                if inp.startswith("n:") and inp in self.g.nodes:
                    self.g.add_edge(inp, new_id)
            # Fan-out worker case: planner emitted inputs=[] on purpose. No
            # data dependency, but we still record the structural parent
            # edge so the executor's `ready_nodes` ordering and replay
            # topology stay coherent.
            if not raw_inputs:
                self.g.add_edge(src_nid, new_id)

        for child_skill in src_def.internal_successors:
            # Prevent double-adding if the Planner already explicitly planned this skill
            # taking input from the current source node.
            already_planned = False
            for existing_nid in self.g.nodes:
                if (self.g.nodes[existing_nid]["skill"] == child_skill 
                        and src_nid in self.g.nodes[existing_nid].get("inputs", [])):
                    already_planned = True
                    break
            if not already_planned:
                nid = self.add_node(child_skill, inputs=[src_nid])
                added.append(nid)

        # Critic auto-insertion: place a Critic before each newly-added
        # child so the child only runs after Critic passes.
        if src_def.critic and added:
            for child_nid in list(added):
                self.g.remove_edge(src_nid, child_nid)
                critic_nid = self.add_node(
                    "critic", inputs=[src_nid],
                    metadata={"target": src_nid, "child": child_nid},
                )
                self.g.add_edge(critic_nid, child_nid)
                added.append(critic_nid)

        return added


# ── Executor ─────────────────────────────────────────────────────────────────

class Executor:
    def __init__(self, registry: SkillRegistry | None = None):
        ensure_gateway()
        self.registry = registry or SkillRegistry()

    async def run(self, query: str, *, session_id: str | None = None,
                  resume: bool = False) -> str:
        sid = session_id or time.strftime("s8-%Y-%m-%d_%H-%M-%S")
        store = SessionStore(sid)
        if resume:
            existing = store.read_graph()
            if existing is None:
                raise RuntimeError(f"cannot resume {sid}: no graph.pkl on disk")
            graph_obj = existing
            graph = Graph.__new__(Graph)
            graph.g = graph_obj
            graph._counter = max(
                [int(n.split(":")[1]) for n in graph.g.nodes if n.startswith("n:")] or [0]
            )
            for _, d in graph.g.nodes(data=True):
                if d["status"] == "running":
                    d["status"] = "pending"
            if not query:
                query = store.read_query()
        else:
            store.write_query(query)
            graph = Graph()
            graph.add_node("planner", inputs=["USER_QUERY"])

        print(f"\n{'═' * 78}\nsession {sid}  ─  query: {query}\n{'═' * 78}")
        # Read memory ONCE at session start; the same hits flow into every
        # skill's prompt. The S7 contract is that every cognitive role sees
        # memory; carrying that forward verbatim here is what makes S7's
        # indexing investment continue to pay off in S8.
        memory_hits = memory_svc.read(query) or []
        if memory_hits:
            print(f"[memory.read] {len(memory_hits)} hit(s) visible to every skill this run")
        try:
            memory_svc.remember(query, source="user_query", run_id=sid)
        except Exception as e:
            print(f"[memory.remember] skipped: {e!r}")

        formatter_answer: str | None = None
        executed_count = 0
        # Per-target cap for critic-fail recovery; see P1 #5 fix below.
        recovered_branches: dict[str, bool] = {}
        # NOTES_RUNS round-3 review #5: when the cap fires, the branch is
        # skipped silently and the final answer reflects missing data with
        # no flag. Track every second-or-later critic-fail here so the
        # final log can surface it.
        critic_fail_cap_hit: list[str] = []

        while True:
            ready = graph.ready_nodes()
            if not ready and not graph.has_running():
                break
            if executed_count + len(ready) > MAX_NODES:
                print(f"[flow] node cap {MAX_NODES} hit at {executed_count}; stopping")
                break

            for nid in ready:
                graph.mark(nid, "running")
            store.write_graph(graph.g)

            outcomes = await asyncio.gather(*[self._run_one(nid, graph, sid, query, store, memory_hits)
                                              for nid in ready])

            for nid, result, prompt in outcomes:
                executed_count += 1
                graph.g.nodes[nid]["result"] = result
                graph.mark(nid, "complete" if result.success else "failed")
                store.write_node(NodeState(
                    node_id=nid, skill=graph.g.nodes[nid]["skill"],
                    status=graph.g.nodes[nid]["status"],
                    inputs=graph.g.nodes[nid]["inputs"],
                    result=result, prompt_sent=prompt,
                    started_at=time.time() - result.elapsed_s,
                    completed_at=time.time(),
                ))
                print(f"[{nid}] {graph.g.nodes[nid]['skill']:18s} "
                      f"{graph.g.nodes[nid]['status']:8s} "
                      f"({result.elapsed_s:.1f}s)"
                      + (f"  err={result.error[:80]}" if result.error else ""))

                if result.success:
                    if graph.g.nodes[nid]["skill"] == "product_shortlister":
                        print(f"\n[DEBUG] product_shortlister output for {nid}:\n{json.dumps(result.output, indent=2)}\n")
                    if graph.g.nodes[nid]["skill"] == "critic":
                        if handle_critic_verdict(nid, result, graph,
                                                 recovered_branches,
                                                 critic_fail_cap_hit):
                            continue
                        # verdict == pass: the child is now ready to run.
                    graph.extend_from(nid, result, registry=self.registry)
                    if graph.g.nodes[nid]["skill"] == "formatter":
                        fa = result.output.get("final_answer")
                        if isinstance(fa, str) and fa.strip():
                            formatter_answer = fa
                else:
                    failed_skill = graph.g.nodes[nid]["skill"]
                    failed_node_meta = graph.g.nodes[nid].get("metadata") or {}
                    parent_depth = failed_node_meta.get("recovery_depth", 0)
                    decision = plan_recovery(
                        failed_skill=failed_skill,
                        error_text=result.error or "",
                        failed_node_id=nid,
                        recovery_depth=parent_depth,
                    )
                    if decision.action == "skip":
                        print(f"  ↪ {nid} failed ({decision.reason}, "
                              f"skill={failed_skill}): {decision.note}")
                        continue
                    # action == "replan"
                    new_depth = parent_depth + 1
                    rec_nid = graph.add_node(
                        "planner", inputs=["USER_QUERY"],
                        metadata={"failure_report": decision.failure_report,
                                  "recovers": nid,
                                  "recovery_reason": decision.reason,
                                  "recovery_depth": new_depth},
                    )
                    print(f"  ↪ recovery ({decision.reason}): planner node "
                          f"{rec_nid} queued for {nid}")

            store.write_graph(graph.g)

        if formatter_answer is None:
            for nid in reversed(list(graph.g.nodes)):
                d = graph.g.nodes[nid]
                if d["status"] == "complete" and isinstance(d.get("result"), AgentResult):
                    formatter_answer = json.dumps(d["result"].output)[:2000]
                    break

        if critic_fail_cap_hit:
            # Loud surface — see review round-3 #5. Without this the cap
            # firing was invisible and the user would just see a thin
            # formatter answer with no explanation of why.
            print(f"\n[flow] WARNING: critic-fail cap hit on "
                  f"{len(critic_fail_cap_hit)} branch(es): "
                  f"{', '.join(critic_fail_cap_hit)}. "
                  f"The final answer reflects missing data from these "
                  f"branches because the Critic rejected the re-planned "
                  f"output too.")
        
        # Query gateway SQLite DB for calls logged for this session, and print them
        try:
            import sqlite3
            from pathlib import Path
            db_path = Path(__file__).resolve().parents[1] / "gateway" / "gateway_v8.db"
            if db_path.exists():
                print(f"\n{'═' * 78}\nGATEWAY DATABASE CALLS LOGGED FOR SESSION: {sid}\n{'═' * 78}")
                conn = sqlite3.connect(str(db_path))
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                rows = cursor.execute(
                    "SELECT ts, provider, model, call_role, status, error, input_tokens, output_tokens, latency_ms FROM calls WHERE session = ? ORDER BY ts ASC",
                    (sid,)
                ).fetchall()
                for r in rows:
                    dt = time.strftime("%H:%M:%S", time.localtime(r["ts"]))
                    role = r["call_role"] or "worker"
                    err = f" | err={r['error']}" if r["error"] else ""
                    print(f"[{dt}] {role.upper():12s} | {r['provider']:14s} | {r['model']:30s} | {r['status'].upper():5s} | in={r['input_tokens']} out={r['output_tokens']} ({r['latency_ms']}ms){err}")
                conn.close()
        except Exception as e:
            print(f"[flow] Failed to retrieve gateway DB logs: {e}")

        print(f"\n{'═' * 78}\nFINAL: {(formatter_answer or '')[:600]}\n{'═' * 78}\n")
        return formatter_answer or ""

    async def _run_one(self, nid: str, graph: Graph, sid: str, query: str,
                       store: SessionStore, memory_hits: list) -> tuple[str, AgentResult, str]:
        skill_name = graph.g.nodes[nid]["skill"]
        skill = self.registry.get(skill_name)
        fr = graph.g.nodes[nid].get("metadata", {}).get("failure_report")
        store.write_node(NodeState(node_id=nid, skill=skill_name, status="running",
                                   inputs=graph.g.nodes[nid]["inputs"],
                                   started_at=time.time()))
        try:
            result, prompt = await run_skill(skill, nid, graph.g.nodes, sid, query, fr,
                                             memory_hits=memory_hits)
        except Exception as e:  # pragma: no cover - dispatcher fault path
            result = AgentResult(success=False, agent_name=skill_name,
                                 error=f"exception: {type(e).__name__}: {e}")
            prompt = "(exception before prompt-render)"
        return nid, result, prompt


# ── CLI ──────────────────────────────────────────────────────────────────────



def load_queries() -> dict[str, tuple[str, str]]:
    """Load queries from queries.md.
    Returns a dict mapping the short key (e.g. 'hello', 'a', 'i')
    to a tuple of (full_heading, query_text).
    """
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "Queries and Logs" / "queries.md"
    if not path.exists():
        return {}
    
    queries = {}
    current_heading = None
    
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("## "):
            current_heading = line[3:].strip()
        elif line and current_heading:
            parts = current_heading.split(".", 1)
            if parts:
                key = parts[0].strip().lower()
                queries[key] = (current_heading, line)
            current_heading = None
            
    return queries


def main() -> None:
    from pathlib import Path
    args = sys.argv[1:]
    resume_sid: str | None = None
    if args and args[0] == "--resume":
        resume_sid = args[1] if len(args) > 1 else None
        query = " ".join(args[2:])
    else:
        query = " ".join(args)

    if not query and not resume_sid:
        queries = load_queries()
        if queries:
            sys.stderr.write("\nAvailable Reference Queries:\n")
            for key, (heading, _) in queries.items():
                sys.stderr.write(f"  [{key.upper()}] {heading}\n")
            sys.stderr.write("\nHow can I help you today? Please enter query code (e.g. hello, A, I) or custom query: ")
            sys.stderr.flush()
            user_input = sys.stdin.readline().strip()

            # Normalize inputs
            norm_input = user_input.lower().replace(".", "").strip()

            match_key = None
            if norm_input in queries:
                match_key = norm_input
            else:
                matches = [k for k in queries if k.startswith(norm_input)]
                if len(matches) == 1:
                    match_key = matches[0]

            if match_key:
                heading, query_text = queries[match_key]
                log_dir = Path(__file__).resolve().parents[1] / "Queries and Logs"
                log_dir.mkdir(exist_ok=True)
                base_path = log_dir / f"{heading}.log"
                log_path = base_path
                version = 1
                while log_path.exists():
                    log_path = log_dir / f"{heading}_v{version}.log"
                    version += 1

                sys.stderr.write(f"\n[logger] Running selected query and saving log to: {log_path.name}\n")
                sys.stderr.flush()

                # Create/truncate the file in write mode first
                with open(log_path, "w", encoding="utf-8") as f:
                    pass

                # We redirect at the OS file descriptor level (FD 1 and 2)
                # to catch subprocesses, crawlers, and native C libs.
                import os
                import threading

                # Dup original stdout/stderr FDs
                orig_stdout_fd = os.dup(1)
                orig_stderr_fd = os.dup(2)

                # Open log file for appending
                log_file = open(log_path, "a", encoding="utf-8")

                # Create pipes for redirecting stdout and stderr
                stdout_pipe_r, stdout_pipe_w = os.pipe()
                stderr_pipe_r, stderr_pipe_w = os.pipe()

                os.dup2(stdout_pipe_w, 1)
                os.dup2(stderr_pipe_w, 2)

                os.close(stdout_pipe_w)
                os.close(stderr_pipe_w)

                stop_event = threading.Event()

                def forward_loop(pipe_r, orig_fd):
                    while not stop_event.is_set():
                        try:
                            # Read chunks of data
                            data = os.read(pipe_r, 4096)
                            if not data:
                                break
                            # Write to original terminal FD
                            os.write(orig_fd, data)
                            # Write to the log file
                            log_file.write(data.decode("utf-8", errors="replace"))
                            log_file.flush()
                        except Exception:
                            break

                t1 = threading.Thread(target=forward_loop, args=(stdout_pipe_r, orig_stdout_fd), daemon=True)
                t2 = threading.Thread(target=forward_loop, args=(stderr_pipe_r, orig_stderr_fd), daemon=True)
                t1.start()
                t2.start()

                try:
                    asyncio.run(Executor().run(query_text))
                finally:
                    # Restore original FDs
                    os.dup2(orig_stdout_fd, 1)
                    os.dup2(orig_stderr_fd, 2)
                    os.close(orig_stdout_fd)
                    os.close(orig_stderr_fd)
                    
                    # Close read pipes to stop threads
                    stop_event.set()
                    try:
                        os.close(stdout_pipe_r)
                    except OSError:
                        pass
                    try:
                        os.close(stderr_pipe_r)
                    except OSError:
                        pass
                    
                    t1.join(timeout=1.0)
                    t2.join(timeout=1.0)
                    log_file.close()
                return
            else:
                query = user_input
        else:
            sys.stderr.write("How can I help you today? Please enter your query: ")
            sys.stderr.flush()
            query = sys.stdin.readline().strip()

    if not query and not resume_sid:
        return

    asyncio.run(Executor().run(query, session_id=resume_sid, resume=bool(resume_sid)))


if __name__ == "__main__":
    main()
