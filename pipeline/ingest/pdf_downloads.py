import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import psycopg2
import psycopg2.extras
import os
import shutil
from dotenv import load_dotenv
from models.paper_record import PaperRecord
from typing import Optional
import socket
import threading
import time


def download_pdf(content_url : str, filename : str) -> None:
    response = requests.get(content_url, timeout=60)
    response.raise_for_status()

    with open(filename, "wb") as f:
        f.write(response.content)

def claim_paper(conn, worker_id) -> Optional[PaperRecord]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            UPDATE pdf_downloader.papers
            SET status = 'in_progress',
                claimed_by = %s,
                claimed_at = now(),
                attempts = attempts + 1
            WHERE id = (
                SELECT id FROM pdf_downloader.papers
                WHERE status = 'pending' AND attempts < max_attempts
                ORDER BY id
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING *;
        """, (worker_id,))
        current_row = cur.fetchone()
        conn.commit()
    return PaperRecord.from_row(current_row) if current_row else None

def mark_done(conn, item_id) -> None:
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE pdf_downloader.papers
            SET status = 'done',
                updated_at = now()
            WHERE id = %s;
            """, (item_id,))
        conn.commit()

def mark_failed(conn, item_id, error) -> None:
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE pdf_downloader.papers
            SET status = 'failed',
                error = %s,
                updated_at = now()
            WHERE id = %s;
            """, (error, item_id))
        conn.commit()

def worker_loop(conn, worker_id: str):
    paper = claim_paper(conn, worker_id)
    if paper is None:
        return False  # nothing left

    os.makedirs("/mnt/downloaded_pdfs", exist_ok=True)
    try:
        download_pdf(paper.content_url, f"/mnt/downloaded_pdfs/{paper.item_id}.pdf")
        mark_done(conn, paper.id)
    except Exception as e:
        mark_failed(conn, paper.id, error=str(e))
    return True

if __name__ == "__main__":
    print("start")
    load_dotenv()
    DATABASE_URL = os.environ["DATABASE_URL"]
    
    def run_one():
        # psycopg2 connections aren't thread-safe — each thread needs its own
        conn = psycopg2.connect(DATABASE_URL)
        worker_id = f"{socket.gethostname()}-{threading.get_ident()}"
        try:
            while True:
                if not worker_loop(conn, worker_id):
                    break
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(run_one) for _ in range(10)]
        for f in as_completed(futures):
            f.result()
