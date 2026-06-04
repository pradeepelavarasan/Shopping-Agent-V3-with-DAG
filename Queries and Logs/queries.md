# Session 8 queries to test

## hello
Say hello.

<!--
Comments:
- Sanity check to test the minimum DAG.
- Structure: Two nodes (Planner -> Formatter).
- Wall-clock time is expected to be under three seconds.
- The Planner's prompt allows this shape since the query needs neither research nor structure; Formatter is the appropriate terminal.
-->

## A. Shannon Wikipedia
Fetch https://en.wikipedia.org/wiki/Claude_Shannon and tell me his birth date, death date, and three key contributions to information theory.

<!--
Comments:
- S7 carryover query to verify graph orchestrator handles sequential dependencies without regression.
- Structure: Four nodes (Planner -> Researcher -> Distiller -> Formatter).
- Critic is auto-inserted between the Distiller and Formatter (verdict: pass).
- Researcher executes fetch_url tool to crawl the Wikipedia page.
-->

## I. Three city populations
Find the populations of London, Paris, Berlin and tell me which two are closest in size.

<!--
Comments:
- Exercises parallel fan-out capabilities.
- Structure: Seven nodes (Planner -> 3 parallel Researchers -> Coder -> Formatter + SandboxExecutor).
- Demonstrates massive token and latency improvements over Session 7 loop architecture.
-->

## J. Graceful failure
Read /nonexistent/path.txt and tell me what's in it.

<!--
Comments:
- Graceful failure test case.
- Structure: Two nodes (Planner -> Formatter).
- The Planner immediately identifies that the file does not exist, shortcuts the process, and outputs a failure note directly to the Formatter. No tool is executed.
-->

## K. Resumable execution
For Lagos, Cairo, and Kinshasa, find current populations and growth rates and tell me which is growing fastest.

<!--
Comments:
- Resumable execution test case.
- Can be killed mid-flow (e.g. during parallel Researcher phase) and resumed with:
  uv run flow.py --resume <session_id>
- The graph file (graph.pkl) will persist state, resetting any "running" node to "pending" to complete the flow gracefully upon resume.
- Expected outcome: Lagos is growing fastest at approx 3.78%.
-->