"""Deterministic generator for the SPEMASS synthetic investigation dataset.

Everything in here is fictional. No real person, phone number, account or
organisation is represented.

Run:  python -m scripts.generate_dataset

Why generate rather than hand-write: anomaly detection is only meaningful against
a baseline, so the dataset needs several hundred routine communication and
transaction events for a quiet period before the events of interest. Those are
generated from a fixed seed so the output is byte-stable and reviewable in git.

Narrative -- Operation ShadowNet (CASE-2024-8812), a trade-based value-transfer
investigation, with an archived predecessor Operation Golden Falcon
(CASE-2023-1104) that shares two entities. The dataset deliberately contains:

  * a witness alibi contradicted by three independent record types
  * a quiet baseline followed by a communications surge
  * relationships that first appear only after a specific meeting
  * an entity duplicate pair requiring resolution rather than silent merging
  * OSINT reporting where many outlets derive from a single original
"""

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEED = 20240215
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "synthetic"

CASE_MAIN = "CASE-2024-8812"
CASE_ARCHIVE = "CASE-2023-1104"


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc(year, month, day, hour=0, minute=0, second=0) -> datetime:
    return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------

CASES = [
    {
        "case_id": CASE_MAIN,
        "title": "Operation ShadowNet",
        "description": (
            "Investigation into suspected trade-based value transfer routed through freight "
            "and logistics intermediaries in the Delhi NCR and Nhava Sheva corridors. Focus on "
            "the relationship between Zenith Holdings, Apex Global Logistics and an offshore "
            "counterparty in Zurich."
        ),
        "status": "ACTIVE",
        "classification": "RESTRICTED",
        "lead_investigator": "rajiv_sen",
        "created_at": "2024-02-18T09:00:00Z",
    },
    {
        "case_id": CASE_ARCHIVE,
        "title": "Operation Golden Falcon",
        "description": (
            "Archived investigation into undeclared consignments moving through Nhava Sheva "
            "port. Closed for want of corroboration in December 2023. Retained for cross-case "
            "reference."
        ),
        "status": "ARCHIVED",
        "classification": "CONFIDENTIAL",
        "lead_investigator": "admin",
        "created_at": "2023-08-02T09:00:00Z",
    },
]


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------

PERSONS = [
    ("ENT-PER-01", "Vikram Malhotra", ["Vicky", "V. Malhotra", "Vikram M"],
     {"role": "Director, Zenith Holdings", "pan": "SYNTH-PAN-0001", "dob": "1974-03-11"}),
    ("ENT-PER-02", "Amit Shahani", ["Amit S.", "A. Shahani"],
     {"role": "Finance Director, Apex Global Logistics", "pan": "SYNTH-PAN-0002", "dob": "1979-11-02"}),
    ("ENT-PER-03", "Rahul Sharma", ["Rahul S."],
     {"role": "Courier and transport coordinator", "pan": "SYNTH-PAN-0003", "dob": "1988-06-24"}),
    ("ENT-PER-04", "Rahul Verma", ["R. Verma"],
     {"role": "Telecom retail associate", "pan": "SYNTH-PAN-0004", "dob": "1991-01-15"}),
    ("ENT-PER-05", "Karan Mehra", ["Karan"],
     {"role": "Driver, Zenith Holdings", "pan": "SYNTH-PAN-0005", "dob": "1985-09-30"}),
    ("ENT-PER-06", "Priya Nair", ["P. Nair"],
     {"role": "External accountant", "pan": "SYNTH-PAN-0006", "dob": "1983-04-19"}),
    ("ENT-PER-07", "Sanjay Gupta", ["S. Gupta", "Sanjay G"],
     {"role": "Licensed customs clearing agent", "pan": "SYNTH-PAN-0007", "dob": "1971-12-05"}),
    ("ENT-PER-08", "Imran Sheikh", ["Imran S."],
     {"role": "Port logistics fixer", "pan": "SYNTH-PAN-0008", "dob": "1980-07-08"}),
    ("ENT-PER-09", "Neha Kapoor", ["N. Kapoor"],
     {"role": "Nominee director", "pan": "SYNTH-PAN-0009", "dob": "1990-02-27"}),
    ("ENT-PER-10", "Farhan Qureshi", ["F. Qureshi"],
     {"role": "Wharf supervisor", "pan": "SYNTH-PAN-0010", "dob": "1977-05-14"}),
    # Deliberate near-duplicate of ENT-PER-01 sourced from a separate record system.
    # Entity resolution must surface this as a candidate, not merge it silently.
    ("ENT-PER-11", "Vikram Malhotra", ["Vikram Malhothra"],
     {"role": "Director (record sourced from corporate registry extract)",
      "pan": "SYNTH-PAN-0001", "dob": "1974-03-11",
      "source_system": "Registrar of Companies extract"}),
]

PHONES = [
    ("ENT-PH-01", "+91-98110-22331", "ENT-PER-01", "Synthetic Telecom North"),
    ("ENT-PH-02", "+91-98220-33442", "ENT-PER-02", "Synthetic Telecom West"),
    ("ENT-PH-03", "+91-98711-44553", "ENT-PER-03", "Synthetic Telecom North"),
    ("ENT-PH-04", "+91-98100-77889", "ENT-PER-04", "Synthetic Telecom North"),
    ("ENT-PH-05", "+91-98110-99882", "ENT-PER-05", "Synthetic Telecom North"),
    ("ENT-PH-06", "+91-98330-11220", "ENT-PER-06", "Synthetic Telecom West"),
    ("ENT-PH-07", "+91-98450-66771", "ENT-PER-07", "Synthetic Telecom South"),
    ("ENT-PH-08", "+91-98330-99881", "ENT-PER-08", "Synthetic Telecom West"),
    # Unattributed handset -- an intentional evidence gap the Copilot should report.
    ("ENT-PH-09", "+91-99000-11223", None, "Synthetic Telecom North"),
]

VEHICLES = [
    ("ENT-VEH-01", "DL-04-E-5544", {"model": "Sport utility vehicle, black", "registered_to": "Zenith Holdings Pvt Ltd"}),
    ("ENT-VEH-02", "MH-02-CP-8811", {"model": "Executive saloon, silver", "registered_to": "Apex Global Logistics"}),
    ("ENT-VEH-03", "HR-26-BQ-1109", {"model": "Panel van, white", "registered_to": "Rahul Sharma"}),
]

ORGS = [
    ("ENT-ORG-01", "Zenith Holdings Pvt Ltd",
     {"jurisdiction": "New Delhi, India", "type": "Private limited company", "incorporated": "2019-06-11"}),
    ("ENT-ORG-02", "Apex Global Logistics",
     {"jurisdiction": "Mumbai, India", "type": "Freight forwarding", "incorporated": "2016-02-03"}),
    ("ENT-ORG-03", "Alpine Holdings AG",
     {"jurisdiction": "Zurich, Switzerland", "type": "Holding company", "incorporated": "2021-09-28"}),
    ("ENT-ORG-04", "Golden Falcon Wharf Logistics",
     {"jurisdiction": "Navi Mumbai, India", "type": "Port handling", "incorporated": "2014-04-22"}),
    ("ENT-ORG-05", "Meridian Trade FZE",
     {"jurisdiction": "Free zone, offshore", "type": "Trading", "incorporated": "2022-01-17"}),
]

ACCOUNTS = [
    ("ENT-ACC-01", "Account 10110 (Zenith Holdings)", {"bank": "Synthetic Metro National Bank", "currency": "INR"}),
    ("ENT-ACC-02", "Account 99218 (Apex Global Logistics)", {"bank": "Synthetic Metro National Bank", "currency": "USD"}),
    ("ENT-ACC-03", "Account SW-77 (Alpine Holdings AG)", {"bank": "Synthetic Cantonal Bank", "currency": "USD"}),
    ("ENT-ACC-04", "Account 44821 (Meridian Trade FZE)", {"bank": "Synthetic Gulf Commercial Bank", "currency": "USD"}),
    ("ENT-ACC-05", "Account 30294 (Golden Falcon Wharf)", {"bank": "Synthetic Metro National Bank", "currency": "INR"}),
]

LOCATIONS = [
    ("ENT-LOC-01", "Hotel Grand Palace, Aerocity", 28.5504, 77.1210, {"city": "New Delhi"}),
    ("ENT-LOC-02", "Connaught Place commercial block", 28.6315, 77.2167, {"city": "New Delhi"}),
    ("ENT-LOC-03", "Nhava Sheva container terminal", 18.9496, 72.9510, {"city": "Navi Mumbai"}),
    ("ENT-LOC-04", "Kherki Daula toll plaza", 28.4032, 76.9930, {"city": "Gurugram"}),
    ("ENT-LOC-05", "Khan Market", 28.6000, 77.2270, {"city": "New Delhi"}),
    ("ENT-LOC-06", "Okhla industrial warehouse", 28.5355, 77.2730, {"city": "New Delhi"}),
    ("ENT-LOC-07", "Zenith Holdings registered office", 28.6280, 77.2190, {"city": "New Delhi"}),
    ("ENT-LOC-08", "Indira Gandhi International Airport", 28.5562, 77.0999, {"city": "New Delhi"}),
]

# Cell towers used for call geolocation.
TOWERS = {
    "DEL-TOW-508": (28.5504, 77.1210, "Aerocity tower DEL-TOW-508"),
    "DEL-TOW-114": (28.6315, 77.2167, "Connaught Place tower DEL-TOW-114"),
    "DEL-TOW-233": (28.6000, 77.2270, "Khan Market tower DEL-TOW-233"),
    "DEL-TOW-407": (28.5355, 77.2730, "Okhla tower DEL-TOW-407"),
    "MUM-TOW-901": (18.9496, 72.9510, "Nhava Sheva tower MUM-TOW-901"),
    "GUR-TOW-062": (28.4032, 76.9930, "Kherki Daula tower GUR-TOW-062"),
}


def build_entities():
    entities = []

    for case in CASES:
        entities.append({
            "entity_id": case["case_id"],
            "case_id": case["case_id"],
            "label": case["title"],
            "entity_type": "CASE",
            "aliases": [],
            "properties": {"status": case["status"]},
        })

    for eid, label, aliases, props in PERSONS:
        case = CASE_ARCHIVE if eid == "ENT-PER-10" else CASE_MAIN
        entities.append({
            "entity_id": eid, "case_id": case, "label": label,
            "entity_type": "PERSON", "aliases": aliases, "properties": props,
        })

    for eid, number, owner, carrier in PHONES:
        props = {"carrier": carrier}
        if owner:
            props["subscriber_entity_id"] = owner
        else:
            props["subscriber"] = "Unregistered prepaid connection - subscriber not established"
        entities.append({
            "entity_id": eid, "case_id": CASE_MAIN, "label": number,
            "entity_type": "PHONE", "aliases": [number.replace("-", "")], "properties": props,
        })

    for eid, plate, props in VEHICLES:
        entities.append({
            "entity_id": eid, "case_id": CASE_MAIN, "label": plate,
            "entity_type": "VEHICLE", "aliases": [plate.replace("-", "")], "properties": props,
        })

    for eid, label, props in ORGS:
        case = CASE_ARCHIVE if eid == "ENT-ORG-04" else CASE_MAIN
        entities.append({
            "entity_id": eid, "case_id": case, "label": label,
            "entity_type": "ORGANIZATION", "aliases": [], "properties": props,
        })

    for eid, label, props in ACCOUNTS:
        entities.append({
            "entity_id": eid, "case_id": CASE_MAIN, "label": label,
            "entity_type": "ACCOUNT", "aliases": [], "properties": props,
        })

    for eid, label, lat, lon, props in LOCATIONS:
        entities.append({
            "entity_id": eid, "case_id": CASE_MAIN, "label": label,
            "entity_type": "LOCATION", "aliases": [], "properties": props,
            "latitude": lat, "longitude": lon,
        })

    return entities


# ---------------------------------------------------------------------------
# Relationships
#
# valid_from is the date the relationship is first supported by a record. It is
# what makes "which relationships appeared only after the 14 February meeting"
# a question the system can actually answer from data.
# ---------------------------------------------------------------------------

def build_relationships():
    rels = []

    def add(rel_id, src, tgt, rel_type, valid_from, confidence=0.95,
            evidence_ids=None, kind="OBSERVED", case=CASE_MAIN, props=None):
        rels.append({
            "rel_id": rel_id, "case_id": case, "source_id": src, "target_id": tgt,
            "rel_type": rel_type, "confidence": confidence, "assertion_kind": kind,
            "evidence_ids": evidence_ids or [], "valid_from": valid_from,
            "properties": props or {},
        })

    # Phone attribution
    for i, (ph_id, _num, owner, _c) in enumerate(PHONES, start=1):
        if owner:
            add(f"R-PH-{i:02d}", owner, ph_id, "USED", "2024-01-01T00:00:00Z", 0.97, ["EVID-CDR-01"])

    # Employment / control
    add("R-EMP-01", "ENT-PER-01", "ENT-ORG-01", "WORKS_FOR", "2019-06-11T00:00:00Z", 0.98, ["EVID-DOC-FIR-01"])
    add("R-EMP-02", "ENT-PER-02", "ENT-ORG-02", "WORKS_FOR", "2016-02-03T00:00:00Z", 0.98, ["EVID-DOC-FIR-01"])
    add("R-EMP-03", "ENT-PER-05", "ENT-ORG-01", "WORKS_FOR", "2021-03-01T00:00:00Z", 0.95, ["EVID-DOC-WITNESS-01"])
    add("R-EMP-04", "ENT-PER-09", "ENT-ORG-05", "WORKS_FOR", "2022-01-17T00:00:00Z", 0.90, ["EVID-OSINT-0011"])
    add("R-EMP-05", "ENT-PER-10", "ENT-ORG-04", "WORKS_FOR", "2014-04-22T00:00:00Z", 0.92,
        ["EVID-DOC-ARCHIVE-01"], case=CASE_ARCHIVE)

    add("R-CTL-01", "ENT-ORG-01", "ENT-ACC-01", "CONTROLS", "2019-06-11T00:00:00Z", 0.99, ["EVID-BANK-01"])
    add("R-CTL-02", "ENT-ORG-02", "ENT-ACC-02", "CONTROLS", "2016-02-03T00:00:00Z", 0.99, ["EVID-BANK-01"])
    add("R-CTL-03", "ENT-ORG-03", "ENT-ACC-03", "CONTROLS", "2021-09-28T00:00:00Z", 0.93, ["EVID-BANK-01"])
    add("R-CTL-04", "ENT-ORG-05", "ENT-ACC-04", "CONTROLS", "2022-01-17T00:00:00Z", 0.88, ["EVID-BANK-02"])
    add("R-CTL-05", "ENT-ORG-04", "ENT-ACC-05", "CONTROLS", "2014-04-22T00:00:00Z", 0.90,
        ["EVID-DOC-ARCHIVE-01"], case=CASE_ARCHIVE)

    # Vehicles
    add("R-VEH-01", "ENT-PER-01", "ENT-VEH-01", "USED", "2024-01-04T00:00:00Z", 0.94, ["EVID-TOLL-01", "EVID-CCTV-01"])
    add("R-VEH-02", "ENT-ORG-01", "ENT-VEH-01", "OWNED", "2021-08-19T00:00:00Z", 0.99, ["EVID-DOC-FIR-01"])
    add("R-VEH-03", "ENT-PER-03", "ENT-VEH-03", "OWNED", "2022-11-02T00:00:00Z", 0.96, ["EVID-TOLL-01"])
    add("R-VEH-04", "ENT-PER-05", "ENT-VEH-01", "DROVE", "2024-01-04T00:00:00Z", 0.91, ["EVID-DOC-WITNESS-01"])

    # Pre-existing associations, established well before the meeting
    add("R-ASC-01", "ENT-PER-01", "ENT-PER-02", "ASSOCIATED_WITH", "2023-11-14T00:00:00Z", 0.93,
        ["EVID-CDR-01", "EVID-CCTV-01"])
    add("R-ASC-02", "ENT-PER-01", "ENT-PER-03", "ASSOCIATED_WITH", "2023-12-02T00:00:00Z", 0.88, ["EVID-CDR-01"])
    add("R-ASC-03", "ENT-PER-03", "ENT-PER-04", "ASSOCIATED_WITH", "2024-01-09T00:00:00Z", 0.81, ["EVID-CDR-01"])
    add("R-ASC-04", "ENT-PER-01", "ENT-PER-05", "ASSOCIATED_WITH", "2021-03-01T00:00:00Z", 0.95,
        ["EVID-DOC-WITNESS-01"])

    # Relationships first recorded only AFTER the 14 February meeting.
    add("R-NEW-01", "ENT-PER-02", "ENT-PER-06", "COMMUNICATED_WITH", "2024-02-16T10:12:00Z", 0.87, ["EVID-CDR-01"])
    add("R-NEW-02", "ENT-PER-01", "ENT-PER-07", "COMMUNICATED_WITH", "2024-02-17T11:48:00Z", 0.89, ["EVID-CDR-01"])
    add("R-NEW-03", "ENT-PER-03", "ENT-PER-08", "COMMUNICATED_WITH", "2024-02-19T09:05:00Z", 0.84, ["EVID-CDR-01"])
    add("R-NEW-04", "ENT-ORG-02", "ENT-ORG-05", "TRANSFERRED_TO", "2024-02-21T14:30:00Z", 0.90, ["EVID-BANK-02"])
    add("R-NEW-05", "ENT-PER-06", "ENT-ORG-05", "WORKS_FOR", "2024-02-22T00:00:00Z", 0.72,
        ["EVID-OSINT-0011"], kind="INFERRED")

    # Financial flows
    add("R-FIN-01", "ENT-ACC-01", "ENT-ACC-02", "TRANSFERRED_TO", "2024-02-11T10:00:00Z", 0.99,
        ["EVID-BANK-01"], props={"amount_usd": 50000})
    add("R-FIN-02", "ENT-ACC-02", "ENT-ACC-03", "TRANSFERRED_TO", "2024-02-15T09:15:00Z", 0.99,
        ["EVID-BANK-01"], props={"amount_usd": 250000})
    add("R-FIN-03", "ENT-ACC-02", "ENT-ACC-04", "TRANSFERRED_TO", "2024-02-21T14:30:00Z", 0.97,
        ["EVID-BANK-02"], props={"amount_usd": 180000})

    # Locations
    add("R-LOC-01", "ENT-ORG-01", "ENT-LOC-07", "LOCATED_AT", "2019-06-11T00:00:00Z", 0.99, ["EVID-DOC-FIR-01"])
    add("R-LOC-02", "ENT-PER-01", "ENT-LOC-03", "RECORDED_AT", "2023-08-20T14:00:00Z", 0.94,
        ["EVID-CDR-ARCHIVE-01"], case=CASE_ARCHIVE)
    add("R-LOC-03", "ENT-PER-08", "ENT-LOC-03", "RECORDED_AT", "2023-08-14T09:20:00Z", 0.92,
        ["EVID-CDR-ARCHIVE-01"], case=CASE_ARCHIVE)

    # Case membership
    for pid in ["ENT-PER-01", "ENT-PER-02", "ENT-PER-03", "ENT-PER-04", "ENT-PER-05",
                "ENT-PER-06", "ENT-PER-07", "ENT-PER-08", "ENT-PER-09"]:
        add(f"R-CASE-{pid[-2:]}", pid, CASE_MAIN, "INVOLVED_IN", "2024-02-18T09:00:00Z", 1.0, ["EVID-DOC-FIR-01"])

    # Cross-case membership: two entities appear in both investigations.
    add("R-XCASE-01", "ENT-PER-01", CASE_ARCHIVE, "INVOLVED_IN", "2023-08-02T09:00:00Z", 0.95,
        ["EVID-DOC-ARCHIVE-01"], case=CASE_ARCHIVE)
    add("R-XCASE-02", "ENT-PER-08", CASE_ARCHIVE, "INVOLVED_IN", "2023-08-02T09:00:00Z", 0.93,
        ["EVID-DOC-ARCHIVE-01"], case=CASE_ARCHIVE)
    add("R-XCASE-03", "ENT-PER-10", CASE_ARCHIVE, "INVOLVED_IN", "2023-08-02T09:00:00Z", 0.90,
        ["EVID-DOC-ARCHIVE-01"], case=CASE_ARCHIVE)
    add("R-XCASE-04", "ENT-PER-08", CASE_MAIN, "INVOLVED_IN", "2024-02-19T09:05:00Z", 0.84,
        ["EVID-CDR-01"])

    return rels


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

def build_events():
    rng = random.Random(SEED)
    events = []
    seq = {"call": 0, "tx": 0, "toll": 0}

    def call_event(when, a_person, a_phone, b_person, b_phone, tower, duration, summary,
                   confidence=0.98, case=CASE_MAIN, evidence="EVID-CDR-01", event_type="CALL"):
        seq["call"] += 1
        lat, lon, name = TOWERS[tower]
        a_label = next(p[1] for p in PERSONS if p[0] == a_person)
        b_label = next((p[1] for p in PERSONS if p[0] == b_person), "unattributed handset")
        events.append({
            "event_id": f"EVT-CALL-{seq['call']:04d}",
            "case_id": case,
            "title": f"Call: {a_label} to {b_label}",
            "event_type": event_type,
            "timestamp": iso(when),
            "location_name": name,
            "latitude": lat, "longitude": lon,
            "related_entities": [e for e in [a_person, a_phone, b_person, b_phone] if e],
            "evidence_id": evidence,
            "summary": summary,
            "confidence": confidence,
            "properties": {"duration_seconds": duration, "cell_tower": tower},
        })

    # --- Baseline period: 1 January to 9 February -------------------------
    # Routine, low-volume contact between pairs already known to each other.
    baseline_pairs = [
        ("ENT-PER-01", "ENT-PH-01", "ENT-PER-02", "ENT-PH-02", 0.55),
        ("ENT-PER-01", "ENT-PH-01", "ENT-PER-03", "ENT-PH-03", 0.40),
        ("ENT-PER-01", "ENT-PH-01", "ENT-PER-05", "ENT-PH-05", 0.65),
        ("ENT-PER-03", "ENT-PH-03", "ENT-PER-04", "ENT-PH-04", 0.30),
        ("ENT-PER-02", "ENT-PH-02", "ENT-PER-03", "ENT-PH-03", 0.25),
    ]
    towers_pool = ["DEL-TOW-114", "DEL-TOW-233", "DEL-TOW-407"]

    day = utc(2024, 1, 1)
    while day < utc(2024, 2, 10):
        for a_p, a_ph, b_p, b_ph, rate in baseline_pairs:
            if rng.random() < rate:
                for _ in range(rng.choice([1, 1, 1, 2])):
                    when = day + timedelta(
                        hours=rng.randint(9, 20), minutes=rng.randint(0, 59), seconds=rng.randint(0, 59)
                    )
                    call_event(
                        when, a_p, a_ph, b_p, b_ph, rng.choice(towers_pool),
                        rng.randint(25, 240),
                        "Routine contact recorded in call detail records. No content is available; "
                        "metadata only.",
                        confidence=0.97,
                    )
        day += timedelta(days=1)

    # --- Surge period: 12 to 16 February ----------------------------------
    # A marked increase over the baseline. Reported as a deviation, never as guilt.
    day = utc(2024, 2, 12)
    while day < utc(2024, 2, 17):
        for a_p, a_ph, b_p, b_ph, _rate in baseline_pairs[:3]:
            for _ in range(rng.randint(3, 6)):
                when = day + timedelta(
                    hours=rng.randint(7, 23), minutes=rng.randint(0, 59), seconds=rng.randint(0, 59)
                )
                call_event(
                    when, a_p, a_ph, b_p, b_ph, rng.choice(towers_pool),
                    rng.randint(40, 420),
                    "Contact recorded during the period of elevated communication volume.",
                    confidence=0.97,
                )
        day += timedelta(days=1)

    # --- Anchor events of investigative interest --------------------------
    call_event(utc(2024, 2, 10, 11, 20), "ENT-PER-01", "ENT-PH-01", "ENT-PER-02", "ENT-PH-02",
               "DEL-TOW-114", 145,
               "Call of 145 seconds routed via the Connaught Place tower. Content unavailable.")

    events.append({
        "event_id": "EVT-TX-0001",
        "case_id": CASE_MAIN,
        "title": "Transfer of USD 50,000 from Zenith Holdings to Apex Global Logistics",
        "event_type": "TRANSACTION",
        "timestamp": "2024-02-11T10:00:00Z",
        "location_name": "Synthetic Metro National Bank, New Delhi",
        "latitude": 28.6315, "longitude": 77.2167,
        "related_entities": ["ENT-ORG-01", "ENT-ORG-02", "ENT-ACC-01", "ENT-ACC-02"],
        "evidence_id": "EVID-BANK-01",
        "summary": "Inter-company transfer of USD 50,000 recorded in the bank ledger extract.",
        "confidence": 0.99,
        "properties": {"amount_usd": 50000, "reference": "TX-9871"},
    })

    events.append({
        "event_id": "EVT-TOLL-0001",
        "case_id": CASE_MAIN,
        "title": "Number plate reader: DL-04-E-5544 northbound",
        "event_type": "VEHICLE_SIGHTING",
        "timestamp": "2024-02-14T18:40:00Z",
        "location_name": "Kherki Daula toll plaza",
        "latitude": 28.4032, "longitude": 76.9930,
        "related_entities": ["ENT-VEH-01", "ENT-PER-01"],
        "evidence_id": "EVID-TOLL-01",
        "summary": ("Automatic number plate recognition recorded vehicle DL-04-E-5544 travelling "
                    "northbound towards Delhi. The reader captures the plate, not the occupants."),
        "confidence": 0.96,
        "properties": {"direction": "northbound", "lane": 4},
    })

    events.append({
        "event_id": "EVT-MEET-0001",
        "case_id": CASE_MAIN,
        "title": "Recorded meeting: Vikram Malhotra and Amit Shahani",
        "event_type": "MEETING",
        "timestamp": "2024-02-14T19:30:00Z",
        "location_name": "Hotel Grand Palace, Aerocity",
        "latitude": 28.5504, "longitude": 77.1210,
        "related_entities": ["ENT-PER-01", "ENT-PER-02", "ENT-VEH-01", "ENT-LOC-01"],
        "evidence_id": "EVID-CCTV-01",
        "summary": ("Closed circuit footage transcript records two individuals identified by hotel "
                    "staff as Vikram Malhotra and Amit Shahani seated together in the lounge from "
                    "19:30 to 20:45. An item described as a tablet device passes between them."),
        "confidence": 0.94,
        "properties": {"duration_minutes": 75, "identification_basis": "staff identification plus vehicle match"},
    })

    call_event(utc(2024, 2, 14, 19, 34, 10), "ENT-PER-01", "ENT-PH-01", "ENT-PER-02", "ENT-PH-02",
               "DEL-TOW-508", 320,
               "Call of 320 seconds. Both handsets registered to the Aerocity tower at the time of "
               "the recorded meeting. This places both handsets in Delhi, contradicting the alibi "
               "recorded in the driver's statement.",
               confidence=0.99)

    events.append({
        "event_id": "EVT-TOLL-0002",
        "case_id": CASE_MAIN,
        "title": "Number plate reader: DL-04-E-5544 southbound",
        "event_type": "VEHICLE_SIGHTING",
        "timestamp": "2024-02-14T21:10:00Z",
        "location_name": "Kherki Daula toll plaza",
        "latitude": 28.4032, "longitude": 76.9930,
        "related_entities": ["ENT-VEH-01", "ENT-PER-01"],
        "evidence_id": "EVID-TOLL-01",
        "summary": "Vehicle DL-04-E-5544 recorded travelling southbound after the Aerocity meeting.",
        "confidence": 0.96,
        "properties": {"direction": "southbound", "lane": 2},
    })

    events.append({
        "event_id": "EVT-TX-0002",
        "case_id": CASE_MAIN,
        "title": "Wire transfer of USD 250,000 to Alpine Holdings AG, Zurich",
        "event_type": "TRANSACTION",
        "timestamp": "2024-02-15T09:15:00Z",
        "location_name": "Synthetic Metro National Bank, New Delhi",
        "latitude": 28.6315, "longitude": 77.2167,
        "related_entities": ["ENT-ORG-02", "ENT-ORG-03", "ENT-ACC-02", "ENT-ACC-03", "ENT-PER-02"],
        "evidence_id": "EVID-BANK-01",
        "summary": ("Outward wire transfer of USD 250,000 authorised on the Apex Global Logistics "
                    "account, beneficiary Alpine Holdings AG, Zurich. The ledger extract names the "
                    "authorising officer as Amit Shahani."),
        "confidence": 0.99,
        "properties": {"amount_usd": 250000, "reference": "TX-9902", "beneficiary_country": "Switzerland"},
    })

    # New contacts appearing only after the meeting
    call_event(utc(2024, 2, 16, 10, 12), "ENT-PER-02", "ENT-PH-02", "ENT-PER-06", "ENT-PH-06",
               "DEL-TOW-114", 268, "First recorded contact between these two handsets.")
    call_event(utc(2024, 2, 17, 11, 48), "ENT-PER-01", "ENT-PH-01", "ENT-PER-07", "ENT-PH-07",
               "DEL-TOW-407", 412, "First recorded contact between these two handsets.")
    call_event(utc(2024, 2, 19, 9, 5), "ENT-PER-03", "ENT-PH-03", "ENT-PER-08", "ENT-PH-08",
               "MUM-TOW-901", 190, "First recorded contact between these two handsets.")

    # The caller's handset registers on the caller's own tower, so this Delhi-to-Mumbai
    # call is recorded at a Delhi tower. Getting this wrong would manufacture a
    # spurious impossible-travel finding.
    call_event(utc(2024, 2, 17, 12, 10), "ENT-PER-01", "ENT-PH-01", "ENT-PER-08", "ENT-PH-08",
               "DEL-TOW-407", 290,
               "Call to a handset at the Nhava Sheva terminal concerning container handling.")

    # Unattributed handset contact -- a deliberate evidence gap.
    call_event(utc(2024, 2, 18, 22, 41), "ENT-PER-01", "ENT-PH-01", None, "ENT-PH-09",
               "DEL-TOW-407", 95,
               "Contact with an unregistered prepaid connection. The subscriber has not been "
               "established, so no person can be attributed to this handset.",
               confidence=0.88)

    events.append({
        "event_id": "EVT-TX-0003",
        "case_id": CASE_MAIN,
        "title": "Transfer of USD 180,000 to Meridian Trade FZE",
        "event_type": "TRANSACTION",
        "timestamp": "2024-02-21T14:30:00Z",
        "location_name": "Synthetic Metro National Bank, New Delhi",
        "latitude": 28.6315, "longitude": 77.2167,
        "related_entities": ["ENT-ORG-02", "ENT-ORG-05", "ENT-ACC-02", "ENT-ACC-04"],
        "evidence_id": "EVID-BANK-02",
        "summary": "Outward transfer of USD 180,000 to a counterparty with no prior transaction history "
                   "on this account.",
        "confidence": 0.97,
        "properties": {"amount_usd": 180000, "reference": "TX-9944"},
    })

    # Impossible-travel pair: two handset registrations too far apart in too little time.
    call_event(utc(2024, 2, 20, 8, 15), "ENT-PER-03", "ENT-PH-03", "ENT-PER-01", "ENT-PH-01",
               "DEL-TOW-407", 60,
               "Handset ENT-PH-03 registered to a Delhi tower.")
    call_event(utc(2024, 2, 20, 9, 5), "ENT-PER-03", "ENT-PH-03", "ENT-PER-08", "ENT-PH-08",
               "MUM-TOW-901", 75,
               "Handset ENT-PH-03 registered to a Nhava Sheva tower fifty minutes after a Delhi "
               "registration. The two towers are roughly 1,150 km apart.")

    # Archived case events
    call_event(utc(2023, 8, 14, 9, 20), "ENT-PER-08", "ENT-PH-08", "ENT-PER-10", "ENT-PH-08",
               "MUM-TOW-901", 210, "Archived call record from Operation Golden Falcon.",
               case=CASE_ARCHIVE, evidence="EVID-CDR-ARCHIVE-01", event_type="CALL")
    call_event(utc(2023, 8, 20, 14, 0), "ENT-PER-01", "ENT-PH-01", "ENT-PER-08", "ENT-PH-08",
               "MUM-TOW-901", 340,
               "Archived call record placing this handset at the Nhava Sheva terminal during the "
               "earlier investigation.",
               case=CASE_ARCHIVE, evidence="EVID-CDR-ARCHIVE-01")

    events.sort(key=lambda e: e["timestamp"])
    return events


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

DOCUMENTS = [
    {
        "document_id": "DOC-FIR-2024-001",
        "case_id": CASE_MAIN,
        "evidence_id": "EVID-DOC-FIR-01",
        "filename": "fir_8812_2024.txt",
        "title": "First information report 8812/2024",
        "file_type": "REPORT",
        "uploaded_by": "rajiv_sen",
        "created_at": "2024-02-18T09:15:00Z",
        "extracted_text": (
            "FIRST INFORMATION REPORT 8812/2024\n"
            "Registered 18 February 2024.\n\n"
            "A complaint received from the financial intelligence desk reports that Zenith Holdings "
            "Pvt Ltd, registered at a commercial address in New Delhi and having Vikram Malhotra as "
            "its director, transferred funds to Apex Global Logistics on 11 February 2024. Apex "
            "Global Logistics, whose finance director is Amit Shahani, subsequently remitted USD "
            "250,000 to Alpine Holdings AG in Zurich on 15 February 2024.\n\n"
            "Vehicle DL-04-E-5544 is registered to Zenith Holdings Pvt Ltd.\n\n"
            "The complaint does not establish the purpose of either transfer. No determination of "
            "wrongdoing has been made. Investigation is directed towards establishing the "
            "commercial basis, if any, for the remittance."
        ),
    },
    {
        "document_id": "DOC-WITNESS-2024-002",
        "case_id": CASE_MAIN,
        "evidence_id": "EVID-DOC-WITNESS-01",
        "filename": "witness_statement_mehra.txt",
        "title": "Witness statement of Karan Mehra, driver",
        "file_type": "STATEMENT",
        "uploaded_by": "rajiv_sen",
        "created_at": "2024-02-20T14:00:00Z",
        "extracted_text": (
            "STATEMENT OF KARAN MEHRA, RECORDED 20 FEBRUARY 2024\n\n"
            "I am employed as a driver by Zenith Holdings. On 14 February 2024 I received a "
            "telephone call from Mr Vikram Malhotra. He told me he was in Dubai and asked me to "
            "hand the keys of vehicle DL-04-E-5544 to Mr Rahul Sharma. I did so at about five in "
            "the evening. I did not see Mr Malhotra at any time that day.\n\n"
            "I do not know where the vehicle went afterwards."
        ),
    },
    {
        "document_id": "DOC-CCTV-2024-014",
        "case_id": CASE_MAIN,
        "evidence_id": "EVID-CCTV-01",
        "filename": "cctv_transcript_aerocity.txt",
        "title": "Closed circuit footage transcript, Hotel Grand Palace Aerocity",
        "file_type": "TRANSCRIPT",
        "uploaded_by": "tech_forensics",
        "created_at": "2024-02-19T11:00:00Z",
        "extracted_text": (
            "TRANSCRIPT OF CLOSED CIRCUIT FOOTAGE\n"
            "Location: Hotel Grand Palace, Aerocity. Date: 14 February 2024.\n\n"
            "19:15 Camera 4. A dark sport utility vehicle bearing registration DL-04-E-5544 enters "
            "the forecourt. One male occupant leaves the vehicle and enters the lobby.\n"
            "19:30 Camera 9. The same individual is seated at table 12 in the lounge with a second "
            "male. Hotel duty staff identified the two, on being shown the footage, as Vikram "
            "Malhotra and Amit Shahani. The identification rests on staff recognition and has not "
            "been independently confirmed by biometric means.\n"
            "20:12 Camera 9. A tablet-sized device passes from the second individual to the first. "
            "The contents of the device are not visible on the footage.\n"
            "20:45 Camera 4. The first individual leaves in the same vehicle."
        ),
    },
    {
        "document_id": "DOC-BANK-2024-003",
        "case_id": CASE_MAIN,
        "evidence_id": "EVID-BANK-01",
        "filename": "bank_ledger_feb2024.txt",
        "title": "Bank ledger extract, February 2024",
        "file_type": "LEDGER",
        "uploaded_by": "financial_desk",
        "created_at": "2024-02-19T16:30:00Z",
        "extracted_text": (
            "SYNTHETIC METRO NATIONAL BANK - LEDGER EXTRACT\n"
            "Account 10110, Zenith Holdings Pvt Ltd\n"
            "Account 99218, Apex Global Logistics\n\n"
            "TX-9871  2024-02-11 10:00  10110 to 99218   USD 50,000   narrative: advance\n"
            "TX-9902  2024-02-15 09:15  99218 to SW-77   USD 250,000  narrative: equipment "
            "procurement, beneficiary Alpine Holdings AG Zurich, authorised by A. Shahani\n\n"
            "No supporting invoice was lodged with the bank for TX-9902."
        ),
    },
    {
        "document_id": "DOC-CUSTOMS-2024-005",
        "case_id": CASE_MAIN,
        "evidence_id": "EVID-DOC-CUSTOMS-01",
        "filename": "customs_query_response.txt",
        "title": "Customs response regarding declared imports",
        "file_type": "REPORT",
        "uploaded_by": "rajiv_sen",
        "created_at": "2024-02-26T10:00:00Z",
        "extracted_text": (
            "RESPONSE TO QUERY, CUSTOMS RECORDS DESK\n"
            "Dated 26 February 2024.\n\n"
            "A search of import declarations filed by Apex Global Logistics for the period 1 "
            "January to 26 February 2024 returns no declaration corresponding to equipment "
            "procurement from a Swiss supplier.\n\n"
            "This absence is not by itself evidence of wrongdoing. Declarations may be filed late, "
            "may be filed by a different importer of record, or the goods may not yet have shipped."
        ),
    },
    {
        "document_id": "DOC-ARCHIVE-2023-001",
        "case_id": CASE_ARCHIVE,
        "evidence_id": "EVID-DOC-ARCHIVE-01",
        "filename": "golden_falcon_closing_note.txt",
        "title": "Closing note, Operation Golden Falcon",
        "file_type": "REPORT",
        "uploaded_by": "admin",
        "created_at": "2023-12-14T17:00:00Z",
        "extracted_text": (
            "CLOSING NOTE, OPERATION GOLDEN FALCON\n"
            "Dated 14 December 2023.\n\n"
            "The investigation examined consignments handled at the Nhava Sheva terminal by Golden "
            "Falcon Wharf Logistics. Persons of interest included Imran Sheikh and Farhan Qureshi. "
            "Call records placed a handset attributed to Vikram Malhotra at the terminal on 20 "
            "August 2023.\n\n"
            "The matter is closed for want of corroboration. No adverse finding was recorded "
            "against any named individual."
        ),
    },
]


# ---------------------------------------------------------------------------
# OSINT records
#
# The Alpine Holdings story is reported by seven outlets. Six of them derive from
# a single original filing, which is what the source-independence analysis has to
# uncover: seven mentions is not seven corroborations.
# ---------------------------------------------------------------------------

OSINT_RECORDS = [
    {
        "record_id": "OSINT-0001",
        "case_id": CASE_MAIN,
        "entity_id": "ENT-ORG-03",
        "query_term": "Alpine Holdings AG",
        "source_name": "Zurich Commercial Register (synthetic mirror)",
        "source_url": "https://example-registry.invalid/zurich/alpine-holdings-ag",
        "source_type": "CORPORATE_REGISTRY",
        "published_at": "2021-09-28T00:00:00Z",
        "reliability": 0.92,
        "confidence": 0.90,
        "claims": [
            "Alpine Holdings AG was incorporated on 28 September 2021.",
            "The registered purpose is stated as the holding of participations in trading companies.",
            "One nominee director is listed. No beneficial owner is disclosed in the public extract.",
        ],
        "origin_record_id": None,
        "requires_human_verification": False,
    },
    {
        "record_id": "OSINT-0002",
        "case_id": CASE_MAIN,
        "entity_id": "ENT-ORG-03",
        "query_term": "Alpine Holdings AG",
        "source_name": "Handelsblatt Regional (synthetic)",
        "source_url": "https://example-news.invalid/original/alpine-holdings-shell-report",
        "source_type": "NEWS",
        "published_at": "2023-11-04T08:00:00Z",
        "reliability": 0.78,
        "confidence": 0.72,
        "claims": [
            "An investigation by this outlet identified Alpine Holdings AG among a group of Zurich "
            "holding companies sharing a single registered address and nominee director.",
        ],
        "origin_record_id": None,
        "requires_human_verification": True,
    },
]

# Six syndicating outlets, all carrying the same original text.
_SYNDICATORS = [
    ("Business Wire Asia (synthetic)", "https://example-wire.invalid/asia/alpine-holdings"),
    ("Delhi Financial Daily (synthetic)", "https://example-daily.invalid/finance/alpine-holdings"),
    ("Trade Compliance Weekly (synthetic)", "https://example-weekly.invalid/alpine-holdings"),
    ("Global Shell Watch (synthetic)", "https://example-watch.invalid/posts/alpine-holdings"),
    ("Mumbai Business Post (synthetic)", "https://example-post.invalid/biz/alpine-holdings"),
    ("Corporate Risk Digest (synthetic)", "https://example-digest.invalid/alpine-holdings"),
]

for _i, (_name, _url) in enumerate(_SYNDICATORS, start=3):
    OSINT_RECORDS.append({
        "record_id": f"OSINT-{_i:04d}",
        "case_id": CASE_MAIN,
        "entity_id": "ENT-ORG-03",
        "query_term": "Alpine Holdings AG",
        "source_name": _name,
        "source_url": _url,
        "source_type": "AGGREGATOR",
        "published_at": f"2023-11-{5 + _i:02d}T09:00:00Z",
        "reliability": 0.45,
        "confidence": 0.40,
        "claims": [
            "An investigation by this outlet identified Alpine Holdings AG among a group of Zurich "
            "holding companies sharing a single registered address and nominee director.",
        ],
        "origin_record_id": "OSINT-0002",
        "requires_human_verification": True,
    })

OSINT_RECORDS.extend([
    {
        "record_id": "OSINT-0009",
        "case_id": CASE_MAIN,
        "entity_id": "ENT-ORG-02",
        "query_term": "Apex Global Logistics",
        "source_name": "Ministry of Corporate Affairs extract (synthetic mirror)",
        "source_url": "https://example-registry.invalid/in/apex-global-logistics",
        "source_type": "CORPORATE_REGISTRY",
        "published_at": "2016-02-03T00:00:00Z",
        "reliability": 0.94,
        "confidence": 0.92,
        "claims": [
            "Apex Global Logistics is an active company incorporated on 3 February 2016.",
            "Its filed principal activity is freight forwarding.",
            "No regulatory sanction is recorded against the company in the public extract.",
        ],
        "origin_record_id": None,
        "requires_human_verification": False,
    },
    {
        "record_id": "OSINT-0010",
        "case_id": CASE_MAIN,
        "entity_id": "ENT-PER-01",
        "query_term": "Vikram Malhotra",
        "source_name": "Regional news archive (synthetic)",
        "source_url": "https://example-news.invalid/archive/logistics-conference-2022",
        "source_type": "NEWS",
        "published_at": "2022-05-18T00:00:00Z",
        "reliability": 0.60,
        "confidence": 0.35,
        "claims": [
            "A person named Vikram Malhotra is quoted in a conference report on freight corridors.",
        ],
        "origin_record_id": None,
        "requires_human_verification": True,
        "verification_note": (
            "Name match only. Vikram Malhotra is a common name and the report carries no "
            "identifier tying it to the subject of this case. Potential external match, human "
            "verification required."
        ),
    },
    {
        "record_id": "OSINT-0011",
        "case_id": CASE_MAIN,
        "entity_id": "ENT-ORG-05",
        "query_term": "Meridian Trade FZE",
        "source_name": "Free zone registry extract (synthetic mirror)",
        "source_url": "https://example-registry.invalid/fze/meridian-trade",
        "source_type": "CORPORATE_REGISTRY",
        "published_at": "2022-01-17T00:00:00Z",
        "reliability": 0.85,
        "confidence": 0.80,
        "claims": [
            "Meridian Trade FZE was registered on 17 January 2022.",
            "A director is recorded under the name Neha Kapoor.",
        ],
        "origin_record_id": None,
        "requires_human_verification": True,
    },
])


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    entities = build_entities()
    relationships = build_relationships()
    events = build_events()

    payloads = {
        "cases.json": CASES,
        "entities.json": entities,
        "relationships.json": relationships,
        "events.json": events,
        "documents.json": DOCUMENTS,
        "osint_records.json": OSINT_RECORDS,
    }

    for name, payload in payloads.items():
        path = DATA_DIR / name
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {path.name}: {len(payload)} records")


if __name__ == "__main__":
    main()
