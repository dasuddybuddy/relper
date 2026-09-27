# RELPER

A research-intelligence pipeline over the [Georgia Tech SMARTECH](https://repository.gatech.edu/) repository. RELPER harvests every open-access paper in the College of Computing, turns each PDF into structured full text with [GROBID](https://github.com/kermitt2/grobid), and reconciles the extraction against the repository's own catalog records to produce a clean, queryable corpus — the substrate a GraphRAG layer will sit on.

**Status:** corpus pipeline is production-shaped and running. The retrieval/graph layer is not built yet.

---

## Pipeline

```
SMARTECH DSpace REST API
        │  3,166 items, 67 metadata fields
        ▼
  get_all_papers.py ──── paginated discovery, concurrent page fetch
        ▼
  bitstream_lookup.py ── walk bundles → ORIGINAL → filter *.pdf
        │  2,860 PDF bitstreams
        ▼
  pdf_db.py ──────────── seed Postgres queue (item_id, handle, bitstream_id, url)
        ▼
  pdf_downloads.py ───── 10 workers · claim queue · download
        │  2,519 PDFs (16.6 GB)
        ▼
  read_text.py ───────── GROBID `processFulltextDocument` → TEI XML
        │  992 extractions (217 MB)
        ▼
  retry_failed.py ────── re-drive GROBID failures until exhausted
        ▼
  build_corpus.py ────── TEI + catalog join → corpus.jsonl / corpus.csv
```

Each stage is independently re-runnable and idempotent: re-running picks up where the last one stopped rather than restarting the crawl.

---

## Design decisions

**A queue in Postgres, not a thread pool over a list.** `claim_paper` issues a single `UPDATE ... WHERE id = (SELECT id ... FOR UPDATE SKIP LOCKED LIMIT 1) RETURNING *`. Ten workers share one queue with no coordinator, no lock contention, and no coordination between them; adding a fourth Kubernetes replica (see `deployment.yaml`) needs zero code change. `attempts`/`max_attempts` bound retries per row, so a permanently dead bitstream is quarantined as `failed` with its error text rather than being retried forever. A `claimed_at` index supports reclaiming rows orphaned by a pod that died mid-download.

**Everything is keyed by `item_id`, never `bitstream_id`.** SMARTECH items are one-to-many with PDF bitstreams — 40 items carry more than one. Naming every artifact after the item means the GROBID output joins back to catalog metadata with a single string match, and the bibliographic record is a property of the *work* rather than of whichever file happened to be downloaded. The tradeoff is that a second bitstream for the same item overwrites the first; that is a known, bounded data loss (40 items) and the fix is a `bitstreams/` subdirectory per item.

**Catalog metadata beats extraction for bibliographic fields.** GROBID is good at text and unreliable at cataloging. It missed `dc.subject` on the majority of records, guessed wrong issue dates, and on at least one thesis returned the *acknowledgements* as the abstract. So title, authors, date, subject, rights, and source URL are read from DSpace, and GROBID is trusted only for `<abstract>` and `<text><body>`. `build_corpus.py` records which side supplied each abstract in an `abstract_source` field, so the 86 GROBID-sourced rows (36 of them stubs under 30 characters) are auditable rather than silently trusted.

**File system as the state machine for the extraction stage.** GROBID writes a `<stem>_<status>.txt` marker on failure and deletes it on success, so `retry_failed.py` derives the retry set by scanning for markers — the failure list shrinks by itself as retries land, and the extraction stage needs no database at all.

**Extraction cleanup happens once, at the end.** TEI markup is normalized into paragraphs at corpus-build time: `<figure>` blocks dropped, `<ref>` citation anchors unwrapped, hyphenated line breaks rejoined, whitespace collapsed. Consumers get a `text` field they can embed without writing a TEI parser, and a re-run of the cleaner is cheap compared to re-running GROBID.

---

## Corpus output

`build_corpus.py` joins the 992 extractions against the catalog and emits `writes/corpus.jsonl` (one object per record) plus `writes/corpus.csv`.

| Column | Source |
|---|---|
| `handle_id` | DSpace item handle (`1853/6604`) |
| `title` | `dc.title` |
| `authors` | `dc.contributor.author` → `local.contributor.author`, ordered by DSpace's `place`, deduped |
| `date` | `dc.date.issued` → `submitted` → `created` → `available` |
| `subject` | `dc.subject` + `.lcsh` + `.mesh` + `.other`, deduped |
| `rights` | `dc.rights` |
| `source_url` | `dc.identifier.uri` |
| `abstract` | DSpace `dc.description.abstract`, falling back to GROBID |
| `text` | GROBID `<text><body>` |
| `item_id`, `bitstream_id`, `content_url` | join keys / provenance |
| `abstract_source` | which side supplied `abstract` |

Current field coverage across the 992 extracted records:

| | records |
|---|---|
| title, date, source_url | 992 |
| authors | 991 |
| subject | 966 |
| abstract | 956 (906 DSpace, 50 GROBID) |
| usable body text (>200 chars) | 989 |
| rights | 3 |

Rights is genuinely sparse: only 280 of 3,166 catalog records carry a `dc.rights` value at all, and the pipeline does not synthesize one. It stays empty rather than guessed.

Author ordering relies on DSpace's `place` field, which encodes submission order — worth noting as a dependency on repository-side behavior rather than a documented guarantee.

---

## Running it

Requires a local GROBID server (`http://localhost:8070` by default, see `config.json`) and a Postgres instance.

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

export DATABASE_URL=postgres://...        # download queue
python get_all_papers.py                  # discover items
python bitstream_lookup.py                # resolve PDF bitstreams
python pdf_db.py                          # seed the queue
python pdf_downloads.py                   # download (10 workers)
python read_text.py                       # GROBID extraction
python retry_failed.py                    # re-drive failures
python build_corpus.py                    # build the corpus
```

`read_text.py`, `retry_failed.py`, and `build_corpus.py` are tunable by environment variable rather than code edits — `THREADS`, `BATCH_SIZE`, `RETRY_ROUNDS`, `KEEP_FIGURES`, `HYPHENATE`, and the input/output paths.

---

## Layout

```
.                       pipeline stages, one concern per file
models/paper_record.py  typed row wrapper for the download queue
config.json             GROBID client + server config
deployment.yaml         4-replica download Deployment
Dockerfile              download worker image
writes/                 catalog JSON, bitstream map, corpus output
downloaded_pdfs/        PDFs, named by item_id
extracted_text/         GROBID TEI output, one file per item_id
```

PDFs, TEI, and corpus output are gitignored. They are large (16.6 GB) and, more importantly, licensed by their authors — redistribution rights are the repository's, not this project's. Code is committed; data is not.

## Stack

Python 3.12 · Postgres (`psycopg2`) · Kubernetes · DSpace REST API · GROBID (`grobid-client-python`) · `lxml` / `xml.etree` for TEI

## Roadmap

- Ingest the 1,854 PDFs that are downloaded but not yet extracted.
- Resolve the 40 items with multiple PDF bitstreams into per-item subdirectories.
- Chunker and embedd `text`, build the graph layer, stand up GraphRAG retrieval.
- Backfill `dc.rights` from license fields (`dc.rights.metadata`, `dc.rights.uri`).

---

## Data source

Content comes from the [Georgia Tech SMARTECH repository](https://repository.gatech.edu/), restricted to the College of Computing. This project redistributes nothing: PDFs and derived text stay local. Only unrestricted, published research is collected — embargoed and access-restricted items are excluded upstream by the repository and are not in this corpus.
