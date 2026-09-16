import requests
import json

with open("temp.json", "r") as f:
    items = json.load(f)

print(len(items))

item = items[0]
print(item['id'])

# Get bundles
bundles_url = (
    f"https://repository.gatech.edu/server/api/core/"
    f"items/{item['id']}/bundles"
)

bundles = requests.get(bundles_url).json()
print(bundles)

bundles = requests.get(bundles_url).json()["_embedded"]["bundles"]


# Find ORIGINAL bundle
original_bundle = next(
    bundle for bundle in bundles
    if bundle["name"] == "ORIGINAL"
)

# Get bitstreams in ORIGINAL
bitstreams_url = (
    f"https://repository.gatech.edu/server/api/core/"
    f"bundles/{original_bundle['uuid']}/bitstreams"
)

bitstreams = requests.get(bitstreams_url).json()["_embedded"]["bitstreams"]
print(bitstreams)
