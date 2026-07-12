# FROM python:3.11-slim

# WORKDIR /app

# COPY requirements.txt .
# RUN pip install --no-cache-dir -r requirements.txt

# COPY . .

# CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "10000"]

FROM python:3.11-slim

# System dependencies:
# - build-essential: C compiler/linker, needed if any pip package builds from source
# - tesseract-ocr + libtesseract-dev: needed by unstructured.pytesseract
# - poppler-utils: needed by pdf2image
# - libmagic1: needed by python-magic
# - libgl1 + libglib2.0-0: common runtime libs needed by pillow/opencv-related deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    tesseract-ocr \
    libtesseract-dev \
    poppler-utils \
    libmagic1 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Playwright needs its browser binaries downloaded separately
RUN playwright install --with-deps chromium

COPY . .

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "10000"]