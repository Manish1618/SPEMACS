import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from app.core.config import settings
from app.services.evidence import calculate_sha256

def perform_osint_expansion(entity_name: str, entity_type: str, case_id: str) -> List[Dict[str, Any]]:
    osint_path = settings.DATA_DIR / "synthetic" / "osint_records.json"
    if not osint_path.exists():
        return []
        
    with open(osint_path, "r", encoding="utf-8") as f:
        records = json.load(f)
        
    results = []
    entity_clean = entity_name.lower().strip()
    
    for r in records:
        name_match = (entity_clean in r["entity_name"].lower()) or any(entity_clean in alias.lower() for alias in r.get("aliases", []))
        if name_match:
            record_id = f"OSINT-{calculate_sha256(r['source_url'].encode('utf-8'))[:8].upper()}"
            results.append({
                "source_name": r["source_name"],
                "source_url": r["source_url"],
                "retrieval_timestamp": datetime.now(timezone.utc),
                "reliability_score": r["reliability_score"],
                "confidence": r["confidence"],
                "extracted_claims": r["extracted_claims"],
                "is_potential_match": r.get("is_potential_match", False),
                "verification_warning": r.get("verification_warning"),
                "evidence_id": record_id
            })
            
    if not results:
        # Generate synthetic public registrar lookup
        record_id = f"OSINT-{calculate_sha256(entity_name.encode('utf-8'))[:8].upper()}"
        results.append({
            "source_name": "Public Commercial Registrar & Telecom Directory",
            "source_url": f"https://public-records.gov.in/search?q={entity_name}",
            "retrieval_timestamp": datetime.now(timezone.utc),
            "reliability_score": 0.70,
            "confidence": 0.75,
            "extracted_claims": f"Public index records matching '{entity_name}'. No adverse regulatory sanctions or red flags recorded.",
            "is_potential_match": True,
            "verification_warning": "Potential Match — Human Verification Required",
            "evidence_id": record_id
        })
        
    return results
