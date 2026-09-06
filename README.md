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

## Signing in

Every route except `/health` and `/api/v1/auth/config` requires an authenticated
investigator. The app opens on a login screen.

**In demo mode** (`DEMO_MODE=true`, the default) four synthetic accounts are
seeded on startup and the login screen lists them — click one to fill the form.
Case access differs by account on purpose; it is what the authorisation tests
exercise. Their passwords live in `backend/app/services/ingestion.py` and are
served by `/api/v1/auth/config` only while demo mode is on.

**Outside demo mode** (`DEMO_MODE=false`) no accounts are seeded at all. Create
the first administrator, then provision everyone else from the **Access Control**
tab:

```bash
cd backend
python create_admin.py
```

Two cases are seeded: **CASE-2024-8812** (Operation ShadowNet, active) and
**CASE-2023-1104** (Operation Golden Falcon, archived).

### How the session works

`POST /auth/login` returns a 15-minute access token, which the browser holds in
memory and sends as a Bearer header, plus an httpOnly `SameSite=Strict` refresh
cookie that script cannot read. `POST /auth/refresh` trades the cookie for a new
access token and rotates the cookie; replaying a rotated token revokes the whole
chain. A reload therefore keeps you signed in without a token ever sitting in
`localStorage`. Five failed sign-ins lock an account for fifteen minutes, and
every attempt is written to the audit log.

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

- **Sessions are single-process.** The login rate limiter keeps its counters in
  memory (`app/core/ratelimit.py`), so behind several uvicorn workers each worker
  enforces its own window. Move it to Redis before scaling out. Per-account
  lockout is in the database and is unaffected.
- **No second factor.** Sign-in is username and password only.
- **Set `COOKIE_SECURE=true` behind HTTPS.** It defaults to false so the refresh
  cookie works over plain HTTP on localhost.
- **`DEMO_MODE` must be off in production.** With it on, four accounts with
  published passwords are seeded on every startup and advertised by
  `/auth/config`. With it off the API refuses to start unless `SECRET_KEY` is set
  to something other than the placeholder in the repository.
- PDF and image text extraction needs optional extras (`pypdf`, `pytesseract`,
  `Pillow`, plus the tesseract binary). Without them the API runs normally and
  reports that extraction is unavailable.
