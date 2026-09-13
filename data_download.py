import requests
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

url = "https://repository.gatech.edu/server/api/discover/browses/organizations/items"

base_params = {
    "scope": "20d31e81-afd7-4b26-bf4a-5785ad2633d0",
    "sort": "default,ASC",
    "size": 100,
    "filterValue": "College of Computing",
    "embed": "thumbnail",
}


def fetch_page(page):
    params = base_params.copy()
    params["page"] = page

    response = requests.get(
        url,
        params=params,
        timeout=30,
    )
    response.raise_for_status()

    return page, response.json()

# Discover total number of pages
first_page_number, first_page = fetch_page(0)

total_pages = first_page["page"]["totalPages"]
all_items = first_page["_embedded"]["items"]

print(f"Total pages: {total_pages}")

# Fetch remaining pages concurrently
with ThreadPoolExecutor(max_workers=5) as executor:
    future_to_page = {
        executor.submit(fetch_page, page): page
        for page in range(1, total_pages)
    }

    for future in as_completed(future_to_page):
        page_number, data = future.result()
        all_items.extend(data["_embedded"]["items"])

with open('temp.json', "w") as file:
    json.dump(all_items, file, indent=2)
print(f"Total items: {len(all_items)}")
