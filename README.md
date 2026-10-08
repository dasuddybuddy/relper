# RELPER

A research-intelligence pipeline over the [Georgia Tech SMARTECH](https://repository.gatech.edu/) repository. RELPER harvests every open-access paper in the College of Computing, turns each PDF into structured full text with [GROBID](https://github.com/kermitt2/grobid), and reconciles the extraction against the repository's own catalog records to produce a clean, queryable corpus. A GraphRAG retrieval layer then reasons across that corpus rather than over single documents, so a query returns the papers *and* the relationships between them.

That retrieval layer is driven from an interactive terminal — [`pipeline/cli/query_cli.py`](pipeline/cli/query_cli.py). A bare question runs a basic search, a leading `basic`/`local`/`global`/`drift` (or `kw=<method>`) selects the retrieval strategy, and `visualize` opens a 3D map of the entity graph the index was built from.

---

## Demo

### Basic Query

### Local Query

### Global Query


### Visualizer


## Pipeline

```
SMARTECH DSpace REST API
        │  3,166 items, 67 metadata fields
        ▼
  pipeline/dspace/get_all_papers.py ── paginated discovery, concurrent page fetch
        ▼
  pipeline/dspace/bitstream_lookup.py ── walk bundles → ORIGINAL → filter *.pdf
        │  2,860 PDF bitstreams
        ▼
  pipeline/ingest/pdf_db.py ── seed Postgres queue (item_id, handle, bitstream_id, url)
        ▼
  pipeline/ingest/pdf_downloads.py ── 10 workers · claim queue · download
        │  2,519 PDFs (16.6 GB)
        ▼
  pipeline/ingest/read_text.py ── GROBID `processFulltextDocument` → TEI XML
        │  1,000+ extractions (217 MB)
        ▼
  pipeline/ingest/retry_failed.py ── re-drive GROBID failures until exhausted
        ▼
  pipeline/build/build_corpus.py ── TEI + catalog join → corpus.jsonl / corpus.csv
        │  1,000+ records, full text + bibliographic fields
        ▼
  build_index.py ─────── structure-aware chunking → embeddings → pgvector
        ▼
  build_graph.py ─────── paper/author/topic/venue graph + citation edges
        │  Louvain communities, summarized and cached
        ▼
  ask.py ──────────────── routed retrieval → answer + citable papers
```

Each stage is independently re-runnable and idempotent: re-running picks up where the last one stopped rather than restarting the crawl.

---

## Design decisions

**A queue in Postgres, not a thread pool over a list.** `claim_paper` issues a single `UPDATE ... WHERE id = (SELECT id ... FOR UPDATE SKIP LOCKED LIMIT 1) RETURNING *`. Ten workers share one queue with no coordinator, no lock contention, and no coordination between them; adding a fourth Kubernetes replica (see `deployment.yaml`) needs zero code change. `attempts`/`max_attempts` bound retries per row, so a permanently dead bitstream is quarantined as `failed` with its error text rather than being retried forever. A `claimed_at` index supports reclaiming rows orphaned by a pod that died mid-download.

**Everything is keyed by `item_id`, never `bitstream_id`.** SMARTECH items are one-to-many with PDF bitstreams — 40 items carry more than one. Naming every artifact after the item means the GROBID output joins back to catalog metadata with a single string match, and the bibliographic record is a property of the *work* rather than of whichever file happened to be downloaded. The same key carries through chunking, embedding, and the graph, so the whole system is joinable end to end without a single crosswalk table. The tradeoff is that a second bitstream for the same item overwrites the first; that is a known, bounded data loss (40 items) and the fix is a `bitstreams/` subdirectory per item.

**Catalog metadata beats extraction for bibliographic fields.** GROBID is good at text and unreliable at cataloging. It missed `dc.subject` on the majority of records, guessed wrong issue dates, and on at least one thesis returned the *acknowledgements* as the abstract. So title, authors, date, subject, rights, and source URL are read from DSpace, and GROBID is trusted only for `<abstract>` and `<text><body>`. `build_corpus.py` records which side supplied each abstract in an `abstract_source` field, so the 86 GROBID-sourced rows (36 of them stubs under 30 characters) are auditable rather than silently trusted. Author nodes in the graph inherit this decision: identity resolution against a curated name map beats fuzzy string matching on extraction output.

**File system as the state machine for the extraction stage.** GROBID writes a `<stem>_<status>.txt` marker on failure and deletes it on success, so `retry_failed.py` derives the retry set by scanning for markers — the failure list shrinks by itself as retries land, and the extraction stage needs no database at all.

**Extraction cleanup happens once, at the end.** TEI markup is normalized into paragraphs at corpus-build time: `<figure>` blocks dropped, `<ref>` citation anchors unwrapped, hyphenated line breaks rejoined, whitespace collapsed. Consumers get a `text` field they can chunk and embed without writing a TEI parser, and a re-run of the cleaner is cheap compared to re-running GROBID.

**Provenance is a schema requirement, not a feature.** `item_id` is carried from the original API response all the way through to the citation attached to an answer. The alternative — a retrieval layer that emits confident prose with no path back to a source PDF — is unusable for research no matter how good the prose reads.

---

## Corpus output

`pipeline/build/build_corpus.py` joins the 1,000+ extractions against the catalog and emits `writes/corpus.jsonl` (one object per record) plus `writes/corpus.csv`.

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

Current field coverage across the 1,000+ extracted records:

| | records |
|---|---|
| title, date, source_url | 1,000+ |
| authors | ~1,000 |
| subject | ~970 |
| abstract | ~960 (910 DSpace, 50 GROBID) |
| usable body text (>200 chars) | ~990 |
| rights | 3 |

Rights is genuinely sparse: only 280 of 3,166 catalog records carry a `dc.rights` value at all, and the pipeline does not synthesize one. It stays empty rather than guessed.

Author ordering relies on DSpace's `place` field, which encodes submission order — worth noting as a dependency on repository-side behavior rather than a documented guarantee.

---

## Graph layer

The corpus is chunked, embedded, and linked into a typed entity graph, then queried through a router that picks the right retrieval strategy per question.

**Chunking follows document structure, not a token window.** GROBID's TEI already carries section boundaries, so chunks split on `<head>` elements and pack whole paragraphs into ~1,200-token windows with a small overlap. Every chunk stores its `item_id`, section head, and character offsets into the normalized text. That provenance is the point: a researcher can trace any sentence in an answer back to a section of a specific PDF, and an untraceable answer is worse than no answer.

**One Postgres, one GROBID.** Embeddings live in `pgvector` in the same instance as the download queue, with an HNSW index and cosine distance. Standing up a second datastore for a corpus this size would be the wrong trade. The embed stage is rate-limited by the embedding API rather than CPU-bound, which makes it a queue problem — so it reuses the same `FOR UPDATE SKIP LOCKED` worker pattern as `pdf_downloads.py` instead of adding new infrastructure. Adding capacity is another replica, same as the downloader.

**The graph reuses metadata that is already on disk.**

| Node | Derived from |
|---|---|
| `paper` | `item_id`, the join key for the whole pipeline |
| `author` | DSpace `dc.contributor.author`, normalized `Last, First` → `First Last` through a name map so authors merge across papers instead of splitting on string variants |
| `topic` | `dc.subject` across plain and `.lcsh` subject terms |
| `venue` | `dc.publisher`, `dc.relation.ispartofseries` |

| Edge | Derived from |
|---|---|
| `authored_by` | DSpace author list |
| `about` | `dc.subject` |
| `cites` | GROBID `<biblStruct>` reference entries |
| `cites_within_corpus` | citation edges resolving to another `item_id` in the collection |

`cites_within_corpus` is the edge worth having. GROBID already writes the reference list into the TEI on disk, so citation structure costs no extra extraction pass. In a single-institution corpus, the subgraph of papers citing each other is a strong signal about which groups built on which — considerably more useful than treating each paper as an isolated blob.

**GraphRAG extraction entity types.** `ragproject/settings.yaml` drives the GraphRAG layer's `extract_graph` step with 26 entity types, scoped to how research papers talk about themselves rather than the generic ORG/PERSON/LOCATION defaults:

| | | |
|---|---|---|
| `Paper` | `Author` | `Institution` |
| `ResearchArea` | `ResearchQuestion` | `Theory` |
| `Problem` | `Task` | `Application` |
| `Method` | `Algorithm` | `OptimizationTechnique` |
| `Model` | `Architecture` | `Hyperparameter` |
| `Dataset` | `Benchmark` | `Metric` |
| `Experiment` | `Result` | `Claim` |
| `Limitation` | `Technology` | `Hardware` |
| `ProgrammingLanguage` | `SoftwareLibrary` | |

**Communities give the system its global view.** Louvain over the co-authorship, co-citation, and topic edges yields clusters that line up with labs and research areas. Each community is summarized once and cached. This is what answers *"what has Georgia Tech worked on in stochastic control?"* — a question about the distribution of papers rather than about any single passage, and precisely the case where pure vector search degrades.

**Retrieval routes by intent.**

- *Specific* — a method, a person, a named result → vector search over chunks, rerank, answer from the top passages.
- *Thematic* — "what has been done on", "which papers" → community summaries plus aggregated topic and co-citation counts.
- *Relational* — "what did this build on", "who works with whom" → traversal outward from a seed node, following `cites_within_corpus` and `authored_by`.

Results merge, and every claim carries the `item_id`s it came from, which resolve to `handle_id` and `source_url` in the corpus. The answer is a set of citable papers, not a paragraph of unattributed prose.

---

## Running the pipeline

Requires a local GROBID server (`http://localhost:8070` by default, see `config.json`) and a Postgres instance.

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

export DATABASE_URL=postgres://...        # queue + pgvector
export GROBID_URL=http://localhost:8070
export EMBEDDING_MODEL=...                # embedding backend

python pipeline/dspace/get_all_papers.py   # discover items
python pipeline/dspace/bitstream_lookup.py # resolve PDF bitstreams
python pipeline/ingest/pdf_db.py           # seed the queue
python pipeline/ingest/pdf_downloads.py    # download (10 workers)
python pipeline/ingest/read_text.py        # GROBID extraction
python pipeline/ingest/retry_failed.py     # re-drive failures
python pipeline/build/build_corpus.py      # join TEI + catalog → corpus

python build_index.py                     # chunk + embed → pgvector
python build_graph.py                     # entity + citation graph, communities
```

`pipeline/ingest/read_text.py`, `pipeline/ingest/retry_failed.py`, `pipeline/build/build_corpus.py`, `build_index.py`, and `ask.py` are tunable by environment variable rather than code edits — thread and batch counts, retry rounds, the embedding model, and the input/output paths.

---

## Running the CLI

The query front-end reads the built index under `ragproject/output/` (override `--root` / `--data`), loading the API key from `ragproject/.env` automatically.

```bash
# interactive: opens its own prompt
python pipeline/cli/query_cli.py
#   kw= What are the dominant themes in stochastic optimal control?   (bare prompt → basic)
#   local Which papers address model predictive control?
#   global What has Georgia Tech worked on?
#   drift Follow the papers that cite each other most
#   visualize                                        (opens the 3D entity graph)
#   exit

# or one-shot, same syntax
python pipeline/cli/query_cli.py "What is the relationship between SOC and MPC?"
python pipeline/cli/query_cli.py global "What themes dominate the corpus?"
```

To open the CLI in its own Terminal window, `cd` into the project root and run:

```bash
cd path/to/relper
./relper.sh
```

The first token sets the search method — `basic` (default), `local` (entity/relationship + vector), `global` (community summaries), or `drift` — either as a bare word or `kw=<method>`. Anything that isn't a method is treated as a prompt and runs a basic search; an unknown `kw=` name is rejected. In the REPL, `visualize` opens `ragproject/output/graph_visualizer.html` in the browser — run `python pipeline/viz/visualize_graph.py` first to generate it. The sidebar search shows a dropdown of matching papers as you type (title or author, arrow keys + Enter work); picking one flies the camera to that node and highlights its edges. Each paper panel also has an **Isolate** button that shows only that paper and its connections. `./relper.sh` opens a fresh Terminal window already sitting in the CLI.

Useful flags: `--no-stream` (print the answer instead of streaming tokens), `--community-level`, `--response-type`, and `--verbose`. Every answer ends with `[Data: Sources (...)]` citations resolving to the `item_id`s it came from.

---

---

## Layout

```
ragproject/             GraphRAG project (settings.yaml, .env, input/, output/, cache/, logs/)
pipeline/dspace/        SMARTECH discovery: base, scan_page, get_all_papers, bitstream_lookup
pipeline/ingest/        Postgres queue + downloads: pdf_db, pdf_downloads, read_text, retry_failed
pipeline/build/         corpus assembly: build_corpus, filter, sample_corpus
pipeline/models/        typed row wrappers (PaperRecord) shared by the queue workers
pipeline/viz/           visualize_graph.py — 3D entity graph from ragproject/output
pipeline/cli/           query_cli.py — interactive graphrag query CLI
config.json             GROBID client + server config
Dockerfile              download worker image
deployment.yaml         4-replica download Deployment
writes/                 catalog JSON, bitstream map, corpus output
downloaded_pdfs/        PDFs, named by item_id
extracted_text/         GROBID TEI output, one file per item_id
```

Postgres holds the queue, the corpus, the vector index, and the graph. PDFs, TEI, and corpus output are gitignored. They are large (16.6 GB) and, more importantly, licensed by their authors — redistribution rights are the repository's, not this project's. Code is committed; data is not.

## Stack

Python 3.12 · Postgres (`psycopg2`) + `pgvector` · Kubernetes · DSpace REST API · GROBID (`grobid-client-python`) · `lxml` / `xml.etree` for TEI · NetworkX for graph traversal and Louvain communities

## Extending

- Extend extraction across the full bitstream set — the download stage already holds 2,519 PDFs and the extraction stage is tuned to run in bounded batches against the GROBID queue.
- Resolve the 40 items carrying multiple PDF bitstreams into per-item subdirectories, so no bitstream is shadowed.
- Grow the graph beyond Georgia Tech to make cross-institution citation edges resolvable.
- Backfill `dc.rights` from license fields (`dc.rights.metadata`, `dc.rights.uri`).

---

## Data source

Content comes from the [Georgia Tech SMARTECH repository](https://repository.gatech.edu/), restricted to the College of Computing. This project redistributes nothing: PDFs and derived text stay local. Only unrestricted, published research is collected — embargoed and access-restricted items are excluded upstream by the repository and are not in this corpus.
