# Decisions

Synthesized from ingested documents. MODE=new. Precedence: SPEC(0) > PRD(1) > DOC/planning(2).

**No ADR-classified documents were ingested.** Therefore no decision in this file is LOCKED. Every entry below is a decision *asserted by a document*, recorded with `status: proposed`, and is open to revision by the roadmapper or the user. Where documents disagree, all positions are recorded and the disagreement is logged in `../INGEST-CONFLICTS.md`.

---

## DEC-doc-precedence: SPEC.md supersedes PRD.md and planning.md on conflict
- source: SPEC.md (Document Status header, line 3)
- status: proposed
- decision: SPEC.md is the authoritative scope definition and supersedes PRD.md and planning.md where they conflict.
- scope: document precedence, conflict resolution across the ingested set

## DEC-inspect-before-implement: Inspect the existing repository before writing code
- source: SPEC.md §1
- status: proposed
- decision: Inspect the entire existing repository first; do not unnecessarily rewrite working components; reuse existing architecture where practical; identify incomplete/mocked/placeholder/broken functionality; produce a technical implementation plan before major changes; preserve existing working features unless they conflict with SPEC requirements.
- scope: development process, change management

## DEC-existing-stack-first: Use the existing stack if already established
- source: SPEC.md §31 ("Use the existing stack if already established. Otherwise prefer:")
- status: proposed
- decision: The recommended stack table (Neo4j, PostgreSQL, pgvector/Qdrant, MinIO/S3, Tesseract/PaddleOCR, spaCy, Hyperledger) applies only when no stack is already established. "Do not introduce technologies without a concrete reason."
- scope: technology selection

## DEC-no-fixed-question-router: Copilot must not be a fixed question dictionary
- source: SPEC.md §4, §43, §44
- status: proposed
- decision: Do NOT build `if question == X then run query A` logic or a finite question dictionary presented as AI. Implement a Dynamic Investigation Query Planner that converts natural-language questions into executable investigation plans generated at runtime. "Never hardcode fake AI answers merely to make the UI appear functional."
- scope: Universal Investigation Copilot, AI architecture

## DEC-graphrag-grounding: LLM may only claim what retrieval supports
- source: SPEC.md §26, §20; PRD.md §5.2 rule 3; planning.md §4.1
- status: proposed
- decision: Implement GraphRAG so the LLM does not operate independently. Every factual statement must carry an evidence citation. If evidence is insufficient, return an explicit insufficient-evidence response. Never fabricate. planning.md §4.1 adds a post-processing verification pass that strips or marks unmatched claims as `[Unverified Investigator Lead]`.
- scope: AI grounding, citation enforcement, hallucination control

## DEC-decision-support-only: SPEMASS never determines guilt or criminality
- source: SPEC.md §28, §16, §17; PRD.md §1.3; planning.md §1.3
- status: proposed
- decision: SPEMASS is strictly decision support. It must not determine guilt or innocence, recommend arrest or punishment, infer criminal intent from association, infer guilt from co-location or graph centrality, treat OSINT mentions or anomaly scores as proof, or present speculation as fact. Output must distinguish OBSERVED FACT / SOURCE INFORMATION / ANALYTICAL INFERENCE / POTENTIAL RELATIONSHIP / HYPOTHESIS / UNKNOWN. Human investigators remain final decision-makers.
- scope: responsible AI, legal and ethical boundaries

## DEC-blockchain-offchain-only: Store evidence off-chain, anchor metadata only
- source: SPEC.md §22; PRD.md §7.2 FR-EVD-04; planning.md §1.4, §8.1
- status: proposed
- decision: Do NOT store sensitive documents on-chain. Record only integrity/provenance metadata (Evidence ID, hash, timestamp, custody event, authorized actor, verification metadata). Blockchain proves the recorded hash history is unchanged per the ledger; it does not prove the underlying evidence is truthful.
- scope: evidence integrity, ledger design

## DEC-mvp-ledger-scope: A local demonstrable permissioned ledger is sufficient for MVP
- source: SPEC.md §22
- status: proposed
- decision: "Possible technology: Hyperledger Fabric, Hyperledger Besu, or another appropriate permissioned ledger. For an MVP, a local demonstrable permissioned-ledger implementation is sufficient."
- scope: ledger technology, MVP scope
- note: planning.md §2.1/§8.1/§12.1 instead mandates Hyperledger Fabric or a local EVM testbed with `EvidenceLedger.sol` and a Ganache/Hardhat container. SPEC precedence 0 wins on scope; see INGEST-CONFLICTS.md.

## DEC-never-silent-merge: Uncertain identities must never be merged silently
- source: SPEC.md §24; PRD.md §4.2 FR-RES-01; planning.md §3.2 step 5, RSK-02
- status: proposed
- decision: Entity resolution must never silently merge uncertain identities. Confidence >= 0.90 may auto-merge with provenance links; confidence 0.70–0.89 must be flagged `Potential Match — Requires Human Verification` and requires explicit investigator approval.
- scope: entity resolution, human-in-the-loop

## DEC-osint-lawful-only: Only legally accessible public information
- source: SPEC.md §14; planning.md §7.1
- status: proposed
- decision: OSINT is an in-platform module, not a separate application, and may only consider legally accessible public information. Do NOT implement credential bypass, private-account access, unauthorized system access, restricted database access, or surveillance of private individuals outside authorization.
- scope: OSINT, legal boundaries

## DEC-synthetic-data-only: Prototype uses entirely fictional data
- source: SPEC.md §33; PRD.md §3 scope matrix; planning.md §1.4
- status: proposed
- decision: For the SIH prototype, use entirely fictional/synthetic investigation data. Do not use real sensitive personal information.
- scope: data policy, demo dataset

## DEC-no-cot-exposure: Do not expose internal chain-of-thought
- source: SPEC.md §38
- status: proposed
- decision: Copilot responses use a structured internal contract. Do not expose internal chain-of-thought; expose only concise, evidence-supported reasoning appropriate for investigators.
- scope: Copilot response contract

## DEC-function-before-polish: Do not polish UI while core functionality is broken
- source: SPEC.md §42, §43 (step 20)
- status: proposed
- decision: Implementation order runs Phase 0–18 with UX polish at Phase 17 and testing at Phase 18. "Do not polish the UI while core functionality is still broken." Final UI polish only after end-to-end investigation works.
- scope: delivery sequencing

## DEC-local-fallback-provider: External API unavailability must not break the demo
- source: SPEC.md §43
- status: proposed
- decision: "If an external API/key is unavailable, implement a clean mock/local provider so the entire demo can still run locally." This permits a local LLM/provider stub but does NOT permit hardcoded fake AI answers (same section).
- scope: AI provider integration, demo resilience

## DEC-post-mvp-deferral: Named capabilities are explicitly deferred
- source: SPEC.md §36; PRD.md §3 scope matrix; planning.md §1.4
- status: proposed
- decision: Defer real CCTNS/ICJS integration, live nationwide data, real-time streaming CDR, production-scale deployment, facial recognition, speaker recognition, predictive policing, autonomous enforcement decisions, and large-scale distributed deployment. Build clean interfaces so these can be integrated later.
- scope: out-of-scope boundary, MVP focus
