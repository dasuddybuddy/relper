import base

def get_page(page):
    params = base_params.copy()
    params["page"] = page

    response = requests.get(
        url,
        params=params,
        timeout=30,
    )
    response.raise_for_status()

    return response.json()
