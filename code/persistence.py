"""Session 8 on-disk persistence for the growing graph.

Lives in its own file because flow.py needs to stay under 350 lines.
The two surfaces:

  - SessionStore: per-session directory under state/sessions/<sid>/.
    Owns reading and writing the graph pickle and the per-node JSON
    files. Atomic-write semantics (write to tmp, rename) so a SIGKILL
    mid-write does not corrupt the last successful snapshot.
  - rebuild_graph_state(): given a populated SessionStore, returns the
    list of NodeState records sorted by completion time so replay.py
    can walk them in order.

The Graph itself (the NetworkX wrapping) lives in flow.py.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import networkx as nx

from schemas import AgentResult, NodeState

SESSIONS_ROOT = Path(__file__).parent / "state" / "sessions"


class SessionLoadError(RuntimeError):
    """Raised when a persisted session cannot be safely loaded.

    Examples: a NodeState file that no longer matches the schema, a
    `_result_typed` payload that cannot round-trip back into an
    AgentResult. We fail loud here rather than silently degrade — the
    Executor's downstream code does `isinstance(..., AgentResult)`
    checks, and stashing a dict where it expects a Pydantic model is
    exactly the silent-degradation pattern review round-3 #4 flagged."""


def _atomic_write(path: Path, data: bytes | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    mode = "wb" if isinstance(data, bytes) else "w"
    with open(tmp, mode) as f:
        f.write(data)
    os.replace(tmp, path)


class SessionStore:
    """One on-disk session. Layout:

        state/sessions/<sid>/
            graph.pkl              # NetworkX DiGraph pickle
            query.txt              # the user's verbatim query
            nodes/
                n_001.json         # NodeState for the n:1 node, etc.
                n_002.json
                ...
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.dir = SESSIONS_ROOT / session_id
        self.nodes_dir = self.dir / "nodes"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.nodes_dir.mkdir(parents=True, exist_ok=True)

    @property
    def query_path(self) -> Path:
        return self.dir / "query.txt"

    @property
    def graph_path(self) -> Path:
        # P1 #6: graph is persisted as JSON via nx.node_link_data so the file
        # is `cat`-able by students and the format survives a Python upgrade.
        return self.dir / "graph.json"

    @property
    def _legacy_graph_path(self) -> Path:
        # Older sessions wrote pickle; the loader tolerates that for resume
        # on pre-fix sessions but the writer always emits JSON now.
        return self.dir / "graph.pkl"

    def write_query(self, query: str) -> None:
        _atomic_write(self.query_path, query)

    def read_query(self) -> str:
        if not self.query_path.exists():
            return ""
        return self.query_path.read_text()

    def write_graph(self, graph_obj: nx.DiGraph) -> None:
        """Serialise the DiGraph to JSON via nx.node_link_data. Per-node
        `result` is an AgentResult (Pydantic) — dump it to a dict so the
        JSON encoder is happy. Reviving on read restores the Pydantic shape.
        """
        # node_link_data accepts arbitrary node-attr dicts; we just need
        # every value to be JSON-serialisable.
        h = nx.DiGraph()
        for n, d in graph_obj.nodes(data=True):
            attrs = dict(d)
            if isinstance(attrs.get("result"), AgentResult):
                attrs["result"] = attrs["result"].model_dump(mode="json")
                attrs["_result_typed"] = True
            h.add_node(n, **attrs)
        for u, v, d in graph_obj.edges(data=True):
            h.add_edge(u, v, **d)
        payload = nx.node_link_data(h, edges="edges")
        _atomic_write(self.graph_path, json.dumps(payload, indent=2, default=str))
        try:
            self._write_graph_html(payload)
        except Exception as e:
            import sys
            print(f"[persistence] WARNING: failed to write graph.html: {e}", file=sys.stderr)

    def _write_graph_html(self, payload: dict) -> None:
        query = self.read_query() or "Unknown Query"
        skill_colors = {
            "planner": {"background": "#1b4f72", "border": "#2874a6", "color": "#ffffff"},
            "researcher": {"background": "#0e6251", "border": "#148f77", "color": "#ffffff"},
            "formatter": {"background": "#5b2c6f", "border": "#884ea0", "color": "#ffffff"},
            "coder": {"background": "#7e5109", "border": "#b9770e", "color": "#ffffff"},
            "sandbox_executor": {"background": "#2e4053", "border": "#5d6d7e", "color": "#ffffff"},
            "critic": {"background": "#78281f", "border": "#b03a2e", "color": "#ffffff"},
            "retriever": {"background": "#145a32", "border": "#1e8449", "color": "#ffffff"},
            "summariser": {"background": "#7d6608", "border": "#d4ac0d", "color": "#ffffff"},
            "distiller": {"background": "#1f1f2e", "border": "#4d4d70", "color": "#ffffff"},
        }
        default_colors = {"background": "#2c3e50", "border": "#34495e", "color": "#ffffff"}

        vis_nodes = []
        for node in payload.get("nodes", []):
            nid = node.get("id")
            skill = node.get("skill")
            status = node.get("status")
            colors = skill_colors.get(skill, default_colors)
            label = f"ID: {nid}\nSkill: {skill}\nStatus: {status}"
            vis_nodes.append({
                "id": nid,
                "label": label,
                "color": colors,
                "shape": "box"
            })

        vis_edges = []
        for edge in payload.get("edges", []):
            vis_edges.append({
                "from": edge.get("source"),
                "to": edge.get("target")
            })

        legend_html = ""
        for skill, colors in skill_colors.items():
            legend_html += f"""
            <div class="legend-item">
                <div class="legend-color" style="background-color: {colors['background']}; border-color: {colors['border']};"></div>
                <span>{skill}</span>
            </div>"""

        html_template = """<!DOCTYPE html>
<html>
<head>
    <title>DAG Session Visualization</title>
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style type="text/css">
        body {{
            background-color: #121212;
            color: #e0e0e0;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            display: flex;
            flex-direction: column;
            height: 100vh;
            box-sizing: border-box;
        }}
        h2 {{
            margin-top: 0;
            color: #ffffff;
            border-bottom: 1px solid #333;
            padding-bottom: 10px;
            margin-bottom: 15px;
        }}
        .query-container {{
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 15px;
            font-size: 14px;
            line-height: 1.5;
            border-left: 4px solid #1b4f72;
        }}
        .query-label {{
            font-weight: bold;
            color: #888888;
            margin-bottom: 4px;
            text-transform: uppercase;
            font-size: 11px;
            letter-spacing: 0.8px;
        }}
        #mynetwork {{
            height: calc(100vh - 280px);
            min-height: 400px;
            width: 100%;
            border: 1px solid #333;
            background-color: #1e1e1e;
            border-radius: 8px;
        }}
        .legend {{
            display: flex;
            gap: 15px;
            margin-bottom: 15px;
            flex-wrap: wrap;
            padding: 10px;
            background: #1a1a1a;
            border-radius: 8px;
            border: 1px solid #333;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 5px;
            font-size: 12px;
        }}
        .legend-color {{
            width: 15px;
            height: 15px;
            border-radius: 3px;
            border: 1px solid;
        }}
    </style>
</head>
<body>
    <h2>DAG Session Visualization: {session_id}</h2>
    <div class="query-container">
        <div class="query-label">Session Query</div>
        <div>{query}</div>
    </div>
    <div class="legend">
        {legend_html}
    </div>
    <div id="mynetwork"></div>

    <script type="text/javascript">
        const nodes = new vis.DataSet({nodes_json});
        const edges = new vis.DataSet({edges_json});

        const container = document.getElementById('mynetwork');
        const data = {{ nodes: nodes, edges: edges }};
        const options = {{
            layout: {{
                hierarchical: {{
                    enabled: true,
                    direction: 'LR',
                    sortMethod: 'directed',
                    nodeSpacing: 150,
                    levelSeparation: 250
                }}
            }},
            nodes: {{
                shape: 'box',
                margin: 10,
                font: {{
                    face: 'monospace',
                    size: 14,
                    color: '#ffffff'
                }},
                borderWidth: 2,
                shadow: true
            }},
            edges: {{
                arrows: {{
                    to: {{ enabled: true, scaleFactor: 1 }}
                }},
                color: {{
                    color: '#848484',
                    highlight: '#ffffff',
                    hover: '#ffffff'
                }},
                width: 2,
                shadow: true
            }}
        }};
        
        const network = new vis.Network(container, data, options);
    </script>
</body>
</html>
"""
        html_content = html_template.format(
            session_id=self.session_id,
            query=query,
            nodes_json=json.dumps(vis_nodes),
            edges_json=json.dumps(vis_edges),
            legend_html=legend_html
        )
        html_path = self.dir / "graph.html"
        _atomic_write(html_path, html_content)


    def read_graph(self) -> nx.DiGraph | None:
        if self.graph_path.exists():
            payload = json.loads(self.graph_path.read_text())
            g = nx.node_link_graph(payload, edges="edges", directed=True)
            # NOTES_RUNS round-3 review #4: a write tagged a node's `result`
            # as a typed AgentResult via `_result_typed`. If the dict no
            # longer round-trips through AgentResult.model_validate, that
            # is silent data corruption — the previous "keep the dict, let
            # downstream isinstance checks handle it" was exactly the
            # silent-degradation pattern we just fixed in P0 #2.
            # Raise instead; the SessionLoadError surfaces the bad file path
            # and the validation message so the operator can act on it.
            for nid, d in g.nodes(data=True):
                if d.pop("_result_typed", False) and isinstance(d.get("result"), dict):
                    try:
                        d["result"] = AgentResult.model_validate(d["result"])
                    except (ValueError, TypeError) as e:
                        raise SessionLoadError(
                            f"node {nid} in {self.graph_path}: persisted "
                            f"AgentResult failed model_validate. The graph "
                            f"is unsafe to resume — inspect the file and "
                            f"either repair it or delete the session. "
                            f"validation error: {type(e).__name__}: {e}"
                        ) from e
            return g
        # Backwards-compat: tolerate sessions written by the pre-P1 pickle
        # path. We import pickle lazily so the dependency is only paid when
        # someone resumes a legacy session.
        if self._legacy_graph_path.exists():
            import pickle, sys
            print(f"[persistence] reading legacy pickle graph from "
                  f"{self._legacy_graph_path}", file=sys.stderr)
            return pickle.loads(self._legacy_graph_path.read_bytes())
        return None

    def _node_path(self, node_id: str) -> Path:
        # node_id is like "n:1" — turn that into n_001.json so directory
        # listings sort sensibly.
        try:
            i = int(node_id.split(":", 1)[1])
            return self.nodes_dir / f"n_{i:03d}.json"
        except (IndexError, ValueError):
            safe = node_id.replace(":", "_").replace("/", "_")
            return self.nodes_dir / f"{safe}.json"

    def write_node(self, state: NodeState) -> None:
        _atomic_write(self._node_path(state.node_id), state.model_dump_json(indent=2))

    def read_node(self, node_id: str) -> NodeState | None:
        p = self._node_path(node_id)
        if not p.exists():
            return None
        return NodeState.model_validate_json(p.read_text())

    def read_all_nodes(self) -> list[NodeState]:
        """Load every persisted NodeState in this session. Corrupt or
        partially-written files (the typical cause is a process kill between
        the temp-file write and the atomic rename) are skipped with a clear
        warning to stderr — never silently dropped. NOTES_RUNS feedback
        P0 #2: a bare `except Exception: continue` here was killing resume
        invisibly when one node file was bad."""
        import sys
        states: list[NodeState] = []
        for p in sorted(self.nodes_dir.glob("n_*.json")):
            try:
                states.append(NodeState.model_validate_json(p.read_text()))
            except (OSError, ValueError) as e:
                # OSError = unreadable; ValueError covers JSON decode +
                # Pydantic ValidationError (which inherits ValueError).
                print(f"[persistence] WARNING: skipped corrupt node file "
                      f"{p}: {type(e).__name__}: {e}", file=sys.stderr)
        return states


def list_sessions() -> list[str]:
    if not SESSIONS_ROOT.exists():
        return []
    return sorted(p.name for p in SESSIONS_ROOT.iterdir() if p.is_dir())
