from fastapi import APIRouter, Query
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.schemas.schemas import MapEventFeature, TimelineEvent

router = APIRouter(prefix="/workspace", tags=["Map & Timeline Synchronizer"])

def get_all_raw_events() -> List[Dict[str, Any]]:
    return [
        {
            "id": "EVT-CDR-01",
            "case_id": "CASE-2024-8812",
            "title": "Voice Call: Vikram Malhotra to Amit Shahani",
            "event_type": "CDR_CALL",
            "timestamp": "2024-02-10T11:20:00Z",
            "location_name": "Connaught Place Head Office, New Delhi",
            "latitude": 28.6315,
            "longitude": 77.2167,
            "related_entities": ["ENT-PER-01", "ENT-PER-02", "ENT-PH-01", "ENT-PH-02"],
            "evidence_id": "EVID-CDR-01",
            "summary": "145s call via Connaught Place tower regarding initial logistics arrangements.",
            "confidence": 0.99
        },
        {
            "id": "EVT-TX-01",
            "case_id": "CASE-2024-8812",
            "title": "Bank Transfer: $50,000 USD (Zenith to Apex)",
            "event_type": "FINANCIAL_TRANSACTION",
            "timestamp": "2024-02-11T10:00:00Z",
            "location_name": "Metro National Bank, New Delhi",
            "latitude": 28.6315,
            "longitude": 77.2167,
            "related_entities": ["ENT-ORG-01", "ENT-ORG-02", "ENT-ACC-01", "ENT-ACC-02"],
            "evidence_id": "EVID-BANK-01",
            "summary": "Fund transfer of $50,000 USD executed between shell entities.",
            "confidence": 0.99
        },
        {
            "id": "EVT-CDR-02",
            "case_id": "CASE-2024-8812",
            "title": "Voice Call: Vikram Malhotra to Rahul Sharma",
            "event_type": "CDR_CALL",
            "timestamp": "2024-02-12T15:40:00Z",
            "location_name": "Khan Market, New Delhi",
            "latitude": 28.6000,
            "longitude": 77.2270,
            "related_entities": ["ENT-PER-01", "ENT-PER-03", "ENT-PH-01", "ENT-PH-03"],
            "evidence_id": "EVID-CDR-01",
            "summary": "80s call to dispatch vehicle DL-04-E-5544.",
            "confidence": 0.98
        },
        {
            "id": "EVT-TOLL-01",
            "case_id": "CASE-2024-8812",
            "title": "ANPR Camera: Fortuner DL-04-E-5544 (Northbound)",
            "event_type": "VEHICLE_SURVEILLANCE",
            "timestamp": "2024-02-14T18:40:00Z",
            "location_name": "Kherki Daula Toll Plaza, Delhi-Gurgaon",
            "latitude": 28.4032,
            "longitude": 76.9930,
            "related_entities": ["ENT-VEH-01", "ENT-PER-01"],
            "evidence_id": "EVID-TOLL-01",
            "summary": "Black Toyota Fortuner captured moving northbound towards Delhi.",
            "confidence": 0.97
        },
        {
            "id": "EVT-MEET-01",
            "case_id": "CASE-2024-8812",
            "title": "Surveillance: Vikram Malhotra & Amit Shahani Secret Meeting",
            "event_type": "SUSPICIOUS_MEETING",
            "timestamp": "2024-02-14T19:30:00Z",
            "location_name": "Hotel Grand Palace, Aerocity, New Delhi",
            "latitude": 28.5504,
            "longitude": 77.1210,
            "related_entities": ["ENT-PER-01", "ENT-PER-02", "ENT-VEH-01", "ENT-LOC-01"],
            "evidence_id": "EVID-CCTV-01",
            "summary": "CCTV records Vikram arriving in vehicle DL-04-E-5544 and receiving encrypted tablet ledger from Amit Shahani.",
            "confidence": 0.98
        },
        {
            "id": "EVT-CDR-04",
            "case_id": "CASE-2024-8812",
            "title": "CDR Tower Triangulation: Aerocity Cell Tower",
            "event_type": "CDR_CALL",
            "timestamp": "2024-02-14T19:34:10Z",
            "location_name": "Aerocity Tower DEL-TOW-508",
            "latitude": 28.5504,
            "longitude": 77.1210,
            "related_entities": ["ENT-PER-01", "ENT-PER-02", "ENT-PH-01", "ENT-PH-02"],
            "evidence_id": "EVID-CDR-01",
            "summary": "320s call during Aerocity meeting. Directly contradicts driver's Dubai alibi.",
            "confidence": 0.99
        },
        {
            "id": "EVT-TOLL-02",
            "case_id": "CASE-2024-8812",
            "title": "ANPR Camera: Fortuner DL-04-E-5544 (Southbound)",
            "event_type": "VEHICLE_SURVEILLANCE",
            "timestamp": "2024-02-14T21:10:00Z",
            "location_name": "Kherki Daula Toll Plaza, Delhi-Gurgaon",
            "latitude": 28.4032,
            "longitude": 76.9930,
            "related_entities": ["ENT-VEH-01", "ENT-PER-01"],
            "evidence_id": "EVID-TOLL-01",
            "summary": "Vehicle returns toward Gurgaon after Aerocity meeting.",
            "confidence": 0.97
        },
        {
            "id": "EVT-TX-02",
            "case_id": "CASE-2024-8812",
            "title": "Wire Transfer: $250,000 USD Foreign Wire to Zurich",
            "event_type": "FINANCIAL_TRANSACTION",
            "timestamp": "2024-02-15T09:15:00Z",
            "location_name": "Metro National Bank, New Delhi",
            "latitude": 28.6315,
            "longitude": 77.2167,
            "related_entities": ["ENT-ORG-02", "ENT-ORG-03", "ENT-ACC-02", "ENT-ACC-03", "ENT-PER-02"],
            "evidence_id": "EVID-BANK-01",
            "summary": "Wire transfer authorized by Amit Shahani to Alpine Holdings AG (Zurich).",
            "confidence": 0.99
        },
        {
            "id": "EVT-CDR-07",
            "case_id": "CASE-2024-8812",
            "title": "Voice Call: Vikram Malhotra to Mumbai Port Logistics",
            "event_type": "CDR_CALL",
            "timestamp": "2024-02-17T12:10:00Z",
            "location_name": "Nhava Sheva Port, Mumbai",
            "latitude": 18.9496,
            "longitude": 72.9510,
            "related_entities": ["ENT-PER-01", "ENT-LOC-03"],
            "evidence_id": "EVID-CDR-01",
            "summary": "290s call coordinating customs clearance for shipping containers.",
            "confidence": 0.96
        },
        {
            "id": "EVT-CDR-08",
            "case_id": "CASE-2023-1104",
            "title": "Historical Call: Vikram Malhotra at Nhava Sheva Wharf",
            "event_type": "HISTORICAL_CALL",
            "timestamp": "2023-08-20T14:00:00Z",
            "location_name": "Nhava Sheva Port, Mumbai",
            "latitude": 18.9496,
            "longitude": 72.9510,
            "related_entities": ["ENT-PER-01", "ENT-LOC-03"],
            "evidence_id": "EVID-CDR-02",
            "summary": "Historical call linking Vikram to Golden Falcon coastal smuggling case.",
            "confidence": 0.95
        }
    ]

@router.get("/map-events", response_model=List[MapEventFeature])
def get_map_events(
    case_id: Optional[str] = None,
    entity_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    raw = get_all_raw_events()
    filtered = []
    
    for e in raw:
        if case_id and e["case_id"] != case_id:
            continue
        if entity_id and entity_id not in e.get("related_entities", []):
            continue
        if start_date and e["timestamp"] < start_date:
            continue
        if end_date and e["timestamp"] > end_date:
            continue
            
        filtered.append(MapEventFeature(
            event_id=e["id"],
            case_id=e["case_id"],
            title=e["title"],
            event_type=e["event_type"],
            latitude=e["latitude"],
            longitude=e["longitude"],
            location_name=e["location_name"],
            timestamp=datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00")),
            related_entities=e.get("related_entities", []),
            evidence_id=e.get("evidence_id"),
            confidence=e.get("confidence", 1.0)
        ))
    return filtered

@router.get("/timeline", response_model=List[TimelineEvent])
def get_timeline(
    case_id: Optional[str] = None,
    entity_id: Optional[str] = None,
    event_type: Optional[str] = None
):
    raw = get_all_raw_events()
    filtered = []
    
    for e in raw:
        if case_id and e["case_id"] != case_id:
            continue
        if entity_id and entity_id not in e.get("related_entities", []):
            continue
        if event_type and e["event_type"] != event_type:
            continue
            
        filtered.append(TimelineEvent(
            id=e["id"],
            case_id=e["case_id"],
            title=e["title"],
            event_type=e["event_type"],
            start_time=datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00")),
            location_name=e.get("location_name"),
            latitude=e.get("latitude"),
            longitude=e.get("longitude"),
            related_entities=e.get("related_entities", []),
            evidence_id=e.get("evidence_id"),
            summary=e.get("summary", ""),
            confidence=e.get("confidence", 1.0)
        ))
        
    filtered.sort(key=lambda x: x.start_time)
    return filtered
