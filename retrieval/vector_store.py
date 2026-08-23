"""Thin wrapper around the Chroma collection used by tools/document_search.py."""

import chromadb

from retrieval.source_authority import Evidence


CHROMA_DIR = "data/processed/chroma"
COLLECTION_NAME = "documents"

_client = None
_collection = None


def get_collection():
    global _client, _collection

    if _collection is None:
        _client = chromadb.PersistentClient(path=CHROMA_DIR)
        _collection = _client.get_or_create_collection(COLLECTION_NAME)

    return _collection


def search(
    query: str,
    account_id: str | None = None,
    document_type: str | None = None,
    n_results: int = 5,
) -> list[Evidence]:

    collection = get_collection()

    where = {}

    if document_type:
        where["source_type"] = document_type

    # Retrieve extra results so unauthorized contracts can be filtered out
    results = collection.query(
        query_texts=[query],
        n_results=n_results + 5,
        where=where or None,
    )

    evidence = []

    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]

    for doc, meta in zip(docs, metas):

        scope = meta.get("account_scope", "ALL")

        # Account-scoped contracts can only be returned
        # to their matching account.
        if (
            meta.get("source_type") == "contract"
            and scope != "ALL"
            and scope != account_id
        ):
            continue

        evidence.append(
            Evidence(
                source=meta.get("source", "unknown"),
                source_type=meta.get("source_type", "unknown"),
                status=meta.get("status"),
                account_scope=scope,
                content=doc,
            )
        )

        if len(evidence) >= n_results:
            break

    return evidence