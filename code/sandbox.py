"""Subprocess Python runner used by the sandbox_executor skill.

What it is. A small wrapper around `subprocess.run` that lets the Coder
skill's output be executed against a controlled environment so the
sandbox_executor can return stdout, stderr, exit code, and any files
written. Captures are bounded by wall-clock and output-size caps.

What it is NOT. This is not OS-level isolation. There is no chroot, no
container, no syscall filter, no FS allowlist beyond cwd. A malicious
script can read /etc and call out to the network. The sandbox is a
USABILITY boundary — it keeps a runaway loop or noisy print from
poisoning the orchestrator's stdout — not a SECURITY boundary. Students
who need real isolation should reach for Firejail or a container
runtime; that path is correctly outside Session 8's scope.

Returns a dict the sandbox_executor skill can pack into
AgentResult.output unchanged.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_TIMEOUT_S = 30
DEFAULT_STDOUT_CAP = 1_000_000  # 1 MB
DEFAULT_STDERR_CAP = 1_000_000  # 1 MB

# Env vars carried into the child by default. Everything else gets dropped.
# PATH is kept so the child can find `python3` etc.; HOME so libraries that
# look for ~ don't crash. Nothing else by default.
DEFAULT_ENV_WHITELIST = ("PATH", "HOME", "LANG", "LC_ALL", "LC_CTYPE")


def _truncate(b: bytes, cap: int) -> tuple[str, bool]:
    if len(b) <= cap:
        return b.decode("utf-8", errors="replace"), False
    head = b[: max(0, cap - 200)].decode("utf-8", errors="replace")
    return head + f"\n...[truncated; {len(b) - cap + 200} more bytes]...", True


def run_python(
    code: str,
    *,
    timeout_s: int = DEFAULT_TIMEOUT_S,
    stdout_cap: int = DEFAULT_STDOUT_CAP,
    stderr_cap: int = DEFAULT_STDERR_CAP,
    env_whitelist: tuple[str, ...] = DEFAULT_ENV_WHITELIST,
    extra_env: dict[str, str] | None = None,
) -> dict:
    """Execute `code` in a subprocess. Returns a dict shaped for
    AgentResult.output:

        {
          "exit_code": int,
          "stdout": str,             # decoded, possibly truncated
          "stdout_truncated": bool,
          "stderr": str,
          "stderr_truncated": bool,
          "files_written": [{"name": str, "size_bytes": int}, ...],
          "timed_out": bool,
          "cwd": str,                # the temp dir, kept for the artifact pipeline
        }
    """
    # Explicit sandbox environment variables 
    default_env = {
        "PATH": "/usr/bin:/bin:/usr/local/bin",
        "HOME": "/home/sandbox",
        "LANG": "en_US.UTF-8",
        "LC_ALL": "C.UTF-8",
        "LC_CTYPE": "en_US.UTF-8",
    }
    
    # Start with explicit defaults, then update with any system whitelisted values if they exist
    scrubbed = dict(default_env)
    for k in env_whitelist:
        if k in os.environ:
            scrubbed[k] = os.environ[k]
            
    if extra_env:
        scrubbed.update(extra_env)

    # Use dedicated sandbox directory relative to the current file (code/sandbox)
    sandbox_dir = Path(__file__).resolve().parent / "sandbox"
    sandbox_dir.mkdir(exist_ok=True)
    
    # Clean up existing files in the sandbox directory to ensure clean run
    for p in sandbox_dir.iterdir():
        try:
            if p.is_file() or p.is_symlink():
                p.unlink()
            elif p.is_dir():
                import shutil
                shutil.rmtree(p)
        except Exception:
            pass

    cwd = str(sandbox_dir)
    script_path = sandbox_dir / "main.py"
    script_path.write_text(code, encoding="utf-8")

    timed_out = False
    try:
        cp = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=cwd,
            env=scrubbed,
            input=b"",
            capture_output=True,
            timeout=timeout_s,
        )
        stdout_b, stderr_b = cp.stdout, cp.stderr
        exit_code = cp.returncode
    except subprocess.TimeoutExpired as te:
        timed_out = True
        stdout_b = te.stdout or b""
        stderr_b = (te.stderr or b"") + f"\n[sandbox] killed after {timeout_s}s wall-clock".encode()
        exit_code = -1

    stdout_txt, so_trunc = _truncate(stdout_b, stdout_cap)
    stderr_txt, se_trunc = _truncate(stderr_b, stderr_cap)

    files = []
    for p in sorted(sandbox_dir.iterdir()):
        if p.name == "main.py":
            continue
        try:
            files.append({"name": p.name, "size_bytes": p.stat().st_size})
        except OSError:
            continue

    return {
        "exit_code": exit_code,
        "stdout": stdout_txt,
        "stdout_truncated": so_trunc,
        "stderr": stderr_txt,
        "stderr_truncated": se_trunc,
        "files_written": files,
        "timed_out": timed_out,
        "cwd": cwd,
    }
