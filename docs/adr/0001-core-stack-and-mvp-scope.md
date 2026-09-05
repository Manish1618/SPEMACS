---
type: ADR
status: accepted
locked: true
date: 2026-09-05
---

# ADR-0001: Core Stack and MVP Scope Resolutions

## Status

Accepted — **LOCKED**. These decisions resolve the four scope forks surfaced by
`/gsd-ingest-docs` in `.planning/INGEST-CONFLICTS.md` (9 warnings, 0 blockers).
They take precedence over any conflicting statement in `SPEC.md`, `PRD.md`, or
`planning.md`.

## Context

Three planning documents were ingested — `SPEC.md` (authoritative master spec),
`PRD.md` (product requirements), and `planning.md` (engineering blueprint). All
three describe a target stack that differs materially from what is actually
built, as established by the codebase map in `.planning/codebase/`:

| Concern | Documents specify | Actually built |
|---|---|---|
| Graph store | Neo4j 5.x + GDS | in-memory `networkx.MultiDiGraph`, non-durable |
| Relational store | PostgreSQL 16 | SQLite via SQLAlchemy |
| Vector retrieval | pgvector, 384-dim, ivfflat | none — no embedding model, no index |
| Ledger | EVM smart contract / Hyperledger | UUID-minted fake hashes in the attested SQLite DB |
| RBAC | 4 roles + case isolation | declared, enforced on zero routes |

`SPEC.md` §31 opens its stack table with "Use the existing stack if already
established", which pulls directly against `PRD.md` §4.2/§4.4 and `planning.md`
§2.1 mandating Neo4j and PostgreSQL unconditionally. That tension could not be
auto-resolved by precedence, because SPEC's clause is conditional and the
condition (an established stack) is arguably satisfied.

## Decisions

### D1 — Migrate to Neo4j 5.x + PostgreSQL 16

Adopt the documented stack. The in-memory NetworkX graph and SQLite store are
replaced.

**Rationale:** Preserves every Neo4j/Cypher/GDS acceptance criterion in
`PRD.md` §4.2 (FR-KNG-01), §4.4 (FR-ANA-01) and `planning.md` §2.1 without
amendment. Also resolves a genuine defect rather than merely relocating it: the
current graph is rebuilt from SQLite at startup and loses API-created entities
on restart, so "keep the existing stack" was never a no-op — it required its own
durability work regardless.

**Consequences:** A datastore migration touching the graph engine
(`backend/app/services/graph_engine.py`), all graph API routes, entity
resolution, analytics, and the AI retrieval layer. This is the largest single
work item in the roadmap and must land early, since GraphRAG, analytics, and
cross-case analysis all sit downstream of it.

**Supersedes:** `SPEC.md` §31's existing-stack clause, for the graph and
relational store only.

### D2 — Evidence ledger: local permissioned ledger with an independent store

Adopt `REQ-ledger-integrity-v1` (`SPEC.md` §22 scope). Implement an append-only,
hash-chained ledger whose storage is **independent of the PostgreSQL database it
attests**.

**Rationale:** `SPEC.md` §22 states a local demonstrable permissioned ledger is
sufficient for the MVP. The decisive constraint is not the ledger technology but
store independence: the current implementation verifies a hash against a record
in the very database being attested, so a single writer can edit both together.
That defeats the evidentiary-integrity claim in `PRD.md` §1.2 and `SPEC.md` §35.

**Consequences:** `PRD.md` §7.2 (FR-EVD-04) and `planning.md` §8.1/§12.1 must be
amended to drop the `EvidenceLedger.sol` / EVM / Ganache-on-8545 requirement.
`MVP-20` and `planning.md` Phase 6 DoD ("altering 1 byte fails hash
verification") remain in force and become honestly satisfiable. The rejected
alternative (Hardhat/Ganache EVM node) may be revisited post-MVP.

**Supersedes:** `PRD.md` §7.2 FR-EVD-04 smart-contract requirement;
`planning.md` §8.1 and §12.1 `spemass-blockchain-mock` service.

### D3 — Vector retrieval: pgvector

Document chunk embeddings are stored in PostgreSQL via the `pgvector` extension,
per the `document_chunks` schema in `planning.md` §5.3.

**Rationale:** D1 adopts PostgreSQL, so pgvector requires no additional
infrastructure and is the option `PRD.md` §4.1 (FR-ING-02), `PRD.md` §5.1 and
`planning.md` §5.3 already specify. No document amendment is needed.

**Consequences:** `MVP-15` (GraphRAG), `MVP-16` (evidence-grounded responses),
UAT-2 and UAT-5 remain achievable as written. The embedding pipeline
(Sentence-Transformers per `planning.md` §3.2 step 6) is new construction — no
embedding code exists today.

### D4 — Full RBAC with case-level isolation

Implement the four roles in `PRD.md` §8 (System Admin, Lead Investigator,
Analyst, Viewer) with case-level tenancy enforced on every route.

**Rationale:** `PRD.md` §3 tiers RBAC as `[MVP]`, not `[MVP-Lite]`, and UAT-10
tests it directly. It is also a judging differentiator for the SIH prototype.

**Consequences:** Requires role claims in the issued JWT, a verification
dependency on every router in `backend/app/api/`, and case-scoping parameters
threaded through every graph query method (`resolve_entity`,
`get_k_hop_neighborhood`, `get_shortest_path`), none of which currently accept
caller context. Also folds in the security defects catalogued in
`.planning/INGEST-CONFLICTS.md`: the plaintext-equals-hash fallback in
`backend/app/core/security.py`, the committed `SECRET_KEY` default and shared
fixed salt, the unused `passlib[bcrypt]` dependency, and
`allow_origins=["*"]` with `allow_credentials=True` in `backend/app/main.py`.

## Non-Decisions Carried Forward

The following warnings from `.planning/INGEST-CONFLICTS.md` required no choice —
they are unambiguous defects or document corrections, and are carried into
requirements rather than resolved here:

- **Copilot is a hardcoded question router.** `backend/app/services/ai_investigator.py`
  matches substrings and returns pre-written payloads, with a Gemini fallback that
  attaches a fabricated `confidence_score` and a fabricated citation. This is the
  exact anti-pattern `SPEC.md` §4 prohibits and violates `SPEC.md` §26/§43. The
  Copilot is scoped as **unbuilt**, not partially built. The fabricated
  confidence and citation must be removed before anything else ships; the
  scripted branches may remain temporarily behind an explicit `DEMO_MODE` flag.
- **Copilot answer format** — `SPEC.md` §20 sections with `PRD.md` §5.2 inline
  per-statement `[EvidenceID: ...]` citations, and confidence rendered as a
  numeric score alongside its categorical band. This unifies both variants rather
  than discarding either.
- **`PRD.md` §12.1 release gate is pre-checked** and asserts false completion.
  All boxes to be unchecked until verified against `SPEC.md` §44.
- **Performance NFRs** (`PRD.md` §8: 350ms/50k-node 2-hop, 200ms tri-view sync,
  2.0s first AI token) are unreachable on the current path — uncached full-graph
  betweenness centrality on every subgraph request, and a blocking synchronous
  `requests.post` with an 8s timeout inside the async event loop. The
  optimization work is committed to; targets are re-validated against the Neo4j
  implementation once D1 lands.
- **Object storage** — MinIO/S3 adopted per `PRD.md` §4.1 (FR-ING-03) and
  `planning.md` §2.1, making the hash-before-persistent-write ordering and UAT-9
  executable as written.
- **Evidence verification can report VERIFIED without recomputing a hash**
  (`backend/app/services/evidence.py`), and the `tampered_mock_cache`
  demo backdoor sits in the production evidence router
  (`backend/app/api/evidence.py`) — both fixed in the evidence phase, the latter
  gated behind `DEMO_MODE`.
- **`pydantic-settings` is imported but absent from `backend/requirements.txt`**,
  breaking a clean install. Foundation-phase fix.
- **No test framework, no container build, no CI.** Captured as
  `REQ-test-suite`, `REQ-uat-suite`, `REQ-deployment-packaging`.

## References

- `.planning/INGEST-CONFLICTS.md` — full conflict report (0 blockers, 9 warnings, 18 info)
- `.planning/intel/SYNTHESIS.md` — consolidated doc synthesis
- `.planning/codebase/` — evidence-backed map of the current implementation
- `SPEC.md`, `PRD.md`, `planning.md` — ingested source documents
