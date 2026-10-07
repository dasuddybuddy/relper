from grobid_client.grobid_client import GrobidClient
import os

INPUT_DIR = os.environ.get("INPUT_DIR", "downloaded_pdfs")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "extracted_text")
MAX_PDFS = int(os.environ.get("MAX_PDFS", "1000"))
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "30"))
THREADS = int(os.environ.get("THREADS", "4"))

os.makedirs(OUTPUT_DIR, exist_ok=True)

pdfs = sorted(
    os.path.join(INPUT_DIR, name)
    for name in os.listdir(INPUT_DIR)
    if name.lower().endswith(".pdf")
)

if len(pdfs) > MAX_PDFS:
    print(f"Found {len(pdfs)} PDFs, taking the first {MAX_PDFS}")
    pdfs = pdfs[:MAX_PDFS]
else:
    print(f"Found {len(pdfs)} PDFs, processing all of them")

# Initialize with default localhost server
client = GrobidClient(config_path="./config.json")

# The client walks the list in chunks of BATCH_SIZE, so PDFs are submitted to
# GROBID BATCH_SIZE at a time, THREADS of them concurrently.
client.config["queue_size"] = BATCH_SIZE

client.process_paths(
    service="processFulltextDocument",
    inputs=pdfs,
    output=OUTPUT_DIR,
    n=THREADS,
    consolidate_header=False,
    consolidate_citations=False,
    skip_errors=True,
)
