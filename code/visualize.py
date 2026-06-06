import json
import sys
from pathlib import Path

SKILL_COLORS = {
    "planner": {"background": "#1b4f72", "border": "#2874a6", "color": "#ffffff"},
    "researcher": {"background": "#0e6251", "border": "#148f77", "color": "#ffffff"},
    "formatter": {"background": "#5b2c6f", "border": "#884ea0", "color": "#ffffff"},
    "coder": {"background": "#7e5109", "border": "#b9770e", "color": "#ffffff"},
    "sandbox_executor": {"background": "#2e4053", "border": "#5d6d7e", "color": "#ffffff"},
    "critic": {"background": "#78281f", "border": "#b03a2e", "color": "#ffffff"},
    "retriever": {"background": "#145a32", "border": "#1e8449", "color": "#ffffff"},
    "summariser": {"background": "#7d6608", "border": "#d4ac0d", "color": "#ffffff"},
    "distiller": {"background": "#1f1f2e", "border": "#4d4d70", "color": "#ffffff"},
    "product_shortlister": {"background": "#1a5276", "border": "#2980b9", "color": "#ffffff"},
    "product_analyst": {"background": "#1d6a39", "border": "#27ae60", "color": "#ffffff"},
    "product_recommendation": {"background": "#6e2f8f", "border": "#9b59b6", "color": "#ffffff"},
}
DEFAULT_COLORS = {"background": "#2c3e50", "border": "#34495e", "color": "#ffffff"}

HTML_TEMPLATE = """<!DOCTYPE html>
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

def generate_visualization(session_id: str) -> None:
    session_dir = Path(__file__).resolve().parent / "state" / "sessions" / session_id
    graph_path = session_dir / "graph.json"
    query_path = session_dir / "query.txt"
    
    if not graph_path.exists():
        print(f"Error: {graph_path} does not exist.")
        sys.exit(1)
        
    query = query_path.read_text(encoding="utf-8").strip() if query_path.exists() else "Unknown Query"
        
    with open(graph_path, "r", encoding="utf-8") as f:
        graph_data = json.load(f)
        
    vis_nodes = []
    for node in graph_data.get("nodes", []):
        nid = node.get("id")
        skill = node.get("skill")
        status = node.get("status")
        
        colors = SKILL_COLORS.get(skill, DEFAULT_COLORS)
        
        label = f"ID: {nid}\nSkill: {skill}\nStatus: {status}"
        metadata = node.get("metadata") or {}
        recovery_depth = metadata.get("recovery_depth", 0)
        if recovery_depth > 0:
            label += f"\nDepth: {recovery_depth}"
        recovery_reason = metadata.get("recovery_reason")
        if recovery_reason:
            label += f"\nReason: {recovery_reason}"

        vis_nodes.append({
            "id": nid,
            "label": label,
            "color": colors,
            "shape": "box"
        })
        
    vis_edges = []
    for edge in graph_data.get("edges", []):
        vis_edges.append({
            "from": edge.get("source"),
            "to": edge.get("target")
        })
        
    # Generate Legend
    legend_html = ""
    for skill, colors in SKILL_COLORS.items():
        legend_html += f"""
        <div class="legend-item">
            <div class="legend-color" style="background-color: {colors['background']}; border-color: {colors['border']};"></div>
            <span>{skill}</span>
        </div>"""
        
    html_content = HTML_TEMPLATE.format(
        session_id=session_id,
        query=query,
        nodes_json=json.dumps(vis_nodes),
        edges_json=json.dumps(vis_edges),
        legend_html=legend_html
    )
    
    output_path = session_dir / "graph.html"
    output_path.write_text(html_content, encoding="utf-8")
    print(f"Successfully generated visualizer page: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python visualize.py <session_id>")
        sys.exit(1)
    generate_visualization(sys.argv[1])
