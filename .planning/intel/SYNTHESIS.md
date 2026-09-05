# Synthesis Summary

Entry point for downstream consumers (`gsd-roadmapper`). Produced by `gsd-doc-synthesizer`. MODE=new.

**Project:** SPEMASS — Secure Pattern & Evidence Mapping and Analysis of Suspicious Structures. AI-powered investigative intelligence decision-support platform, built as an SIH (Smart India Hackathon) prototype.

---

## Documents ingested (3)

- **SPEC.md** — SPEC, precedence 0, confidence high, manifest override, locked false. "SPEMASS — Master Implementation Specification." Self-declares supersession over PRD.md and planning.md where they conflict. 45 sections, 873 lines. Cross-refs: PRD.md, planning.md.
- **PRD.md** — PRD, precedence 1, confidence high, manifest override, locked false. "Product Requirements Document (PRD) — SPEMASS." 12 sections, 381 lines. 24 numbered functional requirements (FR-CAS/ING/KNG/RES/VIS/ANA/OSI/EVD), four NFR categories, nine UI screens, an API table, and 10 UAT scenarios. No cross-refs.
- **planning.md** — DOC, precedence 2, confidence high, manifest override, locked false. "SPEMASS: Engineering Plan, Architecture Blueprint & Delivery Roadmap." 12 sections, 548 lines. Stack table, architecture diagrams, Neo4j schema, PostgreSQL DDL, GraphRAG pipeline, 10-phase roadmap with DoDs, risk register, deployment topology. No cross-refs. Classified DOC by manifest override despite SPEC-shaped content.

Precedence applied: **SPEC > PRD > DOC**. Cross-reference graph acyclic (max depth 2, cap 50). No UNKNOWN or low-confidence classifications.

## Decisions — 15 extracted, 0 locked

No ADR-classified documents were ingested, so **no decision in this ingest is LOCKED**. All 15 entries in `decisions.md` carry `status: proposed` and are open to revision.

Highest-leverage decisions for roadmapping:
- `DEC-existing-stack-first` (SPEC.md §31) — "Use the existing stack if already established", the clause that governs the entire docs-vs-code divergence.
- `DEC-no-fixed-question-router` (SPEC.md §4, §43) — forbids the exact pattern the current Copilot implements.
- `DEC-mvp-ledger-scope` (SPEC.md §22) — a local demonstrable permissioned ledger is sufficient for MVP.
- `DEC-decision-support-only` (SPEC.md §28) — the responsible-AI boundary all three documents agree on.
- `DEC-function-before-polish` (SPEC.md §42, §43) — no UI polish while core functionality is broken.

## Requirements — 54 extracted

Full list in `requirements.md`, IDs `REQ-*`. Grouped:

- **Case & ingestion (4):** `REQ-case-management`, `REQ-tabular-ingestion`, `REQ-document-ocr-extraction`, `REQ-evidence-hash-on-upload`
- **Entity & graph (3):** `REQ-entity-resolution`, `REQ-entity-merge-ui`, `REQ-knowledge-graph`
- **Workspace views (6):** `REQ-graph-visualization`, `REQ-interactive-map`, `REQ-investigation-timeline`, `REQ-triview-sync`, `REQ-temporal-network-evolution`, `REQ-investigation-replay`
- **Analytics (4):** `REQ-graph-analytics`, `REQ-analytics-language-guardrail`, `REQ-cross-case-analysis`, `REQ-anomaly-detection`
- **Copilot (12):** `REQ-universal-copilot`, `REQ-dynamic-query-planner`, `REQ-copilot-pipeline`, `REQ-graphrag`, `REQ-multi-source-retrieval`, `REQ-evidence-grounded-answers-v1`, `REQ-evidence-grounded-answers-v2`, `REQ-copilot-response-contract`, `REQ-conversational-followup`, `REQ-copilot-visual-actions`, `REQ-ambiguity-clarification`, `REQ-evidence-insufficiency-honesty`
- **Reasoning & explainability (3):** `REQ-contradiction-surfacing`, `REQ-hypothesis-engine`, `REQ-explainable-ai`
- **OSINT (3):** `REQ-osint-enrichment`, `REQ-osint-verification-badging`, `REQ-osint-source-independence`
- **Evidence & integrity (5):** `REQ-tamper-detection`, `REQ-chain-of-custody`, `REQ-ledger-integrity-v1`, `REQ-ledger-integrity-v2`, `REQ-court-dossier-export`
- **UI (2):** `REQ-investigator-dashboard`, `REQ-ui-intelligence-console`
- **Security (4):** `REQ-authentication`, `REQ-rbac-case-isolation`, `REQ-audit-logging`, `REQ-secure-handling`
- **Platform & delivery (8):** `REQ-api-surface`, `REQ-synthetic-dataset`, `REQ-test-suite`, `REQ-uat-suite`, `REQ-copilot-acceptance-scenario`, `REQ-demo-scenario`, `REQ-deployment-packaging`, `REQ-runtime-verification`

**Two competing-variant pairs are preserved unmerged** and must be resolved by the user before routing:
- `REQ-evidence-grounded-answers-v1` (SPEC §20 section set, categorical confidence) vs `-v2` (PRD §5.2/§5.3 inline citations, numeric confidence)
- `REQ-ledger-integrity-v1` (SPEC §22 any local permissioned ledger) vs `-v2` (PRD/planning EVM smart contract + Ganache/Hardhat)

## Constraints — 32 extracted

Full detail in `constraints.md`. Type breakdown: **protocol 18, nfr 6, api-contract 5, schema 3**.

Constraints are recorded in matched pairs where a target constraint and a current-build constraint both exist (target stack vs current implemented stack; target evidence-integrity protocol vs current fabricated-hash implementation; target security NFRs vs current zero enforcement; target relational schema vs current SQLAlchemy models; target API surface vs current routers; target deployment topology vs no container config; AI implementation prohibitions vs the current violation). Roadmapping should read each pair together — the delta is the work.

## Context topics — 17

`context.md` covers: product identity and tagline; core product principle; value proposition; target personas; core user journeys; signature features; scope tiering; explicit non-goals; example investigator questions; the Operation ShadowNet golden demo script; technology selection rationale; reference architecture; ingestion pipeline detail; tri-view synchronization behavior; **docs-vs-implementation divergence**; currently working features worth preserving; ingest provenance.

## Conflicts — 0 blockers, 9 warnings (incl. 2 competing-variant pairs), 18 info

**No blockers.** Nothing gates the workflow. Full report: `../INGEST-CONFLICTS.md`.

The nine warnings each require a user decision before routing:
1. Graph and relational store — SPEC §31 "use existing stack" vs PRD/planning mandating Neo4j + PostgreSQL, against a NetworkX + SQLite reality.
2. Copilot is a hardcoded question router, the exact pattern SPEC §4 and §43 forbid — scope it as unbuilt, not partially built.
3. Competing ledger variants, neither currently satisfied (fabricated hashes in the same SQLite DB they attest).
4. No vector/semantic retrieval exists, and GraphRAG depends on it.
5. RBAC and case isolation declared in all three docs, enforced on zero routes; UAT-10 cannot pass.
6. Performance NFRs unattainable against uncached full-graph betweenness centrality and a blocking 8s LLM call.
7. PRD.md §12.1 release gate is pre-marked `[x]` complete while describing an unbuilt system — do not read it as status.
8. Object storage — FR-ING-03's hash-before-write-to-MinIO ordering and UAT-9 assume an object store that does not exist.
9. Competing Copilot answer-format variants (section set and confidence representation).

## The central finding

All three documents describe a **target** state. The codebase map at `../codebase/` describes the **current** state. They differ materially, and the gap is the work to be done — it is captured as requirements and constraints, not as a blocker.

Target vs actual, in brief: Neo4j + GDS → in-memory NetworkX MultiDiGraph rebuilt from SQLite at startup; PostgreSQL 16 + pgvector → SQLite with no vector search of any kind; MinIO → local filesystem; Redis + Celery → absent; Next.js 14 → Vite + React 19; MapLibre → Leaflet (SPEC-permitted); vis-timeline → custom component; Tesseract/spaCy OCR-NER pipeline → absent; GraphRAG dynamic query planner → keyword-matched canned responses with an ungrounded Gemini REST fallback that fabricates citations and confidence; Hyperledger/EVM ledger → `uuid.uuid4()` transaction hashes in a SQLite table; controlled OSINT → mocked; RBAC → declared, never enforced; test suite and Docker Compose → absent.

Two consequences that should shape the roadmap:
- **The Copilot is unbuilt, not half-built.** SPEC.md §43 states "Never hardcode fake AI answers merely to make the UI appear functional", which is precisely what `backend/app/services/ai_investigator.py:21-133` does. Treat MVP-14/MVP-15/MVP-16 as new construction, and treat the fabricated `confidence_score: 0.90` and synthetic citation object on the Gemini fallback path as a correctness defect to remove first.
- **SPEC.md §31's "Use the existing stack if already established" is in direct tension with PRD.md and planning.md mandating Neo4j and PostgreSQL.** This is the single highest-leverage open decision: migrate to the documented stack, or keep SQLite/NetworkX (adding graph durability) and amend the documents. Nearly every other stack warning resolves downstream of this one.

## Files

- `decisions.md` — 15 proposed decisions, 0 locked
- `requirements.md` — 54 requirements, 2 competing-variant pairs preserved
- `constraints.md` — 32 constraints, target and current-build pairs
- `context.md` — 17 topics including the full divergence record
- `../INGEST-CONFLICTS.md` — 0 blockers / 9 warnings / 18 info
- `classifications/` — 3 per-doc classification JSON files
- `../codebase/` — existing codebase map (STACK, ARCHITECTURE, CONCERNS, CONVENTIONS, INTEGRATIONS, STRUCTURE, TESTING)
