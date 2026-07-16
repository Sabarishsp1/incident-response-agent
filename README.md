# AI Incident Response Orchestrator

A multi-agent system that triages system alerts, retrieves matching runbooks from a
dedicated MCP knowledge server, generates a structured incident report, and — critically —
**routes the incident to a human whenever it isn't confident it found the right guidance.**

Built as Project 3 of an Applied AI Engineer portfolio: taking a working multi-agent
system to production grade.

---

## The core idea: the system knows when it doesn't know

Most agent demos answer confidently whether or not they should. This one measures its own
confidence in the knowledge it retrieved and treats that as a **control signal**, not a
decoration:

| Situation | Relevance score | Outcome |
|---|---|---|
| Exact category match on a runbook | `1.0` | Autonomous handling — supervisor review |
| No matching runbook, generic fallback returned | `0.3` | **Escalate to on-call engineer** |
| Knowledge server unreachable after retry | `0.0` | **Escalate to on-call engineer** |

The threshold is `0.5` — below it, the graph takes a different path. The on-call engineer
still receives the full generated report; the score decides *who handles it and how urgently*,
not whether a report exists.

This means a knowledge-base outage degrades the system into "a human is on point" rather than
crashing the incident. During an outage — exactly when the tool matters most — it does not die.

---

## Architecture

```
Alert
  │
  ▼
┌──────────────┐
│    Triage    │  classifies severity (P1/P2/P3) + category
│    Agent     │  → "unclassified" when it can't categorize
└──────────────┘
  │
  ▼
┌──────────────┐         ┌─────────────────────────┐
│  Knowledge   │ ──MCP──▶│   MCP Knowledge Server  │
│    Search    │  stdio  │  (separate process)     │
│              │◀────────│  search_runbooks(...)   │
└──────────────┘         └─────────────────────────┘
  │  writes knowledge_relevance into state
  ▼
┌──────────────┐
│    Report    │  generates structured incident report
│    Agent     │
└──────────────┘
  │
  ▼
[ route_on_relevance ]  ── relevance < 0.5 ──▶ ┌────────────┐
  │                                            │ Escalation │──▶ END
  │ relevance >= 0.5                           └────────────┘
  ▼
┌──────────────┐
│  Supervisor  │  approves or flags the report
│    Review    │
└──────────────┘
  │
  ▼
 END
```

**Shared state** flows through every node via LangGraph's `StateGraph`. **Checkpointing**
persists state to SQLite at each transition, with per-incident `thread_id` isolation — a
failure in one incident doesn't affect others.

---

## Key Decisions

### Why a separate MCP server instead of an in-process function?

The runbook knowledge base was originally a hardcoded dict inside the agent application.
Exposing it as an MCP server over stdio makes the knowledge layer **independently evolvable** —
it can move from a dict to a database or vector store without touching agent code, and the
contract stays the same.

The cost is real and accepted: a second process to run, a new failure mode (server
unreachable mid-incident), and an async client bridge inside a synchronous graph. Those costs
are what the error handling below exists to manage.

### Why does the relevance score live on the search result, not the runbook?

A runbook sitting in the knowledge base has no inherent score. Score only exists *relative to
a query*. So `SearchResult` wraps `{runbook, relevance_score}` rather than putting a score
field on the runbook itself.

The payoff: the same fallback runbook returns at `1.0` when genuinely requested and `0.3`
when it's a fallback for an unmatched category. Same document, different scores, because the
score describes the match — not the document.

### Why is knowledge search a deterministic call and not a ReAct agent?

Triage and report generation make genuine judgments, so they're LLM agents. Knowledge
retrieval is a deterministic lookup — given a category, fetch the runbook. Wrapping that in a
reasoning loop adds cost and latency for no decision. The node calls the MCP tool directly.

### Why is escalation a conditional edge rather than logic inside the supervisor?

Routing an incident to escalation versus normal review is a **control-flow decision about the
workflow**, not a computation inside a step. Conditional edges express "incidents can flow two
ways from here" in the graph topology itself, rather than burying it in an if-statement.

### Why branch *after* report generation rather than before?

The escalated human still needs the report. Short-circuiting to escalation before report
generation would hand an on-call engineer an alert and nothing else. Generating first means
the human gets everything the system could assemble; the score just flags that it's weak.

### Why Pydantic on the MCP boundary?

The models are the API contract, not internal validation. The tool advertises
`-> SearchRunbooksResponse`, so a client calling `list_tools()` discovers the full response
shape and field descriptions rather than an opaque `dict`.

More importantly, they enforce **invariants, not just types**: `relevance_score` is bounded
`[0.0, 1.0]`, because the entire escalation branch depends on that range meaning something.
A runbook must carry at least one remediation step — a runbook with no guidance is invalid
data, not an empty list.

Today the data is hardcoded, so validation mostly catches my own mistakes early. The moment
the dict becomes a database or an external API, the same layer keeps working without changes
elsewhere.

### Why distinguish transport errors from tool errors?

They fail differently, so they're handled differently:

- **`MCPTransportError`** — the subprocess didn't spawn, the connection dropped. Transient.
  Retried once after a 500ms backoff.
- **`MCPToolError`** — the call succeeded; the server ran the tool and returned an error
  (e.g. a validation failure). The transport worked perfectly. Retrying is pointless and
  would waste seconds during a live incident.

The seam is structural: transport failures raise from the connection machinery; tool errors
arrive as a well-formed response with `isError=True`. Collapsing both into one exception type
makes "retry only transient failures" unimplementable.

This is the retry-then-dead-letter pattern from event-driven systems applied to agent tool
calls — transient errors retry, persistent ones route to human escalation instead of killing
the workflow.

### Why does the MCP server log to a file instead of stdout?

Under stdio transport, **stdout is the protocol channel** — every JSON-RPC message flows
through it. A single `print()` corrupts the stream and the client fails to parse. Server logs
go to a file; the application logs to the console.

Logging levels carry meaning: an exact match is `INFO`, a **fallback is `WARNING`** — every
fallback means a human gets paged, so a rising fallback rate signals that triage categories
are drifting away from runbook coverage.

---

## Failure Modes & Handling

| Failure | Detection | Response |
|---|---|---|
| Knowledge server unreachable | `MCPTransportError` | Retry once after 500ms → degrade to `0.0` → escalate |
| Malformed runbook data | Pydantic `ValidationError` → `MCPToolError` | No retry → degrade → escalate |
| Score outside `[0,1]` | Pydantic bound violation | Fails at the boundary with a named field and constraint |
| Triage can't classify the alert | Category = `unclassified` | No exact match → fallback at `0.3` → escalate |
| Mid-execution node failure | SQLite checkpoint | Resume from last stable node on the same `thread_id` |

**Verified, not assumed.** Each path above was tested by deliberately breaking the system —
pointing the client at a nonexistent server, injecting out-of-range scores, and stripping
required fields — and confirming the incident escalated rather than crashed.

---

## Known Limitations

**Triage uses keyword matching.** Brittle on semantic alerts — "storage engine lock
contention" won't classify as `database`. Fix: replace the keyword matcher with an LLM
classifier in `triage_alert`. The tool/agent separation means this swap doesn't touch agent
logic.

**Severity ignores service criticality.** 800ms latency on a payment service classifies as P3
because the matcher has no notion of service tier. Fix: enrich the alert payload with tier
metadata.

**Relevance scoring is category equality, not similarity.** Scores are currently `1.0` or
`0.3` — a proxy, not a real semantic match. The plumbing (bounded score, threshold routing,
escalation) is what a real similarity search would slot into.

**A new subprocess per knowledge call.** Each `fetch_runbooks` spawns Python, handshakes, and
tears down. Fine at one incident at a time; a persistent connection would be needed under load.

**`asyncio.run()` in the sync bridge.** Correct for the current `graph.invoke()` flow, but it
raises inside an already-running event loop — so this needs revisiting when deployed behind
an async framework like FastAPI.

**Runbooks are hardcoded.** Production would connect to a live knowledge base (Confluence,
PagerDuty, or a RAG system over runbook PDFs). The MCP boundary is what makes that swap
cheap.

---

## Stack

| Component | Choice | Reason |
|---|---|---|
| Agent framework | LangGraph | Shared state, checkpointing, conditional edges |
| Knowledge layer | MCP server (stdio) | Independently evolvable behind a stable contract |
| Contract enforcement | Pydantic | Bounded invariants at the boundary; self-describing tool schema |
| Agent pattern | ReAct | Tool-grounded reasoning where judgment is needed |
| LLM | Claude Haiku | Fast and cheap; sufficient for structured, grounded tasks |
| Checkpointing | SQLite | Zero infrastructure; PostgreSQL for distributed deployment |

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

```
ANTHROPIC_API_KEY=your_key_here
LANGSMITH_API_KEY=your_key_here
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=incident-response-agent
```

Run the orchestrator — the MCP server is launched automatically as a subprocess:

```bash
python main.py
```

Exercise the MCP server directly:

```bash
python mcp_client.py
```

Server logs are written to `logs/mcp_server.log`.

---

## Project Layout

```
main.py           graph construction, routing function, entry point
agents.py         node functions (triage, knowledge, report, review, escalation)
tools.py          triage + report generation tools
state.py          IncidentState schema
mcp_server.py     MCP knowledge server — runbooks + search_runbooks tool
mcp_client.py     async MCP client, retry logic, typed errors, sync bridge
schemas.py        shared Pydantic contract (Runbook, SearchResult, response)
```
