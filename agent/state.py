"""Minimal per-session state: who's logged in, and any pending state-changing action."""
from dataclasses import dataclass, field


@dataclass
class SessionState:
    current_account_id: str
    conversation: list[dict] = field(default_factory=list)  # Groq/OpenAI-style message format
    pending_action: dict | None = None
    escalation_rules_note: str = (
        "Escalate when: (1) no sufficiently authoritative source exists, "
        "(2) two authoritative sources conflict, (3) the customer requests an "
        "unsupported exception, (4) required operational data is missing, "
        "(5) the requested action is outside available tools, or "
        "(6) evidence/confidence is insufficient."
    )
