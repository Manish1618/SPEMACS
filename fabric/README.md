# Fabric evidence ledger

Anchors SPEMACS evidence digests and custody events to Hyperledger Fabric
chaincode, endorsed by two organisations.

**What this buys.** One property, and it is worth being precise about it: with
the endorsement policy set to `AND('Org1MSP.member','Org2MSP.member')`, no single
organisation can write or rewrite custody history on its own. That is the only
guarantee the local hash chain in `backend/app/services/ledger/local.py` cannot
provide by itself, and the entire reason this subsystem exists.

**What it does not buy.** It does not make evidence truthful, it does not replace
a §63 BSA certificate, and it does not protect anything if you run it with one
organisation — a single org controls all its own peers, so there is nobody to
collude against. A one-org deployment is strictly more complex than the local
chain with no added trust.

---

## How it fits together

```
FastAPI                    Node sidecar              Fabric
─────────────────────      ────────────────          ──────────────────────
evidence.py
   │ append_block()
   ▼
local hash chain  ────┐    (same DB transaction)
   │                  │
   ▼                  ▼
LedgerBlock      ledger_anchors (outbox, PENDING)
                       │
                       │  worker.py, every 20s
                       ▼
                  POST /anchors  ─────────────►  SealEvidence
                                                 RecordCustody      2 orgs
                                                 RecordAudit        endorse
                       ◄───────────────────────  txId
                  mark ANCHORED
```

The local chain commits **with** the evidence row and answers immediately. Fabric
anchoring happens after, asynchronously. An evidence write never blocks on
consensus and never fails because the network is down — the anchor simply stays
`PENDING` until the worker delivers it.

### Why an outbox rather than writing to Fabric inline

Postgres and Fabric cannot commit atomically together. Writing inline produces
the two failure modes that corrupt an evidence store:

- Fabric commits, Postgres rolls back → an anchor with no evidence behind it
- Postgres commits, Fabric times out → evidence whose anchor never happened, with
  no record that it was owed one

So nothing is written to Fabric inline. The *intent* to anchor is committed in
the same transaction as the evidence, and delivery happens afterwards. Delivery
is idempotent on `anchor_id`, so a retry whose outcome was never observed is
safe.

### Why a Node sidecar

Fabric's v2.4+ Gateway SDKs are published for Go, Node and Java — not Python.
Rather than hand-rolling gRPC and endorsement handling against `fabric-protos`,
the supported Node SDK runs as a small sidecar (`gateway/server.js`) exposing a
narrow HTTP face to the Python backend. It is the only process holding Fabric
identity material.

---

## Layout

```
chaincode/spemacs-ledger/
  lib/evidenceLedger.js    the contract
  test/                    11 contract tests, no network needed
  dev/devserver.js         stub server - contract logic over HTTP, in memory
gateway/server.js          the real sidecar, talks to the network
scripts/                   setup, start, stop, environment
```

---

## Running it

### Without Docker — contract logic and backend integration

This path needs nothing but Node. It runs the **real contract class** against an
in-memory stub, so the logic and the backend wiring are genuinely exercised.

```bash
cd fabric/chaincode/spemacs-ledger && npm install && npm test
```

```bash
cd fabric/chaincode/spemacs-ledger && npm run dev
```

Then, in another terminal:

```bash
cd backend && python test_fabric_integration.py
```

> The dev server is **not a ledger**. No consensus, no second organisation, state
> lost on exit. Every response carries `mode: "stub"` and the API surfaces that,
> so it can never be mistaken for a real anchor. Use it to develop; never to
> demonstrate tamper resistance.

### With Docker — the real two-org network

Requires **WSL2 + Docker Desktop** on Windows. Run these inside WSL, not Git Bash.

```bash
wsl --install
```

(Administrator PowerShell, then reboot. Install Docker Desktop and enable
Settings → Resources → WSL Integration.)

Then:

```bash
bash fabric/scripts/setup.sh
```

```bash
bash fabric/scripts/start-network.sh
```

```bash
source fabric/scripts/env.sh && node fabric/gateway/server.js
```

Finally, in `backend/.env`:

```
FABRIC_ENABLED=true
FABRIC_GATEWAY_URL=http://127.0.0.1:7090
FABRIC_GATEWAY_TOKEN=<a long random string, same value on both sides>
```

Restart the API. `GET /health` should report `"fabric_anchoring": true` and
`"anchor_worker": true`.

---

## Checking it works

| Endpoint | Answers |
|---|---|
| `GET /api/v1/evidence/ledger/anchoring` | Is the gateway reachable, and is anything stuck in the outbox? |
| `GET /api/v1/evidence/{id}/fabric-anchor` | What does chaincode hold for this item, independently of our database? |
| `POST /api/v1/evidence/ledger/drain` | Deliver queued anchors now instead of waiting for the worker (admin) |
| `POST /api/v1/evidence/{id}/verify` | Integrity check, now including the chaincode's own verdict |

The tamper demo (`POST /evidence/{id}/simulate-tamper`, then `verify`, then
`restore`) reports the chaincode's opinion alongside the local one.

---

## Contract surface

| Function | Purpose |
|---|---|
| `SealEvidence(anchorId, payload)` | Register a digest for an evidence item |
| `RecordCustody(anchorId, payload)` | Transfer, access, collection — any custody action |
| `RecordAudit(anchorId, payload)` | Outcome of an integrity check |
| `GetAnchor(evidenceId)` | Latest anchor |
| `GetAnchorHistory(evidenceId)` | Every version, via `GetHistoryForKey` |
| `VerifyAnchor(evidenceId, sha256)` | Does the ledger hold this digest? |
| `QueryByCase(caseId)` | All anchors for a case |
| `AnchorExists(evidenceId)` | Existence check that does not throw |

### Two design decisions worth knowing

**No block counter, no hash chain inside the chaincode.** Fabric blocks already
hash-chain and every key carries version history. Re-implementing a chain inside
would add nothing — and a read-then-increment "head" key is the classic Fabric
hotspot: two transactions in the same block read the same version and the second
fails with `MVCC_READ_CONFLICT`. Records are keyed by evidence id, which has no
shared counter to contend on.

**Nothing reads the wall clock.** Every endorsing peer executes the contract
independently and the read/write sets must match byte for byte. Timestamps
arrive as arguments, fixed before endorsement; anything the contract stamps
itself comes from `GetTxTimestamp()`, never `Date.now()`.

---

## Operational notes

- **The drain worker runs in-process.** With several uvicorn workers each runs
  its own copy. Delivery stays correct because the chaincode deduplicates on
  `anchor_id`, but two workers may briefly attempt the same row. Run the drain in
  one process before scaling out.
- **`FAILED` anchors are kept, never dropped.** After `FABRIC_MAX_ATTEMPTS` a row
  stops being retried but remains visible in `ledger_anchors` and in the
  anchoring status endpoint. An unanchored record should be an obvious gap, not
  a silent one.
- **Tearing down the network destroys the ledger.** Rows already marked
  `ANCHORED` are not re-sent to a rebuilt network. Reset them deliberately if you
  want the new network to carry existing history:
  `UPDATE ledger_anchors SET status='PENDING', fabric_tx_id=NULL, attempts=0;`
- **Set `FABRIC_GATEWAY_TOKEN`.** Anything that can reach the gateway can write
  to the ledger. It binds to loopback by default; the token is the second lock.
