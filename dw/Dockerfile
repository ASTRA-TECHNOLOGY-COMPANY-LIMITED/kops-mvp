# KOPS data warehouse: build + checks + dashboard server (D-07). Apple Silicon (arm64) and Linux x86_64.
# The image holds code only: KLMAS files are mounted read-only at run time (docker-compose.yml), the build output
# lives in a volume, secrets come from .env at run time. Nothing from raw-docs / build / .env is copied in
# (.dockerignore).
FROM python:3.13-slim-bookworm

# LibreOffice Calc: .xlsb -> .xlsx with cell fills; tesseract (kor, vie, eng) + poppler: OCR queue and PDF text;
# pst-utils (readpst): Outlook .pst mailboxes.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      libreoffice-calc-nogui \
      tesseract-ocr tesseract-ocr-kor tesseract-ocr-vie tesseract-ocr-eng \
      poppler-utils pst-utils \
      fonts-noto-cjk tzdata \
 && rm -rf /var/lib/apt/lists/*

# 'today' for data freshness is the date in Vietnam, where the factories report
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TZ=Asia/Ho_Chi_Minh \
    KOPS_RAW_DOCS=/data/raw-docs \
    KOPS_INBOX=/data/raw-docs/inbox:/app/samples/inbox \
    KOPS_BUILD=/app/build \
    KOPS_SOFFICE=/usr/bin/soffice \
    HOME=/app/build/home

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY kops_dw ./kops_dw
COPY sql ./sql
COPY templates ./templates
COPY samples ./samples
COPY README.md mail_allow.example.txt ./

RUN useradd --create-home --uid 1000 kops && mkdir -p /app/build && chown kops:kops /app/build \
 && chmod -R a+rX /app
USER kops

EXPOSE 8765
CMD ["python", "-m", "kops_dw", "serve", "--host", "0.0.0.0", "--port", "8765"]
