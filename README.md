# ParcelPilot AI Agent  

Customer-facing support agent addressing **Trust & Reliability**: it reasons
across policies, SOPs, product docs, customer agreements, and structured
account/order/ticket data — resolving conflicts by an explicit authority
model instead of trusting whichever chunk scores highest in retrieval.

## Setup
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your GROQ_API_KEY
```

## 1. Load the supplied data pack
```bash
# Structured Excel data -> SQLite
python -m ingestion.ingest_excel --xlsx data/raw/operational_data.xlsx

# PDFs (policies, SOPs, product docs, agreements) -> Chroma
python -m ingestion.ingest_documents --docs data/raw/documents/
```
> Check the actual sheet/column and file names in the supplied data pack
> first — `SHEET_TABLE_MAP` in `ingestion/ingest_excel.py` and
> `CLASSIFY_RULES` in `ingestion/ingest_documents.py` are placeholders
> based on the assessment description and will likely need small tweaks.

## 2. Run
```bash
streamlit run app/streamlit_app.py
```

## 3. Test
```bash
pytest
```

## Project layout
See `docs/architecture.md` for the full design; short version:

```
app/            Streamlit UI
agent/          Tool-calling loop, prompts, session state
tools/          The 3 tools: document_search, data_lookup, escalation
ingestion/      Loads the supplied PDFs + Excel into Chroma / SQLite
retrieval/      Vector store wrapper + source authority engine
data/raw/       Put the supplied assessment data pack here
data/processed/ Generated Chroma DB + SQLite DB (gitignored)
tests/          pytest suite: access control, conflicts, confirmation
docs/           architecture.md, product_note.md, demo_script.md
```

## Docs
- [Architecture](docs/architecture.md)
- [Product note](docs/product_note.md)
- [Demo script](docs/demo_script.md)
- AI tool usage: built with Groq as pair-programmer for scaffolding and iteration.

