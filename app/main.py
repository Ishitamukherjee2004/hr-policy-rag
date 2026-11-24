import os
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from datetime import datetime, timezone

from app.schemas import AskRequest, AskResponse, FeedbackRequest
from app.chunker import chunk_markdown, extract_text_from_pdf
from app.rag_engine import index_chunks, answer_question, get_indexed_documents

load_dotenv()
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "hr-admin-2026")

FEEDBACK_FILE = "feedback_log.jsonl"

def verify_admin_token(x_admin_token: str = Header(default="")):
    if not x_admin_token or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Invalid or missing X-Admin-Token.",
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-index sample policies in ./policies on startup if DB is empty
    if not get_indexed_documents() and os.path.isdir("policies"):
        for fname in sorted(os.listdir("policies")):
            if fname.endswith((".md", ".txt")):
                fpath = os.path.join("policies", fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    chunks = chunk_markdown(f.read(), fname)
                    index_chunks(chunks)
    yield


app = FastAPI(
    title="Internal HR FAQ & Policy Assistant",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok", "indexed_documents": get_indexed_documents()}


@app.get("/documents")
def list_documents():
    return {"documents": get_indexed_documents()}


@app.post("/upload", dependencies=[Depends(verify_admin_token)])
async def upload_policy(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in {".md", ".txt", ".pdf"}:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Please upload .md, .txt, or .pdf files.",
        )

    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        if ext == ".pdf":
            text = extract_text_from_pdf(raw_bytes)
        else:
            text = raw_bytes.decode("utf-8")
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Could not read file '{file.filename}': {str(exc)}",
        )

    if not text.strip():
        raise HTTPException(status_code=400, detail="File contains no readable text.")

    chunks = chunk_markdown(text, file.filename)
    if not chunks:
        raise HTTPException(status_code=400, detail="No valid sections could be extracted.")

    num_indexed = index_chunks(chunks)
    return {
        "message": f"Successfully indexed '{chunks[0]['document']}'",
        "document": chunks[0]["document"],
        "chunks_indexed": num_indexed,
    }


@app.post("/ask", response_model=AskResponse)
def ask_hr(payload: AskRequest):
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    try:
        return answer_question(question)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error generating answer: {str(exc)}")


@app.post("/feedback")
def submit_feedback(payload: FeedbackRequest):
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "question": payload.question,
        "answer": payload.answer,
        "rating": payload.rating,
        "citations": [c.model_dump() for c in payload.citations],
        "comment": payload.comment,
    }
    with open(FEEDBACK_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {"status": "saved", "rating": payload.rating}


@app.get("/feedback", dependencies=[Depends(verify_admin_token)])
def get_feedback():
    if not os.path.exists(FEEDBACK_FILE):
        return {"feedback": []}
    with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
        entries = [json.loads(line) for line in f if line.strip()]
    return {"feedback": entries}