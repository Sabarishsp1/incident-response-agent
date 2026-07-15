from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langgraph.prebuilt import create_react_agent
from tools import triage_alert, generate_incident_report
from state import IncidentState
from dotenv import load_dotenv
from mcp_client import fetch_runbooks, MCPTransportError,MCPToolError

load_dotenv()

llm = ChatAnthropic(model="claude-haiku-4-5-20251001")

# --- Triage Agent ---
triage_agent = create_react_agent(
    model=llm,
    tools=[triage_alert],
    prompt="""You are a triage agent. Your job is to classify incoming system alerts.
Call the triage_alert tool with the alert message and return the severity, category and confidence score.
Be concise and always use the tool."""
)

# --- Report Agent ---
report_agent = create_react_agent(
    model=llm,
    tools=[generate_incident_report],
    prompt="""You are a report generation agent. Generate a structured incident report.
Call the generate_incident_report tool with all available incident details.
Always use the tool."""
)

# --- Supervisor Node Functions ---
def run_triage(state: IncidentState) -> dict:
    result = triage_agent.invoke({
        "messages": [("user", f"Triage this alert: {state['alert_message']}")]
    })
    last_message = result["messages"][-1].content

    # Parse tool result from agent response
    import json
    tool_messages = [m for m in result["messages"] if hasattr(m, "type") and m.type == "tool"]
    if tool_messages:
        triage_data = json.loads(tool_messages[-1].content)
        return {
            "severity": triage_data["severity"],
            "category": triage_data["category"],
            "confidence_score": triage_data["confidence_score"],
            "current_stage": "knowledge_search",
            "messages": result["messages"]
        }
    return {"current_stage": "knowledge_search", "messages": result["messages"]}

def run_knowledge_search(state: IncidentState) -> dict:
    try:
        kb_response = fetch_runbooks(state["category"])

        results = kb_response.get("results", [])

        if not results:
            return {
                "similar_incidents": [],
                "recommended_actions": [],
                "knowledge_summary": "No matching runbook found.",
                "knowledge_relevance": 0.0,
                "current_stage": "report_generation",
            }

        result = results[0]
        runbook = result["runbook"]
        relevance = result["relevance_score"]

        return {
            "similar_incidents": runbook["related_incidents"],
            "recommended_actions": runbook["remediation_steps"],
            "knowledge_summary": (
                f"Found runbook '{runbook['title']}' "
                f"(relevance: {relevance:.1f})"
            ),
            "knowledge_relevance": relevance,
            "current_stage": "report_generation",
        }

    except (MCPTransportError, MCPToolError) as e:
        #
        # Degrade gracefully.
        # Preserve the incident and let the router escalate.
        #
        return {
            "similar_incidents": [],
            "recommended_actions": [],
            "knowledge_summary": (
                f"Knowledge lookup failed: {type(e).__name__}"
            ),
            "knowledge_relevance": 0.0,
            "current_stage": "report_generation",
        }

def run_report_generation(state: IncidentState) -> dict:
    result = report_agent.invoke({
        "messages": [("user", f"""Generate incident report for:
Alert: {state['alert_message']}
Severity: {state['severity']}
Category: {state['category']}
Similar incidents: {state['similar_incidents']}
Recommended actions: {state['recommended_actions']}""")]
    })
    tool_messages = [m for m in result["messages"] if hasattr(m, "type") and m.type == "tool"]
    if tool_messages:
        return {
            "draft_response": tool_messages[-1].content,
            "current_stage": "review",
            "messages": result["messages"]
        }
    return {"current_stage": "review", "messages": result["messages"]}

def run_supervisor_review(state: IncidentState) -> dict:
    review_prompt = f"""
Review this incident report structure.
Severity: {state['severity']}
Category: {state['category']}
Report: {state['draft_response']}

Approve if the report contains:
- A clear severity classification
- At least one similar past incident
- At least three recommended actions

Do not require additional diagnostic data beyond what is in the report.
Respond with APPROVED or NEEDS_REVISION followed by one sentence.
"""
    response = llm.invoke(review_prompt)
    approved = "APPROVED" in response.content.upper()
    return {
        "review_status": "approved" if approved else "needs_revision",
        "final_response": state["draft_response"] if approved else "",
        "current_stage": "completed",
        "messages": [response]
    }

def run_escalation(state: IncidentState) -> dict:
    """
    Escalate incidents when the retrieved knowledge is not
    sufficiently relevant for autonomous handling.
    """

    return {
        "review_status": "escalated",
        "final_response": f"""
Incident has been escalated for human review.

Reason:
Knowledge retrieval confidence was too low
(Relevance Score: {state.get("knowledge_relevance", 0.0):.1f}).

Alert:
{state["alert_message"]}

Generated Incident Report:
{state["draft_response"]}

Recommended Action:
Please hand off this incident to the on-call engineer for further investigation.
""".strip(),
        "current_stage": "completed"
    }