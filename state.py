from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages

class IncidentState(TypedDict):
    # Input
    alert_id: str
    alert_message: str
    alert_source: str

    # Conversation history (required by LangGraph)
    messages: Annotated[list, add_messages]

    # Workflow tracking
    current_stage: str

    # Triage output
    severity: str
    category: str
    confidence_score: float

    # Knowledge base output
    similar_incidents: list
    recommended_actions: list
    knowledge_summary: str

    # Report output
    draft_response: str

    # Supervisor review output
    review_status: str
    final_response: str