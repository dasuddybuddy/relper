from grobid_client.grobid_client import GrobidClient
import os

os.makedirs("extracted_text", exist_ok=True)
# Initialize with default localhost server
client = GrobidClient(config_path="./config.json")

client.process(
    service="processFulltextDocument",
    input_path="test",
    output="extracted_text",
    n=4,
    consolidate_header=False,
    consolidate_citations=False,
)
