# System Design: Internal HR FAQ & Policy Assistant

**Author:** Ishita Mukherjee | Kalyani Government Engineering College (KGEC)

---

## 1. Architecture & Data Flow

The system separates document ingestion, semantic vector indexing, and grounded LLM generation behind a stateless **FastAPI** service, backed by a persistent local **ChromaDB** vector store and a **Streamlit** web client.

```text
[INGESTION PIPELINE]
Admin Upload (.md / .txt / .pdf) + X-Admin-Token Header
       │
       ▼
Auth & File Validation (app/main.py, pypdf)
  • Verifies X-Admin-Token against ADMIN_TOKEN
  • Rejects unsupported types, empty files, or unreadable text (HTTP 400)
       │
       ▼
Heading-Aware Chunker (app/chunker.py)
  • Splits strictly on Markdown #, ##, ### boundaries
  • Keeps Markdown pipe tables intact inside their parent section
  • Prepends [Document | Section] context to each chunk
       │
       ▼
Local Embedding Model (all-MiniLM-L6-v2, 384-dim normalized)
       │
       ▼
ChromaDB Persistent Store (./chroma_db)
  • Idempotent upsert: deletes prior chunks for same document before inserting

[QUERY PIPELINE]
Employee Question ──► Input Validation (Pydantic min_length=1 + non-empty check)
                           │
                           ▼
                    Query Embedding (all-MiniLM-L6-v2)
                           │
                           ▼
                    Top-K Cosine Search (k=4 in ChromaDB)
                           │
                           ▼
              Gate 1: Cosine Distance Threshold (<= 0.68)
                 ├── Fail ──► Immediate Refusal JSON (0 LLM calls)
                 └── Pass
                      │
                      ▼
              Gate 2: Gemini 3.5 Flash-Lite (Temp=0.0 + Strict Grounding Prompt)
                      │  (Automatic retry & fallback to gemini-3.8-flash on 503/429)
                      ▼
              Gate 3: Pydantic Schema Enforcement (AskResponse JSON)
                      │
                      ▼
              Structured Response {answer, citations[], grounded}