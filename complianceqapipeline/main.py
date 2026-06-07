"""
Dodd-Frank Communications Surveillance API
Receives call recording URLs (Zoom, Bloomberg, Teams via Azure Blob SAS or YouTube for testing),
runs the trade surveillance workflow, and returns a compliance report.
"""

import uuid
import logging
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from backend.src.graph.workflow import app
from backend.src.schemas.audit import SurveillanceRequest, SurveillanceResponse

load_dotenv(override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("trade-surveillance-api")

app_api = FastAPI(
    title="Dodd-Frank Communications Surveillance API",
    description=(
        "Trade surveillance system for Dodd-Frank, SEC Rule 10b-5, and FINRA compliance. "
        "Analyzes trader and relationship manager call recordings to detect MNPI disclosure, "
        "unauthorized investment advice, market manipulation, and front-running."
    ),
    version="1.0.0",
)


@app_api.get("/health")
def health_check():
    return {"status": "healthy", "service": "trade-surveillance-ai"}


@app_api.post("/surveillance", response_model=SurveillanceResponse)
async def run_surveillance(payload: SurveillanceRequest):
    """
    Submit a call recording URL for Dodd-Frank compliance surveillance.
    Returns CLEAR / REVIEW / ESCALATE status with detailed violation findings.
    """
    try:
        session_id = str(uuid.uuid4())
        call_id = payload.call_id or f"call_{session_id[:8]}"

        logger.info(f"Starting surveillance session={session_id} call_id={call_id}")

        initial_inputs = {
            "video_url": str(payload.video_url),
            "call_id": call_id,
            "compliance_violations": [],
            "flagged_entities": [],
            "errors": [],
        }

        final_state = app.invoke(initial_inputs)

        return SurveillanceResponse(
            session_id=session_id,
            call_id=final_state.get("call_id", call_id),
            final_status=final_state.get("final_status"),
            flagged_entities=final_state.get("flagged_entities", []),
            compliance_violations=final_state.get("compliance_violations", []),
            call_metadata=final_state.get("call_metadata"),
            final_report=final_state.get("final_report"),
            errors=final_state.get("errors", []),
        )

    except Exception as e:
        logger.exception("Surveillance workflow execution failed")
        raise HTTPException(status_code=500, detail=str(e))
