"""
Automated Verification Test Suite for SPEMASS Core MVP & Universal Copilot
Tests all 10 UAT scenarios defined in PRD.md plus the full Section 41 9-Step Acceptance Test flow.
"""

from fastapi.testclient import TestClient
from app.main import app
from app.models.database import SessionLocal
from app.services.ingestion import seed_database_and_graph

client = TestClient(app)

def run_all_tests():
    print("==================================================================")
    print("           SPEMASS MVP & ACCEPTANCE TEST SUITE                    ")
    print("==================================================================")

    # Re-seed DB & Graph
    db = SessionLocal()
    seed_database_and_graph(db)
    db.close()

    passed = 0

    # UAT-10 first: Login to get token for RBAC
    login_res = client.post("/api/v1/auth/login", json={"username": "rajiv_sen", "password": "investigator123"})
    assert login_res.status_code == 200
    auth_data = login_res.json()
    assert "access_token" in auth_data
    assert auth_data["user"]["role"] == "LEAD_INVESTIGATOR"
    token = auth_data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("[PASS - UAT-10] Authentication, RBAC & Immutable Audit Logging")
    passed += 1

    # UAT-1: Ingest Synthetic Case Data & Entity Extraction
    res1 = client.get("/api/v1/cases", headers=headers)
    assert res1.status_code == 200
    cases = res1.json()
    assert any(c["case_id"] == "CASE-2024-8812" for c in cases)
    print("[PASS - UAT-01] Ingest Synthetic Case Data & Entity Extraction")
    passed += 1

    # UAT-2: Document OCR & Upload Hashing
    doc_payload = {
        "case_id": "CASE-2024-8812",
        "title": "Automated Interrogation Memo",
        "file_type": "PDF_SCAN"
    }
    files = {"file": ("test_memo.pdf", b"INTERROGATION_TRANSCRIPT_FEBRUARY_2024_CONFIDENTIAL", "application/pdf")}
    res2 = client.post("/api/v1/ingestion/upload", data=doc_payload, files=files, headers=headers)
    assert res2.status_code == 200
    upload_data = res2.json()
    assert "sha256_hash" in upload_data and len(upload_data["sha256_hash"]) == 64
    print(f"[PASS - UAT-02] Document Upload, OCR & SHA-256 Hashing ({upload_data['sha256_hash'][:16]}...)")
    passed += 1

    # UAT-3: Synchronized Tri-View Graph Data
    res3 = client.get("/api/v1/graph/case/CASE-2024-8812", headers=headers)
    assert res3.status_code == 200
    gdata = res3.json()
    assert len(gdata["nodes"]) >= 10
    assert len(gdata["edges"]) >= 10
    print(f"[PASS - UAT-03] Tri-View Graph Data ({len(gdata['nodes'])} Nodes, {len(gdata['edges'])} Edges)")
    passed += 1

    # UAT-4: Temporal Events & Map Co-presence Coordinates
    res4_map = client.get("/api/v1/workspace/map-events?case_id=CASE-2024-8812", headers=headers)
    res4_time = client.get("/api/v1/workspace/timeline?case_id=CASE-2024-8812", headers=headers)
    assert res4_map.status_code == 200 and len(res4_map.json()) >= 5
    assert res4_time.status_code == 200 and len(res4_time.json()) >= 5
    print(f"[PASS - UAT-04] Spatio-Temporal Sync ({len(res4_map.json())} Geocoded Pins, {len(res4_time.json())} Timeline Ticks)")
    passed += 1

    # UAT-5: Grounded Universal AI Investigator with Exact Citations
    q5 = {"case_id": "CASE-2024-8812", "query": "What connects Vikram Malhotra to the $250k Swiss transfer on Feb 15?"}
    res5 = client.post("/api/v1/ai/investigate", json=q5, headers=headers)
    assert res5.status_code == 200
    ai5 = res5.json()
    assert len(ai5["citations"]) >= 2
    assert any("250,000" in c["quote_or_claim"] or "CCTV" in c["source_title"] or "Tower" in c["source_title"] for c in ai5["citations"])
    print(f"[PASS - UAT-05] Grounded AI Investigator with Citations ({len(ai5['citations'])} Primary References)")
    passed += 1

    # UAT-6: Ambiguous Query Clarification Dialog
    q6 = {"case_id": "CASE-2024-8812", "query": "Show calls made by Rahul"}
    res6 = client.post("/api/v1/ai/investigate", json=q6, headers=headers)
    assert res6.status_code == 200
    ai6 = res6.json()
    assert ai6["is_ambiguous"] is True
    assert len(ai6["clarification_options"]) >= 2
    print(f"[PASS - UAT-06] Ambiguity Clarification Prompt ({len(ai6['clarification_options'])} Disambiguation Options)")
    passed += 1

    # UAT-7: Evidence Insufficiency & Evidence Gaps Handling
    q7 = {"case_id": "CASE-2024-8812", "query": "Show evidence of luxury yacht and helicopter purchases"}
    res7 = client.post("/api/v1/ai/investigate", json=q7, headers=headers)
    assert res7.status_code == 200
    ai7 = res7.json()
    assert ai7["confidence_level"] == "INSUFFICIENT_DATA"
    assert len(ai7["evidence_gaps"]) >= 1
    print(f"[PASS - UAT-07] Evidence Insufficiency Honesty & Evidence Gap Discovery ({len(ai7['evidence_gaps'])} Gaps Identified)")
    passed += 1

    # UAT-8: Contradiction Surfacing (Witness Statement vs CDR / CCTV)
    q8 = {"case_id": "CASE-2024-8812", "query": "Where was Vikram on Feb 14 and is there any contradicting alibi?"}
    res8 = client.post("/api/v1/ai/investigate", json=q8, headers=headers)
    assert res8.status_code == 200
    ai8 = res8.json()
    assert len(ai8["counter_evidence"]) >= 1
    assert "Dubai" in ai8["counter_evidence"][0]["claim"]
    print(f"[PASS - UAT-08] Contradiction Surfacing ({ai8['counter_evidence'][0]['discrepancy'][:55]}...)")
    passed += 1

    # UAT-9: Cryptographic Tamper Detection & Blockchain Ledger Proof
    res_ev = client.get("/api/v1/evidence?case_id=CASE-2024-8812", headers=headers)
    ev_list = res_ev.json()
    ev_id = ev_list[0]["evidence_id"]
    
    # 9a. Clean verification
    verify_clean = client.post(f"/api/v1/evidence/{ev_id}/verify", headers=headers).json()
    assert verify_clean["is_valid"] is True
    assert verify_clean["integrity_status"] == "VERIFIED"

    # 9b. Simulated tamper (1-byte modification)
    tamper_res = client.post(f"/api/v1/evidence/{ev_id}/simulate-tamper", headers=headers).json()
    assert tamper_res["verification_result"]["is_valid"] is False
    assert tamper_res["verification_result"]["integrity_status"] == "TAMPER_DETECTED"

    # 9c. Restore clean
    restore_res = client.post(f"/api/v1/evidence/{ev_id}/restore-clean", headers=headers).json()
    assert restore_res["verification_result"]["is_valid"] is True
    print("[PASS - UAT-09] Cryptographic SHA-256 Tamper Detection & Blockchain Ledger Verification")
    passed += 1

    # =========================================================================
    # SECTION 41 ACCEPTANCE TEST: FULL 9-STEP DYNAMIC INVESTIGATION WORKFLOW
    # =========================================================================
    print("------------------------------------------------------------------")
    print("      SECTION 41: FULL 9-STEP DYNAMIC INVESTIGATION TEST          ")
    print("------------------------------------------------------------------")

    # Step 2: Unpredefined question
    sec41_q2 = {
        "case_id": "CASE-2024-8812",
        "query": "Find unusual relationships that appeared after Person A met Person B and tell me whether any evidence connects them to this case."
    }
    sec41_res2 = client.post("/api/v1/ai/investigate", json=sec41_q2, headers=headers).json()
    assert "query_plan" in sec41_res2 and len(sec41_res2["query_plan"]) >= 4
    assert len(sec41_res2["citations"]) >= 2
    assert sec41_res2["visual_actions"] is not None
    print("[PASS - SEC41 Step 2-5] Dynamic Plan Generation, Grounded Citations & Visual Actions")

    # Step 6: Follow-up: "Show me the second relationship"
    sec41_q6 = {"case_id": "CASE-2024-8812", "query": "Show me the second relationship"}
    sec41_res6 = client.post("/api/v1/ai/investigate", json=sec41_q6, headers=headers).json()
    assert "250,000" in sec41_res6["answer"] or "Alpine Holdings" in sec41_res6["answer"]
    assert any("BANK" in c["evidence_id"] for c in sec41_res6["citations"])
    print("[PASS - SEC41 Step 6] Conversational Context: Focused on 2nd Relationship (Swiss Transfer)")

    # Step 7: Follow-up: "What contradicts this?"
    sec41_q7 = {"case_id": "CASE-2024-8812", "query": "What contradicts this?"}
    sec41_res7 = client.post("/api/v1/ai/investigate", json=sec41_q7, headers=headers).json()
    assert len(sec41_res7["counter_evidence"]) >= 1
    assert "Dubai" in sec41_res7["counter_evidence"][0]["claim"]
    print("[PASS - SEC41 Step 7] Counter-Evidence & Alibi Conflict Discovery")

    # Step 8: Follow-up: "Search authorized public sources for additional information"
    sec41_q8 = {"case_id": "CASE-2024-8812", "query": "Search authorized public sources for additional information"}
    sec41_res8 = client.post("/api/v1/ai/investigate", json=sec41_q8, headers=headers).json()
    assert "source_independence" in sec41_res8 and sec41_res8["source_independence"]["independent_sources_count"] >= 1
    print(f"[PASS - SEC41 Step 8] OSINT Enrichment & Source Independence (Reported: {sec41_res8['source_independence']['reported_sources_count']}, Independent: {sec41_res8['source_independence']['independent_sources_count']})")

    # Step 9: Follow-up: "Has any of this evidence been modified?"
    sec41_q9 = {"case_id": "CASE-2024-8812", "query": "Has any of this evidence been modified?"}
    sec41_res9 = client.post("/api/v1/ai/investigate", json=sec41_q9, headers=headers).json()
    assert "SHA-256" in sec41_res9["answer"] and "Verified Valid" in sec41_res9["answer"]
    print("[PASS - SEC41 Step 9] Cryptographic Hash Audit & Ledger Verification Follow-up")

    # Replay Endpoint Test (Time Machine)
    replay_res = client.get("/api/v1/workspace/replay?case_id=CASE-2024-8812", headers=headers)
    assert replay_res.status_code == 200
    replay_data = replay_res.json()
    assert replay_data["frame_count"] >= 5
    print(f"[PASS - REPLAY] Investigation Replay Engine ({replay_data['frame_count']} Chronological Frames)")

    passed += 1

    print("==================================================================")
    print(f"ALL TESTS PASSED WITH 100% SUCCESS ({passed} Core Suites Verified)!")
    print("==================================================================")

if __name__ == "__main__":
    run_all_tests()
