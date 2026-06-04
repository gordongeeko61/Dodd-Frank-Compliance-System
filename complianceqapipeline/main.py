"""
FastAPI Entry Point for Brand Guardian AI
Receives video URLs from Flagger MicroUI
Runs compliance workflow
Returns JSON response
"""

import uuid
import logging
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from backend.src.graph.workflow import app
from backend.src.schemas.audit import (
    AuditRequest,
    AuditResponse
)

# Load env variables
load_dotenv(override=True)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger("brand-guardian-api")

# FastAPI App
app_api = FastAPI(
    title="Brand Guardian AI",
    description="Video Compliance Audit API",
    version="1.0.0"
)


@app_api.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "brand-guardian-ai"
    }


@app_api.post(
    "/audit",
    response_model=AuditResponse
)
async def run_audit(payload: AuditRequest):

    try:
        # Session tracking
        session_id = str(uuid.uuid4())

        logger.info(
            f"Starting Audit Session: {session_id}"
        )

        # Initial workflow state
        initial_inputs = {
            "video_url": str(payload.video_url),
            "video_id": f"vid_{session_id[:8]}",
            "compliance_results": [],
            "errors": []
        }

        # Execute LangGraph workflow
        final_state = app.invoke(initial_inputs)

        return AuditResponse(
            session_id=session_id,
            video_id=final_state.get("video_id"),
            final_status=final_state.get("final_status"),
            compliance_results=final_state.get(
                "compliance_results", []
            ),
            final_report=final_state.get(
                "final_report"
            ),
            errors=final_state.get(
                "errors", []
            )
        )

    except Exception as e:
        logger.exception(
            "Workflow Execution Failed"
        )

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )