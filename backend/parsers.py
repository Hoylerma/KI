import io

from docx import Document as DocxDocument
from pypdf import PdfReader


def _parse_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    return text


def _parse_docx(file_bytes: bytes) -> str:
    doc = DocxDocument(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _parse_txt(file_bytes: bytes) -> str:
    return file_bytes.decode("utf-8", errors="replace")


def parse_document(filename: str, file_bytes: bytes) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == "pdf":
        return _parse_pdf(file_bytes)
    elif ext == "docx":
        return _parse_docx(file_bytes)
    elif ext in ("txt", "md", "csv", "json", "xml", "html"):
        return _parse_txt(file_bytes)
    else:
        raise ValueError(f"Nicht unterstütztes Dateiformat: .{ext}")
