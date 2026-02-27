# Bug Log — Full Detail

This document preserves the full explanation for each of the 17 bugs fixed in this project. For a summary table, see [README.md](README.md#bugs-fixed).

---

## Category 1 — Crashes & Hard Failures

---

**Bug 1 — Wrong filename in README** · `README.md`

`pip install -r requirement.txt` (missing the `s`) fails immediately with `ERROR: Could not open requirements file`.

Fix: corrected to `requirements.txt`. Also documented the lockfile-based install.

---

**Bug 2 — Wrong Agent import path** · `agents.py`

`from crewai.agents import Agent` — this sub-module no longer exposes `Agent` directly in 0.130.0.

Fix: `from crewai import Agent`

---

**Bug 3 — Undefined variable assignment** · `agents.py`

`llm = llm` was written before `llm` was ever defined — immediate `NameError` on import. The same undefined variable was then passed to every agent via `llm=llm`, crashing all four agent initializations.

Fix: removed entirely. CrewAI reads `OPENAI_API_KEY` from the environment automatically — no manual LLM setup needed.

---

**Bug 4 — Wrong field name on Agent** · `agents.py`

`Agent(tool=[...])` — CrewAI uses strict Pydantic validation and the field is `tools`, not `tool`.

Fix: `Agent(tools=[read_data_tool, search_tool])`

---

**Bug 5 — `memory=True` on Agent** · `agents.py`

Caused a Pydantic `ValidationError` on both `financial_analyst` and `verifier` — memory is a `Crew`-level config in 0.130.0, not per-agent.

Fix: removed `memory=True` from all Agent definitions.

---

**Bug 6 — Tools not decorated with `@tool`** · `tools.py`

`read_data_tool` was defined inside a plain class (`FinancialDocumentTool`) with no decorator. CrewAI requires `@tool` to register a function as a `BaseTool` object that agents can actually invoke.

Fix: removed the class wrapper, added `@tool` decorator from `crewai.tools`.

---

**Bug 7 — Tools defined as `async def`** · `tools.py`

CrewAI agents run synchronously. An `async def` tool returns an unawaited coroutine — the agent receives garbage and fails silently.

Fix: converted `read_data_tool` to a regular `def`.

---

**Bug 8 — `Pdf` class never imported** · `tools.py`

`read_data_tool` called `Pdf(file_path=path).load()` but `Pdf` was never imported anywhere — `NameError` at runtime.

Fix: replaced with `PyPDFLoader` from LangChain (`from langchain_community.document_loaders import PyPDFLoader`).

---

**Bug 9 — `@tool` decorator imported from the wrong package** · `tools.py`

`from crewai_tools import tools` — `crewai_tools` is the package of pre-built tools (like Serper), not where the `@tool` decorator lives.

Fix: `from crewai.tools import tool` for the decorator. `SerperDevTool` correctly stays as `from crewai_tools import SerperDevTool` — that's the right package for pre-built tools.

---

**Bug 10 — Variable name collision in `main.py`** · `main.py`

The FastAPI route was named `async def analyze_financial_document` — the same name as the imported Task object from `task.py`. The function definition overwrote the import, so when `run_crew()` passed `tasks=[analyze_financial_document]`, it was passing a FastAPI endpoint function instead of a Task — fatal type error.

Fix: renamed the route handler to `api_financial_document`.

---

**Bug 11 — Hardcoded file path, outdated kickoff syntax** · `main.py`

`run_crew()` always analyzed `data/sample.pdf` regardless of the user's upload. Also used old syntax `financial_crew.kickoff({'query': query})` which doesn't pass `file_path` at all.

Fix: `crew.kickoff(inputs={'query': query, 'file_path': file_path})`, passing the actual uploaded file. Moved `run_crew()` to `crew.py` for cleaner separation.

---

**Bug 12 — Missing `python-multipart`** · `requirements.txt`

FastAPI requires this package to parse `UploadFile` and `Form` fields. Without it, every file upload crashes with `RuntimeError: Form data requires "python-multipart" to be installed`.

Fix: added to dependencies.

---

**Bug 13 — Wrong argument type to `uvicorn.run`** · `main.py`

`uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)` — the multi-process reloader needs the app as an import string so it can spawn fresh worker processes. Passing the live object causes an immediate exit.

Fix: `uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)`

---

**Bug 14 — Agent never received the uploaded file path** · `task.py`

Task descriptions didn't reference `{file_path}`, so agents guessed filenames, got tool errors, then fabricated answers as if they'd read the document.

Fix: all task descriptions that need the document now explicitly include `"Use the 'Read Financial Document' tool ONCE to read the document at {file_path}."` Task inputs are passed via `crew.kickoff(inputs={..., 'file_path': file_path})`.

---

**Bug 15 — Verification task caused an infinite loop** · `task.py` + `agents.py`

This is the bug that made runs appear to hang for minutes. Here's exactly what happened:

1. Task 1 — `financial_analyst` calls `read_data_tool("data/financial_document_abc.pdf")`. Succeeds.
2. Task 2 (verification) — **also assigned to `financial_analyst`**, also with `tools=[read_data_tool]`, same file path. CrewAI's duplicate-input guard blocks it: *"I tried reusing the same input, I must stop using this action input."*
3. The agent tries inventing paths to work around the block — `/path/to/document.pdf`, `./document.pdf`, `""` — all errors.
4. `max_iter` is hit. Agent produces a hallucinated final answer from nothing.
5. With `max_rpm=5`, every 5th LLM call triggered a 60-second rate-limit pause — making everything look frozen.

Fix: verification task reassigned to the separate `verifier` agent with no tools. In `Process.sequential`, task 1's output is automatically passed as context to task 2 — the verifier reads the analyst's answer directly without touching the PDF. `max_rpm` raised from 5 → 10.

---

**Bug 16 — Relative file path breaks in Celery worker** · `main.py`

*Commit `5a00ce46`* — file not found. The uploaded file was saved as `data/financial_document_xxx.pdf` using a relative path. Uvicorn and Celery have different working directories, so by the time the Celery worker tried to open the file, the relative path resolved to a location where the file didn't exist.

Fix: wrap the save path in `os.path.abspath()` in `main.py`.

```python
# Before
file_path = f"data/financial_document_{job_id}.pdf"

# After
file_path = os.path.abspath(f"data/financial_document_{job_id}.pdf")
```

---

**Bug 17 — Duplicate-read guard stalls `investment_advisor` and `risk_assessor`** · `agents.py` + `task.py`

*Commit `2362e353`* — the PDF read succeeded perfectly on iteration 1 for `investment_advisor`. But then the agent tried to call `read_data_tool` a second time to search for specific risk factors within what it had already read. The duplicate-input guard blocked it: *"I tried reusing the same input."*

With `max_iter=2`, there was no iteration left to recover — so the agent looped indefinitely, burning RPM tokens once per minute.

Fix: raised `max_iter` to 4 on `financial_analyst` and 3 on `investment_advisor`/`risk_assessor` to give agents room to recover. Added an explicit instruction to task descriptions: `"Do not call the tool a second time — all the information you need is in the first read."` This prevents the second call from ever being attempted.


Here's the entry in exact format:

---

**Bug 18 — File cleanup only runs on success** · `worker.py`

`os.remove()` was placed inside the `try` block after `_set_done()`. If the Celery task raised an exception, execution jumped to `except` and returned — the cleanup code was never reached. Every failed job left its uploaded PDF on disk permanently.

Fix: moved `os.remove()` to a `finally` block so the file is deleted regardless of whether the task succeeded or failed.

```python
# Before
        _set_done(job_id, result)
        if os.path.exists(file_path):
            os.remove(file_path)

    except Exception as e:
        _set_failed(job_id, str(e))
        raise

# After
        _set_done(job_id, result)

    except Exception as e:
        _set_failed(job_id, str(e))
        raise

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
```


---

## Category 2 — Broken & Harmful Prompts

---

**Broken agent goals written to hallucinate** · `agents.py`

`investment_advisor` had a goal telling it to *"sell expensive investment products regardless of what the financial document shows"*, *"make up connections between random financial ratios"*, and include *"fake market research"*. Its backstory claimed it *"learned investing from Reddit posts and YouTube influencers"* and that *"SEC compliance is optional"*.

`risk_assessor` was told to *"ignore actual risk factors and create dramatic risk scenarios"* and that *"market regulations are just suggestions"*.

Both also had `max_iter=1, max_rpm=1` — one reasoning step total, and a 60-second stall after every single API call.

Fix: rewrote both agents' `role`, `goal`, and `backstory` to behave as certified professionals grounding every observation in the uploaded document. `max_iter` raised to 3, `max_rpm` raised to 10 for all agents.

---

**Broken task descriptions written to produce fake output** · `task.py`

All four tasks in the original were assigned to `financial_analyst` — none of the other agents were used at all.

`investment_analysis` told the agent to *"make up connections between financial numbers and stock picks"*, recommend *"expensive crypto assets from obscure exchanges"*, and include *"financial websites that definitely don't exist"*.

`risk_assessment` told it to *"add fake research from made-up financial institutions"* and *"suggest risk models that don't actually exist"*.

`verification` told the agent to *"just say it's probably a financial document even if it's not"* and to *"hallucinate financial terms"*.

Fix: rewrote all task descriptions to enforce strict document grounding. Each task is now assigned to its dedicated agent. Agents are explicitly told to cite only data present in the document.

---

**Dead code — `InvestmentTool` and `RiskTool`** · `tools.py`

These were async class methods returning hardcoded placeholder strings and were never assigned to any agent.

Fix: removed. `investment_advisor` and `risk_assessor` receive `read_data_tool` directly at the agent level and read from the actual PDF.

---

**`max_iter` and `max_rpm` set too low** · `agents.py`

Every agent had `max_iter=1` (one reasoning step — nearly guaranteed shallow output) and `max_rpm=1` (a 60-second stall between every single API call).

Fix: `max_iter` raised to 3–4 and `max_rpm` raised to 10 across all agents.

---

**Delegation enabled unnecessarily** · `agents.py`

`allow_delegation=True` on the original agents (CrewAI's default) lets agents hand work off to each other mid-task unpredictably. For a deterministic four-step sequential pipeline this adds non-deterministic routing and extra LLM calls.

Fix: `allow_delegation=False` on all agents.

