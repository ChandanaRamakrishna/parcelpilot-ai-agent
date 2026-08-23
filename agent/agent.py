"""
Core agentic loop: sends the conversation + tool schemas to Groq, executes
whichever tools it calls, enforces access control and confirmation gating,
feeds tool results back to the model, and repeats until it returns a final answer.
"""

import json
import os

from dotenv import load_dotenv
from groq import Groq

from agent.prompts import SYSTEM_PROMPT
from agent.state import SessionState
from retrieval.source_authority import Evidence, resolve
from tools import data_lookup, document_search, escalation

load_dotenv()

# NOTE: temporarily switched to gpt-oss-120b (from gpt-oss-20b) — same
# family, tool-calling capable, but a SEPARATE per-model rate-limit bucket
# on Groq's free tier. Useful if 20b's daily quota is exhausted from
# testing; switch back to "openai/gpt-oss-20b" once quota resets if you
# want to keep the smaller/faster model for the actual submission.
MODEL = "openai/gpt-oss-120b"


# ---------------------------------------------------------
# TOOL DEFINITIONS AVAILABLE TO THE LLM
# ---------------------------------------------------------

TOOLS = [
    document_search.TOOL_SCHEMA,
    data_lookup.TOOL_SCHEMA,
    escalation.PREPARE_SCHEMA,
    escalation.CREATE_SCHEMA,
]


# ---------------------------------------------------------
# GROQ CLIENT
# ---------------------------------------------------------

client: Groq | None = None


def _get_client() -> Groq:
    global client

    if client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Add it to your environment or .env file."
            )
        client = Groq(api_key=api_key)

    return client


def _tool_schemas_for_groq() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"],
            },
        }
        for tool in TOOLS
    ]


def _message_to_dict(message) -> dict:
    """
    Normalizes a conversation entry to a plain dict for the next API call.

    IMPORTANT: this must preserve tool_calls on assistant messages. Groq's
    tool-calling protocol requires that any "tool" role message be
    immediately preceded, in history, by the assistant message that
    requested it — including that message's tool_calls array. Dropping
    tool_calls here causes a 400 on the *next* turn that involves a tool
    result already in history, not on the current turn.
    """
    if isinstance(message, dict):
        return message

    result = {
        "role": getattr(message, "role", "assistant"),
        "content": getattr(message, "content", None),
    }

    tool_calls = getattr(message, "tool_calls", None)

    if tool_calls:
        result["tool_calls"] = [
            tool_call.model_dump(exclude_none=True)
            if hasattr(tool_call, "model_dump")
            else tool_call
            for tool_call in tool_calls
        ]

    return result


def _tool_call_details(tool_call) -> tuple[str, dict, str]:
    function = getattr(tool_call, "function", None)
    if function is None and isinstance(tool_call, dict):
        function = tool_call.get("function", {})

    if isinstance(function, dict):
        name = function.get("name")
        arguments = function.get("arguments", "{}")
    else:
        name = getattr(function, "name", None)
        arguments = getattr(function, "arguments", "{}")

    tool_call_id = getattr(tool_call, "id", None)
    if tool_call_id is None and isinstance(tool_call, dict):
        tool_call_id = tool_call.get("id")

    if isinstance(arguments, str):
        arguments = json.loads(arguments or "{}")

    return name, arguments, tool_call_id


# ---------------------------------------------------------
# CONVERSATION WINDOWING
# ---------------------------------------------------------

# How many of the most recent user turns to actually send to the model.
# Each turn's tool results (raw_results, authority_resolution, etc.) get
# stored in full in session.conversation, so a long test/demo session
# grows fast — resending the ENTIRE history every turn is what caused a
# single request to exceed Groq's free-tier 8000 TPM cap after only a
# handful of tool-heavy turns. This trims what's SENT to the API without
# discarding session.conversation itself (so escalation/pending_action
# state elsewhere is untouched) — only cuts on user-message boundaries so
# an assistant's tool_calls are never separated from their tool results.
MAX_TURNS_SENT = 4


def _windowed_history(conversation: list[dict]) -> list[dict]:
    user_turn_indices = [i for i, m in enumerate(conversation) if m.get("role") == "user"]
    if len(user_turn_indices) <= MAX_TURNS_SENT:
        return conversation
    cutoff = user_turn_indices[-MAX_TURNS_SENT]
    return conversation[cutoff:]


# ---------------------------------------------------------
# TOOL EXECUTION
# ---------------------------------------------------------

def _execute_tool(
    name: str,
    tool_input: dict,
    session: SessionState,
) -> dict:
    """
    Executes tools requested by the LLM.

    Security-sensitive values such as current_account_id and pending_action
    come from session state, never from the LLM.
    """


    # =====================================================
    # TOOL 1: DOCUMENT SEARCH
    # =====================================================

    if name == "search_documents":

        result = document_search.search_documents(
            query=tool_input["query"],
            current_account_id=session.current_account_id,
            document_type=tool_input.get("document_type"),
        )

        evidence = []

        for r in result["results"]:

            evidence.append(
                Evidence(
                    source=r.get("source", "unknown"),
                    source_type=r.get("source_type", "unknown"),
                    status=r.get("status"),
                    account_scope=r.get("account_scope"),
                    content=r.get("content", ""),
                )
            )

        resolution = resolve(
            evidence,
            account_id=session.current_account_id,
        )

        return {
            "raw_results": result["results"],

            "authority_resolution": {
                "winning_source": (
                    resolution.winning_evidence.source
                    if resolution.winning_evidence
                    else None
                ),

                "winning_source_type": (
                    resolution.winning_evidence.source_type
                    if resolution.winning_evidence
                    else None
                ),

                "explanation": resolution.explanation,

                "conflict_detected": resolution.conflict_detected,

                "should_escalate": resolution.should_escalate,

                "escalate_reason": resolution.escalate_reason,

                "ignored": [
                    {
                        "source": evidence_item.source,
                        "reason": reason,
                    }
                    for evidence_item, reason
                    in resolution.ignored
                ],
            },
        }


    # =====================================================
    # TOOL 2: OPERATIONAL DATA LOOKUP
    # =====================================================

    if name == "lookup_operational_data":

        return data_lookup.lookup_operational_data(
            query_type=tool_input["query_type"],
            current_account_id=session.current_account_id,
            order_id=tool_input.get("order_id"),
            ticket_id=tool_input.get("ticket_id"),
        )


    # =====================================================
    # TOOL 3A: PREPARE ESCALATION
    # =====================================================

    if name == "prepare_escalation":

        result = escalation.prepare_escalation(
            issue=tool_input["issue"],
            reason=tool_input["reason"],
            current_account_id=session.current_account_id,
            related_order=tool_input.get("related_order"),
        )

        session.pending_action = result["pending_action"]

        return result


    # =====================================================
    # TOOL 3B: CREATE ESCALATION
    # =====================================================

    if name == "create_escalation":

        if session.pending_action is None:

            return {
                "error": (
                    "No pending escalation exists. "
                    "You must prepare an escalation and obtain "
                    "explicit user confirmation before creating it."
                )
            }

        result = escalation.create_escalation(
            confirmed=tool_input.get("confirmed", False),
            pending_action=session.pending_action,
        )

        if "result" in result:
            session.pending_action = None

        return result


    # =====================================================
    # UNKNOWN TOOL
    # =====================================================

    return {
        "error": f"Unknown tool: {name}"
    }


# ---------------------------------------------------------
# MAIN AGENT LOOP
# ---------------------------------------------------------

def run_turn(
    user_message: str,
    session: SessionState,
) -> tuple[str, list[dict]]:
    """
    Runs one complete user interaction.

    Flow:
        User message
            ↓
        Model decides whether to call tools
            ↓
        Application executes tools securely
            ↓
        Tool results sent back to the model
            ↓
        Model returns final answer

    Returns (answer_text, tool_trace) — tool_trace is a list of
    {"name", "arguments", "result"} dicts for every tool call made this
    turn (across every iteration of the loop, including multi-step
    requests that call several tools). Exposing this lets the UI show
    which tool was used per the assessment's interface requirement, and
    makes retrieval/logic misses debuggable instead of opaque.
    """

    session.conversation.append({"role": "user", "content": user_message})
    tool_trace: list[dict] = []
    tool_called_this_turn = False

    while True:

        # Force at least one tool call before the model is allowed to
        # answer. Prompt instructions alone ("you must call
        # search_documents before answering") were NOT reliably followed
        # by this model — it would sometimes claim "no policy found"
        # having never actually called search_documents, i.e. a
        # hallucinated absence rather than a real retrieval miss. Once a
        # tool HAS been called this turn, relax back to "auto" so the
        # model can actually finalize an answer instead of looping
        # forever. Trade-off: trivial turns ("thanks!", "ok") will also
        # trigger a tool call now — acceptable for a domain-scoped
        # support agent where a wrong "no evidence found" is far worse
        # than one harmless extra tool call.
        tool_choice = "auto" if tool_called_this_turn else "required"

        request_kwargs = dict(
            model=MODEL,
            max_tokens=1500,
            # Low temperature: this is a support agent making structural
            # decisions (which tool to call, whether account context is
            # already known, whether to escalate), not doing creative
            # writing. Higher default temperature was contributing to
            # inconsistent behavior across identical repeated questions
            # (e.g. sometimes correctly using the injected account
            # context, sometimes asking the user for it unnecessarily).
            temperature=0.1,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT + "\n\n" + session.escalation_rules_note,
                },
                *(_message_to_dict(message) for message in _windowed_history(session.conversation)),
            ],
            tools=_tool_schemas_for_groq(),
        )

        try:
            response = _get_client().chat.completions.create(
                tool_choice=tool_choice,
                **request_kwargs,
            )
        except Exception as e:
            # tool_choice="required" forces every response to be a tool
            # call — but sometimes the model legitimately has nothing
            # tool-relevant to do (e.g. the user's request is too vague
            # to call anything yet, and the right move is a clarifying
            # question). Some models handle that mismatch by silently
            # returning no tool_calls (handled elsewhere below); others
            # (observed with gpt-oss-120b) hard-error instead
            # ("tool_use_failed" / 400), with the model's intended reply
            # visible in the error's failed_generation field but not
            # otherwise recoverable. Rather than crash the whole turn,
            # retry once with tool_choice="auto" so the model can answer
            # in plain text if that's genuinely the right move.
            if tool_choice == "required" and "tool_use_failed" in str(e):
                response = _get_client().chat.completions.create(
                    tool_choice="auto",
                    **request_kwargs,
                )
            else:
                raise

        assistant_message = response.choices[0].message
        session.conversation.append(_message_to_dict(assistant_message))

        tool_calls = getattr(assistant_message, "tool_calls", None) or []

        if not tool_calls:
            if tool_choice == "required":
                # The API said tool_choice="required" but returned zero
                # tool calls anyway — this model has been observed
                # ignoring that constraint (same family of harmony-format
                # flakiness seen elsewhere with gpt-oss on Groq). Rather
                # than trust the provider and let an ungrounded answer
                # through, force a search_documents call ourselves so the
                # model has real evidence to work from on the next
                # iteration instead of answering from memory.
                fallback_id = f"forced_search_{len(tool_trace)}"
                fallback_input = {"query": user_message}

                # Replace the just-stored (tool_call-less) assistant
                # message with one that carries this forced call, so
                # conversation history stays internally consistent for
                # the next request (an assistant message with tool_calls
                # must be immediately followed by matching "tool" messages).
                session.conversation[-1] = {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": fallback_id,
                            "type": "function",
                            "function": {
                                "name": "search_documents",
                                "arguments": json.dumps(fallback_input),
                            },
                        }
                    ],
                }

                output = _execute_tool(
                    name="search_documents",
                    tool_input=fallback_input,
                    session=session,
                )

                tool_trace.append({
                    "name": "search_documents",
                    "arguments": fallback_input,
                    "result": output,
                })

                session.conversation.append(
                    {
                        "role": "tool",
                        "tool_call_id": fallback_id,
                        "name": "search_documents",
                        "content": json.dumps(output),
                    }
                )

                tool_called_this_turn = True
                continue

            return assistant_message.content or "", tool_trace

        tool_called_this_turn = True

        for tool_call in tool_calls:
            name, tool_input, tool_call_id = _tool_call_details(tool_call)

            output = _execute_tool(
                name=name,
                tool_input=tool_input,
                session=session,
            )

            tool_trace.append({
                "name": name,
                "arguments": tool_input,
                "result": output,
            })

            session.conversation.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "name": name,
                    "content": json.dumps(output),
                }
            )
