# 🏦 Financial Document Analyzer

An AI-powered financial document analysis system built with CrewAI. Upload any corporate report or financial statement and get structured, grounded analysis — no hallucinations, no speculation.

---

## 📋 Table of Contents

- [Project Overview](#project-overview)
- [Architecture](#architecture)
- [Getting Started](#getting-started)
- [API Documentation](#api-documentation)
- [Bugs Found & Fixed](#bugs-found--fixed)
- [CrewAI Behavior: Why These Bugs Mattered](#crewai-behavior-why-these-bugs-mattered)
- [Tool Allocation & Hallucination Prevention](#tool-allocation--hallucination-prevention)
- [Dependency Setup & Resolution](#dependency-setup--resolution)
- [Bonus: Queue Worker & Database Integration](#bonus-queue-worker--database-integration)
- [Project Structure](#project-structure)

---

## Project Overview

This system uses a **four-agent sequential CrewAI pipeline** to analyze uploaded PDF financial documents:

1. **Senior Financial Analyst** — Reads the document using `read_data_tool` and fetches external market context using `search_tool` (SerperDev), then answers the user's query using only grounded information.
2. **Financial Document Verifier** — Reviews the analyst's output and confirms no hallucinated or unsupported claims are present.
3. **Investment Advisor** — Reads the document directly using `read_data_tool` to extract specific financial metrics (revenue, margins, growth) and produce grounded investment observations.
4. **Risk Assessor** — Reads the document directly using `read_data_tool` to identify explicit risk factors stated in the filing — no invented doomsday scenarios.

The system is exposed as a REST API via FastAPI and supports concurrent request handling via Celery + Redis, with results persisted in MongoDB.

### Sample Document

The system is designed to analyze financial documents like Tesla's Q2 2025 Update.

1. Download: [Tesla Q2 2025 Update PDF](https://www.tesla.com/sites/default/files/downloads/TSLA-Q2-2025-Update.pdf)
2. Save as `data/sample.pdf`, or upload any financial PDF directly via the API.

---

## Architecture

```
┌─────────────┐     HTTP      ┌──────────────┐     Queue      ┌──────────────────┐
│   Client    │ ────────────▶ │   FastAPI    │ ─────────────▶ │  Celery Worker   │
│             │               │   main.py    │                 │   worker.py      │
└─────────────┘               └──────────────┘                 └──────────────────┘
                                      │                                  │
                                      │  Poll /results/{job_id}          │ run_crew()
                                      ▼                                  ▼
                               ┌──────────────┐                ┌──────────────────────────────┐
                               │   MongoDB    │ ◀───────────── │         CrewAI Crew          │
                               │  (results)   │                │                              │
                               └──────────────┘                │  1. Senior Financial Analyst │
                                                               │     ├─ read_data_tool        │
                                                               │     └─ search_tool (Serper)  │
                                                               │  2. Financial Verifier        │
                                                               │     └─ (no tools, uses ctx)  │
                                                               │  3. Investment Advisor        │
                                                               │     └─ read_data_tool        │
                                                               │  4. Risk Assessor             │
                                                               │     └─ read_data_tool        │
                                                               └──────────────────────────────┘
```

**Tech stack:** Python 3.12 · CrewAI 0.130.0 · FastAPI · Celery · Redis · MongoDB · OpenAI GPT-4o-mini · SerperDev

---

## Getting Started

### Prerequisites

| Requirement | Version |
|---|---|
| Python | `>=3.10, <3.14` (3.12.x recommended) |
| Redis | Running on `localhost:6379` |
| MongoDB | Running on `localhost:27017` |
| SerperDev API Key | [serper.dev](https://serper.dev) (free tier available) |

> ⚠️ **Python version is critical.** `crewai==0.130.0` explicitly requires Python `<3.14`. Use pyenv to pin the version:

```bash
pyenv install 3.12.2
pyenv local 3.12.2
```

### Installation

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd financial-document-analyzer-debug

# 2. Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install from the frozen lockfile
pip install -r requirements.lock --no-deps
```

> **Why `--no-deps` and `requirements.lock`?**
>
> The dependency graph for CrewAI + LangChain + Google SDKs is large enough to cause `pip`'s resolver to fail with `resolution-too-deep` or `ResolutionImpossible` when starting from scratch. The lockfile captures a pre-resolved, runtime-verified environment. See [Dependency Setup & Resolution](#dependency-setup--resolution) for the full story.

### Environment Variables

```bash
cp .env.example .env
```

Fill in your `.env`:

```env
OPENAI_API_KEY=your_openai_api_key_here
SERPER_API_KEY=your_serper_api_key_here
REDIS_URL=redis://localhost:6379/0
MONGODB_URL=mongodb://localhost:27017
PYTHONPATH=.
```

### Running the Application

```bash
# Terminal 1 — API server
make api

# Terminal 2 — Background worker
make worker
```

Or without Make:

```bash
# Terminal 1
PYTHONPATH=$PWD uvicorn main:app --reload

# Terminal 2
PYTHONPATH=$PWD celery -A worker:celery_app worker --loglevel=info
```

---

## API Documentation

### `POST /analyze`

Upload a financial PDF and submit a query. Returns a job ID immediately — processing happens in the background.

**Request (multipart/form-data):**

| Field | Type | Description |
|---|---|---|
| `file` | `File` | PDF document to analyze |
| `query` | `string` | Question to answer (e.g. `"What are the key risks?"`) |

**Example:**

```bash
curl -X POST http://localhost:8000/analyze \
  -F "file=@data/sample.pdf" \
  -F "query=What are the key risks?"
```

**Response:**

```json
{
  "job_id": "5a34ff46-aa7c-48e1-ae1b-2ca2192cbfdc",
  "status": "queued"
}
```

---

### `GET /results/{job_id}`

Poll for the result of a submitted job.

```bash
curl http://localhost:8000/results/5a34ff46-aa7c-48e1-ae1b-2ca2192cbfdc
```

**Response (completed):**

```json
{
  "job_id": "5a34ff46-aa7c-48e1-ae1b-2ca2192cbfdc",
  "status": "completed",
  "result": "The document outlines several key risks: ...",
  "created_at": "2026-02-27T12:08:14Z",
  "completed_at": "2026-02-27T12:08:27Z"
}
```

**Status lifecycle:** `queued` → `processing` → `completed` | `failed`

---

### `GET /health`

Quick health check confirming the API is live.

```bash
curl http://localhost:8000/health
```

**Response:**

```json
{ "status": "ok" }
```

---

## Bugs Found & Fixed

The original codebase contained **15 bugs** across two categories: deterministic crashes and inefficient/harmful prompts.

---

### Category 1: Deterministic Bugs (Crashes)

#### Bug 1 — Wrong requirements filename in README
**File:** `README.md`
`pip install -r requirement.txt` (missing the `s`) — causes `ERROR: Could not open requirements file`.
**Fix:** Corrected to `requirements.txt`. Also documented the need for lockfile-based install.

---

#### Bug 2 — Wrong `Agent` import path
**File:** `agents.py`
`from crewai.agents import Agent` — in CrewAI 0.130.0, the sub-module no longer exposes `Agent` directly.
**Fix:** `from crewai import Agent`

---

#### Bug 3 — Undefined variable `llm = llm`
**File:** `agents.py`
`llm = llm` was assigned before the variable ever existed — immediate `NameError` on import. The same undefined variable was then passed to every agent, crashing initialization.
**Fix:** Removed entirely. CrewAI reads `OPENAI_API_KEY` from the environment automatically; no manual LLM setup is needed.

---

#### Bug 4 — Wrong keyword `tool` instead of `tools`
**File:** `agents.py`
`Agent(tool=[read_data_tool])` — CrewAI uses strict Pydantic model validation. The correct field name is `tools`.
**Fix:** `Agent(tools=[read_data_tool])`

---

#### Bug 5 — `memory=True` on Agent (unexpected argument)
**File:** `agents.py`
`Agent(memory=True)` caused a Pydantic `ValidationError`. In CrewAI 0.130.0, memory is a `Crew`-level configuration, not per-agent.
**Fix:** Removed `memory=True` from all Agent definitions.

---

#### Bug 6 — Tools missing `@tool` decorator
**File:** `tools.py`
Tools were plain Python functions. CrewAI requires functions decorated with `@tool` to register them as Pydantic `BaseTool` objects that agents can invoke.
**Fix:** Added `@tool` decorator from `crewai.tools`.

---

#### Bug 7 — Tools defined as `async def`
**File:** `tools.py`
CrewAI agents run synchronously by default. An `async def` tool returns an unawaited coroutine — the agent receives garbage and fails silently.
**Fix:** Converted `async def` to `def`.

---

#### Bug 8 — `Pdf` class never imported
**File:** `tools.py`
`read_data_tool` called `Pdf(file_path=path).load()` but `Pdf` was never imported — `NameError` at runtime.
**Fix:** Replaced with `PyPDFLoader` from LangChain: `from langchain_community.document_loaders import PyPDFLoader`.

---

#### Bug 9 — Wrong `@tool` import source
**File:** `tools.py`
`from crewai_tools import tool` — `crewai_tools` is the package of pre-built tools, not the decorator. The decorator lives in `crewai.tools`.
**Fix:** `from crewai.tools import tool`

Also fixed the `SerperDevTool` import here: `from crewai_tools import SerperDevTool` is the **correct** import source for pre-built tools like Serper, and `search_tool = SerperDevTool()` is now properly instantiated and assigned to the `financial_analyst` agent.

---

#### Bug 10 — Variable shadowing (naming collision)
**File:** `main.py`
The imported Task object `analyze_financial_document` was immediately overwritten by the FastAPI route function of the same name. When `run_crew()` passed `tasks=[analyze_financial_document]`, it was passing a FastAPI endpoint function — fatal type error.
**Fix:** Renamed the route handler to `api_analyze_document`.

---

#### Bug 11 — Hardcoded file path, wrong `kickoff` syntax
**File:** `main.py`
`run_crew()` always analyzed `data/sample.pdf` regardless of the user's upload. Also used outdated syntax `kickoff({'query': query})`.
**Fix:** `crew.kickoff(inputs={'query': query, 'file_path': file_path})`, passing the actual uploaded file path.

---

#### Bug 12 — Missing `python-multipart` dependency
**File:** `requirements.txt`
FastAPI requires `python-multipart` to parse `UploadFile` and `Form` fields. Without it, all file upload routes crash with `RuntimeError: Form data requires "python-multipart" to be installed`.
**Fix:** Added `python-multipart` to dependencies.

---

#### Bug 13 — `uvicorn.run(app, reload=True)` — wrong argument type
**File:** `main.py`
Uvicorn's multi-process reloader requires the app as an import string so it can spawn fresh worker processes. Passing the actual `app` object causes an immediate exit.
**Fix:** `uvicorn.run("main:app", reload=True)`

---

#### Bug 14 — Agent ignores uploaded file path, hallucinates filename
**File:** `task.py`
The task description never referenced `{file_path}`, so the agent guessed the filename, received a tool error, and fabricated an answer.
**Fix:** Task description now explicitly passes the path: `"Use the 'Read Financial Document' tool on this exact file: {file_path}"`

---

#### Bug 15 — `verification` task caused infinite agent loop
**File:** `task.py` + `agents.py`
The verification task was assigned to `financial_analyst` with `tools=[read_data_tool]` — the same agent, same tool, same file path as task 1. CrewAI's duplicate-input guard blocked the second call. The agent then spun trying invented file paths until hitting `max_iter`, restarting the cycle. With `max_rpm=5`, a 60-second wait was inserted every 5 calls, making runs appear to hang indefinitely.

**Fix:**
- Changed `verification` task to use the separate `verifier` agent
- Removed `tools=[read_data_tool]` from the verification task — in `Process.sequential`, the verifier automatically receives task 1's output as context, so it never needs to re-read the PDF
- Raised `max_rpm` from `5` → `10`

---

### Category 2: Inefficient & Harmful Prompts

#### Broken agent goals designed to produce hallucinations

**File:** `agents.py`

Two agents had goals **explicitly written to fabricate financial data**:

- **`investment_advisor`** — goal instructed it to *"sell expensive investment products regardless of what the document shows"*, *"make up connections between random financial ratios"*, and include *"fake market research"*.
- **`risk_assessor`** — goal instructed it to *"ignore actual risk factors"* and *"create dramatic risk scenarios"* with no basis in the document.

Both also had `max_iter=1, max_rpm=1` — guaranteeing shallow reasoning and 60-second stalls between every API call.

**Fix:** Rather than deleting these agents and losing the expected "Investment recommendations" and "Risk assessment" features, I **rewrote their `role`, `goal`, and `backstory`** to act as certified professionals who ground every observation strictly in the uploaded document. Their task descriptions were rewritten to enforce document grounding and prohibit fabrication. `max_iter` and `max_rpm` were raised to sane values.

This is the correct resolution: identifying malicious prompt engineering and fixing it — not discarding the feature.

---

#### Broken task descriptions designed to produce fake output

**File:** `task.py`

- **`investment_analysis`** — description instructed the agent to *"make up connections between financial numbers and stock picks"* and recommend *"expensive crypto assets from obscure exchanges"*.
- **`risk_assessment`** — description instructed the agent to *"add fake research from made-up financial institutions"*.

**Fix:** Rewrote both task descriptions to enforce strict document grounding. Agents are now explicitly instructed to cite only data present in the document and never invent figures, institutions, or market comparisons.

---

#### Dead code in `tools.py` — `InvestmentTool` and `RiskTool`

**File:** `tools.py`

`InvestmentTool` and `RiskTool` were defined as async classes returning hardcoded strings and were never assigned to any agent.

**Fix:** Removed entirely. The correct approach is to give the `investment_advisor` and `risk_assessor` agents the core `read_data_tool` directly, allowing them to read source truth from the PDF rather than receiving hardcoded fake strings.

---

#### `max_iter` and `max_rpm` set too low

**File:** `agents.py`
`max_iter=1` gave agents only one reasoning step. `max_rpm=1` inserted a 60-second wait after every single LLM call.
**Fix:** `max_iter=3` (analyst, investment advisor, risk assessor), `max_iter=2` (verifier), `max_rpm=10` for all agents.

---

#### Agent delegation enabled unnecessarily

**File:** `agents.py`
`allow_delegation=True` (CrewAI's default) allows agents to hand off subtasks unpredictably. For a deterministic four-step pipeline, delegation adds non-deterministic routing and unnecessary LLM calls.
**Fix:** `allow_delegation=False` on all agents.

---

## CrewAI Behavior: Why These Bugs Mattered

### The Duplicate Input Guard (Root Cause of the Infinite Loop)

CrewAI tracks every `(tool, input)` pair an agent uses within a task. If the same combination is attempted again, it is blocked:

```
Tool Output: I tried reusing the same input, I must stop using this action input.
```

This guard is designed to prevent infinite loops — but it *caused* one here due to misconfigured tasks:

1. **Task 1** — `financial_analyst` calls `read_data_tool("data/financial_document_abc.pdf")`. Succeeds.
2. **Task 2** — *also assigned to `financial_analyst`* with `tools=[read_data_tool]`. Same path. **Blocked.**
3. Agent invents paths: `/path/to/document.pdf` → error. `./document.pdf` → error. `""` → error.
4. `max_iter` is hit → agent produces a hallucinated final answer.
5. With `max_rpm=5`, every 5th LLM call triggered a **60-second rate-limit pause**, making the loop appear to hang indefinitely.

**The fix:** Verifier uses a separate agent with no tools. CrewAI's sequential mode automatically passes task 1's output as context to task 2 — no PDF re-read required.

### Sequential Mode and Automatic Context Passing

In `Process.sequential`, each task's output is automatically passed as context to the next task. This is why the verifier and — after the analyst summarizes — downstream agents receive structured output without redundantly re-reading the PDF:

```python
verification = Task (
    description="You will receive the financial analysis as context. Verify it.",
    agent=verifier,
    # No tools — verifier reads analyst output, not the PDF
)
```

### Why `allow_delegation=False` Matters

With delegation enabled, agents can reassign subtasks to other agents mid-execution. For a deterministic four-step pipeline, this creates unpredictable routing. Disabling it makes execution deterministic: each agent does exactly its assigned task.

### The `# type: ignore` on Tool Assignment

```python
tools=[read_data_tool],  # type: ignore
```

Static type checkers cannot infer the runtime type transformation applied by `@tool`. The decorator converts a `Callable` into a Pydantic `BaseTool` subclass, but checkers see a false-positive type mismatch. `# type: ignore` is the documented approach when a framework's type stubs are incomplete — it has no effect at runtime.

---

## Tool Allocation & Hallucination Prevention

### The Problem

Even after fixing the prompts on `investment_advisor` and `risk_assessor`, early test runs produced hallucinated numbers — agents claimed a 45% gross margin when the actual figure was 17.2%, or cited a 12% revenue increase when the document showed a decline.

### Root Cause

In `Process.sequential`, agents without tools rely entirely on the previous agent's output as context. Because the Verifier's output is a high-level confirmation rather than a raw data extract, downstream agents lacked the actual numbers and the LLM filled the gap with fabricated figures.

### The Fix

`read_data_tool` is assigned directly to `investment_advisor` and `risk_assessor`. Each agent reads the source document independently and grounds every observation in the raw text. This eliminates data hallucination from context summarization loss.

```
financial_analyst   → read_data_tool + search_tool (market context)
verifier            → no tools (receives analyst output as context)
investment_advisor  → read_data_tool (reads PDF directly for metrics)
risk_assessor       → read_data_tool (reads PDF directly for risk factors)
```

### Why `max_iter=2` for Tool-Using Agents

Setting `max_iter=3` on tool-using agents was observed to cause redundant re-reads: the agent would call `read_data_tool` successfully, then use its remaining iterations to attempt a second call to verify specific figures. CrewAI's duplicate-input guard blocked the second call, causing a mini-loop before `max_iter` terminated it. The fix is `max_iter=2` on agents using `read_data_tool`: one tool call, one final answer.

Task descriptions also include the explicit instruction: `"Use the 'Read Financial Document' tool ONCE on the provided file path."` This prevents the agent from reasoning itself into a redundant re-read.

---

## Dependency Setup & Resolution

The initial `requirements.txt` cannot be installed with a standard `pip install -r requirements.txt` due to ecosystem-level conflicts. This is not a simple version mismatch — it is a structural incompatibility between several large dependency trees that do not currently agree on shared packages.

### The Core Problem: Protobuf Version Split

The most fundamental conflict is a hard split on the `protobuf` major version:

| Ecosystem | Requires |
|---|---|
| OpenTelemetry ≥1.30, mem0ai | `protobuf >= 5` |
| Google AI & Cloud SDKs | `protobuf < 5` (metadata declaration) |

**There is no version of protobuf that satisfies both constraints at the metadata level.** On top of this, `pip`'s SAT resolver fails with `resolution-too-deep` on the full graph due to its size.

### All Conflicts and Their Resolutions

| Issue | Root Cause | Resolution |
|---|---|---|
| `requirement.txt` not found | Typo in README | Corrected to `requirements.txt` |
| `crewai==0.130.0` install fails | Python 3.14+ installed by default on newer macOS; CrewAI requires `<3.14` | Pinned Python to 3.12.2 via pyenv |
| `onnxruntime==1.18.0` | CrewAI requires `1.22.0` — hard conflict | Updated pin to `1.22.0` |
| `pydantic==1.10.13` | CrewAI requires Pydantic `>=2.4` — major version conflict | Migrated to Pydantic v2, removed `pydantic_core` pin |
| `opentelemetry==1.25.0` | CrewAI requires `>=1.30.0` | Aligned to `1.30.0` |
| Protobuf ecosystem split | OpenTelemetry ≥1.30 needs `>=5`; Google SDKs declare `<5` | Pinned to `5.29.6` — Google SDKs function correctly at runtime despite conservative metadata |
| Explicit `click` pin | Clashed with `crewai` and `crewai-tools` version requirements | Removed explicit pin |
| Explicit `google-api-core` pin | `google-ai-generativelanguage` explicitly excludes certain `2.10.x` versions | Removed explicit pin |
| `embedchain` included | Fundamentally incompatible with `crewai==0.130.0` (conflicting `chromadb`, `tiktoken`, `langsmith`) | Removed — CrewAI does not require it |
| `fastapi==0.110.3` | Pulled in an incompatible Starlette version transitively | Upgraded to `fastapi>=0.111,<0.114` |
| `pip` `resolution-too-deep` | Full CrewAI + LangChain + Google graph too large for single-pass solving | Two-phase install (see below) |

### Two-Phase Install Strategy

Because the full graph is too large for `pip` to solve in a single pass, the environment was stabilized in two phases:

```bash
# Phase 1: Install the core framework and let it resolve its internal graph
pip install crewai==0.130.0 crewai-tools==0.47.1

# Phase 2: Install remaining app dependencies WITHOUT re-triggering the resolver
pip install -r requirements.txt --no-deps

# Freeze the verified environment to a lockfile
pip freeze > requirements.lock
```

`--no-deps` in Phase 2 tells pip: *"install exactly what I listed, don't try to re-solve transitive dependencies."* This bypasses the known conflicts while still installing all required packages.

### Installing Going Forward

```bash
# Always use this — never bare pip install -r requirements.txt
pip install -r requirements.lock --no-deps
```

### Runtime Verification

The final environment was validated:

```python
import crewai, chromadb, litellm, openai, google.generativeai, fastapi
# All imports succeed ✓
```

> `pip check` may still show `protobuf <5` warnings from Google packages. These are expected, accepted, and do not indicate runtime failure. Runtime correctness was prioritized over metadata purity.

---

## Bonus: Queue Worker & Database Integration

### Queue Worker (Celery + Redis)

Rather than processing documents synchronously (which would block the HTTP connection for ~15–30 seconds), requests are queued and processed in the background:

```
POST /analyze  →  save file, enqueue job  →  return job_id immediately (< 100ms)
GET /results/{job_id}  →  poll MongoDB for status + result
```

**Start the worker:**

```bash
make worker
# or
celery -A worker:celery_app worker --loglevel=info
```

### Database Integration (MongoDB)

All analysis jobs are persisted in MongoDB with full lifecycle tracking:

```json
{
  "job_id": "uuid",
  "status": "queued | processing | completed | failed",
  "query": "What are the key risks?",
  "file_path": "data/financial_document_abc123.pdf",
  "result": "The document outlines several key risks...",
  "created_at": "2026-02-27T12:08:14Z",
  "completed_at": "2026-02-27T12:08:27Z"
}
```

### Why Two MongoDB Drivers?

| Context | Driver | Reason |
|---|---|---|
| FastAPI routes (`main.py`) | `Motor` (async) | FastAPI runs on an async event loop — a synchronous driver would block the server |
| Celery worker (`worker.py`) | `PyMongo` (sync) | Celery tasks run in forked processes with no event loop — async drivers cause deadlocks |

---

## Project Structure

```
financial-document-analyzer-debug/
├── main.py           # FastAPI app — endpoints, file upload, job queuing
├── worker.py         # Celery task — runs CrewAI crew in background
├── crew.py           # run_crew() — assembles crew and calls kickoff()
├── agents.py         # Agent definitions: financial_analyst, verifier, investment_advisor, risk_assessor
├── task.py           # Task definitions: analyze, verification, investment_analysis, risk_assessment
├── tools.py          # read_data_tool (@tool PDF reader) + search_tool (SerperDevTool)
├── database.py       # Motor (async) MongoDB client + Pydantic job schemas
├── Makefile          # make api / make worker shortcuts
├── .env.example      # Environment variable template
├── requirements.txt  # Direct project dependencies
└── requirements.lock # Frozen, pre-resolved lockfile — always use this for installation
```