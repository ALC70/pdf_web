FROM python:3.12-slim

# Install Tesseract OCR + language packs
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-spa \
        tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Railway / Render inject PORT; default 8000
ENV PORT=8000
EXPOSE ${PORT}

CMD uvicorn app:app --host 0.0.0.0 --port ${PORT}
