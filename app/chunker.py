import re
from typing import List, Dict
from pypdf import PdfReader
import io


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extracts plain text from uploaded PDF bytes."""
    reader = PdfReader(io.BytesIO(file_bytes))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append(f"## Page {i}\n{text}")
    return "\n\n".join(pages)


def chunk_markdown(content: str, fallback_filename: str) -> List[Dict[str, str]]:
    """
    Splits Markdown/text content by headings (#, ##, ###) while keeping
    tables and paragraphs under their parent section intact.
    """
    lines = content.splitlines()
    doc_title = fallback_filename
    current_h2 = "General"
    current_h3 = ""
    buffer: List[str] = []
    chunks: List[Dict[str, str]] = []

    def flush_buffer():
        body = "\n".join(buffer).strip()
        if not body:
            return
        section_label = f"{current_h2} > {current_h3}" if current_h3 else current_h2
        # Prepend document & section context so embeddings capture structural meaning
        enriched_text = f"Document: {doc_title}\nSection: {section_label}\n\n{body}"
        chunks.append({
            "text": enriched_text,
            "document": doc_title,
            "section": section_label,
        })

    for line in lines:
        stripped = line.strip()

        # Match H1 (# Title)
        if re.match(r"^#\s+(?!#)", stripped):
            flush_buffer()
            buffer = []
            doc_title = stripped.lstrip("#").strip()
            current_h2 = "Overview"
            current_h3 = ""

        # Match H2 (## Section)
        elif re.match(r"^##\s+(?!#)", stripped):
            flush_buffer()
            buffer = []
            current_h2 = stripped.lstrip("#").strip()
            current_h3 = ""

        # Match H3 (### Subsection)
        elif re.match(r"^###\s+(?!#)", stripped):
            flush_buffer()
            buffer = []
            current_h3 = stripped.lstrip("#").strip()

        else:
            buffer.append(line)

    flush_buffer()
    return chunks