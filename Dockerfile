FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pdf_downloads.py .

CMD ["python", "pdf_downloads.py"]
