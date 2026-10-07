import json
import requests


with open("writes/miss.json", "r") as file:
    items = json.load(file)

for item in items:
    print(item['name'] + "\n")
