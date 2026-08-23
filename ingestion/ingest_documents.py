"""
Chunks and embeds the supplied PDFs into Chroma, tagging each chunk with
authority metadata and account scope.

Usage:
    python -m ingestion.ingest_documents --docs data/raw/documents/
"""

import argparse
import re
from pathlib import Path

import chromadb
from pypdf import PdfReader


BASE_DIR = Path(__file__).resolve().parent.parent
CHROMA_DIR = str(BASE_DIR / "data" / "processed" / "chroma")

COLLECTION_NAME = "documents"


# Authority tiers:
# customer contract > current policy/SOP > product documentation
# > deprecated policy
CLASSIFY_RULES = [
    (
        re.compile(r"agreement|contract", re.I),
        {
            "source_type": "contract",
            "authority": "high",
            "status": "CURRENT",
        },
    ),
    (
        re.compile(r"sop", re.I),
        {
            "source_type": "sop",
            "authority": "medium-high",
            "status": "CURRENT",
        },
    ),
    (
        re.compile(r"deprecated|_v[0-9]+_old|archive", re.I),
        {
            "source_type": "policy",
            "authority": "low",
            "status": "DEPRECATED",
        },
    ),
    (
        re.compile(r"policy", re.I),
        {
            "source_type": "policy",
            "authority": "medium-high",
            "status": "CURRENT",
        },
    ),
    (
        re.compile(r"known.?issue|product", re.I),
        {
            "source_type": "product_doc",
            "authority": "medium",
            "status": "CURRENT",
        },
    ),
]


def classify(filename: str) -> dict:
    """Assign document type and authority metadata."""

    for pattern, meta in CLASSIFY_RULES:
        if pattern.search(filename):
            return meta.copy()

    return {
        "source_type": "unknown",
        "authority": "low",
        "status": "UNKNOWN",
    }


def get_account_scope(filename: str, source_type: str) -> str:
    """
    Customer contracts are visible only to the matching account.

    Other company-wide policies/SOPs/product documents use ALL.
    """

    if source_type != "contract":
        return "ALL"

    filename_lower = filename.lower()

    if "northstar" in filename_lower:
        return "ACCT-001"

    if "lumenworks" in filename_lower:
        return "ACCT-002"

    return "ALL"


def chunk_text(
    text: str,
    chunk_size: int = 800,
    overlap: int = 150,
) -> list[str]:

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        chunks.append(text[start:end])

        start = end - overlap

    return [chunk.strip() for chunk in chunks if chunk.strip()]


def ingest(docs_dir: str) -> None:

    client = chromadb.PersistentClient(path=CHROMA_DIR)

    # Delete old collection so rerunning ingestion does not create
    # duplicate chunks.
    try:
        client.delete_collection(COLLECTION_NAME)
        print("[info] Removed existing collection")
    except Exception:
        pass

    collection = client.get_or_create_collection(
        COLLECTION_NAME
    )

    doc_id = 0

    for pdf_path in sorted(Path(docs_dir).glob("*.pdf")):

        meta = classify(pdf_path.name)

        account_scope = get_account_scope(
            pdf_path.name,
            meta["source_type"],
        )

        reader = PdfReader(str(pdf_path))

        full_text = "\n".join(
            page.extract_text() or ""
            for page in reader.pages
        )

        chunks = chunk_text(full_text)

        for i, chunk in enumerate(chunks):

            collection.add(
                ids=[f"doc_{doc_id}_{i}"],
                documents=[chunk],
                metadatas=[
                    {
                        "source": pdf_path.stem,
                        "account_scope": account_scope,
                        **meta,
                    }
                ],
            )

        print(
            f"[ok] {pdf_path.name}: "
            f"{len(chunks)} chunks | "
            f"type={meta['source_type']} | "
            f"status={meta['status']} | "
            f"scope={account_scope}"
        )

        doc_id += 1

    print(
        f"\nDone. Collection '{COLLECTION_NAME}' "
        f"persisted at:\n{CHROMA_DIR}"
    )


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--docs",
        required=True,
        help="Directory containing source PDFs",
    )

    args = parser.parse_args()

    ingest(args.docs)