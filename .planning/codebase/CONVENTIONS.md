# Coding Conventions

**Analysis Date:** 2026-09-05

## Naming Patterns

**Files (backend, `backend/app/`):**
- Snake_case module names matching domain concept: `app/api/cases.py`, `app/services/ai_investigator.py`, `app/services/graph_engine.py`
- One router file per resource under `app/api/`; one service file per domain under `app/services/`
- Single shared schema file `app/schemas/schemas.py` (all Pydantic models, grouped by `# --- Section Name ---` comments)
- Single shared models file `app/models/entities.py` for all SQLAlchemy ORM classes

**Files (frontend, `frontend/src/`):**
- PascalCase for component files matching the exported component: `CytoscapeGraph.tsx`, `UniversalAIInvestigator.tsx`, `EvidenceVault.tsx`
- Components grouped into feature directories: `components/ai/`, `components/graph/`, `components/map/`, `components/evidence/`, `components/timeline/`, `components/ingestion/`, `components/osint/`, `components/documents/`, `components/court/`, `components/resolution/`, `components/layout/`
- Shared/non-component code is lowercase: `lib/api.ts`, `types/index.ts`

**Functions (Python):**
- snake_case: `list_cases`, `get_case_by_id`, `create_access_token`, `seed_database_and_graph`
- FastAPI route handler names describe the action + resource (`get_case_by_id`, `create_case`, `login`)

**Functions (TypeScript):**
- camelCase: `loadCaseData`, `getCases`, `getShortestPath`
- API client methods on the `api` object read as verb + noun: `getCases()`, `getGraph(caseId)`, `mergeEntities(primaryId, duplicateId)`

**Variables:**
- Python: snake_case (`case_id`, `access_token`, `hashed_password`)
- TypeScript: camelCase (`activeCaseId`, `graphData`, `highlightedNodeIds`)
- React state pairs follow `useState` convention: `[thing, setThing]`, e.g. `const [cases, setCases] = useState<Case[]>([])`

**Types/Classes:**
- Python: PascalCase for SQLAlchemy models (`Case`, `Document`, `Evidence`, `AuditLog`, `User`) and Pydantic schemas (`CaseResponse`, `CaseCreate`, `LoginRequest`, `Token`)
- Pydantic response/request schema pairing pattern: `{Resource}Create` for input, `{Resource}Response` for output (see `backend/app/schemas/schemas.py`)
- TypeScript: PascalCase interfaces/types in `frontend/src/types/index.ts` (`Case`, `GraphData`, `MapEvent`, `TimelineEvent`, `GraphNode`, `EvidenceItem`)

## Code Style

**Formatting:**
- No Prettier or Black config detected — no enforced auto-formatter in either package. Style is consistent by convention (2-space TS indent, 4-space Python indent) rather than tooling.

**Linting:**
- Frontend: `oxlint` (see `frontend/package.json` script `"lint": "oxlint"`), configured via `frontend/.oxlintrc.json`:
  - Plugins: `react`, `typescript`, `oxc`
  - Rules: `react/rules-of-hooks: error`, `react/only-export-components: warn` (allows constant exports)
- Backend: no linter (no `.flake8`, `ruff.toml`, or `pyproject.toml` lint config detected). Follow existing style in `backend/app/` files when adding code.

## Import Organization

**Python (see `backend/app/api/cases.py`, `backend/app/main.py`):**
1. Third-party framework imports first: `from fastapi import ...`, `from sqlalchemy.orm import Session`
2. Standard library / typing: `from typing import List`
3. Local app imports last, using absolute `app.` package paths: `from app.models.database import get_db`, `from app.schemas.schemas import CaseResponse, CaseCreate`
- No relative imports (`.` or `..`) — always `app.<subpackage>.<module>`

**TypeScript (see `frontend/src/App.tsx`):**
1. React and third-party imports first: `import React, { useState, useEffect } from 'react'`
2. Local component imports next, one per line, relative paths: `import { Header } from './components/layout/Header'`
3. `import type { ... } from './types'` kept separate from value imports using `type` keyword
4. Local lib/util imports last: `import { api } from './lib/api'`

**Path Aliases:**
- None configured. All frontend imports use relative paths (`./components/...`, `./lib/api`).

## Error Handling

**Backend:**
- Use FastAPI `HTTPException` for all API-level errors, with explicit `status_code` and human-readable `detail`:
  ```python
  raise HTTPException(status_code=404, detail="Case not found")
  raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password", headers={"WWW-Authenticate": "Bearer"})
  ```
- Validate existence before mutating (query first, `if not x: raise HTTPException(...)`), pattern repeated in `backend/app/api/cases.py` and `backend/app/api/auth.py`
- No global exception handler middleware detected in `backend/app/main.py` — errors bubble up as default FastAPI responses.

**Frontend:**
- API calls in `frontend/src/lib/api.ts` do not check `res.ok` or handle non-2xx responses — they call `res.json()` unconditionally. New API client methods should follow existing pattern unless improving error handling.
- Data-loading code in components (e.g. `loadCaseData` in `frontend/src/App.tsx`) wraps `Promise.all([...])` calls in `try { ... } catch` blocks.

## Logging

**Framework:** None (no structured logger, e.g. `logging`/`winston`, detected).

**Patterns:**
- Backend: plain `print()` statements for test/verification output (see `backend/test_mvp.py`, using bracketed `[PASS - UAT-xx]` markers). No logging in route/service files.
- Frontend: no console logging convention observed; avoid introducing `console.log` in committed code unless matching existing debug output style.

## Comments

**When to Comment:**
- Section-divider comments group related code blocks, e.g. `# --- Auth Schemas ---`, `# --- Case Schemas ---` in `backend/app/schemas/schemas.py`, and `// Synchronized Workspace State`, `// Modals` in `frontend/src/App.tsx`
- Inline comments explain intent/business logic, not restating code: `# Re-seed DB & Graph`, `# Enable CORS for frontend`

**JSDoc/TSDoc:**
- Not used. No docstrings observed on Python functions either — rely on descriptive names and inline comments instead.

## Function Design

**Size:** Route handlers and service functions are short (typically 5–30 lines), doing one CRUD operation or one orchestration step per function.

**Parameters:**
- FastAPI handlers use `Depends(get_db)` for DB session injection, plus Pydantic request models for bodies: `def create_case(req: CaseCreate, db: Session = Depends(get_db))`
- TypeScript API methods take positional primitives with optional params defaulted: `async getKHop(entityId: string, k: number = 2)`

**Return Values:**
- FastAPI handlers return ORM objects or Pydantic models directly; `response_model=` on the route decorator handles serialization (`@router.get("", response_model=List[CaseResponse])`)
- Frontend `api.*` methods always return `res.json()` (implicitly `Promise<any>` — no typed response parsing/validation layer)

## Module Design

**Exports:**
- Backend: one `router = APIRouter(...)` per API module, imported and included in `backend/app/main.py` via `app.include_router(...)`
- Frontend: named exports for components (`export const App: React.FC = ...`, `export const Header = ...`), not default exports
- Frontend: single shared `api` object exported from `frontend/src/lib/api.ts` aggregating all backend calls as methods (no per-resource files)

**Barrel Files:**
- Not used. Types are centralized in a single `frontend/src/types/index.ts` rather than per-feature type files.

---

*Convention analysis: 2026-09-05*
