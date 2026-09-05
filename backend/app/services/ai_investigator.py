import json
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from app.services.graph_engine import knowledge_graph
from app.services.query_planner import query_planner
from app.models.entities import Document, Evidence, Case
from app.core.config import settings

class UniversalAIInvestigator:
    def __init__(self):
        self.gemini_key = settings.GEMINI_API_KEY

    def investigate(
        self,
        db: Session,
        case_id: str,
        query: str,
        history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """Routes investigator questions through the Dynamic Investigation Query Planner."""
        return query_planner.plan_and_execute(
            db=db,
            case_id=case_id,
            query=query,
            history=history
        )

    def generate_hypotheses(self, case_id: str) -> List[Dict[str, Any]]:
        return [
            {
                "hypothesis_id": "HYP-01",
                "title": "Coordinated Hawala Transfer & Customs Laundering",
                "probability_score": 0.88,
                "status": "STRONG_LEAD",
                "summary": "Vikram Malhotra coordinates physical delivery of ledgers at Aerocity Hotel on Feb 14; Amit Shahani routes $250,000 USD via Alpine Holdings Zurich on Feb 15 to clear offshore freight.",
                "supporting_evidence": [
                    "CCTV footage confirms Vikram and Amit meeting at Aerocity Hotel [EVID-CCTV-01].",
                    "CDR logs place both phones at Aerocity tower at 19:34 [EVID-CDR-01].",
                    "Bank transfer records $250,000 sent from Apex to Alpine Holdings [EVID-BANK-01]."
                ],
                "contradicting_evidence": [
                    "Driver statement claims Vikram was in Dubai (contradicted by physical CCTV) [DOC-WITNESS-2024-002]."
                ],
                "recommended_actions": [
                    "Issue MLAT request to Swiss Federal Department of Justice for Alpine Holdings beneficial ownership."
                ]
            },
            {
                "hypothesis_id": "HYP-02",
                "title": "Unrelated Legitimate Equipment Purchase",
                "probability_score": 0.22,
                "status": "UNLIKELY",
                "summary": "Transfer to Zurich was an advance payment for industrial port clearance cranes by Apex Global Logistics.",
                "supporting_evidence": [
                    "Apex Global Logistics holds valid corporate registration in Delhi [OSINT-01]."
                ],
                "contradicting_evidence": [
                    "Preceded by encrypted ledger handover and false Dubai alibi by director.",
                    "No commercial invoices or customs declarations filed for crane import."
                ],
                "recommended_actions": [
                    "Verify with Directorate General of Foreign Trade (DGFT) import registry."
                ]
            }
        ]

ai_investigator = UniversalAIInvestigator()
