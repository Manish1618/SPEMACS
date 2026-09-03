import json
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.entities import Case, Document, Evidence, CustodyEvent, BlockchainRecord, User
from app.core.security import get_password_hash
from app.services.evidence import create_evidence_record, calculate_sha256
from app.services.graph_engine import knowledge_graph

def seed_database_and_graph(db: Session):
    # 1. Create Default Admin & Investigator Users
    if db.query(User).count() == 0:
        admin_user = User(
            username="admin",
            email="admin@spemass.gov",
            full_name="Chief Investigator Rajesh Verma",
            hashed_password=get_password_hash("admin123"),
            role="ADMIN",
            badge_number="IND-EOW-001"
        )
        inv_user = User(
            username="rajiv_sen",
            email="rajiv.sen@spemass.gov",
            full_name="Inspector Rajiv Sen",
            hashed_password=get_password_hash("investigator123"),
            role="LEAD_INVESTIGATOR",
            badge_number="IND-EOW-884"
        )
        db.add_all([admin_user, inv_user])
        db.commit()

    # 2. Ingest Cases
    cases_file = settings.DATA_DIR / "synthetic" / "cases.json"
    if cases_file.exists():
        with open(cases_file, "r", encoding="utf-8") as f:
            cases_data = json.load(f)
            for c in cases_data:
                existing = db.query(Case).filter(Case.case_id == c["case_id"]).first()
                if not existing:
                    new_case = Case(
                        case_id=c["case_id"],
                        title=c["title"],
                        description=c["description"],
                        status=c["status"],
                        classification=c["classification"],
                        lead_investigator=c["lead_investigator"],
                        assigned_team=["rajiv_sen", "admin"],
                        created_at=datetime.fromisoformat(c["created_at"].replace("Z", "+00:00"))
                    )
                    db.add(new_case)
            db.commit()

    # Clear and rebuild graph
    knowledge_graph.clear()
    
    # Add Core Case Nodes to Graph
    knowledge_graph.add_entity("CASE-2024-8812", "Operation ShadowNet (2024)", "Case", "CASE-2024-8812")
    knowledge_graph.add_entity("CASE-2023-1104", "Operation Golden Falcon (2023)", "Case", "CASE-2023-1104")

    # 3. Ingest Documents & Scanned Evidence
    fir_file = settings.DATA_DIR / "synthetic" / "fir_records.json"
    if fir_file.exists():
        with open(fir_file, "r", encoding="utf-8") as f:
            docs_data = json.load(f)
            for d in docs_data:
                existing_doc = db.query(Document).filter(Document.document_id == d["document_id"]).first()
                content_bytes = d["extracted_text"].encode("utf-8")
                file_hash = calculate_sha256(content_bytes)
                
                if not existing_doc:
                    doc = Document(
                        document_id=d["document_id"],
                        case_id=d["case_id"],
                        filename=d["filename"],
                        title=d["title"],
                        file_type=d["file_type"],
                        storage_path=f"storage/{d['filename']}",
                        sha256_hash=file_hash,
                        extracted_text=d["extracted_text"],
                        uploaded_by=d["uploaded_by"],
                        created_at=datetime.fromisoformat(d["created_at"].replace("Z", "+00:00"))
                    )
                    db.add(doc)
                    db.commit()
                    
                    # Create Evidence & Blockchain Link
                    create_evidence_record(
                        db=db,
                        case_id=d["case_id"],
                        title=d["title"],
                        evidence_type="DOC_SCAN",
                        content_bytes=content_bytes,
                        document_id=d["document_id"],
                        performed_by=d["uploaded_by"]
                    )

    # 4. Add Canonical Entities to Knowledge Graph
    # Persons
    knowledge_graph.add_entity(
        "ENT-PER-01", "Vikram Malhotra", "Person", "CASE-2024-8812",
        {"aliases": ["Vicky", "V. Malhotra"], "role": "Syndicate Head / Director", "phone": "+919811022331", "pan": "ABCDE1234F"}
    )
    knowledge_graph.add_entity(
        "ENT-PER-02", "Amit Shahani", "Person", "CASE-2024-8812",
        {"aliases": ["AS", "Amit S."], "role": "Finance Director", "phone": "+919822033442", "pan": "FGHIJ5678K"}
    )
    knowledge_graph.add_entity(
        "ENT-PER-03", "Rahul Sharma", "Person", "CASE-2024-8812",
        {"aliases": ["Rahul S."], "role": "Courier & Transport", "phone": "+919871144553"}
    )
    knowledge_graph.add_entity(
        "ENT-PER-04", "Rahul Verma", "Person", "CASE-2024-8812",
        {"aliases": ["R. Verma"], "role": "Telecom Associate", "phone": "+919810077889"}
    )
    knowledge_graph.add_entity(
        "ENT-PER-05", "Karan Mehra", "Person", "CASE-2024-8812",
        {"aliases": ["Karan"], "role": "Driver (Zenith Holdings)", "phone": "+919811099882"}
    )

    # Phones
    knowledge_graph.add_entity("ENT-PH-01", "+91 98110 22331", "Phone", "CASE-2024-8812", {"carrier": "Airtel Delhi", "owner": "Vikram Malhotra"})
    knowledge_graph.add_entity("ENT-PH-02", "+91 98220 33442", "Phone", "CASE-2024-8812", {"carrier": "Vodafone Delhi", "owner": "Amit Shahani"})
    knowledge_graph.add_entity("ENT-PH-03", "+91 98711 44553", "Phone", "CASE-2024-8812", {"carrier": "Jio Delhi", "owner": "Rahul Sharma"})

    # Vehicles
    knowledge_graph.add_entity("ENT-VEH-01", "DL-04-E-5544", "Vehicle", "CASE-2024-8812", {"model": "Toyota Fortuner (Black)", "owner": "Zenith Holdings"})
    knowledge_graph.add_entity("ENT-VEH-02", "MH-02-CP-8811", "Vehicle", "CASE-2024-8812", {"model": "Mercedes E-Class", "owner": "Apex Global Logistics"})

    # Organizations
    knowledge_graph.add_entity("ENT-ORG-01", "Zenith Holdings Pvt Ltd", "Organization", "CASE-2024-8812", {"jurisdiction": "New Delhi, India", "type": "Shell Company"})
    knowledge_graph.add_entity("ENT-ORG-02", "Apex Global Logistics", "Organization", "CASE-2024-8812", {"jurisdiction": "Mumbai / Delhi", "type": "Logistics & Freight"})
    knowledge_graph.add_entity("ENT-ORG-03", "Alpine Holdings AG", "Organization", "CASE-2024-8812", {"jurisdiction": "Zurich, Switzerland", "type": "Offshore Holding"})

    # Accounts
    knowledge_graph.add_entity("ENT-ACC-01", "Account #10110 (Zenith)", "Account", "CASE-2024-8812", {"bank": "Metro National Bank", "currency": "INR/USD"})
    knowledge_graph.add_entity("ENT-ACC-02", "Account #99218 (Apex)", "Account", "CASE-2024-8812", {"bank": "Metro National Bank", "currency": "USD"})
    knowledge_graph.add_entity("ENT-ACC-03", "Account #SWISS-77 (Alpine)", "Account", "CASE-2024-8812", {"bank": "Banque Cantonale de Genève", "currency": "USD"})

    # Locations
    knowledge_graph.add_entity("ENT-LOC-01", "Hotel Grand Palace Aerocity", "Location", "CASE-2024-8812", {"latitude": 28.5504, "longitude": 77.1210})
    knowledge_graph.add_entity("ENT-LOC-02", "Connaught Place Head Office", "Location", "CASE-2024-8812", {"latitude": 28.6315, "longitude": 77.2167})
    knowledge_graph.add_entity("ENT-LOC-03", "Nhava Sheva Port Mumbai", "Location", "CASE-2024-8812", {"latitude": 18.9496, "longitude": 72.9510})
    knowledge_graph.add_entity("ENT-LOC-04", "Kherki Daula Toll Plaza", "Location", "CASE-2024-8812", {"latitude": 28.4032, "longitude": 76.9930})

    # Add Relationships
    # Person -> Organization / Account / Vehicle / Phone
    knowledge_graph.add_relationship("R-01", "ENT-PER-01", "ENT-ORG-01", "WORKS_FOR", "CASE-2024-8812", 0.98, ["EVID-DOC-01"])
    knowledge_graph.add_relationship("R-02", "ENT-PER-02", "ENT-ORG-02", "WORKS_FOR", "CASE-2024-8812", 0.98, ["EVID-DOC-01"])
    knowledge_graph.add_relationship("R-03", "ENT-PER-01", "ENT-PH-01", "USED", "CASE-2024-8812", 0.99, ["EVID-CDR-01"])
    knowledge_graph.add_relationship("R-04", "ENT-PER-02", "ENT-PH-02", "USED", "CASE-2024-8812", 0.99, ["EVID-CDR-01"])
    knowledge_graph.add_relationship("R-05", "ENT-PER-01", "ENT-VEH-01", "USED", "CASE-2024-8812", 0.95, ["EVID-TOLL-01", "EVID-CCTV-01"])
    knowledge_graph.add_relationship("R-06", "ENT-PER-01", "ENT-PER-02", "ASSOCIATED_WITH", "CASE-2024-8812", 0.94, ["EVID-CCTV-01", "EVID-CDR-01"])
    knowledge_graph.add_relationship("R-07", "ENT-PER-02", "ENT-PER-03", "COMMUNICATED_WITH", "CASE-2024-8812", 0.92, ["EVID-CDR-01"])
    knowledge_graph.add_relationship("R-08", "ENT-PER-03", "ENT-PER-04", "COMMUNICATED_WITH", "CASE-2024-8812", 0.85, ["EVID-CDR-01"])
    
    # Financial Flow
    knowledge_graph.add_relationship("R-09", "ENT-ORG-01", "ENT-ACC-01", "CONTROLS", "CASE-2024-8812", 0.99, ["EVID-BANK-01"])
    knowledge_graph.add_relationship("R-10", "ENT-ORG-02", "ENT-ACC-02", "CONTROLS", "CASE-2024-8812", 0.99, ["EVID-BANK-01"])
    knowledge_graph.add_relationship("R-11", "ENT-ACC-01", "ENT-ACC-02", "TRANSFERRED_FUNDS", "CASE-2024-8812", 0.99, ["EVID-BANK-01"], {"amount": "$50,000 USD", "date": "2024-02-11"})
    knowledge_graph.add_relationship("R-12", "ENT-ACC-02", "ENT-ACC-03", "TRANSFERRED_FUNDS", "CASE-2024-8812", 0.99, ["EVID-BANK-01"], {"amount": "$250,000 USD", "date": "2024-02-15"})
    knowledge_graph.add_relationship("R-13", "ENT-ACC-03", "ENT-ORG-03", "OWNED_BY", "CASE-2024-8812", 0.95, ["EVID-BANK-01"])

    # Cross-Case Connections
    knowledge_graph.add_relationship("R-14", "ENT-PER-01", "CASE-2024-8812", "INVOLVED_IN", "CASE-2024-8812", 1.0)
    knowledge_graph.add_relationship("R-15", "ENT-PER-01", "CASE-2023-1104", "INVOLVED_IN", "CASE-2023-1104", 1.0)
    knowledge_graph.add_relationship("R-16", "ENT-PER-01", "ENT-LOC-03", "RECORDED_AT", "CASE-2023-1104", 0.95, ["EVID-CDR-02"])

    # Add Ingested Tabular Records to Evidence Table if missing
    for ev_id, title, ev_type in [
        ("EVID-CDR-01", "Call Detail Records - Delhi / NCR Cluster", "CDR_TELEMETRY"),
        ("EVID-BANK-01", "Metro National Bank Transaction Ledger (Feb 2024)", "BANKING_LEDGER"),
        ("EVID-TOLL-01", "NHAI ANPR Highway Toll Camera Logs", "VEHICLE_SURVEILLANCE"),
        ("EVID-CCTV-01", "Hotel Grand Palace Aerocity CCTV Transcript", "CCTV_SURVEILLANCE"),
        ("EVID-CDR-02", "Archived Case 2023-1104 Mumbai Port CDRs", "HISTORICAL_RECORD")
    ]:
        existing_ev = db.query(Evidence).filter(Evidence.evidence_id == ev_id).first()
        if not existing_ev:
            create_evidence_record(
                db=db,
                case_id="CASE-2024-8812" if ev_id != "EVID-CDR-02" else "CASE-2023-1104",
                title=title,
                evidence_type=ev_type,
                content_bytes=f"{title}_{ev_id}_RAW_AUTHENTICATED_FORENSIC_STREAM".encode("utf-8"),
                performed_by="system_seeder"
            )

    print(">> Successfully seeded Database & Knowledge Graph with Operation ShadowNet dataset.")
