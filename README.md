# Shopping Agent V3 using DAG (Directed Acyclic Graph)

A multi-agent shopping agent orchestrated via a Directed Acyclic Graph (DAG) system. This architecture upgrades from a single-loop sequential execution model to a dynamic, concurrent skill executor. The system supports **general specialized nodes** (Planner, Researcher, Distiller, Summarizer, Critic, Coder, Sandbox Executor, Formatter) and **shopping specialist nodes** (Product Shortlister, Product Analyst, Product Recommender), running them in parallel using `asyncio.gather` for maximum speed and token efficiency.

> **Demo Video**: Watch the Shopping Agent V3 in action, scraping, analyzing, and formatting recommendations: [YouTube Demo Link](https://youtu.be/vPosAeuZ4Pc)

![Shopping Agent Screenshot](assets/Shopping%20Agent%20Screenshot.png)

---

## Shopping Agent V3 Architecture Under the Hood

The Shopping Agent V3 executes in three distinct, highly optimized phases:

![Shopping Agent V3 DAG Architecture](assets/DAG%20Screenshot.png)

### Phase 1: Product Shortlisting (Listing Scraper)
* The **Planner** receives the user query and compiles a DAG.
* The **Product Shortlister** is triggered. It uses a custom-configured **Playwright** browser to fetch the target e-commerce platform's search results page.
* It parses the HTML structure dynamically, utilizing standard browser headers and timing behaviors, to extract the top 10 organic candidates.
* It collects product IDs/ASINs, titles, ratings, reviews count, and listing detail URLs.
* **Price & Currency Integrity**: Prices are harvested natively (preserving the original currency, e.g., Indian Rupees `₹` or `INR` from the regional domain). The system strictly forbids converting or mutating the price.

### Phase 2: Dynamic Code Generation & Sandbox Execution
* The **Coder** node analyzes the shortlister's products. It dynamically writes custom Python scripts to sort the list of products based on the number of reviews in descending order to arrive at the top 3 shortlisted candidates for further analysis.
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

## Shopping Agent Tested Queries and Results

This section documents the execution of the main shopping pipeline. Key architectural highlights of this flow include:
1. **Parallel Fanout**: Spawns three parallel `Product Analyst` nodes concurrently to analyze details and sentiment for the top three products.
2. **Dynamic Ranking via Coder**: Employs a `Coder` node to generate Python scripts that sort and filter scraped products by review counts, executing securely in the `SandboxExecutor`.
3. **Shopping-Specific Skills**: Leverages three specialized shopping nodes designed for e-commerce search, analysis, and comparison, dynamically orchestrated by the `Planner`:
   - **Product Shortlister**: Uses a stealthy Playwright browser to search Amazon, extracts organic search results, preserves original price and currency metadata, and compiles the raw product listings.
   - **Product Analyst**: Concurrently spawned in parallel (one for each of the top 3 products) to deep-scrape individual product pages, extract customer reviews, and perform evaluations across five dimensions: Customer Sentiment, Reliability, Value for Money, Feature Completeness, and Build Quality.
   - **Product Recommender**: Aggregates the parallel analyst reports, evaluates the trade-offs, selects the single best "Top Recommendation", and compiles the unified products and analysis JSON payload.

* **Query**: `bluetooth mouse` (using the professional Amazon Shopping Assistant prompt template)
  - **Prompt Assembly**: When a search is submitted via the UI, the web server loads the static system instruction template (`shopping_system_prompt.txt`) and appends the user's raw search query (`User Query: bluetooth mouse`) at the end. 
  - **Graph Injection**: This combined prompt is fed directly to the orchestrator (`code/flow.py`) as a single input, which represents the root `USER_QUERY` in the DAG. The `Planner` uses this merged query to compile the execution plan and enforce the target JSON schema constraints down the line.
* **Graph Visualization**:
![Shopping Agent Graph](Queries%20and%20Logs/ShoppingAgent.png)

* **Execution Log**:
```text
session s8-2026-06-05_20-11-58  ─  query: You are a professional Amazon Shopping Assistant. Your task is to perform an analysis of the products requested in the query, identify the top three options based on volume of reviews by searching Amazon, evaluate them, select a "Top Recommendation", and output the final findings in a strict JSON format.

If the user query mentions typos like "Batman and brackets" or "brackets", intelligently interpret it as "badminton racquets / rackets".

Your response MUST be a single JSON structure matching this schema exactly, containing the details and evaluations for all three top products (do not output any natural language before or after the JSON, and do not use markdown code fences):

{
  "products": [
    {
      "id": "prod_1",
      "title": "<Full product name, e.g. Yonex Nanoray Light 18i Graphite Badminton Racquet>",
      "price": "<Price, e.g. ₹1,749 or $89>",
      "rating": <Float, e.g. 4.3>,
      "reviews_count": <Integer, e.g. 21200>,
      "image_url": "<Valid image URL>",
      "url": "<Product URL>"
    },
    {
      "id": "prod_2",
      "title": "<Full product name>",
      "price": "<Price>",
      "rating": <Float>,
      "reviews_count": <Integer>,
      "image_url": "<Valid image URL>",
      "url": "<Product URL>"
    },
    {
      "id": "prod_3",
      "title": "<Full product name>",
      "price": "<Price>",
      "rating": <Float>,
      "reviews_count": <Integer>,
      "image_url": "<Valid image URL>",
      "url": "<Product URL>"
    }
  ],
  "analysis": {
    "overall_agent_summary": "<A comprehensive 2-3 sentence paragraph explaining your recommendation reasoning, highlighting why the top choice is superior and who it is best for>",
    "products": [
      {
        "product_id": "prod_1",
        "is_top_recommendation": true,
        "evaluations": {
          // Downstream skills will populate evaluations for CUSTOMER SENTIMENT, RELIABILITY, VALUE FOR MONEY, FEATURE COMPLETENESS, and BUILD QUALITY.
        }
      },
      {
        "product_id": "prod_2",
        "is_top_recommendation": false,
        "evaluations": {}
      },
      {
        "product_id": "prod_3",
        "is_top_recommendation": false,
        "evaluations": {}
      }
    ]
  },
  "task": {
    "priorities": ["CUSTOMER SENTIMENT", "RELIABILITY", "VALUE FOR MONEY", "FEATURE COMPLETENESS", "BUILD QUALITY"]
  }
}


User Query: bluetooth mouse
══════════════════════════════════════════════════════════════════════════════
[memory.read] 8 hit(s) visible to every skill this run
[n:1] planner            complete (2.6s)
[n:2] product_shortlister complete (18.3s)
[n:3] coder              complete (4.7s)
[n:4] sandbox_executor   complete (0.0s)
[n:5] product_analyst    complete (15.6s)
[n:6] product_analyst    complete (14.8s)
[n:7] product_analyst    complete (14.1s)
[n:8] product_recommendation complete (4.8s)
[n:9] formatter          complete (4.8s)

══════════════════════════════════════════════════════════════════════════════
GATEWAY DATABASE CALLS LOGGED FOR SESSION: s8-2026-06-05_20-11-58
══════════════════════════════════════════════════════════════════════════════
[20:12:03] WORKER       | gemini_lite_2  | gemini-3.1-flash-lite          | OK    | in=7561 out=548 (2554ms)
[20:12:04] WORKER       | gemini_lite_1  | gemini-3.1-flash-lite          | OK    | in=694 out=31 (716ms)
[20:12:21] WORKER       | gemini_lite_1  | gemini-3.1-flash-lite          | OK    | in=12632 out=1704 (4798ms)
[20:12:26] WORKER       | gemini_lite_1  | gemini-3.1-flash-lite          | OK    | in=2405 out=1680 (4713ms)
[20:12:27] WORKER       | gemini_lite_2  | gemini-3.1-flash-lite          | OK    | in=1504 out=33 (670ms)
[20:12:27] WORKER       | gemini_lite_1  | gemini-3.1-flash-lite          | OK    | in=1504 out=33 (900ms)
[20:12:27] WORKER       | gemini_lite_3  | gemini-3.1-flash-lite          | OK    | in=1504 out=33 (1166ms)
[20:12:40] WORKER       | gemini_lite_1  | gemini-3.1-flash-lite          | OK    | in=6726 out=397 (2216ms)
[20:12:40] WORKER       | gemini_lite_2  | gemini-3.1-flash-lite          | OK    | in=7353 out=332 (2021ms)
[20:12:41] WORKER       | gemini_lite_3  | gemini-3.1-flash-lite          | OK    | in=7742 out=422 (2130ms)
[20:12:46] WORKER       | gemini_lite_4  | gemini-3.1-flash-lite          | OK    | in=2838 out=1771 (4807ms)
[20:12:51] WORKER       | gemini_lite_1  | gemini-3.1-flash-lite          | OK    | in=4081 out=1771 (4807ms)

══════════════════════════════════════════════════════════════════════════════
FINAL: {"products": [{"id": "prod_1", "title": "Portronics Toad One Bluetooth Mouse with 2.4 GHz & BT 5.3 Dual Wireless, 6 Buttons, Rechargeable, RGB Lights, Connect 3 Devices, Ergonomic Design for Laptop, Smartphone, Tablet (Black)", "price": "₹499", "rating": 4.3, "reviews_count": 9200, "image_url": "https://m.media-amazon.com/images/I/51hZtBRUFBL._SL1500_.jpg", "url": "https://www.amazon.in/dp/B0BG8LZNYL"}, {"id": "prod_2", "title": "ZEBRONICS Blanc Slim Wireless Mouse with Rechargeable Battery, BT + 2.4GHz, 4 Buttons, 800/1200/1600 DPI, Silent Operation, Multicolor LED Lights", "price": "₹299", "rating": 3.7, "reviews_count": 3400, "image_url": "https://m.media-amazon.com/images/I/51hZtBRUFBL._SL1500_.jpg", "url": "https://www.amazon.in/dp/B0BG8LZNYL"}]}
══════════════════════════════════════════════════════════════════════════════
```

## Other Tested Queries & Results

### 1. Hello Sanity Check
* **Query**: `Say hello.`
* **Graph Visualization**:
![hello_graph](Queries%20and%20Logs/hello.png)

* **Execution Log**:
```text
[gateway] up on http://localhost:8108

══════════════════════════════════════════════════════════════════════════════
session s8-2026-06-05_00-45-54  ─  query: Say hello.
══════════════════════════════════════════════════════════════════════════════
[memory.read] 8 hit(s) visible to every skill this run
[n:1] planner            complete (1.3s)
[skills debug] formatter raw reply:
{
  "final_answer": "Hello! How can I assist you today?"
}
[skills debug] End of formatter raw reply
[n:2] formatter          complete (0.8s)

══════════════════════════════════════════════════════════════════════════════
GATEWAY DATABASE CALLS LOGGED FOR SESSION: s8-2026-06-05_00-45-54
══════════════════════════════════════════════════════════════════════════════
[00:45:57] WORKER       | gemini_lite_2  | gemini-3.1-flash-lite          | OK    | in=4522 out=76 (1269ms)
[00:45:58] WORKER       | gemini_lite_3  | gemini-3.1-flash-lite          | OK    | in=750 out=20 (820ms)

══════════════════════════════════════════════════════════════════════════════
FINAL: Hello! How can I assist you today?
══════════════════════════════════════════════════════════════════════════════
```

### 2. Shannon Wikipedia Info Retrieval
* **Query**: `Fetch https://en.wikipedia.org/wiki/Claude_Shannon and tell me his birth date, death date, and three key contributions to information theory.`
* **Graph Visualization**:
![shannon_graph](Queries%20and%20Logs/A.%20Shannon%20Wikipedia.png)

* **Execution Log**:
```text
══════════════════════════════════════════════════════════════════════════════
session s8-2026-06-05_00-47-11  ─  query: Fetch https://en.wikipedia.org/wiki/Claude_Shannon and tell me his birth date, death date, and three key contributions to information theory.
══════════════════════════════════════════════════════════════════════════════
[memory.read] 8 hit(s) visible to every skill this run
[n:1] planner            complete (1.4s)
[06/05/26 00:47:15] INFO     Processing request of type            server.py:727
                             CallToolRequest                                    
[INIT].... → Crawl4AI 0.8.9 
[FETCH]... ↓ https://en.wikipedia.org/wiki/Claude_Shannon                                                         | ✓ | ⏱: 1.30s 
[SCRAPE].. ◆ https://en.wikipedia.org/wiki/Claude_Shannon                                                         | ✓ | ⏱: 0.18s 
[COMPLETE] ● https://en.wikipedia.org/wiki/Claude_Shannon                                                         | ✓ | ⏱: 1.49s 
[06/05/26 00:47:18] INFO     Processing request of type            server.py:727
                             ListToolsRequest                                   
[n:2] researcher         complete (5.9s)
[skills debug] formatter raw reply:
{
  "final_answer": "Claude Shannon (April 30, 1916 – February 24, 2001) is widely recognized as the 'father of information theory.' His three key contributions to the field include:\n\n1. The introduction of the concept of information entropy.\n2. The development of the mathematical theory of communication.\n3. The formulation of the Shannon–Hartley theorem, which defines the maximum rate of error-free data transmission over a noisy channel. \n\nSource: https://en.wikipedia.org/wiki/Claude_Shannon"
}
[skills debug] End of formatter raw reply
[n:3] formatter          complete (1.0s)

══════════════════════════════════════════════════════════════════════════════
GATEWAY DATABASE CALLS LOGGED FOR SESSION: s8-2026-06-05_00-47-11
══════════════════════════════════════════════════════════════════════════════
[00:47:13] WORKER       | gemini_lite_2  | gemini-3.1-flash-lite          | OK    | in=3530 out=173 (1348ms)
[00:47:15] WORKER       | gemini_lite_3  | gemini-3.1-flash-lite          | OK    | in=2578 out=28 (798ms)
[00:47:19] WORKER       | gemini_lite_1  | gemini-3.1-flash-lite          | OK    | in=12075 out=208 (1461ms)
[00:47:20] WORKER       | gemini_lite_2  | gemini-3.1-flash-lite          | OK    | in=1060 out=131 (998ms)

══════════════════════════════════════════════════════════════════════════════
FINAL: Claude Shannon (April 30, 1916 – February 24, 2001) is widely recognized as the 'father of information theory.' His three key contributions to the field include:

1. The introduction of the concept of information entropy.
2. The development of the mathematical theory of communication.
3. The formulation of the Shannon–Hartley theorem, which defines the maximum rate of error-free data transmission over a noisy channel. 

Source: https://en.wikipedia.org/wiki/Claude_Shannon
══════════════════════════════════════════════════════════════════════════════
```

### 3. Three City Populations (Parallel Fan-Out & Calculation)
* **Query**: `Find the populations of London, Paris, Berlin and tell me which two are closest in size.`
* **Graph Visualization**:
![cities_graph](Queries%20and%20Logs/I.%20Three%20city%20populations.png)

* **Execution Log**:
```text
session s8-2026-06-05_20-21-16  ─  query: Find the populations of London, Paris, Berlin and tell me which two are closest in size.
══════════════════════════════════════════════════════════════════════════════
[memory.read] 8 hit(s) visible to every skill this run
[n:1] planner            complete (2.3s)
[06/05/26 20:21:21] INFO     Processing request of type            server.py:727
                             CallToolRequest                                    
[06/05/26 20:21:21] INFO     Processing request of type            server.py:727
                             CallToolRequest                                    
[06/05/26 20:21:21] INFO     Processing request of type            server.py:727
                             CallToolRequest                                    
                    INFO     response:                                lib.rs:444
                             https://grokipedia.com/api/typeahead?que           
                             ry=current+population+of+Berlin+2024+202           
                             5+official+statistics&limit=1 200                  
[06/05/26 20:21:22] INFO     response:                                lib.rs:444
                             https://en.wikipedia.org/w/api.php?actio           
                             n=opensearch&profile=fuzzy&limit=1&searc           
                             h=current%20population%20of%20London%202           
                             024%202025 200                                     
[06/05/26 20:21:22] INFO     response:                                lib.rs:444
                             https://en.wikipedia.org/w/api.php?actio           
                             n=opensearch&profile=fuzzy&limit=1&searc           
                             h=current%20population%20of%20Berlin%202           
                             024%202025%20official%20statistics 200             
                    INFO     response:                                lib.rs:444
                             https://grokipedia.com/api/typeahead?que           
                             ry=current+population+of+London+2024+202           
                             5&limit=1 200                                      
[06/05/26 20:21:22] INFO     response:                                lib.rs:444
                             https://en.wikipedia.org/w/api.php?actio           
                             n=opensearch&profile=fuzzy&limit=1&searc           
                             h=current%20population%20of%20Paris%20ci           
                             ty%20vs%20urban%20area%202024%202025 200           
                    INFO     response:                                lib.rs:444
                             https://grokipedia.com/api/typeahead?que           
                             ry=current+population+of+Paris+city+vs+u           
                             rban+area+2024+2025&limit=1 200                    
[06/05/26 20:21:23] INFO     response:                                lib.rs:444
                             https://search.brave.com/search?q=curren           
                             t+population+of+Berlin+2024+2025+officia           
                             l+statistics&source=web 200                        
                    INFO     Processing request of type            server.py:727
                             ListToolsRequest                                   
[06/05/26 20:21:23] INFO     response:                                lib.rs:444
                             https://www.google.com/search?q=current+           
                             population+of+Paris+city+vs+urban+area+2           
                             024+2025&filter=1&start=0&hl=en-US&lr=la           
                             ng_en&cr=countryUS 200                             
[06/05/26 20:21:23] INFO     response:                                lib.rs:444
                             https://www.mojeek.com/search?q=current+           
                             population+of+London+2024+2025 200                 
                    INFO     Processing request of type            server.py:727
                             CallToolRequest                                    
                    INFO     Processing request of type            server.py:727
                             ListToolsRequest                                   
[06/05/26 20:21:24] INFO     response:                                lib.rs:444
                             https://search.yahoo.com/search;_ylt=Psq           
                             Zegx0f5PiCBIRh7X6g1Kc;_ylu=wF9uHetrssALn           
                             OAiLUj5RWOjMgdDlws5qcbwuiFlTQr5BpM?p=cur           
                             rent+population+of+Paris+city+vs+urban+a           
                             rea+2024+2025 200                                  
                    INFO     Processing request of type            server.py:727
                             ListToolsRequest                                   
[06/05/26 20:21:24] INFO     Processing request of type            server.py:727
                             CallToolRequest                                    
[INIT].... → Crawl4AI 0.8.9 
[INIT].... → Crawl4AI 0.8.9 
[06/05/26 20:21:25] INFO     Processing request of type            server.py:727
                             CallToolRequest                                    
[INIT].... → Crawl4AI 0.8.9 
[FETCH]... ↓ https://www.varbes.com/population/london-population                                                  | ✓ | ⏱: 1.37s 
[SCRAPE].. ◆ https://www.varbes.com/population/london-population                                                  | ✓ | ⏱: 0.00s 
[ERROR]... × https://www.varbes.com/...ation/london-population  | Error: Blocked by anti-bot protection: Structural: minimal_text on small page (159 bytes, 8 chars visible) 
[COMPLETE] ● https://www.varbes.com/population/london-population                                                  | ✗ | ⏱: 1.38s 
[06/05/26 20:21:28] INFO     Processing request of type            server.py:727
                             CallToolRequest                                    
[FETCH]... ↓ https://geographyworlds.com/blog/population-of-paris/                                                | ✓ | ⏱: 1.99s 
[SCRAPE].. ◆ https://geographyworlds.com/blog/population-of-paris/                                                | ✓ | ⏱: 0.00s 
[ERROR]... × https://geographyworlds...og/population-of-paris/  | Error: Blocked by anti-bot protection: Structural: minimal_text, no_content_elements, script_heavy_shell (15234 bytes, 0 chars 
visible) 
[COMPLETE] ● https://geographyworlds.com/blog/population-of-paris/                                                | ✗ | ⏱: 2.00s 
[INIT].... → Crawl4AI 0.8.9 
[06/05/26 20:21:28] INFO     Processing request of type            server.py:727
                             CallToolRequest                                    
[FETCH]... ↓ https://www.thegroundsag.com/en/2026/02/19/berlins-population-rose-to-more-than-3-9-million-in-2025/ | ✓ | ⏱: 3.79s 
[SCRAPE].. ◆ https://www.thegroundsag.com/en/2026/02/19/berlins-population-rose-to-more-than-3-9-million-in-2025/ | ✓ | ⏱: 0.03s 
[COMPLETE] ● https://www.thegroundsag.com/en/2026/02/19/berlins-population-rose-to-more-than-3-9-million-in-2025/ | ✓ | ⏱: 3.83s 
[INIT].... → Crawl4AI 0.8.9 
[FETCH]... ↓ https://en.wikipedia.org/wiki/Paris_metropolitan_area                                                | ✓ | ⏱: 1.07s 
[SCRAPE].. ◆ https://en.wikipedia.org/wiki/Paris_metropolitan_area                                                | ✓ | ⏱: 0.04s 
[COMPLETE] ● https://en.wikipedia.org/wiki/Paris_metropolitan_area                                                | ✓ | ⏱: 1.13s 
[FETCH]... ↓ https://trustforlondon.org.uk/data/topics/population/                                                | ✓ | ⏱: 2.32s 
[SCRAPE].. ◆ https://trustforlondon.org.uk/data/topics/population/                                                | ✓ | ⏱: 0.01s 
[COMPLETE] ● https://trustforlondon.org.uk/data/topics/population/                                                | ✓ | ⏱: 2.34s 
[n:2] researcher         complete (12.4s)
[n:3] researcher         complete (12.2s)
[n:4] researcher         complete (10.5s)
[n:5] coder              complete (1.5s)
[n:6] sandbox_executor   complete (0.0s)
[n:7] formatter          complete (1.0s)

══════════════════════════════════════════════════════════════════════════════
GATEWAY DATABASE CALLS LOGGED FOR SESSION: s8-2026-06-05_20-21-16
══════════════════════════════════════════════════════════════════════════════
[20:21:20] WORKER       | gemini_lite_2  | gemini-3.1-flash-lite          | OK    | in=2125 out=410 (2257ms)
[20:21:21] WORKER       | gemini_lite_4  | gemini-3.1-flash-lite          | OK    | in=905 out=39 (720ms)
[20:21:21] WORKER       | gemini_lite_5  | gemini-3.1-flash-lite          | OK    | in=905 out=31 (736ms)
[20:21:21] WORKER       | gemini_lite_3  | gemini-3.1-flash-lite          | OK    | in=905 out=35 (754ms)
[20:21:23] WORKER       | gemini_lite_1  | gemini-3.1-flash-lite          | OK    | in=1572 out=64 (786ms)
[20:21:24] WORKER       | gemini_lite_2  | gemini-3.1-flash-lite          | OK    | in=1219 out=29 (1056ms)
[20:21:25] WORKER       | gemini_lite_3  | gemini-3.1-flash-lite          | OK    | in=1242 out=31 (862ms)
[20:21:28] WORKER       | gemini_lite_4  | gemini-3.1-flash-lite          | OK    | in=1292 out=31 (983ms)
[20:21:28] WORKER       | gemini_lite_1  | gemini-3.1-flash-lite          | OK    | in=1307 out=31 (590ms)
[20:21:30] WORKER       | gemini_lite_2  | gemini-3.1-flash-lite          | OK    | in=4731 out=268 (1590ms)
[20:21:32] WORKER       | gemini_lite_3  | gemini-3.1-flash-lite          | OK    | in=10083 out=210 (1873ms)
[20:21:32] WORKER       | gemini_lite_5  | gemini-3.1-flash-lite          | OK    | in=3920 out=182 (1524ms)
[20:21:33] WORKER       | gemini_lite_1  | gemini-3.1-flash-lite          | OK    | in=1422 out=305 (1446ms)
[20:21:34] WORKER       | gemini_lite_2  | gemini-3.1-flash-lite          | OK    | in=1061 out=90 (959ms)

══════════════════════════════════════════════════════════════════════════════
FINAL: The populations for the cities are approximately: London (8,982,000), Paris (City, 2,161,000), and Berlin (3,974,644). Among these three, Paris and Berlin are the two cities closest in size, with a population difference of 1,813,644.
══════════════════════════════════════════════════════════════════════════════
```

### 4. Graceful Failure Handling
* **Query**: `Read /nonexistent/path.txt and tell me what's in it.`
* **Graph Visualization**:
![failure_graph](Queries%20and%20Logs/J.%20Graceful%20failure.png)

* **Execution Log**:
```text
══════════════════════════════════════════════════════════════════════════════
session s8-2026-06-05_00-58-01  ─  query: Read /nonexistent/path.txt and tell me what's in it.
══════════════════════════════════════════════════════════════════════════════
[memory.read] 8 hit(s) visible to every skill this run
[n:1] planner            complete (1.2s)
[skills debug] formatter raw reply:
{
  "final_answer": "The requested file path /nonexistent/path.txt could not be found, and therefore its contents cannot be retrieved."
}
[skills debug] End of formatter raw reply
[n:2] formatter          complete (0.7s)

══════════════════════════════════════════════════════════════════════════════
GATEWAY DATABASE CALLS LOGGED FOR SESSION: s8-2026-06-05_00-58-01
══════════════════════════════════════════════════════════════════════════════
[00:58:04] WORKER       | gemini_lite_2  | gemini-3.1-flash-lite          | OK    | in=4591 out=117 (1234ms)
[00:58:04] WORKER       | gemini_lite_3  | gemini-3.1-flash-lite          | OK    | in=804 out=35 (711ms)

══════════════════════════════════════════════════════════════════════════════
FINAL: The requested file path /nonexistent/path.txt could not be found, and therefore its contents cannot be retrieved.
══════════════════════════════════════════════════════════════════════════════
```

### 5. Resumable Execution (SIGKILL Recovery)
* **Query**: `For Lagos, Cairo, and Kinshasa, find current populations and growth rates and tell me which is growing fastest.`
* **Graph Visualization (Kill Phase)**:
![kill_graph](Queries%20and%20Logs/K.%20Resumable%20execution_kill.png)
  - **Observation**: During the kill phase, you can see that only 2 researcher nodes are complete and the other downstream nodes are left pending when the process was killed.

* **Execution Log (Kill Phase)**:
```text
[06/05/26 01:16:16] INFO     Processing request of type            server.py:727
                             CallToolRequest                                    
[06/05/26 01:16:16] INFO     Processing request of type            server.py:727
                             CallToolRequest                                    
[06/05/26 01:16:16] INFO     Processing request of type            server.py:727
                             CallToolRequest                                    
[06/05/26 01:16:17] INFO     response:                                lib.rs:444
                             https://en.wikipedia.org/w/api.php?actio           
                             n=opensearch&profile=fuzzy&limit=1&searc           
                             h=current%20population%20and%20annual%20           
                             growth%20rate%20of%20Lagos%202024%202025           
                              200                                               
[06/05/26 01:16:17] INFO     response:                                lib.rs:444
                             https://en.wikipedia.org/w/api.php?actio           
                             n=opensearch&profile=fuzzy&limit=1&searc           
                             h=current%20population%20and%20annual%20           
                             growth%20rate%20of%20Cairo%202024%202025           
                              200                                               
[06/05/26 01:16:17] INFO     response:                                lib.rs:444
                             https://en.wikipedia.org/w/api.php?actio           
                             n=opensearch&profile=fuzzy&limit=1&searc           
                             h=current%20population%20and%20annual%20           
                             growth%20rate%20of%20Kinshasa%202024%202           
                             025 200                                            
                    INFO     response:                                lib.rs:444
                             https://grokipedia.com/api/typeahead?que           
                             ry=current+population+and+annual+growth+           
                             rate+of+Lagos+2024+2025&limit=1 200                
                    INFO     response:                                lib.rs:444
                             https://grokipedia.com/api/typeahead?que           
                             ry=current+population+and+annual+growth+           
                             rate+of+Cairo+2024+2025&limit=1 200                
                    INFO     response:                                lib.rs:444
                             https://grokipedia.com/api/typeahead?que           
                             ry=current+population+and+annual+growth+           
                             rate+of+Kinshasa+2024+2025&limit=1 200             
                    INFO     HTTP Request: POST                  _client.py:1025
                             https://html.duckduckgo.com/html/                  
                             "HTTP/2 202 Accepted"                              
                    INFO     response:                                lib.rs:444
                             https://www.google.com/search?q=current+           
                             population+and+annual+growth+rate+of+Kin           
                             shasa+2024+2025&filter=1&start=0&hl=en-U           
                             S&lr=lang_en&cr=countryUS 200                      
                    INFO     Processing request of type            server.py:727
                             ListToolsRequest                                   
[06/05/26 01:16:18] INFO     response:                                lib.rs:444
                             https://search.brave.com/search?q=curren           
                             t+population+and+annual+growth+rate+of+L           
                             agos+2024+2025&source=web 200                      
                    INFO     Processing request of type            server.py:727
                             ListToolsRequest                                   
[06/05/26 01:16:18] INFO     response:                                lib.rs:444
                             https://www.mojeek.com/search?q=current+           
                             population+and+annual+growth+rate+of+Cai           
                             ro+2024+2025 403                                   
[06/05/26 01:16:18] INFO     Processing request of type            server.py:727
                             CallToolRequest                                    
                    INFO     Processing request of type            server.py:727
                             CallToolRequest                                    
[06/05/26 01:16:19] INFO     response:                                lib.rs:444
                             https://www.google.com/search?q=current+           
                             population+and+annual+growth+rate+of+Cai           
                             ro+2024+2025&filter=1&start=0&hl=en-US&l           
                             r=lang_en&cr=countryUS 200                         
[06/05/26 01:16:19] INFO     response:                                lib.rs:444
                             https://grokipedia.com/api/typeahead?que           
                             ry=Kinshasa+current+population+2024+2025           
                             +and+annual+growth+rate&limit=1 200                
                    INFO     response:                                lib.rs:444
                             https://en.wikipedia.org/w/api.php?actio           
                             n=opensearch&profile=fuzzy&limit=1&searc           
                             h=Kinshasa%20current%20population%202024           
                             %202025%20and%20annual%20growth%20rate             
                             200                                                
[INIT].... → Crawl4AI 0.8.9 
                    INFO     response:                                lib.rs:444
                             https://www.mojeek.com/search?q=Kinshasa           
                             +current+population+2024+2025+and+annual           
                             +growth+rate 403                                   
[06/05/26 01:16:20] INFO     response:                                lib.rs:444
                             https://yandex.com/search/site/?text=cur           
                             rent+population+and+annual+growth+rate+o           
                             f+Cairo+2024+2025&web=1&searchid=8135107           
                              200                                               
                    INFO     Processing request of type            server.py:727
                             ListToolsRequest                                   
[06/05/26 01:16:20] INFO     response:                                lib.rs:444
                             https://search.brave.com/search?q=Kinsha           
                             sa+current+population+2024+2025+and+annu           
                             al+growth+rate&source=web 200                      
[FETCH]... ↓ https://www.macrotrends.net/global-metrics/cities/22007/lagos/population                             | ✓ | ⏱: 1.55s 
[SCRAPE].. ◆ https://www.macrotrends.net/global-metrics/cities/22007/lagos/population                             | ✓ | ⏱: 0.04s 
[COMPLETE] ● https://www.macrotrends.net/global-metrics/cities/22007/lagos/population                             | ✓ | ⏱: 1.60s 
[06/05/26 01:16:21] INFO     Processing request of type            server.py:727
                             CallToolRequest                                    
[INIT].... → Crawl4AI 0.8.9
[PROCESS TERMINATED BY SIGKILL]
```

* **Graph Visualization (Resume Phase)**:
![resume_graph](Queries%20and%20Logs/K.%20Resumable%20execution_resumed.png)
  - **Observation**: During the resume phase (resuming the same session), you can see that the previously pending items were successfully picked up and processed to completion.

* **Execution Log (Resume Phase)**:
```text
══════════════════════════════════════════════════════════════════════════════
session s8-2026-06-05_01-16-12  ─  query: For Lagos, Cairo, and Kinshasa, find current populations and growth rates and tell me which is growing fastest.
══════════════════════════════════════════════════════════════════════════════
[memory.read] 8 hit(s) visible to every skill this run
[06/05/26 01:21:40] INFO     Processing request of type            server.py:727
                             CallToolRequest                                    
[06/05/26 01:21:41] INFO     response:                                lib.rs:444
                             https://en.wikipedia.org/w/api.php?actio           
                             n=opensearch&profile=fuzzy&limit=1&searc           
                             h=current%20population%20and%20annual%20           
                             growth%20rate%20of%20Cairo%202024%202025           
                              200                                               
                    INFO     response:                                lib.rs:444
                             https://grokipedia.com/api/typeahead?que           
                             ry=current+population+and+annual+growth+           
                             rate+of+Cairo+2024+2025&limit=1 200                
[06/05/26 01:21:42] INFO     response: https://www.startpage.com/ 200 lib.rs:444
[06/05/26 01:21:43] INFO     response:                                lib.rs:444
                             https://www.startpage.com/sp/search 200            
                    INFO     Processing request of type            server.py:727
                             ListToolsRequest                                   
[06/05/26 01:21:44] INFO     Processing request of type            server.py:727
                             CallToolRequest                                    
[INIT].... → Crawl4AI 0.8.9 
[FETCH]... ↓ https://www.macrotrends.net/global-metrics/cities/22812/cairo/population                             | ✓ | ⏱: 1.88s 
[SCRAPE].. ◆ https://www.macrotrends.net/global-metrics/cities/22812/cairo/population                             | ✓ | ⏱: 0.01s 
[COMPLETE] ● https://www.macrotrends.net/global-metrics/cities/22812/cairo/population                             | ✓ | ⏱: 1.91s 
[n:3] researcher         complete (9.2s)
[skills debug] coder raw reply:
{
  "code": "import json\n\ncities = [\n    {\"name\": \"Lagos\", \"population\": 17804000, \"growth_rate\": 3.78},\n    {\"name\": \"Cairo\", \"population\": 23540000, \"growth_rate\": 2.0},\n    {\"name\": \"Kinshasa\", \"population\": 18500000, \"growth_rate\": 4.38}\n]\n\ndef identify_fastest_growth(city_data):\n    fastest = max(city_data, key=lambda x: x['growth_rate'])\n    return fastest\n\nresults = identify_fastest_growth(cities)\n\nprint(f\"City Data:\")\nfor city in cities:\n    print(f\"{city['name']}: Population {city['population']:,}, Growth Rate {city['growth_rate']}%\")\n\nprint(f\"\\nThe city growing the fastest is {results['name']} with a growth rate of {results['growth_rate']}%.\")",
  "rationale": "I extracted the population and growth rate values from the inputs, stored them in a list of dictionaries, and used the max() function with a lambda key to identify the city with the highest growth rate."
}
[skills debug] End of coder raw reply
[n:5] coder              complete (1.3s)
[n:6] sandbox_executor   complete (0.0s)
[skills debug] formatter raw reply:
{
  "final_answer": "Based on current data, here are the population statistics for the three cities:\n\n* Lagos: 17,804,000 population, 3.78% growth rate.\n* Cairo: 23,540,000 population, 2.0% growth rate.\n* Kinshasa: 18,500,000 population, 4.38% growth rate.\n\nKinshasa is currently the fastest-growing city among the three, with an annual growth rate of 4.38%."
}
[skills debug] End of formatter raw reply
[n:7] formatter          complete (1.1s)

══════════════════════════════════════════════════════════════════════════════
GATEWAY DATABASE CALLS LOGGED FOR SESSION: s8-2026-06-05_01-16-12
══════════════════════════════════════════════════════════════════════════════
[01:16:15] WORKER       | gemini_lite_2  | gemini-3.1-flash-lite          | OK    | in=1958 out=449 (2062ms)
[01:16:16] WORKER       | gemini_lite_4  | gemini-3.1-flash-lite          | OK    | in=901 out=33 (653ms)
[01:16:16] WORKER       | gemini_lite_3  | gemini-3.1-flash-lite          | OK    | in=901 out=33 (666ms)
[01:16:16] WORKER       | gemini_lite_5  | gemini-3.1-flash-lite          | OK    | in=903 out=41 (663ms)
[01:16:18] WORKER       | gemini_lite_1  | gemini-3.1-flash-lite          | OK    | in=1317 out=40 (817ms)
[01:16:18] WORKER       | gemini_lite_2  | gemini-3.1-flash-lite          | OK    | in=1515 out=40 (827ms)
[01:16:21] WORKER       | gemini_lite_3  | gemini-3.1-flash-lite          | OK    | in=1395 out=30 (800ms)
[01:16:22] WORKER       | gemini_lite_4  | gemini-3.1-flash-lite          | OK    | in=1701 out=250 (1390ms)
[01:16:22] WORKER       | gemini_lite_5  | gemini-3.1-flash-lite          | OK    | in=4499 out=242 (1447ms)
[01:21:40] WORKER       | gemini_lite_2  | gemini-3.1-flash-lite          | OK    | in=904 out=39 (570ms)
[01:21:44] WORKER       | gemini_lite_1  | gemini-3.1-flash-lite          | OK    | in=1270 out=40 (560ms)
[01:21:49] WORKER       | gemini_lite_2  | gemini-3.1-flash-lite          | OK    | in=2509 out=192 (1435ms)
[01:21:50] WORKER       | gemini_lite_1  | gemini-3.1-flash-lite          | OK    | in=1430 out=305 (1309ms)
[01:21:51] WORKER       | gemini_lite_3  | gemini-3.1-flash-lite          | OK    | in=1033 out=137 (1046ms)

══════════════════════════════════════════════════════════════════════════════
FINAL: Based on current data, here are the population statistics for the three cities:

* Lagos: 17,804,000 population, 3.78% growth rate.
* Cairo: 23,540,000 population, 2.0% growth rate.
* Kinshasa: 18,500,000 population, 4.38% growth rate.

Kinshasa is currently the fastest-growing city among the three, with an annual growth rate of 4.38%.
══════════════════════════════════════════════════════════════════════════════
```


### 6. Critic verification (Pass run)
* **Query**: `Fetch https://www.iplt20.com/matches/points-table and find the team who got finished top of the table. Verify the details extracted are correct.`

The planner explicitly emits a critic node to verify the details. We'll see how the critic evaluates and provides a success example of the same.

* **Graph Visualization**:
![L1 Graph](Queries%20and%20Logs/L1.%20Critic%20verification%20(Pass%20run).png)

* **Execution Log**:
```text
session s8-2026-06-05_15-48-59  ─  query: Fetch https://www.iplt20.com/matches/points-table and find the team who got finished top of the table. Verify the details extracted are correct.
[memory.read] 8 hit(s) visible to every skill this run
[n:1] planner            complete (1.7s)
[INIT].... → Crawl4AI 0.8.9 
[FETCH]... ↓ https://www.iplt20.com/matches/points-table                                                          | ✓ | ⏱: 2.28s 
[SCRAPE].. ◆ https://www.iplt20.com/matches/points-table                                                          | ✓ | ⏱: 0.03s 
[COMPLETE] ● https://www.iplt20.com/matches/points-table                                                          | ✓ | ⏱: 2.32s 
[n:2] researcher         complete (7.0s)
[n:3] critic             complete (1.2s)
[n:4] formatter          complete (1.5s)

GATEWAY DATABASE CALLS LOGGED FOR SESSION: s8-2026-06-05_15-48-59
[15:49:02] WORKER       | gemini_lite_2  | gemini-3.1-flash-lite          | OK    | in=3569 out=256 (1697ms)
[15:49:04] WORKER       | gemini_lite_3  | gemini-3.1-flash-lite          | OK    | in=2616 out=31 (1350ms)
[15:49:09] WORKER       | gemini_lite_1  | gemini-3.1-flash-lite          | OK    | in=8043 out=180 (1374ms)
[15:49:10] WORKER       | gemini_lite_2  | gemini-3.1-flash-lite          | OK    | in=2501 out=42 (1153ms)
[15:49:12] WORKER       | gemini_lite_3  | gemini-3.1-flash-lite          | OK    | in=1223 out=100 (1534ms)

FINAL: According to the official IPL 2026 points table (https://www.iplt20.com/matches/points-table), Royal Challengers Bengaluru (RCB) finished at the top of the standings. They achieved this position by securing 18 points from 14 matches, consisting of 9 wins and 5 losses, and maintaining a Net Run Rate (NRR) of 0.783.
```

---

### 7. Critic verification (Pass and Fail-Recover runs)
* **Query**: `Using the researcher skill, fetch https://en.wikipedia.org/wiki/Claude_Shannon to identify his birth city. Then, using the distiller skill, write a haiku (5-7-5 syllables) about this city. The first line of the haiku must contain exactly 3 words. Have the critic verify that the haiku has the correct 5-7-5 syllable structure and that the first line contains exactly 3 words. If the critic fails, have the planner re-plan.`

To ensure the high accuracy and reliability of the output data, the planner embeds a **Critic** node to check the research outputs before they are formatted. When a Critic node evaluates the initial research and issues a **fail** verdict (due to missing or inaccurate information, or violating structural constraints), the orchestrator intercepts the failure and invokes the **Planner** in recovery mode. The Planner analyzes the Critic's feedback, dynamically rebuilds a corrected execution graph, and re-executes the plan to correct the output.

In this specific run:
- The first distiller attempt failed the Critic check because the generated haiku did not strictly meet the 5-7-5 syllable count constraint or the 3-word first-line constraint.
- The orchestrator caught the failure and spun up a recovery planner (`n:7`) to rebuild the graph.
- On the second attempt, the distiller successfully generated a correct haiku (*"Petoskey is home..."*), which met the syllable count (5-7-5) and the 3-word first-line constraint. This was verified and approved by the Critic, allowing the `formatter` to output the final user-facing response.

* **Graph Visualization**:
![L2 Graph](Queries%20and%20Logs/L2.%20Critic%20verification%20(Pass%20and%20Fail-Recover%20runs).png)


* **Execution Log**:
```text
session s8-2026-06-06_07-18-07  ─  query: Using the researcher skill, fetch https://en.wikipedia.org/wiki/Claude_Shannon to identify his birth city. Then, using the distiller skill, write a haiku (5-7-5 syllables) about this city. The first line of the haiku must contain exactly 3 words. Have the critic verify that the haiku has the correct 5-7-5 syllable structure and that the first line contains exactly 3 words. If the critic fails, have the planner re-plan.
[memory.read] 8 hit(s) visible to every skill this run
[n:1] planner            complete (1.8s)
[INIT].... → Crawl4AI 0.8.9 
[FETCH]... ↓ https://en.wikipedia.org/wiki/Claude_Shannon                                                         | ✓ | ⏱: 1.44s 
[SCRAPE].. ◆ https://en.wikipedia.org/wiki/Claude_Shannon                                                         | ✓ | ⏱: 0.18s 
[COMPLETE] ● https://en.wikipedia.org/wiki/Claude_Shannon                                                         | ✓ | ⏱: 1.64s 
[n:2] researcher         complete (6.4s)
[n:3] distiller          complete (1.4s)
[n:4] critic             complete (1.1s)
  ↪ critic-fail recovery: planner node n:7 for n:3
[n:6] critic             complete (0.9s)
[n:7] planner            complete (1.9s)
[INIT].... → Crawl4AI 0.8.9 
[FETCH]... ↓ https://en.wikipedia.org/wiki/Claude_Shannon                                                         | ✓ | ⏱: 1.67s 
[SCRAPE].. ◆ https://en.wikipedia.org/wiki/Claude_Shannon                                                         | ✓ | ⏱: 0.18s 
[COMPLETE] ● https://en.wikipedia.org/wiki/Claude_Shannon                                                         | ✓ | ⏱: 1.86s 
[n:8] researcher         complete (5.8s)
[n:9] distiller          complete (1.0s)
[n:10] critic             complete (1.3s)
[n:12] critic             complete (1.3s)
[n:11] formatter          complete (1.6s)

GATEWAY DATABASE CALLS LOGGED FOR SESSION: s8-2026-06-06_07-18-07
[07:18:10] WORKER       | gemini_lite_2  | gemini-3.1-flash-lite          | OK    | in=2963 out=320 (1751ms)
[07:18:12] WORKER       | gemini_lite_3  | gemini-3.1-flash-lite          | OK    | in=1756 out=28 (1043ms)
[07:18:16] WORKER       | gemini_lite_1  | gemini-3.1-flash-lite          | OK    | in=11253 out=119 (1671ms)
[07:18:18] WORKER       | gemini_lite_2  | gemini-3.1-flash-lite          | OK    | in=1518 out=66 (1408ms)
[07:18:19] WORKER       | gemini_lite_4  | gemini-3.1-flash-lite          | OK    | in=678 out=55 (889ms)
[07:18:19] WORKER       | gemini_lite_3  | gemini-3.1-flash-lite          | OK    | in=549 out=93 (1130ms)
[07:18:21] WORKER       | gemini_lite_1  | gemini-3.1-flash-lite          | OK    | in=3055 out=371 (1903ms)
[07:18:23] WORKER       | gemini_lite_2  | gemini-3.1-flash-lite          | OK    | in=1756 out=28 (1547ms)
[07:18:27] WORKER       | gemini_lite_1  | gemini-3.1-flash-lite          | OK    | in=11265 out=116 (1262ms)
[07:18:28] WORKER       | gemini_lite_2  | gemini-3.1-flash-lite          | OK    | in=1525 out=77 (995ms)
[07:18:29] WORKER       | gemini_lite_4  | gemini-3.1-flash-lite          | OK    | in=686 out=41 (1290ms)
[07:18:29] WORKER       | gemini_lite_3  | gemini-3.1-flash-lite          | OK    | in=585 out=74 (1301ms)
[07:18:31] WORKER       | gemini_lite_5  | gemini-3.1-flash-lite          | OK    | in=1289 out=54 (1538ms)

FINAL: Claude Shannon was born in Petoskey, Michigan. Here is a haiku about the city:

Petoskey is home,
Birthplace of the genius man,
Known for pure logic.
```

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



