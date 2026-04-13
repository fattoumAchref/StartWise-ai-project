# backend/agents/document_processor.py — Extraction de texte PDF/TXT légère
import io


def extract_text(file_bytes: bytes, filename: str) -> str:
    """Extract plain text from uploaded PDF or TXT file."""
    fn = filename.lower()
    if fn.endswith('.pdf'):
        return _extract_pdf(file_bytes)
    return _extract_txt(file_bytes)


def _extract_pdf(file_bytes: bytes) -> str:
    # Tentative 1 : pdfplumber (plus fiable)
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        return "\n\n".join(p.strip() for p in pages if p.strip())
    except ImportError:
        pass
    except Exception as e:
        print(f"[DOC PROCESSOR] pdfplumber error: {e}")

    # Tentative 2 : PyPDF2
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(p.strip() for p in pages if p.strip())
    except ImportError:
        pass
    except Exception as e:
        print(f"[DOC PROCESSOR] PyPDF2 error: {e}")

    return "[Erreur : impossible d'extraire le texte PDF. Installez pdfplumber ou PyPDF2.]"


def _extract_txt(file_bytes: bytes) -> str:
    for enc in ('utf-8', 'latin-1', 'cp1252'):
        try:
            return file_bytes.decode(enc).strip()
        except UnicodeDecodeError:
            continue
    return file_bytes.decode('utf-8', errors='replace').strip()
