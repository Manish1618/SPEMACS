---
type: ADR
status: accepted
locked: false
date: 2026-09-13
supersedes: ADR-0001 D2 (partially)
---

# ADR-0002: Fabric chaincode anchoring for the evidence ledger

## Status

Accepted. Partially supersedes `ADR-0001` **D2**, which resolved that a local
append-only ledger with an independent store was sufficient and that a
smart-contract ledger "may be revisited post-MVP". This is that revisit.

`ADR-0001` D1 (Neo4j + PostgreSQL) is untouched by this decision.

## Context

`ADR-0001` D2 was decided on the reasoning that *"the decisive constraint is not
the ledger technology but store independence"* — the then-current implementation
verified a hash against a record in the very database being attested, so a
single writer could edit both together.

That reasoning was correct as far as it went, and it remains correct: store
independence is necessary. What it did not weigh is that store independence is
not **sufficient** for the multi-agency claim the product makes. A ledger held in
a second store that the same organisation controls still has exactly one party
who can rewrite it. The evidentiary claim SPEMACS makes — that custody history is
trustworthy across agencies — needs an attestation no single agency can forge
alone.

Two further facts changed the calculus:

1. The store-independence requirement from D2 **was never met**. `LedgerBlock`
   is declared on the same SQLAlchemy `Base` as `Evidence`, so the proof still
   lives inside the database it proves. Something had to change here regardless.
2. The integration seam turned out to be small: three write sites in
   `backend/app/services/evidence.py`, all with the same payload shape, and
   about seven call sites in total.

## Decision

Anchor evidence digests and custody events to Hyperledger Fabric chaincode,
endorsed by **two organisations**, while PostgreSQL remains the system of record.

### D2.1 — Chaincode is additive, not a replacement

The local hash chain stays and remains the synchronous path. Every anchor is
written locally first, inside the caller's own transaction. Fabric attests the
same records independently and asynchronously.

**Rationale:** an evidence write must never fail because a distributed ledger is
unreachable. It also keeps the app fully functional with `FABRIC_ENABLED=false`,
which is the default and the mode the existing test suite runs in.

### D2.2 — Two organisations, `AND` endorsement

Deployed with `AND('Org1MSP.member','Org2MSP.member')`.

**Rationale:** this is the entire justification for the subsystem. A single-org
Fabric network provides *no* trust benefit over the local chain — one operator
controls all its peers — while costing 7–9 containers and a WSL2 dependency. If
the policy is ever weakened to `OR`, the subsystem should be removed rather than
kept as decoration.

### D2.3 — Transactional outbox, never inline writes

`ledger_anchors` records the committed intent to anchor, written in the same
transaction as the `LedgerBlock`. A background worker delivers it afterwards.
Delivery is idempotent on a payload-derived `anchor_id`.

**Rationale:** Postgres and Fabric cannot commit atomically. Inline writes
produce either anchors with no evidence behind them, or evidence whose anchor
silently never happened. The outbox makes the second case visible instead:
a `PENDING` or `FAILED` row is an auditable gap.

### D2.4 — Node sidecar for gateway access

`fabric/gateway/server.js` holds the Fabric identity material and exposes a
narrow HTTP face to FastAPI.

**Rationale:** Fabric's v2.4+ Gateway SDKs are Go, Node and Java. The alternative
was hand-rolled gRPC against `fabric-protos` from Python — SDK glue we would own
and maintain on the integrity path. Chaincode is written in JavaScript for the
same reason: the sidecar is Node regardless, so this adds one language, not two.

### D2.5 — No hash chain inside the chaincode

Records are keyed by evidence id. History comes from `GetHistoryForKey`.

**Rationale:** Fabric blocks already hash-chain, so an inner chain adds nothing.
More importantly, a read-then-increment "head" counter is the canonical Fabric
hotspot — concurrent transactions in one block read the same version and all but
one fail with `MVCC_READ_CONFLICT`. Keying by evidence id has no shared counter
to contend on.

## Consequences

**Gained:** no single organisation can write or rewrite custody history alone.
The attestation lives outside the attested database, satisfying D2's original
requirement in its strongest form.

**Costs accepted:**

- WSL2 + Docker Desktop become prerequisites for the full configuration; the
  README grows a prerequisites section. Mitigated by the default-off switch and
  the stub dev server, so neither is needed for ordinary development.
- 7–9 additional containers when the network is running.
- A third language (JavaScript, server-side) and a fourth process.
- Chaincode changes require approve-then-commit from both orgs.
- The drain worker is in-process, so it is single-instance like the login rate
  limiter. Both need addressing before scaling out.

**Explicitly not claimed.** This attests that a recorded digest and custody
history have not changed. It does not attest that evidence is truthful, does not
replace a §63 BSA certificate, and provides nothing if run with one organisation.

## Alternatives rejected

**Public chain / DApp.** Permanent public record of case activity — even hashes
leak existence, timing and volume. Cannot comply with erasure or expungement
orders. Investigator wallets with no recovery contradict the account recovery
and session revocation already built.

**All state on-chain, no relational database.** A chain cannot serve the
retrieval layer's fuzzy matching and ranking, cannot delete when a court orders
it, and cannot absorb auth state — every failed login would become a
network-wide transaction, making the write cost the denial-of-service vector.

**Doing nothing (keeping `ADR-0001` D2 as decided).** Rejected because the
store-independence requirement it set was never actually implemented, so "no
change" was never the zero-cost option it appeared to be.

## Cheaper measures still worth taking

These were costed alongside chaincode and are **not** superseded by it. They
remain the right work, and two of them are independent of Fabric entirely:

1. Move the local ledger to its own store with `INSERT`-only permissions — still
   the right default for `FABRIC_ENABLED=false` deployments.
2. Sign each block with an agency key (Ed25519) for non-repudiation.
3. Periodic Merkle root anchoring to an RFC 3161 timestamp authority, giving
   third-party verifiability without depending on the Fabric network being up.
