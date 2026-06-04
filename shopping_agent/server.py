import json
import re
import sys
import subprocess
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, HTTPServer

PORT = 8000
ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent

class ShoppingAgentHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        # Serve index.html for root path
        if self.path == "/" or self.path == "/index.html":
            file_path = ROOT / "index.html"
            self.serve_file(file_path, "text/html")
        # Serve static files from static directory
        elif self.path.startswith("/static/"):
            rel_path = self.path[8:]
            file_path = ROOT / "static" / rel_path
            
            # Determine content type
            content_type = "application/octet-stream"
            if file_path.suffix == ".css":
                content_type = "text/css"
            elif file_path.suffix == ".js":
                content_type = "application/javascript"
            elif file_path.suffix in (".png", ".jpg", ".jpeg"):
                content_type = f"image/{file_path.suffix[1:]}"
                
            self.serve_file(file_path, content_type)
        else:
            self.send_error(404, "Not Found")

    def serve_file(self, file_path, content_type):
        if not file_path.exists() or file_path.is_dir():
            self.send_error(404, "File Not Found")
            return
        
        try:
            content = file_path.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, f"Internal Server Error: {e}")

    def do_POST(self):
        if self.path == "/api/search":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            req = json.loads(post_data.decode('utf-8'))
            query = req.get('query', '').strip()

            if not query:
                self.send_error_response("Empty query received.")
                return

            try:
                # Load system prompt
                sys_prompt_path = ROOT / "shopping_system_prompt.txt"
                sys_prompt = sys_prompt_path.read_text(encoding="utf-8") if sys_prompt_path.exists() else ""

                # Build combined query
                combined_query = f"{sys_prompt}\n\nUser Query: {query}"

                # Invoke flow.py in a subprocess from PROJECT_ROOT using the .venv python directly
                # to avoid uv lock sync delays
                python_bin = PROJECT_ROOT / ".venv" / "bin" / "python"
                if not python_bin.exists():
                    python_bin = PROJECT_ROOT / "code" / ".venv" / "bin" / "python"
                if not python_bin.exists():
                    # Fallback to sys.executable if .venv python is missing
                    python_bin = Path(sys.executable)

                print(f"[server] Invoking DAG executor for query: {query}")
                result = subprocess.run(
                    [str(python_bin), "code/flow.py", combined_query],
                    cwd=str(PROJECT_ROOT),
                    capture_output=True,
                    text=True,
                    encoding="utf-8"
                )

                stdout_text = result.stdout
                print(stdout_text)
                if result.stderr:
                    print(result.stderr, file=sys.stderr)

                # Find session ID in stdout (format is usually: session s8-YYYY-MM-DD_HH-MM-SS or s8-<8-char-hex>)
                session_match = re.search(r"session (s8-[\w\d_-]+)", stdout_text)
                if not session_match:
                    self.send_error_response("Could not identify the orchestrator session ID from output.")
                    return

                session_id = session_match.group(1)
                print(f"[server] Identified session ID: {session_id}")

                # Read graph.json for this session
                graph_path = PROJECT_ROOT / "code" / "state" / "sessions" / session_id / "graph.json"
                if not graph_path.exists():
                    self.send_error_response(f"Session graph file not found on disk at {graph_path}")
                    return

                with open(graph_path, "r", encoding="utf-8") as f:
                    graph_data = json.load(f)

                # Locate formatter node
                formatter_node = None
                for node in graph_data.get("nodes", []):
                    if node.get("skill") == "formatter" and node.get("status") == "complete":
                        formatter_node = node
                        break

                if not formatter_node:
                    self.send_error_response("The DAG execution did not complete the Formatter node successfully.")
                    return

                # Get final answer output.
                # The formatter may output either:
                #   (a) {"final_answer": "<json-string or plain text>"}  — old schema
                #   (b) {"products": [...], "analysis": {...}}            — direct schema
                formatter_output = formatter_node.get("result", {}).get("output", {})
                final_answer = formatter_output.get("final_answer", "")

                # Case (b): formatter wrote products+analysis directly into output
                if not final_answer and "products" in formatter_output:
                    self.send_success_response(formatter_output)
                    return

                if not final_answer:
                    self.send_error_response("Formatter output is empty.")
                    return

                # Case (a-i): final_answer is already a parsed dict
                if isinstance(final_answer, dict):
                    self.send_success_response(final_answer)
                    return

                # Case (a-ii): final_answer is a JSON string — parse it
                try:
                    # Clean up if markdown fences were added
                    cleaned_answer = final_answer.strip()
                    if cleaned_answer.startswith("```"):
                        cleaned_answer = cleaned_answer.strip("`").strip()
                        if cleaned_answer.startswith("json"):
                            cleaned_answer = cleaned_answer[4:].strip()

                    # Remove any leading/trailing characters that are not part of the JSON object
                    start_idx = cleaned_answer.find("{")
                    end_idx = cleaned_answer.rfind("}")
                    if start_idx != -1 and end_idx != -1:
                        cleaned_answer = cleaned_answer[start_idx:end_idx+1]

                    parsed_response = json.loads(cleaned_answer)
                    self.send_success_response(parsed_response)
                except json.JSONDecodeError as je:
                    print(f"[server] JSON Decode Error: {je}")
                    self.send_error_response("The agent output was not valid JSON: " + final_answer)

            except Exception as e:
                self.send_error_response(f"Server error: {e}")
        else:
            self.send_error(404, "Not Found")

    def send_success_response(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def send_error_response(self, message):
        self.send_response(500)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode('utf-8'))

def run_server():
    server = HTTPServer(('127.0.0.1', PORT), ShoppingAgentHandler)
    print(f"Server running at http://localhost:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        server.server_close()

if __name__ == "__main__":
    run_server()
