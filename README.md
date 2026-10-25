# PDF & Imagen → Markdown (Web App)

Convertí PDFs e imágenes con texto a Markdown desde el navegador.  
Subís archivos, los convierte y descargás un ZIP con los `.md` resultantes.

## Features

- **PDF → Markdown** vía pymupdf4llm (tablas, headers, listas)
- **Imagen → Markdown** vía Tesseract OCR (JPG, PNG, WEBP, TIFF, BMP)
- Marcadores de página opcionales para PDFs
- Unificación de todos los archivos en un solo `.md`
- Idiomas OCR configurables (default: español + inglés)
- Procesamiento 100% in-memory (sin archivos temporales)
- Dark mode UI

## Formatos soportados

| Tipo   | Extensiones                          |
|--------|--------------------------------------|
| PDF    | `.pdf`                               |
| Imagen | `.jpg` `.jpeg` `.png` `.webp` `.tiff` `.tif` `.bmp` |

## Uso local

```bash
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

Abrí `http://localhost:8000` en el navegador.

> **Nota:** Necesitás Tesseract instalado en el sistema para OCR:
> ```bash
> # Ubuntu/Debian
> sudo apt install tesseract-ocr tesseract-ocr-spa tesseract-ocr-eng
>
> # macOS
> brew install tesseract tesseract-lang
> ```

## Deploy con Docker

```bash
docker build -t pdf2md-web .
docker run -p 8000:8000 pdf2md-web
```

### Railway / Render

1. Pusheá el repo a GitHub
2. Conectá el repo en Railway o Render
3. El `Dockerfile` se detecta automáticamente
4. Variable de entorno: `PORT` (se inyecta sola en ambas plataformas)

## API

### `POST /convert`

**Form fields:**

| Campo        | Tipo     | Default     | Descripción                          |
|--------------|----------|-------------|--------------------------------------|
| `files`      | File[]   | (requerido) | PDFs y/o imágenes                    |
| `page_markers` | bool   | `false`     | Insertar marcadores de página (PDF)  |
| `unify`      | bool     | `false`     | Generar `unificado.md` adicional     |
| `unified_only` | bool   | `false`     | Solo el archivo unificado            |
| `ocr_lang`   | string   | `spa+eng`   | Idiomas Tesseract para OCR           |

**Response:** ZIP con archivos `.md`

### `GET /health`

Health check → `{"status": "ok"}`

## Stack

- **FastAPI** + Uvicorn
- **pymupdf4llm** / **pymupdf** — PDF conversion
- **pytesseract** / **Pillow** — Image OCR
- **Docker** — Tesseract + Python runtime
