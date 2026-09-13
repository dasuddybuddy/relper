import requests
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

def get_pdf_bitstreams(item):
    item_id = item['id']
    bundles_url = (
        f"https://repository.gatech.edu/server/api/core/"
        f"items/{item_id}/bundles"
    )

    response = requests.get(bundles_url, timeout=30)
    response.raise_for_status()

    bundles = response.json()["_embedded"]["bundles"]

    original_bundle = next(
        bundle
        for bundle in bundles
        if bundle["name"] == "ORIGINAL"
    )

    bundle_id = original_bundle["uuid"]

    bitstreams_url = (
        f"https://repository.gatech.edu/server/api/core/"
        f"bundles/{bundle_id}/bitstreams"
    )

    response = requests.get(bitstreams_url, timeout=30)
    response.raise_for_status()

    bitstreams = response.json()["_embedded"]["bitstreams"]

    return [
        bitstream
        for bitstream in bitstreams
        if bitstream.get("mimeType") == "application/pdf"
    ]

with open("temp.json", "r") as f:
    items = json.load(f)

all_pdf_bitstreams = []

with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {
        executor.submit(get_pdf_bitstreams, item): item
        for item in items
    }

    completed = 0
total = len(futures)

for future in as_completed(futures):
    completed += 1

    try:
        pdf_bitstreams = future.result()
        all_pdf_bitstreams.extend(pdf_bitstreams)

    except Exception as e:
        item = futures[future]
        print(f"\nFAILED {completed}/{total}")
        print(f"Item ID: {item['id']}")
        print(f"Error: {type(e).__name__}: {e}")

    if completed % 100 == 0 or completed == total:
        print(f"Progress: {completed}/{total} ({completed / total * 100:.1f}%)")

total_bytes = sum(
    bitstream["sizeBytes"]
    for bitstream in all_pdf_bitstreams
)

total_gb = total_bytes / 10**9
total_gib = total_bytes / 1024**3

print(f"{total_gb:.2f} GB")
print(f"{total_gib:.2f} GiB")

