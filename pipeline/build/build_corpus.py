import csv
import glob
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

NS = "{http://www.tei-c.org/ns/1.0}"
ITEMS_JSON = os.environ.get("ITEMS_JSON", "writes/temp.json")
BITSTREAMS_JSON = os.environ.get("BITSTREAMS_JSON", "writes/pdf_bitstreams.json")
TEI_DIR = os.environ.get("TEI_DIR", "extracted_text")
PDF_DIR = os.environ.get("PDF_DIR", "downloaded_pdfs")
JSONL_OUT = os.environ.get("JSONL_OUT", "writes/corpus.jsonl")
CSV_OUT = os.environ.get("CSV_OUT", "writes/corpus.csv")
HYPHENATE = os.environ.get("HYPHENATE", "1") == "1"
KEEP_FIGURES = os.environ.get("KEEP_FIGURES", "0") == "1"

BLOCK_TAGS = {"p", "head", "note", "item", "label", "quote", "formula", "figDesc"}
SKIP_TAGS = {"figure", "biblStruct", "figure"} if not KEEP_FIGURES else {"biblStruct"}

AUTHOR_KEYS = ("dc.contributor.author", "local.contributor.author")
DATE_KEYS = ("dc.date.issued", "dc.date.submitted", "dc.date.created", "dc.date.available")
SUBJECT_KEYS = ("dc.subject", "dc.subject.lcsh", "dc.subject.mesh", "dc.subject.other")

HYPHEN_BREAK = re.compile(r"(\w)-[ \t]*\n?[ \t]*(\w)")
WHITESPACE = re.compile(r"[ \t\r\f\v]+")


def local(tag: str) -> str:
    return tag.rpartition("}")[2]


def clean(text: str) -> str:
    text = WHITESPACE.sub(" ", text.replace("\n", " "))
    if HYPHENATE:
        text = HYPHEN_BREAK.sub(r"\1\2", text)
    return text.strip()


def text_of(node, drop_refs: bool = True) -> str:
    parts: list[str] = []

    def walk(current):
        if drop_refs and local(current.tag) == "ref":
            return
        if current.text:
            parts.append(current.text)
        for child in current:
            walk(child)
            if child.tail:
                parts.append(child.tail)

    walk(node)
    return clean("".join(parts))


def iter_blocks(node):
    tag = local(node.tag)
    if tag in SKIP_TAGS:
        return
    if tag in BLOCK_TAGS:
        if node.text and node.text.strip():
            yield node
        return
    for child in node:
        yield from iter_blocks(child)


def extract_body_text(root) -> str:
    body = root.find(f".//{NS}text/{NS}body")
    if body is None:
        return ""
    paragraphs = [text_of(block) for block in iter_blocks(body)]
    return "\n\n".join(p for p in paragraphs if p)


def extract_abstract(root) -> str:
    node = root.find(f".//{NS}profileDesc/{NS}abstract")
    if node is None:
        return ""
    paragraphs = [text_of(block) for block in iter_blocks(node)]
    return "\n\n".join(p for p in paragraphs if p)


def meta_values(metadata: dict, key: str) -> list:
    return [entry.get("value", "").strip() for entry in metadata.get(key, [])]


def first_meta(metadata: dict, keys: tuple) -> str:
    for key in keys:
        values = meta_values(metadata, key)
        if values:
            return values[0]
    return ""


def ordered_meta(metadata: dict, key: str) -> list:
    entries = sorted(metadata.get(key, []), key=lambda e: e.get("place") or 0)
    return [e.get("value", "").strip() for e in entries]


def unique(values) -> list:
    seen = set()
    out = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def load_metadata() -> tuple:
    with open(ITEMS_JSON, encoding="utf-8") as handle:
        items = {item["id"]: item for item in json.load(handle)}

    bitstream_by_item = {}
    if os.path.isfile(BITSTREAMS_JSON):
        with open(BITSTREAMS_JSON, encoding="utf-8") as handle:
            for row in json.load(handle):
                bitstream_by_item.setdefault(row["item_id"], []).append(row)

    return items, bitstream_by_item


def build_record(stem: str, items: dict, bitstream_by_item: dict) -> dict:
    item = items.get(stem, {})
    metadata = item.get("metadata", {})

    tei_path = os.path.join(TEI_DIR, f"{stem}.grobid.tei.xml")
    grobid_abstract, grobid_text = "", ""
    if os.path.isfile(tei_path):
        root = ET.parse(tei_path).getroot()
        grobid_abstract = extract_abstract(root)
        grobid_text = extract_body_text(root)

    dspace_abstract = first_meta(metadata, ("dc.description.abstract",))
    if dspace_abstract:
        abstract, abstract_source = dspace_abstract, "dspace"
    else:
        abstract, abstract_source = grobid_abstract, "grobid"

    bitstreams = bitstream_by_item.get(stem, [])
    return {
        "item_id": stem,
        "handle_id": item.get("handle", ""),
        "bitstream_id": bitstreams[0]["bitstream_id"] if bitstreams else "",
        "content_url": bitstreams[0]["content_url"] if bitstreams else "",
        "title": first_meta(metadata, ("dc.title",)) or item.get("name", ""),
        "authors": unique(
            value
            for key in AUTHOR_KEYS
            for value in ordered_meta(metadata, key)
        ),
        "date": first_meta(metadata, DATE_KEYS),
        "subject": unique(
            value for key in SUBJECT_KEYS for value in ordered_meta(metadata, key)
        ),
        "rights": first_meta(metadata, ("dc.rights",)),
        "source_url": first_meta(metadata, ("dc.identifier.uri",)),
        "abstract": abstract,
        "abstract_source": abstract_source,
        "text": grobid_text,
        "pdf_path": os.path.join(PDF_DIR, f"{stem}.pdf"),
        "tei_path": tei_path if os.path.isfile(tei_path) else "",
    }


def write_outputs(records: list) -> None:
    os.makedirs(os.path.dirname(JSONL_OUT) or ".", exist_ok=True)

    with open(JSONL_OUT, "w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    list_fields = ("authors", "subject")
    columns = [
        "handle_id", "title", "authors", "date", "subject",
        "rights", "source_url", "abstract", "text",
        "item_id", "bitstream_id", "content_url",
        "abstract_source", "pdf_path", "tei_path",
    ]

    with open(CSV_OUT, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for record in records:
            row = dict(record)
            for field in list_fields:
                row[field] = "; ".join(row[field])
            writer.writerow({column: row.get(column, "") for column in columns})


def main() -> None:
    items, bitstream_by_item = load_metadata()

    stems = sorted(
        os.path.basename(path).split(".")[0]
        for path in glob.glob(os.path.join(TEI_DIR, "*.tei.xml"))
    )
    if not stems:
        sys.exit(f"No TEI files in {TEI_DIR}")

    records = [build_record(stem, items, bitstream_by_item) for stem in stems]
    write_outputs(records)

    total = len(records)
    with_pdf = sum(1 for r in records if os.path.isfile(r["pdf_path"]))
    with_meta = sum(1 for r in records if r["title"])
    with_abstract = sum(1 for r in records if r["abstract"])
    grobid_abstracts = sum(1 for r in records if r["abstract_source"] == "grobid")
    with_text = sum(1 for r in records if len(r["text"]) > 200)
    with_authors = sum(1 for r in records if r["authors"])
    with_subject = sum(1 for r in records if r["subject"])
    with_rights = sum(1 for r in records if r["rights"])
    with_date = sum(1 for r in records if r["date"])

    print(f"records        : {total}")
    print(f"pdf on disk    : {with_pdf}")
    print(f"dspace title   : {with_meta}")
    print(f"with abstract  : {with_abstract} (dspace {total - grobid_abstracts}, grobid {grobid_abstracts})")
    print(f"usable text    : {with_text}")
    print(f"with authors   : {with_authors}")
    print(f"with date      : {with_date}")
    print(f"with subject   : {with_subject}")
    print(f"with rights    : {with_rights}")
    print(f"\nwrote {JSONL_OUT} and {CSV_OUT}")


if __name__ == "__main__":
    main()
