import base64
import io
import logging

from PIL import Image

from docx import Document as DocxDocument
from pypdf import PdfReader
from pypdf.errors import PdfReadError, PdfStreamError

# LangChain Imports für das Vision-Modell
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage

# Importiere deine Config-Variable
from config import OLLAMA_BASE_URL

logger = logging.getLogger("bwiki.parsers")


vision_llm = ChatOllama(
    model="llava-phi3", 
    base_url=OLLAMA_BASE_URL,
    temperature=0.0 
)

def resize_image(image_bytes: bytes, max_size: int = 800) -> bytes:
    """Verkleinert das Bild, um den VRAM der Grafikkarte zu schonen."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        # Konvertiere zu RGB (falls es z.B. ein transparentes PNG ist)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Verkleinere das Bild proportional, sodass die längste Seite max_size ist
        img.thumbnail((max_size, max_size))
        
        # Speichere es als komprimiertes JPEG zurück in den Arbeitsspeicher
        output = io.BytesIO()
        img.save(output, format="JPEG", quality=85)
        return output.getvalue()
    except Exception as e:
        logger.warning(f"Bild konnte nicht verkleinert werden, nutze Original: {e}")
        return image_bytes

def describe_image(image_bytes: bytes) -> str:
    """Schickt ein Bild an das lokale Vision-Modell und gibt die Beschreibung zurück."""
    try:

        optimized_image_bytes = resize_image(image_bytes, max_size=800)
        # Bilder müssen für die API in Base64 umgewandelt werden
        image_b64 = base64.b64encode(optimized_image_bytes).decode("utf-8")
        
        # Die Anweisung an das Modell
        message = HumanMessage(
            content=[
                {
                    "type": "text", 
                    "text": "Beschreiben Sie dieses Bild, diesen UI-Screenshot oder dieses Diagramm detailliert."
                    "Erwähnen Sie alle sichtbaren Texte, Schaltflächen, Zahlen und Layout-Elemente.. "
                    "Geben Sie eine genaue Beschreibung, damit jemand, der das Bild nicht sehen kann, es sich vorstellen kann."
                    "Nennen Sie am Ende die wichtigsten Informationen kurz zusammengefasst."
                    "Antworten Sie auf Deutsch.Erwähnte englische Wörter im Bild dürfen übernommen werden, aber die Beschreibung selbst muss Deutsch sein."
                            
                },
                {
                    "type": "image_url", 
                    "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}
                }
            ]
        )
        
        # Modell fragen
        logger.info("Sende Bild an Ollama...")
        response = vision_llm.invoke([message])
        description = response.content.strip()
        
        
        
            
        return description

    except Exception as e:
        logger.error(f"Fehler bei der Bildanalyse: {e}")
        return ""


def _parse_pdf(file_bytes: bytes, filename: str) -> str:
    """Liest Text und Bilder aus einer PDF aus und verschmilzt sie zu reinem Text."""
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        text = ""
        
        for i, page in enumerate(reader.pages):
            page_number = i + 1
            
            # 1. Normalen Text extrahieren
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
                
            # 2. Bilder auf dieser Seite suchen und analysieren
            for image_file_object in page.images:
                logger.info(f"🖼️ Bild gefunden auf Seite {page_number} in Dokument {filename}, starte KI-Analyse...")
                
                image_bytes = image_file_object.data
                description = describe_image(image_bytes)
                
                if description:
                    # Füge die Beschreibung unsichtbar für den Nutzer in den Text ein
                    text += f"\n\n[KI-Bildbeschreibung (Seite {page_number}): {description}]\n\n"
                    logger.info(f"✅ Bild auf Seite {page_number} erfolgreich beschrieben.")
                    
        return text
        
    except (PdfReadError, PdfStreamError, Exception) as e:
        # Fängt kaputte Header, unerwartete Dateiendungen und Lesefehler ab
        logger.error(f"❌ PDF konnte nicht gelesen werden (kaputt oder falsches Format). Fehler: {e}")
        return ""  # Gibt leeren Text zurück


def _parse_docx(file_bytes: bytes, filename: str) -> str:
    doc = DocxDocument(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _parse_txt(file_bytes: bytes, filename: str) -> str:
    return file_bytes.decode("utf-8", errors="replace")


def parse_document(filename: str, file_bytes: bytes) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == "pdf":
        return _parse_pdf(file_bytes, filename)
    elif ext == "docx":
        return _parse_docx(file_bytes, filename)
    elif ext in ("txt", "md", "csv", "json", "xml", "html"):
        return _parse_txt(file_bytes, filename)
    else:
        raise ValueError(f"Nicht unterstütztes Dateiformat: .{ext}")