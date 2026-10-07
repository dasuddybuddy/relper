from grobid_client.grobid_client import GrobidClient
import os
import re
import time
from collections import Counter

INPUT_DIR = os.environ.get("INPUT_DIR", "downloaded_pdfs")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "extracted_text")
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "30"))
THREADS = int(os.environ.get("THREADS", "4"))
RETRY_LIMIT = int(os.environ.get("RETRY_LIMIT", "100"))
RETRY_ROUNDS = int(os.environ.get("RETRY_ROUNDS", "3"))
RETRY_DELAY = float(os.environ.get("RETRY_DELAY", "5"))
ERROR_MARKER = re.compile(r"_\d{3}\.txt$")


def list_failed() -> list:
    """PDFs in INPUT_DIR whose last extraction left a <stem>_<status>.txt marker.

    GROBID records a failure as <stem>_<status>.txt next to the TEI output and
    deletes that marker once the document succeeds, so this list shrinks by
    itself as retries land.
    """
    failed = []
    for name in os.listdir(OUTPUT_DIR):
        if not ERROR_MARKER.search(name):
            continue
        stem = name[: name.rindex("_")]
        pdf = os.path.join(INPUT_DIR, f"{stem}.pdf")
        if os.path.isfile(pdf):
            failed.append(pdf)
    return sorted(failed)


def status_counts() -> Counter:
    counts = Counter()
    for name in os.listdir(OUTPUT_DIR):
        if ERROR_MARKER.search(name):
            counts[name[name.rindex("_") + 1: -len(".txt")]] += 1
    return counts


def main() -> None:
    if not os.path.isdir(OUTPUT_DIR):
        raise SystemExit(f"No such output directory: {OUTPUT_DIR}")

    client = GrobidClient(config_path="./config.json")
    client.config["queue_size"] = BATCH_SIZE

    for attempt in range(1, RETRY_ROUNDS + 1):
        if attempt > 1:
            time.sleep(RETRY_DELAY)

        failed = list_failed()
        if not failed:
            print("No failed documents left")
            break

        batch = failed[:RETRY_LIMIT] if RETRY_LIMIT else failed
        print(
            f"Round {attempt}/{RETRY_ROUNDS}: retrying {len(batch)} of "
            f"{len(failed)} failed document(s)"
        )

        client.process_paths(
            service="processFulltextDocument",
            inputs=batch,
            output=OUTPUT_DIR,
            n=THREADS,
            consolidate_header=False,
            consolidate_citations=False,
            skip_errors=True,
        )

        remaining = list_failed()
        print(
            f"Round {attempt}: recovered {len(failed) - len(remaining)}, "
            f"{len(remaining)} still failing"
        )

    remaining = list_failed()
    print(f"\nFailed documents remaining: {len(remaining)}")
    for status, count in sorted(status_counts().items()):
        print(f"  HTTP {status}: {count}")


if __name__ == "__main__":
    main()
