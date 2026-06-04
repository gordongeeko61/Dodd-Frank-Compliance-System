from pydantic import BaseModel, HttpUrl
from typing import List, Optional

from backend.src.graph.state import ComplianceIssue

class AuditRequest(BaseModel):
    video_url: HttpUrl




class AuditResponse(BaseModel):
    session_id: str
    video_id: str
    final_status: Optional[str]
    compliance_results: List[ComplianceIssue]
    final_report: Optional[str]
    errors: List[str]