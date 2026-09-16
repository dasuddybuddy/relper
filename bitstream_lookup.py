import requests
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

def get_bundle(item, retries=3):
    item_id = item["id"]

    bundles_url = (
        f"https://repository.gatech.edu/server/api/core/"
        f"items/{item_id}/bundles"
    )

    for attempt in range(retries):
        try:
            response = requests.get(bundles_url, timeout=30)
            response.raise_for_status()
            break

        except requests.exceptions.RequestException:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)

    bundles = response.json()["_embedded"]["bundles"]

    original_bundle = next(
        bundle for bundle in bundles
        if bundle["name"] == "ORIGINAL"
    )

    original_bundle["uuid"]
    return original_bundle["uuid"]

def get_pdf(item, retries=3):
    bundle_id = get_bundle(item)

    bitstreams_url = (
        f"https://repository.gatech.edu/server/api/core/"
        f"bundles/{bundle_id}/bitstreams"
    )

    for attempt in range(retries):
        try:
            response = requests.get(bitstreams_url, timeout=30)
            response.raise_for_status()
            break

        except requests.exceptions.RequestException:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)

    bitstreams = response.json()["_embedded"]["bitstreams"]

    return [
        {
            "item_id": item["id"],
            "item_handle": item.get("handle"),
            "bitstream_id": bitstream["id"],
            "content_url": bitstream["_links"]["content"]["href"],
        }
        for bitstream in bitstreams
        if bitstream.get("name").lower().endswith("pdf")
    ]


if __name__ == "__main__":
    print("start")
    with open("writes/temp.json", "r") as f:
        items = json.load(f)

    all_pdf_bitstreams = []
    failed_items = []

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(get_pdf, item): item
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
                failed_items.append(item)
                print(f"\nFAILED {completed}/{total}")
                print(f"Item ID: {item['id']}")
                print(f"Error: {type(e).__name__}: {e}")

            print(f"Progress: {completed}/{total} ({completed / total * 100:.1f}%)")

    for item in failed_items:
        try:
            pdf_bitstreams = get_pdf(item)
            all_pdf_bitstreams.extend(pdf_bitstreams)
        except Exception as e:
            print(f"Retry failed for {item['id']}: {e}")

    with open("writes/miss.json", "w", encoding="utf-8") as file:
        json.dump(failed_items, file, indent=2)

    with open("writes/pdf_bitstreams.json", "w", encoding="utf-8") as file:
        json.dump(all_pdf_bitstreams, file, indent=2)



