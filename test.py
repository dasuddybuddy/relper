import json

with open("writes/pdf_bitstreams.json", "r") as file:
    pdfs = json.load(file)

with open("writes/temp.json", "r") as file:
    original = json.load(file)

print(original[0])
print()
print(pdfs[0])
