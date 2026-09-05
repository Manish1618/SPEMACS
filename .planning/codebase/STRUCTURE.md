# Codebase Structure

**Analysis Date:** 2026-09-05

## Directory Layout

```
Spemacs/
├── PRD.md                     # Original product requirements (aspirational; not fully implemented)
├── planning.md                 # Original architecture plan (mentions Neo4j, Next.js — see note below)
├── README.md
├── backend/                    # Python FastAPI service
│   ├── app/
│   │   ├── main.py             # App factory, router registration, startup seeding
│   │   ├── api/                 # HTTP routers, one file per domain
│   │   │   ├── auth.py
│   │   │   ├── cases.py
│   │   │   ├── graph.py
│   │   │   ├── map_timeline.py
│   │   │   ├── evidence.py
│   │   │   ├── ai.py
│   │   │   ├── osint.py
│   │   │   └── ingestion.py
│   │   ├── core/
│   │   │   ├── config.py       # Settings (env-driven), Pydantic BaseSettings
│   │   │   └── security.py     # JWT + password hashing
│   │   ├── models/
│   │   │   ├── database.py     # SQLAlchemy engine, SessionLocal, get_db dependency
│   │   │   └── entities.py     # ORM table definitions
│   │   ├── schemas/
│   │   │   └── schemas.py      # Pydantic request/response DTOs (all routers)
│   │   └── services/
│   │       ├── graph_engine.py     # In-memory NetworkX knowledge graph + analytics
│   │       ├── ai_investigator.py  # Gemini-backed + scripted AI investigator
│   │       ├── evidence.py         # SHA-256 hashing, mock blockchain, custody chain
│   │       ├── osint.py            # Simulated OSINT enrichment
│   │       └── ingestion.py        # Seeds DB+graph, parses uploaded documents
│   ├── data/
│   │   └── synthetic/          # Seed dataset (cases, entities, events) loaded at startup
│   └── storage/                # Uploaded/generated evidence files (created at runtime)
└── frontend/                   # Vite + React 19 SPA (TypeScript)
    ├── src/
    │   ├── main.tsx             # React root bootstrap
    │   ├── App.tsx              # Top-level shell owning all synchronized workspace state
    │   ├── App.css / index.css  # Global styles (Tailwind)
    │   ├── lib/
    │   │   └── api.ts           # Fetch-based API client (hardcoded localhost:8000 base URL)
    │   ├── types/
    │   │   └── index.ts         # Shared TS types (Case, GraphData, MapEvent, TimelineEvent, etc.)
    │   └── components/
    │       ├── layout/          # Header/nav (`Header.tsx`)
    │       ├── graph/           # Cytoscape network graph (`CytoscapeGraph.tsx`)
    │       ├── map/             # Leaflet map (`InvestigatorMap.tsx`)
    │       ├── timeline/        # Chronological event strip (`InvestigatorTimeline.tsx`)
    │       ├── ai/              # AI chat investigator (`UniversalAIInvestigator.tsx`)
    │       ├── evidence/        # Evidence vault UI (`EvidenceVault.tsx`)
    │       ├── analytics/       # Graph analytics panel (`AnalyticsPanel.tsx`)
    │       ├── ingestion/       # File upload / reseed UI (`IngestionHub.tsx`)
    │       ├── osint/           # OSINT enrichment modal (`OSINTModal.tsx`)
    │       ├── documents/       # Document viewer modal (`DocumentViewerModal.tsx`)
    │       ├── court/           # Court dossier export modal (`CourtDossierModal.tsx`)
    │       └── resolution/      # Entity merge/resolution modal (`EntityResolutionModal.tsx`)
    ├── public/                  # Static assets served as-is
    └── dist/                    # Vite production build output (generated, committed — verify .gitignore)
```

## Directory Purposes

**`backend/app/api/`:**
- Purpose: HTTP boundary — one router module per resource domain
- Contains: FastAPI `APIRouter` instances, route handlers, dependency injection of `get_db`
- Key files: `graph.py` (network queries/analytics), `ai.py` (AI investigator endpoint), `evidence.py` (integrity verification/tamper simulation), `ingestion.py` (upload + reseed)

**`backend/app/services/`:**
- Purpose: All business logic; routers stay thin and delegate here
- Contains: Graph algorithms (`graph_engine.py`), AI orchestration (`ai_investigator.py`), evidence/custody/blockchain-simulation logic (`evidence.py`), OSINT simulation (`osint.py`), seeding/parsing (`ingestion.py`)
- Key files: `graph_engine.py` exports the process-global `knowledge_graph` singleton used across the whole graph feature set

**`backend/app/models/`:**
- Purpose: Database access layer
- Contains: `database.py` (engine/session setup), `entities.py` (all SQLAlchemy table classes: `User`, `Case`, `Document`, `Evidence`, `CustodyEvent`, `BlockchainRecord`, plus any graph-seed entity tables)
- Generated: `backend/spemass.db` SQLite file is created here at import time via `Base.metadata.create_all`

**`backend/data/synthetic/`:**
- Purpose: Seed/demo dataset used to populate SQLite + the in-memory graph on every startup and on `/ingestion/reseed`
- Contains: Structured synthetic case data (CSV/JSON — inspect contents before modifying seeding logic)

**`backend/storage/`:**
- Purpose: Runtime storage for uploaded evidence documents
- Generated: Yes (created by `settings.STORAGE_DIR.mkdir(...)` in `core/config.py`)
- Committed: No — treat as runtime data directory

**`frontend/src/components/`:**
- Purpose: One directory per feature/domain, each holding the primary component(s) for that feature area
- Naming: Directory name matches the domain (`graph`, `map`, `timeline`, `evidence`, `ai`, `analytics`, `ingestion`, `osint`, `documents`, `court`, `resolution`, `layout`)
- Pattern: Mostly one main `.tsx` file per directory named after the component (PascalCase), not further subdivided into subcomponents/hooks/styles files

**`frontend/src/lib/`:**
- Purpose: Cross-cutting frontend utilities
- Contains: `api.ts`, the single fetch client for all backend calls
- Key files: `api.ts` — add new backend calls here as additional methods on the exported `api` object

**`frontend/src/types/`:**
- Purpose: Central TypeScript type definitions shared across all components
- Contains: `index.ts` with `Case`, `GraphData`, `GraphNode`, `MapEvent`, `TimelineEvent`, `EvidenceItem`, `HighlightAction`, etc.

## Key File Locations

**Entry Points:**
- `backend/app/main.py`: FastAPI app creation, router registration, startup hook
- `frontend/src/main.tsx`: React root render
- `frontend/src/App.tsx`: Application shell, all cross-view synchronized state

**Configuration:**
- `backend/app/core/config.py`: All backend settings (DB URL, Gemini API key, JWT secret, storage paths) — reads from `.env` via `pydantic_settings.BaseSettings`
- `frontend/vite.config.ts` (if present), `frontend/tsconfig.json`, `frontend/package.json`: Frontend build/tooling config
- `frontend/src/lib/api.ts`: Hardcoded backend base URL (`http://localhost:8000/api/v1`) — not environment-driven; edit directly to point at a different backend

**Core Logic:**
- `backend/app/services/graph_engine.py`: Graph data structure, fuzzy entity resolution, k-hop/shortest-path/centrality analytics, anomaly detection
- `backend/app/services/ai_investigator.py`: AI investigation logic (live Gemini + scripted demo responses)
- `backend/app/services/evidence.py`: Evidence hashing, mock blockchain anchoring, tamper simulation/verification
- `frontend/src/App.tsx`: Tri-view (Graph/Map/Timeline) synchronization handlers

**Testing:**
- Not detected — no `tests/`, `*.test.*`, `*.spec.*`, `pytest.ini`, or Jest/Vitest config found in either `backend/` or `frontend/` at time of analysis.

## Naming Conventions

**Files:**
- Backend: `snake_case.py`, one module per domain in `api/` and `services/`
- Frontend: `PascalCase.tsx` for React components (e.g. `CytoscapeGraph.tsx`, `InvestigatorMap.tsx`), `camelCase.ts` for non-component modules (`api.ts`)

**Directories:**
- Backend: singular/plural domain nouns (`api`, `core`, `models`, `schemas`, `services`) — layer-based, not feature-based
- Frontend: `components/<feature-noun>/` — feature-based grouping, singular lowercase noun per feature (`graph`, `map`, `timeline`, `evidence`, `ai`, `analytics`, `ingestion`, `osint`, `documents`, `court`, `resolution`, `layout`)

## Where to Add New Code

**New backend API feature:**
- Router: add a new file in `backend/app/api/` (e.g. `backend/app/api/<feature>.py`), register it in `backend/app/main.py` with `app.include_router(...)`
- Business logic: add a corresponding module in `backend/app/services/<feature>.py`
- Data model: add SQLAlchemy classes to `backend/app/models/entities.py`; add matching Pydantic schemas to `backend/app/schemas/schemas.py`

**New frontend feature/view:**
- Create `frontend/src/components/<feature>/<ComponentName>.tsx`
- Add corresponding types to `frontend/src/types/index.ts`
- Add API methods to `frontend/src/lib/api.ts`
- Wire into `frontend/src/App.tsx` (new tab in the `activeTab` switch, or new modal state if it's a modal)

**Graph algorithm additions:**
- Add methods directly to `TemporalKnowledgeGraph` class in `backend/app/services/graph_engine.py`; expose via a new or existing route in `backend/app/api/graph.py`

**Utilities:**
- Backend: no dedicated `utils/` directory exists; small helpers currently live inline in `services/*.py` (e.g. `calculate_sha256` in `evidence.py`, `_haversine` in `graph_engine.py`) — follow this pattern for now, or introduce `backend/app/utils/` if helpers proliferate
- Frontend: no dedicated `hooks/` or `utils/` directory exists yet; all shared logic currently lives in `lib/api.ts` or inline in `App.tsx`

## Special Directories

**`backend/data/synthetic/`:**
- Purpose: Seed dataset for demo/dev database and graph
- Generated: No (hand-authored or scripted seed data, committed)
- Committed: Yes

**`backend/storage/`:**
- Purpose: Uploaded evidence file storage
- Generated: Yes (created at runtime by config)
- Committed: No — should be gitignored (verify)

**`frontend/dist/`:**
- Purpose: Vite production build artifacts
- Generated: Yes
- Committed: Present in repo at analysis time — verify whether this is intentional (typically build output should be gitignored, not committed)

**`backend/spemass.db`:**
- Purpose: Default SQLite database file (created next to `backend/app/` per `BASE_DIR` in `config.py`)
- Generated: Yes, on first run
- Committed: Should not be — verify `.gitignore` coverage

---

*Structure analysis: 2026-09-05*
