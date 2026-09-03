# Product Requirements Document (PRD)
## Secure Pattern & Evidence Mapping and Analysis of Suspicious Structures (SPEMASS)

**Document Version:** 1.0.0  
**Document Status:** Approved for Engineering Implementation  
**Product Category:** AI-Powered Investigative Intelligence & Evidence Decision-Support System  
**Target Delivery:** Full MVP Prototype & Production Blueprint  

---

## 1. Executive Summary

### 1.1 Product Purpose
**SPEMASS** is an investigator decision-support platform that transforms unstructured, fragmented, and multi-source case data into actionable, explainable relationship, spatial, temporal, and cross-case intelligence. By unifying a **Temporal Knowledge Graph (Neo4j)**, an **Actual Interactive Map (MapLibre GL / Leaflet)**, an **Event Chronology Timeline**, and an **Evidence Integrity Engine (SHA-256 + Blockchain)** under an open-ended **Universal AI Investigator (GraphRAG)**, SPEMASS empowers authorized investigators to uncover hidden networks, validate investigative leads, and uphold evidentiary integrity without human bias or AI hallucination.

### 1.2 Core Value Proposition
> **SPEMASS does not merely find connections. It explains the connection, shows where and when it occurred, traces it to evidence, identifies contradictions and evidence gaps, and preserves evidence integrity.**

### 1.3 Strict Legal, Ethical & Decision-Support Principles
- **No Automated Accusation:** SPEMASS is strictly a decision-support tool. It shall never present anomaly scores, network centrality, proximity, OSINT mentions, or AI inferences as proof of criminality, guilt, intent, or legal liability.
- **Evidence-Grounded Intelligence:** Every analytical claim must be grounded in an authorized document or verified evidence artifact with a cryptographic hash (`SHA-256`).
- **Human in the Loop:** All high-impact decisions (entity merges, OSINT integration, subpoena generation, formal case indexing) require explicit human investigator authorization.

---

## 2. Target Personas & User Journeys

### 2.1 Target Personas

```
+----------------------------------------------------------------------------------------------------+
|                                         PRIMARY USER PERSONAS                                      |
+------------------------------------+---------------------------------------------------------------+
| Persona & Role                     | Core Responsibilities & Needs                                 |
+------------------------------------+---------------------------------------------------------------+
| 1. Senior Field Investigator       | • Investigates complex financial crimes, organized rings,     |
|    (e.g., Inspector / Detective)   |   and multi-jurisdiction conspiracies.                        |
|                                    | • Needs rapid link analysis, co-presence tracking on maps,    |
|                                    |   and timeline reconstruction without manual Excel merging.   |
+------------------------------------+---------------------------------------------------------------+
| 2. Intelligence Analyst            | • Performs cross-case correlation, link discovery, and        |
|    (e.g., Forensic Data Analyst)   |   deep anomaly analysis across CDRs and bank transactions.    |
|                                    | • Needs advanced graph queries, centrality metrics, and       |
|                                    |   OSINT enrichment with verification flags.                   |
+------------------------------------+---------------------------------------------------------------+
| 3. Evidence Custodian & Prosecutor | • Oversees evidentiary compliance, forensic chain of custody, |
|    (e.g., Forensic Lead / Legal)   |   and court-admissible documentation.                         |
|                                    | • Requires cryptographic audit trails, SHA-256 integrity       |
|                                    |   verification, and contradiction/gap reports.                |
+------------------------------------+---------------------------------------------------------------+
| 4. System Administrator / Lead     | • Manages user access, case permissions, audit logs, and      |
|    (e.g., Security & IT Admin)     |   security compliance across agency divisions.                |
+------------------------------------+---------------------------------------------------------------+
```

### 2.2 Core User Journeys

#### Journey 1: Multi-Source Case Ingestion & Tri-View Analysis
1. Investigator creates a new Case (`CASE-2024-001`) and uploads a scanned First Information Report (FIR PDF) and Call Detail Records (CDR CSV).
2. SPEMASS automatically computes SHA-256 hashes, logs initial custody events, runs OCR, extracts entities (`Vikram Malhotra`, `+91-98110-XXXXX`), and resolves aliases.
3. Investigator enters the **Synchronized Workspace**: selecting `Vikram Malhotra` highlights his node in the **Network Graph**, displays his CDR cell-tower locations on the **Actual Map**, and places his calls on the **Timeline**.

#### Journey 2: Universal AI Investigator Deep Query with Contradiction Surfacing
1. Investigator asks the AI: *"Where was Vikram Malhotra on the evening of February 14th, and what evidence connects him to the vehicle DL-04-E-5544?"*
2. AI plans a multi-source query across Neo4j and pgvector document chunks.
3. AI returns a grounded answer citing FIR line 42, CCTV log p. 3, and CDR Tower records, while explicitly flagging a contradiction: *Witness Statement B claims he was out of town, but CDR places his phone within 200m of the hotel at 19:34.*
4. AI provides interactive links that highlight the relevant map coordinates and timeline ticks.

#### Journey 3: Cryptographic Integrity Verification & Court Export
1. Legal analyst selects an evidence item (CCTV log) and triggers **Verify Integrity**.
2. System re-hashes the object from storage, compares it against the initial record and blockchain ledger, and outputs an audit certificate confirming zero tampering.

---

## 3. Product Scope & Classification Matrix

Requirements across this document are strictly categorized:
- **[MVP]**: Mandatory for the initial working platform and prototype evaluation.
- **[MVP-Lite]**: Streamlined/demo implementation suitable for prototype demonstration.
- **[Post-MVP]**: Planned for future enterprise and national-scale deployment.

```
+----------------------------------------------------------------------------------------------------+
|                                    SPEMASS CAPABILITY SCOPE MATRIX                                 |
+----------------------+---------------------------------+-------------------------------------------+
| Tier                 | Capabilities Included           | Target Deliverables                       |
+----------------------+---------------------------------+-------------------------------------------+
| [MVP]                | MVP-01 through MVP-25           | Fully functional web app, Neo4j, MapLibre,|
|                      |                                 | Timeline, Universal AI, SHA-256, Mock BC  |
+----------------------+---------------------------------+-------------------------------------------+
| [MVP-Lite]           | Advanced NLP / Entity Matching  | Heuristic & RapidFuzz matching, mock      |
|                      | Controlled OSINT Scraper        | synthetic OSINT registry endpoints        |
+----------------------+---------------------------------+-------------------------------------------+
| [Post-MVP]           | Live National Police Feeds,     | Production distributed cluster, HSM keys, |
|                      | Facial/Voice Biometrics         | automated multi-agency federation         |
+----------------------+---------------------------------+-------------------------------------------+
```

---

## 4. Functional Requirements

### 4.1 Case Management & Data Ingestion

| Req ID | Capability Description | Scope | Acceptance Criteria |
|---|---|---|---|
| **FR-CAS-01** | Create, update, archive, and assign cases with unique `CaseID`, title, status, and classification. | **[MVP]** | User can create a case; assign lead investigators; enforce case-level access isolation. |
| **FR-ING-01** | Tabular data ingestion (CSV/JSON) for synthetic CDRs, bank transactions, and vehicle records. | **[MVP]** | Ingestion pipeline parses files $\le 50\text{MB}$, maps columns to canonical entity schema, logs row errors. |
| **FR-ING-02** | Document upload (PDF, PNG, JPG) with automated OCR and layout text extraction. | **[MVP]** | Tesseract OCR extracts text from scanned PDFs/images; generates searchable text and chunk embeddings in `pgvector`. |
| **FR-ING-03** | Immediate SHA-256 hash generation upon upload and initial custody event recording. | **[MVP]** | Hash computed before persistent write to MinIO; custody event stored in PostgreSQL with timestamp and user ID. |

### 4.2 Entity Resolution & Knowledge Graph

| Req ID | Capability Description | Scope | Acceptance Criteria |
|---|---|---|---|
| **FR-KNG-01** | Neo4j property graph modeling for `Person`, `Phone`, `Vehicle`, `Organization`, `Location`, `Account`, `Event`, and `Evidence`. | **[MVP]** | Graph schema supports temporal, spatial, and provenance edge attributes (`timestamp`, `confidence`, `evidence_ids`). |
| **FR-RES-01** | Deterministic and fuzzy entity resolution for names, phone numbers, vehicle plates, and aliases. | **[MVP]** | Exact matches auto-merged; fuzzy matches (score $0.70-0.89$) flagged as `Potential Match - Requires Human Verification`. |
| **FR-RES-02** | Manual entity merge/unmerge UI with full provenance preservation. | **[MVP]** | Investigator can review suggested merges, approve or reject them, and trace merged entities back to original documents. |

### 4.3 Synchronized Workspace (Graph + Actual Map + Timeline)

| Req ID | Capability Description | Scope | Acceptance Criteria |
|---|---|---|---|
| **FR-VIS-01** | Interactive Network Graph (Cytoscape.js) supporting zoom, pan, k-hop expansion, and community grouping. | **[MVP]** | Renders $\ge 1,000$ nodes smoothly; node click triggers global selection state. |
| **FR-VIS-02** | Actual Interactive Geographic Map (MapLibre GL / Leaflet) with event coordinates, clusters, and paths. | **[MVP]** | Displays pins for all geocoded events; clicking pin opens event card with exact time, entities, and evidence links. |
| **FR-VIS-03** | Chronological Event Timeline (vis-timeline) with range scrubber and event categorization. | **[MVP]** | Renders events chronologically; drag scrubber filters active graph and map state dynamically. |
| **FR-VIS-04** | Tri-view bidirectional synchronization across Graph, Map, and Timeline. | **[MVP]** | Selecting an entity in any one view instantly filters and highlights the corresponding elements in the other two views ($<200\text{ms}$). |
| **FR-VIS-05** | Temporal network playback/replay demonstrating network evolution over time. | **[MVP]** | Play button iterates time steps, dynamically displaying the addition of nodes, edges, and movement paths. |

### 4.4 Graph Analytics & Cross-Case Analysis

| Req ID | Capability Description | Scope | Acceptance Criteria |
|---|---|---|---|
| **FR-ANA-01** | Network centrality, bridge node identification, and Louvain community detection. | **[MVP]** | Executes Neo4j GDS algorithms; highlights top central figures and structural bridges with visual badges. |
| **FR-ANA-02** | Shortest path discovery between any two selected entities. | **[MVP]** | Computes all shortest paths with evidence citations for each intermediate relationship. |
| **FR-ANA-03** | Cross-Case entity and pattern matching across authorized cases. | **[MVP]** | Alerts investigator when an entity (phone, vehicle, person) appears in multiple active/archived cases. |
| **FR-ANA-04** | Transparent anomaly detection (unusual transaction spikes, burst communication patterns, impossible travel). | **[MVP]** | Flags anomalies with clear rule explanations (e.g., *Entity logged in Delhi and Mumbai within 30 minutes*). |

---

## 5. Universal AI Investigator (Mandatory Top-Level Requirement)

### 5.1 System Directive & Scope
> **SPEMASS must answer any reasonable investigation-related question using all data sources, tools, and information it is authorized and able to access.**

The Universal AI Investigator is not a rigid chatbot or static FAQ parser; it is an open-ended natural-language reasoning agent operating over structured graph queries (Cypher), vector search (`pgvector`), relational SQL queries, spatial filters, and evidence metadata.

```
+----------------------------------------------------------------------------------------------------+
|                                UNIVERSAL AI INVESTIGATOR PIPELINE                                  |
+----------------------------------------------------------------------------------------------------+
| 1. Natural-Language Question Input                                                                 |
| 2. Intent, Entity, Time & Location Parsing                                                         |
| 3. Authorization & Case-Scope Check (RBAC Filter)                                                  |
| 4. Ambiguity Evaluation (Ask clarification if multiple entities match)                             |
| 5. Multi-Tool Query Planning (Neo4j Cypher + SQL + pgvector + Spatial Filter)                      |
| 6. Evidence Retrieval & Cross-Validation                                                           |
| 7. Grounded Reasoning with Strict Citation Enforcement                                             |
| 8. Counter-Evidence & Evidence-Gap Detection                                                       |
| 9. Formatted Response Generation with Citations, Confidence, Limitations & Visual Highlight Triggers|
+----------------------------------------------------------------------------------------------------+
```

### 5.2 Mandatory Behavioral Guardrails & Rules

1. **Clarification on Ambiguity:** If a question refers to "Amit" and two people named "Amit Kumar" and "Amit Shahani" exist in the case, the AI **must not guess**. It must output a concise clarification prompt: *"Multiple entities named Amit found. Did you mean Amit Kumar (+91-98...) or Amit Shahani (DL-01...)?"*
2. **Evidence-Insufficiency Honesty:** If no data exists in the authorized scope to answer the question, the AI must explicitly state: *"Based on available authorized records, there is no evidence regarding [topic]. Identified evidence gap: [missing data type]."*
3. **Strict Citation Enforcement:** Every factual statement must cite `[EvidenceID: SourceDocument, p. X / Row Y]`. Unsubstantiated claims are strictly prohibited.
4. **Contradiction Surfacing:** If witness testimony conflicts with digital records (e.g., CDR or toll logs), the AI must present both sides under a dedicated `Contradicting Evidence & Discrepancies` heading.
5. **No Legal Accusations:** Responses must use objective investigative language (e.g., *"Associated with," "Present at location," "Recorded in transaction"*) rather than prejudicial terms (*"Guilty," "Criminal mastermind," "Perpetrator"*).

### 5.3 Representative Questions & Acceptance Scenarios

```
+----------------------------------------------------------------------------------------------------+
| Sample Investigator Question 1 (Cross-Source Path Analysis):                                       |
| "What connects Vikram Malhotra to the $250,000 transaction on Feb 15th?"                           |
|                                                                                                    |
| Required AI Output Format:                                                                         |
| • Direct Answer: Vikram Malhotra met Amit Shahani on Feb 14 at 19:30 [EVID-8821: CCTV_Log.pdf].   |
|   Amit Shahani authorized the $250,000 transfer from Account #9921 to Swiss Entity on Feb 15 at    |
|   09:15 [EVID-4402: Bank_Tx_Log.csv].                                                              |
| • Confidence: High (0.94)                                                                          |
| • Limitations: No direct financial record shows Vikram as the named account holder.                |
| • Visual Action: Highlights Node(Vikram) -> Node(Amit) -> Node(Account) on Graph; zooms Map.       |
+----------------------------------------------------------------------------------------------------+
| Sample Investigator Question 2 (Ambiguity Handling):                                               |
| "Show me all calls made by Rahul last week."                                                       |
|                                                                                                    |
| Required AI Output Format:                                                                         |
| • Clarification Prompt: "There are 2 individuals named Rahul in this case:                         |
|   1. Rahul Sharma (Phone: +91-98711-XXXXX)                                                         |
|   2. Rahul Verma (Phone: +91-98100-XXXXX)                                                          |
|   Please specify which person you would like to analyze."                                          |
+----------------------------------------------------------------------------------------------------+
| Sample Investigator Question 3 (Counter-Evidence & Evidence Gaps):                                 |
| "Did Vikram Malhotra leave Delhi between Feb 10 and Feb 20?"                                       |
|                                                                                                    |
| Required AI Output Format:                                                                         |
| • Supporting Evidence: Flight manifest shows a booking on Feb 12 for Delhi->Dubai [EVID-1092].     |
| • Contradicting Evidence: CDR logs record Phone +91-98110 connected to Aerocity Delhi tower on     |
|   Feb 14 at 19:34 [EVID-3301], indicating physical presence in Delhi or SIM handover.             |
| • Evidence Gap: Immigration biometric exit records for Feb 12 are missing from case files.        |
+----------------------------------------------------------------------------------------------------+
```

---

## 6. Controlled OSINT Enrichment Requirements

| Req ID | Capability Description | Scope | Acceptance Criteria |
|---|---|---|---|
| **FR-OSI-01** | User-initiated "Expand with OSINT" action on Person, Phone, Vehicle, or Organization nodes. | **[MVP]** | Queries authorized public or synthetic registries; extracts relevant corporate, social, or domain links. |
| **FR-OSI-02** | Explicit provenance and verification labeling on all OSINT findings. | **[MVP]** | Every OSINT record contains `SourceURL`, `RetrievalTimestamp`, `ReliabilityScore`, and `EvidenceID`. |
| **FR-OSI-03** | Mandatory warning badge for unverified matches. | **[MVP]** | Matches with confidence $<0.90$ are rendered with dashed borders and labeled: `Potential Match — Human Verification Required`. |

---

## 7. Evidence Provenance, Custody & Blockchain Integrity

### 7.1 Evidence Lifecycle & Traceability
Every system insight must be fully traceable through the following hierarchy:

$$\text{Insight} \longrightarrow \text{Analytical Explanation} \longrightarrow \text{Supporting Evidence} \longrightarrow \text{Source Document} \longrightarrow \text{SHA-256 Hash} \longrightarrow \text{Chain of Custody Event} \longrightarrow \text{Blockchain Proof}$$

### 7.2 Requirements Table

| Req ID | Capability Description | Scope | Acceptance Criteria |
|---|---|---|---|
| **FR-EVD-01** | Cryptographic SHA-256 evidence hashing upon document/record ingestion. | **[MVP]** | Generates 64-character hex hash; stores in PostgreSQL and graph metadata. |
| **FR-EVD-02** | Tamper detection and real-time integrity verification endpoint. | **[MVP]** | `POST /api/v1/evidence/{id}/verify` re-computes storage hash; flags mismatch immediately if file is altered. |
| **FR-EVD-03** | Immutable Chain-of-Custody event logger. | **[MVP]** | Records all `UPLOAD`, `VIEW`, `ANALYZE`, `EXPORT`, and `TRANSFER` actions with investigator UUID, timestamp, and IP. |
| **FR-EVD-04** | Permissioned / Local Testbed Blockchain ledger integration for metadata and hash anchoring. | **[MVP]** | Anchors evidence metadata (`EvidenceID`, `SHA256`, `Timestamp`, `CaseID`) to smart contract without storing sensitive raw files on-chain. |
| **FR-EVD-05** | Defensible Case Dossier & Court Summary Export. | **[MVP]** | Generates PDF/JSON dossier with complete graph snapshots, timeline chronology, citations, and blockchain proofs. |

---

## 8. Non-Functional Requirements (NFRs)

```
+----------------------------------------------------------------------------------------------------+
|                                      NON-FUNCTIONAL REQUIREMENTS                                   |
+-------------+--------------------------------------------------------------------------------------+
| Category    | Specific Technical Requirement & SLA                                                 |
+-------------+--------------------------------------------------------------------------------------+
| Performance | • Graph query response (2-hop traversal over 50,000 nodes) $\le 350\text{ms}$.        |
|             | • Tri-view synchronization lag across Graph, Map, and Timeline $\le 200\text{ms}$.    |
|             | • Universal AI Investigator initial streamed token response $\le 2.0\text{s}$.       |
+-------------+--------------------------------------------------------------------------------------+
| Security &  | • Role-Based Access Control (RBAC): System Admin, Lead Investigator, Analyst, Viewer.|
| Access      | • Case-level isolation: Users can only query cases explicitly assigned to them.      |
|             | • End-to-end encryption: TLS 1.3 in transit; AES-256 at rest (Database & MinIO).    |
+-------------+--------------------------------------------------------------------------------------+
| Integrity & | • Immutable append-only audit logging for all user queries, downloads, and merges.  |
| Compliance  | • Automated PII masking/redaction on export views where required by policy.          |
|             | • Zero raw sensitive file payloads placed on public or unauthorized networks.       |
+-------------+--------------------------------------------------------------------------------------+
| Reliability | • High availability architecture with containerized auto-restart.                    |
|             | • Data durability with point-in-time recovery for PostgreSQL and Neo4j backups.      |
+-------------+--------------------------------------------------------------------------------------+
```

---

## 9. User Interface & Screen Specifications

```
+----------------------------------------------------------------------------------------------------+
|                                      MVP SCREEN SPECIFICATION                                      |
+-----+-------------------------------+--------------------------------------------------------------+
| No. | Screen Name                   | Key UI Components & Capabilities                             |
+-----+-------------------------------+--------------------------------------------------------------+
| 1   | Login & Auth                  | Secure login, MFA input, session timeout warnings.           |
| 2   | Master Case Dashboard         | Case list, active alerts, recent uploads, cross-case badges. |
| 3   | Ingestion & OCR Hub           | Drag-and-drop file upload, real-time OCR progress, hash logs.|
| 4   | Synchronized Workspace        | Tri-view layout: Cytoscape Graph + MapLibre Map + Timeline.  |
| 5   | Universal AI Investigator     | Grounded chat panel, citation pills, visual highlight action.|
| 6   | Entity Explorer               | Detailed node profile, aliases, association cards, OSINT tab.|
| 7   | Evidence & Custody Vault      | Evidence file viewer, SHA-256 validator, blockchain receipts.|
| 8   | Contradiction & Gap Matrix    | Discrepancy comparison cards, missing data checklist.        |
| 9   | Case Report & Court Exporter  | Filterable export builder with cryptographic seal generation.|
+-----+-------------------------------+--------------------------------------------------------------+
```

---

## 10. API Specification & Integration Endpoints

```
+----------------------------------------------------------------------------------------------------+
|                                     CORE API ENDPOINTS (FASTAPI)                                   |
+----------------------------------------------------------------------------------------------------+
| Authentication & Access Control:                                                                   |
|   POST   /api/v1/auth/login                  -> Authenticates user; returns JWT with RBAC claims.  |
|   GET    /api/v1/auth/me                     -> Returns current user profile and case permissions. |
|                                                                                                    |
| Case Management:                                                                                   |
|   GET    /api/v1/cases                       -> List assigned cases for authenticated user.        |
|   POST   /api/v1/cases                       -> Create a new investigation case.                    |
|   GET    /api/v1/cases/{case_id}             -> Fetch case metadata, stats, and assigned team.     |
|                                                                                                    |
| Ingestion, Documents & OCR:                                                                        |
|   POST   /api/v1/cases/{case_id}/upload      -> Multipart upload of PDF/CSV/Images. Computes hash. |
|   GET    /api/v1/documents/{doc_id}/ocr      -> Fetch extracted text chunks, status, and metadata. |
|                                                                                                    |
| Knowledge Graph & Visual Workspace:                                                                |
|   GET    /api/v1/cases/{case_id}/graph       -> Returns Cytoscape JSON (nodes, edges, properties). |
|   GET    /api/v1/cases/{case_id}/map-events  -> Returns GeoJSON feature collection for map pins.   |
|   GET    /api/v1/cases/{case_id}/timeline    -> Returns chronological event series with entities.  |
|   POST   /api/v1/entities/merge              -> Merges 2 entities with provenance tracking.        |
|                                                                                                    |
| Universal AI Investigator (GraphRAG):                                                              |
|   POST   /api/v1/ai/investigate              -> Main NLP query endpoint. Returns grounded answer,  |
|                                                 citations, contradictions, gaps, and UI actions.   |
|                                                                                                    |
| Evidence Integrity & Blockchain:                                                                   |
|   GET    /api/v1/evidence/{evidence_id}      -> Fetch evidence details, source document & history. |
|   POST   /api/v1/evidence/{evidence_id}/verify-> Recalculates hash; checks against blockchain.      |
|   GET    /api/v1/evidence/{evidence_id}/custody-> Returns immutable chain-of-custody audit log.    |
|                                                                                                    |
| OSINT Engine:                                                                                      |
|   POST   /api/v1/osint/expand                -> Initiates controlled OSINT lookup for an entity.   |
+----------------------------------------------------------------------------------------------------+
```

---

## 11. User Acceptance Testing (UAT) Test Plan

The following 10 UAT scenarios must pass with a 100% success rate prior to MVP sign-off:

```
+----------------------------------------------------------------------------------------------------+
|                                    10 MANDATORY UAT TEST SCENARIOS                                 |
+----+-----------------------------+------------------------------------+----------------------------+
| #  | Test Scenario               | Execution Steps                    | Expected Outcome           |
+----+-----------------------------+------------------------------------+----------------------------+
| 1  | Synthetic Case Ingestion    | Import synthetic FIR, CDR, and     | All entities/events parsed |
|    | & Entity Extraction         | Bank CSV data into a new case.     | and visible in Neo4j.      |
+----+-----------------------------+------------------------------------+----------------------------+
| 2  | Document OCR & Text Chunks  | Upload scanned FIR PDF. Verify OCR | OCR extracts $>95\%$ text; |
|    |                             | execution and vector indexing.     | chunks embedded in vector. |
+----+-----------------------------+------------------------------------+----------------------------+
| 3  | Graph-Map-Timeline Sync     | Select node "Vikram Malhotra" in   | Map zooms to Delhi/Mumbai; |
|    |                             | Graph view.                        | Timeline filters to calls. |
+----+-----------------------------+------------------------------------+----------------------------+
| 4  | Temporal Network Scrubber   | Drag timeline slider across dates  | Graph hides future links;  |
|    |                             | Jan 01 - Feb 28.                   | Map animates movement path.|
+----+-----------------------------+------------------------------------+----------------------------+
| 5  | Grounded AI Investigator    | Ask multi-hop investigation        | AI returns exact citations |
|    | Query with Citations        | question regarding money transfer. | without hallucinations.    |
+----+-----------------------------+------------------------------------+----------------------------+
| 6  | Ambiguous AI Query          | Ask query mentioning common name   | AI prompts clarification;  |
|    | Clarification Dialog        | "Rahul" without phone/ID.          | does not silently guess.   |
+----+-----------------------------+------------------------------------+----------------------------+
| 7  | Evidence Insufficiency      | Ask question on unrecorded topic   | AI states data absence and |
|    | & Evidence Gaps             | (e.g., offshore yacht registry).   | highlights evidence gap.   |
+----+-----------------------------+------------------------------------+----------------------------+
| 8  | Contradiction Surfacing     | Query Vikram's location on Feb 14  | AI highlights witness vs.  |
|    |                             | (conflicting witness vs. CDR).     | CDR tower contradiction.   |
+----+-----------------------------+------------------------------------+----------------------------+
| 9  | Cryptographic Tamper        | Alter 1 byte of stored PDF in      | System detects hash        |
|    | Detection Verification      | MinIO; trigger `/verify`.          | mismatch; raises alert.    |
+----+-----------------------------+------------------------------------+----------------------------+
| 10 | RBAC & Case Isolation       | Attempt cross-case query as user   | Query strictly rejected;   |
|    | Enforcement                 | without assigned permission.       | security audit log raised. |
+----+-----------------------------+------------------------------------+----------------------------+
```

---

## 12. Release & Acceptance Criteria

### 12.1 MVP Release Gate Checklist
- [x] All 25 MVP capabilities (MVP-01 to MVP-25) fully implemented and operational.
- [x] 100% pass rate on all 10 UAT scenarios.
- [x] Universal AI Investigator citation validation passes all test suites (zero ungrounded claims).
- [x] Zero critical or high-severity security vulnerabilities in dependencies.
- [x] Sub-200ms latency on Tri-View workspace synchronization.
- [x] Complete Docker Compose orchestration for local 1-click startup.
- [x] Synthetic dataset seeded with complete multi-case criminal conspiracy scenario.
