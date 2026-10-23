# KOPS images (D-07, F-06). Apple Silicon (arm64) and Linux x86_64. Two targets from one file:
#   app    (kops-app:local)    DW build + checks + web app; no browser
#   tools  (kops-tools:local)  app + Chromium + Playwright: make check-ui, make report (server-side PDF)
# The images hold code only: KLMAS files are mounted read-only at run time (docker-compose.yml), the build output and
# the app state live in volumes, secrets come from .env at run time. Nothing from raw-docs / build / state / .env is
# copied in (.dockerignore).
FROM python:3.13-slim-bookworm AS app

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
    KOPS_STATE=/app/state \
    KOPS_SOFFICE=/usr/bin/soffice \
    HOME=/app/build/home

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY kops_dw ./kops_dw
COPY app ./app
COPY sql ./sql
COPY templates ./templates
COPY samples ./samples
COPY eval ./eval
COPY README.md mail_allow.example.txt ./

RUN useradd --create-home --uid 1000 kops && mkdir -p /app/build /app/state && chown kops:kops /app/build /app/state \
 && chmod -R a+rX /app
USER kops

EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8765/healthz', timeout=4).status == 200 else 1)"
CMD ["python", "-m", "kops_dw", "serve", "--host", "0.0.0.0", "--port", "8765"]

# ------------------------------------------------------------------ tools: UI tests and PDF reports
FROM app AS tools
USER root
RUN apt-get update && apt-get install -y --no-install-recommends chromium && rm -rf /var/lib/apt/lists/*
COPY requirements-tools.txt .
RUN pip install --no-cache-dir -r requirements-tools.txt
ENV KOPS_CHROME=/usr/bin/chromium
USER kops
HEALTHCHECK NONE
CMD ["python", "-m", "kops_dw", "check-ui", "--out", "/out"]
