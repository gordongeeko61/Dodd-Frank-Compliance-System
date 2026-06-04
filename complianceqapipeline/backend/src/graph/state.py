import operator
from typing import Any, Dict, List, Optional,Annotated, TypedDict

# def scheme for compliance result
# error report 
class ComplianceIssue(TypedDict):
    category: str
    description: str # specific violation details
    severity: str # critical | warning
    time: Optional[str]

# define the global graph state
# this defines the state that gets passed around in th agentic workflow 
class VideoAuditState(TypedDict):
    '''
    Defines the data scheme for langgraph exceution content
    main store where it contains all the data related to the video audit process, from ingestion, extraction, compliance checking and final report generation.
    '''
    #inputs
    video_url: str
    video_id: str

    #ingestion and exxtarction data
    local_file_path: Optional[str]
    video_metadata: Dict[str, Any]
    transcript: Optional[str]
    ocr_text: List[str]

    compliance_results: Annotated[List[ComplianceIssue],operator.add]

    final_status: str # pass || fail
    final_report: str # markdown format 

    #list of system erros 
    errors: Annotated[List[str],operator.add] 

