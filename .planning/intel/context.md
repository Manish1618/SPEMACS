# Context

Running notes keyed by topic. Primary source is planning.md (classified DOC, precedence 2), with narrative framing from SPEC.md and PRD.md and current-state notes from the codebase map.

---

## Product identity and tagline
- source: SPEC.md (header, lines 4-13)
- SPEMASS — Secure Pattern & Evidence Mapping and Analysis of Suspicious Structures. Context: SIH (Smart India Hackathon) project prototype.
- Tagline: "Connect Evidence. Reveal Networks. Empower Investigators."
- Positioning: an AI-powered investigation intelligence platform helping authorized investigators analyze fragmented investigative information across documents, people, communications, transactions, vehicles, organizations, locations, timelines, OSINT and digital evidence.
- Explicit anti-goal: "The goal is not a generic CRUD application or a chatbot with a dashboard. Build a technically credible, visually impressive, functional investigative intelligence platform that demonstrates a realistic end-to-end workflow."

## Core product principle
- source: SPEC.md §2, §45
- "Investigators ask questions. SPEMASS determines how to answer them."
- Final philosophy: "AI Discovers. Graph Connects. Maps Reveal Space. Timelines Reveal Sequence. OSINT Enriches. Evidence Explains. Counter-Evidence Challenges. Blockchain Preserves Integrity. Investigators Decide."
- The single most important capability: an investigator should be able to ask any reasonable question about an investigation in their own words, and SPEMASS should dynamically determine how to retrieve, correlate, analyze and explain the answer using all authorized available information.

## Value proposition
- source: PRD.md §1.2; planning.md §1.2
- "SPEMASS does not merely find connections. It explains the connection, shows where and when it occurred, traces it to evidence, identifies contradictions and evidence gaps, and preserves evidence integrity." planning.md adds "...with cryptographic proofs."
- Problem framing (planning.md §1.1): traditional investigation tools suffer from siloed datasets, static link charts, hallucination-prone AI summarizers, and disjointed maps and timelines.

## Target personas
- source: PRD.md §2.1
- Senior Field Investigator (Inspector/Detective) — investigates complex financial crimes, organized rings, multi-jurisdiction conspiracies; needs rapid link analysis, co-presence tracking on maps, timeline reconstruction without manual Excel merging.
- Intelligence Analyst (Forensic Data Analyst) — cross-case correlation, link discovery, deep anomaly analysis across CDRs and bank transactions; needs advanced graph queries, centrality metrics, OSINT enrichment with verification flags.
- Evidence Custodian & Prosecutor (Forensic Lead / Legal) — evidentiary compliance, forensic chain of custody, court-admissible documentation; needs cryptographic audit trails, SHA-256 verification, contradiction/gap reports.
- System Administrator / Lead (Security & IT Admin) — user access, case permissions, audit logs, security compliance across agency divisions.

## Core user journeys
- source: PRD.md §2.2
- Journey 1 — Multi-source case ingestion and tri-view analysis: investigator creates CASE-2024-001, uploads a scanned FIR PDF and a CDR CSV; SPEMASS computes SHA-256 hashes, logs initial custody events, runs OCR, extracts entities (Vikram Malhotra, +91-98110-XXXXX), resolves aliases; investigator enters the Synchronized Workspace where selecting Vikram highlights his graph node, plots his CDR cell-tower locations on the map, and places his calls on the timeline.
- Journey 2 — Universal AI deep query with contradiction surfacing: investigator asks where Vikram was on the evening of Feb 14 and what evidence connects him to vehicle DL-04-E-5544; AI plans a multi-source query, returns a grounded answer citing FIR line 42, CCTV log p. 3 and CDR tower records, and flags the contradiction that Witness Statement B claims he was out of town while CDR places his phone within 200m of the hotel at 19:34; AI provides interactive links highlighting map coordinates and timeline ticks.
- Journey 3 — Cryptographic integrity verification and court export: legal analyst selects a CCTV log evidence item and triggers Verify Integrity; the system re-hashes from storage, compares against the initial record and the ledger, and outputs an audit certificate confirming zero tampering.

## Signature features (SIH judging priorities)
- source: SPEC.md §35
- 1. Universal Investigation Copilot — investigator asks their OWN questions, no fixed question set.
- 2. Graph + Map + Timeline Intelligence — one selection updates all three.
- 3. Investigation Replay — watch the investigation evolve over time.
- 4. Evidence + Counter-Evidence — the AI actively challenges its own analytical hypothesis.
- 5. Evidence Integrity — hash → provenance → custody → ledger verification → tamper detection.
- 6. OSINT Enrichment — internal evidence plus authorized public information.

## Scope tiering
- source: PRD.md §3
- [MVP]: MVP-01 through MVP-25 — fully functional web app, graph store, map, timeline, Universal AI, SHA-256, mock blockchain.
- [MVP-Lite]: advanced NLP / entity matching via heuristics and RapidFuzz; controlled OSINT scraper against mock synthetic registry endpoints.
- [Post-MVP]: live national police feeds, facial/voice biometrics, production distributed cluster, HSM keys, automated multi-agency federation.

## Explicit non-goals
- source: SPEC.md §36; planning.md §1.4
- Deferred: real CCTNS/ICJS integration, live nationwide data, real-time streaming CDR, production-scale deployment, advanced facial recognition, advanced speaker recognition, predictive policing, autonomous enforcement decisions, large-scale distributed deployment. Build clean interfaces so these can be integrated later.
- Never in scope: automated criminal profiling, automated sentencing/charging recommendations, autonomous actions, unsupervised external network scanning, unconstrained generative chat without citations, storing raw sensitive evidence payloads on public blockchains, automated legal warrant execution, live feeds into classified national security networks, unverified dark-web scraping without warrant clearance.

## Example investigator questions (illustrative, not a fixed set)
- source: SPEC.md §3
- "Who is connected to Person A?" / "How are Person A and Person B connected?" / "Where was Person A during the evening of August 15?" / "What changed in this network during the last 30 days?" / "Which people appear across multiple cases?" / "Find unusual communication patterns." / "Why was Person B flagged?" / "What evidence supports this relationship?" / "What evidence contradicts this hypothesis?" / "Find all relationships between these two groups." / "Which locations have the highest concentration of related events?" / "Find information about this person from authorized public sources." / "Compare Case 101 with Case 117." / "What information are we missing?" / "Show me everything connecting Person A to Organization X." / "Find unusual relationships created after Person A met Person B." / "Summarize everything known about this investigation." / "I don't know what I'm looking for. Find the most unusual changes in this case."
- SPEC is emphatic that these are examples only and must not become the capability boundary.

## Golden demo script — Operation ShadowNet
- source: planning.md §10; SPEC.md §41
- Scenario: "Operation ShadowNet — Cross-Border Smuggling & Hawala Network", case CASE-2024-8812 (Hawala Syndicate).
- Step 1 Ingestion: upload raw FIR scan (PDF) and CDR record (CSV); OCR runs in real time; extracts Vikram Malhotra, phone +91-98110-XXXXX, Toyota Fortuner DL-04-E-5544; hashes the file (SHA-256 7f8a...9c12).
- Step 2 Entity resolution: graph resolves "Vicky" from a WhatsApp chat to "Vikram Malhotra" at confidence 0.94; shows a connection to previously closed CASE-2023-1104.
- Step 3 Tri-view: selecting Vikram zooms the map to three hotspots (Aerocity Hotel, Connaught Place, Mumbai Port); timeline shows 14 events across Jan 15 - Feb 28; scrubbing to Feb 14 shows co-presence of Vikram and Amit Shahani at Aerocity Hotel at 19:30.
- Step 4 AI query: "What links Vikram Malhotra to the foreign bank transfer on Feb 15, and is there any contradicting evidence?" → answer citing Aerocity_CCTV_Log.pdf p.3 and Bank_Tx_Log.csv row 442, contradiction flag (Witness Statement #2 places Vikram in Dubai on Feb 14 vs CDR tower at Aerocity 19:34, CDR_98110.csv), evidence gap (missing CCTV logs for the bank branch entrance).
- Step 5 Integrity: Verify Integrity on the CCTV evidence recalculates SHA-256, matches on-chain hash 0x44ab..., confirms INTEGRITY VERIFIED; investigator exports a case summary report with a full cryptographic audit trail.
- SPEC §41 frames the same arc as a 5-minute demo and requires it feel like one coherent investigation rather than a collection of disconnected features.

## Technology selection rationale (as argued in planning.md)
- source: planning.md §2.2
- FastAPI: native ecosystem compatibility with ML libraries, graph algorithms, OCR engines, vector math, and LangChain/LlamaIndex; native async I/O and auto-generated OpenAPI docs.
- Neo4j: native graph storage and traversal; Cypher for multi-hop queries, shortest paths, temporal filtering; GDS algorithms (PageRank, Louvain, betweenness) with index-free adjacency.
- PostgreSQL 16 + pgvector: avoids running a separate vector database for the MVP while giving ACID guarantees for case records, users, audit logs, and custody transactions.
- Cytoscape.js: performant canvas/WebGL link analysis for thousands of nodes with compound nodes, force-directed layouts (Cola, CoSE-Bilkent), and programmatic event hooks.
- MapLibre GL JS: open-source Mapbox GL fork, no license fees, hardware-accelerated vector tiles, cluster-to-pin transitions, custom layers for time-stamped trajectory animation.
- Next.js 14 + React + TypeScript: strict typing to prevent runtime state bugs across synchronized views; modular components for sub-second synchronized updates via Zustand or React Context.

## Reference architecture (as drawn in planning.md)
- source: planning.md §3.1, §1.1
- Investigator Workspace (Next.js SPA + state orchestrator) → HTTPS/WSS with JWT auth → API Gateway (FastAPI, RBAC, rate limiting, audit intercept) → three parallel subsystems: Ingestion & Extraction (CSV/JSON loaders, Tesseract OCR, spaCy NER, entity resolver, geocoding), Universal AI Investigator (query planner, GraphRAG router, tool execution engine, grounded generator, citation validator), and Evidence & Blockchain (SHA-256 engine, custody tracker, smart contract logger) → Persistence: Neo4j, PostgreSQL + pgvector, MinIO, Redis.
- Pipeline framing: Authorized Sources → Ingestion/OCR → Entity Resolution → Temporal Graph → Map & Timeline → Universal AI/GraphRAG → Evidence Engine → Chain of Custody → Human Investigator Decision (explainable and audited).

## Ingestion pipeline detail
- source: planning.md §3.2
- 1. Upload of PDF, image, CDR CSV, bank transaction Excel, or FIR record by an authorized investigator.
- 2. Cryptographic sealing: file written to object storage, SHA-256 computed immediately and recorded in the Evidence table with an initial CustodyEvent.
- 3. Extraction: structured tabular data via deterministic schema mappers; unstructured documents via PyMuPDF text extraction plus Tesseract OCR preprocessing.
- 4. NLP: entities (Person, Phone, Vehicle, Organization, Location, Account) and events (Call, Transaction, Meeting, Incident); geocoding assigns exact (latitude, longitude) to extracted locations.
- 5. Entity resolution: rule-based matchers, fuzzy matchers, semantic vector similarity, with the 0.70/0.90 threshold policy.
- 6. Graph and vector ingestion: entities/relationships/events committed to the graph with timestamp, confidence, source document ID and case ID; document chunks and entity descriptions embedded via Sentence-Transformers into pgvector.

## Tri-view synchronization behavior
- source: planning.md §6.1
- Frontend implements a single unified state machine (selected entities, date filter, case) to avoid jitter and visual desynchronization.
- Graph node click → filters map pins to locations where the selected entity participated in an event, filters timeline to that entity's chronological trajectory.
- Map pin click → focuses the graph on the associated event node and its immediate neighbor entities, highlights the precise timeline tick.
- Timeline scrubber drag → hides relationships formed after the selected timestamp (temporal network replay) and animates map paths.

## Docs-vs-implementation divergence (central context for planning)
- source: ../codebase/CONCERNS.md ("Summary: PRD Promises vs Implementation Reality"), ../codebase/ARCHITECTURE.md, ../codebase/STACK.md; contrasted against SPEC.md §31, PRD.md §1.1, planning.md §2.1
- The three ingested documents describe a TARGET state. The codebase map describes the CURRENT state. The gap is the work to be done.
- Graph: target Neo4j 5.x with Cypher and GDS; actual in-memory `networkx.MultiDiGraph` rebuilt from SQLite at startup, no Neo4j dependency, driver, or Cypher anywhere.
- Relational/vector: target PostgreSQL 16 + pgvector; actual SQLite via SQLAlchemy with no embedding model, no vector index, no pgvector dependency, and no `document_chunks` table.
- Object storage: target MinIO/S3; actual local filesystem `backend/storage/`.
- Queue/cache: target Redis 7.x + Celery/ARQ; actual none.
- Frontend: target Next.js 14 App Router + Shadcn + Zustand; actual Vite + React 19 with prop-drilled `useState` in `App.tsx`, no router, no state library.
- Map: target MapLibre GL JS; actual Leaflet (permitted by SPEC §31, which allows "MapLibre GL JS or Leaflet").
- Timeline: target vis-timeline; actual a custom chronological strip component.
- Copilot: target dynamic query planner + GraphRAG multi-tool agent with citation enforcement; actual `if/elif` keyword matching on "vikram"/"rahul"/"golden falcon"/"250" returning pre-written JSON, with an ungrounded Gemini REST fallback that fabricates a `confidence_score: 0.90` and a citation object. Directly violates SPEC §4 and SPEC §43.
- Ledger: target permissioned Hyperledger/EVM anchoring; actual `uuid.uuid4()`-derived fake `tx_hash` and incrementing fake block number in a SQLite `BlockchainRecord` table, with `contract_address` a literal placeholder string.
- OCR/NLP: target Tesseract + PyMuPDF + spaCy; actual none present in `requirements.txt` and no OCR code.
- Community detection: target Louvain via Neo4j GDS; actual `nx.connected_components`.
- Auth/RBAC: target JWT with role claims plus RBAC enforced on every endpoint and LLM tool call; actual login mints a token nothing validates, no route guards, `/auth/me` ignores the caller.
- OSINT: target controlled enrichment with provenance; actual `backend/app/services/osint.py` returns simulated lookups.
- Tests/CI/deployment: target Docker Compose 1-click plus a UAT suite; actual no test framework, no pytest, no Jest/Vitest, no Dockerfile, no CI.
- Codebase-map guidance verbatim: "Anyone planning new phases against this codebase should treat PRD.md/planning.md as aspirational, not descriptive."

## Currently working features worth preserving
- source: ../codebase/ARCHITECTURE.md, ../codebase/STACK.md; SPEC.md §1 ("Do NOT unnecessarily rewrite working components")
- Layered FastAPI monolith with one router per domain under `/api/v1` and a clean service layer.
- Tri-view synchronization is genuinely implemented: `selectedNodeId` / `selectedEventId` / `highlightedNodeIds` / `highlightedCoords` in `frontend/src/App.tsx` fan out to Cytoscape graph, Leaflet map, and the timeline, with symmetric handlers in all three directions.
- Graph engine already provides entity/relationship CRUD, fuzzy entity resolution, k-hop neighborhoods, shortest path, degree/betweenness centrality, connected components, cross-case overlap, and impossible-travel anomaly detection.
- Evidence pipeline already produces SHA-256 hashes, Evidence/CustodyEvent/BlockchainRecord rows, verification, and a tamper simulate/restore demo path.
- AI responses already carry a `HighlightAction` payload that drives the workspace views from an answer (`App.tsx:134`), which is the mechanism SPEC §10 visual actions require.
- Synthetic seed data exists at `backend/data/synthetic/` and is loaded by `seed_database_and_graph` on startup.

## Ingest provenance
- source: .planning/intel/classifications/*.json
- SPEC.md → type SPEC, confidence high, manifest_override true, precedence 0, locked false, cross_refs [PRD.md, planning.md]. Classifier note: document self-declares supersession over PRD.md and planning.md.
- PRD.md → type PRD, confidence high, manifest_override true, precedence 1, locked false, cross_refs [].
- planning.md → type DOC, confidence high, manifest_override true, precedence 2, locked false, cross_refs []. Classifier note: the document self-labels "Classification: Technical Specification / Engineering Architecture" and contains SPEC-like content (stack table, Neo4j schema, PostgreSQL DDL, architecture diagrams) that would otherwise indicate SPEC; the manifest override to DOC wins, placing it at the lowest precedence of the ingested set.
- Cross-reference graph is acyclic: SPEC.md → {PRD.md, planning.md}; both leaves have no outbound references. Maximum traversal depth 2, well under the depth-50 cap.
