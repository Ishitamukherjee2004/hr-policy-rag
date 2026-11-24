import os
import time
from typing import List, Dict
import chromadb
from google import genai
from google.genai import types
from dotenv import load_dotenv

from app.schemas import AskResponse, Citation

load_dotenv()

# Initialize Gemini client (used for both embeddings and grounded generation)
api_key = os.getenv("GEMINI_API_KEY")
gemini_client = genai.Client(api_key=api_key) if api_key else None

EMBED_MODEL_NAME = "gemini-embedding-001"
LLM_MODELS = ["gemini-3.8-flash", "gemini-3.5-flash-lite"]

# Initialize persistent ChromaDB vector store
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection(
    name="hr_policies",
    metadata={"hnsw:space": "cosine"},
)

# Cosine distance threshold (0 = exact match, 1 = orthogonal, 2 = opposite)
MAX_COSINE_DISTANCE = 0.68

REFUSAL_MESSAGE = (
    "I don't have enough information in the uploaded policies to answer that; "
    "please contact HR."
)


def get_embeddings(texts: List[str]) -> List[List[float]]:
    """Generates normalized vector embeddings via Gemini Embedding API (lightweight, <120MB RAM)."""
    if not gemini_client:
        raise RuntimeError("GEMINI_API_KEY is missing in environment variables.")
    res = gemini_client.models.embed_content(
        model=EMBED_MODEL_NAME,
        contents=texts,
    )
    return [e.values for e in res.embeddings]


def index_chunks(chunks: List[Dict[str, str]]) -> int:
    """Embeds and upserts chunks into ChromaDB, replacing any previous version of the same document."""
    if not chunks:
        return 0

    doc_name = chunks[0]["document"]

    # Remove existing chunks for this document to prevent duplicates on re-upload
    existing = collection.get(where={"document": doc_name})
    if existing and existing["ids"]:
        collection.delete(ids=existing["ids"])

    texts = [c["text"] for c in chunks]
    embeddings = get_embeddings(texts)
    ids = [f"{doc_name}::chunk_{i}" for i in range(len(chunks))]
    metadatas = [{"document": c["document"], "section": c["section"]} for c in chunks]

    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=texts,
        metadatas=metadatas,
    )
    return len(chunks)


def get_indexed_documents() -> List[str]:
    """Returns a sorted list of unique policy document titles currently in the database."""
    data = collection.get(include=["metadatas"])
    if not data or not data["metadatas"]:
        return []
    docs = {m["document"] for m in data["metadatas"] if "document" in m}
    return sorted(docs)


def answer_question(question: str, top_k: int = 4) -> AskResponse:
    """Retrieves relevant policy chunks and generates a strictly grounded, cited JSON answer."""
    if collection.count() == 0:
        return AskResponse(
            answer="No policy documents have been uploaded yet. Please upload HR policies first.",
            citations=[],
            grounded=False,
        )

    # 1. Embed query and search vector store
    query_embedding = get_embeddings([question])
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    docs = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    # 2. Gate 1: Refuse immediately if even the best chunk is semantically too far
    if not docs or distances[0] > MAX_COSINE_DISTANCE:
        return AskResponse(answer=REFUSAL_MESSAGE, citations=[], grounded=False)

    # Keep only chunks within a reasonable distance window
    relevant_excerpts = []
    for doc_text, meta, dist in zip(docs, metadatas, distances):
        if dist <= MAX_COSINE_DISTANCE + 0.08:
            relevant_excerpts.append(
                f"--- SOURCE: {meta['document']} | SECTION: {meta['section']} ---\n{doc_text}"
            )

    context_block = "\n\n".join(relevant_excerpts)

    # 3. Gate 2: Call Gemini with strict grounding instructions & Pydantic JSON schema
    if not gemini_client:
        raise RuntimeError("GEMINI_API_KEY is missing in environment variables.")

    system_instruction = (
        "You are an internal HR Policy Assistant. Answer the employee's question using ONLY "
        "the provided policy excerpts.\n"
        "STRICT RULES:\n"
        "1. Do NOT use outside knowledge, assumptions, or general HR practices.\n"
        "2. Read Markdown tables carefully—match the exact row and column requested.\n"
        "3. If a policy explicitly prohibits or excludes something (e.g. 'not reimbursable'), "
        "state that clearly and cite the section.\n"
        "4. If the provided excerpts do not contain enough information to answer the question, "
        f"set grounded=false, citations=[], and answer='{REFUSAL_MESSAGE}'.\n"
        "5. Every claim in your answer must include the exact document name and section in citations."
    )

    user_prompt = f"POLICY EXCERPTS:\n{context_block}\n\nEMPLOYEE QUESTION: {question}"

    response = None
    last_error = None

    for model_name in LLM_MODELS:
        for attempt in range(2):
            try:
                response = gemini_client.models.generate_content(
                    model=model_name,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        response_mime_type="application/json",
                        response_schema=AskResponse,
                        temperature=0.0,
                    ),
                )
                break
            except Exception as exc:
                last_error = exc
                err_str = str(exc)
                if "503" in err_str or "429" in err_str or "404" in err_str:
                    time.sleep(1.5)
                    continue
                raise
        if response is not None:
            break

    if response is None:
        raise RuntimeError(f"All Gemini fallback models unavailable: {last_error}")

    parsed: AskResponse = response.parsed

    # 4. Gate 3: Enforce consistency—if grounded is False, clear any stray citations
    if not parsed.grounded:
        return AskResponse(answer=REFUSAL_MESSAGE, citations=[], grounded=False)

    # Deduplicate citations while preserving order
    seen = set()
    unique_citations = []
    for c in parsed.citations:
        key = (c.document.strip(), c.section.strip())
        if key not in seen:
            seen.add(key)
            unique_citations.append(Citation(document=c.document.strip(), section=c.section.strip()))

    return AskResponse(
        answer=parsed.answer.strip(),
        citations=unique_citations,
        grounded=True,
    )