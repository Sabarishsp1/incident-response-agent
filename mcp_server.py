from mcp.server.fastmcp import FastMCP
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
            "INC-2024-089: MySQL CPU spike to 98% - resolved by killing long-running queries",
            "INC-2024-134: PostgreSQL connection pool exhausted - resolved by restarting pgBouncer",
            "INC-2024-201: MongoDB memory pressure - resolved by adding index on query field"
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
            "INC-2024-045: Network latency spike between services - resolved by restarting load balancer",
            "INC-2024-112: DNS resolution failures - resolved by flushing DNS cache on affected nodes"
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
            "INC-2024-067: JVM heap exhaustion causing OOM kills - resolved by increasing heap size",
            "INC-2024-156: Memory leak in payment service - resolved by rolling restart"
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
            "INC-2024-023: CPU spike due to infinite loop in worker - resolved by restarting worker",
            "INC-2024-178: High CPU from malformed regex in API - resolved by deploying hotfix"
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
            "INC-2024-055: Disk usage hit 95% on app-server - resolved by clearing old logs",
            "INC-2024-143: Log rotation misconfiguration caused disk fill - resolved by fixing logrotate"
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
            "INC-2024-099: Generic service degradation - resolved by rolling restart"
        ]
    }
}
@mcp.tool()
def search_runbooks(category: str) -> dict:
    """Search the knowledge base for runbooks matching an incident category."""

    category = category.lower()

    # Exact category match
    if category in RUNBOOKS:
        return {
            "results": [
                {
                    "runbook": RUNBOOKS[category],
                    "relevance_score": 1.0
                }
            ]
        }

    # Fallback to generic runbook
    return {
        "results": [
            {
                "runbook": RUNBOOKS["default"],
                "relevance_score": 0.3
            }
        ]
    }
if __name__ == "__main__":
    mcp.run()