# Architecture Note

## 1. System Architecture
```
USER → Streamlit Chat UI → AI Agent
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
  search_documents   lookup_operational_data   prepare/create_escalation
        │                     │                     │
     Chroma            SQLite (accounts,        SQLite (escalations)
   (PDFs + agreements)  orders, tickets)
        │                     │
        └──────────┬──────────┘
                    ▼
          Source Authority Engine
                    ▼
     Final Answer / Ask Confirmation / Escalate
```

## 2. Agent Design
- Tool-calling loop in `agent/agent.py` using Groq chat completions with function calling.
- Decision-making: retrieval and authority resolution are separated —
  the model never picks a "winner" among conflicting sources by itself;
  `retrieval/source_authority.py` does that deterministically.
- Escalation conditions are defined explicitly (see `agent/state.py`), not
  left to model judgment alone.
- Session/pending-action state (`agent/state.py`) distinguishes informational
  requests from pending state-changing actions.

## 3. Tool Design
- **search_documents** — semantic search over PDFs with authority metadata.
- **lookup_operational_data** — structured account/order/ticket queries.
- **prepare_escalation / create_escalation** — two-stage, confirmation-gated.

## 4. Access Control
Enforced inside `tools/data_lookup.py`, not via prompting: every row fetch
checks `row.account_id == current_account_id` in code before any data is
returned to the model. The LLM never decides whether access is allowed.

## 5. Source Reliability Model
Authority is ranked by: specificity (customer agreement) > freshness
(current vs deprecated) > document type (policy/SOP > product doc) >
historical usage (tickets = context only). See `Authority` enum in
`retrieval/source_authority.py`.

## 6. Conflict Resolution
Example: customer-specific agreement vs. general cancellation policy —
agreement wins, and the response explains the override explicitly.

## 7. Trade-offs
- Mock authentication (account picker, not real login)
- Local vector DB (Chroma), no reranker
- Customer-facing scope only, not the internal/proactive-detection problem
- Escalation execution is mocked (writes to local SQLite, no ticketing integration)

## 8. Evaluation / Testing
| Test | Expected behavior |
|---|---|
| Cross-account order | Access denied |
| Contract vs policy | Contract wins |
| Current vs deprecated | Current wins |
| Historical incorrect ticket | Not authoritative |
| Unsupported exception | Escalate |
| Escalation without confirmation | Don't execute |

See `tests/`.
