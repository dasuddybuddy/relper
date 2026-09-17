from grobid_client.grobid_client import GrobidClient
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import json
import os
import shutil

def download_pdf(item):
    response = requests.get(item["content_url"])
    response.raise_for_status()
    filename = f"temp_pdfs/{item['item_id']}.pdf"

    with open(filename, "wb") as f:
        f.write(response.content)


def download_pdfs():
    os.makedirs("temp_pdfs", exist_ok=True)

    with open("writes/pdf_bitstreams.json", "r") as f:
        bitstreams = json.load(f)

    failed = []

    with ThreadPoolExecutor(max_workers=10) as executor:
        
        futures = {
            executor.submit(download_pdf, item) : item
            for item in bitstreams
        }

        for future in as_completed(futures):
            item = futures[future]
            try:
                future.result()
            except Exception as e:
                failed.append(item)
                print(f"Failed {item['item_id']}: {e}")

    return failed

if __name__ == "__main__":
    print("start")

    failed = download_pdfs()
    print(f"{len(failed)} downloads failed")

    with open("writes/miss-pdfs.json", "w", encoding="utf-8") as f:
        json.dump(failed, f, indent=2)

    client = GrobidClient()

    client.process(
        service="processFulltextDocument",
        input_path="temp_pdfs",
        output="writes/tei",
        consolidate_header=True,
    )

    import shutil
    shutil.rmtree("temp_pdfs")
