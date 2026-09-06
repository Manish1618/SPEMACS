"""Loads the synthetic dataset into the database and rebuilds the knowledge graph.

The previous seeder declared entities and relationships as literal Python calls in
this module, which meant nothing was queryable and the seed was not idempotent
(it looked for evidence ids it never created, so it duplicated every evidence row
on each restart). Everything is now read from data/synthetic and written to real
tables, and every write is an upsert keyed on a stable id.

The graph is projected from those tables, so the database is the single source of
truth and NetworkX is only an analysis index over it.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.entities import (
    Case,
    Document,
    Entity,
    Event,
    Hypothesis,
    OsintRecord,
    Relationship,
    User,
)
from app.services.evidence import calculate_sha256, register_evidence
from app.services.graph_engine import knowledge_graph

SYNTHETIC_DIR = settings.DATA_DIR / "synthetic"

DEFAULT_USERS = [
    {
        "username": "admin",
        "email": "admin@spemass.example",
        "full_name": "Chief Investigator R. Verma",
        "password": "admin123",
        "role": "ADMIN",
        "badge_number": "SYNTH-001",
    },
    {
        "username": "rajiv_sen",
        "email": "rajiv.sen@spemass.example",
        "full_name": "Inspector Rajiv Sen",
        "password": "investigator123",
        "role": "LEAD_INVESTIGATOR",
        "badge_number": "SYNTH-884",
    },
    {
        "username": "ananya_rao",
        "email": "ananya.rao@spemass.example",
        "full_name": "Analyst Ananya Rao",
        "password": "analyst123",
        "role": "ANALYST",
        "badge_number": "SYNTH-231",
    },
    {
        "username": "auditor",
        "email": "auditor@spemass.example",
        "full_name": "Integrity Auditor",
        "password": "auditor123",
        "role": "AUDITOR",
        "badge_number": "SYNTH-900",
    },
]

# Which case each auditless user may reach. The auditor sees integrity records
# across cases; the analyst is scoped to the active case only.
USER_CASE_ACCESS = {
    "admin": ["CASE-2024-8812", "CASE-2023-1104"],
    "rajiv_sen": ["CASE-2024-8812", "CASE-2023-1104"],
    "ananya_rao": ["CASE-2024-8812"],
    "auditor": ["CASE-2024-8812", "CASE-2023-1104"],
}


def _load(name: str) -> List[Dict[str, Any]]:
    path = SYNTHETIC_DIR / name
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _seed_users(db: Session) -> None:
    for spec in DEFAULT_USERS:
        user = db.query(User).filter(User.username == spec["username"]).first()
        if user is None:
            db.add(
                User(
                    username=spec["username"],
                    email=spec["email"],
                    full_name=spec["full_name"],
                    hashed_password=get_password_hash(spec["password"]),
                    role=spec["role"],
                    badge_number=spec["badge_number"],
                )
            )
    db.commit()


def _seed_cases(db: Session) -> None:
    for spec in _load("cases.json"):
        case = db.query(Case).filter(Case.case_id == spec["case_id"]).first()
        if case is None:
            case = Case(case_id=spec["case_id"], created_at=_parse_dt(spec.get("created_at")))
            db.add(case)
        case.title = spec["title"]
        case.description = spec.get("description")
        case.status = spec.get("status", "ACTIVE")
        case.classification = spec.get("classification", "RESTRICTED")
        case.lead_investigator = spec["lead_investigator"]
        case.assigned_team = [
            username
            for username, cases in USER_CASE_ACCESS.items()
            if spec["case_id"] in cases
        ]
    db.commit()


def _seed_entities(db: Session) -> None:
    for spec in _load("entities.json"):
        entity = db.query(Entity).filter(Entity.entity_id == spec["entity_id"]).first()
        if entity is None:
            entity = Entity(entity_id=spec["entity_id"])
            db.add(entity)
        entity.case_id = spec["case_id"]
        entity.label = spec["label"]
        entity.entity_type = spec["entity_type"]
        entity.aliases = spec.get("aliases", [])
        entity.properties = spec.get("properties", {})
        entity.latitude = spec.get("latitude")
        entity.longitude = spec.get("longitude")
    db.commit()


def _seed_relationships(db: Session) -> None:
    for spec in _load("relationships.json"):
        rel = db.query(Relationship).filter(Relationship.rel_id == spec["rel_id"]).first()
        if rel is None:
            rel = Relationship(rel_id=spec["rel_id"])
            db.add(rel)
        rel.case_id = spec["case_id"]
        rel.source_id = spec["source_id"]
        rel.target_id = spec["target_id"]
        rel.rel_type = spec["rel_type"]
        rel.confidence = spec.get("confidence", 1.0)
        rel.assertion_kind = spec.get("assertion_kind", "OBSERVED")
        rel.evidence_ids = spec.get("evidence_ids", [])
        rel.valid_from = _parse_dt(spec.get("valid_from"))
        rel.properties = spec.get("properties", {})
    db.commit()


def _seed_events(db: Session) -> None:
    for spec in _load("events.json"):
        event = db.query(Event).filter(Event.event_id == spec["event_id"]).first()
        if event is None:
            event = Event(event_id=spec["event_id"])
            db.add(event)
        event.case_id = spec["case_id"]
        event.title = spec["title"]
        event.event_type = spec["event_type"]
        event.timestamp = _parse_dt(spec["timestamp"])
        event.location_name = spec.get("location_name")
        event.latitude = spec.get("latitude")
        event.longitude = spec.get("longitude")
        event.related_entities = spec.get("related_entities", [])
        event.evidence_id = spec.get("evidence_id")
        event.summary = spec.get("summary", "")
        event.confidence = spec.get("confidence", 1.0)
        event.properties = spec.get("properties", {})
    db.commit()


def _seed_documents_and_evidence(db: Session) -> None:
    """Register documents, then the derived-record evidence the events cite.

    Evidence content is written to disk so integrity verification rehashes a real
    artifact rather than the string it was just handed.
    """
    for spec in _load("documents.json"):
        text = spec["extracted_text"]
        content = text.encode("utf-8")
        doc = db.query(Document).filter(Document.document_id == spec["document_id"]).first()
        if doc is None:
            doc = Document(document_id=spec["document_id"], created_at=_parse_dt(spec.get("created_at")))
            db.add(doc)
        doc.case_id = spec["case_id"]
        doc.filename = spec["filename"]
        doc.title = spec["title"]
        doc.file_type = spec["file_type"]
        doc.storage_path = f"storage/documents/{spec['filename']}"
        doc.sha256_hash = calculate_sha256(content)
        doc.extracted_text = text
        doc.parsed_metadata = {"evidence_id": spec["evidence_id"]}
        doc.uploaded_by = spec["uploaded_by"]
        db.commit()

        doc_dir = settings.STORAGE_DIR / "documents"
        doc_dir.mkdir(parents=True, exist_ok=True)
        (doc_dir / spec["filename"]).write_bytes(content)

        register_evidence(
            db=db,
            evidence_id=spec["evidence_id"],
            case_id=spec["case_id"],
            title=spec["title"],
            evidence_type=spec["file_type"],
            content_bytes=content,
            document_id=spec["document_id"],
            performed_by=spec["uploaded_by"],
            metadata={"source": "case document"},
        )

    # Derived-record evidence. The artifact is the actual record listing built
    # from the events that cite it, so the hash covers real content.
    derived = [
        ("EVID-CDR-01", "CASE-2024-8812", "Call detail records, Delhi NCR cluster", "CDR_EXTRACT"),
        ("EVID-BANK-01", "CASE-2024-8812", "Bank ledger extract, February 2024", "BANK_EXTRACT"),
        ("EVID-BANK-02", "CASE-2024-8812", "Bank ledger extract, supplementary transfers", "BANK_EXTRACT"),
        ("EVID-TOLL-01", "CASE-2024-8812", "Number plate reader logs, Kherki Daula", "ANPR_EXTRACT"),
        ("EVID-CDR-ARCHIVE-01", "CASE-2023-1104", "Archived call detail records, Nhava Sheva", "CDR_EXTRACT"),
    ]

    for evidence_id, case_id, title, evidence_type in derived:
        rows = (
            db.query(Event)
            .filter(Event.evidence_id == evidence_id)
            .order_by(Event.timestamp.asc())
            .all()
        )
        lines = [title.upper(), f"Records: {len(rows)}", ""]
        for row in rows:
            props = " ".join(f"{k}={v}" for k, v in sorted((row.properties or {}).items()))
            lines.append(
                f"{row.event_id} | {row.timestamp.isoformat()} | {row.title} | "
                f"{row.location_name or '-'} | {props}"
            )
        content = ("\n".join(lines) + "\n").encode("utf-8")

        register_evidence(
            db=db,
            evidence_id=evidence_id,
            case_id=case_id,
            title=title,
            evidence_type=evidence_type,
            content_bytes=content,
            performed_by="records_desk",
            metadata={"record_count": len(rows), "source": "records extract"},
        )


def _seed_osint(db: Session) -> None:
    for spec in _load("osint_records.json"):
        record = (
            db.query(OsintRecord).filter(OsintRecord.record_id == spec["record_id"]).first()
        )
        if record is None:
            record = OsintRecord(record_id=spec["record_id"])
            db.add(record)
        record.case_id = spec["case_id"]
        record.entity_id = spec.get("entity_id")
        record.query_term = spec["query_term"]
        record.source_name = spec["source_name"]
        record.source_url = spec["source_url"]
        record.source_type = spec.get("source_type", "NEWS")
        record.published_at = _parse_dt(spec.get("published_at"))
        record.reliability = spec.get("reliability", 0.5)
        record.confidence = spec.get("confidence", 0.5)
        record.claims = spec.get("claims", [])
        # The hash of the claim text is what lets duplicate reporting be detected.
        record.content_hash = calculate_sha256(
            "\n".join(spec.get("claims", [])).encode("utf-8")
        )
        record.origin_record_id = spec.get("origin_record_id")
        record.is_derivative = bool(spec.get("origin_record_id"))
        record.requires_human_verification = spec.get("requires_human_verification", True)
    db.commit()

    # Public-source material is evidence too, and citations to it must resolve.
    # Each originating source is sealed as its own artifact so a claim drawn from
    # it can be traced back and re-verified like any other exhibit.
    originals = [r for r in db.query(OsintRecord).all() if not r.is_derivative]
    for record in originals:
        evidence_id = f"EVID-OSINT-{record.record_id.split('-')[-1]}"
        derivatives = (
            db.query(OsintRecord)
            .filter(OsintRecord.origin_record_id == record.record_id)
            .all()
        )
        lines = [
            f"PUBLIC SOURCE RECORD {record.record_id}",
            f"Source: {record.source_name}",
            f"Reference: {record.source_url}",
            f"Source type: {record.source_type}",
            f"Published: {record.published_at.isoformat() if record.published_at else 'not stated'}",
            f"Assessed reliability: {record.reliability}",
            f"Reported by {len(derivatives)} further outlets carrying the same text.",
            "",
            "Extracted claims:",
        ]
        lines += [f"  - {claim}" for claim in (record.claims or [])]
        if record.requires_human_verification:
            lines += ["", "Potential external match. Human verification required."]

        content = ("\n".join(lines) + "\n").encode("utf-8")
        register_evidence(
            db=db,
            evidence_id=evidence_id,
            case_id=record.case_id,
            title=f"Public source: {record.source_name}",
            evidence_type="OSINT_RECORD",
            content_bytes=content,
            performed_by="osint_collection",
            metadata={
                "osint_record_id": record.record_id,
                "source_url": record.source_url,
                "derivative_count": len(derivatives),
            },
        )
        record.evidence_id = evidence_id
    db.commit()


def _seed_hypotheses(db: Session) -> None:
    """Two opposed starting hypotheses, so the counter-evidence engine has
    something to argue against from the first minute of a demo."""
    seeds = [
        {
            "hypothesis_id": "HYP-01",
            "case_id": "CASE-2024-8812",
            "title": "The Zurich remittance was connected to the Aerocity meeting",
            "statement": (
                "The transfer of USD 250,000 to Alpine Holdings AG on 15 February 2024 was "
                "arranged at the meeting recorded at Aerocity on 14 February 2024."
            ),
            "status": "UNDER_REVIEW",
            "created_by": "rajiv_sen",
        },
        {
            "hypothesis_id": "HYP-02",
            "case_id": "CASE-2024-8812",
            "title": "The Zurich remittance was an ordinary commercial payment",
            "statement": (
                "The transfer of USD 250,000 was an advance payment for equipment procurement, "
                "unconnected to the meeting of 14 February 2024."
            ),
            "status": "OPEN",
            "created_by": "rajiv_sen",
        },
    ]
    for spec in seeds:
        row = db.query(Hypothesis).filter(Hypothesis.hypothesis_id == spec["hypothesis_id"]).first()
        if row is None:
            db.add(Hypothesis(**spec))
    db.commit()


def rebuild_graph(db: Session) -> Dict[str, int]:
    """Project the persisted entities and relationships into the NetworkX index."""
    knowledge_graph.clear()

    entities = db.query(Entity).all()
    for entity in entities:
        props = dict(entity.properties or {})
        props["aliases"] = entity.aliases or []
        if entity.latitude is not None:
            props["latitude"] = entity.latitude
            props["longitude"] = entity.longitude
        knowledge_graph.add_entity(
            entity_id=entity.entity_id,
            label=entity.label,
            entity_type=entity.entity_type,
            case_id=entity.case_id,
            properties=props,
        )

    relationships = db.query(Relationship).all()
    known = {e.entity_id for e in entities}
    for rel in relationships:
        if rel.source_id not in known or rel.target_id not in known:
            continue
        knowledge_graph.add_relationship(
            rel_id=rel.rel_id,
            source_id=rel.source_id,
            target_id=rel.target_id,
            rel_type=rel.rel_type,
            case_id=rel.case_id,
            confidence=rel.confidence or 1.0,
            evidence_ids=rel.evidence_ids or [],
            properties={
                "assertion_kind": rel.assertion_kind,
                "valid_from": rel.valid_from.isoformat() if rel.valid_from else None,
                **(rel.properties or {}),
            },
        )

    return {"entities": len(entities), "relationships": len(relationships)}


def seed_database_and_graph(db: Session) -> Dict[str, Any]:
    # The synthetic investigator accounts carry published passwords, so they exist
    # only in demo mode. A real deployment provisions its first administrator with
    # backend/create_admin.py and everyone else through the /users API.
    if settings.DEMO_MODE:
        _seed_users(db)
    _seed_cases(db)
    _seed_entities(db)
    _seed_relationships(db)
    _seed_events(db)
    _seed_documents_and_evidence(db)
    _seed_osint(db)
    _seed_hypotheses(db)
    counts = rebuild_graph(db)

    summary = {
        "entities": counts["entities"],
        "relationships": counts["relationships"],
        "events": db.query(Event).count(),
        "documents": db.query(Document).count(),
        "osint_records": db.query(OsintRecord).count(),
        "seeded_at": datetime.now(timezone.utc).isoformat(),
    }
    print(
        f">> SPEMASS dataset loaded: {summary['entities']} entities, "
        f"{summary['relationships']} relationships, {summary['events']} events, "
        f"{summary['documents']} documents."
    )
    return summary
