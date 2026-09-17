import os
import json
import psycopg2

with open("writes/pdf_bitstreams.json", "r") as f:
    items = json.load(f)

DATABASE_URL = os.environ["DATABASE_URL"]

conn = psycopg2.connect(DATABASE_URL)

cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS pdf_downloader.papers (
    id SERIAL PRIMARY KEY,
    item_id UUID NOT NULL,
    item_handle TEXT NOT NULL,
    bitstream_id UUID UNIQUE NOT NULL,
    content_url TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'in_progress', 'done', 'failed')),
    attempts INT NOT NULL DEFAULT 0,
    max_attempts INT NOT NULL DEFAULT 5,
    claimed_by TEXT,
    claimed_at TIMESTAMPTZ,
    error TEXT,
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_papers_status ON pdf_downloader.papers(status);
CREATE INDEX IF NOT EXISTS idx_papers_claimed_at ON pdf_downloader.papers(claimed_at)
    WHERE status = 'in_progress';
""")

for p in papers:
    cur.execute(
        """INSERT INTO pdf_downloader.papers (item_id, item_handle, bitstream_id, content_url)
           VALUES (%s, %s, %s, %s)
           ON CONFLICT (bitstream_id) DO NOTHING""",
        (p["item_id"], p["item_handle"], p["bitstream_id"], p["content_url"])
    )

conn.commit()
print(f"Seeded {len(papers)} papers")
cur.close()
conn.close()
