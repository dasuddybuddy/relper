import bitstream_lookup as bl

pdfs = []
with open('writes/miss.json', 'r') as file:
    for line in file:
        item = {"id": line.strip()}
        pdfs.append(bl.get_pdf(item))

print(pdfs)

