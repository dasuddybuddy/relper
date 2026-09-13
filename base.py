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
