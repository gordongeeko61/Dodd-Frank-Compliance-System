"""
Dodd-Frank Communications Surveillance — LangGraph Workflow

START -> call_indexer_node -> surveillance_auditor_node -> END

call_indexer_node:    Downloads call recording, uploads to Azure Video Indexer,
                      extracts speaker-attributed transcript + OCR from shared screens.

surveillance_auditor_node: RAGs against SEC/FINRA/Dodd-Frank knowledge base,
                           detects MNPI, unauthorized advice, market manipulation, etc.
"""

from langgraph.graph import StateGraph, END
from backend.src.graph.state import CallSurveillanceState
from backend.src.graph.nodes import (
    call_indexer_node,
    surveillance_auditor_node,
)


def create_graph():
    workflow = StateGraph(CallSurveillanceState)

    workflow.add_node("call_indexer", call_indexer_node)
    workflow.add_node("surveillance_auditor", surveillance_auditor_node)

    workflow.set_entry_point("call_indexer")
    workflow.add_edge("call_indexer", "surveillance_auditor")
    workflow.add_edge("surveillance_auditor", END)

    return workflow.compile()


app = create_graph()
