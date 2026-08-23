import chromadb

client = chromadb.PersistentClient(path="data/processed/chroma")

try:
    collection = client.get_collection("documents")

    print(f"Collection 'documents' exists with {collection.count()} chunks.")

    if collection.count() > 0:
        sample = collection.peek(3)

        for meta in sample["metadatas"]:
            print(
                " -",
                meta.get("source"),
                "|",
                meta.get("source_type"),
                "|",
                meta.get("status"),
            )

except Exception as e:
    print(f"ERROR: {e}")