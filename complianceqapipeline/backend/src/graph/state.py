import operator
from typing import Any, Dict, List, Optional, Annotated, TypedDict


class ComplianceViolation(TypedDict):
    category: str       # MNPI Disclosure | Unauthorized Investment Advice | Market Manipulation | Front-Running | Restricted Securities | Recordkeeping Violation
    regulation: str     # SEC Rule 10b-5 | Dodd-Frank Section X | FINRA Rule 2010 | etc.
    severity: str       # CRITICAL | HIGH | MEDIUM | LOW
    description: str    # specific violation details with evidence from transcript
    timestamp: Optional[str]  # HH:MM:SS in the call where the violation occurred


class CallSurveillanceState(TypedDict):
    """
    LangGraph execution state for Dodd-Frank communications surveillance.
    Tracks the full lifecycle: call ingestion → transcript extraction → trade surveillance → report.
    """
    # inputs
    video_url: str
    call_id: str

    # ingestion and extraction
    local_file_path: Optional[str]
    call_metadata: Dict[str, Any]   # participants, platform, duration, date, speaker_map
    transcript: Optional[str]       # speaker-attributed transcript
    ocr_text: List[str]             # Bloomberg terminal, spreadsheet, chart text captured on screen

    # surveillance findings
    flagged_entities: List[str]     # restricted tickers / securities / company names mentioned
    compliance_violations: Annotated[List[ComplianceViolation], operator.add]

    final_status: str    # CLEAR | REVIEW | ESCALATE
    final_report: str    # detailed surveillance report in markdown

    errors: Annotated[List[str], operator.add]
