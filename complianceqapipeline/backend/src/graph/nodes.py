import json 
import os 
import re 
import logging
from typing import Any, Dict, List, Optional, Tuple, Union
from sentence_transformers import CrossEncoder

from langchain_openai import ChatOpenAI, AzureOpenAIEmbeddings
from langchain_community.vectorstores import AzureSearch
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, SystemMessagePromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from backend.src.graph.state import VideoAuditState, ComplianceIssue
from backend.src.services.video_indexer import VideoIndexerService


## configure logger
logger = logging.getLogger("brand-compliance")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
_reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2") 

def _get_llm() -> ChatOpenAI:
    """
    Reads credentials from environment variable:
      OPENAI_API_KEY   (required)
      OPENAI_MODEL     (optional, default: gpt-4o)
    """
    return ChatOpenAI(
        model=os.environ.get("OPENAI_MODEL", "gpt-4o"),
        api_key=os.environ["OPENAI_API_KEY"],
        temperature=0,
    )

def index_video_node(state: VideoAuditState) -> Dict[str, Any]:  
    '''
    Node function for video indexing, it takes the video url as input, download the video, extract metadata, transcript and ocr text, then update the state with the extracted information.
    '''
    video_url = state.get("video_url")
    video_id_input = state.get("video_id","vid_demo")

    logger.info(f"Starting video indexing for video_id: {video_id_input} from url: {video_url}")
    # initialize video indexer service

    local_filename="temp_video.mp4"

    try: 
        vi_service = VideoIndexerService()

        if "youtube.com" in video_url or "youtu.be" in video_url:
            # for youtube video, we can directly download the video and save it to local file system
            local_path = vi_service.download_youtube_video(video_url, output_path=local_filename)
        else:
            raise Exception("Unsupported video source. Currently only youtube videos are supported.")
        
        azure_video_id = vi_service.upload_video(local_path,video_name=video_id_input)
        logger.info(f"Video uploaded to Azure Video Indexer with video_id: {azure_video_id}")

        if os.path.exists(local_path):
            os.remove(local_path)
            logger.info(f"Temporary video file {local_path} removed after upload.")
        
        raw_insights= vi_service.wait_for_processing(azure_video_id)
        logger.info(f"Video processing completed for video_id: {azure_video_id}")

        clean_data = vi_service.extract_data(raw_insights)
        logger.info(f"Data extraction completed for video_id: {azure_video_id}")
        return clean_data
    
    except Exception as e:
        logger.error(f"Error in video indexing for video_id: {video_id_input} - {str(e)}")
        return{ 
            "errors": [str(e)],
            "final_status": "FAIL",
            "transcript": "",
            "ocr_text": []
        }
    
def audio_content_node(state: VideoAuditState) -> Dict[str, Any]:
        '''
        Perform Retrieval Augmented Generation (RAG) on the extracted transcript and OCR text to generate a comprehensive compliance report. This node will take the transcript and OCR text as input, perform RAG using a language model, and update the state with the generated compliance report.   
        '''

        logger.info("--[Node:Auditor] quering knowledge base for compliance checking & LLM--")
        transcript = state.get("transcript","")

        if not transcript:
            logger.warning("No transcript available for RAG. Skipping compliance report generation.")
            return {
                "final_status": "FAIL",
                "final_report": "No transcript available for compliance analysis."
            }
        
        ### get azure services

        llm = _get_llm()

        embedding_model = AzureOpenAIEmbeddings(
            azure_deployment=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
        )   

        vector_store = AzureSearch(
            azure_search_endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
            azure_search_key=os.getenv("AZURE_SEARCH_KEY"),
            index_name=os.getenv("AZURE_SEARCH_INDEX_NAME"),
            embedding_function=embedding_model.embed_query,
            semantic_configuration_name="brand-compliance-semantic-config" 
        )

        ### RAG retrieval 

        ocr_text = state.get("ocr_text",[])
        query_text = f"{transcript}\n OCR Text: {''.join(ocr_text)}"
        docs = vector_store.semantic_hybrid_search(query_text, k=10)
        scores = _reranker.predict([(query_text, doc.page_content) for doc in docs])
        docs = [doc for _, doc in sorted(zip(scores, docs), key=lambda x: x[0], reverse=True)][:3]
        retrieved_rules = "\n\n".join([doc.page_content for doc in docs])
        
        ### LLM analysis
        # --- UPDATED PROMPT WITH STRICT SCHEMA ---
        system_prompt = f"""
        You are a Senior Brand Compliance Auditor.
        
        OFFICIAL REGULATORY RULES:
        {retrieved_rules}
        
        INSTRUCTIONS:
        1. Analyze the Transcript and OCR text below.
        2. Identify ANY violations of the rules.
        3. Return strictly JSON in the following format:
        
        {{
            "compliance_results": [
                {{
                    "category": "Claim Validation",
                    "severity": "CRITICAL",
                    "description": "Explanation of the violation..."
                }}
            ],
            "status": "FAIL",  
            "final_report": "Summary of findings..."
        }}

        If no violations are found, set "status" to "PASS" and "compliance_results" to [].
        """

        user_message = f"""
        VIDEO METADATA: {state.get('video_metadata', {})}
        TRANSCRIPT: {transcript}
        ON-SCREEN TEXT (OCR): {ocr_text}
        """

        try:
            response = llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_message)
            ])
            
            # --- FIX: Clean Markdown if present (```json ... ```) ---
            content = response.content
            if "```" in content:
                # Regex to find JSON inside code blocks
                content = re.search(r"```(?:json)?(.*?)```", content, re.DOTALL).group(1)
                
            audit_data = json.loads(content.strip())
            
            return {
                "compliance_results": audit_data.get("compliance_results", []),
                "final_status": audit_data.get("status", "FAIL"),
                "final_report": audit_data.get("final_report", "No report generated.")
            }

        except Exception as e:
            logger.error(f"System Error in Auditor Node: {str(e)}")
            # Log the raw response to see what went wrong
            logger.error(f"Raw LLM Response: {response.content if 'response' in locals() else 'None'}")
            return {
                "errors": [str(e)],
                "final_status": "FAIL"
            } 
            
            
        
            

         