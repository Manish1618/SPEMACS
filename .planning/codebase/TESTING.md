# Testing Patterns

**Analysis Date:** 2026-09-05

## Test Framework

**Runner:**
- No pytest, unittest, jest, or vitest is configured anywhere in the repo. There is no `pytest.ini`, `pyproject.toml` test config, `jest.config.*`, or `vitest.config.*`.
- The only "test" artifact is `backend/test_mvp.py`, a standalone script executed directly with `python test_mvp.py` (guarded by `if __name__ == "__main__": run_all_tests()`), not discovered/run by a test runner.
- It uses FastAPI's `TestClient` (from `fastapi.testclient`) for in-process HTTP calls against the app, and plain `assert` statements for verification — there is no `pytest` import and no test framework dependency in `backend/requirements.txt`.

**Assertion Library:**
- Bare Python `assert` statements. No `pytest.raises`, no matcher library (no `expect`, no `chai`, no `jest` matchers).

**Run Commands:**
```bash
cd backend
python test_mvp.py       # Runs all 10 UAT scenarios sequentially, prints PASS/FAIL to stdout
```
- Frontend has no test script in `frontend/package.json` (`scripts` only defines `dev`, `build`, `lint`, `preview`). There is no frontend test suite of any kind.

## Test File Organization

**Location:**
- `backend/test_mvp.py` lives at the top of `backend/`, not inside a `tests/` directory, and not co-located with the modules it exercises.
- No `frontend` test files exist (no `*.test.tsx`, `*.spec.ts`, or `__tests__/` directories under `frontend/src/`).

**Naming:**
- Single file named `test_mvp.py` — no per-module test file naming convention has been established yet (no `test_<module>.py` pattern to follow).

**Structure:**
```
backend/
└── test_mvp.py     # single script covering all 10 UAT scenarios in one function
```

## Test Structure

**Suite Organization:**
`backend/test_mvp.py` defines one flat function, `run_all_tests()`, that runs all scenarios linearly and re-seeds the database at the start:

```python
def run_all_tests():
    db = SessionLocal()
    seed_database_and_graph(db)
    db.close()

    passed = 0

    # UAT-1: Ingest Synthetic Case Data & Entity Extraction
    res1 = client.get("/api/v1/cases")
    assert res1.status_code == 200
    cases = res1.json()
    assert any(c["case_id"] == "CASE-2024-8812" for c in cases)
    print("[PASS - UAT-01] Ingest Synthetic Case Data & Entity Extraction")
    passed += 1
    ...
```

**Patterns:**
- Setup: explicit DB re-seed at the start of the run (`seed_database_and_graph(db)`), not per-test fixtures.
- No teardown — SQLite file persists between runs; the seed function appears idempotent/reset-capable.
- Assertion pattern: perform an HTTP call via `TestClient`, assert `status_code == 200`, then assert specific fields/shape in the JSON body.
- Each scenario ends with a `print(f"[PASS - UAT-xx] ...")` and `passed += 1` — no formal pass/fail reporting beyond console output and Python's own `AssertionError` on failure (no try/except around each scenario, so a failure aborts the whole run).

## Mocking

**Framework:** None. No `unittest.mock`, `pytest-mock`, `msw`, or `vi.mock` usage detected anywhere in the codebase.

**Patterns:**
- Tests run against the real FastAPI app with a real SQLite database (via `SessionLocal` from `backend/app/models/database.py`) and real service logic (`seed_database_and_graph`) — no network/service mocking layer exists.
- The AI investigator (`backend/app/services/ai_investigator.py`, integrating Gemini) and OSINT service (`backend/app/services/osint.py`) are exercised directly through `TestClient` calls rather than mocked; any external calls they make are not isolated in tests.

**What to Mock:**
- Not established by precedent. If adding a real test suite, external/paid calls (Gemini LLM in `ai_investigator.py`, any OSINT network calls in `osint.py`) are the primary candidates to mock going forward, since `test_mvp.py` currently exercises them live.

**What NOT to Mock:**
- Database and internal service layer — current script exercises these directly via `TestClient` + real SQLite DB, and that pattern should be preserved for consistency if extending `test_mvp.py`.

## Fixtures and Factories

**Test Data:**
- No fixture files or factory functions. Seed data is produced by the application's own seeding function:
  ```python
  from app.services.ingestion import seed_database_and_graph
  db = SessionLocal()
  seed_database_and_graph(db)
  db.close()
  ```
- Hardcoded literal test data is inlined directly in the test file, e.g.:
  ```python
  doc_payload = {"case_id": "CASE-2024-8812", "title": "Automated Interrogation Memo", "file_type": "PDF_SCAN"}
  files = {"file": ("test_memo.pdf", b"INTERROGATION_TRANSCRIPT_FEBRUARY_2024_CONFIDENTIAL", "application/pdf")}
  ```
- Fixed known case ID `"CASE-2024-8812"` and fixed user credentials (`"rajiv_sen"` / `"investigator123"`) are used throughout as the canonical seeded demo dataset — new tests should reuse this same seeded case rather than introducing new IDs, unless the seeding logic in `backend/app/services/ingestion.py` is extended.

**Location:**
- Seed/demo data logic lives in `backend/app/services/ingestion.py` (`seed_database_and_graph`), which doubles as both application bootstrap data (also called on FastAPI `startup_event` in `backend/app/main.py`) and test fixture data.

## Coverage

**Requirements:** None enforced. No coverage tool (`coverage.py`, `pytest-cov`, `c8`, `istanbul`) is configured.

**View Coverage:**
```bash
# Not applicable — no coverage tooling present.
```

## Test Types

**Unit Tests:**
- None. No isolated unit tests exist for services (`ai_investigator.py`, `graph_engine.py`, `evidence.py`, `ingestion.py`, `osint.py`) or utilities (`app/core/security.py`).

**Integration Tests:**
- `backend/test_mvp.py` is effectively a full-stack integration/acceptance test: it drives the FastAPI app end-to-end (routing → service → DB) via `TestClient`, covering 10 documented UAT scenarios (cases listing, document upload/hashing, graph data, map/timeline sync, AI investigation with citations, ambiguity handling, evidence-gap handling, contradiction detection, tamper detection/blockchain ledger, auth/RBAC/audit logging).

**E2E Tests:**
- Not used. No Playwright/Cypress/Selenium setup for the frontend, and no browser-driven testing of the React app.

## Common Patterns

**Async Testing:**
- Not applicable — `TestClient` calls are synchronous even though the underlying FastAPI routes are defined as sync `def` handlers (no `async def` routes observed in `backend/app/api/`).

**Error Testing:**
- Not directly tested (no scenario asserts a 4xx/5xx failure path such as invalid login or missing case). If adding tests, follow the existing status-code + JSON-body assertion pattern:
  ```python
  res = client.post("/api/v1/auth/login", json={"username": "bad", "password": "wrong"})
  assert res.status_code == 401
  ```

## Recommendations for Extending Test Coverage

- No test runner is wired up (`pytest`) — before adding new tests, introduce `pytest` as a dependency and a `tests/` directory, since `test_mvp.py`'s manual-script style does not scale or integrate with CI.
- No frontend tests exist at all; introducing Vitest + React Testing Library (compatible with the existing Vite setup in `frontend/vite.config.ts`) would be the natural first step if UI testing is required.
- Current single-script approach means one assertion failure aborts all subsequent UAT checks — splitting into independent pytest test functions would isolate failures per scenario.

---

*Testing analysis: 2026-09-05*
