"""Tool 1 — search_documents: retrieves PDF-sourced evidence with authority metadata."""
from retrieval import vector_store

TOOL_SCHEMA = {
    "name": "search_documents",
    "description": (
        "Search policies, SOPs, product/known-issues docs, and customer agreements. "
        "Returns chunks tagged with source type, status (CURRENT/DEPRECATED), and "
        "account scope. Does NOT decide which source wins — that's a separate step."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural-language search query",
            },
            "document_type": {
                "type": ["string", "null"],
                "enum": ["contract", "sop", "policy", "product_doc", None],
                "description": "Optional filter to a specific document category",
            },
        },
        "required": ["query"],
    },
}


def search_documents(
    query: str,
    current_account_id: str | None = None,   # injected by the agent from session state, never from the LLM
    document_type: str | None = None,
) -> dict:
    evidence = vector_store.search(
        query=query,
        account_id=current_account_id,
        document_type=document_type,
    )

    # Safety net: a document_type filter narrows retrieval BEFORE search
    # runs, so a wrong guess (e.g. filtering to "policy" when the answer
    # is actually in a "sop" doc) can return zero results even though the
    # answer exists elsewhere in the corpus. Prompt instructions alone
    # didn't reliably stop the model from over-filtering, so if a
    # filtered search comes back empty, retry once with no filter rather
    # than reporting "no evidence found" on a false negative.
    if not evidence and document_type is not None:
        evidence = vector_store.search(
            query=query,
            account_id=current_account_id,
            document_type=None,
        )

    return {
        "results": [
            {
                "source": e.source,
                "source_type": e.source_type,
                "status": e.status,
                "authority": e.authority_rank().name,
                "account_scope": e.account_scope,
                "content": e.content,
            }
            for e in evidence
        ]
    }
