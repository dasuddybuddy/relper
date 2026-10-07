FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pipeline/ingest/pdf_downloads.py .
COPY pipeline/models models 
COPY .env .

CMD ["python", "pdf_downloads.py"]
