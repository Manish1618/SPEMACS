# Codebase Concerns

**Analysis Date:** 2026-09-05

> **Authentication section superseded on 2026-09-06.** Every auth and access-control
> concern recorded below has since been resolved; the entries are kept for history but
> no longer describe the code. See **Resolved: authentication and access control**
> at the end of this document before planning against any of them.

## Summary: PRD Promises vs Implementation Reality

`PRD.md` and `planning.md` describe an ambitious 25-requirement MVP built on Neo4j, GraphRAG, pgvector, MinIO, PostgreSQL, permissioned blockchain, and enforced RBAC. The actual codebase in `backend/app/` implements a much smaller, heavily scripted/demo system. This is the single biggest concern in the repo — nearly every "concern" below traces back to this gap. Anyone planning new phases against this codebase should treat PRD.md/planning.md as aspirational, not descriptive.

| Promised (PRD.md / planning.md) | Actual Implementation | File(s) |
|---|---|---|
| Neo4j 5.x graph database with Cypher + GDS | In-memory `networkx.MultiDiGraph`, rebuilt from scratch on every process start, no persistence | `backend/app/services/graph_engine.py` |
| PostgreSQL | SQLite (`spemass.db`) via SQLAlchemy | `backend/app/core/config.py:17` |
| MinIO object storage for evidence files | Local filesystem `storage/` dir (implied by `STORAGE_DIR`); no object storage client present | `backend/app/core/config.py:14-15` |
| pgvector semantic search / embeddings | Not implemented anywhere — no embedding model, no vector index, no `pgvector` dependency | `backend/requirements.txt` |
| GraphRAG multi-tool LLM agent with Cypher/SQL/spatial query planning | Hardcoded `if/elif` keyword matching on specific names ("vikram", "rahul", "golden falcon") that returns pre-written canned JSON responses; only falls through to a real Gemini call if none of the keyword branches match | `backend/app/services/ai_investigator.py:21-133` |
| Citation-enforced, hallucination-free AI answers | Canned responses contain fabricated but fixed citations; the live Gemini fallback path (`_call_live_gemini`) has **no grounding, no tool use, no citation enforcement** — it just asks Gemini a free-text question and returns whatever comes back as if it were evidence-grounded (fake `confidence_score: 0.90`, fake citation object) | `backend/app/services/ai_investigator.py:174-224` |
| Permissioned blockchain integrity anchoring | No blockchain node, contract, or web3 library. `BlockchainRecord` is a random hex string (`uuid.uuid4()`) written to SQLite; `contract_address` is a literal placeholder string | `backend/app/services/evidence.py:26-40`, `backend/app/models/entities.py:101` |
| RBAC enforced on every LLM tool call and API endpoint | No RBAC middleware or dependency exists. Every API route in `backend/app/api/*.py` is unauthenticated — no `Depends(get_current_user)` guard found anywhere in the router files inspected (`cases.py`, `graph.py`, `evidence.py`, `ai.py`, `osint.py`, `ingestion.py`, `map_timeline.py`) | `backend/app/api/*.py` |
| JWT auth with role claims | `create_access_token` issues a JWT with only `sub`/`exp` (no role claim). No token-verification dependency is used by any route — `/auth/login` mints a token but nothing ever validates it on subsequent requests | `backend/app/core/security.py`, `backend/app/api/auth.py` |
| OCR pipeline (Tesseract/PyMuPDF) | Not present in `requirements.txt`; no OCR code found | `backend/requirements.txt` |
| Louvain community detection | Uses `nx.connected_components` (basic component labeling), not Louvain/GDS | `backend/app/services/graph_engine.py:159-164` |

## Tech Debt

**Scripted "AI Investigator" masquerading as GraphRAG:**
- Issue: `investigate()` matches on hardcoded substrings (`"rahul"`, `"vikram"`, `"golden falcon"`, `"250"`, etc.) and returns fully pre-written answer/citation payloads rather than querying the graph or documents dynamically for most cases.
- Files: `backend/app/services/ai_investigator.py:21-133` (see `_build_vikram_swiss_transfer_response`, `_build_vikram_location_response`, `_build_cross_case_response`)
- Impact: The AI Investigator only "works" for the specific demo case (`CASE-2024-8812`) and specific named entities seeded into the synthetic dataset. Any new case data or entity will fall through to the generic/low-confidence branch or an ungrounded Gemini call. This is not extensible and cannot be validated against the PRD's citation-enforcement requirement (FR set around GraphRAG).
- Fix approach: Replace with a real retrieval pipeline — query `knowledge_graph` + document store for relevant entities/events, pass structured context (not free text) to the LLM, and post-validate that every citation in the model's answer maps to a real evidence ID before returning it to the client.

**In-memory, non-persistent knowledge graph:**
- Issue: `TemporalKnowledgeGraph` (networkx) is a process-local singleton (`knowledge_graph = TemporalKnowledgeGraph()` at module scope). It is rebuilt from `seed_database_and_graph()` on every app startup.
- Files: `backend/app/services/graph_engine.py:1-9,290`, `backend/app/main.py:36-42`, `backend/app/services/ingestion.py`
- Impact: Any entity/relationship created via the API during a running session is lost on restart. Cannot scale beyond a single process (no shared state across workers). Not what PRD.md promises ("Neo4j property graph modeling").
- Fix approach: Either (a) explicitly document this as a "demo-mode" limitation and design future phases around eventually swapping in a real graph DB, or (b) persist entities/relationships to SQLite/Postgres and rehydrate the networkx graph from DB on startup so data survives restarts.

**Mock blockchain layer presented as real integrity infrastructure:**
- Issue: `create_evidence_record()` mints a `tx_hash` from `uuid.uuid4()` (not a real transaction, no chain, no consensus) and a monotonically incrementing fake `block_number`. `BlockchainRecord.contract_address` default is the literal string `"0x71C2B890a8813C124231EVID_LEDGER_MOCK"`.
- Files: `backend/app/services/evidence.py:26-40`, `backend/app/models/entities.py:101`
- Impact: `verify_evidence_integrity()` compares the SQLite-stored hash against this same mock "blockchain" record stored in the same SQLite DB — there is no independent immutable ledger, so tamper detection only catches accidental mismatches, not deliberate DB tampering (an attacker with DB write access can edit both records together). This directly contradicts the evidentiary-integrity value proposition in `PRD.md:21`.
- Fix approach: Either integrate a real anchor (e.g., periodic Merkle root submission to a public/permissioned chain or an external notarization service) or rename/document this feature clearly as "simulated blockchain anchor for demo purposes" so no downstream consumer treats `integrity_status: VERIFIED` as legally defensible.

**Built-in tamper-test backdoor shipped in evidence API:**
- Issue: `tampered_mock_cache: Dict[str, bytes] = {}` is a module-level dict in the evidence router used to simulate corrupting evidence for demo purposes, with routes that write/read/delete it.
- Files: `backend/app/api/evidence.py:12,31,50,68-69`
- Impact: If this router is ever exposed in a non-demo deployment, it likely provides an endpoint to artificially mark evidence as tampered/untampered — a real security and integrity risk if reachable in production. At minimum it is dead-weight/demo scaffolding mixed into production code paths.
- Fix approach: Gate this behind a `DEMO_MODE` flag/env var and exclude the router from production builds, or move it to a separate demo-only router that's not mounted by default.

## Known Bugs

**`verify_password` accepts plaintext-equals-hash as valid:**
- Symptoms: `verify_password` returns `True` if `expected_hash == hashed_password` **or** `plain_password == hashed_password` (i.e., if the stored "hash" in the DB literally equals the plaintext password, login succeeds).
- Files: `backend/app/core/security.py:12-14`
- Trigger: Any seeded/test user whose `hashed_password` column happens to equal their plaintext password will authenticate via two different code paths, and any DB row where someone forgot to hash a password silently "works" instead of failing loudly.
- Workaround: None currently; this appears to be a deliberate demo shortcut but is a real vulnerability if any real password ends up unhashed in the DB.

**`/auth/me` ignores the authenticated caller entirely:**
- Symptoms: `get_current_user_profile()` takes no token/session, just runs `db.query(User).first()` — every caller gets whichever user happens to be first in the table (or a hardcoded fallback `rajiv_sen` / `LEAD_INVESTIGATOR`), regardless of who actually logged in.
- Files: `backend/app/api/auth.py:48-57`
- Trigger: Call `GET /api/v1/auth/me` as any user; the response never reflects the caller's real identity.
- Workaround: None. This makes any UI/business logic built on "current user" (e.g., audit attribution, RBAC) meaningless.

**No authentication enforcement on any protected route:**
- Symptoms: Login issues a JWT, but no route (`cases`, `graph`, `evidence`, `ai`, `osint`, `ingestion`, `map_timeline`) validates or requires that JWT — `main.py` never wires up an `OAuth2PasswordBearer`/dependency check on these routers.
- Files: `backend/app/main.py:27-34`, `backend/app/api/*.py`
- Trigger: Any client can call any API endpoint directly without a token.
- Workaround: None currently implemented.

## Security Considerations

**CORS wide open (`allow_origins=["*"]`) combined with `allow_credentials=True`:**
- Risk: Per the Fetch/CORS spec this combination is invalid for credentialed requests in real browsers, but frameworks may reflect the origin, effectively allowing any site to make credentialed requests against the API. Combined with the missing auth enforcement above, this is a low-priority concern relative to the auth gaps but should be tightened before any non-local deployment.
- Files: `backend/app/main.py:17-24`
- Current mitigation: None.
- Recommendations: Restrict `allow_origins` to explicit frontend origin(s) once a real deployment target exists.

**Hardcoded default `SECRET_KEY` and password salt committed to source:**
- Risk: `SECRET_KEY` defaults to a fixed string (`"spemass-super-secure-jwt-secret-key-2026-audit-investigation"`) if `SECRET_KEY` env var is unset, and the password-hash salt is a fixed literal (`"spemass_secure_salt_2026"`) with no per-user salt.
- Files: `backend/app/core/config.py:9`, `backend/app/core/security.py:9`
- Current mitigation: None — both are usable as-is if env vars aren't set, which is the default local/dev path (and likely CI/demo too).
- Recommendations: Require `SECRET_KEY` via env with no insecure default in non-dev environments; move to per-user random salts with `passlib`'s bcrypt (already a dependency in `requirements.txt` but unused — `security.py` uses raw `hashlib.sha256` instead of `passlib[bcrypt]`).

**`passlib[bcrypt]` is a declared dependency but never used:**
- Risk: `backend/requirements.txt` lists `passlib[bcrypt]>=1.7.4`, but `backend/app/core/security.py` implements its own salted-SHA256 hashing instead of using bcrypt. SHA-256 (even salted with a fixed salt) is fast to brute-force compared to bcrypt, and the fixed salt means all password hashes are vulnerable to a single precomputed rainbow table.
- Files: `backend/app/core/security.py:7-10`, `backend/requirements.txt`
- Recommendations: Switch to `passlib.context.CryptContext(schemes=["bcrypt"])` for `get_password_hash`/`verify_password`.

**No case-tenancy / row-level isolation enforced despite RSK-04 in planning.md calling this out as a "High" risk:**
- Risk: `planning.md:528` explicitly flags "Unauthorized Data Exfiltration / Cross-Case Leak" as a high-impact risk requiring "Row-level and Cypher-level case tenancy filters; strict RBAC checks injected into all LLM tool calls." No such filters exist in the current API/graph code — `resolve_entity`, `get_k_hop_neighborhood`, etc. take no caller/role/case-authorization context.
- Files: `backend/app/services/graph_engine.py` (all query methods), `backend/app/api/*.py`
- Recommendations: Before adding multi-case/multi-tenant features, add case-scoping checks to every graph query and API handler.

## Performance Bottlenecks

**Full graph analytics recomputed on every subgraph request:**
- Problem: `_build_subgraph_response()` calls `self.compute_graph_analytics()` (degree centrality, betweenness centrality, connected components) from scratch on every single call, including from `get_k_hop_neighborhood` and `get_shortest_path`, which are likely invoked on nearly every graph API request.
- Files: `backend/app/services/graph_engine.py:247-250`
- Cause: `compute_graph_analytics()` is O(V·E) or worse (betweenness centrality is particularly expensive) and is not cached/memoized; it re-runs the same computation over the *entire* graph every time a small subgraph is requested.
- Improvement path: Cache analytics per case_id and invalidate only when the graph mutates, or compute them lazily/on-demand only for endpoints that specifically need centrality data.

**Synchronous external HTTP call inline in request path:**
- Problem: `_call_live_gemini()` makes a blocking `requests.post(...)` call (not `httpx.AsyncClient`) inside what appears to be an async-capable FastAPI app.
- Files: `backend/app/services/ai_investigator.py:174-224`
- Cause: `requests` is synchronous; if the route handler is `async def`, this call blocks the event loop for up to the 8s timeout, stalling all other concurrent requests on that worker.
- Improvement path: Use `httpx.AsyncClient` with `await`, or run the sync call in a thread pool via `run_in_threadpool`.

## Fragile Areas

**`ai_investigator.py` keyword-matching logic:**
- Files: `backend/app/services/ai_investigator.py:21-133`
- Why fragile: Adding any new case or entity requires hand-writing new `if` branches and new hardcoded JSON response builders (`_build_*_response` methods). The keyword conditions are broad and overlapping (e.g. `"vikram" in query_lower` appears in three separate `if` branches with different downstream behavior depending on order), making behavior hard to predict and easy to break when adding new phrases.
- Safe modification: Any change to branch ordering or keyword lists in `investigate()` needs manual re-testing of all documented demo queries in `PRD.md`/`planning.md` walkthrough section (section describing example queries).
- Test coverage: `backend/test_mvp.py` exists but should be checked against these exact branches before any refactor (not verified in this pass beyond confirming the file exists).

**Module-level singleton `knowledge_graph`:**
- Files: `backend/app/services/graph_engine.py:290`
- Why fragile: Shared mutable global state across all requests in the process. Not thread-safe for concurrent writes (no locking), and any future move to multiple uvicorn workers/processes will silently give each worker a different graph.
- Safe modification: Do not add new mutation methods without considering concurrent-request safety; do not assume graph state is durable across restarts.

## Test Coverage Gaps

**No tests for auth/security paths:**
- What's not tested: `verify_password`'s plaintext-fallback behavior, missing route-level auth enforcement, and JWT validation are not exercised by any visible test suite (only `backend/test_mvp.py` was found at the repo root, and its scope wasn't confirmed to include auth).
- Files: `backend/test_mvp.py`, `backend/app/core/security.py`, `backend/app/api/auth.py`
- Risk: The plaintext-password bug and lack of endpoint auth enforcement could ship into a real deployment unnoticed.
- Priority: High.

**No tests for evidence integrity edge cases:**
- What's not tested: Behavior when `verify_evidence_integrity` is called with no `document.extracted_text` and no `current_content_bytes` (falls back to comparing `stored_hash` to itself, always reporting `VERIFIED` even if nothing was actually re-checked).
- Files: `backend/app/services/evidence.py:88-97`
- Risk: `verify_evidence_integrity()` can report `"Evidence integrity confirmed"` without ever recomputing a hash from real content, giving false assurance in the audit trail.
- Priority: High — this directly undermines the evidentiary-integrity value proposition core to SPEMASS.

---

*Concerns audit: 2026-09-05*


---

## Resolved: authentication and access control (2026-09-06)

The auth findings above predate the access-control work and are no longer accurate.
Current state:

| Concern as recorded above | Current state |
|---|---|
| "No RBAC middleware or dependency exists. Every API route is unauthenticated" | Every data route declares `Depends(get_current_user)`. There is no anonymous path: a request without a valid bearer token is rejected with 401. The demo fallback that resolved header-less requests to the first ADMIN row is gone. |
| "`create_access_token` issues a JWT with only `sub`/`exp` (no role claim)" | Access tokens carry `sub`, `role`, `typ`, `ver`, `jti`, `iat`, `nbf`, `exp`. Authorisation still reads the role from the database rather than trusting the claim; `ver` is checked against `User.token_version` so a password change, deactivation or logout-everywhere invalidates tokens already in circulation. |
| "`verify_password` accepts plaintext-equals-hash as valid" | Gone. Passwords are bcrypt with a per-password salt (`security.py`); pre-existing SHA-256 digests verify in constant time and are rehashed on the next successful login. |
| "`/auth/me` ignores the authenticated caller entirely" | `/auth/me` resolves the caller through `get_current_user`. |
| "CORS wide open (`allow_origins=["*"]`) with `allow_credentials=True`" | `allow_origins` is an explicit list from `settings.CORS_ORIGINS`. |
| "Hardcoded default `SECRET_KEY` committed to source" | The placeholder is rejected outright. With `DEMO_MODE=false` the app refuses to start without a real `SECRET_KEY`; in demo mode it generates an ephemeral one per process. |
| "`passlib[bcrypt]` is a declared dependency but never used" | bcrypt is used directly (the installed passlib does not work with bcrypt 5). `passlib` remains in `requirements.txt` and could now be dropped. |
| "No case-tenancy / row-level isolation enforced" | `accessible_cases` / `require_case_access` scope every case-bearing route to the cases a user leads or is named on, and `PUT /cases/{case_id}/team` is the control that grants membership. |
| "No tests for auth/security paths" | `backend/test_mvp.py` exercises login, case scoping and 403s on unauthorised cases. Dedicated regression tests for the header-less-request case were considered and deliberately left out of scope. |

Added alongside those fixes: an httpOnly rotating refresh-cookie session with reuse
detection, double-submit CSRF on the two cookie-authenticated routes, per-account
lockout plus a per-IP login throttle, administrator-only user provisioning
(`app/api/users.py`), and a `create_admin.py` bootstrap CLI.

Still open: no second factor, and the login rate limiter keeps its counters in
process memory, so it is per-worker.
