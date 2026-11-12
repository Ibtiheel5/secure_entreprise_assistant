"""Validation de fichier + extraction de texte (PDF, DOCX, TXT) + nettoyage."""
import io
import re
import unicodedata

from app.config import get_settings

ALLOWED = {"pdf", "docx", "txt"}


class InvalidFile(ValueError):
    pass


def file_extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def validate_file(filename: str, data: bytes) -> str:
    """Contrôle extension, taille ET contenu réel (magic bytes) : l'extension seule ne suffit pas."""
    ext = file_extension(filename)
    if ext not in ALLOWED:
        raise InvalidFile(f"Unsupported file type (allowed: {', '.join(sorted(ALLOWED))})")
    if not data:
        raise InvalidFile("Empty file")
    if len(data) > get_settings().max_upload_mb * 1024 * 1024:
        raise InvalidFile("File too large")
    if ext == "pdf" and not data.startswith(b"%PDF"):
        raise InvalidFile("File content is not a PDF")
    if ext == "docx" and not data.startswith(b"PK"):
        raise InvalidFile("File content is not a DOCX")
    if ext == "txt" and b"\x00" in data[:4096]:
        raise InvalidFile("File content is not text")
    return ext


def clean_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(c for c in text if c == "\n" or c == "\t" or unicodedata.category(c)[0] != "C")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_text(filename: str, data: bytes) -> str:
    ext = validate_file(filename, data)
    try:
        if ext == "txt":
            raw = data.decode("utf-8", errors="replace")
        elif ext == "pdf":
            from pypdf import PdfReader
            raw = "\n\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages)
        else:
            from docx import Document as Docx
            raw = "\n\n".join(p.text for p in Docx(io.BytesIO(data)).paragraphs)
    except Exception as exc:  # fichier corrompu : erreur claire, pas de trace interne
        raise InvalidFile(f"Could not read {ext.upper()} file") from exc
    text = clean_text(raw)
    if not text:
        raise InvalidFile("No extractable text (scanned PDF? OCR is not supported)")
    return text
