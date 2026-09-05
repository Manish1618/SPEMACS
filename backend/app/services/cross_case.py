"""Cross-Case Intelligence Engine.

Finds where an active investigation touches other investigations the caller is
authorised to read, and says *why* each touch was detected.

Two rules shape everything here:

1. **Authorisation is the outer boundary.** Every query is filtered to
   ``ctx.allowed_cases`` before any comparison happens. A case the caller cannot
   open contributes nothing to the result and is never named. The response
   reports how many cases were out of scope so the investigator knows the search
   was bounded, without leaking what it was bounded from.

2. **A link is an association, never an accusation.** Confidence here measures
   *how certain we are the link exists in the records* - not how suspicious it
   is. Shared entities, shared locations, shared timing and network proximity are
   reasons to read two files together. Every record carries its uncertainties and
   an explicit statement that it is not a finding of wrongdoing.
"""

from __future__ import annotations

import re
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from app.models.entities import (
    Case,
    Document,
    Entity,
    Evidence,
    Event,
    OsintRecord,
    Relationship,
)
from app.services.retrieval import AccessContext

# Weak signals (a shared city, a same-day event) can enumerate into the hundreds
# without adding information. Each basis is capped and the record says so.
WEAK_SIGNAL_CAP = 12
MAX_HOPS = 3
PROXIMITY_KM = 1.0
TEMPORAL_WINDOW_HOURS = 48

# Identifier-bearing property keys, by what they identify. Matching on these is
# stronger than matching on a name because they are issued, not chosen.
IDENTIFIER_KEYS = {
    "pan": "tax identifier",
    "passport": "passport number",
    "national_id": "national identity number",
    "subscriber": "telecom subscriber",
    "imei": "handset IMEI",
    "iban": "bank IBAN",
    "account_number": "account number",
    "swift": "SWIFT/BIC code",
    "cin": "company registration number",
    "uid": "registry UID",
    "registration": "registration number",
    "vin": "vehicle identification number",
}

# The one sentence that must survive every code path.
NOT_A_FINDING = (
    "Association only. A shared entity, identifier, location, time window or network "
    "path is a reason to read the two files together. It is not evidence that an "
    "offence occurred and must not be treated as one."
)

CONFIDENCE_MEANING = (
    "Confidence expresses how certain the engine is that this link genuinely exists in "
    "the records - not how incriminating it is. A high-confidence link can be entirely "
    "innocent."
)


def _band(confidence: float) -> str:
    if confidence >= 0.8:
        return "HIGH"
    if confidence >= 0.5:
        return "MODERATE"
    return "LOW"


def _normalise_name(value: str) -> str:
    """Fold a name or identifier to a comparable form.

    Phone numbers, plates and registry ids are written inconsistently across
    agencies, so punctuation and spacing are dropped before comparison.
    """
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def _aware(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math

    radius = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@dataclass
class _Corpus:
    """Everything the engine is allowed to look at, loaded once."""

    cases: Dict[str, Case]
    entities: Dict[str, Entity]
    relationships: List[Relationship]
    events: List[Event]
    documents: List[Document]
    evidence: Dict[str, Evidence]
    osint: List[OsintRecord]
    appearances: Dict[str, Set[str]]  # entity_id -> case ids whose records mention it

    def label(self, entity_id: str) -> str:
        entity = self.entities.get(entity_id)
        return entity.label if entity else entity_id

    def case_title(self, case_id: str) -> str:
        case = self.cases.get(case_id)
        return case.title if case else case_id


class CrossCaseIntelligenceEngine:
    """Detects, explains and scores relationships between separate investigations."""

    # ------------------------------------------------------------------ load

    def _load(self, db: Session, allowed: List[str]) -> _Corpus:
        cases = {
            c.case_id: c for c in db.query(Case).filter(Case.case_id.in_(allowed)).all()
        }
        entities = {
            e.entity_id: e
            for e in db.query(Entity).filter(Entity.case_id.in_(allowed)).all()
        }
        relationships = db.query(Relationship).filter(Relationship.case_id.in_(allowed)).all()
        events = db.query(Event).filter(Event.case_id.in_(allowed)).all()
        documents = db.query(Document).filter(Document.case_id.in_(allowed)).all()
        evidence = {
            e.evidence_id: e
            for e in db.query(Evidence).filter(Evidence.case_id.in_(allowed)).all()
        }
        osint = db.query(OsintRecord).filter(OsintRecord.case_id.in_(allowed)).all()

        # An entity "appears in" a case when that case's records mention it, which
        # is not the same as the case it is registered under. Cross-case presence
        # lives in this distinction.
        appearances: Dict[str, Set[str]] = defaultdict(set)
        for entity in entities.values():
            appearances[entity.entity_id].add(entity.case_id)
        for rel in relationships:
            appearances[rel.source_id].add(rel.case_id)
            appearances[rel.target_id].add(rel.case_id)
        for event in events:
            for eid in event.related_entities or []:
                appearances[eid].add(event.case_id)

        return _Corpus(
            cases=cases,
            entities=entities,
            relationships=relationships,
            events=events,
            documents=documents,
            evidence=evidence,
            osint=osint,
            appearances=appearances,
        )

    # --------------------------------------------------------------- helpers

    def _evidence_brief(self, corpus: _Corpus, evidence_ids: Iterable[str]) -> List[Dict[str, Any]]:
        briefs = []
        for eid in dict.fromkeys(e for e in evidence_ids if e):
            item = corpus.evidence.get(eid)
            if item is None:
                # Referenced but not readable under this authorisation.
                briefs.append(
                    {
                        "evidence_id": eid,
                        "title": "Not readable under current authorisation",
                        "case_id": None,
                        "integrity_status": "UNKNOWN",
                        "readable": False,
                    }
                )
                continue
            briefs.append(
                {
                    "evidence_id": item.evidence_id,
                    "title": item.title,
                    "case_id": item.case_id,
                    "evidence_type": item.evidence_type,
                    "integrity_status": item.integrity_status,
                    "sha256_hash": item.sha256_hash,
                    "readable": True,
                }
            )
        return briefs

    def _integrity_contradictions(
        self, corpus: _Corpus, evidence_ids: Iterable[str]
    ) -> List[Dict[str, Any]]:
        """Evidence that undercuts a link: failed digests, or unreadable artifacts."""
        problems = []
        for eid in dict.fromkeys(e for e in evidence_ids if e):
            item = corpus.evidence.get(eid)
            if item is None:
                problems.append(
                    {
                        "source": eid,
                        "claim": "This link cites an evidence artifact.",
                        "discrepancy": (
                            "The artifact is outside this user's authorised scope, so the link "
                            "cannot be independently checked here."
                        ),
                    }
                )
            elif item.integrity_status != "VERIFIED":
                problems.append(
                    {
                        "source": f"{item.evidence_id} ({item.title})",
                        "claim": "This link rests on the cited artifact.",
                        "discrepancy": (
                            f"The artifact's integrity status is {item.integrity_status}; its "
                            "digest does not match the recorded anchor. Re-acquire before relying "
                            "on this link."
                        ),
                    }
                )
        return problems

    def _entity_refs(self, corpus: _Corpus, entity_ids: Iterable[str]) -> List[Dict[str, Any]]:
        refs = []
        for eid in dict.fromkeys(entity_ids):
            entity = corpus.entities.get(eid)
            refs.append(
                {
                    "entity_id": eid,
                    "label": entity.label if entity else eid,
                    "entity_type": entity.entity_type if entity else "UNKNOWN",
                    "registered_case_id": entity.case_id if entity else None,
                    "appears_in_cases": sorted(corpus.appearances.get(eid, set())),
                }
            )
        return refs

    def _sync(
        self,
        node_ids: Iterable[str] = (),
        event_ids: Iterable[str] = (),
        coordinates: Iterable[Tuple[float, float]] = (),
        timeline: Optional[Tuple[Optional[str], Optional[str]]] = None,
    ) -> Dict[str, Any]:
        """The payload the workspace uses to focus graph, map and timeline together."""
        return {
            "node_ids": list(dict.fromkeys(node_ids)),
            "event_ids": list(dict.fromkeys(event_ids)),
            "coordinates": [list(c) for c in coordinates],
            "timeline_from": timeline[0] if timeline else None,
            "timeline_to": timeline[1] if timeline else None,
        }

    def _link(
        self,
        link_id: str,
        basis: str,
        basis_label: str,
        summary: str,
        explanation: List[str],
        case_a: str,
        case_b: str,
        corpus: _Corpus,
        confidence: float,
        uncertainty: List[str],
        entities: List[Dict[str, Any]],
        supporting_evidence: Optional[List[Dict[str, Any]]] = None,
        contradicting_evidence: Optional[List[Dict[str, Any]]] = None,
        hops: int = 0,
        path: Optional[List[Dict[str, Any]]] = None,
        view_sync: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        confidence = round(max(0.0, min(1.0, confidence)), 2)
        return {
            "link_id": link_id,
            "basis": basis,
            "basis_label": basis_label,
            "summary": summary,
            "explanation": explanation,
            "case_a": {"case_id": case_a, "title": corpus.case_title(case_a)},
            "case_b": {"case_id": case_b, "title": corpus.case_title(case_b)},
            "entities": entities,
            "hops": hops,
            "path": path or [],
            "supporting_evidence": supporting_evidence or [],
            "contradicting_evidence": contradicting_evidence or [],
            "confidence": confidence,
            "confidence_band": _band(confidence),
            "confidence_meaning": CONFIDENCE_MEANING,
            "uncertainty": uncertainty,
            "requires_human_verification": confidence < 0.8 or bool(contradicting_evidence),
            "interpretation": NOT_A_FINDING,
            "view_sync": view_sync or self._sync(),
        }

    # --------------------------------------------------------------- signals

    def _shared_entities(self, corpus: _Corpus, case_id: str) -> List[Dict[str, Any]]:
        """The same record referenced by both files - the strongest identity signal."""
        links = []
        for entity_id, cases in sorted(corpus.appearances.items()):
            if case_id not in cases or len(cases) < 2:
                continue
            if entity_id in corpus.cases:  # the case node itself is not a subject
                continue
            entity = corpus.entities.get(entity_id)
            if entity is None:
                continue

            for other in sorted(cases - {case_id}):
                own_events = [
                    e for e in corpus.events
                    if e.case_id == other and entity_id in (e.related_entities or [])
                ]
                own_rels = [
                    r for r in corpus.relationships
                    if r.case_id == other and entity_id in (r.source_id, r.target_id)
                ]
                evidence_ids = [e.evidence_id for e in own_events if e.evidence_id]
                for rel in own_rels:
                    evidence_ids.extend(rel.evidence_ids or [])

                explanation = [
                    f"Entity record {entity_id} ({entity.label}) is registered under "
                    f"{entity.case_id}.",
                    f"Records held under {other} reference the same entity id: "
                    f"{len(own_events)} event(s) and {len(own_rels)} relationship(s).",
                    "This is one record referenced by two files, not two records judged to be "
                    "the same person.",
                ]

                links.append(
                    self._link(
                        link_id=f"XC-ENT-{entity_id}-{other}",
                        basis="SHARED_ENTITY",
                        basis_label="Same entity record in both files",
                        summary=(
                            f"{entity.label} ({entity.entity_type.title()}) is referenced by "
                            f"records in both {case_id} and {other}."
                        ),
                        explanation=explanation,
                        case_a=case_id,
                        case_b=other,
                        corpus=corpus,
                        confidence=0.92,
                        uncertainty=[
                            "Presence in both files says nothing about the nature of the person's "
                            "involvement in either.",
                            "If the entity was created by an automated extraction, confirm the "
                            "underlying source document names the same subject.",
                        ],
                        entities=self._entity_refs(corpus, [entity_id]),
                        supporting_evidence=self._evidence_brief(corpus, evidence_ids),
                        contradicting_evidence=self._integrity_contradictions(corpus, evidence_ids),
                        view_sync=self._sync(
                            node_ids=[entity_id],
                            event_ids=[e.event_id for e in own_events],
                            coordinates=[
                                (e.latitude, e.longitude)
                                for e in own_events
                                if e.latitude is not None and e.longitude is not None
                            ],
                            timeline=self._span([e.timestamp for e in own_events]),
                        ),
                    )
                )
        return links

    def _cross_case_relationships(self, corpus: _Corpus, case_id: str) -> List[Dict[str, Any]]:
        """A recorded relationship whose two ends are registered under different cases."""
        links = []
        for rel in corpus.relationships:
            source = corpus.entities.get(rel.source_id)
            target = corpus.entities.get(rel.target_id)
            if source is None or target is None:
                continue
            if source.case_id == target.case_id:
                continue
            if case_id not in (source.case_id, target.case_id, rel.case_id):
                continue

            other = target.case_id if source.case_id == case_id else source.case_id
            if other == case_id:
                other = rel.case_id if rel.case_id != case_id else target.case_id
            if other == case_id:
                continue

            observed = (rel.assertion_kind or "OBSERVED") == "OBSERVED"
            sourced = bool(rel.evidence_ids)
            confidence = (rel.confidence or 1.0) * (1.0 if observed else 0.7)
            if not sourced:
                confidence *= 0.7

            uncertainty = []
            if not sourced:
                uncertainty.append(
                    "No evidence id is attached to this relationship, so it rests on the "
                    "analyst's entry rather than on a source artifact."
                )
            if not observed:
                uncertainty.append(
                    f"The relationship is recorded as {rel.assertion_kind}, i.e. inferred rather "
                    "than directly observed."
                )
            uncertainty.append(
                "A commercial or contractual relationship between parties in two files is "
                "ordinary and expected in trade investigations."
            )

            links.append(
                self._link(
                    link_id=f"XC-REL-{rel.rel_id}",
                    basis="CROSS_CASE_RELATIONSHIP",
                    basis_label="Recorded relationship spanning two files",
                    summary=(
                        f"{corpus.label(rel.source_id)} ({source.case_id}) —{rel.rel_type}→ "
                        f"{corpus.label(rel.target_id)} ({target.case_id})."
                    ),
                    explanation=[
                        f"Relationship {rel.rel_id} of type {rel.rel_type} joins "
                        f"{corpus.label(rel.source_id)}, registered under {source.case_id}, to "
                        f"{corpus.label(rel.target_id)}, registered under {target.case_id}.",
                        f"Assertion kind: {rel.assertion_kind or 'OBSERVED'}; recorded confidence "
                        f"{rel.confidence if rel.confidence is not None else 'unstated'}.",
                        (
                            f"Cited evidence: {', '.join(rel.evidence_ids)}."
                            if rel.evidence_ids
                            else "No evidence artifact is cited for this relationship."
                        ),
                    ],
                    case_a=case_id,
                    case_b=other,
                    corpus=corpus,
                    confidence=confidence,
                    uncertainty=uncertainty,
                    entities=self._entity_refs(corpus, [rel.source_id, rel.target_id]),
                    supporting_evidence=self._evidence_brief(corpus, rel.evidence_ids or []),
                    contradicting_evidence=self._integrity_contradictions(
                        corpus, rel.evidence_ids or []
                    ),
                    hops=1,
                    path=[
                        {
                            "from": rel.source_id,
                            "from_label": corpus.label(rel.source_id),
                            "rel_type": rel.rel_type,
                            "to": rel.target_id,
                            "to_label": corpus.label(rel.target_id),
                            "rel_id": rel.rel_id,
                        }
                    ],
                    view_sync=self._sync(node_ids=[rel.source_id, rel.target_id]),
                )
            )
        return links

    def _identifier_matches(self, corpus: _Corpus, case_id: str) -> List[Dict[str, Any]]:
        """Distinct records in two files carrying the same issued identifier."""
        index: Dict[Tuple[str, str], List[Entity]] = defaultdict(list)
        for entity in corpus.entities.values():
            for key, description in IDENTIFIER_KEYS.items():
                value = (entity.properties or {}).get(key)
                if isinstance(value, str) and _normalise_name(value):
                    index[(key, _normalise_name(value))].append(entity)

        links = []
        for (key, value), group in sorted(index.items()):
            cases = {e.case_id for e in group}
            if case_id not in cases or len(cases) < 2:
                continue
            for other in sorted(cases - {case_id}):
                here = [e for e in group if e.case_id == case_id]
                there = [e for e in group if e.case_id == other]
                links.append(
                    self._link(
                        link_id=f"XC-ID-{key}-{value}-{other}",
                        basis="IDENTIFIER_MATCH",
                        basis_label=f"Same {IDENTIFIER_KEYS[key]} in both files",
                        summary=(
                            f"{', '.join(e.label for e in here)} ({case_id}) and "
                            f"{', '.join(e.label for e in there)} ({other}) carry the same "
                            f"{IDENTIFIER_KEYS[key]}."
                        ),
                        explanation=[
                            f"Property '{key}' holds the same normalised value in records under "
                            f"both {case_id} and {other}.",
                            "Issued identifiers are stronger than name matches because they are "
                            "assigned rather than chosen.",
                            "These remain two separate records; nothing here merges them.",
                        ],
                        case_a=case_id,
                        case_b=other,
                        corpus=corpus,
                        confidence=0.85,
                        uncertainty=[
                            "Identifiers are mis-keyed during data entry and are sometimes reused "
                            "or recycled by the issuing body.",
                            "Confirm against the source document before treating the two records "
                            "as one subject.",
                        ],
                        entities=self._entity_refs(
                            corpus, [e.entity_id for e in here + there]
                        ),
                        view_sync=self._sync(
                            node_ids=[e.entity_id for e in here + there]
                        ),
                    )
                )
        return links

    def _alias_matches(self, corpus: _Corpus, case_id: str) -> List[Dict[str, Any]]:
        """Different records in two files whose name or alias is the same string."""
        index: Dict[str, List[Entity]] = defaultdict(list)
        for entity in corpus.entities.values():
            if entity.entity_type == "CASE":
                continue
            for name in [entity.label] + list(entity.aliases or []):
                key = _normalise_name(name)
                if len(key) >= 4:
                    index[key].append(entity)

        links = []
        for key, group in sorted(index.items()):
            unique = {e.entity_id: e for e in group}.values()
            cases = {e.case_id for e in unique}
            if case_id not in cases or len(cases) < 2:
                continue
            for other in sorted(cases - {case_id}):
                here = [e for e in unique if e.case_id == case_id]
                there = [e for e in unique if e.case_id == other]
                if not here or not there:
                    continue
                types = {e.entity_type for e in here} | {e.entity_type for e in there}
                confidence = 0.6 if len(types) == 1 else 0.4

                links.append(
                    self._link(
                        link_id=f"XC-ALIAS-{key}-{other}",
                        basis="ALIAS_MATCH",
                        basis_label="Matching name or alias across files",
                        summary=(
                            f"'{here[0].label}' in {case_id} and '{there[0].label}' in {other} "
                            "resolve to the same name after normalisation."
                        ),
                        explanation=[
                            f"Normalised name '{key}' occurs on records in both {case_id} and "
                            f"{other}.",
                            f"Records involved: "
                            + "; ".join(
                                f"{e.entity_id} ({e.label}, {e.entity_type}, {e.case_id})"
                                for e in list(here) + list(there)
                            ),
                            (
                                "Both sides are the same entity type."
                                if len(types) == 1
                                else f"The records are of different types ({', '.join(sorted(types))}), "
                                "which weakens the match considerably."
                            ),
                            "This is a name collision until an investigator confirms otherwise. "
                            "The engine does not merge records.",
                        ],
                        case_a=case_id,
                        case_b=other,
                        corpus=corpus,
                        confidence=confidence,
                        uncertainty=[
                            "Common names collide. Two people sharing a name is unremarkable and "
                            "carries no evidential weight on its own.",
                            "Verify with an issued identifier, date of birth or a source document "
                            "before treating these as one subject.",
                        ],
                        entities=self._entity_refs(
                            corpus, [e.entity_id for e in list(here) + list(there)]
                        ),
                        view_sync=self._sync(
                            node_ids=[e.entity_id for e in list(here) + list(there)]
                        ),
                    )
                )
        return links

    def _shared_artifacts(self, corpus: _Corpus, case_id: str) -> List[Dict[str, Any]]:
        """One evidence artifact or document cited by records in two files."""
        cited: Dict[str, Set[str]] = defaultdict(set)
        for event in corpus.events:
            if event.evidence_id:
                cited[event.evidence_id].add(event.case_id)
        for rel in corpus.relationships:
            for eid in rel.evidence_ids or []:
                cited[eid].add(rel.case_id)

        links = []
        for evidence_id, cases in sorted(cited.items()):
            if case_id not in cases or len(cases) < 2:
                continue
            item = corpus.evidence.get(evidence_id)
            for other in sorted(cases - {case_id}):
                links.append(
                    self._link(
                        link_id=f"XC-EVID-{evidence_id}-{other}",
                        basis="SHARED_ARTIFACT",
                        basis_label="One artifact cited by both files",
                        summary=(
                            f"Evidence {evidence_id}"
                            + (f" ({item.title})" if item else "")
                            + f" is cited by records in both {case_id} and {other}."
                        ),
                        explanation=[
                            f"Artifact {evidence_id} is referenced by records held under both "
                            f"cases.",
                            (
                                f"Registered under {item.case_id} as a {item.evidence_type}; "
                                f"integrity status {item.integrity_status}."
                                if item
                                else "The artifact itself is outside this user's authorised scope."
                            ),
                            "A single source document covering both investigations is a direct "
                            "documentary connection, not an inferred one.",
                        ],
                        case_a=case_id,
                        case_b=other,
                        corpus=corpus,
                        confidence=0.9 if item and item.integrity_status == "VERIFIED" else 0.55,
                        uncertainty=[
                            "A shared artifact may simply be a bulk data extract (a tower dump, a "
                            "bank statement range) that covers unrelated subjects.",
                        ],
                        entities=[],
                        supporting_evidence=self._evidence_brief(corpus, [evidence_id]),
                        contradicting_evidence=self._integrity_contradictions(
                            corpus, [evidence_id]
                        ),
                        view_sync=self._sync(
                            event_ids=[
                                e.event_id for e in corpus.events if e.evidence_id == evidence_id
                            ]
                        ),
                    )
                )
        return links

    def _shared_locations(self, corpus: _Corpus, case_id: str) -> List[Dict[str, Any]]:
        """Places recorded in both files - named the same, or within a short radius."""
        here = [e for e in corpus.events if e.case_id == case_id]
        elsewhere = [e for e in corpus.events if e.case_id != case_id]
        if not here or not elsewhere:
            return []

        seen: Set[Tuple[str, str]] = set()
        links = []
        for event_a in here:
            for event_b in elsewhere:
                name_a = (event_a.location_name or "").strip().lower()
                name_b = (event_b.location_name or "").strip().lower()

                same_name = bool(name_a) and name_a == name_b
                near = False
                distance = None
                if not same_name and None not in (
                    event_a.latitude, event_a.longitude, event_b.latitude, event_b.longitude
                ):
                    distance = _haversine_km(
                        event_a.latitude, event_a.longitude, event_b.latitude, event_b.longitude
                    )
                    near = distance <= PROXIMITY_KM

                if not (same_name or near):
                    continue

                key = (name_a or f"{event_a.latitude},{event_a.longitude}", event_b.case_id)
                if key in seen:
                    continue
                seen.add(key)

                place = event_a.location_name or f"{event_a.latitude}, {event_a.longitude}"
                links.append(
                    self._link(
                        link_id=f"XC-LOC-{_normalise_name(place)}-{event_b.case_id}",
                        basis="SHARED_LOCATION",
                        basis_label="Same place recorded in both files",
                        summary=(
                            f"{place} appears in records for both {case_id} and {event_b.case_id}."
                            + (f" Nearest recorded points are {distance:.2f} km apart." if distance else "")
                        ),
                        explanation=[
                            f"{case_id} records '{event_a.title}' at {place}.",
                            f"{event_b.case_id} records '{event_b.title}' at "
                            f"{event_b.location_name or 'the same coordinates'}.",
                            (
                                "Matched on identical location name."
                                if same_name
                                else f"Matched on coordinates {distance:.2f} km apart, within the "
                                f"{PROXIMITY_KM} km threshold."
                            ),
                        ],
                        case_a=case_id,
                        case_b=event_b.case_id,
                        corpus=corpus,
                        confidence=0.35 if same_name else 0.3,
                        uncertainty=[
                            "Co-location is the weakest signal the engine produces. Ports, hotels, "
                            "toll plazas and telecom towers serve thousands of unconnected people.",
                            "A cell tower location is a coverage area, not a position; two records "
                            "on one tower can be hundreds of metres apart.",
                            "Presence at a place carries no implication about conduct there.",
                        ],
                        entities=self._entity_refs(
                            corpus,
                            list(event_a.related_entities or [])[:3]
                            + list(event_b.related_entities or [])[:3],
                        ),
                        supporting_evidence=self._evidence_brief(
                            corpus, [event_a.evidence_id, event_b.evidence_id]
                        ),
                        view_sync=self._sync(
                            node_ids=list(event_a.related_entities or [])
                            + list(event_b.related_entities or []),
                            event_ids=[event_a.event_id, event_b.event_id],
                            coordinates=[
                                (e.latitude, e.longitude)
                                for e in (event_a, event_b)
                                if e.latitude is not None and e.longitude is not None
                            ],
                            timeline=self._span([event_a.timestamp, event_b.timestamp]),
                        ),
                    )
                )
                if len(links) >= WEAK_SIGNAL_CAP:
                    return links
        return links

    def _temporal_patterns(self, corpus: _Corpus, case_id: str) -> List[Dict[str, Any]]:
        """Activity in one file closely followed by activity in another, same subject."""
        by_case: Dict[str, List[Event]] = defaultdict(list)
        for event in corpus.events:
            by_case[event.case_id].append(event)

        here = sorted(
            by_case.get(case_id, []), key=lambda e: _aware(e.timestamp) or datetime.min.replace(tzinfo=timezone.utc)
        )
        links = []
        window = timedelta(hours=TEMPORAL_WINDOW_HOURS)

        for other, events in by_case.items():
            if other == case_id:
                continue
            for event_b in events:
                stamp_b = _aware(event_b.timestamp)
                if stamp_b is None:
                    continue
                shared_subjects = set(event_b.related_entities or [])
                for event_a in here:
                    stamp_a = _aware(event_a.timestamp)
                    if stamp_a is None or abs(stamp_a - stamp_b) > window:
                        continue
                    overlap = shared_subjects & set(event_a.related_entities or [])
                    if not overlap:
                        continue

                    gap_hours = abs((stamp_a - stamp_b).total_seconds()) / 3600
                    links.append(
                        self._link(
                            link_id=f"XC-TIME-{event_a.event_id}-{event_b.event_id}",
                            basis="TEMPORAL_PATTERN",
                            basis_label="Activity in both files within one window",
                            summary=(
                                f"{', '.join(corpus.label(e) for e in sorted(overlap))} appears in "
                                f"records from both cases within {gap_hours:.1f} hours."
                            ),
                            explanation=[
                                f"{case_id}: '{event_a.title}' at "
                                f"{stamp_a.isoformat() if stamp_a else 'unknown time'}.",
                                f"{other}: '{event_b.title}' at "
                                f"{stamp_b.isoformat() if stamp_b else 'unknown time'}.",
                                f"Both records reference "
                                f"{', '.join(corpus.label(e) for e in sorted(overlap))}, and fall "
                                f"{gap_hours:.1f} hours apart, inside the "
                                f"{TEMPORAL_WINDOW_HOURS}-hour comparison window.",
                                "Ordering in time is not causation. The window is a retrieval "
                                "device for finding records to read together.",
                            ],
                            case_a=case_id,
                            case_b=other,
                            corpus=corpus,
                            confidence=0.3,
                            uncertainty=[
                                "Temporal proximity is a correlation. It does not establish that "
                                "either record caused or related to the other.",
                                "The window is an arbitrary analytical choice; widening or "
                                "narrowing it changes what appears here.",
                                "Timestamps across agencies may sit in different time zones or "
                                "carry recording delays.",
                            ],
                            entities=self._entity_refs(corpus, sorted(overlap)),
                            supporting_evidence=self._evidence_brief(
                                corpus, [event_a.evidence_id, event_b.evidence_id]
                            ),
                            view_sync=self._sync(
                                node_ids=sorted(overlap),
                                event_ids=[event_a.event_id, event_b.event_id],
                                coordinates=[
                                    (e.latitude, e.longitude)
                                    for e in (event_a, event_b)
                                    if e.latitude is not None and e.longitude is not None
                                ],
                                timeline=self._span([event_a.timestamp, event_b.timestamp]),
                            ),
                        )
                    )
                    if len(links) >= WEAK_SIGNAL_CAP:
                        return links
        return links

    def _multi_hop(
        self, corpus: _Corpus, case_id: str, already_linked: Set[str]
    ) -> List[Dict[str, Any]]:
        """Shortest relationship path from this case's records into another file.

        Paths are walked over real relationship edges only. Case nodes are excluded
        as intermediates - every entity hangs off its case node, so routing through
        one would make any two entities look two hops apart.
        """
        adjacency: Dict[str, List[Tuple[str, Relationship]]] = defaultdict(list)
        for rel in corpus.relationships:
            if rel.source_id in corpus.cases or rel.target_id in corpus.cases:
                continue
            adjacency[rel.source_id].append((rel.target_id, rel))
            adjacency[rel.target_id].append((rel.source_id, rel))

        origins = [
            eid
            for eid, cases in corpus.appearances.items()
            if case_id in cases and eid not in corpus.cases
        ]
        origin_set = set(origins)

        found: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for origin in origins:
            queue: deque = deque([(origin, [])])
            visited = {origin}
            while queue:
                node, path = queue.popleft()
                if len(path) >= MAX_HOPS:
                    continue
                for neighbour, rel in adjacency.get(node, []):
                    if neighbour in visited:
                        continue
                    visited.add(neighbour)
                    step = path + [(node, rel, neighbour)]

                    neighbour_cases = corpus.appearances.get(neighbour, set())
                    reaches_other = neighbour_cases - {case_id}
                    # A genuine crossing: the endpoint belongs to another file and
                    # is not itself already one of this case's own records.
                    if reaches_other and neighbour not in origin_set and len(step) >= 2:
                        other = sorted(reaches_other)[0]
                        key = (origin, neighbour)
                        if key not in found:
                            found[key] = {"path": step, "other": other}
                        continue
                    queue.append((neighbour, step))

        links = []
        for (origin, endpoint), detail in sorted(found.items()):
            step_list = detail["path"]
            other = detail["other"]
            if f"XC-ENT-{endpoint}-{other}" in already_linked:
                continue

            hops = len(step_list)
            edge_confidences = [
                (rel.confidence or 1.0) * (1.0 if (rel.assertion_kind or "OBSERVED") == "OBSERVED" else 0.7)
                for _, rel, _ in step_list
            ]
            # A chain is no stronger than its weakest edge, and each additional
            # hop is one more place the reasoning can be wrong.
            confidence = round(min(edge_confidences) * (0.6 ** (hops - 1)), 2)

            path_repr = [
                {
                    "from": a,
                    "from_label": corpus.label(a),
                    "rel_type": rel.rel_type,
                    "rel_id": rel.rel_id,
                    "to": b,
                    "to_label": corpus.label(b),
                    "assertion_kind": rel.assertion_kind,
                    "evidence_ids": rel.evidence_ids or [],
                }
                for a, rel, b in step_list
            ]
            evidence_ids = [eid for step in path_repr for eid in step["evidence_ids"]]

            links.append(
                self._link(
                    link_id=f"XC-HOP-{origin}-{endpoint}",
                    basis="MULTI_HOP_PATH",
                    basis_label=f"{hops}-hop network path between files",
                    summary=(
                        f"{corpus.label(origin)} ({case_id}) reaches {corpus.label(endpoint)} "
                        f"({other}) in {hops} recorded steps."
                    ),
                    explanation=[
                        " → ".join(
                            [corpus.label(origin)]
                            + [f"[{s['rel_type']}] {s['to_label']}" for s in path_repr]
                        ),
                        f"Every step is a relationship recorded in the case files; none is "
                        f"invented by the engine.",
                        "Confidence is the weakest edge on the path, reduced for each additional "
                        "hop.",
                        "Network proximity describes the shape of the records. It does not imply "
                        "the endpoints know of each other.",
                    ],
                    case_a=case_id,
                    case_b=other,
                    corpus=corpus,
                    confidence=confidence,
                    uncertainty=[
                        "Intermediate parties may be banks, couriers, registries or employers "
                        "whose role is entirely routine.",
                        "Longer paths connect almost anything to anything; treat this as a "
                        "retrieval hint, not as a relationship between the endpoints.",
                        "If any intermediate record is a mis-resolved duplicate, the whole path "
                        "is spurious.",
                    ],
                    entities=self._entity_refs(
                        corpus, [origin] + [s["to"] for s in path_repr]
                    ),
                    supporting_evidence=self._evidence_brief(corpus, evidence_ids),
                    contradicting_evidence=self._integrity_contradictions(corpus, evidence_ids),
                    hops=hops,
                    path=path_repr,
                    view_sync=self._sync(
                        node_ids=[origin] + [s["to"] for s in path_repr]
                    ),
                )
            )
        return links

    def _span(
        self, stamps: Iterable[Optional[datetime]]
    ) -> Tuple[Optional[str], Optional[str]]:
        values = sorted(s for s in (_aware(t) for t in stamps) if s is not None)
        if not values:
            return (None, None)
        return (values[0].isoformat(), values[-1].isoformat())

    # ----------------------------------------------------------------- entry

    def analyse(
        self,
        db: Session,
        ctx: AccessContext,
        case_id: str,
        min_confidence: float = 0.0,
        bases: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Every cross-case link the caller is authorised to see, with its basis."""
        if not ctx.permits(case_id):
            return {
                "case_id": case_id,
                "authorised": False,
                "links": [],
                "authorisation": (
                    f"Access to case {case_id} is not granted to this user. No cross-case "
                    "analysis has been performed and no data from that case has been read."
                ),
                "caveat": NOT_A_FINDING,
            }

        allowed = ctx.scope(None)
        total_cases = db.query(Case).count()
        corpus = self._load(db, allowed)

        shared = self._shared_entities(corpus, case_id)
        already = {link["link_id"] for link in shared}

        links: List[Dict[str, Any]] = []
        links += self._cross_case_relationships(corpus, case_id)
        links += shared
        links += self._identifier_matches(corpus, case_id)
        links += self._alias_matches(corpus, case_id)
        links += self._shared_artifacts(corpus, case_id)
        links += self._multi_hop(corpus, case_id, already)
        links += self._shared_locations(corpus, case_id)
        links += self._temporal_patterns(corpus, case_id)

        if bases:
            wanted = {b.upper() for b in bases}
            links = [link for link in links if link["basis"] in wanted]
        if min_confidence > 0:
            links = [link for link in links if link["confidence"] >= min_confidence]

        links.sort(key=lambda link: (-link["confidence"], link["basis"], link["link_id"]))

        by_case: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for link in links:
            by_case[link["case_b"]["case_id"]].append(link)

        related_cases = [
            {
                "case_id": other,
                "title": corpus.case_title(other),
                "status": corpus.cases[other].status if other in corpus.cases else "UNKNOWN",
                "link_count": len(group),
                "strongest_confidence": max(link["confidence"] for link in group),
                "strongest_basis": max(group, key=lambda link: link["confidence"])["basis"],
                "bases": sorted({link["basis"] for link in group}),
            }
            for other, group in sorted(
                by_case.items(), key=lambda kv: -max(link["confidence"] for link in kv[1])
            )
        ]

        basis_counts: Dict[str, int] = defaultdict(int)
        for link in links:
            basis_counts[link["basis"]] += 1

        return {
            "case_id": case_id,
            "case_title": corpus.case_title(case_id),
            "authorised": True,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "links": links,
            "related_cases": related_cases,
            "summary": {
                "link_count": len(links),
                "related_case_count": len(related_cases),
                "by_basis": dict(sorted(basis_counts.items())),
                "by_band": {
                    band: sum(1 for link in links if link["confidence_band"] == band)
                    for band in ("HIGH", "MODERATE", "LOW")
                },
                "needs_verification": sum(
                    1 for link in links if link["requires_human_verification"]
                ),
            },
            "authorisation": {
                "username": ctx.username,
                "role": ctx.role,
                "cases_in_scope": sorted(allowed),
                "cases_out_of_scope": max(0, total_cases - len(allowed)),
                "note": (
                    f"{len(allowed)} case(s) were searched - those this account is authorised to "
                    "read. "
                    + (
                        f"{total_cases - len(allowed)} further case(s) exist on this system and "
                        "were excluded from the comparison; their contents were not read and are "
                        "not named here."
                        if total_cases > len(allowed)
                        else "No case on this system was excluded from the comparison."
                    )
                ),
            },
            "caveat": NOT_A_FINDING,
            "confidence_meaning": CONFIDENCE_MEANING,
        }


cross_case_engine = CrossCaseIntelligenceEngine()
