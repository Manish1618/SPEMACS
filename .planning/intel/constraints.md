# Constraints

Technical constraints extracted from SPEC.md (SPEC, precedence 0), plus constraint-shaped content from PRD.md (§8 NFRs, §10 API) and planning.md (§2.1 stack, §5 schemas, §8 protocol). Current-build constraints are sourced to the codebase map at `../codebase/` and are recorded here because they bound what the target constraints can assume.

Type values: `api-contract` | `schema` | `nfr` | `protocol`.

---

## Target technology stack (recommended, conditional)
- source: SPEC.md §31
- type: protocol
- content: "Use the existing stack if already established. Otherwise prefer:" Frontend React/Next.js + TypeScript + Tailwind CSS; Graph Neo4j + Cytoscape.js; Map MapLibre GL JS or Leaflet; Backend Python + FastAPI; Relational DB PostgreSQL; Vector search pgvector or Qdrant; Object storage MinIO / S3-compatible; OCR PaddleOCR or Tesseract; NLP spaCy + Transformers; AI an appropriate LLM provider/model with structured tool/function calling where available; Ledger Hyperledger Fabric/Besu or an appropriate permissioned ledger; Deployment Docker + Docker Compose for prototype. "Do not introduce technologies without a concrete reason." The conditional clause is load-bearing: the stack table applies only when no stack is already established.

## Target technology stack (mandated, unconditional)
- source: planning.md §2.1, §2.2
- type: protocol
- content: Presentation Next.js 14 (App Router) + TypeScript + TailwindCSS + Shadcn UI; Visualizations Cytoscape.js + MapLibre GL JS + vis-timeline; API Python FastAPI + Pydantic v2 + LangChain/LlamaIndex core tooling; Knowledge Graph Neo4j 5.x (Cypher + GDS Library); Relational & Vector DB PostgreSQL 16 + pgvector; Document & File Storage MinIO / AWS S3; OCR Tesseract + PyMuPDF (fitz) + Unstructured.io; NLP spaCy NER + Sentence-Transformers + RapidFuzz + custom deduplication; Caching & Queue Redis 7.x + Celery/ARQ; Blockchain Hyperledger Fabric or a local Ethereum/EVM testbed with smart contract logs; Security JWT (OAuth2/OIDC) + RBAC + AES-256 + Cryptography (PyCA). Stated unconditionally, with no "use existing stack" escape clause.

## Current implemented stack
- source: ../codebase/STACK.md, ../codebase/ARCHITECTURE.md
- type: protocol
- content: Python 3.x + FastAPI >=0.110 + Uvicorn + SQLAlchemy >=2.0.28 + Pydantic >=2.6 backend; TypeScript + React ^19.2.8 + Vite ^8.2.2 + Tailwind ^3.4.17 frontend (no Next.js, no routing library, no state library — shared state is lifted `useState` in `frontend/src/App.tsx`); graph via `networkx>=3.2.1` in-memory MultiDiGraph (`backend/app/services/graph_engine.py`), no Neo4j driver or Cypher anywhere; persistence SQLite `backend/spemass.db` via SQLAlchemy, `DATABASE_URL`-swappable; visualization Cytoscape.js ^3.34.2 and Leaflet ^1.9.4 (not MapLibre); timeline is a custom component, not vis-timeline; blob storage is the local filesystem `backend/storage/` (no MinIO/S3 client); no Redis, no Celery/ARQ, no LangChain/LlamaIndex; LLM access is a raw `requests` REST call to Gemini in `backend/app/services/ai_investigator.py`; no pgvector, no embedding model, no vector index; no OCR dependency or code; no Dockerfile, docker-compose, or CI config; `pydantic-settings` is imported by `backend/app/core/config.py` but absent from `backend/requirements.txt`, so a clean `pip install -r requirements.txt` will not start the app.

## Graph store constraint — in-memory, non-durable
- source: ../codebase/ARCHITECTURE.md ("Architectural Constraints"), ../codebase/CONCERNS.md
- type: protocol
- content: `knowledge_graph` is a process-global mutable `TemporalKnowledgeGraph` singleton (`backend/app/services/graph_engine.py:290`) rebuilt from SQLite by `seed_database_and_graph` on every startup. Graph mutations made through the API are lost on restart unless written back to SQL. The singleton is not lock-protected, so concurrent mutating requests can race, and any move to multiple uvicorn workers gives each worker a divergent graph. There is no transactional coupling between SQLite commits and graph mutations.

## Performance NFRs
- source: PRD.md §8 (Performance), §4.3 FR-VIS-01, FR-VIS-04, §12.1
- type: nfr
- content: Graph query response for a 2-hop traversal over 50,000 nodes <= 350ms. Tri-view synchronization lag across Graph, Map, and Timeline <= 200ms. Universal AI Investigator initial streamed token response <= 2.0s. Network graph renders >= 1,000 nodes smoothly. planning.md RSK-03 mitigates large-graph latency with Cytoscape compound subgraph clustering, server-side k-hop limiters (default k=2), and WebGL rendering.

## Performance constraint — current analytics path
- source: ../codebase/CONCERNS.md ("Performance Bottlenecks")
- type: nfr
- content: `_build_subgraph_response()` calls `compute_graph_analytics()` (degree centrality, betweenness centrality, connected components) from scratch on every call, including from `get_k_hop_neighborhood` and `get_shortest_path` (`backend/app/services/graph_engine.py:247-250`). Betweenness centrality is O(V·E) or worse and is neither cached nor memoized, and runs over the entire graph for every small subgraph request. Separately, `_call_live_gemini()` performs a blocking synchronous `requests.post(...)` with an 8s timeout inside an async-capable FastAPI app (`backend/app/services/ai_investigator.py:174-224`), stalling the event loop for concurrent requests.

## Security and access NFRs
- source: PRD.md §8 (Security & Access); SPEC.md §32; planning.md RSK-04
- type: nfr
- content: RBAC with four roles — System Admin, Lead Investigator, Analyst, Viewer. Case-level isolation: users can only query cases explicitly assigned to them. End-to-end encryption: TLS 1.3 in transit, AES-256 at rest for both database and object storage. Row-level and graph-level case tenancy filters, with strict RBAC checks injected into all LLM tool calls. Secrets via environment variables; no hardcoded API keys; no sensitive information in frontend source.

## Security constraint — current enforcement state
- source: ../codebase/CONCERNS.md ("Known Bugs", "Security Considerations"), ../codebase/STACK.md
- type: nfr
- content: No RBAC middleware or dependency exists; no route in `backend/app/api/*.py` carries a `Depends(get_current_user)` guard, so every endpoint is unauthenticated. `create_access_token` issues a JWT with only `sub`/`exp` and no role claim, and nothing validates the token on subsequent requests. `GET /auth/me` (`backend/app/api/auth.py:48-57`) ignores the caller entirely and returns `db.query(User).first()` or a hardcoded `rajiv_sen` fallback. `verify_password` (`backend/app/core/security.py:12-14`) returns True when the plaintext equals the stored hash. `SECRET_KEY` has a committed default (`backend/app/core/config.py:9`) and the password salt is a fixed literal (`backend/app/core/security.py:9`); `passlib[bcrypt]` is declared but unused in favor of raw salted SHA-256. CORS is `allow_origins=["*"]` with `allow_credentials=True` (`backend/app/main.py:17-24`). No case-tenancy or row-level isolation exists on any graph query method or API handler.

## Integrity and compliance NFRs
- source: PRD.md §8 (Integrity & Compliance); SPEC.md §32
- type: nfr
- content: Immutable append-only audit logging for all user queries, downloads, and merges. Automated PII masking/redaction on export views where required by policy. Zero raw sensitive file payloads placed on public or unauthorized networks.

## Reliability NFRs
- source: PRD.md §8 (Reliability)
- type: nfr
- content: High-availability architecture with containerized auto-restart. Data durability with point-in-time recovery for PostgreSQL and Neo4j backups.

## Graph schema — node and relationship model
- source: SPEC.md §7; planning.md §5.1, §5.2; PRD.md §4.2 FR-KNG-01
- type: schema
- content: Entity labels PERSON, PHONE, VEHICLE, ORGANIZATION, LOCATION, ACCOUNT, TRANSACTION, CASE, EVENT, DOCUMENT, EVIDENCE, OSINT_SOURCE, HYPOTHESIS, AI_INSIGHT. Relationship types CALLED, USED, OWNED, ASSOCIATED_WITH, WORKS_FOR, LOCATED_AT, INVOLVED_IN, PARTICIPATED_IN, TRANSFERRED_TO, CONNECTED_TO, SUPPORTED_BY, CONTRADICTED_BY, MENTIONED_IN, DERIVED_FROM. Relationships must carry metadata: `timestamp`, `source`, `confidence`, `evidence_id`, `case_id`. planning.md §5.2 gives concrete Cypher forms: `(:Person)-[:ASSOCIATED_WITH {relationship_type, confidence, case_id, evidence_ids, verified_by_investigator}]->(:Person)`; `(:Person)-[:USED {from_date, to_date, evidence_ids, source}]->(:Vehicle {plate_number, make, model})`; `(:Event {id, event_type, timestamp, summary, case_id})-[:OCCURRED_AT]->(:Location {id, address, latitude, longitude})`; `(:Event)-[:SUPPORTED_BY {confidence}]->(:Evidence {id, sha256_hash, evidence_type, integrity_status})-[:FROM_SOURCE]->(:Document {id, filename, storage_uri})`. planning.md §5.1 adds `[:INVOLVED_IN]` to Case and `[:WORKS_FOR]` to Organization. Provenance is mandatory: "Do not represent an analytical relationship as established fact without provenance."

## Relational schema — cases, documents, evidence, custody, chunks
- source: planning.md §5.3
- type: schema
- content: `cases(case_id VARCHAR(64) PK, title VARCHAR(255) NOT NULL, description TEXT, status VARCHAR(32) DEFAULT 'ACTIVE', classification_level VARCHAR(32) DEFAULT 'RESTRICTED', lead_investigator_id UUID NOT NULL, created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ)`. `documents(document_id PK, case_id FK ON DELETE CASCADE, filename, file_type, storage_path TEXT NOT NULL, sha256_hash CHAR(64) NOT NULL, ocr_extracted_text TEXT, parsed_metadata JSONB, uploaded_by UUID NOT NULL, created_at)`. `evidence(evidence_id PK, case_id FK, document_id FK, title, evidence_type, sha256_hash CHAR(64) NOT NULL, integrity_status VARCHAR(32) DEFAULT 'VERIFIED', blockchain_tx_id VARCHAR(128), blockchain_block_num BIGINT, blockchain_timestamp TIMESTAMPTZ, created_at)`. `custody_events(event_id UUID PK, evidence_id FK ON DELETE CASCADE, action VARCHAR(64) NOT NULL /* UPLOAD, VERIFY_HASH, TRANSFER, VIEW, EXPORT */, performed_by UUID NOT NULL, ip_address VARCHAR(45) NOT NULL, details JSONB, sha256_at_event CHAR(64) NOT NULL, tamper_detected BOOLEAN DEFAULT FALSE, created_at)`. `document_chunks(chunk_id UUID PK, document_id FK, case_id FK, content TEXT NOT NULL, chunk_index INT NOT NULL, embedding vector(384) /* all-MiniLM-L6-v2, or 1536 for OpenAI */, metadata JSONB, created_at)` with `CREATE EXTENSION IF NOT EXISTS vector;` and `CREATE INDEX ON document_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);`.

## Relational schema — current implementation
- source: ../codebase/ARCHITECTURE.md ("Component Responsibilities", "Key Abstractions")
- type: schema
- content: SQLAlchemy models in `backend/app/models/entities.py`: User, Case, Document, Evidence (line 57), CustodyEvent (line 77), BlockchainRecord (line 92), plus graph-seed entity tables. Engine/session in `backend/app/models/database.py` with `check_same_thread: False`. No `document_chunks`/embedding table and no vector extension. `BlockchainRecord.contract_address` defaults to the literal string `"0x71C2B890a8813C124231EVID_LEDGER_MOCK"` (`backend/app/models/entities.py:101`).

## Copilot response contract
- source: SPEC.md §38, §20
- type: api-contract
- content: Internal structured response object `{ "answer": "...", "confidence": "medium", "sources": [], "evidence": [], "contradictions": [], "limitations": [], "entities": [], "visual_actions": [], "query_plan": [], "requires_clarification": false }`. Internal chain-of-thought must not be exposed. The rendered answer shape (SPEC §20) is ANSWER / Evidence / Sources / Confidence (High|Medium|Low) / Contradictions / Limitations / Suggested next step, with clickable citations that navigate back to the underlying evidence.

## Visual action contract
- source: SPEC.md §10
- type: api-contract
- content: Copilot responses may return structured UI actions: `{ "action": "FOCUS_GRAPH_NODE", "entity_id": "person_123" }`, `{ "action": "FILTER_MAP", "event_ids": ["event_1", "event_2"] }`, `{ "action": "FOCUS_TIMELINE", "start": "...", "end": "..." }`. Actions must be implemented safely and validated on the frontend.

## API surface — SPEC namespaces
- source: SPEC.md §37
- type: api-contract
- content: `/auth`, `/cases`, `/entities`, `/relationships`, `/events`, `/documents`, `/evidence`, `/graph`, `/graph/query`, `/graph/analytics`, `/map/events`, `/timeline`, `/osint`, `/hypotheses`, `/insights`, `/copilot/query`, `/copilot/plan`, `/copilot/actions`, `/integrity`, `/chain-of-custody`, `/audit`. SPEC explicitly permits deviation: "The exact API design may differ based on the existing project."

## API surface — PRD concrete routes
- source: PRD.md §10
- type: api-contract
- content: `POST /api/v1/auth/login` (returns JWT with RBAC claims); `GET /api/v1/auth/me` (profile + case permissions); `GET|POST /api/v1/cases`; `GET /api/v1/cases/{case_id}`; `POST /api/v1/cases/{case_id}/upload` (multipart PDF/CSV/images, computes hash); `GET /api/v1/documents/{doc_id}/ocr`; `GET /api/v1/cases/{case_id}/graph` (Cytoscape JSON); `GET /api/v1/cases/{case_id}/map-events` (GeoJSON FeatureCollection); `GET /api/v1/cases/{case_id}/timeline`; `POST /api/v1/entities/merge`; `POST /api/v1/ai/investigate`; `GET /api/v1/evidence/{evidence_id}`; `POST /api/v1/evidence/{evidence_id}/verify`; `GET /api/v1/evidence/{evidence_id}/custody`; `POST /api/v1/osint/expand`.

## API surface — current implementation
- source: ../codebase/ARCHITECTURE.md, ../codebase/STACK.md
- type: api-contract
- content: Routers mounted under `settings.API_V1_STR` = `/api/v1` in `backend/app/main.py`: `auth.py`, `cases.py`, `graph.py`, `map_timeline.py`, `evidence.py`, `ai.py`, `osint.py`, `ingestion.py`, plus `/` and `/health`. Implemented endpoints include `GET /api/v1/graph/case/{case_id}`, `POST /api/v1/ai/investigate`, `POST /api/v1/evidence/{id}/verify`, `POST /api/v1/evidence/{id}/simulate-tamper`, and `restore-clean`. No `/hypotheses`, `/insights`, `/copilot/plan`, `/copilot/actions`, `/integrity`, or `/audit` namespace. Frontend hardcodes the base URL `http://localhost:8000/api/v1` in `frontend/src/lib/api.ts` with no `VITE_*` env wiring.

## Evidence integrity protocol
- source: SPEC.md §21, §22, §23; planning.md §8.1; PRD.md §7.1
- type: protocol
- content: Evidence → SHA-256 Hash → Evidence ID → Timestamp → Custodian → Chain of Custody. Custody lifecycle: Created → Registered → Hashed → Custodian Assigned → Transferred → Analyzed → Transferred → Verified, recording actor, timestamp, action, evidence ID, hash, and authorization context. Ledger anchoring commits hash + metadata (case_id, uploaded_by, timestamp, parent document ID) to a permissioned ledger; verification recalculates the hash from object storage and compares it against the relational record and the on-chain log, returning `INTEGRITY_MISMATCH_DETECTED` with a diff alert on divergence. PRD §7.1 traceability chain: Insight → Analytical Explanation → Supporting Evidence → Source Document → SHA-256 Hash → Chain of Custody Event → Blockchain Proof. Legal boundary (SPEC §22, planning.md §8.1): the ledger proves the recorded hash history is unchanged; it does not prove the underlying evidence is truthful. Sensitive raw files are never stored on-chain.

## Evidence integrity constraint — current implementation
- source: ../codebase/CONCERNS.md, ../codebase/ARCHITECTURE.md ("Evidence Integrity Flow")
- type: protocol
- content: `create_evidence_record()` (`backend/app/services/evidence.py:26-40`) mints `tx_hash` as `f"0x{uuid.uuid4().hex}{uuid.uuid4().hex}"[:66]` with a monotonically incrementing fake `block_number` and stores it in the SQLite `BlockchainRecord` table. There is no chain, contract, consensus, or web3 dependency. `verify_evidence_integrity()` compares the SQLite-stored hash against a record held in the same SQLite database, so it cannot detect deliberate tampering by anyone with DB write access. It can also report `VERIFIED` without recomputing any hash when `document.extracted_text` and `current_content_bytes` are both absent (`backend/app/services/evidence.py:88-97`). A module-level `tampered_mock_cache: Dict[str, bytes]` demo backdoor lives in the production evidence router (`backend/app/api/evidence.py:12,31,50,68-69`) with routes that write, read, and delete it.

## Entity resolution thresholds
- source: SPEC.md §24; PRD.md §4.2 FR-RES-01; planning.md §3.2 step 5, RSK-02
- type: protocol
- content: Deterministic matchers on exact phone numbers, vehicle license plates, and national IDs. Fuzzy matchers on names/aliases (Levenshtein/RapidFuzz) plus semantic vector similarity. Threshold policy: confidence >= 0.90 merges with provenance links; confidence in [0.70, 0.89] flags `Potential Match - Requires Human Verification` and requires explicit investigator approval; uncertain identities are never silently merged.

## OSINT protocol
- source: SPEC.md §14, §15; planning.md §7.1; PRD.md §6
- type: protocol
- content: Flow is Question → Authorization → Public Source Discovery → Collection → Extraction → Verification → Entity Resolution → Evidence Preservation → Knowledge Graph → GraphRAG → Investigator. Manual investigator trigger only ("Expand with OSINT"), preceded by a lawful-scope check against jurisdiction policy and synthetic/public-only parameters. Every OSINT result records source, URL/reference, timestamp, source type, reliability, extracted entity, relationship, evidence ID, hash where applicable, confidence, and case ID. Confidence below 0.90 is marked `Potential Match — Human Verification Required` and rendered with dashed borders until confirmed. Prohibited: credential bypass, private-account access, unauthorized system access, restricted database access, surveillance of private individuals outside authorization, dark-web scraping without warrant clearance. Source-independence analysis distinguishes originating, duplicated, copied, and derivative sources.

## Responsible-AI prohibitions
- source: SPEC.md §28, §16, §17; PRD.md §1.3, §5.2 rule 5; planning.md §1.3, §1.4
- type: protocol
- content: SPEMASS must not determine guilt, determine innocence, recommend arrest solely from AI output, recommend punishment, infer criminal intent from association, infer guilt from co-location, infer guilt from graph centrality, treat OSINT mentions as proof, treat anomaly scores as proof, or present speculation as fact. Prohibited output categories also include automated criminal profiling, predictive policing, automated sentencing/charging recommendations, autonomous actions, unsupervised external network scanning, and unconstrained generative chat without citations. Every output must be typed as OBSERVED FACT, SOURCE INFORMATION, ANALYTICAL INFERENCE, POTENTIAL RELATIONSHIP, HYPOTHESIS, or UNKNOWN. Language must be objective ("Associated with", "Present at location", "Recorded in transaction"), never prejudicial ("Guilty", "Criminal mastermind", "Perpetrator"). Human investigators remain the final decision-makers.

## AI implementation prohibitions
- source: SPEC.md §4, §43
- type: protocol
- content: Do NOT build `if question == "..."` → fixed query routing. Do NOT create a finite question dictionary and present it as AI. "Never hardcode fake AI answers merely to make the UI appear functional." If an external API/key is unavailable, implement a clean mock/local provider so the demo still runs locally — this permits a local provider stub, not canned answers.

## AI implementation constraint — current violation
- source: ../codebase/CONCERNS.md ("Tech Debt", "Fragile Areas"), ../codebase/ARCHITECTURE.md ("Anti-Patterns")
- type: protocol
- content: `UniversalAIInvestigator.investigate()` (`backend/app/services/ai_investigator.py:21-133`) matches hardcoded substrings ("rahul", "vikram", "golden falcon", "250") and returns pre-written answer/citation payloads via `_build_vikram_swiss_transfer_response`, `_build_vikram_location_response`, and `_build_cross_case_response`. Only unmatched queries fall through to `_call_live_gemini` (`ai_investigator.py:174-224`), which has no grounding, no tool use, and no citation enforcement — it asks Gemini a free-text question and returns the result with a fabricated `confidence_score: 0.90` and a fabricated citation object. The `"vikram" in query_lower` condition appears in three separate branches with order-dependent behavior. This is the exact pattern SPEC.md §4 and §43 forbid, so the Copilot is unbuilt rather than partially built.

## Anomaly explanation protocol
- source: SPEC.md §17; PRD.md §4.4 FR-ANA-04
- type: protocol
- content: Every anomaly must state observed behavior, baseline, deviation, data sources, evidence, confidence, and alternative explanations, with a clear rule explanation (e.g. "Entity logged in Delhi and Mumbai within 30 minutes"). Never "This person is suspicious because the AI says so" — always "This activity deviates from the established baseline."

## Citation guardrail protocol
- source: planning.md §4, §4.1, RSK-01; PRD.md §5.2 rule 3
- type: protocol
- content: "Zero citations = zero claims." Every assertion links to a specific `[Evidence-ID:Doc-Page-Line]` reference. The generation layer runs a post-processing verification pass: any fact or relationship with no matching retrieved entity/chunk is stripped or marked `[Unverified Investigator Lead]`. Contradictions between retrieved sources are surfaced under `Contradicting Evidence & Discrepancies`. RSK-01 mitigation additionally requires schema-enforced output plus regex post-validation that every claim maps to an active EvidenceID.

## Delivery sequencing protocol
- source: SPEC.md §42, §43; planning.md §9
- type: protocol
- content: SPEC §42 defines Phases 0-18: repository inspection + architecture plan; data model + synthetic dataset; backend APIs; knowledge graph; graph UI; actual map; timeline; graph-map-timeline synchronization; document/OCR pipeline; entity resolution; Universal Copilot + dynamic query planner; GraphRAG; evidence engine; OSINT; anomaly + hypothesis + counter-evidence; hashing + chain of custody + ledger; security + audit; UX polish + demo scenario; testing + bug fixing. "Do not polish the UI while core functionality is still broken." planning.md §9 defines a different 10-phase sprint plan (Foundation & RBAC; Ingestion & Document Intelligence; Knowledge Graph & Entity Resolution; Synchronized Visual Workspace; Graph Analytics & Cross-Case; Evidence & Blockchain Integrity; OSINT Enrichment; Universal AI Investigator & GraphRAG; Explainability, Counter-Evidence & Gaps; Hardening, UAT, Testing & Packaging) with per-phase Definitions of Done.

## Testing constraint — current state
- source: ../codebase/STACK.md, ../codebase/TESTING.md, ../codebase/CONCERNS.md ("Test Coverage Gaps")
- type: protocol
- content: No test framework is configured. `pytest` is absent from `backend/requirements.txt`; no Jest/Vitest config exists in `frontend/`. `backend/test_mvp.py` is a standalone script issuing `requests` calls against a running server, not an integrated suite, and there is no CI configuration anywhere in the repo. Auth/security paths and evidence-integrity edge cases are entirely untested.

## Risk register
- source: planning.md §11
- type: protocol
- content: RSK-01 LLM hallucination of case evidence (Critical/Medium) — schema-enforced output, regex post-validation against active EvidenceIDs, ungrounded claims stripped. RSK-02 entity resolution false-positive merge (High/Medium) — >= 0.90 merge threshold, 0.70-0.89 human approval. RSK-03 visual latency with graphs >50k nodes (Medium/High) — compound subgraph clustering, server-side k-hop limiters (k=2 default), WebGL rendering. RSK-04 unauthorized data exfiltration / cross-case leak (High/Low) — row-level and Cypher-level case tenancy filters, RBAC injected into all LLM tool calls. RSK-05 document OCR failure on degraded scans (Medium/Medium) — multi-pass OpenCV image enhancement (binarization, deskewing) before Tesseract.

## Deployment topology
- source: planning.md §12.1, §12.2; PRD.md §12.1; SPEC.md §31
- type: protocol
- content: Local prototype `docker-compose.yml` services — `spemass-frontend` (Next.js 14, port 3000), `spemass-backend` (FastAPI, 8000), `spemass-neo4j` (7474, 7687), `spemass-postgres` (PostgreSQL 16 + pgvector, 5432), `spemass-minio` (9000, 9001), `spemass-redis` (6379), `spemass-blockchain-mock` (Ganache/Hardhat EVM, 8545). Required outcome: complete Docker Compose orchestration for 1-click local startup. Production roadmap (post-MVP): Kubernetes (EKS/GKE) with autoscaling Celery/FastAPI workers, AWS S3 with Object Lock (WORM), permissioned Hyperledger Fabric across agency nodes, HSM-signed custody keys, mTLS between microservices.

## Deployment constraint — current state
- source: ../codebase/STACK.md ("Platform Requirements")
- type: protocol
- content: No Dockerfile, docker-compose, or CI/CD configuration exists anywhere in the repo; no deployment target is defined in code. Backend runs via `python -m app.main` or `uvicorn app.main:app --reload` on port 8000 with `reload=True` in the entrypoint. Frontend runs via `npm run dev` / `npm run build` (`tsc -b && vite build`). `backend/spemass.db` is present in the working tree. `backend/.env` exists in the working tree and must be verified git-ignored.
