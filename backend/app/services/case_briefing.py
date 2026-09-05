"""Full-detail case briefing builder.

The Universal AI Investigator used to answer in a couple of paragraphs and push
everything else into side cards. This module assembles the *whole* picture out of
the real tables - entities, relationships, events, documents, evidence, custody,
OSINT and hypotheses - so the chat can print a complete investigative dossier
inline instead of a teaser.

Every number in a brief is counted from the database, never asserted, so a brief
stays honest when the dataset changes.
"""

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy.orm import Session

from app.models.entities import (
    Case,
    CustodyEvent,
    Document,
    Entity,
    Evidence,
    Event,
    Hypothesis,
    OsintRecord,
    Relationship,
)
from app.services.graph_engine import knowledge_graph

# A chat bubble can carry a lot, but not 205 events. Sections carry the first
# ROW_CAP rows plus a total so the UI can say what it is not showing.
ROW_CAP = 40
TIMELINE_CAP = 60

FINANCIAL_EVENT_TYPES = {"TRANSACTION", "TRANSFER", "PAYMENT", "REMITTANCE"}
COMMS_EVENT_TYPES = {"CALL", "SMS", "MESSAGE", "COMMUNICATION"}
MOVEMENT_EVENT_TYPES = {"VEHICLE_SIGHTING", "TOLL", "TOLL_CROSSING", "MEETING", "SIGHTING"}


def _fmt_dt(value: Optional[datetime]) -> str:
    if not value:
        return "—"
    if isinstance(value, str):
        return value
    return value.strftime("%Y-%m-%d %H:%M")


def _short_hash(value: Optional[str]) -> str:
    if not value:
        return "—"
    return f"{value[:12]}…{value[-6:]}" if len(value) > 20 else value


def _prop_summary(props: Optional[Dict[str, Any]], limit: int = 4) -> str:
    if not props:
        return "—"
    parts = []
    for key, val in props.items():
        if key in ("case_id", "entity_type", "label") or val in (None, "", [], {}):
            continue
        if isinstance(val, list):
            val = ", ".join(str(v) for v in val)
        elif isinstance(val, dict):
            val = str(val)
        parts.append(f"{key.replace('_', ' ')}: {val}")
        if len(parts) >= limit:
            break
    return " · ".join(parts) if parts else "—"


def _section(section_id: str, title: str, kind: str, **payload: Any) -> Dict[str, Any]:
    section: Dict[str, Any] = {"section_id": section_id, "title": title, "kind": kind}
    section.update({k: v for k, v in payload.items() if v is not None})
    return section


def _table(
    section_id: str,
    title: str,
    columns: Sequence[str],
    rows: Sequence[Sequence[Any]],
    summary: str = "",
    cap: int = ROW_CAP,
) -> Dict[str, Any]:
    normalised = [[("—" if cell is None else str(cell)) for cell in row] for row in rows]
    return _section(
        section_id,
        title,
        "table",
        summary=summary,
        columns=list(columns),
        rows=normalised[:cap],
        total_rows=len(normalised),
    )


class CaseBriefingService:
    """Builds full-detail briefs and per-entity dossiers from live case records."""

    # ---------------------------------------------------------------- loading

    def _load_case_records(self, db: Session, case_id: str) -> Dict[str, Any]:
        case = db.query(Case).filter(Case.case_id == case_id).first()
        entities = db.query(Entity).filter(Entity.case_id == case_id).all()
        relationships = db.query(Relationship).filter(Relationship.case_id == case_id).all()
        events = (
            db.query(Event)
            .filter(Event.case_id == case_id)
            .order_by(Event.timestamp.asc())
            .all()
        )
        documents = db.query(Document).filter(Document.case_id == case_id).all()
        evidence = db.query(Evidence).filter(Evidence.case_id == case_id).all()
        osint = db.query(OsintRecord).filter(OsintRecord.case_id == case_id).all()
        hypotheses = db.query(Hypothesis).filter(Hypothesis.case_id == case_id).all()

        evidence_ids = [e.evidence_id for e in evidence]
        custody: List[CustodyEvent] = []
        if evidence_ids:
            custody = (
                db.query(CustodyEvent)
                .filter(CustodyEvent.evidence_id.in_(evidence_ids))
                .all()
            )

        return {
            "case": case,
            "entities": entities,
            "relationships": relationships,
            "events": events,
            "documents": documents,
            "evidence": evidence,
            "osint": osint,
            "hypotheses": hypotheses,
            "custody": custody,
        }

    # ------------------------------------------------------------ full brief

    def build_full_brief(
        self,
        db: Session,
        case_id: str,
        focus_entity_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Assembles the complete case dossier: narrative plus every detail section."""
        data = self._load_case_records(db, case_id)
        case = data["case"]
        entities: List[Entity] = data["entities"]
        relationships: List[Relationship] = data["relationships"]
        events: List[Event] = data["events"]
        documents: List[Document] = data["documents"]
        evidence: List[Evidence] = data["evidence"]
        osint: List[OsintRecord] = data["osint"]
        hypotheses: List[Hypothesis] = data["hypotheses"]
        custody: List[CustodyEvent] = data["custody"]

        label_of = {e.entity_id: e.label for e in entities}
        by_type: Dict[str, List[Entity]] = defaultdict(list)
        for ent in entities:
            by_type[ent.entity_type].append(ent)

        analytics = self._graph_analytics(case_id, label_of)
        integrity = self._integrity_rollup(evidence, custody)

        sections: List[Optional[Dict[str, Any]]] = [
            self._section_overview(case, case_id, data, analytics, integrity),
            self._section_entities(by_type),
            self._section_relationships(relationships, label_of),
            self._section_timeline(events, label_of),
            self._section_financials(events, label_of),
            self._section_communications(events, label_of),
            self._section_movements(events, label_of),
            self._section_evidence(evidence, custody),
            self._section_documents(documents),
            self._section_network(analytics, by_type),
            self._section_osint(osint, label_of),
            self._section_hypotheses(hypotheses),
            self._section_gaps(data, integrity, analytics),
        ]
        resolved = [s for s in sections if s]

        dossiers = [
            d
            for d in (
                self.build_entity_dossier(db, case_id, entity_id, preloaded=data)
                for entity_id in (focus_entity_ids or [])[:3]
            )
            if d
        ]
        resolved[1:1] = dossiers

        narrative = self._narrative(case, case_id, data, analytics, integrity)
        if dossiers:
            named = ", ".join(d["title"].split("— ", 1)[-1] for d in dossiers)
            narrative += (
                "\n\n## 6. Subjects you named\n"
                f"Full dossiers for **{named}** are attached at the top of the detail "
                "sections below - profile, every direct link, the complete activity log, "
                "and the evidence that references them."
            )

        return {
            "narrative": narrative,
            "sections": resolved,
            "stats": {
                "entities": len(entities),
                "relationships": len(relationships),
                "events": len(events),
                "documents": len(documents),
                "evidence": len(evidence),
                "osint_records": len(osint),
                "custody_events": len(custody),
                "hypotheses": len(hypotheses),
                "sections": len(resolved),
            },
            "citations": self._citations_from_evidence(evidence, documents),
            "integrity": integrity,
        }

    # -------------------------------------------------------- entity dossier

    def build_entity_dossier(
        self,
        db: Session,
        case_id: str,
        entity_id: str,
        preloaded: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Everything on file about a single subject, as one nested detail section."""
        data = preloaded or self._load_case_records(db, case_id)
        entities: List[Entity] = data["entities"]
        subject = next((e for e in entities if e.entity_id == entity_id), None)
        if subject is None:
            return None

        label_of = {e.entity_id: e.label for e in entities}
        rels = [
            r
            for r in data["relationships"]
            if r.source_id == entity_id or r.target_id == entity_id
        ]
        evts = [e for e in data["events"] if entity_id in (e.related_entities or [])]

        evidence_ids = {e.evidence_id for e in evts if e.evidence_id}
        for rel in rels:
            evidence_ids.update(rel.evidence_ids or [])
        linked_evidence = [e for e in data["evidence"] if e.evidence_id in evidence_ids]
        linked_osint = [o for o in data["osint"] if o.entity_id == entity_id]

        pairs = [
            ["Entity ID", subject.entity_id],
            ["Type", subject.entity_type],
            ["Aliases", ", ".join(subject.aliases or []) or "none recorded"],
            ["First seen", _fmt_dt(subject.first_seen)],
            [
                "Coordinates",
                f"{subject.latitude}, {subject.longitude}" if subject.latitude else "—",
            ],
            ["Linked relationships", str(len(rels))],
            ["Events involving subject", str(len(evts))],
            ["Evidence artifacts referencing subject", str(len(linked_evidence))],
            ["OSINT records", str(len(linked_osint))],
        ]
        for key, val in (subject.properties or {}).items():
            if key in ("case_id", "entity_type", "label") or val in (None, "", [], {}):
                continue
            if isinstance(val, list):
                val = ", ".join(str(v) for v in val)
            pairs.append([key.replace("_", " ").title(), str(val)])

        children = [
            _section("dossier_profile", "Profile", "keyvalue", pairs=pairs),
            _table(
                "dossier_links",
                "Direct links",
                ["Counterparty", "Relationship", "Direction", "Confidence", "Evidence"],
                [
                    [
                        label_of.get(
                            r.target_id if r.source_id == entity_id else r.source_id,
                            r.target_id if r.source_id == entity_id else r.source_id,
                        ),
                        r.rel_type,
                        "outbound" if r.source_id == entity_id else "inbound",
                        f"{r.confidence:.2f}" if r.confidence is not None else "—",
                        ", ".join(r.evidence_ids or []) or "—",
                    ]
                    for r in rels
                ],
                summary=f"{len(rels)} recorded links.",
            ),
            _table(
                "dossier_activity",
                "Activity log",
                ["When", "Event", "Type", "Location", "Evidence"],
                [
                    [
                        _fmt_dt(e.timestamp),
                        e.title,
                        e.event_type,
                        e.location_name or "—",
                        e.evidence_id or "—",
                    ]
                    for e in sorted(evts, key=lambda x: x.timestamp or datetime.min)
                ],
                summary=f"{len(evts)} events reference this subject.",
            ),
            _table(
                "dossier_evidence",
                "Evidence referencing subject",
                ["Evidence ID", "Title", "Type", "Integrity", "SHA-256"],
                [
                    [
                        e.evidence_id,
                        e.title,
                        e.evidence_type,
                        e.integrity_status,
                        _short_hash(e.sha256_hash),
                    ]
                    for e in linked_evidence
                ],
            ),
        ]
        if linked_osint:
            children.append(
                _table(
                    "dossier_osint",
                    "Open-source records",
                    ["Source", "Type", "Reliability", "Claim"],
                    [
                        [
                            o.source_name,
                            o.source_type,
                            f"{o.reliability:.2f}",
                            (o.claims or ["—"])[0],
                        ]
                        for o in linked_osint
                    ],
                )
            )

        same_label = [
            e for e in entities if e.label == subject.label and e.entity_id != entity_id
        ]
        if same_label:
            pairs.insert(
                3,
                [
                    "⚠️ Name collision",
                    "Another entity in this case carries the same label: "
                    + ", ".join(e.entity_id for e in same_label)
                    + ". Confirm which subject is meant before acting on this dossier.",
                ],
            )

        return _section(
            f"dossier_{entity_id}",
            f"Subject dossier — {subject.label} ({entity_id})",
            "group",
            summary=(
                f"{subject.entity_type.title()} · {len(rels)} links · {len(evts)} events · "
                f"{len(linked_evidence)} evidence artifacts"
            ),
            children=[c for c in children if c.get("rows") or c.get("pairs")],
        )

    # -------------------------------------------------------------- sections

    def _section_overview(
        self,
        case: Optional[Case],
        case_id: str,
        data: Dict[str, Any],
        analytics: Dict[str, Any],
        integrity: Dict[str, Any],
    ) -> Dict[str, Any]:
        stats = [
            {"label": "Entities", "value": len(data["entities"])},
            {"label": "Relationships", "value": len(data["relationships"])},
            {"label": "Events", "value": len(data["events"])},
            {"label": "Documents", "value": len(data["documents"])},
            {"label": "Evidence", "value": len(data["evidence"])},
            {"label": "Custody records", "value": len(data["custody"])},
            {"label": "OSINT records", "value": len(data["osint"])},
            {
                "label": "Integrity verified",
                "value": f"{integrity['verified']}/{integrity['total']}",
                "tone": "good" if integrity["tampered"] == 0 else "bad",
            },
        ]
        pairs = [
            ["Case ID", case_id],
            ["Title", case.title if case else "—"],
            ["Status", case.status if case else "—"],
            ["Classification", case.classification if case else "—"],
            ["Lead investigator", case.lead_investigator if case else "—"],
            ["Assigned team", ", ".join(case.assigned_team or []) if case else "—"],
            ["Opened", _fmt_dt(case.created_at) if case else "—"],
            ["Description", case.description if case and case.description else "—"],
            ["Network density", f"{analytics.get('density', 0):.3f}"],
        ]
        return _section(
            "case_overview",
            "Case overview",
            "stats",
            summary="Everything currently on file for this case, counted from the record store.",
            stats=stats,
            pairs=pairs,
        )

    def _section_entities(self, by_type: Dict[str, List[Entity]]) -> Dict[str, Any]:
        children = []
        for entity_type in sorted(by_type, key=lambda t: -len(by_type[t])):
            group = sorted(by_type[entity_type], key=lambda e: e.label)
            children.append(
                _table(
                    f"entities_{entity_type.lower()}",
                    f"{entity_type.title()} ({len(group)})",
                    ["ID", "Label", "Aliases", "Attributes"],
                    [
                        [
                            e.entity_id,
                            e.label,
                            ", ".join(e.aliases or []) or "—",
                            _prop_summary(e.properties),
                        ]
                        for e in group
                    ],
                )
            )
        total = sum(len(v) for v in by_type.values())
        return _section(
            "entity_roster",
            "Entity roster",
            "group",
            summary=f"{total} entities across {len(by_type)} types.",
            children=children,
        )

    def _section_relationships(
        self, relationships: List[Relationship], label_of: Dict[str, str]
    ) -> Dict[str, Any]:
        rows = [
            [
                label_of.get(r.source_id, r.source_id),
                r.rel_type,
                label_of.get(r.target_id, r.target_id),
                f"{r.confidence:.2f}" if r.confidence is not None else "—",
                r.assertion_kind or "—",
                _fmt_dt(r.valid_from),
                ", ".join(r.evidence_ids or []) or "—",
            ]
            for r in sorted(relationships, key=lambda r: r.rel_type)
        ]
        kinds = Counter(r.rel_type for r in relationships)
        summary = " · ".join(f"{k}: {v}" for k, v in kinds.most_common(6))
        return _table(
            "relationship_matrix",
            "Relationship matrix",
            [
                "Source",
                "Relationship",
                "Target",
                "Confidence",
                "Assertion",
                "Valid from",
                "Evidence",
            ],
            rows,
            summary=summary or "No relationships recorded.",
        )

    def _section_timeline(self, events: List[Event], label_of: Dict[str, str]) -> Dict[str, Any]:
        rows = [
            [
                _fmt_dt(e.timestamp),
                e.event_type,
                e.title,
                e.location_name or "—",
                ", ".join(label_of.get(x, x) for x in (e.related_entities or [])[:4]) or "—",
                e.evidence_id or "—",
            ]
            for e in events
        ]
        span = "—"
        if events:
            span = f"{_fmt_dt(events[0].timestamp)} → {_fmt_dt(events[-1].timestamp)}"
        return _table(
            "chronology",
            "Full chronology",
            ["When", "Type", "Event", "Location", "Parties", "Evidence"],
            rows,
            summary=f"{len(rows)} events spanning {span}.",
            cap=TIMELINE_CAP,
        )

    def _event_slice(
        self,
        events: List[Event],
        types: set,
        section_id: str,
        title: str,
        label_of: Dict[str, str],
        extra_props: Sequence[str] = (),
    ) -> Optional[Dict[str, Any]]:
        picked = [e for e in events if (e.event_type or "").upper() in types]
        if not picked:
            return None
        columns = (
            ["When", "Event", "Parties", "Location"]
            + [p.replace("_", " ").title() for p in extra_props]
            + ["Evidence"]
        )
        rows = []
        for e in picked:
            props = e.properties or {}
            rows.append(
                [
                    _fmt_dt(e.timestamp),
                    e.title,
                    ", ".join(label_of.get(x, x) for x in (e.related_entities or [])[:4]) or "—",
                    e.location_name or "—",
                    *[props.get(p, "—") for p in extra_props],
                    e.evidence_id or "—",
                ]
            )
        return _table(section_id, title, columns, rows, summary=f"{len(rows)} records.")

    def _section_financials(self, events, label_of) -> Optional[Dict[str, Any]]:
        return self._event_slice(
            events,
            FINANCIAL_EVENT_TYPES,
            "financial_trail",
            "Financial trail",
            label_of,
            extra_props=("amount", "currency", "direction"),
        )

    def _section_communications(self, events, label_of) -> Optional[Dict[str, Any]]:
        return self._event_slice(
            events,
            COMMS_EVENT_TYPES,
            "communications",
            "Communications analysis",
            label_of,
            extra_props=("duration_seconds", "cell_tower"),
        )

    def _section_movements(self, events, label_of) -> Optional[Dict[str, Any]]:
        return self._event_slice(
            events,
            MOVEMENT_EVENT_TYPES,
            "movements",
            "Movement, meetings & sightings",
            label_of,
            extra_props=("vehicle", "camera"),
        )

    def _section_evidence(
        self, evidence: List[Evidence], custody: List[CustodyEvent]
    ) -> Dict[str, Any]:
        custody_count = Counter(c.evidence_id for c in custody)
        rows = [
            [
                e.evidence_id,
                e.title,
                e.evidence_type,
                e.integrity_status,
                _short_hash(e.sha256_hash),
                e.blockchain_tx_id or "—",
                e.blockchain_block_num if e.blockchain_block_num is not None else "—",
                custody_count.get(e.evidence_id, 0),
            ]
            for e in evidence
        ]
        tampered = [e.evidence_id for e in evidence if e.integrity_status != "VERIFIED"]
        summary = f"{len(evidence)} artifacts, {len(custody)} custody records. " + (
            "All digests match their ledger anchors."
            if not tampered
            else f"Integrity alert on: {', '.join(tampered)}."
        )
        return _table(
            "evidence_register",
            "Evidence register & chain of custody",
            [
                "Evidence ID",
                "Title",
                "Type",
                "Integrity",
                "SHA-256",
                "Ledger tx",
                "Block",
                "Custody events",
            ],
            rows,
            summary=summary,
        )

    def _section_documents(self, documents: List[Document]) -> Dict[str, Any]:
        rows = [
            [
                d.document_id,
                d.title,
                d.file_type,
                d.uploaded_by,
                _fmt_dt(d.created_at),
                _short_hash(d.sha256_hash),
                f"{len(d.extracted_text or '')} chars",
            ]
            for d in documents
        ]
        return _table(
            "document_register",
            "Document register",
            ["Document ID", "Title", "Type", "Uploaded by", "Filed", "SHA-256", "Extracted text"],
            rows,
            summary=f"{len(rows)} source documents held for this case.",
        )

    def _section_network(
        self, analytics: Dict[str, Any], by_type: Dict[str, List[Entity]]
    ) -> Dict[str, Any]:
        pairs = [
            ["Nodes", analytics.get("total_nodes", 0)],
            ["Edges", analytics.get("total_edges", 0)],
            ["Density", f"{analytics.get('density', 0):.3f}"],
            ["Hub nodes", ", ".join(analytics.get("hubs", [])) or "none identified"],
            ["Structural bridges", ", ".join(analytics.get("bridges", [])) or "none identified"],
            ["Communities detected", analytics.get("communities", 0)],
            [
                "Composition",
                " · ".join(f"{t.title()}: {len(v)}" for t, v in sorted(by_type.items())),
            ],
        ]
        return _section(
            "network_analytics",
            "Network analytics",
            "keyvalue",
            summary="Centrality and structure computed over the case subgraph.",
            pairs=[[k, str(v)] for k, v in pairs],
        )

    def _section_osint(
        self, osint: List[OsintRecord], label_of: Dict[str, str]
    ) -> Optional[Dict[str, Any]]:
        if not osint:
            return None
        rows = [
            [
                o.source_name,
                o.source_type,
                label_of.get(o.entity_id, o.entity_id or "—"),
                f"{o.reliability:.2f}",
                "derivative" if o.is_derivative else "independent",
                "yes" if o.requires_human_verification else "no",
                (o.claims or ["—"])[0],
            ]
            for o in osint
        ]
        independent = sum(1 for o in osint if not o.is_derivative)
        return _table(
            "osint_register",
            "Open-source intelligence & source independence",
            [
                "Source",
                "Type",
                "Subject",
                "Reliability",
                "Independence",
                "Needs verification",
                "Lead claim",
            ],
            rows,
            summary=(
                f"{len(osint)} records: {independent} likely independent, "
                f"{len(osint) - independent} derivative replicas."
            ),
        )

    def _section_hypotheses(self, hypotheses: List[Hypothesis]) -> Optional[Dict[str, Any]]:
        if not hypotheses:
            return None
        return _table(
            "hypotheses",
            "Working hypotheses on file",
            ["ID", "Title", "Status", "Raised by", "Statement"],
            [[h.hypothesis_id, h.title, h.status, h.created_by, h.statement] for h in hypotheses],
            summary=f"{len(hypotheses)} hypotheses tracked for this case.",
        )

    def _section_gaps(
        self, data: Dict[str, Any], integrity: Dict[str, Any], analytics: Dict[str, Any]
    ) -> Dict[str, Any]:
        gaps: List[str] = []

        unsourced = [r.rel_type for r in data["relationships"] if not (r.evidence_ids or [])]
        if unsourced:
            gaps.append(
                f"{len(unsourced)} relationship(s) carry no evidence id and rest on inference: "
                f"{', '.join(sorted(set(unsourced))[:5])}."
            )

        inferred = [r for r in data["relationships"] if (r.assertion_kind or "") != "OBSERVED"]
        if inferred:
            gaps.append(
                f"{len(inferred)} relationship(s) are asserted rather than observed - "
                "confirm before relying on them in a filing."
            )

        no_evidence_events = [e for e in data["events"] if not e.evidence_id]
        if no_evidence_events:
            gaps.append(
                f"{len(no_evidence_events)} of {len(data['events'])} events have no evidence "
                "artifact attached."
            )

        if integrity["tampered"]:
            gaps.append(
                f"{integrity['tampered']} evidence artifact(s) failed digest verification and must "
                "be re-acquired before use."
            )

        needs_verification = [o for o in data["osint"] if o.requires_human_verification]
        if needs_verification:
            gaps.append(
                f"{len(needs_verification)} OSINT record(s) are flagged as potential matches "
                "requiring human verification; do not treat them as identity confirmations."
            )

        if not data["hypotheses"]:
            gaps.append("No competing hypothesis has been formally logged for this case.")

        if not gaps:
            gaps.append("No structural gaps detected in the current record set.")

        actions = [
            "Confirm each inferred relationship against a primary source before charging decisions.",
            "Request the custodian records for any evidence artifact with zero custody events.",
            "Re-run integrity verification after any export so the ledger reflects the access.",
        ]
        if analytics.get("bridges"):
            actions.insert(
                0,
                "Prioritise the structural bridge nodes ("
                + ", ".join(analytics["bridges"][:3])
                + ") - removing them fragments the network.",
            )

        return _section(
            "gaps_and_actions",
            "Evidence gaps & recommended actions",
            "list",
            summary="What the record set cannot currently support, and what to do about it.",
            items=[f"GAP · {g}" for g in gaps] + [f"ACTION · {a}" for a in actions],
        )

    # --------------------------------------------------------------- helpers

    def _graph_analytics(
        self, case_id: str, label_of: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Normalises the graph engine's raw output into brief-ready figures.

        compute_graph_analytics returns node ids and a node->community map; a brief
        needs human-readable names, counts, and a density figure.
        """
        label_of = label_of or {}
        try:
            raw = knowledge_graph.compute_graph_analytics(case_id) or {}
            subgraph = knowledge_graph.get_case_subgraph(case_id) or {}
        except Exception:
            return {
                "hubs": [],
                "bridges": [],
                "communities": 0,
                "total_nodes": 0,
                "total_edges": 0,
                "density": 0.0,
            }

        nodes = subgraph.get("nodes", [])
        edges = subgraph.get("edges", [])
        graph_labels = {n["id"]: n.get("label", n["id"]) for n in nodes}

        def name(node_id: str) -> str:
            return label_of.get(node_id) or graph_labels.get(node_id) or node_id

        node_count = len(nodes)
        edge_count = len(edges)
        possible = node_count * (node_count - 1) / 2
        communities = raw.get("communities", {})

        # The case node itself joins every entity, so it always tops centrality
        # without telling an investigator anything. Drop it from hubs and bridges.
        case_nodes = {n["id"] for n in nodes if n.get("entity_type") == "CASE"}

        def named(ids: List[str]) -> List[str]:
            return [name(n) for n in ids if n not in case_nodes]

        return {
            "hubs": named(raw.get("hubs", []))[:5],
            "bridges": named(raw.get("bridges", []))[:5],
            "communities": len(set(communities.values())) if isinstance(communities, dict) else 0,
            "total_nodes": node_count,
            "total_edges": edge_count,
            "density": round(edge_count / possible, 4) if possible else 0.0,
        }

    def _integrity_rollup(
        self, evidence: List[Evidence], custody: List[CustodyEvent]
    ) -> Dict[str, Any]:
        total = len(evidence)
        verified = sum(1 for e in evidence if e.integrity_status == "VERIFIED")
        return {
            "total": total,
            "verified": verified,
            "tampered": total - verified,
            "custody_events": len(custody),
            "tamper_flags": sum(1 for c in custody if c.tamper_detected),
        }

    def _citations_from_evidence(
        self, evidence: List[Evidence], documents: List[Document]
    ) -> List[Dict[str, Any]]:
        doc_by_id = {d.document_id: d for d in documents}
        citations = []
        for item in evidence[:8]:
            doc = doc_by_id.get(item.document_id) if item.document_id else None
            citations.append(
                {
                    "evidence_id": item.evidence_id,
                    "document_id": item.document_id,
                    "source_title": item.title,
                    "reference_location": (
                        f"{item.evidence_type} · digest {_short_hash(item.sha256_hash)}"
                    ),
                    "quote_or_claim": (
                        (doc.extracted_text or "")[:220].replace("\n", " ").strip() + "…"
                        if doc and doc.extracted_text
                        else (
                            f"Registered {item.evidence_type} artifact, "
                            f"integrity {item.integrity_status}."
                        )
                    ),
                    "confidence": 0.99 if item.integrity_status == "VERIFIED" else 0.4,
                }
            )
        return citations

    def _narrative(
        self,
        case: Optional[Case],
        case_id: str,
        data: Dict[str, Any],
        analytics: Dict[str, Any],
        integrity: Dict[str, Any],
    ) -> str:
        events: List[Event] = data["events"]
        entities: List[Entity] = data["entities"]
        label_of = {e.entity_id: e.label for e in entities}

        persons = [e.label for e in entities if e.entity_type == "PERSON"]
        orgs = [e.label for e in entities if e.entity_type == "ORGANIZATION"]
        accounts = [e.label for e in entities if e.entity_type == "ACCOUNT"]

        first_seen = _fmt_dt(events[0].timestamp) if events else "—"
        last_seen = _fmt_dt(events[-1].timestamp) if events else "—"
        type_counts = Counter(e.event_type for e in events)

        key_events = sorted(
            events,
            key=lambda e: (-(e.confidence or 0), e.timestamp or datetime.min),
        )[:6]

        lines = [
            f"# Full case brief — {case.title if case else case_id}",
            "",
            f"**{case_id}** · status **{case.status if case else 'UNKNOWN'}** · classification "
            f"**{case.classification if case else 'UNKNOWN'}** · lead "
            f"**{case.lead_investigator if case else 'unassigned'}**",
            "",
            (case.description or "") if case else "",
            "",
            "## 1. What the record set contains",
            f"- **{len(entities)} entities** ({len(persons)} persons, {len(orgs)} organisations, "
            f"{len(accounts)} accounts) joined by **{len(data['relationships'])} relationships**.",
            f"- **{len(events)} recorded events** between {first_seen} and {last_seen}: "
            + ", ".join(f"{count} {kind.lower()}" for kind, count in type_counts.most_common(5))
            + ".",
            f"- **{len(data['documents'])} source documents** and "
            f"**{len(data['evidence'])} evidence artifacts** under "
            f"**{integrity['custody_events']} custody records**.",
            f"- **{len(data['osint'])} open-source records** attached, of which "
            f"{sum(1 for o in data['osint'] if o.requires_human_verification)} still need "
            "human verification.",
            "",
            "## 2. Network shape",
            f"- Density **{analytics.get('density', 0):.3f}** across "
            f"{analytics.get('total_nodes', len(entities))} nodes and "
            f"{analytics.get('total_edges', len(data['relationships']))} edges.",
            f"- Hubs: **{', '.join(analytics.get('hubs', [])) or 'none identified'}**.",
            f"- Structural bridges: **{', '.join(analytics.get('bridges', [])) or 'none identified'}** — "
            "these are the nodes whose removal splits the network.",
            "",
            "## 3. Sequence that matters",
        ]

        for evt in sorted(key_events, key=lambda e: e.timestamp or datetime.min):
            parties = ", ".join(label_of.get(x, x) for x in (evt.related_entities or [])[:3])
            cite = (
                f" `[{evt.evidence_id}]`"
                if evt.evidence_id
                else " *(no evidence artifact attached)*"
            )
            lines.append(
                f"- **{_fmt_dt(evt.timestamp)}** — {evt.title}"
                + (f" ({parties})" if parties else "")
                + (f". {evt.summary}" if evt.summary else "")
                + cite
            )

        lines += [
            "",
            "## 4. Evidence integrity",
            f"- **{integrity['verified']}/{integrity['total']}** artifacts match their recorded "
            "SHA-256 digest.",
            (
                "- No tamper flags are open on the custody ledger."
                if integrity["tamper_flags"] == 0
                else f"- ⚠️ **{integrity['tamper_flags']} tamper flag(s)** are open on the "
                "custody ledger."
            ),
            "",
            "## 5. How to read this",
            "Counts above are read from the case record store at query time, not asserted from a "
            "template. Every section below is expandable and lists the underlying rows, so any "
            "figure here can be traced to the records that produced it. Items marked as inferred "
            "or unsourced are **not** established fact and are listed in the gaps section.",
        ]
        return "\n".join(line for line in lines if line is not None)


case_briefing = CaseBriefingService()
