"""
Tool 2 — lookup_operational_data.

Access control is enforced HERE, in code, not left to the LLM's judgment.
The model can ask for anything; if the row's account_id doesn't match the
authenticated session's account_id, this function refuses before any data
reaches the model's context.
"""
import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "processed" / "parcelpilot.db"

TOOL_SCHEMA = {
    "name": "lookup_operational_data",
    "description": (
        "Look up account, order, or ticket data. Access is restricted to the "
        "currently authenticated account — requests for other accounts' data "
        "are denied regardless of what the user asks."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query_type": {
                "type": "string",
                "enum": ["get_account", "get_order", "get_ticket", "get_tickets_for_order", "get_orders_for_account"],
            },
            "order_id": {"type": "string"},
            "ticket_id": {"type": "string"},
        },
        "required": ["query_type"],
    },
}


def _conn():
    return sqlite3.connect(DB_PATH)


def lookup_operational_data(
    query_type: str,
    current_account_id: str,           # injected by the agent from session state, never from the LLM
    order_id: str | None = None,
    ticket_id: str | None = None,
) -> dict:
    conn = _conn()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        if query_type == "get_account":
            row = cur.execute("SELECT * FROM accounts WHERE account_id = ?", (current_account_id,)).fetchone()
            return {"result": dict(row)} if row else {"error": "Account not found"}

        if query_type == "get_order":
            if not order_id:
                return {"error": "order_id is required"}
            row = cur.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
            if not row:
                return {"error": f"Order {order_id} not found"}
            if row["account_id"] != current_account_id:
                return {"error": "Access denied: this order does not belong to the current account."}
            return {"result": dict(row)}

        if query_type == "get_orders_for_account":
            rows = cur.execute("SELECT * FROM orders WHERE account_id = ?", (current_account_id,)).fetchall()
            return {"result": [dict(r) for r in rows]}

        if query_type == "get_ticket":
            if not ticket_id:
                return {"error": "ticket_id is required"}
            row = cur.execute("SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,)).fetchone()
            if not row:
                return {"error": f"Ticket {ticket_id} not found"}
            if row["account_id"] != current_account_id:
                return {"error": "Access denied: this ticket does not belong to the current account."}
            return {"result": dict(row)}

        if query_type == "get_tickets_for_order":
            if not order_id:
                return {"error": "order_id is required"}
            order_row = cur.execute("SELECT account_id FROM orders WHERE order_id = ?", (order_id,)).fetchone()
            if not order_row:
                return {"error": f"Order {order_id} not found"}
            if order_row["account_id"] != current_account_id:
                return {"error": "Access denied: this order does not belong to the current account."}
            rows = cur.execute("SELECT * FROM tickets WHERE order_id = ?", (order_id,)).fetchall()
            return {"result": [dict(r) for r in rows]}

        return {"error": f"Unknown query_type: {query_type}"}
    finally:
        conn.close()
