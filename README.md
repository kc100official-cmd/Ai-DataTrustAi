# DataTrust AI

> **Tagline:** “Ask your data. Verify every answer.”  
> **Graph-Powered, Self-Validating Intelligence Agent for Messy Databases**

DataTrust AI is a full-stack AI data-intelligence platform built to explore messy relational databases and unstructured compliance documents, understand natural-language questions, route queries across 6 specialized strategies, execute safe read-only SQL with bounded schema repair, reason over entity relationships, and expose exact **Evidence Path Replay** provenance traces for every claim.

---

## 1. Architecture Overview

```
+-----------------------------------------------------------------------------------+
|                           DataTrust AI Frontend (React + TS)                      |
|  [Overview & 3D Core]  [Ask Workspace]  [Knowledge Graph]  [Communities]          |
|  [Routing Inspector]   [Database Explorer]                 [BIRD Evaluation]      |
+-----------------------------------------+-----------------------------------------+
                                          | REST JSON API (/api/*)
+-----------------------------------------v-----------------------------------------+
|                        FastAPI Intelligence Backend (Python)                      |
|                                                                                   |
|  1. Intelligent Question Router (router_engine.py)                                |
|     -> SQL | Graph | Semantic | Hybrid | Clarification | Verified Abstention      |
|                                                                                   |
|  2. Safe NL-to-SQL & Bounded Repair Engine (sql_engine.py + database.py)          |
|     -> SQLite URI mode=ro + PRAGMA query_only=ON + sqlite3.set_authorizer         |
|     -> Schema introspection, EXPLAIN QUERY PLAN validation, bounded repair (<=2)  |
|                                                                                   |
|  3. Knowledge Graph & Entity Resolution Engine (graph_engine.py)                  |
|     -> Persistent SQLite graph store (entities, relationships, documents)         |
|     -> Confirmed Fact vs. Inferred Rule separation, reversible alias merging      |
|                                                                                   |
|  4. Louvain Community Detection (community_engine.py)                             |
|     -> NetworkX Louvain modularity Q, internal density, scoped community Q&A      |
|                                                                                   |
|  5. Claim-Level Answer Validator & Evidence Path Replay (validation_engine.py)    |
|     -> Supported | Partially supported | Conflicting evidence |                   |
|        Needs clarification | Insufficient evidence                                |
|                                                                                   |
|  6. BIRD Text-to-SQL Benchmark Pipeline (bird_evaluator.py)                       |
|     -> Enforces <= 8.0B parameter open-weight model restriction                   |
+-----------------------------------------------------------------------------------+
```

---

## 2. Quick Start (Windows PowerShell)

### Option A: One-Command Development Startup
From the repository root in PowerShell:
```powershell
.\start-dev.ps1
```
On first use, install the backend dependencies in a local virtual environment:
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

The script initializes the sample SQLite databases and persistent Knowledge Graph, launches the FastAPI backend on `http://127.0.0.1:8001`, and starts the Vite React frontend on `http://localhost:5173`. The VS Code task **Run DataTrust AI (localhost)** starts the same script.

### Option B: Separate Terminal Commands

**1. Initialize Sample Databases & Knowledge Graph (Optional — also runs automatically on backend startup):**
```powershell
python scripts/init_db.py
```

**2. Start the FastAPI Backend:**
```powershell
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8001 --reload
```

**3. Start the React Frontend:**
```powershell
Set-Location frontend
pnpm install
pnpm run dev
```
Open `http://localhost:5173` in your browser.

---

## 3. Sample Datasets Included

DataTrust AI initializes two realistic, local SQLite databases and a persistent Knowledge Graph (`backend/data/graph_store.db`):

1. **`enterprise_supply_ops` (`enterprise_supply_ops.db`)**
   - **Tables:** `regions`, `facilities`, `vendors`, `procurement_contracts`, `shipments`, `quality_incidents`
   - **Intentional Real-World Messiness:**
     - Duplicate vendor aliases (`Apex Labs` vs `Apex Laboratories Inc.`, `Vortex Semi` vs `Vortex Semiconductors`) for testing reversible **Entity Resolution**.
     - Missing (`NULL`) fields (`facilities.headcount` on `FAC-401`, `vendors.compliance_score` on `VND-05`).
     - Cross-source conflict between legacy ERP table `procurement_contracts:CNT-904` (`Helios Energy Systems` listed as `ACTIVE`) and Compliance Directive `DOC-2026-04` (`SUSPENDED` following critical incident `INC-701 Transformer Thermal Failure`).
     - Ambiguous entity collision (`"Mercury"` matching both `Mercury Logistics` vendor and `Project Mercury` optical transceiver product).

2. **`california_schools_bird_demo` (`california_schools_bird_demo.db`)**
   - **Tables:** `schools`, `frpm` (Free or Reduced-Price Meals), `satscores`
   - **Features:** Matches the BIRD benchmark California Schools domain (`CDSCode`, `Charter`, `AvgScrMath`, `EligibleFreeRate_K12`) paired with policy brief `DOC-EDU-101` (`School A (Horizon STEM Academy) → LOCATED_IN → Region North`).

---

## 4. Running Automated Tests

### Backend Test Suite (Pytest)
Tests schema discovery, SQL read-only authorizer & injection/DDL rejection, bounded column repair, empty/NULL result validation, Knowledge Graph ingestion, Evidence Path Replay, reversible Entity Resolution (`merge` & `unmerge`), Louvain community detection, 6-way routing, conflict detection, abstention, and the `<= 8B` BIRD benchmark restriction:
```powershell
python -m pytest backend/tests/test_datatrust.py -v
```

### Frontend Test Suite & Production Build (Vitest + TypeScript + Vite)
```powershell
Set-Location frontend
pnpm test
pnpm run build
```

---

## 5. BIRD Benchmark Configuration & `<= 8B` Open-Weight Restriction

DataTrust AI includes a configurable BIRD evaluation pipeline (`backend/app/bird_evaluator.py` and the **BIRD Evaluation** screen):

- **Parameter Ceiling Enforcement:** The evaluation pipeline enforces that any model used in the restricted benchmark workflow must be an open-weight model with **at most 8.0 billion parameters** (`DATATRUST_LLM_PARAM_BILLIONS <= 8.0`). Attempting to run an evaluation with a larger model (e.g., `70B`) is automatically rejected with HTTP `400`.
- **Running with Official BIRD Data:**
  1. Obtain the official BIRD benchmark dataset (`dev.json` or `mini_dev_sqlite.json` and `dev_databases/<db_id>/<db_id>.sqlite`).
  2. Set `DATATRUST_BIRD_DATASET_PATH=C:\path\to\bird_dev` in `.env` (or enter the path in the **BIRD Evaluation** UI under `Official BIRD Dataset Path`).
  3. Trigger a run and export results as machine-readable JSON or CSV.
- **Local Smoke-Test Suite:** When external BIRD files are not configured, you can run the clearly labeled `bird_smoke_synthetic` suite to verify the end-to-end execution accuracy (`EX`) harness locally. DataTrust AI never claims an official benchmark score from synthetic smoke tests.

---

## 6. SQL Security Architecture & Limitations

DataTrust AI enforces defense-in-depth for SQL execution (`backend/app/database.py` and `backend/app/sql_engine.py`):
1. **OS / Driver Read-Only Mode:** Connections open SQLite files via URI `file:...?mode=ro`.
2. **Connection Pragma Lock:** `PRAGMA query_only = ON` is executed on every connection.
3. **Engine-Level C Authorizer Hook:** `conn.set_authorizer(_read_only_authorizer)` whitelists only `SQLITE_SELECT`, `SQLITE_READ`, and `SQLITE_FUNCTION`, denying `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `PRAGMA`, `ATTACH`, and access to internal metadata tables (`query_history`, `evaluation_runs`).
4. **Wall-Clock Progress Timeout & Row Limits:** `conn.set_progress_handler` aborts queries exceeding `DATATRUST_SQL_TIMEOUT_SECONDS` (`5.0s`), and results are capped at `DATATRUST_SQL_MAX_ROWS` (`500`).

*Security Limitation Note:* While SQLite's C-level `set_authorizer` and `mode=ro` file descriptors provide strong read-only isolation for local SQLite databases, production deployments connecting to networked RDBMS instances (PostgreSQL, MySQL, Snowflake) should additionally use dedicated read-only database roles, network egress policies, and container sandboxing.

---

## 7. Troubleshooting

- **LLM / Ollama Endpoint Not Running:** DataTrust AI works out of the box without any external API keys or local GPU servers. When `DATATRUST_LLM_ENABLED=false` (default) or the endpoint is unreachable, the platform transparently uses its deterministic schema-grounded SQL compiler and TF-IDF lexical retrieval fallback.
- **Resetting Sample Databases:** Delete `backend/data/*.db` and run `python scripts/init_db.py` to restore a clean initial state.
