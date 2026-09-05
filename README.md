# SPEMACS

Secure Pattern &amp; Evidence Mapping and Analysis of Suspicious Structure — an
investigative decision-support platform. It ingests case documents, telecom and
financial records, builds a temporal knowledge graph over them, and answers
open-ended investigator questions with citations, counter-evidence and stated
uncertainty.

Everything in this repo runs against a **synthetic dataset**. No real case data,
no real people.

---

## Running it

You need **Python 3.11+** and **Node 20.19+ or 22.12+** (Vite 8 refuses older
Node). Two terminals.

### First time only

```bash
pip install -r backend/requirements.txt && npm install --prefix frontend
```

Optionally, copy the environment template. The API starts fine without it —
every setting has a working default:

```bash
cp backend/env.example backend/.env
```

### Terminal 1 — backend

```bash
cd backend && python -m uvicorn app.main:app --reload --port 8000
```

Serves on http://localhost:8000, with interactive API docs at
http://localhost:8000/docs. The database seeds itself on startup, so there is
no migration step.

### Terminal 2 — frontend

```bash
cd frontend && npm run dev
```

Open http://localhost:5173. Vite proxies `/api` to `127.0.0.1:8000`, so start
the backend first.

### Tests

```bash
cd backend && python test_mvp.py
```

31 assertions across the UAT scenarios, the acceptance-test flow, full-detail
briefs and the cross-case engine.

---

## Seeded accounts

Synthetic demo credentials, created on first startup. Case access differs by
account on purpose — it is what the authorisation tests exercise.

| Username | Password | Role | Cases |
|---|---|---|---|
| `admin` | `admin123` | ADMIN | both |
| `rajiv_sen` | `investigator123` | LEAD_INVESTIGATOR | both |
| `ananya_rao` | `analyst123` | ANALYST | ShadowNet only |
| `auditor` | `auditor123` | AUDITOR | both |

Two cases are seeded: **CASE-2024-8812** (Operation ShadowNet, active) and
**CASE-2023-1104** (Operation Golden Falcon, archived).

---

## What is in here

| Tab | What it does |
|---|---|
| **Tri-View Workspace** | Knowledge graph, satellite map and event timeline, kept in sync — selecting in one focuses the others. |
| **AI Investigator** | Ask open-ended questions in plain language. Answers cite evidence, surface contradictions and state what is missing. Flip **Full Info** to get the entire record set inline. |
| **Evidence & Blockchain** | Evidence register with SHA-256 digests, chain of custody, and a tamper simulation. |
| **Cross-Case & Anomalies** | Where this case touches other investigations, and why; plus spatial and temporal anomalies with their baselines. |
| **Ingestion & OCR** | Upload documents, extract text, register evidence. |
| **Court Dossier** | Export a court-admissible case memorandum. |

### Layout

```
backend/
  app/api/          FastAPI routes
  app/services/     the engines - query planner, cross-case, briefing, graph, retrieval
  app/models/       SQLAlchemy tables
  data/synthetic/   the seeded dataset
  test_mvp.py       the whole test suite
frontend/src/
  components/       one directory per workspace panel
  lib/api.ts        every backend call
```

---

## Two rules the code holds to

**Nothing is asserted that the records do not support.** Answers carry
citations, counter-evidence, and explicit evidence gaps. Counts in a case brief
are read from the record store at query time rather than written into a
template, so they stay honest when the data changes.

**A connection is never a conclusion.** The cross-case engine reports shared
entities, identifiers, locations, timing and network paths as reasons to read
two files together. Confidence measures how sure the engine is that a link
*exists in the records*, not how suspicious it is, and every link ships with
what would make it wrong. Nothing in the system scores suspicion or infers
criminality from association.

---

## Known limitations

- **Authentication is bypassed for the prototype.** A request with no bearer
  token resolves to the first ADMIN account (`app/core/security.py`), so the
  case-level authorisation checks pass unconditionally for unauthenticated
  callers. The scoping logic itself is correct and tested — it only takes effect
  once the frontend sends the token from `/auth/login`. Remove that fallback
  before this runs anywhere real.
- `SECRET_KEY` has a public default committed in `config.py`. Set your own in
  `.env` before exposing the API beyond localhost.
- PDF and image text extraction needs optional extras (`pypdf`, `pytesseract`,
  `Pillow`, plus the tesseract binary). Without them the API runs normally and
  reports that extraction is unavailable.
