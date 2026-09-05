# SPEMASS — Master Implementation Specification

**Document Status:** Authoritative scope definition (supersedes PRD.md and planning.md where they conflict)
**Project:** SPEMASS — Secure Pattern & Evidence Mapping and Analysis of Suspicious Structures
**Context:** SIH project prototype

**Tagline:**

> Connect Evidence. Reveal Networks. Empower Investigators.

SPEMASS is an AI-powered investigation intelligence platform designed to help authorized investigators analyze fragmented investigative information across documents, people, communications, transactions, vehicles, organizations, locations, timelines, OSINT and digital evidence.

The goal is not a generic CRUD application or a chatbot with a dashboard. Build a technically credible, visually impressive, functional investigative intelligence platform that demonstrates a realistic end-to-end workflow.

---

## 1. First Rule — Inspect Before Implementing

Before writing or modifying code:

1. Inspect the entire existing repository.
2. Identify: frontend framework, backend framework, database, existing components, existing APIs, existing authentication, existing AI integration, existing graph implementation, existing map implementation, existing timeline, existing data models, existing files and folder structure.
3. Do NOT unnecessarily rewrite working components.
4. Reuse existing architecture where practical.
5. Identify incomplete, mocked, placeholder or broken functionality.
6. Create a technical implementation plan before making major changes.
7. Preserve existing working features unless they conflict with the requirements below.

If something is already implemented, improve/integrate it instead of duplicating it.

---

## 2. Core Product Principle

> **Investigators ask questions. SPEMASS determines how to answer them.**

The Investigation Copilot must NOT be restricted to a fixed question set. There may be suggested/example questions in the UI, but those are only suggestions. They must NOT define the capabilities of the system. An investigator must be able to type their own natural-language investigation question.

---

## 3. Universal Investigation Copilot — Critical MVP

Implement a genuinely open-ended Investigation Copilot. The investigator should be able to type questions such as:

- "Who is connected to Person A?"
- "How are Person A and Person B connected?"
- "Where was Person A during the evening of August 15?"
- "What changed in this network during the last 30 days?"
- "Which people appear across multiple cases?"
- "Find unusual communication patterns."
- "Why was Person B flagged?"
- "What evidence supports this relationship?"
- "What evidence contradicts this hypothesis?"
- "Find all relationships between these two groups."
- "Which locations have the highest concentration of related events?"
- "Find information about this person from authorized public sources."
- "Compare Case 101 with Case 117."
- "What information are we missing?"
- "Show me everything connecting Person A to Organization X."
- "Find unusual relationships created after Person A met Person B."
- "Summarize everything known about this investigation."
- "I don't know what I'm looking for. Find the most unusual changes in this case."

These are examples only. The system must support investigator-created questions beyond these examples.

---

## 4. Do NOT Implement a Fixed Question Router

DO NOT build logic such as:

```text
if question == "Who is connected?"
    execute query A

if question == "Where was X?"
    execute query B
```

Do NOT create a finite question dictionary and pretend that is the AI.

Instead implement a **Dynamic Investigation Query Planner**. The system should convert natural-language questions into an executable investigation plan.

Example — investigator asks:

> "What unusual relationships appeared after Person A met Person B, and is there evidence connecting those relationships to Case 17?"

SPEMASS should dynamically determine something similar to:

```text
1. Resolve Person A
2. Resolve Person B
3. Find meeting events
4. Establish relevant time window
5. Find relationships created after the event
6. Perform network anomaly analysis
7. Check Case 17
8. Retrieve supporting evidence
9. Retrieve contradictory evidence
10. Verify evidence integrity
11. Generate grounded response
```

The exact plan must be generated dynamically rather than hardcoded for this question.

---

## 5. Copilot Pipeline

```text
Natural Language Question
        ↓
Question Understanding
        ↓
Intent Detection
        ↓
Entity / Date / Time / Location Extraction
        ↓
Conversation Context Resolution
        ↓
Authorization Check
        ↓
Dynamic Query Planning
        ↓
Determine Required Data Sources
        ↓
┌────────┬────────┬────────┬────────┬────────┐
│ Graph  │Database│Documents│ OSINT │Evidence│
└────────┴────────┴────────┴────────┴────────┘
        ↓
Evidence Retrieval
        ↓
Evidence Fusion
        ↓
Graph / Temporal / Spatial Analysis
        ↓
Validation
        ↓
Counter-Evidence Search
        ↓
Reasoning
        ↓
Grounded Answer
        ↓
Sources + Evidence + Confidence + Limitations
        ↓
Optional Visual Actions
(Graph / Map / Timeline / Evidence)
```

---

## 6. Multi-Source Retrieval

The Copilot must dynamically determine which sources are required.

**Structured:** PostgreSQL, Neo4j, case database, CDR metadata, transaction data, vehicle records, location events.

**Unstructured:** FIRs, police reports, witness statements, investigation reports, PDFs, scanned documents, images, text files.

**Intelligence:** OSINT, public news, public government information, public court/legal information, public business/corporate information, public documents.

**Evidence:** digital evidence metadata, evidence hashes, chain of custody, provenance, integrity status.

The query planner should decide which sources are necessary.

---

## 7. Graph Querying

Use the investigation knowledge graph as a first-class source.

Potential entities:

```text
PERSON, PHONE, VEHICLE, ORGANIZATION, LOCATION, ACCOUNT, TRANSACTION,
CASE, EVENT, DOCUMENT, EVIDENCE, OSINT_SOURCE, HYPOTHESIS, AI_INSIGHT
```

Potential relationships:

```text
CALLED, USED, OWNED, ASSOCIATED_WITH, WORKS_FOR, LOCATED_AT, INVOLVED_IN,
PARTICIPATED_IN, TRANSFERRED_TO, CONNECTED_TO, SUPPORTED_BY,
CONTRADICTED_BY, MENTIONED_IN, DERIVED_FROM
```

Relationships must support metadata such as: `timestamp`, `source`, `confidence`, `evidence_id`, `case_id`.

Do not represent an analytical relationship as established fact without provenance.

---

## 8. Open-Ended Question Types

The Copilot should dynamically support: entity questions, relationship questions, path questions, temporal questions, spatial questions, network questions, communication questions, transaction questions, cross-case questions, OSINT questions, evidence questions, contradiction questions, integrity questions, hypothesis questions, comparison questions, "why" questions, "how" questions, and discovery questions ("What should I investigate next?").

These are capability categories, not fixed questions.

---

## 9. Conversational Follow-Up

The Copilot must preserve investigation context across turns. Example:

> Investigator: "Find unusual relationships in Case 17."
> Copilot: "Three potentially unusual relationship clusters were identified."
> Investigator: "Show me the second one."
> Investigator: "When did it first appear?"
> Investigator: "What evidence do we have?"
> Investigator: "What contradicts it?"
> Investigator: "Search authorized public sources for additional context."

The Copilot should maintain: active case, selected entities, selected graph nodes, selected events, previous results, current hypothesis, temporal context, geographic context, evidence context.

---

## 10. Visual Actions From Questions

The Copilot is NOT just a text chatbot. Questions should be able to control the investigation interface.

- "Show me Person A's connections." → Graph focuses on Person A.
- "Show me where those events happened." → Map filters to those events.
- "When did these connections appear?" → Timeline focuses on relevant period.
- "Show only evidence related to this relationship." → Evidence panel filters.
- "Show the suspicious cluster." → Graph highlights the cluster.

The response should optionally return structured UI actions such as:

```json
{ "action": "FOCUS_GRAPH_NODE", "entity_id": "person_123" }
```

```json
{ "action": "FILTER_MAP", "event_ids": ["event_1", "event_2"] }
```

```json
{ "action": "FOCUS_TIMELINE", "start": "...", "end": "..." }
```

Implement these actions safely and validate them on the frontend.

---

## 11. Actual Map — Must Have

The map must be a real interactive map, not a decorative mockup. Use MapLibre GL JS or Leaflet.

Display authorized/synthetic: locations, events, movements where available, incident locations, entity activity, geographic clusters.

Support filters: time, case, entity, event, source, confidence.

Map selection must communicate with the graph and timeline.

---

## 12. Temporal Investigation Engine

Implement a real timeline supporting: exact timestamps, date ranges, event ordering, calls, transactions, meetings, locations, evidence events, case events, OSINT events.

Add a time slider where practical. When time changes: graph changes, map changes, timeline changes.

This creates the **Investigation Time Machine** — the investigator can move through the case chronologically and see the network evolve.

---

## 13. Investigation Replay

Implement a demonstration mode called **Investigation Replay**. The system should reconstruct an investigation chronologically:

```text
08:10 — Person A appears at Location 1
08:25 — Communication event
08:41 — Vehicle event
09:05 — Person B appears
09:17 — Transaction
09:42 — New relationship
10:15 — OSINT information discovered
10:30 — Evidence registered
```

The graph, map and timeline should update together where technically feasible. The investigator can pause and ask "Why is this event important?" and the Copilot should explain using evidence.

---

## 14. OSINT Module

OSINT is part of SPEMASS, not a separate application. When internal information is insufficient and the investigator is authorized to perform public-source enrichment:

```text
Question → Authorization → Public Source Discovery → Collection → Extraction
→ Verification → Entity Resolution → Evidence Preservation → Knowledge Graph
→ GraphRAG → Investigator
```

Only legally accessible public information should be considered.

Do NOT implement: credential bypass, private-account access, unauthorized system access, restricted database access, surveillance of private individuals outside authorization.

Every OSINT result should record: source, URL/reference, timestamp, source type, reliability, extracted entity, relationship, evidence ID, hash where applicable, confidence, case ID.

Uncertain identity matches must be labeled: *Potential external match — human verification required.*

---

## 15. Source Independence

Implement source independence analysis. If 15 websites repeat the same original report, do not treat them as 15 independent sources.

SPEMASS should attempt to identify: originating source, duplicated reporting, copied content, derivative sources.

Display something like:

```text
Reported sources: 15
Likely independent sources: 1
Derivative sources: 14
```

This is an analytical aid, not an absolute determination.

---

## 16. Graph Analytics

Implement: degree centrality, betweenness centrality, PageRank/eigenvector-style importance, community detection, shortest paths, connected components, bridge-node detection, network density, similarity, temporal network changes.

**IMPORTANT:** Never label a person "criminal" because of graph centrality. Use language such as "High network connectivity" or "Structurally important node" and explain the analytical meaning.

---

## 17. Anomaly Detection

Implement baseline-based anomaly detection for: sudden increase in communications, unusual transaction patterns, unusual location patterns, rapid network expansion, new relationships, cross-case overlaps.

Every anomaly must explain: observed behavior, baseline, deviation, data sources, evidence, confidence, alternative explanations.

Never say "This person is suspicious because the AI says so." Instead: "This activity deviates from the established baseline."

---

## 18. Hypothesis Engine

Allow investigators to create hypotheses, e.g. *"Person A may connect Group X and Group Y."*

SPEMASS should show:

- **Supporting Evidence** — communication relationships, shared locations, transactions, documents
- **Counter-Evidence** — conflicting timestamps, lack of expected relationships, contradictory records
- **Unknowns** — unidentified phone owner, missing transaction information
- **Status** — `OPEN`, `UNDER REVIEW`, `SUPPORTED`, `DISPUTED`, `DISMISSED`, `RESOLVED`

Do not automatically determine guilt.

---

## 19. Counter-Evidence Engine

A critical responsible-AI feature. For important hypotheses or AI-generated insights, actively search for evidence that could contradict the conclusion.

Display: claim, supporting evidence, contradicting evidence, alternative explanations, evidence gaps.

The system must avoid confirmation bias.

---

## 20. Evidence-Grounded Answers

Every important Copilot answer should follow:

```text
ANSWER

Evidence:
- Evidence item 1
- Evidence item 2

Sources:
- Source 1
- Source 2

Confidence: High / Medium / Low

Contradictions: ...

Limitations: ...

Suggested next step: ...
```

Citations should be clickable whenever possible. The investigator must be able to navigate from an AI statement back to the underlying evidence.

---

## 21. Evidence Integrity

Implement evidence hashing:

```text
Evidence → SHA-256 Hash → Evidence ID → Timestamp → Custodian → Chain of Custody
```

The system should detect file modification. If the file changes:

```text
⚠ INTEGRITY FAILURE

Original hash: ABC...
Current hash:  XYZ...

Status: Potential evidence modification detected.
```

---

## 22. Permissioned Blockchain / Distributed Ledger

Use blockchain only where it provides value. Do NOT store sensitive documents directly on-chain — store them off-chain.

Record integrity/provenance metadata such as: Evidence ID, hash, timestamp, custody event, authorized actor, verification metadata.

Possible technology: Hyperledger Fabric, Hyperledger Besu, or another appropriate permissioned ledger. For an MVP, a local demonstrable permissioned-ledger implementation is sufficient.

**IMPORTANT:** Blockchain proves that the recorded digital object/hash history has not changed according to the ledger. It does NOT prove that the underlying evidence is truthful.

---

## 23. Chain of Custody

Support:

```text
Evidence Created → Registered → Hashed → Custodian Assigned → Transferred
→ Analyzed → Transferred → Verified
```

Record: actor, timestamp, action, evidence ID, hash, authorization context.

---

## 24. Entity Resolution

Implement entity resolution for people, phone numbers, vehicles, organizations, accounts.

Handle: aliases, spelling variations, duplicate records, incomplete information.

Never silently merge uncertain identities. Use confidence and human verification.

---

## 25. Document Intelligence

Support PDF, images, scanned documents, text.

```text
Document → OCR → Text extraction → NER → Relationship extraction
→ Event/date extraction → Entity resolution → Knowledge graph → Evidence linking
```

Use practical open-source tools where appropriate: PaddleOCR/Tesseract, spaCy, Transformers, LLM.

---

## 26. GraphRAG

Implement GraphRAG so that the LLM does not operate independently.

```text
Question → Graph retrieval → Vector retrieval → Structured database retrieval
→ Document retrieval → Timeline retrieval → Map/event retrieval → OSINT retrieval
→ Evidence retrieval → Evidence fusion → LLM → Grounded answer
```

The LLM must only make claims supported by retrieved information. If evidence is insufficient: *"Insufficient authorized evidence to determine the answer."* Never fabricate.

---

## 27. "Answer Anything Reasonable" Requirement

A formal product requirement. The Copilot must support:

> **Any reasonable investigation-related question that falls within SPEMASS's authorized scope and available information.**

This does NOT mean the system must answer every question with a definitive answer.

If information is missing:

```text
I cannot determine this from the currently available authorized information.

Missing information: ...
Potentially useful sources: ...
```

If the question is ambiguous:

```text
I need clarification before proceeding.

Did you mean:
A...
B...
```

Do not silently guess.

---

## 28. Responsible AI

SPEMASS must NOT: determine guilt, determine innocence, recommend arrest solely from AI output, recommend punishment, infer criminal intent from association, infer guilt from co-location, infer guilt from graph centrality, treat OSINT mentions as proof, treat anomaly scores as proof, present speculation as fact.

Distinguish clearly between:

```text
OBSERVED FACT
SOURCE INFORMATION
ANALYTICAL INFERENCE
POTENTIAL RELATIONSHIP
HYPOTHESIS
UNKNOWN
```

Human investigators remain the final decision-makers.

---

## 29. Investigator Dashboard

Create a polished dashboard containing: active cases, investigation status, network overview, important entities, recent events, anomalies, AI insights, OSINT findings, evidence conflicts, integrity alerts, hypothesis status.

The primary workspace should combine:

```text
NETWORK GRAPH + ACTUAL MAP + TIMELINE + EVIDENCE + OSINT + AI COPILOT
```

---

## 30. UI/UX Requirement

The UI should look like a serious intelligence-analysis platform.

**Avoid:** generic admin-dashboard appearance, excessive cards, unnecessary gradients, meaningless animations, fake statistics, decorative graphs, fake map data.

**Prioritize:** information density, clarity, dark/light professional intelligence-console aesthetic, fast navigation, explainability, evidence traceability, clear status indicators, keyboard-friendly investigation workflow.

The Copilot should feel embedded into the investigation workspace.

---

## 31. Recommended Tech Stack

Use the existing stack if already established. Otherwise prefer:

| Layer | Technology |
|---|---|
| Frontend | React / Next.js, TypeScript, Tailwind CSS |
| Graph | Neo4j, Cytoscape.js |
| Map | MapLibre GL JS or Leaflet |
| Backend | Python, FastAPI |
| Relational DB | PostgreSQL |
| Vector search | pgvector or Qdrant |
| Object storage | MinIO / S3-compatible |
| OCR | PaddleOCR or Tesseract |
| NLP | spaCy, Transformers |
| AI | appropriate LLM provider/model, structured tool/function calling where available |
| Ledger | Hyperledger Fabric/Besu or an appropriate permissioned ledger |
| Deployment | Docker, Docker Compose for prototype |

Do not introduce technologies without a concrete reason.

---

## 32. Security

Implement appropriate prototype-level security: authentication, RBAC, authorization checks, case-level access control where practical, secure file handling, encrypted transport, audit logs, input validation, secrets through environment variables, no hardcoded API keys, no sensitive information in frontend source, no unauthorized OSINT access.

---

## 33. Synthetic Data

For the SIH prototype, use entirely fictional/synthetic investigation data.

Create a realistic synthetic investigation containing: multiple people, aliases, phone numbers, vehicles, organizations, locations, cases, communications, transactions, documents, evidence, OSINT records, contradictory records, anomalies, cross-case relationships.

The dataset should be rich enough to demonstrate the entire platform. Do not use real sensitive personal information.

---

## 34. MVP Priority

Must-have MVP capabilities:

| ID | Capability |
|---|---|
| MVP-01 | Case management |
| MVP-02 | Synthetic data ingestion |
| MVP-03 | Document OCR and entity extraction |
| MVP-04 | Entity resolution |
| MVP-05 | Knowledge graph |
| MVP-06 | Interactive graph visualization |
| MVP-07 | Actual interactive map |
| MVP-08 | Investigation timeline |
| MVP-09 | Graph + Map + Timeline synchronization |
| MVP-10 | Graph analytics |
| MVP-11 | Temporal network evolution |
| MVP-12 | Cross-case analysis |
| MVP-13 | Anomaly detection |
| MVP-14 | **Universal Open-Ended Investigation Copilot** |
| MVP-15 | GraphRAG |
| MVP-16 | Evidence-grounded responses |
| MVP-17 | Controlled OSINT enrichment |
| MVP-18 | Evidence hashing |
| MVP-19 | Chain of custody |
| MVP-20 | Blockchain/ledger integrity demonstration |
| MVP-21 | Explainable AI |
| MVP-22 | Counter-evidence |
| MVP-23 | Evidence-gap detection |
| MVP-24 | Investigator dashboard |
| MVP-25 | Security and audit logging |

---

## 35. Signature Features

Prioritize these heavily because they are intended to impress SIH judges:

1. **Universal Investigation Copilot** — Investigator can ask their OWN questions. No fixed question set.
2. **Graph + Map + Timeline Intelligence** — One selection updates all three.
3. **Investigation Replay** — Watch the investigation evolve over time.
4. **Evidence + Counter-Evidence** — The AI actively challenges its own analytical hypothesis.
5. **Evidence Integrity** — Hash → provenance → custody → ledger verification → tamper detection.
6. **OSINT Enrichment** — Internal evidence + authorized public information.

---

## 36. Post-MVP

Do not spend excessive development time on these before the MVP works:

- real CCTNS/ICJS integration
- live nationwide data
- real-time streaming CDR
- production-scale deployment
- advanced facial recognition
- advanced speaker recognition
- predictive policing
- autonomous enforcement decisions
- large-scale distributed deployment

Build clean interfaces so these can be integrated later.

---

## 37. API Design

Design clean APIs for:

```text
/auth
/cases
/entities
/relationships
/events
/documents
/evidence
/graph
/graph/query
/graph/analytics
/map/events
/timeline
/osint
/hypotheses
/insights
/copilot/query
/copilot/plan
/copilot/actions
/integrity
/chain-of-custody
/audit
```

The exact API design may differ based on the existing project.

---

## 38. Copilot Response Contract

Use structured responses internally:

```json
{
  "answer": "...",
  "confidence": "medium",
  "sources": [],
  "evidence": [],
  "contradictions": [],
  "limitations": [],
  "entities": [],
  "visual_actions": [],
  "query_plan": [],
  "requires_clarification": false
}
```

Do not expose internal chain-of-thought. Expose only concise reasoning/explanations appropriate for investigators, supported by evidence.

---

## 39. Testing

Create tests for:

- **Copilot** — open-ended questions, multi-hop questions, ambiguous questions, follow-up questions, missing information, conflicting evidence, cross-case queries
- **Graph** — entity relationships, path finding, temporal filtering, analytics
- **Map** — event filtering, time filtering, entity filtering
- **Evidence** — hashing, tamper detection, provenance
- **OSINT** — source recording, uncertain entity matching, source independence
- **Security** — unauthorized case access, unauthorized evidence access, invalid input, API authentication

---

## 40. Acceptance Test for the Most Important Feature

The system should pass this scenario:

1. Investigator opens Case 17.
2. They type a question that was NOT predefined: *"Find unusual relationships that appeared after Person A met Person B and tell me whether any evidence connects them to this case."*
3. SPEMASS dynamically: resolves A and B, finds relevant meeting events, establishes a time window, searches the graph, analyzes network changes, retrieves case information, retrieves documents, retrieves evidence, checks OSINT if authorized/necessary, searches for contradictory evidence, validates evidence integrity.
4. It returns: answer, evidence, sources, confidence, contradictions, limitations.
5. It offers visual actions: view relationship graph, view timeline, view locations, view evidence.
6. Investigator asks *"Show me the second relationship."* — the system understands the conversational context.
7. Investigator asks *"What contradicts this?"* — the system retrieves counter-evidence.
8. Investigator asks *"Search authorized public sources for additional information."* — the OSINT module executes.
9. Investigator asks *"Has any of this evidence been modified?"* — SPEMASS checks integrity hashes/ledger records.

This complete flow must work in the final prototype.

---

## 41. Demo Experience

The final implementation must be optimized for a 5-minute SIH demonstration:

```text
OPEN CASE → UPLOAD/LOAD SYNTHETIC DATA → AI EXTRACTS INFORMATION
→ KNOWLEDGE GRAPH APPEARS → MAP + TIMELINE APPEAR
→ INVESTIGATOR ASKS THEIR OWN QUESTION → COPILOT ANALYZES MULTIPLE SOURCES
→ GRAPH UPDATES → MAP UPDATES → TIMELINE UPDATES
→ EVIDENCE APPEARS → COUNTER-EVIDENCE APPEARS → OSINT ENRICHMENT
→ EVIDENCE HASH VERIFICATION → INVESTIGATION REPLAY
```

The demo should feel like one coherent investigation rather than a collection of disconnected features.

---

## 42. Implementation Priority

| Phase | Scope |
|---|---|
| Phase 0 | Repository inspection + architecture plan |
| Phase 1 | Data model + synthetic dataset |
| Phase 2 | Backend APIs |
| Phase 3 | Knowledge graph |
| Phase 4 | Graph UI |
| Phase 5 | Actual map |
| Phase 6 | Timeline |
| Phase 7 | Graph-map-timeline synchronization |
| Phase 8 | Document/OCR pipeline |
| Phase 9 | Entity resolution |
| Phase 10 | Universal Copilot + dynamic query planner |
| Phase 11 | GraphRAG |
| Phase 12 | Evidence engine |
| Phase 13 | OSINT |
| Phase 14 | Anomaly + hypothesis + counter-evidence |
| Phase 15 | Hashing + chain of custody + ledger |
| Phase 16 | Security + audit |
| Phase 17 | UX polish + demo scenario |
| Phase 18 | Testing + bug fixing |

Do not polish the UI while core functionality is still broken.

---

## 43. Important Development Behavior

Do not simply create documentation and stop. After creating the planning and PRD:

1. Implement the MVP.
2. Run the project.
3. Test every major workflow.
4. Fix compilation/runtime errors.
5. Verify frontend-backend integration.
6. Verify database connectivity.
7. Verify graph queries.
8. Verify map rendering.
9. Verify timeline.
10. Verify Copilot.
11. Verify open-ended questions.
12. Verify follow-up questions.
13. Verify evidence citations.
14. Verify OSINT.
15. Verify hashing.
16. Verify ledger integrity workflow.
17. Verify security.
18. Populate synthetic demo data.
19. Perform an end-to-end investigation.
20. Only then perform final UI polish.

If an external API/key is unavailable, implement a clean mock/local provider so the entire demo can still run locally.

**Never hardcode fake AI answers merely to make the UI appear functional.**

---

## 44. Definition of Done

The implementation is complete only when:

- The project starts successfully.
- The frontend is functional.
- The backend is functional.
- Synthetic data can be loaded.
- Documents can be processed.
- Entities can be extracted.
- Entities can be resolved.
- Knowledge graph works.
- Network graph works.
- Actual map works.
- Timeline works.
- Graph/map/timeline synchronize.
- Graph analytics work.
- Cross-case analysis works.
- Anomaly detection works.
- OSINT workflow works or has a functional local demonstration provider.
- Evidence is linked to claims.
- Counter-evidence works.
- Hypotheses work.
- Evidence hashes work.
- Chain of custody works.
- Ledger integrity demo works.
- GraphRAG works.
- **Investigators can ask arbitrary reasonable investigation questions rather than selecting from a fixed question set.**
- Follow-up questions retain context.
- Ambiguous questions request clarification.
- Missing information produces an honest insufficient-evidence response.
- Answers contain evidence/source references.
- No unsupported criminality conclusions are generated.
- Audit logging works.
- The complete SIH demo scenario works from start to finish.

---

## 45. Final Product Philosophy

> **AI Discovers.
> Graph Connects.
> Maps Reveal Space.
> Timelines Reveal Sequence.
> OSINT Enriches.
> Evidence Explains.
> Counter-Evidence Challenges.
> Blockchain Preserves Integrity.
> Investigators Decide.**

The most important capability is:

> **An investigator should be able to ask SPEMASS any reasonable question about an investigation in their own words, and SPEMASS should dynamically determine how to retrieve, correlate, analyze and explain the answer using all authorized available information.**

Do not turn the Copilot into a predefined-question chatbot. Build it as an **actionable AI investigation interface over the entire SPEMASS intelligence platform.**
