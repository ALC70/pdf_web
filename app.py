"""
app.py
======
FastAPI web app — PDF + Image (OCR) to Markdown conversion.

Run locally:
    uvicorn app:app --reload --port 8000

Production:
    uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}
"""

import logging
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from converter import process_batch, is_supported

# -- Logging --
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

# -- App --
app = FastAPI(
    title="PDF & Imagen → Markdown",
    description="Convertí PDFs e imágenes con texto a Markdown. Descargá como ZIP.",
)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

MAX_TOTAL_BYTES = 100 * 1024 * 1024  # 100 MB


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/convert")
async def convert(
    files: list[UploadFile] = File(...),
    page_markers: bool = Form(False),
    unify: bool = Form(False),
    unified_only: bool = Form(False),
    ocr_lang: str = Form("spa+eng"),
):
    """Receive uploaded PDFs/images, convert to Markdown, return ZIP."""
    valid_files: list[tuple[str, bytes]] = []
    rejected: list[str] = []
    total_size = 0

    for f in files:
        fname = f.filename or "unknown"
        if not is_supported(fname):
            rejected.append(fname)
            continue

        content = await f.read()
        total_size += len(content)
        if total_size > MAX_TOTAL_BYTES:
            return JSONResponse(
                status_code=413,
                content={"error": "El total de archivos supera 100 MB."},
            )
        valid_files.append((fname, content))

    if not valid_files:
        msg = "No se recibieron archivos válidos."
        if rejected:
            msg += f" Rechazados: {', '.join(rejected)}"
        return JSONResponse(status_code=400, content={"error": msg})

    # Convert
    batch = process_batch(
        valid_files,
        page_markers=page_markers,
        unify=unify,
        unified_only=unified_only,
        ocr_lang=ocr_lang,
    )

    if not batch.converted:
        errors = [{"file": r.filename, "error": r.error} for r in batch.failed]
        return JSONResponse(
            status_code=422,
            content={"error": "Ningún archivo se pudo convertir.", "details": errors},
        )

    # Build response summary header
    pdf_count = sum(1 for r in batch.converted if r.source_type == "pdf")
    img_count = sum(1 for r in batch.converted if r.source_type == "image")
    zip_name = f"markdown_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"

    return Response(
        content=batch.zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{zip_name}"',
            "X-Converted-PDFs": str(pdf_count),
            "X-Converted-Images": str(img_count),
            "X-Failed": str(len(batch.failed)),
        },
    )


@app.get("/health")
async def health():
    return {"status": "ok"}
