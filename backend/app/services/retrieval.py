"""The investigation retrieval layer.

Every tool here is a real, parameterised query against persisted data. Together
they form the action space the Copilot's planner composes over: the planner never
matches a question against a template, it decides which of these to call, with
which arguments, in which order.

Contract for every tool:

  * takes (db, ctx, **params) where ctx carries the caller's case authorisation
  * returns a dict with a "records" list and a "provenance" list
  * every record that rests on a source carries the evidence id it came from
  * an empty result is returned as an empty result -- never padded with a guess

Nothing in this module composes prose. Wording of the final answer is the
planner's job, and it may only use what these tools returned.
"""

from __future__ import annotations

import math
import re
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from app.models.entities import (
    Case,
    CustodyEvent,
    Document,
    Entity,
    Event,
    Evidence,
    Hypothesis,
    OsintRecord,
    Relationship,
)
from app.services import ledger
from app.services.evidence import calculate_sha256, read_artifact


# ---------------------------------------------------------------------------
# Access context
# ---------------------------------------------------------------------------

@dataclass
class AccessContext:
    """Who is asking, and which cases they may read.

    Every tool filters on allowed_cases. A question that would reach a case the
    caller cannot open returns an authorisation note rather than the data.
    """

    username: str = "system"
    role: str = "INVESTIGATOR"
    allowed_cases: List[str] = field(default_factory=list)
    active_case_id: Optional[str] = None

    def permits(self, case_id: Optional[str]) -> bool:
        if case_id is None:
            return True
        return case_id in self.allowed_cases

    def scope(self, case_id: Optional[str]) -> List[str]:
        """Resolve a requested case filter to the set of cases actually readable."""
        if case_id:
            return [case_id] if self.permits(case_id) else []
        return list(self.allowed_cases)


def _denied(case_id: Optional[str]) -> Dict[str, Any]:
    return {
        "records": [],
        "provenance": [],
        "authorisation": (
            f"Access to case {case_id} is not granted to this user. No data from that case has "
            "been retrieved or included in the answer."
        ),
    }


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _aware(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _entity_brief(entity: Entity) -> Dict[str, Any]:
    return {
        "entity_id": entity.entity_id,
        "label": entity.label,
        "entity_type": entity.entity_type,
        "case_id": entity.case_id,
        "aliases": entity.aliases or [],
        "properties": entity.properties or {},
    }


def _event_brief(event: Event) -> Dict[str, Any]:
    return {
        "event_id": event.event_id,
        "case_id": event.case_id,
        "title": event.title,
        "event_type": event.event_type,
        "timestamp": _aware(event.timestamp).isoformat() if event.timestamp else None,
        "location_name": event.location_name,
        "latitude": event.latitude,
        "longitude": event.longitude,
        "related_entities": event.related_entities or [],
        "evidence_id": event.evidence_id,
        "summary": event.summary,
        "confidence": event.confidence,
        "properties": event.properties or {},
    }


def _rel_brief(rel: Relationship) -> Dict[str, Any]:
    return {
        "rel_id": rel.rel_id,
        "case_id": rel.case_id,
        "source_id": rel.source_id,
        "target_id": rel.target_id,
        "rel_type": rel.rel_type,
        "confidence": rel.confidence,
        "assertion_kind": rel.assertion_kind,
        "evidence_ids": rel.evidence_ids or [],
        "first_recorded": _aware(rel.valid_from).isoformat() if rel.valid_from else None,
        "properties": rel.properties or {},
    }


def _label_map(db: Session, entity_ids: List[str]) -> Dict[str, str]:
    if not entity_ids:
        return {}
    rows = db.query(Entity).filter(Entity.entity_id.in_(list(set(entity_ids)))).all()
    return {row.entity_id: row.label for row in rows}


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

def resolve_entity(
    db: Session,
    ctx: AccessContext,
    query: str,
    entity_type: Optional[str] = None,
    limit: int = 6,
) -> Dict[str, Any]:
    """Find entities matching a name, alias, phone number or registration mark.

    Deliberately returns candidates rather than picking one. Where two candidates
    score closely the caller is expected to ask the investigator which is meant.
    """
    cases = ctx.scope(None)
    needle = (query or "").strip().lower()
    if not needle:
        return {"records": [], "provenance": [], "note": "No search term supplied."}

    compact = re.sub(r"[^a-z0-9]", "", needle)
    rows = db.query(Entity).filter(Entity.case_id.in_(cases)).all()
    if entity_type:
        rows = [r for r in rows if r.entity_type == entity_type.upper()]

    scored = []
    for row in rows:
        candidates = [row.label] + list(row.aliases or [])
        best = 0.0
        for candidate in candidates:
            c_low = candidate.lower()
            c_compact = re.sub(r"[^a-z0-9]", "", c_low)
            if compact and c_compact and (compact == c_compact):
                best = max(best, 1.0)
            elif compact and c_compact and (compact in c_compact or c_compact in compact):
                best = max(best, 0.93)
            else:
                best = max(best, fuzz.token_set_ratio(needle, c_low) / 100.0)

        for key, value in (row.properties or {}).items():
            if isinstance(value, str) and needle and needle in value.lower():
                best = max(best, 0.80)

        if best >= 0.62:
            scored.append((best, row))

    scored.sort(key=lambda pair: (-pair[0], pair[1].entity_id))
    records = []
    for score, row in scored[:limit]:
        brief = _entity_brief(row)
        brief["match_confidence"] = round(score, 3)
        brief["match_basis"] = "exact identifier" if score >= 0.99 else "name or alias similarity"
        records.append(brief)

    ambiguous = (
        len(records) > 1
        and records[0]["match_confidence"] - records[1]["match_confidence"] < 0.08
    )

    return {
        "records": records,
        "provenance": [{"source": "entity register", "case_scope": cases}],
        "ambiguous": ambiguous,
        "note": (
            "More than one entity matches this term with similar confidence. Ask the investigator "
            "which is meant before proceeding."
            if ambiguous
            else ""
        ),
    }


def get_entity_profile(db: Session, ctx: AccessContext, entity_id: str) -> Dict[str, Any]:
    """Everything recorded about one entity: attributes, relationships, events, evidence."""
    entity = db.query(Entity).filter(Entity.entity_id == entity_id).first()
    if entity is None:
        return {"records": [], "provenance": [], "note": f"No entity with id {entity_id}."}
    if not ctx.permits(entity.case_id):
        return _denied(entity.case_id)

    cases = ctx.scope(None)
    rels = (
        db.query(Relationship)
        .filter(
            Relationship.case_id.in_(cases),
            (Relationship.source_id == entity_id) | (Relationship.target_id == entity_id),
        )
        .all()
    )
    events = (
        db.query(Event)
        .filter(Event.case_id.in_(cases))
        .order_by(Event.timestamp.asc())
        .all()
    )
    related_events = [e for e in events if entity_id in (e.related_entities or [])]

    evidence_ids = sorted(
        {eid for r in rels for eid in (r.evidence_ids or [])}
        | {e.evidence_id for e in related_events if e.evidence_id}
    )

    counterpart_ids = [
        r.target_id if r.source_id == entity_id else r.source_id for r in rels
    ]
    labels = _label_map(db, counterpart_ids)

    profile = _entity_brief(entity)
    profile["relationships"] = [
        {**_rel_brief(r), "counterpart_label": labels.get(
            r.target_id if r.source_id == entity_id else r.source_id, "unknown"
        )}
        for r in rels
    ]
    profile["event_count"] = len(related_events)
    profile["first_event"] = (
        _aware(related_events[0].timestamp).isoformat() if related_events else None
    )
    profile["last_event"] = (
        _aware(related_events[-1].timestamp).isoformat() if related_events else None
    )
    profile["recent_events"] = [_event_brief(e) for e in related_events[-12:]]
    profile["evidence_ids"] = evidence_ids

    return {
        "records": [profile],
        "provenance": [{"source": "entity register, relationship store, event store"}],
    }


def get_neighborhood(
    db: Session, ctx: AccessContext, entity_id: str, hops: int = 1, limit: int = 60
) -> Dict[str, Any]:
    """Entities within N relationship hops, with the edges that connect them."""
    entity = db.query(Entity).filter(Entity.entity_id == entity_id).first()
    if entity is None:
        return {"records": [], "provenance": [], "note": f"No entity with id {entity_id}."}
    if not ctx.permits(entity.case_id):
        return _denied(entity.case_id)

    cases = ctx.scope(None)
    rels = db.query(Relationship).filter(Relationship.case_id.in_(cases)).all()

    adjacency: Dict[str, List[Relationship]] = defaultdict(list)
    for rel in rels:
        adjacency[rel.source_id].append(rel)
        adjacency[rel.target_id].append(rel)

    reached = {entity_id}
    frontier = {entity_id}
    edges: Dict[str, Relationship] = {}
    for _ in range(max(1, min(hops, 4))):
        nxt = set()
        for node in frontier:
            for rel in adjacency.get(node, []):
                edges[rel.rel_id] = rel
                other = rel.target_id if rel.source_id == node else rel.source_id
                if other not in reached:
                    nxt.add(other)
        reached |= nxt
        frontier = nxt
        if len(reached) >= limit:
            break

    labels = _label_map(db, list(reached))
    return {
        "records": [
            {
                "centre": entity_id,
                "hops": hops,
                "nodes": [
                    {"entity_id": eid, "label": labels.get(eid, eid)}
                    for eid in sorted(reached)
                ],
                "edges": [
                    {
                        **_rel_brief(rel),
                        "source_label": labels.get(rel.source_id, rel.source_id),
                        "target_label": labels.get(rel.target_id, rel.target_id),
                    }
                    for rel in edges.values()
                ],
            }
        ],
        "provenance": [{"source": "relationship store"}],
    }


def find_paths(
    db: Session,
    ctx: AccessContext,
    source_id: str,
    target_id: str,
    max_hops: int = 5,
    max_paths: int = 3,
) -> Dict[str, Any]:
    """Shortest relationship chains between two entities, with the evidence per link."""
    cases = ctx.scope(None)
    rels = db.query(Relationship).filter(Relationship.case_id.in_(cases)).all()

    adjacency: Dict[str, List[Relationship]] = defaultdict(list)
    for rel in rels:
        adjacency[rel.source_id].append(rel)
        adjacency[rel.target_id].append(rel)

    # Breadth-first so the first paths found are the shortest.
    paths: List[List[Relationship]] = []
    queue: List[tuple] = [(source_id, [], {source_id})]
    while queue and len(paths) < max_paths:
        node, chain, seen = queue.pop(0)
        if len(chain) >= max_hops:
            continue
        for rel in adjacency.get(node, []):
            other = rel.target_id if rel.source_id == node else rel.source_id
            if other in seen:
                continue
            new_chain = chain + [rel]
            if other == target_id:
                paths.append(new_chain)
                if len(paths) >= max_paths:
                    break
            else:
                queue.append((other, new_chain, seen | {other}))

    all_ids = {source_id, target_id}
    for chain in paths:
        for rel in chain:
            all_ids.add(rel.source_id)
            all_ids.add(rel.target_id)
    labels = _label_map(db, list(all_ids))

    records = []
    for chain in paths:
        # A chain is only as well supported as its weakest link.
        weakest = min((r.confidence or 1.0) for r in chain) if chain else 0.0
        records.append(
            {
                "hop_count": len(chain),
                "weakest_link_confidence": round(weakest, 3),
                "contains_inference": any(r.assertion_kind != "OBSERVED" for r in chain),
                "links": [
                    {
                        **_rel_brief(rel),
                        "source_label": labels.get(rel.source_id, rel.source_id),
                        "target_label": labels.get(rel.target_id, rel.target_id),
                    }
                    for rel in chain
                ],
            }
        )

    return {
        "records": records,
        "provenance": [{"source": "relationship store"}],
        "note": (
            ""
            if records
            else f"No relationship chain of {max_hops} hops or fewer connects these two entities "
            "in the authorised case scope."
        ),
    }


def find_relationships(
    db: Session,
    ctx: AccessContext,
    entity_ids: Optional[List[str]] = None,
    rel_types: Optional[List[str]] = None,
    first_recorded_after: Optional[str] = None,
    first_recorded_before: Optional[str] = None,
    case_id: Optional[str] = None,
    limit: int = 80,
) -> Dict[str, Any]:
    """Relationships filtered by participants, type and when they were first recorded.

    first_recorded_after is what answers questions of the form "which connections
    appeared only after <event>".
    """
    cases = ctx.scope(case_id)
    if not cases:
        return _denied(case_id)

    query = db.query(Relationship).filter(Relationship.case_id.in_(cases))
    rows = query.all()

    after = _parse_dt(first_recorded_after)
    before = _parse_dt(first_recorded_before)

    filtered = []
    for rel in rows:
        if entity_ids and not (rel.source_id in entity_ids or rel.target_id in entity_ids):
            continue
        if rel_types and rel.rel_type not in [t.upper() for t in rel_types]:
            continue
        valid_from = _aware(rel.valid_from)
        if after and (valid_from is None or valid_from <= after):
            continue
        if before and (valid_from is None or valid_from >= before):
            continue
        filtered.append(rel)

    filtered.sort(key=lambda r: (_aware(r.valid_from) or datetime.min.replace(tzinfo=timezone.utc)))
    filtered = filtered[:limit]

    ids = {i for r in filtered for i in (r.source_id, r.target_id)}
    labels = _label_map(db, list(ids))

    return {
        "records": [
            {
                **_rel_brief(rel),
                "source_label": labels.get(rel.source_id, rel.source_id),
                "target_label": labels.get(rel.target_id, rel.target_id),
            }
            for rel in filtered
        ],
        "provenance": [{"source": "relationship store", "case_scope": cases}],
        "filters_applied": {
            "entity_ids": entity_ids or [],
            "rel_types": rel_types or [],
            "first_recorded_after": first_recorded_after,
            "first_recorded_before": first_recorded_before,
        },
    }


def find_events(
    db: Session,
    ctx: AccessContext,
    entity_ids: Optional[List[str]] = None,
    event_types: Optional[List[str]] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    case_id: Optional[str] = None,
    near_latitude: Optional[float] = None,
    near_longitude: Optional[float] = None,
    radius_km: Optional[float] = None,
    text_contains: Optional[str] = None,
    limit: int = 60,
) -> Dict[str, Any]:
    """Recorded events filtered by participant, type, time window, place or text."""
    cases = ctx.scope(case_id)
    if not cases:
        return _denied(case_id)

    rows = (
        db.query(Event)
        .filter(Event.case_id.in_(cases))
        .order_by(Event.timestamp.asc())
        .all()
    )

    start = _parse_dt(start_time)
    end = _parse_dt(end_time)
    types = [t.upper() for t in event_types] if event_types else None
    needle = (text_contains or "").lower().strip()

    matched = []
    for event in rows:
        when = _aware(event.timestamp)
        if start and when < start:
            continue
        if end and when > end:
            continue
        if types and event.event_type not in types:
            continue
        if entity_ids and not set(entity_ids) & set(event.related_entities or []):
            continue
        if needle and needle not in f"{event.title} {event.summary} {event.location_name}".lower():
            continue
        if (
            near_latitude is not None
            and near_longitude is not None
            and radius_km
            and event.latitude is not None
        ):
            if _haversine_km(near_latitude, near_longitude, event.latitude, event.longitude) > radius_km:
                continue
        matched.append(event)

    total = len(matched)
    window = matched[:limit]

    return {
        "records": [_event_brief(e) for e in window],
        "provenance": [{"source": "event store", "case_scope": cases}],
        "total_matching": total,
        "returned": len(window),
        "truncated": total > len(window),
    }


def graph_analytics(db: Session, ctx: AccessContext, case_id: Optional[str] = None) -> Dict[str, Any]:
    """Structural measures over the relationship network.

    These describe network position only. A high score means an entity sits at a
    structurally important point in the recorded data; it carries no implication
    about conduct, and the wording of any answer must preserve that.
    """
    cases = ctx.scope(case_id)
    if not cases:
        return _denied(case_id)

    entities = db.query(Entity).filter(Entity.case_id.in_(cases)).all()
    rels = db.query(Relationship).filter(Relationship.case_id.in_(cases)).all()
    known = {e.entity_id for e in entities}
    labels = {e.entity_id: e.label for e in entities}

    import networkx as nx

    graph = nx.Graph()
    graph.add_nodes_from(known)
    for rel in rels:
        if rel.source_id in known and rel.target_id in known:
            graph.add_edge(rel.source_id, rel.target_id, weight=rel.confidence or 1.0)

    if graph.number_of_nodes() == 0:
        return {"records": [], "provenance": [], "note": "No network data in scope."}

    degree = nx.degree_centrality(graph)
    betweenness = nx.betweenness_centrality(graph)
    try:
        pagerank = nx.pagerank(graph)
    except Exception:
        pagerank = {n: 0.0 for n in graph.nodes}

    try:
        communities = nx.community.greedy_modularity_communities(graph)
    except Exception:
        communities = list(nx.connected_components(graph))
    community_of = {
        node: idx for idx, group in enumerate(communities) for node in group
    }

    articulation = set(nx.articulation_points(graph))

    ranked = sorted(
        graph.nodes,
        key=lambda n: (degree.get(n, 0), pagerank.get(n, 0)),
        reverse=True,
    )

    records = [
        {
            "entity_id": node,
            "label": labels.get(node, node),
            "degree_centrality": round(degree.get(node, 0.0), 4),
            "betweenness_centrality": round(betweenness.get(node, 0.0), 4),
            "pagerank": round(pagerank.get(node, 0.0), 4),
            "community_id": community_of.get(node, -1),
            "is_articulation_point": node in articulation,
            "interpretation": (
                "Removing this entity would disconnect part of the recorded network."
                if node in articulation
                else "Ordinary position within its community."
            ),
        }
        for node in ranked
    ]

    return {
        "records": records,
        "provenance": [{"source": "relationship store", "method": "NetworkX centrality"}],
        "summary": {
            "node_count": graph.number_of_nodes(),
            "edge_count": graph.number_of_edges(),
            "community_count": len(communities),
            "density": round(nx.density(graph), 4),
        },
        "caveat": (
            "These are structural measures of position in the recorded network. They reflect what "
            "has been collected, not what exists, and say nothing about whether any person has "
            "done anything wrong."
        ),
    }


def detect_anomalies(
    db: Session,
    ctx: AccessContext,
    case_id: Optional[str] = None,
    entity_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Deviations from an observed baseline.

    Each finding states the observation, the baseline it is measured against, the
    size of the deviation, and at least one alternative explanation. A deviation
    is a reason to look, not a finding of fact.
    """
    cases = ctx.scope(case_id)
    if not cases:
        return _denied(case_id)

    events = (
        db.query(Event)
        .filter(Event.case_id.in_(cases))
        .order_by(Event.timestamp.asc())
        .all()
    )
    entities = {e.entity_id: e for e in db.query(Entity).filter(Entity.case_id.in_(cases)).all()}
    findings: List[Dict[str, Any]] = []

    # --- Communication volume against each pair's own baseline ----------------
    calls = [e for e in events if e.event_type == "CALL" and e.timestamp]
    per_pair_day: Dict[tuple, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for call in calls:
        people = sorted(
            eid for eid in (call.related_entities or [])
            if entities.get(eid) and entities[eid].entity_type == "PERSON"
        )
        if len(people) < 2:
            continue
        pair = (people[0], people[1])
        day = _aware(call.timestamp).date().isoformat()
        per_pair_day[pair][day] += 1

    for pair, by_day in per_pair_day.items():
        counts = list(by_day.values())
        if len(counts) < 8:
            continue
        peak_day, peak = max(by_day.items(), key=lambda kv: kv[1])
        others = [c for day, c in by_day.items() if day != peak_day]
        if not others:
            continue
        mean = statistics.fmean(others)
        stdev = statistics.pstdev(others) if len(others) > 1 else 0.0
        if stdev == 0 and peak <= mean + 1:
            continue
        deviation = (peak - mean) / stdev if stdev > 0 else float(peak - mean)
        if deviation < 2.5:
            continue

        findings.append(
            {
                "anomaly_type": "COMMUNICATION_VOLUME",
                "entities": list(pair),
                "labels": [entities[pair[0]].label, entities[pair[1]].label],
                "observed": f"{peak} recorded calls on {peak_day}",
                "baseline": (
                    f"mean of {mean:.2f} calls per active day across {len(others)} other days "
                    f"between these two handsets"
                ),
                "deviation": f"{deviation:.1f} standard deviations above that baseline",
                "date": peak_day,
                "evidence_ids": sorted({c.evidence_id for c in calls if c.evidence_id}),
                "alternative_explanations": [
                    "An ordinary business or personal matter needing several calls in one day.",
                    "Records for other days may be incomplete, which would inflate the apparent peak.",
                    "A single conversation repeatedly dropped and redialled registers as many calls.",
                ],
                "significance": "Indicates where to look. It is not evidence of wrongdoing.",
            }
        )

    # --- Movement that the recorded timings cannot accommodate ---------------
    by_entity: Dict[str, List[Event]] = defaultdict(list)
    for event in events:
        if event.latitude is None or event.timestamp is None:
            continue
        for eid in event.related_entities or []:
            if entities.get(eid) and entities[eid].entity_type in ("PERSON", "PHONE", "VEHICLE"):
                by_entity[eid].append(event)

    # A person and the handset attributed to them produce the same pair of
    # records. Report it once, against the person, rather than twice.
    type_rank = {"PERSON": 0, "VEHICLE": 1, "PHONE": 2}
    ordered = sorted(
        by_entity.items(), key=lambda kv: type_rank.get(entities[kv[0]].entity_type, 3)
    )
    reported_pairs: set = set()

    for eid, seq in ordered:
        seq.sort(key=lambda e: e.timestamp)
        for first, second in zip(seq, seq[1:]):
            distance = _haversine_km(first.latitude, first.longitude, second.latitude, second.longitude)
            hours = (_aware(second.timestamp) - _aware(first.timestamp)).total_seconds() / 3600.0
            if distance < 200 or hours <= 0:
                continue
            speed = distance / hours
            if speed < 700:
                continue
            pair_key = (first.event_id, second.event_id)
            if pair_key in reported_pairs:
                continue
            reported_pairs.add(pair_key)
            findings.append(
                {
                    "anomaly_type": "INFEASIBLE_MOVEMENT",
                    "entities": [eid],
                    "labels": [entities[eid].label],
                    "observed": (
                        f"recorded at {first.location_name} at "
                        f"{_aware(first.timestamp).isoformat()} and at {second.location_name} at "
                        f"{_aware(second.timestamp).isoformat()}"
                    ),
                    "baseline": f"the two locations are about {distance:.0f} km apart",
                    "deviation": (
                        f"the gap of {hours:.1f} hours implies an average speed of {speed:.0f} km/h"
                    ),
                    "date": _aware(second.timestamp).date().isoformat(),
                    "evidence_ids": sorted({e.evidence_id for e in (first, second) if e.evidence_id}),
                    "alternative_explanations": [
                        "The handset was carried by another person for part of the period.",
                        "A cell tower or reader identifier may be mislabelled in the source extract.",
                        "The two records may refer to different devices attributed to the same person.",
                    ],
                    "significance": (
                        "Two records cannot both describe the movement of one person. At least one "
                        "attribution needs checking."
                    ),
                }
            )

    # --- Counterparties with no prior transaction history --------------------
    transfers = [e for e in events if e.event_type == "TRANSACTION"]
    seen_pairs: set = set()
    for transfer in sorted(transfers, key=lambda e: e.timestamp):
        orgs = [
            eid for eid in (transfer.related_entities or [])
            if entities.get(eid) and entities[eid].entity_type == "ORGANIZATION"
        ]
        if len(orgs) < 2:
            continue
        pair = tuple(sorted(orgs[:2]))
        amount = (transfer.properties or {}).get("amount_usd")
        if pair not in seen_pairs and amount and amount >= 100000:
            findings.append(
                {
                    "anomaly_type": "FIRST_TRANSACTION_WITH_COUNTERPARTY",
                    "entities": list(pair),
                    "labels": [entities[pair[0]].label, entities[pair[1]].label],
                    "observed": f"transfer of USD {amount:,} on {_aware(transfer.timestamp).date().isoformat()}",
                    "baseline": "no earlier transaction between these two parties appears in the ingested ledger extracts",
                    "deviation": "first recorded transaction between the parties is also a large one",
                    "date": _aware(transfer.timestamp).date().isoformat(),
                    "evidence_ids": [transfer.evidence_id] if transfer.evidence_id else [],
                    "alternative_explanations": [
                        "A genuine new commercial relationship, which normally begins with a first payment.",
                        "Earlier dealings may sit in ledgers that have not been obtained.",
                    ],
                    "significance": "Worth establishing the commercial basis for the payment.",
                }
            )
        seen_pairs.add(pair)

    if entity_ids:
        findings = [f for f in findings if set(entity_ids) & set(f["entities"])]

    findings.sort(key=lambda f: f.get("date") or "")
    return {
        "records": findings,
        "provenance": [{"source": "event store", "method": "per-series baseline comparison"}],
        "method_note": (
            "Baselines are computed from the ingested records themselves. Where collection is "
            "incomplete, a baseline will be too low and deviations overstated."
        ),
    }


def find_cross_case_entities(db: Session, ctx: AccessContext) -> Dict[str, Any]:
    """Entities that appear in more than one authorised case."""
    cases = ctx.scope(None)
    rels = db.query(Relationship).filter(Relationship.case_id.in_(cases)).all()
    events = db.query(Event).filter(Event.case_id.in_(cases)).all()

    appearances: Dict[str, set] = defaultdict(set)
    for rel in rels:
        appearances[rel.source_id].add(rel.case_id)
        appearances[rel.target_id].add(rel.case_id)
    for event in events:
        for eid in event.related_entities or []:
            appearances[eid].add(event.case_id)

    shared = {eid: cs for eid, cs in appearances.items() if len(cs) > 1}
    labels = _label_map(db, list(shared))
    case_titles = {c.case_id: c.title for c in db.query(Case).all()}

    records = []
    for eid, case_set in sorted(shared.items()):
        if eid in case_titles:  # skip case nodes themselves
            continue
        records.append(
            {
                "entity_id": eid,
                "label": labels.get(eid, eid),
                "cases": sorted(case_set),
                "case_titles": [case_titles.get(c, c) for c in sorted(case_set)],
                "note": (
                    "This entity is referenced by records in more than one investigation. Shared "
                    "presence is a reason to compare the files, not a finding in itself."
                ),
            }
        )

    return {"records": records, "provenance": [{"source": "relationship and event stores"}]}


def search_documents(
    db: Session,
    ctx: AccessContext,
    query: str,
    case_id: Optional[str] = None,
    limit: int = 5,
) -> Dict[str, Any]:
    """Passage retrieval over case documents.

    Scores paragraphs by term overlap weighted by inverse document frequency, so
    a rare name outweighs a common word. Returns the matching passage rather than
    the whole document, so a citation can point at a specific place.
    """
    cases = ctx.scope(case_id)
    if not cases:
        return _denied(case_id)

    docs = db.query(Document).filter(Document.case_id.in_(cases)).all()
    if not docs:
        return {"records": [], "provenance": [], "note": "No documents in scope."}

    def tokenize(text: str) -> List[str]:
        return re.findall(r"[a-z0-9]+", (text or "").lower())

    passages = []
    for doc in docs:
        for index, para in enumerate(re.split(r"\n\s*\n", doc.extracted_text or "")):
            para = para.strip()
            if len(para) < 25:
                continue
            passages.append((doc, index, para, set(tokenize(para))))

    if not passages:
        return {"records": [], "provenance": [], "note": "No document text in scope."}

    frequency: Dict[str, int] = defaultdict(int)
    for _doc, _idx, _text, tokens in passages:
        for token in tokens:
            frequency[token] += 1

    total = len(passages)
    query_tokens = [t for t in tokenize(query) if len(t) > 2]
    if not query_tokens:
        return {"records": [], "provenance": [], "note": "Search term carried no usable words."}

    scored = []
    for doc, index, text, tokens in passages:
        score = 0.0
        for token in query_tokens:
            if token in tokens:
                score += math.log(1 + total / (1 + frequency[token]))
        if score > 0:
            scored.append((score, doc, index, text))

    scored.sort(key=lambda row: -row[0])
    best = scored[0][0] if scored else 1.0

    records = [
        {
            "document_id": doc.document_id,
            "case_id": doc.case_id,
            "title": doc.title,
            "evidence_id": (doc.parsed_metadata or {}).get("evidence_id"),
            "passage_index": index,
            "passage": text,
            "relevance": round(score / best, 3),
        }
        for score, doc, index, text in scored[:limit]
    ]

    return {
        "records": records,
        "provenance": [{"source": "document store", "method": "IDF-weighted passage retrieval"}],
        "note": "" if records else "No passage in the authorised documents matches this term.",
    }


def get_evidence(
    db: Session,
    ctx: AccessContext,
    evidence_ids: Optional[List[str]] = None,
    case_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Evidence records with their integrity status and custody history."""
    cases = ctx.scope(case_id)
    if not cases:
        return _denied(case_id)

    query = db.query(Evidence).filter(Evidence.case_id.in_(cases))
    if evidence_ids:
        query = query.filter(Evidence.evidence_id.in_(evidence_ids))
    rows = query.all()

    records = []
    for item in rows:
        custody = (
            db.query(CustodyEvent)
            .filter(CustodyEvent.evidence_id == item.evidence_id)
            .order_by(CustodyEvent.created_at.asc())
            .all()
        )
        records.append(
            {
                "evidence_id": item.evidence_id,
                "case_id": item.case_id,
                "title": item.title,
                "evidence_type": item.evidence_type,
                "sha256": item.sha256_hash,
                "integrity_status": item.integrity_status,
                "ledger_block": item.blockchain_block_num,
                "document_id": item.document_id,
                "custody_chain": [
                    {
                        "action": c.action,
                        "actor": c.performed_by,
                        "at": _aware(c.created_at).isoformat() if c.created_at else None,
                        "tamper_detected": c.tamper_detected,
                    }
                    for c in custody
                ],
            }
        )

    missing = sorted(set(evidence_ids or []) - {r["evidence_id"] for r in records})
    return {
        "records": records,
        "provenance": [{"source": "evidence register"}],
        "unresolved_ids": missing,
        "note": (
            f"These evidence ids were referenced but do not exist: {', '.join(missing)}."
            if missing
            else ""
        ),
    }


def verify_integrity(
    db: Session,
    ctx: AccessContext,
    evidence_ids: Optional[List[str]] = None,
    case_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Rehash stored artifacts and check them against the ledger."""
    cases = ctx.scope(case_id)
    if not cases:
        return _denied(case_id)

    query = db.query(Evidence).filter(Evidence.case_id.in_(cases))
    if evidence_ids:
        query = query.filter(Evidence.evidence_id.in_(evidence_ids))
    rows = query.all()

    chain = ledger.verify_chain(db)
    records = []
    for item in rows:
        current = read_artifact(item.evidence_id)
        if current is None:
            status = "UNVERIFIED"
            recomputed = None
        else:
            recomputed = calculate_sha256(current)
            status = "VERIFIED" if recomputed == item.sha256_hash else "TAMPER_DETECTED"
        records.append(
            {
                "evidence_id": item.evidence_id,
                "title": item.title,
                "sealed_sha256": item.sha256_hash,
                "current_sha256": recomputed,
                "integrity_status": status,
                "ledger_block": item.blockchain_block_num,
            }
        )

    failures = [r for r in records if r["integrity_status"] != "VERIFIED"]
    return {
        "records": records,
        "provenance": [{"source": "evidence store and permissioned ledger"}],
        "ledger": chain,
        "summary": {
            "checked": len(records),
            "verified": len(records) - len(failures),
            "failed": len(failures),
        },
        "caveat": (
            "A pass confirms the record has not changed since it was sealed. It does not attest "
            "that the content of the record is true."
        ),
    }


def osint_lookup(
    db: Session,
    ctx: AccessContext,
    query: str,
    entity_id: Optional[str] = None,
    case_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Public-source material held for an entity, with source-independence analysis.

    Counts distinct originating sources rather than distinct outlets: many outlets
    carrying one original filing are one source, not many.
    """
    cases = ctx.scope(case_id)
    if not cases:
        return _denied(case_id)

    rows = db.query(OsintRecord).filter(OsintRecord.case_id.in_(cases)).all()
    needle = (query or "").lower().strip()

    matched = [
        r
        for r in rows
        if (entity_id and r.entity_id == entity_id)
        or (needle and (needle in r.query_term.lower() or needle in r.source_name.lower()))
    ]

    if not matched:
        return {
            "records": [],
            "provenance": [],
            "note": (
                "No public-source material is held for this term in the authorised case scope. "
                "Nothing has been inferred in its absence."
            ),
        }

    # Group by origin: a record with an origin_record_id is a derivative of it.
    by_origin: Dict[str, List[OsintRecord]] = defaultdict(list)
    for record in matched:
        by_origin[record.origin_record_id or record.record_id].append(record)

    # Also treat identical claim text as derivative even when no link is recorded.
    by_hash: Dict[str, List[OsintRecord]] = defaultdict(list)
    for record in matched:
        by_hash[record.content_hash].append(record)
    repeated_text = {h: rs for h, rs in by_hash.items() if len(rs) > 1}

    records = [
        {
            "record_id": r.record_id,
            "entity_id": r.entity_id,
            "source_name": r.source_name,
            "source_url": r.source_url,
            "source_type": r.source_type,
            "published_at": _aware(r.published_at).isoformat() if r.published_at else None,
            "reliability": r.reliability,
            "confidence": r.confidence,
            "claims": r.claims or [],
            "is_derivative": r.is_derivative,
            "derives_from": r.origin_record_id,
            "requires_human_verification": r.requires_human_verification,
            "verification_note": (
                "Potential external match. Human verification required before this is relied on."
                if r.requires_human_verification
                else ""
            ),
        }
        for r in sorted(matched, key=lambda r: (r.is_derivative, r.record_id))
    ]

    independent = [origin for origin, group in by_origin.items()]
    derivative_count = sum(1 for r in matched if r.is_derivative)

    return {
        "records": records,
        "provenance": [{"source": "public-source register"}],
        "source_independence": {
            "reports_held": len(matched),
            "likely_independent_sources": len(independent),
            "derivative_reports": derivative_count,
            "repeated_text_groups": len(repeated_text),
            "interpretation": (
                f"{len(matched)} reports are held, but they trace back to about "
                f"{len(independent)} originating sources. Repetition across outlets is not "
                "corroboration."
            ),
        },
    }


def find_contradictions(
    db: Session,
    ctx: AccessContext,
    entity_ids: Optional[List[str]] = None,
    case_id: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
) -> Dict[str, Any]:
    """Search for material that cuts against the recorded picture.

    Three structural checks, all computed from data rather than asserted:
      1. a place asserted in a witness document against places in the record for
         the same person at the same time
      2. movement the recorded timings cannot accommodate
      3. documents recording the absence of an expected corroborating record
    """
    cases = ctx.scope(case_id)
    if not cases:
        return _denied(case_id)

    entities = {e.entity_id: e for e in db.query(Entity).filter(Entity.case_id.in_(cases)).all()}
    docs = db.query(Document).filter(Document.case_id.in_(cases)).all()
    events = (
        db.query(Event)
        .filter(Event.case_id.in_(cases))
        .order_by(Event.timestamp.asc())
        .all()
    )

    start = _parse_dt(start_time)
    end = _parse_dt(end_time)
    findings: List[Dict[str, Any]] = []

    # Gazetteer built from the case's own location entities plus place words that
    # appear in the documents but nowhere in the location register -- those are
    # exactly the places a statement asserts but the records do not support.
    known_places = {e.label: e for e in entities.values() if e.entity_type == "LOCATION"}
    city_terms = set()
    for entity in known_places.values():
        city = (entity.properties or {}).get("city")
        if city:
            city_terms.add(city.lower())

    external_places = set()
    for doc in docs:
        for match in re.findall(r"\bin ([A-Z][a-z]+(?: [A-Z][a-z]+)?)\b", doc.extracted_text or ""):
            if match.lower() not in city_terms:
                external_places.add(match)

    # A label can belong to more than one entity id -- unresolved duplicates are
    # exactly that. Keyed by label, one would silently shadow the other, so keep
    # every candidate id per name.
    person_names: Dict[str, List[str]] = defaultdict(list)
    for eid, entity in entities.items():
        if entity.entity_type == "PERSON":
            person_names[entity.label].append(eid)

    # "A. Shahani" must not be treated as a sentence boundary, hence the guard
    # against splitting after a single capital letter.
    sentence_break = re.compile(r"(?<![A-Z])(?<=[.!?])\s+|\n\s*\n")
    # Only a statement of being somewhere counts. "filed in Delhi" is not an alibi.
    location_claim = re.compile(
        r"\b(?:was|were|is|are|remained|stayed|travelling|traveling)\b[^.]{0,40}?\bin\s+(%s)\b"
        % "|".join(re.escape(p) for p in external_places),
        re.IGNORECASE,
    ) if external_places else None

    for doc in docs:
        text = doc.extracted_text or ""
        doc_evidence = (doc.parsed_metadata or {}).get("evidence_id")

        date_match = re.search(r"\b(\d{1,2} [A-Z][a-z]+ \d{4})\b", text)
        asserted_day = None
        if date_match:
            try:
                asserted_day = datetime.strptime(date_match.group(1), "%d %B %Y").replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                asserted_day = None

        # Walk the document a sentence at a time, carrying the person last named.
        # In "I received a call from Mr Vikram Malhotra. He told me he was in Dubai
        # and asked me to hand the keys to Mr Rahul Sharma", the alibi belongs to
        # Vikram Malhotra. Attributing it to the other person named in the same
        # sentence would invent a contradiction that the document does not contain,
        # so the subject is taken from the nearest name *preceding* the claim.
        carried_subject: Optional[tuple] = None

        for sentence in sentence_break.split(text):
            sentence = " ".join(sentence.split())
            if not sentence:
                continue

            mentions = sorted(
                (sentence.index(name), name, ids)
                for name, ids in person_names.items()
                if name in sentence
            )

            if location_claim is not None:
                for claim in location_claim.finditer(sentence):
                    place = claim.group(1)
                    preceding = [m for m in mentions if m[0] < claim.start()]
                    subject = (preceding[-1][1], preceding[-1][2]) if preceding else carried_subject
                    if subject is None:
                        continue

                    name, candidate_ids = subject
                    # Where a name is carried by several unresolved entity records,
                    # test each: the contradiction attaches to whichever of them the
                    # records actually place somewhere at the relevant time.
                    for eid in candidate_ids:
                        if entity_ids and eid not in entity_ids:
                            continue

                        conflicting = []
                        for event in events:
                            if eid not in (event.related_entities or []):
                                continue
                            when = _aware(event.timestamp)
                            if asserted_day and not (
                                asserted_day <= when < asserted_day + timedelta(days=1)
                            ):
                                continue
                            if start and when < start:
                                continue
                            if end and when > end:
                                continue
                            if event.location_name:
                                conflicting.append(event)

                        if len(conflicting) < 2:
                            continue

                        findings.append(
                            {
                                "contradiction_type": "ASSERTED_LOCATION_AGAINST_RECORDS",
                                "entity_id": eid,
                                "entity_label": name,
                                "asserted": (
                                    f"{doc.title} records an account placing {name} in {place}"
                                    + (f" on {date_match.group(1)}" if date_match else "")
                                ),
                                "asserted_quote": sentence,
                                "asserted_source": {
                                    "document_id": doc.document_id,
                                    "title": doc.title,
                                    "evidence_id": doc_evidence,
                                },
                                "conflicting_records": [
                                    {
                                        "event_id": e.event_id,
                                        "title": e.title,
                                        "timestamp": _aware(e.timestamp).isoformat(),
                                        "location_name": e.location_name,
                                        "evidence_id": e.evidence_id,
                                    }
                                    for e in conflicting[:6]
                                ],
                                "record_types": sorted({e.event_type for e in conflicting}),
                                "assessment": (
                                    f"{len(conflicting)} records of "
                                    f"{len({e.event_type for e in conflicting})} different types place "
                                    f"{name} elsewhere during the same period. The account and the "
                                    "records cannot both be accurate."
                                ),
                                "alternative_explanations": [
                                    "The account may be mistaken about the date rather than untruthful.",
                                    "Device-based records establish the location of a device, not of a person.",
                                    "Identification in footage rests on staff recognition unless confirmed otherwise.",
                                ],
                            }
                        )

            if mentions:
                carried_subject = (mentions[-1][1], mentions[-1][2])

        # Documents that record the absence of an expected corroborating record.
        for sentence in sentence_break.split(text):
            sentence = " ".join(sentence.split())
            if re.search(r"\b(no|not|nor)\b.{0,60}\b(declaration|invoice|record|corroboration|filing)\b",
                         sentence, re.IGNORECASE):
                findings.append(
                    {
                        "contradiction_type": "ABSENCE_OF_EXPECTED_RECORD",
                        "entity_id": None,
                        "entity_label": None,
                        "asserted": sentence.strip(),
                        "asserted_source": {
                            "document_id": doc.document_id,
                            "title": doc.title,
                            "evidence_id": doc_evidence,
                        },
                        "conflicting_records": [],
                        "record_types": [],
                        "assessment": (
                            "A record that would be expected to exist has not been found. Absence "
                            "weakens a supporting account but is not itself proof of anything."
                        ),
                        "alternative_explanations": [
                            "The record may exist but not yet have been obtained.",
                            "It may have been filed by a different party or under a different reference.",
                        ],
                    }
                )
                break

    # Infeasible movement is a contradiction between two records.
    movement = detect_anomalies(db, ctx, case_id=case_id, entity_ids=entity_ids)
    for finding in movement["records"]:
        if finding["anomaly_type"] != "INFEASIBLE_MOVEMENT":
            continue
        findings.append(
            {
                "contradiction_type": "RECORDS_MUTUALLY_INCOMPATIBLE",
                "entity_id": finding["entities"][0],
                "entity_label": finding["labels"][0],
                "asserted": finding["observed"],
                "asserted_source": {"evidence_id": (finding.get("evidence_ids") or [None])[0]},
                "conflicting_records": [],
                "record_types": [],
                "assessment": finding["deviation"] + ". Both records cannot describe one person.",
                "alternative_explanations": finding["alternative_explanations"],
            }
        )

    if entity_ids:
        findings = [
            f for f in findings
            if f["entity_id"] is None or f["entity_id"] in entity_ids
        ]

    return {
        "records": findings,
        "provenance": [{"source": "document store and event store"}],
        "note": (
            ""
            if findings
            else "No contradicting material was found in scope. That is not the same as "
            "confirmation: it may mean the contradicting record has not been collected."
        ),
    }


def get_hypotheses(
    db: Session, ctx: AccessContext, case_id: Optional[str] = None, hypothesis_id: Optional[str] = None
) -> Dict[str, Any]:
    """Recorded hypotheses for a case."""
    cases = ctx.scope(case_id)
    if not cases:
        return _denied(case_id)

    query = db.query(Hypothesis).filter(Hypothesis.case_id.in_(cases))
    if hypothesis_id:
        query = query.filter(Hypothesis.hypothesis_id == hypothesis_id)

    return {
        "records": [
            {
                "hypothesis_id": h.hypothesis_id,
                "case_id": h.case_id,
                "title": h.title,
                "statement": h.statement,
                "status": h.status,
                "created_by": h.created_by,
                "notes": h.notes,
            }
            for h in query.all()
        ],
        "provenance": [{"source": "hypothesis register"}],
    }


def find_resolution_candidates(
    db: Session, ctx: AccessContext, case_id: Optional[str] = None
) -> Dict[str, Any]:
    """Entity pairs that may be the same real-world subject.

    Candidates only. Nothing is merged automatically: a wrong merge silently
    fabricates a connection that was never in the data.
    """
    cases = ctx.scope(case_id)
    if not cases:
        return _denied(case_id)

    rows = db.query(Entity).filter(Entity.case_id.in_(cases)).all()
    records = []
    for i, left in enumerate(rows):
        for right in rows[i + 1:]:
            if left.entity_type != right.entity_type:
                continue
            name_score = fuzz.token_sort_ratio(left.label.lower(), right.label.lower()) / 100.0
            alias_hit = bool(
                {a.lower() for a in (left.aliases or [])} & {right.label.lower()}
                or {a.lower() for a in (right.aliases or [])} & {left.label.lower()}
            )
            shared_attrs = [
                key
                for key in set(left.properties or {}) & set(right.properties or {})
                if key in ("pan", "dob", "phone") and left.properties[key] == right.properties[key]
            ]
            if name_score < 0.82 and not alias_hit and not shared_attrs:
                continue

            confidence = min(
                0.97, name_score * 0.6 + 0.25 * bool(alias_hit) + 0.12 * len(shared_attrs)
            )
            records.append(
                {
                    "left": _entity_brief(left),
                    "right": _entity_brief(right),
                    "match_confidence": round(confidence, 3),
                    "matching_attributes": shared_attrs,
                    "name_similarity": round(name_score, 3),
                    "recommendation": (
                        "Strong candidate. Confirm with an investigator before merging."
                        if confidence >= 0.85
                        else "Weak candidate. Do not merge without further identifying information."
                    ),
                }
            )

    records.sort(key=lambda r: -r["match_confidence"])
    return {
        "records": records,
        "provenance": [{"source": "entity register", "method": "name, alias and attribute comparison"}],
        "policy": "Candidates are never merged automatically. A merge requires investigator confirmation.",
    }


def compare_cases(
    db: Session, ctx: AccessContext, case_id_a: str, case_id_b: str
) -> Dict[str, Any]:
    """Side-by-side comparison of two investigations."""
    for case_id in (case_id_a, case_id_b):
        if not ctx.permits(case_id):
            return _denied(case_id)

    summary = {}
    for case_id in (case_id_a, case_id_b):
        case = db.query(Case).filter(Case.case_id == case_id).first()
        if case is None:
            return {"records": [], "provenance": [], "note": f"No case with id {case_id}."}
        entity_rows = db.query(Entity).filter(Entity.case_id == case_id).all()
        summary[case_id] = {
            "case_id": case_id,
            "title": case.title,
            "status": case.status,
            "entity_count": len(entity_rows),
            "event_count": db.query(Event).filter(Event.case_id == case_id).count(),
            "evidence_count": db.query(Evidence).filter(Evidence.case_id == case_id).count(),
            "entity_ids": {e.entity_id for e in entity_rows},
        }

    shared_direct = summary[case_id_a]["entity_ids"] & summary[case_id_b]["entity_ids"]

    # Entities whose records span both cases even where the register assigns them
    # to only one.
    spanning = find_cross_case_entities(db, ctx)
    spanning_ids = {
        r["entity_id"]
        for r in spanning["records"]
        if case_id_a in r["cases"] and case_id_b in r["cases"]
    }
    shared = sorted(shared_direct | spanning_ids)
    labels = _label_map(db, shared)

    for case_id in (case_id_a, case_id_b):
        summary[case_id].pop("entity_ids")

    return {
        "records": [
            {
                "case_a": summary[case_id_a],
                "case_b": summary[case_id_b],
                "shared_entities": [
                    {"entity_id": eid, "label": labels.get(eid, eid)} for eid in shared
                ],
                "shared_count": len(shared),
                "note": (
                    "Shared entities indicate where the two files touch. It is a reason to read "
                    "them together, not a conclusion about either."
                ),
            }
        ],
        "provenance": [{"source": "case, entity, event and evidence registers"}],
    }


def summarise_case(db: Session, ctx: AccessContext, case_id: str) -> Dict[str, Any]:
    """Counts and coverage for one case, including what is missing."""
    if not ctx.permits(case_id):
        return _denied(case_id)

    case = db.query(Case).filter(Case.case_id == case_id).first()
    if case is None:
        return {"records": [], "provenance": [], "note": f"No case with id {case_id}."}

    entities = db.query(Entity).filter(Entity.case_id == case_id).all()
    events = db.query(Event).filter(Event.case_id == case_id).order_by(Event.timestamp.asc()).all()
    by_type: Dict[str, int] = defaultdict(int)
    for entity in entities:
        by_type[entity.entity_type] += 1
    event_types: Dict[str, int] = defaultdict(int)
    for event in events:
        event_types[event.event_type] += 1

    # Gaps that can be established structurally.
    gaps = []
    unattributed = [
        e for e in entities
        if e.entity_type == "PHONE" and "subscriber_entity_id" not in (e.properties or {})
    ]
    for phone in unattributed:
        gaps.append(
            f"Handset {phone.label} appears in the call records but no subscriber has been established."
        )
    inferred = (
        db.query(Relationship)
        .filter(Relationship.case_id == case_id, Relationship.assertion_kind != "OBSERVED")
        .all()
    )
    for rel in inferred:
        gaps.append(
            f"Relationship {rel.rel_id} ({rel.rel_type}) is an analytical inference, not a "
            "directly recorded fact."
        )

    return {
        "records": [
            {
                "case_id": case.case_id,
                "title": case.title,
                "status": case.status,
                "classification": case.classification,
                "description": case.description,
                "lead_investigator": case.lead_investigator,
                "entity_counts": dict(by_type),
                "event_counts": dict(event_types),
                "evidence_count": db.query(Evidence).filter(Evidence.case_id == case_id).count(),
                "document_count": db.query(Document).filter(Document.case_id == case_id).count(),
                "first_event": _aware(events[0].timestamp).isoformat() if events else None,
                "last_event": _aware(events[-1].timestamp).isoformat() if events else None,
                "known_gaps": gaps,
            }
        ],
        "provenance": [{"source": "case registers"}],
    }


# ---------------------------------------------------------------------------
# Tool registry
#
# The schemas below are handed to the language model as callable function
# declarations. Adding a tool here makes it immediately available to the planner
# with no change to the planner itself.
# ---------------------------------------------------------------------------

@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Callable[..., Dict[str, Any]]


def _schema(properties: Dict[str, Any], required: Optional[List[str]] = None) -> Dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required or []}


_STR = {"type": "string"}
_NUM = {"type": "number"}
_STR_LIST = {"type": "array", "items": {"type": "string"}}

TOOLS: Dict[str, ToolSpec] = {
    "resolve_entity": ToolSpec(
        name="resolve_entity",
        description=(
            "Look up entities by name, alias, phone number or vehicle registration. Always call "
            "this first to turn a name mentioned by the investigator into an entity id. Returns "
            "several candidates when the term is ambiguous."
        ),
        parameters=_schema(
            {
                "query": {**_STR, "description": "Name, alias, number or registration to look up."},
                "entity_type": {
                    **_STR,
                    "description": "Optional filter: PERSON, PHONE, VEHICLE, ORGANIZATION, ACCOUNT, LOCATION, CASE.",
                },
            },
            ["query"],
        ),
        handler=resolve_entity,
    ),
    "get_entity_profile": ToolSpec(
        name="get_entity_profile",
        description="Everything recorded about one entity: attributes, relationships, events and evidence ids.",
        parameters=_schema({"entity_id": _STR}, ["entity_id"]),
        handler=get_entity_profile,
    ),
    "get_neighborhood": ToolSpec(
        name="get_neighborhood",
        description="Entities within N relationship hops of a given entity, with the connecting edges.",
        parameters=_schema(
            {"entity_id": _STR, "hops": {**_NUM, "description": "1 to 4. Default 1."}},
            ["entity_id"],
        ),
        handler=get_neighborhood,
    ),
    "find_paths": ToolSpec(
        name="find_paths",
        description=(
            "Shortest relationship chains between two entities. Use for questions about how two "
            "parties are connected."
        ),
        parameters=_schema({"source_id": _STR, "target_id": _STR, "max_hops": _NUM},
                           ["source_id", "target_id"]),
        handler=find_paths,
    ),
    "find_relationships": ToolSpec(
        name="find_relationships",
        description=(
            "Relationships filtered by participant, type and when they were first recorded. Use "
            "first_recorded_after to find connections that appeared only after a given moment, "
            "which is how to answer questions about what changed following an event."
        ),
        parameters=_schema(
            {
                "entity_ids": _STR_LIST,
                "rel_types": _STR_LIST,
                "first_recorded_after": {**_STR, "description": "ISO 8601 timestamp."},
                "first_recorded_before": {**_STR, "description": "ISO 8601 timestamp."},
                "case_id": _STR,
            }
        ),
        handler=find_relationships,
    ),
    "find_events": ToolSpec(
        name="find_events",
        description=(
            "Recorded events (calls, transactions, meetings, vehicle sightings) filtered by "
            "participant, type, time window, proximity to a point, or text. Use for questions "
            "about where someone was, what happened when, or what occurred at a place."
        ),
        parameters=_schema(
            {
                "entity_ids": _STR_LIST,
                "event_types": {
                    **_STR_LIST,
                    "description": "CALL, TRANSACTION, MEETING, VEHICLE_SIGHTING.",
                },
                "start_time": {**_STR, "description": "ISO 8601 timestamp."},
                "end_time": {**_STR, "description": "ISO 8601 timestamp."},
                "case_id": _STR,
                "near_latitude": _NUM,
                "near_longitude": _NUM,
                "radius_km": _NUM,
                "text_contains": _STR,
            }
        ),
        handler=find_events,
    ),
    "graph_analytics": ToolSpec(
        name="graph_analytics",
        description=(
            "Structural measures of the network: degree and betweenness centrality, PageRank, "
            "communities, and entities whose removal would fragment the network. Describes "
            "position in the recorded data only."
        ),
        parameters=_schema({"case_id": _STR}),
        handler=graph_analytics,
    ),
    "detect_anomalies": ToolSpec(
        name="detect_anomalies",
        description=(
            "Deviations from an observed baseline: communication surges, movement the timings "
            "cannot accommodate, and unusually large first transactions with a counterparty. Each "
            "finding carries its baseline and alternative explanations."
        ),
        parameters=_schema({"case_id": _STR, "entity_ids": _STR_LIST}),
        handler=detect_anomalies,
    ),
    "find_cross_case_entities": ToolSpec(
        name="find_cross_case_entities",
        description="Entities appearing in more than one authorised case.",
        parameters=_schema({}),
        handler=find_cross_case_entities,
    ),
    "search_documents": ToolSpec(
        name="search_documents",
        description=(
            "Search the text of case documents (reports, statements, transcripts, ledger "
            "extracts) and return the matching passages with their document and evidence ids."
        ),
        parameters=_schema({"query": _STR, "case_id": _STR}, ["query"]),
        handler=search_documents,
    ),
    "get_evidence": ToolSpec(
        name="get_evidence",
        description="Evidence records with integrity status and custody history.",
        parameters=_schema({"evidence_ids": _STR_LIST, "case_id": _STR}),
        handler=get_evidence,
    ),
    "verify_integrity": ToolSpec(
        name="verify_integrity",
        description=(
            "Rehash stored evidence artifacts and check them against the permissioned ledger. "
            "Use for any question about whether evidence has been altered."
        ),
        parameters=_schema({"evidence_ids": _STR_LIST, "case_id": _STR}),
        handler=verify_integrity,
    ),
    "osint_lookup": ToolSpec(
        name="osint_lookup",
        description=(
            "Public-source material held for an entity, with an analysis of how many genuinely "
            "independent sources it represents as opposed to repeated syndication of one report."
        ),
        parameters=_schema({"query": _STR, "entity_id": _STR, "case_id": _STR}, ["query"]),
        handler=osint_lookup,
    ),
    "find_contradictions": ToolSpec(
        name="find_contradictions",
        description=(
            "Search for material that cuts against the recorded picture: accounts contradicted by "
            "records, records incompatible with each other, and expected records that are absent. "
            "Call this before stating any significant conclusion."
        ),
        parameters=_schema(
            {"entity_ids": _STR_LIST, "case_id": _STR, "start_time": _STR, "end_time": _STR}
        ),
        handler=find_contradictions,
    ),
    "get_hypotheses": ToolSpec(
        name="get_hypotheses",
        description="Hypotheses recorded against a case and their status.",
        parameters=_schema({"case_id": _STR, "hypothesis_id": _STR}),
        handler=get_hypotheses,
    ),
    "find_resolution_candidates": ToolSpec(
        name="find_resolution_candidates",
        description=(
            "Entity pairs that may refer to the same real-world subject. Candidates only; nothing "
            "is merged without investigator confirmation."
        ),
        parameters=_schema({"case_id": _STR}),
        handler=find_resolution_candidates,
    ),
    "compare_cases": ToolSpec(
        name="compare_cases",
        description="Compare two investigations and list the entities they share.",
        parameters=_schema({"case_id_a": _STR, "case_id_b": _STR}, ["case_id_a", "case_id_b"]),
        handler=compare_cases,
    ),
    "summarise_case": ToolSpec(
        name="summarise_case",
        description=(
            "Counts, coverage and time span for a case, together with gaps that can be "
            "established structurally such as unattributed handsets and inferred relationships."
        ),
        parameters=_schema({"case_id": _STR}, ["case_id"]),
        handler=summarise_case,
    ),
}


def tool_declarations() -> List[Dict[str, Any]]:
    """Function declarations in the shape the model expects."""
    return [
        {"name": spec.name, "description": spec.description, "parameters": spec.parameters}
        for spec in TOOLS.values()
    ]


def execute_tool(
    db: Session, ctx: AccessContext, name: str, arguments: Dict[str, Any]
) -> Dict[str, Any]:
    """Run one tool with validated arguments."""
    spec = TOOLS.get(name)
    if spec is None:
        return {"error": f"No such tool: {name}", "records": [], "provenance": []}

    allowed = set(spec.parameters.get("properties", {}))
    cleaned = {k: v for k, v in (arguments or {}).items() if k in allowed and v not in (None, "")}

    missing = [r for r in spec.parameters.get("required", []) if r not in cleaned]
    if missing:
        return {
            "error": f"Tool {name} requires: {', '.join(missing)}",
            "records": [],
            "provenance": [],
        }

    try:
        return spec.handler(db, ctx, **cleaned)
    except TypeError as exc:
        return {"error": f"Invalid arguments for {name}: {exc}", "records": [], "provenance": []}
    except Exception as exc:  # noqa: BLE001 - surface tool failure to the planner
        return {"error": f"{name} failed: {exc}", "records": [], "provenance": []}
