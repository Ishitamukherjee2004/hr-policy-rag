# Internal HR FAQ & Policy Assistant

**Author:** Ishita Mukherjee | Kalyani Government Engineering College (KGEC) 

A Retrieval-Augmented Generation (RAG) service that allows HR administrators to upload policy documents (`.md`, `.txt`, `.pdf`) and lets employees ask natural language questions with strictly grounded answers, exact section citations, and reliable out-of-policy refusals.

---

## Tech Stack & Models
* **Backend API:** Python, FastAPI, Pydantic (strict JSON response schemas)
* **Local Embeddings (Free / Offline):** `sentence-transformers` (`all-MiniLM-L6-v2` — 384-dim normalized vectors running locally on CPU)
* **Vector Database:** ChromaDB (persistent local cosine similarity index in `./chroma_db`)
* **LLM (Free Tier):** Google AI Studio (`gemini-3.5-flash-lite` primary, with automatic retry & fallback to `gemini-3.8-flash`) using `response_schema` structured JSON output
* **Frontend UI:** Streamlit (with Employee Q&A view and Token-Protected Admin Policy Management view)

---

## Quick Start (Runs in < 5 Minutes)

### 1. Clone the Repository & Create Virtual Environment
```bash
git clone https://github.com/ishita-mukherjee/hr-policy-rag.git
cd hr-policy-rag
python -m venv venv

# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate