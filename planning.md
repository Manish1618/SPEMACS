# SPEMASS: Engineering Plan, Architecture Blueprint & Delivery Roadmap
**Project Name:** Secure Pattern & Evidence Mapping and Analysis of Suspicious Structures (SPEMASS)  
**Document Version:** 1.0.0  
**Target Milestone:** MVP Release & Production Blueprint  
**Classification:** Technical Specification / Engineering Architecture

---

## 1. Executive Summary & Goals

### 1.1 Mission & Vision
SPEMASS is an AI-powered, evidence-grounded investigation decision-support platform designed to assist authorized investigators in transforming fragmented, heterogeneous case data into explainable relationship, spatial, temporal, and cross-case intelligence. 

Traditional investigation tools suffer from siloed datasets, static link charts, hallucination-prone AI summarizers, and disjointed maps and timelines. SPEMASS resolves these bottlenecks by pairing a **Temporal Knowledge Graph (Neo4j)** with an **Actual Interactive Map (MapLibre/Leaflet)**, a **Chronological Event Timeline**, and an **Evidence Grounding Engine (SHA-256 + Permissioned Blockchain Ledger)**, orchestrated through a **Universal AI Investigator (GraphRAG + LLM Tool-Use Pipeline)**.

```
+----------------------------------------------------------------------------------------------------+
|                                           SPEMASS PIPELINE                                         |
|                                                                                                    |
|  [Authorized Sources]  -->  [Ingestion / OCR]  -->  [Entity Resolution]  -->  [Temporal Graph]     |
|                                                                                       |            |
|  [Chain of Custody]    <--  [Evidence Engine]  <--  [Universal AI / GraphRAG]  <-- [Map & Timeline] |
|           |                                                                                        |
|           +-------------->  [Human Investigator Decision (Explainable & Audited)]                  |
+----------------------------------------------------------------------------------------------------+
```

### 1.2 Core Differentiator
> **SPEMASS does not merely find connections. It explains the connection, shows where and when it occurred, traces it directly to verifiable evidence, identifies contradictions and evidence gaps, and preserves evidence integrity with cryptographic proofs.**

### 1.3 Strict Operational Boundaries & Ethical Mandates
1. **Decision Support Only:** SPEMASS never determines guilt, intent, liability, or criminality. It surfaces relationships, patterns, anomalies, and leads for human verification.
2. **No Uncorroborated Accusations:** Anomaly scores, network centrality, geospatial co-presence, or OSINT findings are strictly labeled as analytical leads or source claims—never verified facts without ground evidence.
3. **Evidence Integrity:** Every claim, link, and visual artifact must trace back to an `EvidenceID` with cryptographic hash verification (`SHA-256`) and an immutable audit trail.

### 1.4 Product Goals vs. Non-Goals

| Category | In Scope (Goals) | Out of Scope (Non-Goals) |
|---|---|---|
| **Intelligence** | Multi-hop graph analysis, geographic co-occurrence, temporal evolution, cross-case pattern matching. | Automated criminal profiling, predictive policing, automated sentencing/charging recommendations. |
| **AI Assistant** | Natural-language multi-tool GraphRAG agent with citation grounding, contradiction detection, and clarification dialogs. | Autonomous actions, unsupervised external network scanning, unconstrained generative chat without citations. |
| **Evidence & Integrity**| SHA-256 hashing, chain-of-custody tracking, tamper detection, permissioned blockchain metadata anchoring. | Storing raw sensitive evidence payloads on public blockchains; automated legal warrant execution. |
| **Data Scope (MVP)**| Synthetic FIRs, CDRs, financial transactions, vehicle registry, person profiles, document uploads (PDF/Images/OCR), controlled OSINT. | Live feeds into classified national security networks or unverified dark web scraping without warrant clearance. |

---

## 2. Technical Stack & Architectural Rationale

### 2.1 Recommended Technology Stack

```
+----------------------------------------------------------------------------------------------------+
|                                    SPEMASS TECHNOLOGY STACK                                        |
+----------------------------------------------------------------------------------------------------+
| Presentation Layer       | Next.js 14 (App Router) + TypeScript + TailwindCSS + Shadcn UI         |
| Visualizations           | Cytoscape.js (Graph) + MapLibre GL JS (Map) + vis-timeline (Timeline)   |
| API & Orchestration      | Python FastAPI + Pydantic v2 + LangChain / LlamaIndex Core Tooling     |
| Knowledge Graph          | Neo4j 5.x Enterprise / Community (Cypher + GDS Library)                |
| Relational & Vector DB   | PostgreSQL 16 + pgvector (Operational metadata, Cases, Vector Chunks)  |
| Document & File Storage  | MinIO / AWS S3 (S3-compatible object store for raw evidence & docs)    |
| OCR & Document Parsing   | Tesseract OCR + PyMuPDF (fitz) + Unstructured.io                       |
| NLP & Entity Resolution  | spaCy (NER) + Sentence-Transformers + RapidFuzz + Custom Deduplication|
| Caching & Message Queue  | Redis 7.x + Celery / ARQ (Background async ingestion and OCR tasks)    |
| Blockchain Integrity     | Hyperledger Fabric or Local Ethereum/EVM Testbed (Smart Contract Logs) |
| Security & Auth          | JWT (OAuth2 / OIDC) + RBAC + AES-256 Encryption + Cryptography (PyCA)  |
+----------------------------------------------------------------------------------------------------+
```

### 2.2 Technology Selection Rationale

1. **Backend: Python FastAPI**
   - *Rationale:* Native ecosystem compatibility with machine learning libraries, graph algorithms (NetworkX, Neo4j Python Driver), OCR engines, vector math, and LangChain/LlamaIndex frameworks. Provides native asynchronous I/O and auto-generated OpenAPI documentation.
2. **Knowledge Graph: Neo4j**
   - *Rationale:* Native graph storage and traversal engine. Cypher query language allows expressive multi-hop relational queries, shortest path analysis, temporal filtering, and Graph Data Science (GDS) algorithms (PageRank, Louvain Community Detection, Betweenness Centrality) with index-free adjacency performance.
3. **Relational & Vector Store: PostgreSQL 16 with `pgvector`**
   - *Rationale:* Eliminates the complexity of running a separate vector database (e.g., Pinecone/Milvus) for the MVP while providing rock-solid ACID guarantees for structured case records, user tables, audit logs, and chain-of-custody transactions.
4. **Graph Visualization: Cytoscape.js**
   - *Rationale:* Highly performant canvas/WebGL-based link analysis library capable of handling thousands of nodes/edges with customizable compound nodes, force-directed layouts (Cola, CoSE-Bilkent), and programmatic event hooks.
5. **Interactive Mapping: MapLibre GL JS**
   - *Rationale:* Open-source fork of Mapbox GL with zero license fees, hardware-accelerated vector tile rendering, smooth cluster-to-pin zoom transitions, coordinate tracking, and custom layer support for time-stamped trajectory animations.
6. **Frontend: Next.js 14 + React + TypeScript**
   - *Rationale:* Strict typing prevents runtime state bugs across complex synchronized graph-map-timeline views; modular component architecture allows sub-second synchronized state updates using Zustand or React Context.

---

## 3. System Architecture Blueprint

### 3.1 High-Level Component Architecture

```
                                  +---------------------------------------+
                                  |         INVESTIGATOR WORKSPACE        |
                                  | (Next.js 14 SPA + State Orchestrator) |
                                  +-------------------+-------------------+
                                                      |
                                          HTTPS / WSS (JWT Auth)
                                                      |
                                  +-------------------v-------------------+
                                  |         API GATEWAY / FASTAPI         |
                                  |  (RBAC, Rate Limiting, Audit Intercept)|
                                  +-------------------+-------------------+
                                                      |
        +---------------------------------------------+---------------------------------------------+
        |                                             |                                             |
+-------v-------+                             +-------v-------+                             +-------v-------+
|  INGESTION &  |                             |  UNIVERSAL AI |                             |  EVIDENCE &   |
|  EXTRACTION   |                             | INVESTIGATOR  |                             |  BLOCKCHAIN   |
+-------+-------+                             +-------+-------+                             +-------+-------+
        |                                             |                                             |
  * CSV/JSON Loaders                            * Query Planner                               * SHA-256 Engine
  * Tesseract OCR                               * GraphRAG Router                             * Custody Tracker
  * spaCy NER Engine                            * Tool Execution Engine                       * Smart Contract 
  * Entity Resolver                             * Grounded Generator                            Logger (EVM/
  * Geocoding Service                           * Citation Validator                            Hyperledger)
        |                                             |                                             |
        +---------------------------------------------+---------------------------------------------+
                                                      |
                                  +-------------------v-------------------+
                                  |        PERSISTENCE & STORAGE          |
                                  +---------------------------------------+
                                  | 1. Neo4j (Entity/Event/Rel Graph)     |
                                  | 2. PostgreSQL + pgvector (Docs/Embeds)|
                                  | 3. MinIO (Raw Evidence Objects)       |
                                  | 4. Redis (Task Queue & Cache)         |
                                  +---------------------------------------+
```

### 3.2 Data Flow & Ingestion Pipeline
1. **Document / Raw Ingestion:** Authorized investigator uploads PDF, image, CDR CSV, bank transaction Excel, or FIR record.
2. **Cryptographic Sealing:** File is written to MinIO object storage. `SHA-256` hash is calculated immediately and recorded in PostgreSQL `Evidence` table with initial `CustodyEvent`.
3. **Text & Data Extraction:**
   - Structured tabular data (CSV/JSON) is parsed via deterministic schema mappers.
   - Unstructured documents undergo PyMuPDF text extraction and Tesseract OCR preprocessing.
4. **NLP, Entity & Event Extraction:**
   - Extractor identifies Entities (`Person`, `Phone`, `Vehicle`, `Organization`, `Location`, `Account`) and Events (`Call`, `Transaction`, `Meeting`, `Incident`).
   - Geocoding assigns exact `(Latitude, Longitude)` coordinates to extracted locations.
5. **Entity Resolution (Deduplication):**
   - Rule-based matchers (exact phone numbers, vehicle license plates, national IDs).
   - Fuzzy matchers (Levenshtein distance on names/aliases) and semantic vector similarity.
   - Ambiguity threshold: If match confidence $\in [0.70, 0.89]$, flag as `Potential Match - Requires Human Review`; if $\ge 0.90$, merge entity node with provenance links.
6. **Graph & Vector Ingestion:**
   - Entities, Relationships, and Events are committed to Neo4j with full properties (timestamp, confidence, source document ID, case ID).
   - Document text chunks and entity descriptions are embedded via `Sentence-Transformers` and saved into PostgreSQL `pgvector`.

---

## 4. Universal AI Investigator: Architecture & Query Pipeline

The Universal AI Investigator is an open-ended, multi-agent investigative reasoning engine. It operates with strict guardrails: **zero citations = zero claims**.

```
                           +----------------------------------------+
                           |  Investigator Natural-Language Query   |
                           +-------------------+--------------------+
                                               |
                                   +-----------v-----------+
                                   | Question Decomposition|
                                   |  & Intent Extraction  |
                                   +-----------+-----------+
                                               |
                          +--------------------+--------------------+
                          | Check Ambiguity & Authorization Scope   |
                          +--------------------+--------------------+
                                   |                       |
                     [Ambiguous / Multi-Match]      [Clear & Authorized]
                                   |                       |
                     +-------------v------------+          v
                     | Ask Clarification Prompt |  +----------------+
                     +--------------------------+  | Query Planner  |
                                                   +-------+--------+
                                                           |
          +------------------------------------------------+------------------------------------------------+
          |                                                |                                                |
+---------v---------+                            +---------v---------+                            +---------v---------+
| Neo4j Cypher Tool |                            | pgvector Semantic |                            | Spatial/Temporal  |
| (Paths, Comm.,    |                            | Document Search   |                            | Filter Engine     |
| Centrality)       |                            | (FIRs, Transcripts|                            | (Bounding Box,    |
+---------+---------+                            +---------+---------+                            | Date Range)       |
          |                                                |                                      +---------+---------+
          +------------------------------------------------+------------------------------------------------+
                                                           |
                                               +-----------v-----------+
                                               | Evidence Fusion Engine|
                                               | & Conflict Detector   |
                                               +-----------+-----------+
                                                           |
                                               +-----------v-----------+
                                               | Grounded Reasoning    |
                                               | LLM (Strict Schema)   |
                                               +-----------+-----------+
                                                           |
                                               +-----------v-----------+
                                               | Structured Response:  |
                                               | - Direct Answer       |
                                               | - Evidence Citations  |
                                               | - Counter-Evidence    |
                                               | - Evidence Gaps       |
                                               | - Visual Action Hooks |
                                               +-----------------------+
```

### 4.1 Grounded Reasoning & Citation Guardrail
Every assertion in the generated response must link to a specific `[Evidence-ID:Doc-Page-Line]` reference. The generation layer runs a post-processing verification pass:
- If a fact or relationship has no matching retrieved entity/chunk, it is stripped or marked as `[Unverified Investigator Lead]`.
- If two pieces of evidence contradict (e.g., CDR places Phone A at Tower X at 14:00, but witness statement claims Person A was in City Y at 14:00), the engine explicitly highlights the contradiction under `Contradicting Evidence & Discrepancies`.

---

## 5. Knowledge Graph & Data Architecture

### 5.1 Neo4j Graph Schema

```
                                  +-------------------+
                                  |       Case        |
                                  +---------+---------+
                                            ^
                                            | [:INVOLVED_IN]
                                            |
+-------------------+              +--------+----------+             +--------------------+
|   Organization    |<-------------+      Person       +------------>|       Phone        |
+-------------------+ [:WORKS_FOR] +--+------+-------+-+   [:USED]   +---------+----------+
                                      |      |       |                         |
               +----------------------+      |       +-----------------+       |
               | [:ASSOCIATED_WITH]          | [:USED]                 |       |
               v                             v                         |       |
      +--------+---------+          +--------+---------+               |       |
      |      Person      |          |     Vehicle      |               |       |
      +------------------+          +--------+---------+               |       |
                                             |                         |       |
                                             v                         |       |
                                    +--------+---------+               |       |
                                    |      Event       |<--------------+-------+
                                    | (Call, Meeting,  |   [:PARTICIPATED_IN]
                                    |  Transaction)    |
                                    +----+--------+----+
                                         |        |
                         [:OCCURRED_AT]  |        | [:SUPPORTED_BY]
                                         v        v
                        +----------------+--+  +--+-----------------+
                        |     Location      |  |     Evidence       |
                        |  (lat, lon, addr) |  +--+-----------------+
                        +-------------------+     |
                                                  | [:FROM_SOURCE]
                                                  v
                                               +--+-----------------+
                                               |     Document /     |
                                               |    OSINTSource     |
                                               +--------------------+
```

### 5.2 Core Cypher Relationship Types & Properties

```cypher
// 1. Person to Person Association
(:Person {id: "P-101", name: "Vikram Malhotra", aliases: ["Vicky"]})
  -[:ASSOCIATED_WITH {
      relationship_type: "CO_CONSPIRATOR",
      confidence: 0.92,
      case_id: "CASE-2024-001",
      evidence_ids: ["EVID-8821"],
      verified_by_investigator: true
  }]->
(:Person {id: "P-102", name: "Amit Shahani", aliases: ["AS"]})

// 2. Person to Vehicle Usage
(:Person {id: "P-101"})
  -[:USED {
      from_date: "2024-01-10T00:00:00Z",
      to_date: "2024-03-15T00:00:00Z",
      evidence_ids: ["EVID-4412"],
      source: "Traffic Toll Cam & Rental Record"
  }]->
(:Vehicle {id: "VEH-9001", plate_number: "DL-01-AB-1234", make: "Toyota", model: "Innova"})

// 3. Event Spatio-Temporal Grounding
(:Event {
    id: "EVT-501",
    event_type: "SUSPICIOUS_MEETING",
    timestamp: "2024-02-14T19:30:00Z",
    summary: "Meeting prior to financial transfer",
    case_id: "CASE-2024-001"
})
  -[:OCCURRED_AT]->
(:Location {
    id: "LOC-301",
    address: "Hotel Grand Palace, Aerocity, New Delhi",
    latitude: 28.5504,
    longitude: 77.1210
})

// 4. Evidence to Document Provenance
(:Event {id: "EVT-501"})
  -[:SUPPORTED_BY {confidence: 0.95}]->
(:Evidence {
    id: "EVID-8821",
    sha256_hash: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    evidence_type: "CCTV_LOG_TRANSCRIPT",
    integrity_status: "VERIFIED"
})
  -[:FROM_SOURCE]->
(:Document {
    id: "DOC-1002",
    filename: "Aerocity_CCTV_Log_Feb14.pdf",
    storage_uri: "s3://spemass-evidence/CASE-2024-001/Aerocity_CCTV_Log_Feb14.pdf"
})
```

### 5.3 PostgreSQL Relational & Vector Schema

```sql
-- Cases Table
CREATE TABLE cases (
    case_id VARCHAR(64) PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(32) DEFAULT 'ACTIVE',
    classification_level VARCHAR(32) DEFAULT 'RESTRICTED',
    lead_investigator_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Documents & Ingested Files
CREATE TABLE documents (
    document_id VARCHAR(64) PRIMARY KEY,
    case_id VARCHAR(64) REFERENCES cases(case_id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    file_type VARCHAR(64) NOT NULL,
    storage_path TEXT NOT NULL,
    sha256_hash CHAR(64) NOT NULL,
    ocr_extracted_text TEXT,
    parsed_metadata JSONB DEFAULT '{}',
    uploaded_by UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Evidence & Integrity Registry
CREATE TABLE evidence (
    evidence_id VARCHAR(64) PRIMARY KEY,
    case_id VARCHAR(64) REFERENCES cases(case_id) ON DELETE CASCADE,
    document_id VARCHAR(64) REFERENCES documents(document_id),
    title VARCHAR(255) NOT NULL,
    evidence_type VARCHAR(64) NOT NULL,
    sha256_hash CHAR(64) NOT NULL,
    integrity_status VARCHAR(32) DEFAULT 'VERIFIED',
    blockchain_tx_id VARCHAR(128),
    blockchain_block_num BIGINT,
    blockchain_timestamp TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Chain of Custody Events
CREATE TABLE custody_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evidence_id VARCHAR(64) REFERENCES evidence(evidence_id) ON DELETE CASCADE,
    action VARCHAR(64) NOT NULL, -- UPLOAD, VERIFY_HASH, TRANSFER, VIEW, EXPORT
    performed_by UUID NOT NULL,
    ip_address VARCHAR(45) NOT NULL,
    details JSONB DEFAULT '{}',
    sha256_at_event CHAR(64) NOT NULL,
    tamper_detected BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Document Chunks for Semantic Vector Search (pgvector)
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE document_chunks (
    chunk_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id VARCHAR(64) REFERENCES documents(document_id) ON DELETE CASCADE,
    case_id VARCHAR(64) REFERENCES cases(case_id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    chunk_index INT NOT NULL,
    embedding vector(384), -- for all-MiniLM-L6-v2 or 1536 for OpenAI
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX ON document_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

---

## 6. Synchronized Workspace (Graph + Actual Map + Timeline)

### 6.1 State Synchronization Architecture (Zustand / Reactive State)
To avoid jitter and visual desynchronization, the frontend implements a single unified state machine:

```
                          +------------------------------------------+
                          |        Investigator Workspace State      |
                          |  (Selected Entities, Date Filter, Case)  |
                          +--------------------+---------------------+
                                               |
         +-------------------------------------+-------------------------------------+
         |                                     |                                     |
+--------v--------+                   +--------v--------+                   +--------v--------+
|  Cytoscape.js   |                   |  MapLibre GL    |                   |   vis-timeline  |
|  Network View   |                   | Geospatial View |                   | Chronology View |
+--------+--------+                   +--------+--------+                   +--------+--------+
         |                                     |                                     |
         +-------------------------------------+-------------------------------------+
                                               |
                                     (Bi-Directional Action)
```

1. **Graph Node Click:** Filters Map pins to only locations where the selected entity participated in an event; filters Timeline to display chronological trajectory of that entity.
2. **Map Pin Click:** Focuses the graph on the associated event node and its immediate neighbor entities; highlights the precise timeline tick.
3. **Timeline Scrubber Drag / Range Slider:** Updates the graph to hide relationships formed after the selected timestamp (Temporal Network Replay) and animates the map paths.

---

## 7. OSINT & External Intelligence Engine

### 7.1 Controlled Enrichment Workflow
1. **Manual Trigger:** Investigator clicks `Expand with OSINT` on an entity (e.g., Person, Phone, Vehicle, Org).
2. **Lawful Scope Check:** Ensures the search scope adheres to jurisdiction policy and synthetic/public-only parameters.
3. **Connector Execution:** Searches authorized public registries, synthetic demo sources, company records, or news archives.
4. **Extraction & Verification Flagging:**
   - Matches are ingested as `OSINTSource` nodes.
   - If confidence is below $0.90$, property is marked: `status: "Potential Match — Human Verification Required"`.
   - Node is color-coded with dashed borders in the visual workspace until explicitly confirmed by the investigator.

---

## 8. Cryptographic Integrity & Blockchain Layer

### 8.1 Evidence Hash Registration & Verification
1. Every ingested artifact generates a `SHA-256` digest:
   $$\text{Hash} = \text{SHA256}(\text{RawFileBytes})$$
2. The hash, metadata (`case_id`, `uploaded_by`, `timestamp`), and parent document ID are packaged into a state payload.
3. **Blockchain Anchor:** Payload is committed to a permissioned ledger smart contract (`EvidenceLedger.sol` on EVM or Hyperledger chaincode).
4. **Integrity Check Endpoint (`POST /api/v1/evidence/{id}/verify`):**
   - Recalculates file hash on MinIO.
   - Compares with PostgreSQL recorded hash and Blockchain on-chain transaction logs.
   - If a byte has been modified, returns `INTEGRITY_MISMATCH_DETECTED` with diff alert.

> **Legal Disclaimer:** *Blockchain proves that the registered record has not changed since anchoring; it does not prove the underlying contents of the file were truthful when created.*

---

## 9. Implementation Phases, Milestones & Definition of Done

```
Phase 1: Foundation & RBAC
  ├── Repo setup, FastAPI + Next.js scaffolding, PostgreSQL schema, JWT RBAC, Synthetic Case Data
Phase 2: Ingestion & Document Intelligence
  ├── MinIO, SHA-256 engine, PyMuPDF + Tesseract OCR, CSV/JSON loaders
Phase 3: Knowledge Graph & Entity Resolution
  ├── Neo4j schema, Cypher loaders, rapidfuzz/spaCy entity resolution & deduplication
Phase 4: Synchronized Visual Workspace
  ├── Cytoscape graph, MapLibre GL map, vis-timeline, synchronized Zustand state
Phase 5: Graph Analytics & Cross-Case Engine
  ├── Centrality, Louvain communities, shortest paths, cross-case shared entity detector
Phase 6: Evidence & Blockchain Integrity Engine
  ├── Chain of custody logger, local test blockchain anchor contract, tamper verification
Phase 7: OSINT Enrichment Engine
  ├── Public/synthetic OSINT scraper, extraction pipeline, "Human Verification Required" flags
Phase 8: Universal AI Investigator & GraphRAG
  ├── Query planner, multi-tool executor (Cypher + Vector + SQL), citation guardrails
Phase 9: Explainability, Counter-Evidence & Gaps
  ├── Contradiction detector, evidence gap analyzer, visual explanation cards
Phase 10: Hardening, UAT, Testing & Packaging
  ├── End-to-end integration tests, Docker Compose deployment, demo data seeding
```

### 9.1 Milestone Schedule & Definition of Done (DoD)

| Phase | Duration | Core Deliverables | Definition of Done (DoD) |
|---|---|---|---|
| **Phase 1: Foundation** | Sprint 1 | Scaffolding, Auth, PostgreSQL, RBAC, Synthetic Datasets | All tables created; JWT auth functional; Admin/Investigator roles enforced; Synthetic FIR/CDR datasets seeded. |
| **Phase 2: Ingestion** | Sprint 2 | S3/MinIO, OCR Pipeline, SHA-256 Hashing | PDFs/Images uploaded, OCR converts scans to searchable text chunks with pgvector embeddings; Hash verified. |
| **Phase 3: Knowledge Graph** | Sprint 3 | Neo4j Models, Cypher ETL, Entity Resolution | Entities deduplicated; Graph populated; Aliases linked with confidence scores $\ge 0.70$. |
| **Phase 4: Workspace** | Sprint 4 | Cytoscape, MapLibre Map, Chronology Timeline | Graph, map, and timeline render synchronously; click on node filters map and timeline without lag. |
| **Phase 5: Analytics** | Sprint 5 | GDS Graph Algorithms, Cross-Case Detection | Hub/Bridge nodes identified; Louvain clusters colored; Shared entities across cases surfaced. |
| **Phase 6: Blockchain** | Sprint 6 | Custody Logs, Blockchain Smart Contract | Tamper test suite passes; altering 1 byte in storage fails hash verification and alerts investigator. |
| **Phase 7: OSINT** | Sprint 7 | OSINT Connectors, Provenance Tracking | Expand entity with OSINT fetches mock records; unverified leads tagged with warning badge. |
| **Phase 8: Universal AI** | Sprint 8 | GraphRAG Planner, Multi-Tool Agent, Citations | AI answers open queries with exact `[Doc-ID]` citations; asks clarification when ambiguous. |
| **Phase 9: Explainability**| Sprint 9 | Contradiction Matrix, Evidence Gap Cards | Conflicting witness statements and CDR towers flagged; Missing phone records listed in gap panel. |
| **Phase 10: Demo & Hardening**| Sprint 10| Docker Compose, Demo Script, UAT Test Suite | Full multi-case demo runs in 1-click Docker setup; all 10 UAT scenarios pass 100%. |

---

## 10. End-to-End Golden Demo Script

### Scenario: *Operation ShadowNet — Cross-Border Smuggling & Hawala Network*

```
Step 1: Ingestion & Document Intelligence
  - Investigator opens Case "CASE-2024-8812 (Hawala Syndicate)".
  - Uploads raw FIR scan (PDF) and CDR record (CSV).
  - System executes OCR in real-time, extracts entities (Vikram Malhotra, Phone +91-98110-XXXXX, Toyota Fortuner DL-04-E-5544), and hashes the file (SHA-256: 7f8a...9c12).

Step 2: Entity Resolution & Knowledge Graph
  - Graph resolves "Vicky" (from WhatsApp chat) to "Vikram Malhotra" (confidence: 0.94).
  - Graph shows connection to previously closed "CASE-2023-1104".

Step 3: Synchronized Tri-View Workspace
  - Investigator selects "Vikram Malhotra" on Cytoscape Graph.
  - MapLibre Map immediately zooms into 3 hotspot coordinates (Aerocity Hotel, Connaught Place, Mumbai Port).
  - Timeline displays 14 chronological events across Jan 15 - Feb 28.
  - Investigator scrubs timeline to Feb 14: Map shows co-presence event of Vikram and Amit Shahani at Aerocity Hotel at 19:30.

Step 4: Universal AI Investigator Query
  - Investigator asks: "What links Vikram Malhotra to the foreign bank transfer on Feb 15, and is there any contradicting evidence?"
  - AI Planner queries Neo4j + pgvector document chunks.
  - AI Output: 
    * "Vikram Malhotra met Amit Shahani on Feb 14 at 19:30 [Aerocity_CCTV_Log.pdf, p. 3]. Amit transferred $250k on Feb 15 [Bank_Tx_Log.csv, row 442]."
    * Contradiction Flag: "Witness Statement #2 claims Vikram was in Dubai on Feb 14; however, CDR Tower Log places his phone at Aerocity at 19:34 [CDR_98110.csv]."
    * Evidence Gap: "Missing CCTV logs for the bank branch entrance."

Step 5: Evidence Integrity & Chain of Custody
  - Investigator clicks "Verify Integrity" on CCTV evidence.
  - System recalculates SHA-256, matches Blockchain on-chain hash `0x44ab...`, confirms "INTEGRITY VERIFIED".
  - Investigator exports Case Summary Report with full cryptographic audit trail.
```

---

## 11. Risk Register & Mitigations

| Risk ID | Risk Description | Severity | Likelihood | Mitigation Strategy |
|---|---|---|---|---|
| **RSK-01** | LLM Hallucination of Case Evidence | Critical | Medium | Strict schema-enforced output; regex post-validation requires every claim to have a matching active `EvidenceID`; ungrounded claims stripped. |
| **RSK-02** | Entity Resolution False Positive Merge | High | Medium | Merge thresholds require $\ge 0.90$ confidence; $0.70 - 0.89$ flagged as `Potential Match` requiring explicit human investigator approval. |
| **RSK-03** | Visual Latency with Large Graphs (>50k nodes)| Medium | High | Cytoscape compound subgraph clustering; server-side Cypher limiters (k-hop expansion default $k=2$); WebGL rendering. |
| **RSK-04** | Unauthorized Data Exfiltration / Cross-Case Leak| High | Low | Row-level and Cypher-level case tenancy filters; strict RBAC checks injected into all LLM tool calls. |
| **RSK-05** | Document OCR Failure on Degraded Scans | Medium | Medium | Multi-pass image enhancement (binarization, deskewing) with OpenCV prior to Tesseract OCR pass. |

---

## 12. Deployment Architecture (Local, Prototype & Future Production)

### 12.1 Local Prototype Deployment (`docker-compose.yml`)
- `spemass-frontend`: Next.js 14 Web Application (Port 3000)
- `spemass-backend`: FastAPI Python Core (Port 8000)
- `spemass-neo4j`: Neo4j 5.x Graph Engine (Ports 7474, 7687)
- `spemass-postgres`: PostgreSQL 16 with `pgvector` (Port 5432)
- `spemass-minio`: MinIO S3 Object Storage (Ports 9000, 9001)
- `spemass-redis`: Redis 7.x Queue & Cache (Port 6379)
- `spemass-blockchain-mock`: Local Ganache / Hardhat EVM Node (Port 8545)

### 12.2 Production Cloud Architecture Roadmap
- **Compute:** Kubernetes (EKS / GKE) with autoscaling worker pods for Celery/FastAPI.
- **Storage:** AWS S3 with Object Lock (WORM - Write Once Read Many) for legally defensible evidence storage.
- **Ledger:** Permissioned Hyperledger Fabric network across authorized agency nodes.
- **Security:** Hardware Security Module (HSM) for signing chain-of-custody keys; mTLS between microservices.
