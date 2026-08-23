"""
Tool 3 — escalation, deliberately two-stage:

  1. prepare_escalation(...)  -> returns a draft + asks for confirmation.
     Nothing is written yet. The agent stores this as session.pending_action.
  2. create_escalation(confirmed=True) -> only now does it write a record.

The agent layer (agent/agent.py) is responsible for refusing to call
create_escalation unless the user has explicitly confirmed the matching
pending_action in session state — the tool itself also double-checks.
"""
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "processed" / "parcelpilot.db"


PREPARE_SCHEMA = {
    "name": "prepare_escalation",
    "description": "Draft an escalation for human review. Does not create anything yet — returns a summary and asks for user confirmation.",
    "input_schema": {
        "type": "object",
        "properties": {
            "issue": {
                "type": "string"
            },
            "reason": {
                "type": "string"
            },
            "related_order": {
                "type": ["string", "null"]
            },
        },
        "required": ["issue", "reason"],
    },
}

CREATE_SCHEMA = {
    "name": "create_escalation",
    "description": "Actually creates the escalation record. Only call this after the user has explicitly confirmed a prepared escalation.",
    "input_schema": {
        "type": "object",
        "properties": {"confirmed": {"type": "boolean"}},
        "required": ["confirmed"],
    },
}


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS escalations (
            escalation_id TEXT PRIMARY KEY,
            account_id TEXT,
            issue TEXT,
            reason TEXT,
            related_order TEXT,
            created_at TEXT
        )
    """)


def prepare_escalation(issue: str, reason: str, current_account_id: str, related_order: str | None = None) -> dict:
    draft = {
        "type": "create_escalation",
        "data": {
            "issue": issue,
            "reason": reason,
            "related_order": related_order,
            "account_id": current_account_id,
        },
    }
    return {
        "pending_action": draft,
        "summary": (
            f"I can create an escalation with:\n\n"
            f"Issue: {issue}\n"
            f"Order: {related_order or 'N/A'}\n"
            f"Reason: {reason}\n\n"
            f"Would you like me to proceed?"
        ),
    }


def create_escalation(confirmed: bool, pending_action: dict | None) -> dict:
    if not confirmed:
        return {"error": "Escalation not created — confirmation was not given."}
    if not pending_action or pending_action.get("type") != "create_escalation":
        return {"error": "No matching pending escalation found in session state. Call prepare_escalation first."}

    data = pending_action["data"]
    conn = sqlite3.connect(DB_PATH)
    _ensure_table(conn)
    escalation_id = f"ESC-{uuid.uuid4().hex[:8].upper()}"
    conn.execute(
        "INSERT INTO escalations (escalation_id, account_id, issue, reason, related_order, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (
            escalation_id,
            data["account_id"],
            data["issue"],
            data["reason"],
            data.get("related_order"),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    return {"result": {"escalation_id": escalation_id, "status": "created"}}
