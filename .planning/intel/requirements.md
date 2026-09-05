# Requirements

Synthesized from PRD.md (functional requirements FR-*), SPEC.md (MVP-01..MVP-25 and §3–§44), and planning.md (Definitions of Done). Precedence SPEC(0) > PRD(1) > DOC/planning(2).

Where SPEC.md and PRD.md state different acceptance criteria for the same scope, both variants are preserved as separate `-v1` / `-v2` IDs per the competing-variants rule and are logged in `../INGEST-CONFLICTS.md`. Current-build divergence is recorded in `constraints.md`, not here.

---

## REQ-case-management
- source: SPEC.md §34 MVP-01; PRD.md §4.1 FR-CAS-01
- description: Create, update, archive, and assign investigation cases with unique CaseID, title, status, and classification level.
- acceptance: User can create a case; assign lead investigators; enforce case-level access isolation.
- scope: case management

## REQ-tabular-ingestion
- source: SPEC.md §34 MVP-02; PRD.md §4.1 FR-ING-01; planning.md §3.2 step 3
- description: Tabular data ingestion (CSV/JSON) for synthetic CDRs, bank transactions, and vehicle records via deterministic schema mappers.
- acceptance: Ingestion pipeline parses files <= 50MB, maps columns to the canonical entity schema, and logs row errors.
- scope: ingestion, structured data

## REQ-document-ocr-extraction
- source: SPEC.md §34 MVP-03, §25; PRD.md §4.1 FR-ING-02; planning.md §3.2 steps 3-4, Phase 2 DoD
- description: Document upload (PDF, PNG, JPG) with automated OCR and layout text extraction, feeding the pipeline Document → OCR → text extraction → NER → relationship extraction → event/date extraction → entity resolution → knowledge graph → evidence linking.
- acceptance: OCR extracts text from scanned PDFs/images and generates searchable text; PRD adds "generates chunk embeddings in pgvector"; UAT-2 requires >95% text extraction with chunks embedded in a vector index; planning.md Phase 5 risk RSK-05 requires multi-pass image enhancement (binarization, deskewing) before the OCR pass.
- scope: document intelligence, OCR

## REQ-evidence-hash-on-upload
- source: SPEC.md §34 MVP-18, §21; PRD.md §4.1 FR-ING-03, §7.2 FR-EVD-01; planning.md §8.1
- description: Compute a SHA-256 digest of every ingested artifact at upload time and record it with an initial chain-of-custody event.
- acceptance: 64-character hex hash generated; PRD requires the hash be computed before the persistent write to object storage and the custody event stored with timestamp and user ID; hash stored in the relational store and in graph metadata.
- scope: evidence integrity, ingestion

## REQ-entity-resolution
- source: SPEC.md §34 MVP-04, §24; PRD.md §4.2 FR-RES-01; planning.md §3.2 step 5, RSK-02
- description: Deterministic and fuzzy entity resolution for people, phone numbers, vehicle plates, organizations, accounts, and aliases; handles spelling variations, duplicate records, and incomplete information.
- acceptance: Exact matches auto-merged; fuzzy matches scoring 0.70-0.89 flagged `Potential Match - Requires Human Verification`; matches >= 0.90 merged with provenance links; uncertain identities are never silently merged.
- scope: entity resolution

## REQ-entity-merge-ui
- source: PRD.md §4.2 FR-RES-02; SPEC.md §24
- description: Manual entity merge/unmerge UI with full provenance preservation.
- acceptance: Investigator can review suggested merges, approve or reject them, and trace merged entities back to the original documents.
- scope: entity resolution, human-in-the-loop UI

## REQ-knowledge-graph
- source: SPEC.md §34 MVP-05, §7; PRD.md §4.2 FR-KNG-01; planning.md §5.1, §5.2
- description: Temporal investigation knowledge graph modeling PERSON, PHONE, VEHICLE, ORGANIZATION, LOCATION, ACCOUNT, TRANSACTION, CASE, EVENT, DOCUMENT, EVIDENCE, OSINT_SOURCE, HYPOTHESIS, AI_INSIGHT and relationships CALLED, USED, OWNED, ASSOCIATED_WITH, WORKS_FOR, LOCATED_AT, INVOLVED_IN, PARTICIPATED_IN, TRANSFERRED_TO, CONNECTED_TO, SUPPORTED_BY, CONTRADICTED_BY, MENTIONED_IN, DERIVED_FROM.
- acceptance: Graph schema supports temporal, spatial and provenance edge attributes (timestamp, source, confidence, evidence_id, case_id); no analytical relationship is represented as established fact without provenance.
- scope: knowledge graph, data model

## REQ-graph-visualization
- source: SPEC.md §34 MVP-06; PRD.md §4.3 FR-VIS-01; planning.md §2.2 item 4
- description: Interactive network graph supporting zoom, pan, k-hop expansion, and community grouping.
- acceptance: Renders >= 1,000 nodes smoothly; node click triggers global selection state.
- scope: graph UI

## REQ-interactive-map
- source: SPEC.md §34 MVP-07, §11; PRD.md §4.3 FR-VIS-02
- description: A real interactive geographic map (not a decorative mockup) displaying locations, events, movements, incident locations, entity activity, and geographic clusters, with filters for time, case, entity, event, source, and confidence.
- acceptance: Displays pins for all geocoded events; clicking a pin opens an event card with exact time, entities, and evidence links; map selection communicates with graph and timeline.
- scope: map view, geospatial

## REQ-investigation-timeline
- source: SPEC.md §34 MVP-08, §12; PRD.md §4.3 FR-VIS-03
- description: Chronological event timeline supporting exact timestamps, date ranges, event ordering, and event categories (calls, transactions, meetings, locations, evidence events, case events, OSINT events), with a range scrubber / time slider.
- acceptance: Renders events chronologically; dragging the scrubber dynamically filters active graph and map state.
- scope: timeline view, temporal

## REQ-triview-sync
- source: SPEC.md §34 MVP-09, §29; PRD.md §4.3 FR-VIS-04; planning.md §6.1
- description: Bidirectional synchronization across Graph, Map, and Timeline — one selection updates all three views.
- acceptance: Selecting an entity in any one view instantly filters and highlights corresponding elements in the other two views in under 200ms. planning.md §6.1 specifies the three directions: graph node click filters map pins and timeline trajectory; map pin click focuses the graph on the event node and neighbors and highlights the timeline tick; timeline scrubber drag hides relationships formed after the selected timestamp and animates map paths.
- scope: synchronized workspace, tri-view

## REQ-temporal-network-evolution
- source: SPEC.md §34 MVP-11, §12; PRD.md §4.3 FR-VIS-05
- description: Temporal network playback demonstrating how the network evolves over time — the "Investigation Time Machine". When time changes, graph, map, and timeline all change.
- acceptance: Play button iterates time steps, dynamically displaying the addition of nodes, edges, and movement paths; UAT-4 requires dragging the slider across Jan 01 - Feb 28 to hide future links and animate map movement paths.
- scope: temporal analysis, replay

## REQ-investigation-replay
- source: SPEC.md §13, §35 signature feature 3
- description: A demonstration mode called Investigation Replay that reconstructs an investigation chronologically (appearance, communication, vehicle event, transaction, new relationship, OSINT discovery, evidence registration), updating graph, map and timeline together.
- acceptance: The investigator can pause the replay and ask "Why is this event important?" and the Copilot explains using evidence.
- scope: demo mode, replay, Copilot integration

## REQ-graph-analytics
- source: SPEC.md §34 MVP-10, §16; PRD.md §4.4 FR-ANA-01, FR-ANA-02; planning.md Phase 5 DoD
- description: Degree centrality, betweenness centrality, PageRank/eigenvector-style importance, community detection, shortest paths, connected components, bridge-node detection, network density, similarity, and temporal network change analysis.
- acceptance: Highlights top central figures and structural bridges with visual badges; computes shortest paths between any two selected entities with evidence citations for each intermediate relationship; hub/bridge nodes identified and communities colored.
- scope: graph analytics

## REQ-analytics-language-guardrail
- source: SPEC.md §16 ("IMPORTANT"), §28
- description: Analytics output must never label a person "criminal" on the basis of graph centrality.
- acceptance: Uses language such as "High network connectivity" or "Structurally important node" and explains the analytical meaning of the metric.
- scope: responsible AI, analytics presentation

## REQ-cross-case-analysis
- source: SPEC.md §34 MVP-12; PRD.md §4.4 FR-ANA-03; planning.md Phase 5 DoD
- description: Cross-case entity and pattern matching across authorized cases.
- acceptance: Alerts the investigator when an entity (phone, vehicle, person) appears in multiple active or archived cases; shared entities across cases surfaced.
- scope: cross-case analysis

## REQ-anomaly-detection
- source: SPEC.md §34 MVP-13, §17; PRD.md §4.4 FR-ANA-04
- description: Baseline-based anomaly detection for sudden increases in communication, unusual transaction patterns, unusual location patterns, rapid network expansion, new relationships, and cross-case overlaps.
- acceptance: Flags anomalies with clear rule explanations (e.g. "Entity logged in Delhi and Mumbai within 30 minutes"). SPEC additionally requires every anomaly to state observed behavior, baseline, deviation, data sources, evidence, confidence, and alternative explanations, and to phrase findings as "This activity deviates from the established baseline" rather than "This person is suspicious."
- scope: anomaly detection

## REQ-universal-copilot
- source: SPEC.md §34 MVP-14, §2, §3, §8, §27, §35 signature feature 1; PRD.md §5.1
- description: A genuinely open-ended Universal Investigation Copilot. Suggested questions in the UI are suggestions only and must not define system capability. The investigator must be able to type their own natural-language investigation question.
- acceptance: Supports investigator-authored questions beyond the SPEC §3 example list, across capability categories: entity, relationship, path, temporal, spatial, network, communication, transaction, cross-case, OSINT, evidence, contradiction, integrity, hypothesis, comparison, "why", "how", and discovery questions. Per SPEC §44, "Investigators can ask arbitrary reasonable investigation questions rather than selecting from a fixed question set."
- scope: Universal Investigation Copilot

## REQ-dynamic-query-planner
- source: SPEC.md §4, §5, §6; PRD.md §5.1 pipeline step 5; planning.md §4
- description: A Dynamic Investigation Query Planner that converts a natural-language question into an executable multi-step investigation plan generated at runtime, then determines which data sources are required (structured stores, unstructured documents, intelligence/OSINT, evidence metadata).
- acceptance: For an unseen question the system dynamically produces a plan of the shape shown in SPEC §4 (resolve entities → find events → establish time window → find relationships in window → network anomaly analysis → check case → retrieve supporting evidence → retrieve contradictory evidence → verify integrity → generate grounded response). The plan must be generated, not hardcoded for a specific question. Explicitly forbidden: `if question == X then query A` routing or a finite question dictionary.
- scope: Copilot, query planning

## REQ-copilot-pipeline
- source: SPEC.md §5; PRD.md §5.1; planning.md §4
- description: The Copilot pipeline stages: question understanding → intent detection → entity/date/time/location extraction → conversation context resolution → authorization check → dynamic query planning → source determination → retrieval across graph/database/documents/OSINT/evidence → evidence fusion → graph/temporal/spatial analysis → validation → counter-evidence search → reasoning → grounded answer → sources/evidence/confidence/limitations → optional visual actions.
- acceptance: All stages present and traceable; the authorization/RBAC scope check occurs before query planning (PRD §5.1 step 3, planning.md §4).
- scope: Copilot architecture

## REQ-graphrag
- source: SPEC.md §34 MVP-15, §26; PRD.md §5.1; planning.md §4, Phase 8 DoD
- description: GraphRAG retrieval so the LLM never operates independently: question → graph retrieval → vector retrieval → structured database retrieval → document retrieval → timeline retrieval → map/event retrieval → OSINT retrieval → evidence retrieval → evidence fusion → LLM → grounded answer.
- acceptance: The LLM only makes claims supported by retrieved information; insufficient evidence produces "Insufficient authorized evidence to determine the answer."; never fabricates. planning.md Phase 8 DoD: AI answers open queries with exact [Doc-ID] citations and asks clarification when ambiguous.
- scope: GraphRAG, retrieval

## REQ-multi-source-retrieval
- source: SPEC.md §6
- description: The Copilot dynamically determines which of four source classes are required: Structured (relational store, graph, case database, CDR metadata, transaction data, vehicle records, location events); Unstructured (FIRs, police reports, witness statements, investigation reports, PDFs, scanned documents, images, text files); Intelligence (OSINT, public news, public government, public court/legal, public business/corporate, public documents); Evidence (digital evidence metadata, hashes, chain of custody, provenance, integrity status).
- acceptance: The query planner decides which sources are necessary per question rather than always querying all or a fixed subset.
- scope: Copilot, retrieval routing

## REQ-evidence-grounded-answers-v1
- source: SPEC.md §34 MVP-16, §20
- description: Every important Copilot answer follows the SPEC §20 response shape.
- acceptance: Response contains ANSWER, Evidence list, Sources list, Confidence rendered as High/Medium/Low, Contradictions, Limitations, and Suggested next step. Citations are clickable wherever possible and the investigator can navigate from an AI statement back to the underlying evidence.
- scope: Copilot answer format, evidence grounding
- note: competing acceptance variant — see REQ-evidence-grounded-answers-v2.

## REQ-evidence-grounded-answers-v2
- source: PRD.md §5.2 rule 3, §5.3 sample outputs
- description: Every factual statement in a Copilot answer carries an inline citation.
- acceptance: Every factual statement cites `[EvidenceID: SourceDocument, p. X / Row Y]`; unsubstantiated claims are strictly prohibited; confidence is rendered as a numeric score (PRD §5.3 example: "Confidence: High (0.94)"); output includes Direct Answer, Confidence, Limitations, and Visual Action.
- scope: Copilot answer format, evidence grounding
- note: competing acceptance variant with REQ-evidence-grounded-answers-v1 — SPEC specifies a categorical confidence (High/Medium/Low), PRD specifies a numeric confidence score, and the two prescribe different section sets. Not merged. See ../INGEST-CONFLICTS.md.

## REQ-copilot-response-contract
- source: SPEC.md §38
- description: Copilot responses use a structured internal contract.
- acceptance: Internal response object contains `answer`, `confidence`, `sources`, `evidence`, `contradictions`, `limitations`, `entities`, `visual_actions`, `query_plan`, `requires_clarification`. Internal chain-of-thought is not exposed; only concise investigator-appropriate reasoning supported by evidence.
- scope: Copilot API contract

## REQ-conversational-followup
- source: SPEC.md §9, §40 steps 6-7, §44
- description: The Copilot preserves investigation context across conversational turns.
- acceptance: Maintains active case, selected entities, selected graph nodes, selected events, previous results, current hypothesis, temporal context, geographic context, and evidence context. Follow-ups such as "Show me the second one.", "When did it first appear?", "What evidence do we have?", "What contradicts it?" resolve against prior turns.
- scope: Copilot, conversation state

## REQ-copilot-visual-actions
- source: SPEC.md §10, §35 signature feature 1
- description: The Copilot is not a text-only chatbot; questions can drive the investigation interface.
- acceptance: Responses may return structured UI actions such as `{"action":"FOCUS_GRAPH_NODE","entity_id":"..."}`, `{"action":"FILTER_MAP","event_ids":[...]}`, `{"action":"FOCUS_TIMELINE","start":"...","end":"..."}`; actions are implemented safely and validated on the frontend.
- scope: Copilot, UI integration

## REQ-ambiguity-clarification
- source: SPEC.md §27; PRD.md §5.2 rule 1, §5.3 sample 2, UAT-6; planning.md §4
- description: When a question is ambiguous the Copilot requests clarification instead of guessing.
- acceptance: Given a query naming a common first name matching multiple entities, the AI must not guess; it emits a clarification prompt enumerating the candidate entities with distinguishing identifiers (e.g. "There are 2 individuals named Rahul in this case: 1. Rahul Sharma (+91-98711-XXXXX) 2. Rahul Verma (+91-98100-XXXXX)"). SPEC adds the "Did you mean A / B" form and "Do not silently guess."
- scope: Copilot, ambiguity handling

## REQ-evidence-insufficiency-honesty
- source: SPEC.md §34 MVP-23, §27, §26; PRD.md §5.2 rule 2, §5.3 sample 3, UAT-7; planning.md Phase 9
- description: When authorized data cannot answer the question, the Copilot states this explicitly and identifies the evidence gap.
- acceptance: Output states data absence and names the missing data type — SPEC form: "I cannot determine this from the currently available authorized information. Missing information: ... Potentially useful sources: ..."; PRD form: "Based on available authorized records, there is no evidence regarding [topic]. Identified evidence gap: [missing data type]." Evidence gaps are surfaced in a gap panel/checklist.
- scope: Copilot, evidence gap detection

## REQ-contradiction-surfacing
- source: SPEC.md §34 MVP-22, §19; PRD.md §5.2 rule 4, UAT-8; planning.md §4.1, Phase 9 DoD
- description: Counter-evidence engine — for important hypotheses and AI-generated insights, actively search for evidence that could contradict the conclusion.
- acceptance: Displays claim, supporting evidence, contradicting evidence, alternative explanations, and evidence gaps; conflicting witness testimony vs digital records is presented under a dedicated `Contradicting Evidence & Discrepancies` heading; the system avoids confirmation bias.
- scope: counter-evidence, explainability

## REQ-hypothesis-engine
- source: SPEC.md §18
- description: Investigators can create hypotheses (e.g. "Person A may connect Group X and Group Y") and the system evaluates them.
- acceptance: For each hypothesis SPEMASS shows Supporting Evidence (communication relationships, shared locations, transactions, documents), Counter-Evidence (conflicting timestamps, absent expected relationships, contradictory records), Unknowns, and Status from {OPEN, UNDER REVIEW, SUPPORTED, DISPUTED, DISMISSED, RESOLVED}. Guilt is never automatically determined.
- scope: hypothesis engine

## REQ-explainable-ai
- source: SPEC.md §34 MVP-21, §28; PRD.md §1.3; planning.md §1.3, Phase 9
- description: All analytical output is explainable and clearly typed by epistemic status.
- acceptance: Output distinguishes OBSERVED FACT, SOURCE INFORMATION, ANALYTICAL INFERENCE, POTENTIAL RELATIONSHIP, HYPOTHESIS, UNKNOWN; visual explanation cards are provided; no prejudicial terminology ("Guilty", "Criminal mastermind", "Perpetrator") — objective language only ("Associated with", "Present at location", "Recorded in transaction").
- scope: responsible AI, explainability

## REQ-osint-enrichment
- source: SPEC.md §34 MVP-17, §14; PRD.md §6 FR-OSI-01, FR-OSI-02; planning.md §7.1, Phase 7 DoD
- description: Investigator-triggered "Expand with OSINT" enrichment on Person, Phone, Vehicle, or Organization nodes, following the flow Question → Authorization → Public Source Discovery → Collection → Extraction → Verification → Entity Resolution → Evidence Preservation → Knowledge Graph → GraphRAG → Investigator.
- acceptance: Queries authorized public or synthetic registries and extracts corporate, social, or domain links; every OSINT record records source, URL/reference, timestamp, source type, reliability, extracted entity, relationship, evidence ID, hash where applicable, confidence, and case ID; results are ingested as OSINTSource nodes.
- scope: OSINT enrichment

## REQ-osint-verification-badging
- source: SPEC.md §14; PRD.md §6 FR-OSI-03; planning.md §7.1 step 4
- description: Unverified OSINT matches are visually and semantically flagged.
- acceptance: Matches with confidence below 0.90 are rendered with dashed borders and labeled `Potential Match — Human Verification Required`, and remain so until explicitly confirmed by the investigator.
- scope: OSINT, human-in-the-loop

## REQ-osint-source-independence
- source: SPEC.md §15
- description: Source independence analysis — repeated republication of one original report must not be counted as multiple independent sources.
- acceptance: System attempts to identify originating source, duplicated reporting, copied content, and derivative sources, and displays a breakdown of the form "Reported sources: 15 / Likely independent sources: 1 / Derivative sources: 14"; presented as an analytical aid, not an absolute determination.
- scope: OSINT, source reliability

## REQ-tamper-detection
- source: SPEC.md §21; PRD.md §7.2 FR-EVD-02, UAT-9; planning.md §8.1 step 4, Phase 6 DoD
- description: Real-time integrity verification endpoint that detects file modification.
- acceptance: `POST /api/v1/evidence/{id}/verify` recomputes the hash from stored content and compares it against the recorded hash and the ledger record; altering a single byte fails verification and raises an alert. SPEC requires the failure output to show original hash, current hash, and the status "Potential evidence modification detected."; planning.md requires `INTEGRITY_MISMATCH_DETECTED` with a diff alert.
- scope: evidence integrity, tamper detection

## REQ-chain-of-custody
- source: SPEC.md §34 MVP-19, §23; PRD.md §7.2 FR-EVD-03; planning.md §5.3 custody_events schema, Phase 6
- description: Immutable append-only chain-of-custody event logger covering the lifecycle Evidence Created → Registered → Hashed → Custodian Assigned → Transferred → Analyzed → Transferred → Verified.
- acceptance: Records actor, timestamp, action, evidence ID, hash, and authorization context for all UPLOAD, VIEW, ANALYZE, VERIFY_HASH, EXPORT, and TRANSFER actions, with investigator UUID and IP address; the custody row carries `sha256_at_event` and a `tamper_detected` flag.
- scope: chain of custody, audit

## REQ-ledger-integrity-v1
- source: SPEC.md §34 MVP-20, §22, §35 signature feature 5
- description: Permissioned ledger / distributed ledger integrity demonstration anchoring evidence metadata off-chain-first.
- acceptance: Records Evidence ID, hash, timestamp, custody event, authorized actor, and verification metadata to a ledger; sensitive documents are never stored on-chain. "For an MVP, a local demonstrable permissioned-ledger implementation is sufficient." The ledger integrity workflow must be verifiable end to end (SPEC §43 step 16, §44).
- scope: evidence ledger, integrity
- note: competing acceptance variant — see REQ-ledger-integrity-v2.

## REQ-ledger-integrity-v2
- source: PRD.md §7.2 FR-EVD-04; planning.md §2.1, §8.1 step 3, §12.1, Phase 6 DoD
- description: Permissioned blockchain ledger integration via a smart contract.
- acceptance: Evidence metadata (EvidenceID, SHA256, Timestamp, CaseID) is anchored to a smart contract — `EvidenceLedger.sol` on an EVM chain or Hyperledger Fabric chaincode — with a local Ganache/Hardhat EVM node (`spemass-blockchain-mock`, port 8545) in the Docker Compose prototype; verification compares the recomputed hash against on-chain transaction logs.
- scope: evidence ledger, integrity
- note: competing acceptance variant with REQ-ledger-integrity-v1 — SPEC permits any local demonstrable permissioned ledger, PRD/planning mandate a specific smart-contract stack. Not merged. See ../INGEST-CONFLICTS.md.

## REQ-court-dossier-export
- source: PRD.md §7.2 FR-EVD-05, §9 screen 9; planning.md §10 Step 5
- description: Defensible case dossier and court summary export.
- acceptance: Generates a PDF/JSON dossier containing complete graph snapshots, timeline chronology, citations, and blockchain proofs; export builder supports filtering and cryptographic seal generation.
- scope: reporting, court export

## REQ-investigator-dashboard
- source: SPEC.md §34 MVP-24, §29; PRD.md §9 screens 1-9
- description: A polished investigator dashboard plus the primary workspace combining NETWORK GRAPH + ACTUAL MAP + TIMELINE + EVIDENCE + OSINT + AI COPILOT.
- acceptance: Dashboard contains active cases, investigation status, network overview, important entities, recent events, anomalies, AI insights, OSINT findings, evidence conflicts, integrity alerts, and hypothesis status. PRD enumerates nine MVP screens: Login & Auth, Master Case Dashboard, Ingestion & OCR Hub, Synchronized Workspace, Universal AI Investigator, Entity Explorer, Evidence & Custody Vault, Contradiction & Gap Matrix, Case Report & Court Exporter.
- scope: dashboard, screens

## REQ-ui-intelligence-console
- source: SPEC.md §30
- description: The UI must read as a serious intelligence-analysis platform.
- acceptance: Avoids generic admin-dashboard appearance, excessive cards, unnecessary gradients, meaningless animations, fake statistics, decorative graphs, and fake map data. Prioritizes information density, clarity, a dark/light professional intelligence-console aesthetic, fast navigation, explainability, evidence traceability, clear status indicators, and a keyboard-friendly investigation workflow. The Copilot feels embedded in the workspace rather than bolted on.
- scope: UI/UX

## REQ-authentication
- source: SPEC.md §32; PRD.md §10 auth endpoints, §9 screen 1; planning.md Phase 1 DoD
- description: Authentication with JWT/OAuth2 session handling.
- acceptance: `POST /api/v1/auth/login` authenticates and returns a JWT carrying RBAC claims; `GET /api/v1/auth/me` returns the current user profile and case permissions; login screen supports MFA input and session timeout warnings; JWT auth functional with Admin/Investigator roles.
- scope: authentication, security

## REQ-rbac-case-isolation
- source: SPEC.md §32, §39; PRD.md §8 NFR Security & Access, UAT-10; planning.md RSK-04, Phase 1 DoD
- description: Role-Based Access Control and case-level tenancy isolation enforced across API, graph queries, and LLM tool calls.
- acceptance: Roles System Admin, Lead Investigator, Analyst, Viewer; users can only query cases explicitly assigned to them; a cross-case query by an unauthorized user is strictly rejected and raises a security audit log entry; row-level and graph-level case tenancy filters applied, with RBAC checks injected into all LLM tool calls.
- scope: authorization, multi-tenancy, security

## REQ-audit-logging
- source: SPEC.md §34 MVP-25, §32, §37 (`/audit`); PRD.md §8 NFR Integrity & Compliance
- description: Immutable append-only audit logging.
- acceptance: All user queries, downloads, and entity merges are logged append-only; audit logging is verified working as part of the Definition of Done (SPEC §44).
- scope: audit, compliance

## REQ-secure-handling
- source: SPEC.md §32; PRD.md §8 NFR Security & Access, Integrity & Compliance
- description: Prototype-level security hardening.
- acceptance: Secure file handling, encrypted transport (TLS 1.3 in transit, AES-256 at rest for database and object storage), input validation, secrets supplied through environment variables, no hardcoded API keys, no sensitive information in frontend source, no unauthorized OSINT access, automated PII masking/redaction on export views where policy requires, and zero raw sensitive file payloads on public or unauthorized networks.
- scope: security hardening

## REQ-api-surface
- source: SPEC.md §37; PRD.md §10
- description: Clean API surface for the platform.
- acceptance: SPEC §37 lists `/auth`, `/cases`, `/entities`, `/relationships`, `/events`, `/documents`, `/evidence`, `/graph`, `/graph/query`, `/graph/analytics`, `/map/events`, `/timeline`, `/osint`, `/hypotheses`, `/insights`, `/copilot/query`, `/copilot/plan`, `/copilot/actions`, `/integrity`, `/chain-of-custody`, `/audit`, noting "The exact API design may differ based on the existing project." PRD §10 specifies concrete FastAPI routes under `/api/v1/` including `/ai/investigate`, `/cases/{case_id}/graph|map-events|timeline|upload`, `/documents/{doc_id}/ocr`, `/entities/merge`, `/evidence/{id}`, `/evidence/{id}/verify`, `/evidence/{id}/custody`, `/osint/expand`.
- scope: API design

## REQ-synthetic-dataset
- source: SPEC.md §33; PRD.md §12.1; planning.md §10, Phase 1 DoD
- description: A rich synthetic investigation dataset sufficient to demonstrate the entire platform.
- acceptance: Contains multiple people, aliases, phone numbers, vehicles, organizations, locations, cases, communications, transactions, documents, evidence, OSINT records, contradictory records, anomalies, and cross-case relationships; seeded as a complete multi-case criminal conspiracy scenario; entirely fictional.
- scope: synthetic data

## REQ-test-suite
- source: SPEC.md §39
- description: Automated tests across all major subsystems.
- acceptance: Copilot tests (open-ended, multi-hop, ambiguous, follow-up, missing information, conflicting evidence, cross-case); Graph tests (entity relationships, path finding, temporal filtering, analytics); Map tests (event/time/entity filtering); Evidence tests (hashing, tamper detection, provenance); OSINT tests (source recording, uncertain entity matching, source independence); Security tests (unauthorized case access, unauthorized evidence access, invalid input, API authentication).
- scope: testing

## REQ-uat-suite
- source: PRD.md §11, §12.1
- description: Ten mandatory UAT scenarios that must pass at a 100% rate prior to MVP sign-off.
- acceptance: (1) Synthetic case ingestion and entity extraction; (2) Document OCR and text chunks with >95% extraction and vector indexing; (3) Graph-Map-Timeline sync on node selection; (4) Temporal network scrubber; (5) Grounded AI query with exact citations and no hallucinations; (6) Ambiguous AI query clarification without silent guessing; (7) Evidence insufficiency and gap highlighting; (8) Contradiction surfacing between witness and CDR; (9) Cryptographic tamper detection after a one-byte alteration; (10) RBAC and case isolation enforcement with security audit log.
- scope: acceptance testing

## REQ-copilot-acceptance-scenario
- source: SPEC.md §40, §44
- description: The single most important acceptance scenario for the platform.
- acceptance: With Case 17 open, an investigator types a non-predefined question ("Find unusual relationships that appeared after Person A met Person B and tell me whether any evidence connects them to this case."). SPEMASS dynamically resolves A and B, finds meeting events, establishes a time window, searches the graph, analyzes network changes, retrieves case information, documents and evidence, checks OSINT if authorized, searches for contradictory evidence, and validates evidence integrity. It returns answer, evidence, sources, confidence, contradictions, limitations, and offers visual actions (graph, timeline, locations, evidence). Follow-ups "Show me the second relationship.", "What contradicts this?", "Search authorized public sources for additional information.", and "Has any of this evidence been modified?" all resolve correctly. "This complete flow must work in the final prototype."
- scope: acceptance criteria, Copilot

## REQ-demo-scenario
- source: SPEC.md §41; planning.md §10
- description: A coherent end-to-end demonstration optimized for a 5-minute SIH presentation.
- acceptance: Flow runs OPEN CASE → UPLOAD/LOAD SYNTHETIC DATA → AI EXTRACTS INFORMATION → KNOWLEDGE GRAPH APPEARS → MAP + TIMELINE APPEAR → INVESTIGATOR ASKS THEIR OWN QUESTION → COPILOT ANALYZES MULTIPLE SOURCES → GRAPH/MAP/TIMELINE UPDATE → EVIDENCE APPEARS → COUNTER-EVIDENCE APPEARS → OSINT ENRICHMENT → EVIDENCE HASH VERIFICATION → INVESTIGATION REPLAY. planning.md §10 scripts this as "Operation ShadowNet — Cross-Border Smuggling & Hawala Network" over CASE-2024-8812 in five steps. The demo must feel like one coherent investigation rather than a collection of disconnected features.
- scope: demo, delivery

## REQ-deployment-packaging
- source: SPEC.md §31 (Deployment row); PRD.md §12.1; planning.md §12.1, Phase 10 DoD
- description: Containerized local prototype deployment.
- acceptance: Complete Docker Compose orchestration providing 1-click local startup. planning.md §12.1 enumerates services `spemass-frontend` (3000), `spemass-backend` (8000), `spemass-neo4j` (7474/7687), `spemass-postgres` (5432), `spemass-minio` (9000/9001), `spemass-redis` (6379), `spemass-blockchain-mock` (8545).
- scope: deployment, packaging

## REQ-runtime-verification
- source: SPEC.md §43, §44
- description: The project must be demonstrably running and verified end to end, not merely documented.
- acceptance: SPEC §43 requires implementing the MVP, running the project, testing every major workflow, fixing compilation/runtime errors, and verifying frontend-backend integration, database connectivity, graph queries, map rendering, timeline, Copilot, open-ended questions, follow-up questions, evidence citations, OSINT, hashing, ledger integrity workflow, and security, then seeding synthetic demo data and performing an end-to-end investigation — with final UI polish performed only after all of that. SPEC §44 enumerates the full Definition of Done checklist.
- scope: delivery verification, definition of done
