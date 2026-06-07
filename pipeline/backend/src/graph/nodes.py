import os
import logging
from typing import Any, Dict, List, Literal, Optional
from sentence_transformers import CrossEncoder
from pydantic import BaseModel, Field

from langchain_openai import ChatOpenAI, AzureOpenAIEmbeddings
from langchain_community.vectorstores import AzureSearch
from langchain_core.messages import SystemMessage, HumanMessage
from backend.src.graph.state import CallSurveillanceState
from backend.src.services.video_indexer import VideoIndexerService


logger = logging.getLogger("trade-surveillance")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
_reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")


# --- Structured output schema for the LLM ---

class ViolationOutput(BaseModel):
    category: Literal[
        "MNPI Disclosure",
        "Unauthorized Investment Advice",
        "Market Manipulation",
        "Front-Running",
        "Restricted Securities",
        "Recordkeeping Violation",
    ]
    regulation: str = Field(description="Applicable regulation, e.g. SEC Rule 10b-5, FINRA Rule 2010")
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    description: str = Field(description="Specific evidence from the transcript supporting this violation")
    timestamp: Optional[str] = Field(default=None, description="HH:MM:SS in the call where the violation occurred")


class SurveillanceAnalysis(BaseModel):
    compliance_violations: List[ViolationOutput] = Field(default_factory=list)
    flagged_entities: List[str] = Field(
        default_factory=list,
        description="All security tickers, company names, and financial instruments mentioned",
    )
    status: Literal["CLEAR", "REVIEW", "ESCALATE"]
    final_report: str = Field(description="Narrative summary of surveillance findings for the compliance officer")


# ---


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=os.environ.get("OPENAI_MODEL", "gpt-4o"),
        api_key=os.environ["OPENAI_API_KEY"],
        temperature=0,
    )


def call_indexer_node(state: CallSurveillanceState) -> Dict[str, Any]:
    """
    Ingests a trader/RM call recording, uploads to Azure Video Indexer,
    and extracts the speaker-attributed transcript and on-screen OCR text.
    Supports YouTube (testing), Azure Blob Storage SAS URLs (production internal recordings).
    """
    video_url = state.get("video_url")
    call_id = state.get("call_id", "call_demo")

    logger.info(f"[CallIndexer] Starting ingestion for call_id={call_id} url={video_url}")

    local_filename = "temp_call_recording.mp4"

    try:
        vi_service = VideoIndexerService()

        if "youtube.com" in video_url or "youtu.be" in video_url:
            local_path = vi_service.download_youtube_video(video_url, output_path=local_filename)
        elif "blob.core.windows.net" in video_url:
            local_path = vi_service.download_from_blob(video_url, output_path=local_filename)
        else:
            raise Exception(
                "Unsupported video source. Provide a YouTube URL (testing) "
                "or an Azure Blob Storage SAS URL (production call recordings)."
            )

        azure_video_id = vi_service.upload_video(local_path, video_name=call_id)
        logger.info(f"[CallIndexer] Uploaded to Azure Video Indexer — azure_video_id={azure_video_id}")

        if os.path.exists(local_path):
            os.remove(local_path)
            logger.info(f"[CallIndexer] Temporary file {local_path} removed.")

        raw_insights = vi_service.wait_for_processing(azure_video_id)
        logger.info(f"[CallIndexer] Processing complete for azure_video_id={azure_video_id}")

        clean_data = vi_service.extract_data(raw_insights)
        logger.info(f"[CallIndexer] Data extraction complete for call_id={call_id}")
        return clean_data

    except Exception as e:
        logger.error(f"[CallIndexer] Error for call_id={call_id}: {str(e)}")
        return {
            "errors": [str(e)],
            "final_status": "ESCALATE",
            "transcript": "",
            "ocr_text": [],
        }


def surveillance_auditor_node(state: CallSurveillanceState) -> Dict[str, Any]:
    """
    Trade Surveillance Agent: RAGs against Dodd-Frank / SEC / FINRA knowledge base,
    then uses structured LLM output to detect MNPI disclosure, unauthorized investment advice,
    market manipulation signals, front-running, and restricted-securities violations.
    """
    logger.info("[SurveillanceAuditor] Starting compliance analysis against regulatory knowledge base.")

    transcript = state.get("transcript", "")
    if not transcript:
        logger.warning("[SurveillanceAuditor] No transcript available. Skipping analysis.")
        return {
            "final_status": "REVIEW",
            "final_report": "No transcript available for surveillance analysis. Manual review required.",
        }

    llm = _get_llm()
    structured_llm = llm.with_structured_output(SurveillanceAnalysis)

    embedding_model = AzureOpenAIEmbeddings(
        azure_deployment=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
    )

    vector_store = AzureSearch(
        azure_search_endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
        azure_search_key=os.getenv("AZURE_SEARCH_KEY"),
        index_name=os.getenv("AZURE_SEARCH_INDEX_NAME"),
        embedding_function=embedding_model.embed_query,
        semantic_configuration_name="dodd-frank-compliance-semantic-config",
    )

    ocr_text = state.get("ocr_text", [])
    query_text = f"{transcript}\n\nOn-Screen Content: {' '.join(ocr_text)}"

    docs = vector_store.semantic_hybrid_search(query_text, k=10)
    scores = _reranker.predict([(query_text, doc.page_content) for doc in docs])
    docs = [doc for _, doc in sorted(zip(scores, docs), key=lambda x: x[0], reverse=True)][:4]
    retrieved_rules = "\n\n".join([doc.page_content for doc in docs])

    system_prompt = f"""
You are a Senior Trade Surveillance Officer at a US bank, responsible for Dodd-Frank and SEC/FINRA compliance.

Your role is to analyze recorded trader and relationship manager (RM) communications to detect regulatory violations under:
- Dodd-Frank Wall Street Reform and Consumer Protection Act
- SEC Rule 10b-5 (Securities Fraud / Insider Trading / MNPI)
- SEC Rule 17a-4 (Books and Records)
- FINRA Rule 2010 (Standards of Commercial Honor)
- FINRA Rule 2020 (Use of Manipulative, Deceptive Devices)
- FINRA Rule 4511 (General Requirements — Books and Records)

OFFICIAL REGULATORY RULES AND PROHIBITED CONTENT (retrieved from compliance knowledge base):
{retrieved_rules}

SURVEILLANCE INSTRUCTIONS:
1. Analyze the call transcript and any on-screen content (OCR from Bloomberg terminals, spreadsheets, or charts).
2. Identify violations across these categories:
   - MNPI Disclosure: unreleased earnings, M&A activity, regulatory actions, clinical trial results
   - Unauthorized Investment Advice: specific buy/sell recommendations without required disclosures
   - Market Manipulation: coordinated trading, layering, spoofing, marking the close, wash trading
   - Front-Running: trading ahead of known pending client orders
   - Restricted Securities: referencing or facilitating trades in firm-restricted securities
   - Recordkeeping Violation: shifting communications to WhatsApp, personal email, Signal
3. Extract all security tickers, company names, and financial instruments mentioned.
4. Assign status:
   - ESCALATE: confirmed violations requiring immediate compliance officer escalation
   - REVIEW: potential violations requiring human review
   - CLEAR: no violations found
"""

    user_message = f"""
CALL METADATA: {state.get('call_metadata', {})}

SPEAKER-ATTRIBUTED TRANSCRIPT:
{transcript}

ON-SCREEN CONTENT (OCR from Bloomberg/spreadsheets):
{ocr_text}
"""

    try:
        result: SurveillanceAnalysis = structured_llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ])

        logger.info(f"[SurveillanceAuditor] Analysis complete — status={result.status}, violations={len(result.compliance_violations)}")

        return {
            "compliance_violations": [v.model_dump() for v in result.compliance_violations],
            "flagged_entities": result.flagged_entities,
            "final_status": result.status,
            "final_report": result.final_report,
        }

    except Exception as e:
        logger.error(f"[SurveillanceAuditor] Structured LLM call failed: {str(e)}")
        return {
            "errors": [str(e)],
            "final_status": "REVIEW",
        }
