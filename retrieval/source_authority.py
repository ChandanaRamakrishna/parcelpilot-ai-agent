"""
The piece that differentiates this from a plain RAG chatbot: given a set of
retrieved chunks (possibly conflicting), decide which one governs the
answer, and produce a human-readable explanation of why.

This does NOT pick answers by embedding similarity alone. It applies an
explicit, inspectable authority hierarchy.
"""
from dataclasses import dataclass, field
from enum import IntEnum


class Authority(IntEnum):
    HISTORICAL_TICKET = 0   # context only, never authoritative on its own
    DEPRECATED_POLICY = 1
    PRODUCT_DOC = 2
    CURRENT_POLICY = 3
    CURRENT_SOP = 3          # same tier as current policy; more specific wins on tie
    CUSTOMER_AGREEMENT = 4   # highest — overrides general policy for that account


AUTHORITY_LABELS = {
    "contract": Authority.CUSTOMER_AGREEMENT,
    "sop": Authority.CURRENT_SOP,
    "policy_current": Authority.CURRENT_POLICY,
    "policy_deprecated": Authority.DEPRECATED_POLICY,
    "product_doc": Authority.PRODUCT_DOC,
    "historical_ticket": Authority.HISTORICAL_TICKET,
}


@dataclass
class Evidence:
    source: str
    source_type: str          # contract | sop | policy | product_doc | historical_ticket
    status: str | None = None  # CURRENT | DEPRECATED | None
    account_scope: str | None = None  # account_id this evidence applies to, or "ALL"
    content: str = ""

    def authority_rank(self) -> Authority:
        if self.source_type == "contract":
            return Authority.CUSTOMER_AGREEMENT
        if self.source_type == "sop":
            return Authority.CURRENT_SOP
        if self.source_type == "policy":
            return Authority.DEPRECATED_POLICY if self.status == "DEPRECATED" else Authority.CURRENT_POLICY
        if self.source_type == "product_doc":
            return Authority.PRODUCT_DOC
        if self.source_type == "historical_ticket":
            return Authority.HISTORICAL_TICKET
        return Authority.HISTORICAL_TICKET  # unknown -> treat as lowest, never trust blindly


@dataclass
class Resolution:
    winning_evidence: Evidence | None
    used: list[Evidence] = field(default_factory=list)
    ignored: list[tuple[Evidence, str]] = field(default_factory=list)  # (evidence, reason)
    conflict_detected: bool = False
    explanation: str = ""
    should_escalate: bool = False
    escalate_reason: str | None = None


def resolve(evidence_list: list[Evidence], account_id: str | None = None) -> Resolution:
    """
    Core conflict-resolution logic. Filters evidence to what's actually
    scoped to this account/query, ranks by authority, and returns a
    single governing answer plus an explanation of what was ignored and why.
    """
    if not evidence_list:
        return Resolution(
            winning_evidence=None,
            should_escalate=True,
            escalate_reason="No sufficiently authoritative source was found for this query.",
        )

    used, ignored = [], []
    for e in evidence_list:
        if e.account_scope and e.account_scope != "ALL" and account_id and e.account_scope != account_id:
            ignored.append((e, f"Not applicable to account {account_id}"))
            continue
        if e.authority_rank() == Authority.DEPRECATED_POLICY:
            ignored.append((e, "Deprecated — superseded by current policy"))
            continue
        if e.authority_rank() == Authority.HISTORICAL_TICKET:
            ignored.append((e, "Historical ticket resolution — context only, not authoritative"))
            continue
        used.append(e)

    if not used:
        return Resolution(
            winning_evidence=None,
            ignored=ignored,
            should_escalate=True,
            escalate_reason="Only low-authority or out-of-scope evidence was found.",
        )

    used.sort(key=lambda e: e.authority_rank(), reverse=True)
    top = used[0]
    conflict = len(used) > 1 and used[0].authority_rank() != used[1].authority_rank()

    # Two sources tied at the SAME top authority tier with different content
    # is the "two authoritative sources conflict" escalation case.
    tie_conflict = (
        len(used) > 1
        and used[0].authority_rank() == used[1].authority_rank()
        and used[0].content.strip() != used[1].content.strip()
    )
    if tie_conflict:
        return Resolution(
            winning_evidence=None,
            used=used,
            ignored=ignored,
            conflict_detected=True,
            should_escalate=True,
            escalate_reason="Two equally authoritative sources conflict — requires human review.",
        )

    explanation = f"Governing source: {top.source} ({top.source_type}, rank={top.authority_rank().name})."
    if conflict:
        explanation += f" Overrides {used[1].source} ({used[1].source_type})."

    return Resolution(
        winning_evidence=top,
        used=used,
        ignored=ignored,
        conflict_detected=conflict,
        explanation=explanation,
        should_escalate=False,
    )
