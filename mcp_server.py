from mcp.server.fastmcp import FastMCP
from schemas import (
    Runbook,
    SearchResult,
    SearchRunbooksResponse,
)
mcp = FastMCP("incident-knowledge-base")

RUNBOOKS = {
    "database": {
        "runbook_id": "RB-001",
        "title": "High Database CPU / Resource Pressure",
        "category": "database",
        "summary": "Database under heavy load — high CPU, connection exhaustion, or memory pressure, typically from long-running queries, missing indexes, or connection leaks.",
        "remediation_steps": [
            "Identify and kill long-running queries immediately",
            "Check active connections and kill idle ones",
            "Review slow query log for the past 30 minutes",
            "Check if any batch jobs are running unexpectedly",
            "Consider read replica failover if primary is unresponsive"
        ],
        "related_incidents": [
            {
                "incident_id": "INC-2024-089",
                "description": "MySQL CPU spike to 98%",
                "resolution": "Killed long-running queries"
            },
            {
                "incident_id": "INC-2024-134",
                "description": "PostgreSQL connection pool exhausted",
                "resolution": "Restarted pgBouncer"
            },
            {
                "incident_id": "INC-2024-201",
                "description": "MongoDB memory pressure",
                "resolution": "Added missing index"
            }
        ]
    },
    "network": {
        "runbook_id": "RB-002",
        "title": "Network Latency / Connectivity Investigation",
        "category": "network",
        "summary": "Increased network latency or connectivity failures affecting inter-service communication.",
        "remediation_steps": [
            "Check network interface errors and packet loss",
            "Verify load balancer health checks",
            "Review firewall rules for recent changes",
            "Test connectivity between affected services"
        ],
        "related_incidents": [
            {
                "incident_id": "INC-2024-045",
                "description": "Network latency spike between services",
                "resolution": "Restarted load balancer"
            },
            {
                "incident_id": "INC-2024-112",
                "description": "DNS resolution failures",
                "resolution": "Flushed DNS cache on affected nodes"
            }
        ]
    },
    "memory": {
        "runbook_id": "RB-003",
        "title": "Memory Exhaustion / OOM",
        "category": "memory",
        "summary": "Service consuming excess memory or hitting OOM kills, often from leaks or undersized heap.",
        "remediation_steps": [
            "Identify process consuming excess memory",
            "Check for memory leaks in recent deployments",
            "Review garbage collection logs",
            "Consider rolling restart of affected service"
        ],
        "related_incidents": [
            {
                "incident_id": "INC-2024-067",
                "description": "JVM heap exhaustion causing OOM kills",
                "resolution": "Increased heap size"
            },
            {
                "incident_id": "INC-2024-156",
                "description": "Memory leak in payment service",
                "resolution": "Rolling restart"
            }
        ]
    },
    "cpu": {
        "runbook_id": "RB-004",
        "title": "High CPU Utilization",
        "category": "cpu",
        "summary": "Sustained high CPU usage, commonly from runaway processes, infinite loops, or load spikes.",
        "remediation_steps": [
            "Identify process consuming excess CPU with top/htop",
            "Check for recent deployments that may have introduced the issue",
            "Review application logs for errors or infinite loops",
            "Consider scaling horizontally if load-related"
        ],
        "related_incidents": [
            {
                "incident_id": "INC-2024-023",
                "description": "CPU spike due to infinite loop in worker",
                "resolution": "Restarted worker"
            },
            {
                "incident_id": "INC-2024-178",
                "description": "High CPU from malformed regex in API",
                "resolution": "Deployed hotfix"
            }
        ]
    },
    "disk": {
        "runbook_id": "RB-005",
        "title": "Disk Space / Filesystem Pressure",
        "category": "disk",
        "summary": "Disk usage approaching capacity, risking write failures and service degradation.",
        "remediation_steps": [
            "Identify large files and directories with du -sh /*",
            "Clear old application logs if safe to do so",
            "Check log rotation configuration",
            "Consider archiving or moving old data",
            "Alert if usage exceeds 90% - escalate immediately"
        ],
        "related_incidents": [
            {
                "incident_id": "INC-2024-055",
                "description": "Disk usage hit 95% on app-server",
                "resolution": "Cleared old logs"
            },
            {
                "incident_id": "INC-2024-143",
                "description": "Log rotation misconfiguration caused disk fill",
                "resolution": "Fixed logrotate configuration"
            }
        ]
    },
    "default": {
        "runbook_id": "RB-000",
        "title": "Generic Service Degradation",
        "category": "default",
        "summary": "No specific category matched — general triage and escalation path.",
        "remediation_steps": [
            "Check service health endpoints",
            "Review recent deployments and config changes",
            "Escalate to on-call engineer if unresolved within 15 minutes"
        ],
        "related_incidents": [
            {
                "incident_id": "INC-2024-099",
                "description": "Generic service degradation",
                "resolution": "Rolling restart"
            }
        ]
    }
}
@mcp.tool()
def search_runbooks(category: str) -> SearchRunbooksResponse:
    """Search the knowledge base for runbooks matching an incident category."""

    category = category.lower()

    if category in RUNBOOKS:
        runbook = Runbook(**RUNBOOKS[category])

        return SearchRunbooksResponse(
            results=[
                SearchResult(
                    runbook=runbook,
                    relevance_score=1.0
                )
            ]
        )

    runbook = Runbook(**RUNBOOKS["default"])

    return SearchRunbooksResponse(
        results=[
            SearchResult(
                runbook=runbook,
                relevance_score=0.3
            )
        ]
    )
if __name__ == "__main__":
    mcp.run()