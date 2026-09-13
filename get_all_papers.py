import scan_page

def get_all_papers():
    # Discover total number of pages
    first_page = scan_page.get_page(0)

    total_pages = first_page["page"]["totalPages"]
    all_items = first_page["_embedded"]["items"]

    print(f"Total pages: {total_pages}")

    # Fetch remaining pages concurrently
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_page = {
            executor.submit(scan_page.get_page, page): page
            for page in range(1, total_pages)
        }

        for future in as_completed(future_to_page):
            data = future.result()[1]
            all_items.extend(data["_embedded"]["items"])

    with open('temp.json', "w") as file:
        json.dump(all_items, file, indent=2)
    print(f"Total items: {len(all_items)}")
