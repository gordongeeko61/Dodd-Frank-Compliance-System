'''
this module defines the Workflow class which manages the execution of a workflow consisting of multiple nodes. It handles the orchestration of node execution, passing data between nodes, and managing the overall workflow state.
its connects the nodes using stategraph from langgraph 

START -> index_video_node -> audio_content_node -> END
'''


from langgraph.graph import StateGraph,END
from backend.src.graph.nodes import VideoAuditState


from backend.src.graph.nodes import (
    index_video_node,
    audio_content_node
)

def create_graph():
    '''
    Creates a StateGraph and adds nodes to it.
    returns runnable graph object.
    '''

    workflow = StateGraph(VideoAuditState)
    workflow.add_node("indexer",index_video_node)
    workflow.add_node("auditor",audio_content_node)

    workflow.set_entry_point("indexer")
    workflow.add_edge("indexer","auditor")
    workflow.add_edge("auditor",END)

    app = workflow.compile()
    return app

###expose this app

app=create_graph()
