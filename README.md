# AI Incident Response Orchestrator

A multi-agent system that autonomously triages, investigates, and generates 
incident reports for system alerts. Built as Project 2 of an Applied AI 
Engineer portfolio.

---

## Problem

On-call engineers responding to system alerts face three bottlenecks:
1. Manual severity classification wastes critical response time
2. Institutional knowledge of past incidents lives in scattered runbooks
3. Incident report generation is repetitive but requires accuracy

This system automates all three — an alert comes in, agents triage it, 
search historical runbooks, generate a structured report, and route for 
supervisor review without human intervention.

---

## Architecture

Alert Input

│

▼

┌─────────────┐

│   Triage    │ → classifies severity (P1/P2/P3) and category

│    Agent    │

└─────────────┘

│

▼

┌─────────────┐

│  Knowledge  │ → searches runbook for similar incidents

│    Agent    │   and recommended actions

└─────────────┘

│

▼

┌─────────────┐

│   Report    │ → generates structured incident report

│    Agent    │

└─────────────┘

│

▼

┌─────────────┐

│  Supervisor │ → reviews report, approves or flags for revision

│    Agent    │

└─────────────┘

│

▼

Final Incident Report

**Shared state** flows through all agents via LangGraph's `StateGraph`. 
Each agent reads from and writes to the same `IncidentState` object — 
no output passing between functions, no state loss between steps.

**Checkpointing** persists state to SQLite at every node transition. 
Each incident runs on its own `thread_id` — a failure in one incident 
doesn't affect others and resumes from the last stable checkpoint.

---

## Key Decisions

### Why multi-agent over a single agent with multiple tools?
A single agent accumulating results across 4 tool calls bloats the context 
window and mixes concerns. Dedicated agents maintain focused contexts — 
the triage agent only knows about classification, the knowledge agent only 
knows about runbook search. Failures are isolated and debuggable 
independently. Agents can also run in parallel where tasks are independent.

### Why LangGraph over sequential LangChain calls?
LangChain sequential chains work for fixed linear pipelines. LangGraph adds:
- **Shared state** — every node reads from and writes to `IncidentState`
- **Checkpointing** — resume from failure without restarting from scratch
- **Conditional edges** — graph can branch based on state (extensible to 
  retry loops and escalation paths)

### Why ReAct pattern for each agent?
ReAct (Reasoning + Acting) forces agents to call tools and observe results 
before proceeding — preventing hallucinated classifications or fabricated 
runbook entries. Each agent reasons about what tool to call, calls it, 
observes the result, then decides next steps.

### Why SQLite for checkpointing?
Zero infrastructure, runs locally, sufficient for a single-node system. 
Production would use PostgreSQL-backed checkpointing for distributed 
deployments across multiple workers.

### Why separate triage tool from triage agent?
Tools are stateless functions — swap the keyword classifier for an LLM 
classifier without touching agent logic. The agent orchestrates; the tool 
executes. Clean separation means fixing a tool doesn't require rewriting 
the agent.

---

## Failure Modes & Recovery

**Triage misclassification:** Keyword-based triage fails on semantic 
alerts (e.g. "storage engine lock contention" not classified as database). 
Fix: replace keyword matcher with LLM-based classifier in `triage_alert` tool.

**Network severity underclassification:** 800ms latency on a payment 
service classified as P3 instead of P1/P2 — keyword matcher has no 
context about service criticality. Fix: enrich alert payload with service 
tier metadata.

**Supervisor over-rejection:** LLM supervisor applies real-world report 
standards that exceed what minimal alert data can satisfy. Resolved by 
scoping approval criteria to report structure rather than diagnostic completeness.

**Mid-execution failure:** Without checkpointing, any agent failure 
requires full re-execution from triage. With SQLite checkpointing and 
per-incident thread IDs, each incident resumes from its last stable node.

---

## Known Limitations

- Triage uses keyword matching — brittle for semantic or domain-specific alerts
- Runbook is hardcoded — production would connect to a live knowledge base 
  (Confluence, PagerDuty, or a RAG system over runbook PDFs)
- No parallel agent execution yet — agents run sequentially; 
  knowledge search and report generation could run concurrently
- No real escalation path — P1 incidents should page on-call; 
  currently supervisor only approves or flags revision

---

## How to Run

**Requirements:** Python 3.11+, Anthropic API key

```bash
git clone https://github.com/Sabarishsp1/incident-response-agent.git
cd incident-response-agent
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac/Linux
pip install -r requirements.txt
```

Create `.env`:

ANTHROPIC_API_KEY=your_key_here

LANGSMITH_API_KEY=your_key_here

LANGSMITH_TRACING=true

LANGSMITH_PROJECT=incident-response-agent

---

```bash
python main.py
```

---

## Stack

| Component | Choice | Reason |
|---|---|---|
| Agent Framework | LangGraph | Stateful graph, checkpointing, conditional edges |
| Agent Pattern | ReAct | Tool-grounded reasoning, no hallucination |
| LLM | Claude Haiku | Fast, cheap, sufficient for structured tasks |
| Checkpointing | SQLite | Zero infrastructure, local persistence |
| Orchestration | Supervisor + Workers | Focused contexts, isolated failures |

---

## Demonstrated Failure & Recovery

To demonstrate checkpointing, if `report_generation` fails mid-execution, 
re-running with the same `thread_id` resumes from `knowledge_search` output 
without re-running triage. State is preserved in `checkpoints.db`.	