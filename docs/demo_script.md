# ~5 Minute Demo Script

**0:00–0:40 — Problem + architecture**
Show the diagram: User → Agent → Tools → Sources → Trust layer. State the
problem chosen (Trust & Reliability) and why.

**0:40–2:30 — Multi-step example**
Ask: "Can Northstar cancel ORD-1001 without a cancellation fee?"
Narrate as it happens: data lookup → agreement search → current policy
search → conflict resolution → final answer with sources.

**2:30–3:15 — Access control**
While logged in as Northstar, ask: "Tell me about LumenWorks' order
ORD-XXXX." Show the access-denied response. Explain it's enforced in the
tool layer, not by prompting.

**3:15–4:00 — Trust/conflict example**
Trigger a CURRENT vs DEPRECATED policy conflict, or a contract vs general
policy conflict. Show the trust panel / explanation.

**4:00–4:30 — Escalation**
Ask something requiring human judgment. Show prepare_escalation's draft,
confirm, then create_escalation actually firing.

**4:30–5:00 — Decisions + future**
Why customer-facing, why Trust & Reliability, trade-offs made, what's next.
