import io
import logging
import os

import docling
from docx import Document as DocxDocument

from docling.datamodel.base_models import DocumentStream
from docling.datamodel.base_models import InputFormat


from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions, TesseractCliOcrOptions
from docling.datamodel.base_models import InputFormat




logger = logging.getLogger("bwiki.parsers")


def get_docling_converter():
   
    pipeline_options = PdfPipelineOptions()
    pipeline_options.ocr_options = TesseractCliOcrOptions()
    
    
    format_options = {
        InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
    }
    
    
    return DocumentConverter(
        allowed_formats=[InputFormat.PDF, InputFormat.IMAGE],
        format_options=format_options
    )

def _parse_docling(file_bytes: bytes, filename: str) -> str:
    try:
        logger.info(f"🔍 Docling OCR startet für: {filename}...")
        converter = get_docling_converter()
        
        source = DocumentStream(name=filename, stream=io.BytesIO(file_bytes))
        
        result = converter.convert(source)
        markdown_text = result.document.export_to_markdown()
        
        if not markdown_text.strip():
            logger.warning(f"⚠️ OCR lieferte keinen Text für {filename}")
            
        return markdown_text
    except Exception as e:
        logger.error(f"❌ Docling OCR Fehler: {e}")
        return ""


def _parse_docx(file_bytes: bytes, filename: str) -> str:
    try:
        doc = DocxDocument(io.BytesIO(file_bytes))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception as e:
        logger.error(f"❌ DOCX Fehler bei {filename}: {e}")
        return ""


def _parse_txt(file_bytes: bytes, filename: str) -> str:
    return file_bytes.decode("utf-8", errors="replace")


def parse_document(filename: str, file_bytes: bytes) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    
   
    if ext in ("pdf", "jpg", "jpeg", "png"):
        return _parse_docling(file_bytes, filename)
    elif ext == "docx":
        return _parse_docx(file_bytes, filename)
    elif ext in ("txt", "md", "csv", "json", "xml", "html"):
        return _parse_txt(file_bytes, filename)
    else:
        logger.warning(f"⚠️ Nicht unterstütztes Format: .{ext} bei {filename}")
        return ""