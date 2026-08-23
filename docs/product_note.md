# Product Note

## Problem chosen
Trust & Reliability (customer-facing chatbot)

## How addressed
- Source metadata (type, status, account scope) attached at ingestion
- Explicit authority hierarchy, not similarity-only retrieval
- Freshness awareness (current vs. deprecated policy)
- Conflict detection between equally-authoritative sources
- Explicit, rule-based escalation conditions
- Source transparency — every answer cites what it used and what it ignored, and why
- Confirmation required before any state-changing action (escalation creation)

## Success metric
**Correct Autonomous Resolution Rate**

```
Correct Autonomous Resolution Rate =
   (Queries resolved without escalation AND without later correction)
   / (Total customer queries)
```

This is deliberately stricter than a plain resolution rate, which can be
gamed by confidently answering everything. It rewards automation *and*
correctness together — the right metric for a Trust & Reliability system.

## What I would build next
1. Real authentication + RBAC (most important before production)
2. Human review workflow for escalations (approve/correct)
3. Feedback loop from corrected answers and ticket outcomes
4. Proactive issue detection (the second client problem, as an internal dashboard)
5. Monitoring: hallucination rate, escalation rate, source-conflict rate, tool failure rate
