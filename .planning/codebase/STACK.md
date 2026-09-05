# Technology Stack

**Analysis Date:** 2026-09-05

## Languages

**Primary:**
- Python 3.x - Backend (`backend/app/`), FastAPI service
- TypeScript - Frontend (`frontend/src/`), React app

**Secondary:**
- SQL (via SQLAlchemy ORM, no raw `.sql` files found) - `backend/app/models/database.py`

## Runtime

**Environment:**
- Python (version unpinned; no `.python-version` file present) - runs backend via `uvicorn`
- Node.js (version unpinned; no `.nvmrc` present) - runs frontend via Vite

**Package Manager:**
- Backend: `pip` with `backend/requirements.txt` (no lockfile — plain `>=` version ranges, not pinned)
- Frontend: `npm` with `frontend/package.json` and `frontend/package-lock.json` (lockfile present)

## Frameworks

**Core:**
- FastAPI `>=0.110.0` - backend HTTP API framework, `backend/app/main.py`
- Uvicorn `>=0.28.0` - ASGI server (dev entrypoint uses `reload=True`), `backend/app/main.py`
- SQLAlchemy `>=2.0.28` - ORM / DB access, `backend/app/models/database.py`, `backend/app/models/entities.py`
- Pydantic `>=2.6.0` - request/response schemas, `backend/app/schemas/schemas.py`
- React `^19.2.8` + `react-dom` `^19.2.8` - frontend UI, `frontend/src/`
- Vite `^8.2.2` with `@vitejs/plugin-react` `^6.1.0` - frontend build/dev tooling, `frontend/vite.config.ts`

**Testing:**
- No frontend test framework configured (no Jest/Vitest config found)
- `backend/test_mvp.py` present at repo root of backend — appears to be an ad-hoc manual/smoke test script (uses `requests` against a running server), not a pytest suite integrated into CI. No `pytest` in `requirements.txt`.

**Build/Dev:**
- TypeScript `~6.0.2` - `frontend/tsconfig.json`, `tsconfig.app.json`, `tsconfig.node.json`
- Tailwind CSS `^3.4.17` + PostCSS `^8.5.27` + Autoprefixer `^10.5.4` - `frontend/tailwind.config.js`, `frontend/postcss.config.js`
- oxlint `^1.79.0` - frontend linting (`npm run lint`), config at `frontend/.oxlintrc.json`

## Key Dependencies

**Critical (backend):**
- `python-jose[cryptography]>=3.3.0` - JWT issuing/verification, `backend/app/core/security.py`
- `passlib[bcrypt]>=1.7.4` - listed in requirements but NOT used for hashing; actual password hashing is manual salted SHA-256 in `backend/app/core/security.py` (`get_password_hash`) — a discrepancy between declared dependency and actual implementation
- `networkx>=3.2.1` - in-memory knowledge graph engine (MultiDiGraph, shortest-path, centrality, connected components), `backend/app/services/graph_engine.py`
- `pandas>=2.2.1`, `scikit-learn>=1.4.1.post1`, `rapidfuzz>=3.6.1` - present in requirements; used for entity resolution / fuzzy matching support (see `backend/app/services/ingestion.py` and entity resolution flows)
- `requests>=2.31.0` - outbound HTTP calls, used to call the Gemini generative API directly via raw REST (`backend/app/services/ai_investigator.py`)
- `python-multipart>=0.0.9` - file upload handling for FastAPI, `backend/app/api/ingestion.py` / `backend/app/api/evidence.py`
- `aiofiles>=23.2.1` - async file I/O for evidence/document storage, `backend/storage/`

**Not in requirements.txt but imported in code (undeclared dependency — likely installed ad hoc in the dev environment):**
- `pydantic-settings` - imported in `backend/app/core/config.py` (`from pydantic_settings import BaseSettings`) but absent from `requirements.txt`. This is a real gap: a fresh `pip install -r requirements.txt` would fail to start the app.

**Infrastructure (frontend):**
- `cytoscape` `^3.34.2` + `@types/cytoscape` - network/graph visualization, `frontend/src/components/graph/CytoscapeGraph.tsx`
- `leaflet` `^1.9.4` + `@types/leaflet` - map/geospatial visualization, `frontend/src/components/map/InvestigatorMap.tsx`
- `lucide-react` `^1.40.0` - icon set
- `clsx` `^2.1.1`, `tailwind-merge` `^3.6.0` - conditional className utilities

## Configuration

**Environment:**
- Backend loads config via `pydantic_settings.BaseSettings` in `backend/app/core/config.py`, reading an optional `.env` file (`Config.env_file = ".env"`) plus `os.getenv()` fallbacks.
- `backend/.env` exists in the repo working tree (present but its contents were not read — treat as containing local secrets; verify it is git-ignored before committing).
- `backend/.env.example` exists as a template (contents not read per secret-handling policy, but its existence confirms env-var-based config is the intended pattern).
- Key configured variables (from `config.py` defaults): `SECRET_KEY`, `DATABASE_URL`, `GEMINI_API_KEY`.
- Frontend has **no `.env` handling** — the API base URL is hardcoded as `http://localhost:8000/api/v1` in `frontend/src/lib/api.ts`. There is no `VITE_*` env var usage found.

**Build:**
- `frontend/vite.config.ts` - minimal Vite config, just the React plugin, no proxy/env wiring
- `frontend/tailwind.config.js`, `frontend/postcss.config.js` - Tailwind/PostCSS pipeline
- `frontend/tsconfig.json` (references `tsconfig.app.json` and `tsconfig.node.json`) - TypeScript project config

## Platform Requirements

**Development:**
- Backend: run via `python -m app.main` or `uvicorn app.main:app --reload` (see `if __name__ == "__main__"` block in `backend/app/main.py`), listens on port 8000.
- Database file `backend/spemass.db` (SQLite) is committed/present in the working tree, confirming default local dev uses SQLite, not Postgres.
- Frontend: `npm run dev` (Vite dev server), `npm run build` (`tsc -b && vite build`), `npm run preview`.

**Production:**
- No Dockerfile, docker-compose, or CI/CD config found anywhere in the repo. No deployment target is defined in code.
- CORS in `backend/app/main.py` is wide open (`allow_origins=["*"]`, `allow_credentials=True`), which is a development-only configuration that would need tightening for any real deployment.

---

*Stack analysis: 2026-09-05*
