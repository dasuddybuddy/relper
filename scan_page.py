import base
from typing import Any

def get_page(page : int) -> dict[str, Any]:
    """Get one page of items from SMARTECH repository.

    Args:
        page (int): The current page number.

    Returns:
        dict[str, Any]: A json of the contents of the current page.

    Raises:
        requests.exceptions.HTTPError: If page returns a status error
    """
    params = base_params.copy()
    params["page"] = page

    response = requests.get(
        url,
        params=params,
        timeout=30,
    )
    response.raise_for_status()

    return response.json()
