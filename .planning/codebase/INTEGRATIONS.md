# External Integrations

**Analysis Date:** 2026-09-05

## Note on Planning Docs vs. Actual Implementation

`PRD.md` and `planning.md` at the repo root describe an intended architecture involving Neo4j, PostgreSQL+pgvector, MinIO, Redis, Tesseract OCR, spaCy, and a blockchain/EVM testbed. **None of these are actually installed or used in the current code.** The verified, real integrations are documented below; treat anything not listed here as aspirational/planning-stage only, not implemented.

## APIs & External Services

**Generative AI:**
- Google Gemini (`gemini-1.5-flash`) - used for free-form investigative Q&A synthesis
  - Integration: raw REST call via `requests.post()`, NOT the official Google SDK — `backend/app/services/ai_investigator.py` (`_call_live_gemini`, line ~179)
  - Endpoint: `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}`
  - Auth: API key passed as a URL query parameter, sourced from `GEMINI_API_KEY` env var via `backend/app/core/config.py`
  - Behavior: if the key is missing/short (<10 chars), the call is silently skipped and the code falls through to hardcoded/scripted responses and local graph lookups (see below) — the AI investigator is NOT purely LLM-driven; most "investigation" answers are hand-authored canned responses keyed off keyword matching in the user's query (e.g. "vikram", "swiss", "rahul"), with Gemini only invoked as a fallback path.
  - No streaming, no retry logic; `timeout=8` seconds; exceptions are caught and swallowed (`except Exception: pass`).

## Data Storage

**Databases:**
- SQLite - default and currently active database (`backend/spemass.db` is present in the working tree)
  - Connection: `DATABASE_URL` env var, defaulting to `sqlite:///{BASE_DIR}/spemass.db` — `backend/app/core/config.py`
  - Client/ORM: SQLAlchemy `>=2.0.28`, engine setup in `backend/app/models/database.py` (SQLite-specific `connect_args={"check_same_thread": False}`)
  - The `DATABASE_URL` pattern would allow swapping in Postgres via env var, but no Postgres driver (`psycopg2`, `asyncpg`) is listed in `backend/requirements.txt`, so Postgres is not actually usable out of the box despite being mentioned in planning docs.
- **No Neo4j.** The "knowledge graph" is an in-memory Python object using `networkx.MultiDiGraph`, rebuilt at runtime — `backend/app/services/graph_engine.py`. It is not persisted to a graph database; state lives only in the running process (rebuilt from the seed/ingestion routine on startup, see `backend/app/services/ingestion.py` and `seed_database_and_graph` called from `backend/app/main.py` startup event).
- **No pgvector / vector database.** No embedding/vector-search dependencies (`pgvector`, `faiss`, `chromadb`, `pinecone`, etc.) appear in `requirements.txt` or imports.

**File Storage:**
- Local filesystem only. `backend/app/core/config.py` defines `STORAGE_DIR` (`backend/storage/`) and `DATA_DIR` (`backend/data/`), created on startup via `settings.STORAGE_DIR.mkdir(...)`.
- No MinIO, S3, or any object-storage SDK is present in `requirements.txt` or imports, despite MinIO being referenced in planning docs.

**Caching:**
- None. No Redis client, no in-memory cache library, no caching layer found anywhere in `backend/app`.

## Blockchain / Evidence Integrity

**"Blockchain" ledger — simulated, not a real chain:**
- `backend/app/services/evidence.py` (`create_evidence_record`) mints a `BlockchainRecord` row with a fabricated `tx_hash` (`f"0x{uuid.uuid4().hex}{uuid.uuid4().hex}"[:66]`) and an incrementing fake `block_number` (`14200000 + count`). This is a mock/simulated blockchain stored as a regular SQL table (`BlockchainRecord` in `backend/app/models/entities.py`) — there is no real EVM node, no web3 library (`web3.py` not in requirements), and no actual on-chain transaction.
- Evidence integrity is verified by recomputing SHA-256 hashes and comparing against the stored/"blockchain" hash — pure application-level hashing (`hashlib.sha256`), not cryptographic chain verification.

## OCR / NLP

**No Tesseract OCR, no spaCy.** Neither appears in `requirements.txt` nor is imported anywhere in `backend/app`. Document text extraction (`extracted_text` field referenced in `backend/app/services/evidence.py`) is presumably populated from pre-seeded synthetic data (see `backend/data/`) rather than real OCR/NLP pipelines.

**Entity resolution / fuzzy matching:**
- `rapidfuzz` is used for approximate string matching in entity resolution flows (`backend/app/services/ingestion.py` and related graph resolution logic in `backend/app/services/graph_engine.py`).
- `scikit-learn` and `pandas` are declared dependencies, likely supporting light data-processing/matching utilities in the ingestion pipeline.

## OSINT

**Simulated OSINT expansion, not a live web/API integration:**
- `backend/app/services/osint.py` (`perform_osint_expansion`) reads a static local JSON file `backend/data/synthetic/osint_records.json` and matches entity names/aliases against it. If no match is found, it synthesizes a fake "public registrar" result pointing to a non-functional placeholder URL (`https://public-records.gov.in/search?q={entity_name}`) — this URL is never actually fetched.
- No real OSINT/web-search API (e.g., SerpAPI, Google Custom Search, social media APIs) is integrated.

## Authentication & Identity

**Auth Provider:**
- Custom, self-hosted — no third-party auth provider (no Auth0, Firebase Auth, Clerk, Supabase Auth, etc.)
  - JWT issuance/verification: `python-jose` in `backend/app/core/security.py` (`create_access_token`), signed with `SECRET_KEY` from `backend/app/core/config.py` (HS256, 24-hour expiry)
  - Password hashing: manual salted SHA-256 (`hashlib.sha256(f"{salt}_{password}")`) in `backend/app/core/security.py` — NOT bcrypt, despite `passlib[bcrypt]` being listed as a dependency in `requirements.txt`. This is a real mismatch between declared and actual security implementation, and salted-SHA256 is weaker than bcrypt for password storage.
  - `verify_password` also has a fallback plaintext-equality check (`or plain_password == hashed_password`), which is a security concern — see CONCERNS.md.
  - Backend routes: `backend/app/api/auth.py`

## Monitoring & Observability

**Error Tracking:**
- None. No Sentry, Rollbar, or similar SDK found.

**Logs:**
- No structured logging framework configured; relies on FastAPI/Uvicorn's default console output. No `logging` module usage detected in a custom logger setup.

## CI/CD & Deployment

**Hosting:**
- Not defined. No Dockerfile, `docker-compose.yml`, Procfile, or platform-specific deployment config (Vercel, Netlify, Render, Fly.io, etc.) found in the repo.

**CI Pipeline:**
- None. No `.github/workflows/`, `.gitlab-ci.yml`, or other CI config found.

## Environment Configuration

**Required env vars (backend, from `backend/app/core/config.py`):**
- `SECRET_KEY` - JWT signing secret (has an insecure hardcoded fallback default in code)
- `DATABASE_URL` - defaults to local SQLite file
- `GEMINI_API_KEY` - optional; app degrades gracefully to scripted responses if absent

**Secrets location:**
- `backend/.env` (present in working tree — verify it is excluded via `.gitignore` before any commit; contents were not inspected per this analysis's security policy)
- `backend/.env.example` documents the expected variable names as a template

**Frontend:**
- No environment variable usage found. API base URL is hardcoded in `frontend/src/lib/api.ts` (`http://localhost:8000/api/v1`), meaning the frontend cannot point at a different backend without a code change.

## Webhooks & Callbacks

**Incoming:**
- None. No webhook receiver endpoints found in `backend/app/api/`.

**Outgoing:**
- None beyond the Gemini API call described above.

---

*Integration audit: 2026-09-05*
