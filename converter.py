"""
converter.py
============
PDF and image to Markdown conversion logic.
- PDFs: pymupdf4llm (in-memory via pymupdf stream)
- Images: pytesseract OCR (Tesseract)
All processing is in-memory — no temp files on disk.
"""

import io
import zipfile
import logging
from datetime import datetime
from dataclasses import dataclass, field

import pymupdf
import pymupdf4llm
import pytesseract
from PIL import Image

log = logging.getLogger("pdf2md.converter")

# -- Supported file extensions --
PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tiff", ".tif", ".bmp"}
ALL_EXTENSIONS = PDF_EXTENSIONS | IMAGE_EXTENSIONS


def is_supported(filename: str) -> bool:
    """Check if a filename has a supported extension."""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in ALL_EXTENSIONS


def is_pdf(filename: str) -> bool:
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in PDF_EXTENSIONS


def is_image(filename: str) -> bool:
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in IMAGE_EXTENSIONS


@dataclass
class ConversionResult:
    """Holds the result of converting one file."""
    filename: str
    markdown: str
    source_type: str  # "pdf" or "image"
    success: bool
    error: str | None = None


@dataclass
class BatchResult:
    """Holds the result of converting a batch of files."""
    results: list[ConversionResult] = field(default_factory=list)
    zip_bytes: bytes = b""

    @property
    def converted(self) -> list[ConversionResult]:
        return [r for r in self.results if r.success]

    @property
    def failed(self) -> list[ConversionResult]:
        return [r for r in self.results if not r.success]


# ----------------------------------------------------------------
# PDF conversion (pymupdf4llm, in-memory)
# ----------------------------------------------------------------
def convert_pdf_bytes(
    pdf_bytes: bytes,
    filename: str,
    page_markers: bool = False,
) -> ConversionResult:
    """Convert raw PDF bytes to Markdown using pymupdf4llm."""
    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")

        if page_markers:
            pages = pymupdf4llm.to_markdown(doc, page_chunks=True)
            parts = []
            for i, page in enumerate(pages, start=1):
                parts.append(f"\n\n<!-- --- página {i} --- -->\n\n")
                parts.append(page.get("text", ""))
            md_text = "".join(parts).strip() + "\n"
        else:
            md_text = pymupdf4llm.to_markdown(doc).strip() + "\n"

        doc.close()

        header = (
            f"<!-- Generado desde '{filename}' "
            f"el {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} -->\n\n"
        )
        return ConversionResult(
            filename=filename,
            markdown=header + md_text,
            source_type="pdf",
            success=True,
        )

    except Exception as exc:
        log.error(f"Error converting PDF '{filename}': {exc}")
        return ConversionResult(
            filename=filename, markdown="",
            source_type="pdf", success=False, error=str(exc),
        )


# ----------------------------------------------------------------
# Image OCR conversion (pytesseract)
# ----------------------------------------------------------------
def convert_image_bytes(
    img_bytes: bytes,
    filename: str,
    ocr_lang: str = "spa+eng",
) -> ConversionResult:
    """
    Extract text from an image via Tesseract OCR and format as Markdown.
    Default languages: Spanish + English. Adjust with ocr_lang param.
    """
    try:
        image = Image.open(io.BytesIO(img_bytes))

        # Convert to RGB if needed (RGBA/palette modes break tesseract)
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")

        # Run OCR — returns plain text
        raw_text = pytesseract.image_to_string(image, lang=ocr_lang)

        if not raw_text.strip():
            return ConversionResult(
                filename=filename, markdown="",
                source_type="image", success=False,
                error="No se detectó texto en la imagen.",
            )

        # Format as markdown: keep paragraph structure, clean up
        lines = raw_text.strip().split("\n")
        cleaned = []
        for line in lines:
            stripped = line.strip()
            if stripped:
                cleaned.append(stripped)
            elif cleaned and cleaned[-1] != "":
                cleaned.append("")  # preserve paragraph breaks

        md_text = "\n".join(cleaned).strip() + "\n"

        header = (
            f"<!-- OCR desde '{filename}' "
            f"el {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} "
            f"(lang: {ocr_lang}) -->\n\n"
        )
        return ConversionResult(
            filename=filename,
            markdown=header + md_text,
            source_type="image",
            success=True,
        )

    except Exception as exc:
        log.error(f"Error OCR on '{filename}': {exc}")
        return ConversionResult(
            filename=filename, markdown="",
            source_type="image", success=False, error=str(exc),
        )


# ----------------------------------------------------------------
# Unified markdown + ZIP packaging
# ----------------------------------------------------------------
def build_unified_markdown(results: list[ConversionResult]) -> str:
    """Concatenate all successful conversions into a single Markdown doc."""
    parts = [
        f"<!-- Documento unificado generado el "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} -->\n\n"
    ]
    for idx, r in enumerate(sorted(results, key=lambda x: x.filename), start=1):
        md_name = r.filename.rsplit(".", 1)[0] + ".md"
        tag = "OCR" if r.source_type == "image" else "PDF"
        parts.append(f"\n\n---\n\n## {idx}. {md_name} [{tag}]\n\n---\n\n")
        parts.append(r.markdown)
        parts.append("\n")
    return "".join(parts)


def build_zip(
    results: list[ConversionResult],
    unify: bool = False,
    unified_only: bool = False,
) -> bytes:
    """Package conversion results into a ZIP returned as bytes."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if not unified_only:
            for r in results:
                md_name = r.filename.rsplit(".", 1)[0] + ".md"
                zf.writestr(md_name, r.markdown)

        if unify:
            unified_md = build_unified_markdown(results)
            zf.writestr("unificado.md", unified_md)

    return buf.getvalue()


def process_batch(
    files: list[tuple[str, bytes]],
    page_markers: bool = False,
    unify: bool = False,
    unified_only: bool = False,
    ocr_lang: str = "spa+eng",
) -> BatchResult:
    """
    Main entry: receives list of (filename, file_bytes),
    routes each to PDF or image converter, builds ZIP.
    """
    batch = BatchResult()

    for filename, file_bytes in files:
        if is_pdf(filename):
            log.info(f"[PDF] Converting: {filename}")
            result = convert_pdf_bytes(file_bytes, filename, page_markers)
        elif is_image(filename):
            log.info(f"[IMG] OCR: {filename}")
            result = convert_image_bytes(file_bytes, filename, ocr_lang)
        else:
            log.warning(f"Unsupported file type: {filename}")
            result = ConversionResult(
                filename=filename, markdown="",
                source_type="unknown", success=False,
                error=f"Tipo de archivo no soportado: {filename}",
            )
        batch.results.append(result)

    if batch.converted:
        batch.zip_bytes = build_zip(
            batch.converted,
            unify=unify,
            unified_only=unified_only,
        )

    return batch
