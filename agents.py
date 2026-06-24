from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langgraph.prebuilt import create_react_agent
from tools import triage_alert, search_knowledge_base, generate_incident_report
from state import IncidentState
from dotenv import load_dotenv

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

# --- Knowledge Base Agent ---
knowledge_agent = create_react_agent(
    model=llm,
    tools=[search_knowledge_base],
    prompt="""You are a knowledge base agent. Given an incident category, search the runbook.
Call the search_knowledge_base tool with the category and return similar incidents and recommended actions.
Always use the tool."""
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
    result = knowledge_agent.invoke({
        "messages": [("user", f"Search runbook for category: {state['category']}")]
    })
    tool_messages = [m for m in result["messages"] if hasattr(m, "type") and m.type == "tool"]
    if tool_messages:
        import json
        kb_data = json.loads(tool_messages[-1].content)
        return {
            "similar_incidents": kb_data["similar_incidents"],
            "recommended_actions": kb_data["recommended_actions"],
            "knowledge_summary": kb_data["knowledge_summary"],
            "current_stage": "report_generation",
            "messages": result["messages"]
        }
    return {"current_stage": "report_generation", "messages": result["messages"]}

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