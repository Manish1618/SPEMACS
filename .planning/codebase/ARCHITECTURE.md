<!-- refreshed: 2026-09-05 -->
# Architecture

**Analysis Date:** 2026-09-05

## System Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                  Frontend SPA (React 19 + Vite)              │
├───────────┬───────────┬────────────┬─────────────┬──────────┤
│  Graph    │   Map     │  Timeline  │  AI Chat    │ Evidence │
│ Cytoscape │  Leaflet  │  Custom    │ Investigator│  Vault   │
│`components/graph`│`components/map`│`components/timeline`│`components/ai`│`components/evidence`│
└─────┬─────┴─────┬─────┴─────┬──────┴──────┬──────┴─────┬────┘
      │           │           │             │            │
      └───────────┴─────┬─────┴─────────────┴────────────┘
                         ▼
              `frontend/src/lib/api.ts` (fetch wrapper)
                         │
                         ▼  HTTP JSON, CORS "*"
┌─────────────────────────────────────────────────────────────┐
│              FastAPI App  `backend/app/main.py`               │
├───────────┬───────────┬────────────┬─────────────┬──────────┤
│  auth.py  │ cases.py  │  graph.py  │map_timeline │evidence.py│
│           │           │            │  .py        │           │
│  ai.py    │ osint.py  │ ingestion.py│            │           │
└─────┬─────┴─────┬─────┴─────┬──────┴──────┬──────┴─────┬────┘
      │           │           │             │            │
      ▼           ▼           ▼             ▼            ▼
┌─────────────────────────────────────────────────────────────┐
│                     Service Layer (business logic)            │
│ `services/graph_engine.py`  (in-memory NetworkX MultiDiGraph)│
│ `services/ai_investigator.py` (Gemini LLM + scripted demo)   │
│ `services/evidence.py` (SHA-256 + mock blockchain ledger)    │
│ `services/osint.py`  `services/ingestion.py` (seed/parse)    │
└──────────────────────────┬────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Persistence: SQLite via SQLAlchemy ORM `models/entities.py` │
│  File: `backend/spemass.db` (created at import time)          │
│  Blob storage: `backend/storage/` (uploaded docs)             │
└─────────────────────────────────────────────────────────────┘
```

**Important deviation from planning docs:** `PRD.md`/`planning.md` describe Neo4j as the graph store. The actual implementation uses an **in-process NetworkX `MultiDiGraph`** singleton (`knowledge_graph` in `backend/app/services/graph_engine.py`), rebuilt from SQLite rows at startup via `seed_database_and_graph` (`backend/app/services/ingestion.py`). There is no Neo4j dependency, driver, or Cypher anywhere in the codebase. Similarly, "blockchain anchoring" is simulated: `backend/app/services/evidence.py` generates a fake `tx_hash` (`f"0x{uuid.uuid4().hex}{uuid.uuid4().hex}"[:66]`) and stores it in a `BlockchainRecord` SQLite table (`backend/app/models/entities.py`) — there is no real chain, smart contract, or external ledger.

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| FastAPI app bootstrap | Wires routers, CORS, DB table creation, startup seeding | `backend/app/main.py` |
| Config | Env-driven settings (DB URL, Gemini key, JWT secret, storage paths) | `backend/app/core/config.py` |
| Security | JWT encode/decode, password hashing helpers | `backend/app/core/security.py` |
| ORM models | SQLAlchemy table definitions (User, Case, Document, Evidence, CustodyEvent, BlockchainRecord, plus graph-seed entities) | `backend/app/models/entities.py` |
| DB engine/session | SQLAlchemy engine, `SessionLocal`, `get_db` dependency | `backend/app/models/database.py` |
| Pydantic schemas | Request/response DTOs for all routers | `backend/app/schemas/schemas.py` |
| Graph engine | In-memory temporal knowledge graph: entity/relationship CRUD, fuzzy entity resolution, k-hop, shortest path, centrality/hub/bridge analytics, cross-case overlap, anomaly detection (impossible travel) | `backend/app/services/graph_engine.py` |
| AI investigator | Builds context from graph + case data, calls Gemini API live, falls back to scripted/canned "demo" responses for specific known queries | `backend/app/services/ai_investigator.py` |
| Evidence/custody service | SHA-256 hashing, evidence record + custody chain + mock blockchain record creation, tamper simulation/verification | `backend/app/services/evidence.py` |
| OSINT service | Simulated open-source enrichment lookups | `backend/app/services/osint.py` |
| Ingestion/seed service | Seeds SQLite + rebuilds NetworkX graph from `backend/data/synthetic/`, parses uploaded CSV/PDF documents | `backend/app/services/ingestion.py` |
| API routers | Thin controllers per domain, one file per resource | `backend/app/api/{auth,cases,graph,map_timeline,evidence,ai,osint,ingestion}.py` |
| Frontend shell/state | Owns synchronized workspace state (selected node/event, highlights, active tab), fetches data on case switch | `frontend/src/App.tsx` |
| API client | Single fetch-based client hitting `http://localhost:8000/api/v1` (hardcoded, not env-driven) | `frontend/src/lib/api.ts` |
| Graph view | Cytoscape.js network rendering + interactions | `frontend/src/components/graph/CytoscapeGraph.tsx` |
| Map view | Leaflet map of geolocated events | `frontend/src/components/map/InvestigatorMap.tsx` |
| Timeline view | Custom chronological event strip | `frontend/src/components/timeline/InvestigatorTimeline.tsx` |
| AI chat UI | Chat-style interface calling `/api/v1/ai/investigate` | `frontend/src/components/ai/UniversalAIInvestigator.tsx` |
| Evidence UI | Evidence vault, integrity verification, tamper simulation UI | `frontend/src/components/evidence/EvidenceVault.tsx` |

## Pattern Overview

**Overall:** Layered monolith — a single FastAPI backend (routers → services → SQLAlchemy ORM + in-memory graph singleton) paired with a single-page React frontend that composes multiple synchronized visualization "views" into one workspace tab.

**Key Characteristics:**
- Backend has no separate repository/DAO layer; services query SQLAlchemy models directly and also mutate a process-global `knowledge_graph` singleton (`graph_engine.knowledge_graph`).
- Graph state is entirely in-memory (rebuilt from SQLite on every startup/reseed) — not persisted as a graph database; restarting the process without reseeding first loses any graph mutations not written back to SQL.
- The frontend has no routing library; a single `activeTab` string in `App.tsx` state switches between workspace/ai/evidence/analytics/ingestion views. No React Router, no Redux/Zustand — plain `useState`/`useEffect` lifted to the top-level `App` component.
- Cross-view synchronization ("Tri-View": Graph + Map + Timeline) is implemented via shared `selectedNodeId` / `selectedEventId` / `highlightedNodeIds` / `highlightedCoords` state in `App.tsx`, passed down as props and callbacks — not via context or a pub/sub bus.
- AI responses mix a genuine live Gemini API call with hardcoded scripted "canned" narrative responses for specific demo queries (`_build_vikram_swiss_transfer_response`, `_build_vikram_location_response`, `_build_cross_case_response` in `backend/app/services/ai_investigator.py`), indicating this is a demo/hackathon-style system with fallback theatrics rather than a fully generative pipeline.

## Layers

**API/Routing layer:**
- Purpose: HTTP request parsing, auth dependency injection, response shaping via Pydantic
- Location: `backend/app/api/`
- Contains: One router module per domain (`auth.py`, `cases.py`, `graph.py`, `map_timeline.py`, `evidence.py`, `ai.py`, `osint.py`, `ingestion.py`)
- Depends on: Service layer, `models/database.get_db`, `schemas/schemas.py`
- Used by: `backend/app/main.py` (registers all routers under `settings.API_V1_STR` = `/api/v1`)

**Service layer:**
- Purpose: Business logic — graph algorithms, AI orchestration, evidence integrity, OSINT simulation, data seeding
- Location: `backend/app/services/`
- Contains: `graph_engine.py`, `ai_investigator.py`, `evidence.py`, `osint.py`, `ingestion.py`
- Depends on: `models/entities.py` (SQLAlchemy), `core/config.py` (Gemini key), `networkx`, `rapidfuzz`
- Used by: API routers

**Persistence layer:**
- Purpose: Relational storage of cases, documents, evidence, custody, blockchain-simulation records, users
- Location: `backend/app/models/` (`database.py` engine/session, `entities.py` table definitions)
- Contains: SQLite (default) via SQLAlchemy ORM; swappable via `DATABASE_URL` env var
- Depends on: `core/config.py`
- Used by: Service layer and routers via `get_db` dependency

**Frontend view layer:**
- Purpose: Renders workspace UI and domain-specific visualizations
- Location: `frontend/src/components/{graph,map,timeline,ai,evidence,analytics,ingestion,osint,documents,court,resolution,layout}/`
- Contains: One (mostly) top-level component per feature area, each a `.tsx` file named after its feature (e.g. `CytoscapeGraph.tsx`, `InvestigatorMap.tsx`)
- Depends on: `frontend/src/lib/api.ts`, `frontend/src/types/index.ts`
- Used by: `frontend/src/App.tsx`

## Data Flow

### Primary Request Path (Workspace load)

1. `App.tsx` mounts, `useEffect` calls `loadCaseData(activeCaseId)` (`frontend/src/App.tsx:62`)
2. `loadCaseData` fires 5 parallel fetches via `api.getCases/getGraph/getMapEvents/getTimeline/getEvidence` (`frontend/src/lib/api.ts`)
3. Each hits a FastAPI router (e.g. `GET /api/v1/graph/case/{case_id}` → `backend/app/api/graph.py:10`)
4. Router calls into `graph_engine.knowledge_graph` (in-memory) or queries SQLAlchemy models directly, returns Pydantic response models
5. Frontend sets `graphData`/`mapEvents`/`timelineEvents`/`evidenceList` state, which cascades down as props to `CytoscapeGraph`, `InvestigatorMap`, `InvestigatorTimeline`, `EvidenceVault`

### Tri-View Selection Sync

1. User clicks a node in `CytoscapeGraph` → `onSelectNode` callback → `handleSelectGraphNode` in `App.tsx:80`
2. Handler sets `selectedNodeId`, looks up `mapEvents` whose `related_entities` include the node id, sets `highlightedCoords`/`selectedEventId`
3. `InvestigatorMap` and `InvestigatorTimeline` receive the updated `selectedEventId`/`highlightedCoords` as props and re-render highlighted state
4. Symmetric handlers exist for map-event selection (`handleSelectMapEvent`) and timeline-event selection (`handleSelectTimelineEvent`), each cross-updating the other two views

### AI Investigation Flow

1. User submits a query in `UniversalAIInvestigator.tsx` → POST `/api/v1/ai/investigate` (`backend/app/api/ai.py:10`)
2. `UniversalAIInvestigator` service class (`backend/app/services/ai_investigator.py:10`) builds context from the graph/case, then either matches a scripted demo scenario or calls `_call_live_gemini` (`ai_investigator.py:174`) using `settings.GEMINI_API_KEY`
3. Response includes narrative text plus a `HighlightAction` payload (node ids / coordinates / event ids)
4. Frontend calls `onTriggerVisualHighlight` (`App.tsx:134`) which sets highlight state and switches `activeTab` back to `'workspace'`, visually driving the Graph+Map+Timeline from an AI answer

### Evidence Integrity Flow

1. Upload/ingest creates an `Evidence` row with a computed SHA-256 (`calculate_sha256` in `backend/app/services/evidence.py:9`) and a fabricated `blockchain_tx_id`/`BlockchainRecord`
2. `POST /api/v1/evidence/{id}/verify` (`backend/app/api/evidence.py:28`) recomputes the hash from stored content and compares against the stored hash and the `BlockchainRecord` hash (`evidence.py:74`)
3. `POST /api/v1/evidence/{id}/simulate-tamper` deliberately corrupts stored content/hash to demonstrate detection; `restore-clean` reverts it — this is a demo mechanism, not a security feature
4. Every action appends a `CustodyEvent` row for audit trail (chain-of-custody)

**State Management:**
- Backend: process-global `knowledge_graph` singleton in `graph_engine.py` (module-level instance, not per-request) plus SQLAlchemy session-scoped DB state
- Frontend: all shared state lives in `App.tsx` via `useState`; no global store library

## Key Abstractions

**`TemporalKnowledgeGraph`** (`backend/app/services/graph_engine.py:6`):
- Purpose: Wraps a NetworkX `MultiDiGraph` to represent entities/relationships with case scoping, confidence scores, and evidence links
- Examples: single instance `knowledge_graph` exported at module bottom (`graph_engine.py:290`)
- Pattern: Singleton service object mutated directly by routers/services rather than instantiated per request

**Evidence + CustodyEvent + BlockchainRecord triad** (`backend/app/models/entities.py`):
- Purpose: Models chain-of-custody with a simulated tamper-evidence mechanism
- Examples: `Evidence` (57), `CustodyEvent` (77), `BlockchainRecord` (92)
- Pattern: Every mutating action on evidence writes a `CustodyEvent`; integrity is "verified" by comparing three hash sources (stored, recomputed, blockchain-record)

**Synchronized Workspace State** (`frontend/src/App.tsx`):
- Purpose: Cross-links Graph/Map/Timeline selection and highlighting without a shared state library
- Examples: `selectedNodeId`, `selectedEventId`, `highlightedNodeIds`, `highlightedCoords`
- Pattern: Lifted state + prop drilling; each view's `onSelect*` callback fans out updates to the other views' props

## Entry Points

**Backend HTTP server:**
- Location: `backend/app/main.py`
- Triggers: `uvicorn app.main:app` (also runnable directly via `python -m app.main`, `main.py:61`)
- Responsibilities: Creates DB tables, registers routers, seeds DB+graph on startup event, exposes `/` and `/health`

**Frontend SPA:**
- Location: `frontend/src/main.tsx` → renders `App` (`frontend/src/App.tsx`)
- Triggers: `npm run dev` (Vite dev server) or built `frontend/dist/` served statically
- Responsibilities: Bootstraps React root, mounts single-page workspace shell

## Architectural Constraints

- **Threading:** Backend runs single-process FastAPI/uvicorn; SQLite configured with `check_same_thread: False`, but the in-memory `knowledge_graph` singleton is not lock-protected — concurrent requests mutating it (e.g. `merge-entities`, ingestion) can race.
- **Global state:** `knowledge_graph` singleton in `backend/app/services/graph_engine.py:290` is shared, mutable, process-wide state; any request handler can mutate it directly with no transactional boundary tying it to the SQL DB.
- **Hardcoded API base URL:** `frontend/src/lib/api.ts` hardcodes `http://localhost:8000/api/v1` — no environment-based configuration for different deploy targets.
- **CORS wide open:** `backend/app/main.py` sets `allow_origins=["*"]` with `allow_credentials=True`, which is invalid/insecure in production (browsers reject wildcard origin + credentials combos, and any tightening will require explicit origin config).
- **No Neo4j / no real blockchain:** Despite naming and planning docs, graph persistence is in-memory NetworkX (lost on restart unless reseeded from SQLite) and "blockchain" is a locally generated fake transaction hash stored in SQLite — do not assume distributed-ledger or graph-DB guarantees anywhere in this codebase.

## Anti-Patterns

### Mutable global singleton bypassing DB transactions

**What happens:** `graph_engine.knowledge_graph` is mutated directly from multiple routers (`graph.py`, `ingestion.py`) independent of SQLAlchemy transaction commits.
**Why it's wrong:** A failed DB write can leave SQLite and the in-memory graph out of sync, with no rollback coupling between them.
**Do this instead:** Treat SQLite as the source of truth and always rebuild affected subgraphs from committed rows, or introduce a lock/queue around graph mutations, before assuming graph state matches persisted state.

### Scripted "AI" fallback masquerading as generative output

**What happens:** `ai_investigator.py` contains hardcoded response builders (`_build_vikram_swiss_transfer_response`, `_build_vikram_location_response`, `_build_cross_case_response`) returned for specific known demo queries instead of always invoking Gemini.
**Why it's wrong:** Behavior is non-deterministic depending on exact query phrasing matched against scripted cases vs. falling through to the live LLM call, which will surprise anyone extending the AI feature expecting uniform LLM-backed behavior.
**Do this instead:** When adding new AI capabilities, check `ai_investigator.py:14` (`investigate`) first to see whether a query matches a scripted branch before assuming your prompt reaches Gemini.

## Error Handling

**Strategy:** Mostly implicit — FastAPI's default exception handling (unhandled exceptions become 500s); a few `try/except Exception: pass` swallow-and-continue blocks in graph anomaly detection (`graph_engine.py:235`).

**Patterns:**
- Frontend: `try/catch` around API calls in `App.tsx`, logs to `console.error`, does not surface user-facing error UI in most paths
- Backend: services return structured "not found" dict shapes (e.g. `{"path_found": False, ...}`) rather than raising HTTP errors in some graph endpoints; other endpoints presumably raise `HTTPException` (verify per-router as needed)

## Cross-Cutting Concerns

**Logging:** No structured logging framework detected; relies on default uvicorn access logs and `console.error` on the frontend.
**Validation:** Pydantic schemas (`backend/app/schemas/schemas.py`) validate request/response shapes at the API boundary.
**Authentication:** JWT-based (`backend/app/core/security.py`, `backend/app/api/auth.py`), but CORS/global-state issues above mean auth is not deeply enforced across all routers — verify per-route dependencies before assuming protection.

---

*Architecture analysis: 2026-09-05*
