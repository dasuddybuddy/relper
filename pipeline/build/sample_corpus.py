import csv
import os
import sys

try:
    csv.field_size_limit(sys.maxsize)
except OverflowError:
    csv.field_size_limit(2**31 - 1)

CSV_IN = os.environ.get("CSV_IN", "ragproject/input/gt_cs_papers.csv")
CSV_OUT = os.environ.get("CSV_OUT", "ragproject/input/corpus_sample.csv")
ROWS = int(os.environ.get("ROWS", "100"))


def main():
    with open(CSV_IN, newline="", encoding="utf-8") as src, open(
        CSV_OUT, "w", newline="", encoding="utf-8"
    ) as dst:
        reader = csv.reader(src)
        writer = csv.writer(dst)
        header = next(reader, None)
        if header is None:
            raise SystemExit(f"{CSV_IN} is empty")
        writer.writerow(header)
        written = 0
        for row in reader:
            if written >= ROWS:
                break
            writer.writerow(row)
            written += 1
    print(f"wrote {written} rows to {CSV_OUT} from {CSV_IN}")


if __name__ == "__main__":
    main()
