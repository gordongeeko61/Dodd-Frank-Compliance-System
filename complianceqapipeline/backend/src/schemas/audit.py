from pydantic import BaseModel, HttpUrl
from typing import Any, Dict, List, Optional

from backend.src.graph.state import ComplianceViolation


class SurveillanceRequest(BaseModel):
    video_url: HttpUrl
    call_id: Optional[str] = None   # e.g. "trader-desk-3-2024-06-04-143022"; auto-generated if omitted


class SurveillanceResponse(BaseModel):
    session_id: str
    call_id: str
    final_status: Optional[str]             # CLEAR | REVIEW | ESCALATE
    flagged_entities: List[str]             # tickers / companies mentioned
    compliance_violations: List[ComplianceViolation]
    call_metadata: Optional[Dict[str, Any]] # participants, platform, duration
    final_report: Optional[str]
    errors: List[str]
