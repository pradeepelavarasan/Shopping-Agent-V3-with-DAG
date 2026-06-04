# Shopping Agent V3 using DAG (Directed Acyclic Graph)

A production-grade, multi-agent shopping agent orchestrated via a Directed Acyclic Graph (DAG) system. This architecture upgrades from a single-loop sequential execution model to a dynamic, concurrent skill executor. Specialized nodes (Planner, Shortlister, Coder, SandboxExecutor, Analyst, Recommendation, Formatter) run in parallel using `asyncio.gather` for maximum speed and token efficiency.

> **Demo Video**: Watch the Shopping Agent V3 in action, scraping, analyzing, and formatting recommendations: [YouTube Demo Link](https://youtu.be/vPosAeuZ4Pc) (Placeholder for demo video link)

```mermaid
flowchart TD
    UserQuery[User Query: "computer mouse"] --> Planner[Planner Node]
    Planner --> Shortlister[Product Shortlister Node: Stealth Scraper]
    Shortlister --> Coder[Coder Node: Code Gen]
    Coder --> Sandbox[Sandbox Executor Node: Subprocess Runner]
    Sandbox --> AnalystA[Product Analyst A: Deep Scraper & Evaluator]
    Sandbox --> AnalystB[Product Analyst B: Deep Scraper & Evaluator]
    Sandbox --> AnalystC[Product Analyst C: Deep Scraper & Evaluator]
    AnalystA --> Recommendation[Product Recommendation Node]
    AnalystB --> Recommendation
    AnalystC --> Recommendation
    Recommendation --> Formatter[Formatter Node: Output Merger]
    Formatter --> FinalJSON[Final Recommendation JSON Output]

    style Planner fill:#1f2d3d,stroke:#3b82f6,stroke-width:2px;
    style Shortlister fill:#1f2d3d,stroke:#10b981,stroke-width:2px;
    style Sandbox fill:#1f2d3d,stroke:#f59e0b,stroke-width:2px;
    style AnalystA fill:#1f2d3d,stroke:#8b5cf6,stroke-width:2px;
    style AnalystB fill:#1f2d3d,stroke:#8b5cf6,stroke-width:2px;
    style AnalystC fill:#1f2d3d,stroke:#8b5cf6,stroke-width:2px;
    style Formatter fill:#2e1065,stroke:#ec4899,stroke-width:2px;
```

---

## The Paradigm Shift: From Single-Loop to DAG Orchestration

In previous iterations (like Session 7 RAG), agentic workflows were bound by a **single iterating loop**: one perception call, one decision call, and one action dispatch per iteration. 

This serial execution pattern severely bottlenecks execution:
* **Latency Penalty**: Parallelizable requests (e.g., analyzing multiple products or fetching distinct URLs) are serialized. A multi-item search query takes 11 iterations and 125 seconds.
* **Token Bloat**: Each loop iteration accumulates redundant prompt histories, causing the input token footprint to skyrocket (~54,000 input tokens).

### Session 8 DAG Optimization Results

By transitioning orchestration to a **Directed Acyclic Graph (DAG)** where tasks are independent skills executing concurrently under `asyncio.gather`, we achieve substantial gains:

| Metric | Sequential Agent Loop (Session 7) | Dynamic DAG Orchestrator (Session 8) | Performance Gain |
| :--- | :--- | :--- | :--- |
| **Wall-Clock Execution Time** | ~125 seconds | **~62 seconds** | **~50.4% Latency Reduction** |
| **Input Token Consumption** | ~54,000 tokens | **~17,000 tokens** | **~68.5% Cost Reduction** |
| **Concurrency Model** | Sequential Loops (blocking) | Concurrent Coroutines (`asyncio.gather`) | Multi-threaded Branching |

---

## Shopping Agent V3 Architecture Under the Hood

The Shopping Agent V3 executes in three distinct, highly optimized phases:

### Phase 1: Product Shortlisting (Stealth Listing Scraper)
* The **Planner** receives the user query and compiles a DAG.
* The **Product Shortlister** is triggered. It uses a stealth-configured **Playwright** headless browser to fetch the Amazon search results page.
* It parses the HTML structure dynamically, bypassing bot detection, to extract the top 10 organic candidates.
* It collects product ASINs, titles, ratings, reviews count, and listing detail URLs.
* **Price & Currency Integrity**: Prices are harvested natively (preserving the original currency, e.g., Indian Rupees `₹` or `INR` from `amazon.in`). The system strictly forbids converting or mutating the price.

### Phase 2: Dynamic Code Generation & Sandbox Execution
* The **Coder** node analyzes the shortlister's products. It dynamically writes custom Python scripts to sanitize, filter, or rank the items.
* **Dynamic Node Extensions**: In `agent_config.yaml`, the coder declares `internal_successors: [sandbox_executor]`. When the Coder completes, the orchestrator automatically appends the **SandboxExecutor** to the active graph.
* The **SandboxExecutor** runs the Python script in a secure subprocess environment, capturing stdout and returning cleaned data.

### Phase 3: Parallel Product Analysis & Recommendation
* Using the sandbox outputs, the executor spawns **three parallel Product Analyst nodes** concurrently—one for each of the top three products.
* **Deep Scraping**: Each Product Analyst fetches the specific product's detail page to retrieve high-resolution product image URLs. This avoids fetching large image payloads for all candidates during Phase 1.
* **Evaluation Matrix**: The analysts evaluate the products across five core dimensions:
  1. **Customer Sentiment** (Positive/Neutral/Negative)
  2. **Reliability**
  3. **Value For Money**
  4. **Feature Completeness**
  5. **Build Quality**
* The **Product Recommendation** node aggregates these reports, selects the top-rated item, and drafts an overall executive summary.
* The **Formatter** (terminal node) parses the query constraints and merges all metrics into a final, valid JSON matching the target schema.

---

## Tested Queries & Results

*(To be showcased by the user)*

---

## Quickstart

### Prerequisites
* Python 3.11+
* [uv](https://docs.astral.sh/uv/) package manager
* Ollama (`brew install ollama` and `ollama pull nomic-embed-text` for vector search indexing)
* Playwright browsers (`uv run playwright install`)

### Setup and Install
1. **Configure Environment Secrets**:
   ```bash
   cp .env.example .env
   # Open .env and add your LLM provider API keys
   ```

2. **Sync Dependencies**:
   ```bash
   cd gateway && uv sync && cd ..
   cd code && uv sync && cd ..
   ```

3. **Start the FastAPI Model Gateway** (Terminal 1):
   ```bash
   cd gateway && uv run main.py
   # Gateway boots on http://localhost:8108
   ```

4. **Start the Shopping Agent Web Server** (Terminal 2):
   ```bash
   cd shopping_agent && python server.py
   # Portal runs on http://localhost:8000
   ```

Open your browser to `http://localhost:8000` to interact with the Shopping Portal, search for products, and observe the live DAG execution logs!
