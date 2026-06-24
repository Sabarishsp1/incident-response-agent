from langchain_core.tools import tool

RUNBOOK = {
    "database": {
        "similar_incidents": [
            "INC-2024-089: MySQL CPU spike to 98% - resolved by killing long-running queries",
            "INC-2024-134: PostgreSQL connection pool exhausted - resolved by restarting pgBouncer",
            "INC-2024-201: MongoDB memory pressure - resolved by adding index on query field"
        ],
        "recommended_actions": [
            "1. Identify and kill long-running queries immediately",
            "2. Check active connections and kill idle ones",
            "3. Review slow query log for the past 30 minutes",
            "4. Check if any batch jobs are running unexpectedly",
            "5. Consider read replica failover if primary is unresponsive"
        ]
    },
    "network": {
        "similar_incidents": [
            "INC-2024-045: Network latency spike between services - resolved by restarting load balancer",
            "INC-2024-112: DNS resolution failures - resolved by flushing DNS cache on affected nodes"
        ],
        "recommended_actions": [
            "1. Check network interface errors and packet loss",
            "2. Verify load balancer health checks",
            "3. Review firewall rules for recent changes",
            "4. Test connectivity between affected services"
        ]
    },
    "memory": {
        "similar_incidents": [
            "INC-2024-067: JVM heap exhaustion causing OOM kills - resolved by increasing heap size",
            "INC-2024-156: Memory leak in payment service - resolved by rolling restart"
        ],
        "recommended_actions": [
            "1. Identify process consuming excess memory",
            "2. Check for memory leaks in recent deployments",
            "3. Review garbage collection logs",
            "4. Consider rolling restart of affected service"
        ]
    },
    "cpu": {
        "similar_incidents": [
            "INC-2024-023: CPU spike due to infinite loop in worker - resolved by restarting worker",
            "INC-2024-178: High CPU from malformed regex in API - resolved by deploying hotfix"
        ],
        "recommended_actions": [
            "1. Identify process consuming excess CPU with top/htop",
            "2. Check for recent deployments that may have introduced the issue",
            "3. Review application logs for errors or infinite loops",
            "4. Consider scaling horizontally if load-related"
        ]
    },
    "disk": {
        "similar_incidents": [
            "INC-2024-055: Disk usage hit 95% on app-server - resolved by clearing old logs",
            "INC-2024-143: Log rotation misconfiguration caused disk fill - resolved by fixing logrotate"
        ],
        "recommended_actions": [
            "1. Identify large files and directories with du -sh /*",
            "2. Clear old application logs if safe to do so",
            "3. Check log rotation configuration",
            "4. Consider archiving or moving old data",
            "5. Alert if usage exceeds 90% - escalate immediately"
        ]
    },
    "default": {
        "similar_incidents": [
            "INC-2024-099: Generic service degradation - resolved by rolling restart",
        ],
        "recommended_actions": [
            "1. Check service health endpoints",
            "2. Review recent deployments and config changes",
            "3. Escalate to on-call engineer if unresolved within 15 minutes"
        ]
    }
}

@tool
def triage_alert(alert_message: str) -> dict:
    """Classify the severity and category of an incoming alert."""
    alert_lower = alert_message.lower()

    # Category detection
    if any(word in alert_lower for word in ["database", "db", "mysql", "postgres", "mongo", "sql"]):
        category = "database"
    elif any(word in alert_lower for word in ["network", "latency", "dns", "connection", "timeout"]):
        category = "network"
    elif any(word in alert_lower for word in ["memory", "heap", "oom", "ram"]):
        category = "memory"
    elif any(word in alert_lower for word in ["cpu", "processor"]):
        category = "cpu"
    elif any(word in alert_lower for word in ["disk", "storage", "space", "filesystem"]):
        category = "disk"
    else:
        category = "default"

    # Severity detection
    if any(word in alert_lower for word in ["critical", "down", "outage", "95%", "98%", "100%", "failed"]):
        severity = "P1"
        confidence = 0.92
    elif any(word in alert_lower for word in ["high", "warning", "80%", "85%", "90%", "degraded"]):
        severity = "P2"
        confidence = 0.85
    else:
        severity = "P3"
        confidence = 0.75

    return {
        "severity": severity,
        "category": category,
        "confidence_score": confidence
    }

@tool
def search_knowledge_base(category: str) -> dict:
    """Search the runbook for similar incidents and recommended actions."""
    result = RUNBOOK.get(category, RUNBOOK["default"])
    return {
        "similar_incidents": result["similar_incidents"],
        "recommended_actions": result["recommended_actions"],
        "knowledge_summary": f"Found {len(result['similar_incidents'])} similar incidents for category: {category}"
    }

@tool
def generate_incident_report(
    alert_message: str,
    severity: str,
    category: str,
    similar_incidents: list,
    recommended_actions: list
) -> str:
    """Generate a structured incident report."""
    incidents_text = "\n".join([f"  - {i}" for i in similar_incidents])
    actions_text = "\n".join([f"  {a}" for a in recommended_actions])

    report = f"""
INCIDENT REPORT
===============
Alert    : {alert_message}
Severity : {severity}
Category : {category.upper()}

SIMILAR PAST INCIDENTS:
{incidents_text}

RECOMMENDED ACTIONS:
{actions_text}

STATUS: Under Investigation
"""
    return report.strip()