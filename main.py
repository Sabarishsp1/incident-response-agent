from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from state import IncidentState
from agents import run_triage, run_knowledge_search, run_report_generation, run_supervisor_review
from dotenv import load_dotenv
import sqlite3

load_dotenv()

def build_graph(checkpointer):
    graph = StateGraph(IncidentState)

    graph.add_node("triage", run_triage)
    graph.add_node("knowledge_search", run_knowledge_search)
    graph.add_node("report_generation", run_report_generation)
    graph.add_node("supervisor_review", run_supervisor_review)

    graph.set_entry_point("triage")
    graph.add_edge("triage", "knowledge_search")
    graph.add_edge("knowledge_search", "report_generation")
    graph.add_edge("report_generation", "supervisor_review")
    graph.add_edge("supervisor_review", END)

    return graph.compile(checkpointer=checkpointer)

def run_incident(alert_message: str, alert_source: str = "Datadog", thread_id: str = "thread-1"):
    with SqliteSaver.from_conn_string("checkpoints.db") as checkpointer:
        graph = build_graph(checkpointer)

        initial_state = {
            "alert_id": "ALT-001",
            "alert_message": alert_message,
            "alert_source": alert_source,
            "messages": [],
            "current_stage": "triage",
            "severity": "",
            "category": "",
            "confidence_score": 0.0,
            "similar_incidents": [],
            "recommended_actions": [],
            "knowledge_summary": "",
            "draft_response": "",
            "review_status": "",
            "final_response": ""
        }

        config = {"configurable": {"thread_id": thread_id}}

        print(f"\nProcessing alert: {alert_message}")
        print("=" * 60)

        result = graph.invoke(initial_state, config=config)

        print(f"Severity  : {result['severity']}")
        print(f"Category  : {result['category']}")
        print(f"Confidence: {result['confidence_score']}")
        print(f"Review    : {result['review_status']}")
        print(f"\nFinal Report:\n{result['final_response'] or result['draft_response']}")

        return result

if __name__ == "__main__":
    run_incident("Database CPU usage exceeded 95% on prod-db-01", thread_id="INC-001")
    run_incident("Network latency spike to 800ms between payment service and order service", thread_id="INC-002")
    run_incident("Disk space warning at 85% on app-server-03", thread_id="INC-003")