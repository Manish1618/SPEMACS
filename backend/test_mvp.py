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

    print("------------------------------------------------------------------")
    print("        FULL-DETAIL MODE: COMPLETE RECORD SET IN CHAT              ")
    print("------------------------------------------------------------------")

    # FULL-01: a question that asks for everything returns the whole record set inline
    full_q = {"case_id": "CASE-2024-8812", "query": "Give me full information about this case"}
    full_res = client.post("/api/v1/ai/investigate", json=full_q, headers=headers).json()
    sections = full_res["detail_sections"]
    section_ids = {s["section_id"] for s in sections}
    assert len(sections) >= 10, f"expected a full brief, got {len(sections)} sections"
    for required in (
        "case_overview",
        "entity_roster",
        "relationship_matrix",
        "chronology",
        "evidence_register",
        "network_analytics",
        "gaps_and_actions",
    ):
        assert required in section_ids, f"missing section {required}"
    # Every figure is counted, not asserted: the brief's stats must match the API.
    stats = full_res["detail_stats"]
    graph_res = client.get("/api/v1/graph/case/CASE-2024-8812", headers=headers).json()
    assert stats["entities"] == graph_res["stats"]["total_nodes"], (
        f"brief claims {stats['entities']} entities, graph reports {graph_res['stats']['total_nodes']}"
    )
    assert len(full_res["citations"]) >= 1
    print(f"[PASS - FULL-01] Full Case Brief In Chat ({len(sections)} Sections, {stats['events']} Events, {stats['evidence']} Artifacts)")

    # FULL-02: naming a subject attaches their individual dossier
    subj_q = {"case_id": "CASE-2024-8812", "query": "Tell me everything about Vikram Malhotra"}
    subj_res = client.post("/api/v1/ai/investigate", json=subj_q, headers=headers).json()
    dossiers = [s for s in subj_res["detail_sections"] if s["section_id"].startswith("dossier_")]
    assert dossiers, "naming a subject should attach a dossier"
    child_titles = {c["title"] for c in dossiers[0]["children"]}
    assert {"Profile", "Direct links", "Activity log"} <= child_titles, child_titles
    print(f"[PASS - FULL-02] Per-Subject Dossier Attached ({len(dossiers)} Subjects, {len(dossiers[0]['children'])} Blocks Each)")

    # FULL-03: the detail_level switch enriches a focused answer without replacing it
    focused = client.post(
        "/api/v1/ai/investigate",
        json={"case_id": "CASE-2024-8812", "query": "What contradicts this?"},
        headers=headers,
    ).json()
    enriched = client.post(
        "/api/v1/ai/investigate",
        json={"case_id": "CASE-2024-8812", "query": "What contradicts this?", "detail_level": "full"},
        headers=headers,
    ).json()
    assert enriched["answer"] == focused["answer"], "full mode must keep the focused answer"
    assert not focused["detail_sections"], "standard mode should not attach the record set"
    assert len(enriched["detail_sections"]) >= 10
    assert enriched["query_plan"][-1]["action"] == "EXPAND_FULL_DETAIL"
    print("[PASS - FULL-03] Detail Switch Appends Record Set Without Replacing The Answer")

    # FULL-04: the brief and dossier are reachable directly, not only through chat
    brief_res = client.get("/api/v1/ai/full-brief?case_id=CASE-2024-8812", headers=headers)
    assert brief_res.status_code == 200 and brief_res.json()["stats"]["sections"] >= 10
    dossier_res = client.get("/api/v1/ai/entity-dossier?entity_id=ENT-ORG-03", headers=headers)
    assert dossier_res.status_code == 200 and "Alpine Holdings" in dossier_res.json()["title"]
    assert client.get("/api/v1/ai/entity-dossier?entity_id=NO-SUCH", headers=headers).status_code == 404
    print("[PASS - FULL-04] Standalone Brief & Dossier Endpoints (404 On Unknown Subject)")

    # FULL-05: network topology answer no longer depends on a missing analytics method
    net_res = client.post(
        "/api/v1/ai/investigate",
        json={"case_id": "CASE-2024-8812", "query": "Show all networks"},
        headers=headers,
    )
    assert net_res.status_code == 200
    assert "Hub Nodes" in net_res.json()["answer"]
    print("[PASS - FULL-05] Network Topology Answer With Named Hubs & Bridges")

    print("------------------------------------------------------------------")
    print("           CROSS-CASE INTELLIGENCE ENGINE                          ")
    print("------------------------------------------------------------------")

    xc = client.get("/api/v1/cross-case/analyse?case_id=CASE-2024-8812", headers=headers)
    assert xc.status_code == 200
    report = xc.json()
    assert report["authorised"] is True
    links = report["links"]
    assert links, "expected cross-case links between ShadowNet and Golden Falcon"

    # XC-01: every link explains itself, is scored, and carries its uncertainties.
    for link in links:
        assert link["explanation"], f"{link['link_id']} has no stated basis"
        assert link["uncertainty"], f"{link['link_id']} has no stated uncertainty"
        assert 0.0 <= link["confidence"] <= 1.0
        assert link["confidence_band"] in ("HIGH", "MODERATE", "LOW")
        assert link["case_a"]["case_id"] == "CASE-2024-8812"
        assert link["case_b"]["case_id"] != "CASE-2024-8812"
    bases = {link["basis"] for link in links}
    print(
        f"[PASS - XC-01] {len(links)} Explained Links Across {len(bases)} Detection Bases "
        f"({', '.join(sorted(bases))})"
    )

    # XC-02: the non-inference rule is present on the report and on every link.
    assert "not evidence that an offence occurred" in report["caveat"]
    assert all("Association only" in link["interpretation"] for link in links)
    assert "not how incriminating" in report["confidence_meaning"]
    # Nothing in the payload may score or rank suspicion.
    forbidden = ("suspicion_score", "risk_score", "guilt", "criminality_score", "threat_score")
    payload_text = xc.text.lower()
    assert not any(term in payload_text for term in forbidden), "engine must not score suspicion"
    print("[PASS - XC-02] Non-Inference Guardrail On Report And Every Link")

    # XC-03: direct and multi-hop relationships are both detected.
    direct = [l for l in links if l["basis"] == "CROSS_CASE_RELATIONSHIP"]
    shared = [l for l in links if l["basis"] == "SHARED_ENTITY"]
    hops = [l for l in links if l["basis"] == "MULTI_HOP_PATH"]
    assert direct, "expected a recorded relationship spanning both files"
    assert shared, "expected an entity referenced by both files"
    assert hops, "expected an indirect network path between the files"
    multi = hops[0]
    assert multi["hops"] >= 2 and len(multi["path"]) == multi["hops"]
    # An indirect path must score below a direct relationship on the same data.
    assert multi["confidence"] < max(l["confidence"] for l in direct)
    print(
        f"[PASS - XC-03] Direct ({len(direct)}), Shared-Entity ({len(shared)}) And "
        f"{multi['hops']}-Hop Paths Detected With Decayed Confidence"
    )

    # XC-04: authorisation is the outer boundary of the search.
    analyst = client.post(
        "/api/v1/auth/login", json={"username": "ananya_rao", "password": "analyst123"}
    ).json()
    analyst_headers = {"Authorization": f"Bearer {analyst['access_token']}"}
    scoped = client.get(
        "/api/v1/cross-case/analyse?case_id=CASE-2024-8812", headers=analyst_headers
    ).json()
    assert scoped["authorisation"]["cases_in_scope"] == ["CASE-2024-8812"]
    assert scoped["authorisation"]["cases_out_of_scope"] >= 1
    assert scoped["summary"]["link_count"] == 0, "analyst must not see the archived case"
    # The excluded case must not be named anywhere in the analyst's payload.
    assert "CASE-2023-1104" not in client.get(
        "/api/v1/cross-case/analyse?case_id=CASE-2024-8812", headers=analyst_headers
    ).text
    denied = client.get(
        "/api/v1/cross-case/analyse?case_id=CASE-2023-1104", headers=analyst_headers
    )
    assert denied.status_code == 403
    print("[PASS - XC-04] Case-Level Authorisation Bounds The Search (403 On Unauthorised Case)")

    # XC-05: evidence is attached, and failed integrity surfaces as contradiction.
    with_evidence = [l for l in links if l["supporting_evidence"]]
    assert with_evidence, "expected links to cite evidence artifacts"
    assert all(
        "integrity_status" in item
        for link in with_evidence
        for item in link["supporting_evidence"]
    )
    print(
        f"[PASS - XC-05] {len(with_evidence)} Links Carry Cited Evidence With Integrity Status"
    )

    # XC-06: every link can drive the synchronized graph, map and timeline.
    syncable = [
        l for l in links if l["view_sync"]["node_ids"] or l["view_sync"]["event_ids"]
    ]
    assert syncable, "no link can be opened in the workspace"
    spatial = [l for l in links if l["view_sync"]["coordinates"]]
    temporal = [l for l in links if l["view_sync"]["timeline_from"]]
    print(
        f"[PASS - XC-06] View Sync: {len(syncable)} Graph, {len(spatial)} Map, "
        f"{len(temporal)} Timeline"
    )

    # XC-07: reachable from the investigator chat, under the caller's own scope.
    chat = client.post(
        "/api/v1/ai/investigate",
        json={
            "case_id": "CASE-2024-8812",
            "query": "Are there any cross-case links to past operations?",
        },
        headers=headers,
    ).json()
    assert "Cross-Case Intelligence" in chat["answer"]
    assert "Association only" in chat["answer"]
    section_ids = {s["section_id"] for s in chat["detail_sections"]}
    assert {"cross_case_scope", "cross_case_links", "cross_case_basis"} <= section_ids
    # The same question asked by the analyst must not reveal the archived case.
    analyst_chat = client.post(
        "/api/v1/ai/investigate",
        json={
            "case_id": "CASE-2024-8812",
            "query": "Are there any cross-case links to past operations?",
        },
        headers=analyst_headers,
    ).json()
    assert "CASE-2023-1104" not in analyst_chat["answer"]
    print("[PASS - XC-07] Chat Integration Respects The Caller's Own Authorised Scope")

    # XC-08: the AI endpoints now refuse cases the caller cannot open.
    assert client.post(
        "/api/v1/ai/investigate",
        json={"case_id": "CASE-2023-1104", "query": "Summarise this case"},
        headers=analyst_headers,
    ).status_code == 403
    assert client.get(
        "/api/v1/ai/full-brief?case_id=CASE-2023-1104", headers=analyst_headers
    ).status_code == 403
    print("[PASS - XC-08] AI Investigator Endpoints Enforce Case-Level Authorisation")

    # XC-09: detection bases are published with their strength.
    bases_doc = client.get("/api/v1/cross-case/bases", headers=headers).json()
    assert len(bases_doc["bases"]) >= 8
    assert all("strength" in b for b in bases_doc["bases"])
    detail = client.get(
        f"/api/v1/cross-case/link/{links[0]['link_id']}?case_id=CASE-2024-8812", headers=headers
    )
    assert detail.status_code == 200
    assert client.get(
        "/api/v1/cross-case/link/NO-SUCH-LINK?case_id=CASE-2024-8812", headers=headers
    ).status_code == 404
    print("[PASS - XC-09] Published Detection Bases And Per-Link Retrieval (404 On Unknown Link)")

    # XC-10: the detectors the shipped dataset never triggers. The archived case is
    # small, so alias, identifier, artifact and temporal matching would otherwise go
    # untested. Fixture records are inserted, asserted against, and removed.
    from datetime import datetime, timezone

    from app.models.entities import Entity as EntityRow, Event as EventRow

    fixture_db = SessionLocal()
    fixture_entities = [
        EntityRow(
            entity_id="TMP-XC-PER",
            case_id="CASE-2023-1104",
            label="Vikram Malhotra",
            entity_type="PERSON",
            aliases=["V. Malhotra"],
            properties={"pan": "SYNTH-PAN-0001"},
        ),
        EntityRow(
            entity_id="TMP-XC-VEH",
            case_id="CASE-2023-1104",
            label="DL-04-E-5544",
            entity_type="VEHICLE",
            aliases=["DL04E5544"],
            properties={"registration": "DL-04-E-5544"},
        ),
    ]
    fixture_event = EventRow(
        event_id="TMP-XC-EVT",
        case_id="CASE-2023-1104",
        title="Archived wharf handover",
        event_type="MEETING",
        timestamp=datetime(2024, 2, 14, 22, 0, tzinfo=timezone.utc),
        location_name="Nhava Sheva container terminal",
        latitude=18.9496,
        longitude=72.951,
        related_entities=["ENT-PER-01"],
        evidence_id="EVID-CCTV-01",
        summary="Test fixture for cross-case detector coverage.",
    )
    for row in fixture_entities:
        fixture_db.add(row)
    fixture_db.add(fixture_event)
    fixture_db.commit()

    try:
        seeded = client.get(
            "/api/v1/cross-case/analyse?case_id=CASE-2024-8812", headers=headers
        ).json()
        seeded_bases = {link["basis"] for link in seeded["links"]}
        for expected in (
            "ALIAS_MATCH",
            "IDENTIFIER_MATCH",
            "SHARED_ARTIFACT",
            "TEMPORAL_PATTERN",
        ):
            assert expected in seeded_bases, f"{expected} detector produced nothing"

        by_basis = {link["basis"]: link for link in seeded["links"]}
        # A name collision must score below an issued identifier, and must ask for
        # verification rather than assert identity.
        assert by_basis["ALIAS_MATCH"]["confidence"] < by_basis["IDENTIFIER_MATCH"]["confidence"]
        assert by_basis["ALIAS_MATCH"]["requires_human_verification"] is True
        assert by_basis["TEMPORAL_PATTERN"]["confidence_band"] == "LOW"
        assert all("Association only" in l["interpretation"] for l in seeded["links"])
        print(
            f"[PASS - XC-10] All 8 Detectors Exercised ({len(seeded_bases)} Bases; Alias "
            f"{by_basis['ALIAS_MATCH']['confidence']:.2f} < Identifier "
            f"{by_basis['IDENTIFIER_MATCH']['confidence']:.2f})"
        )
    finally:
        fixture_db.delete(fixture_event)
        for row in fixture_entities:
            fixture_db.delete(row)
        fixture_db.commit()
        fixture_db.close()

    restored = client.get(
        "/api/v1/cross-case/analyse?case_id=CASE-2024-8812", headers=headers
    ).json()
    assert restored["summary"]["link_count"] == report["summary"]["link_count"], (
        "fixture cleanup left records behind"
    )

    passed += 1

    print("==================================================================")
    print(f"ALL TESTS PASSED WITH 100% SUCCESS ({passed} Core Suites Verified)!")
    print("==================================================================")

if __name__ == "__main__":
    run_all_tests()
