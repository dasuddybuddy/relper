import json
import os
import re

import pandas as pd

GRAPH_DIR = os.environ.get("GRAPH_DIR", "ragproject/output")
HTML_OUT = os.environ.get("VISUALIZER_OUT", os.path.join(GRAPH_DIR, "graph_visualizer.html"))
VIS_JS = os.environ.get("VIS_JS", "/tmp/vis-network.min.js")
MIN_SHARED = int(os.environ.get("MIN_SHARED", "1"))
MAX_EDGE_CONCEPTS = int(os.environ.get("MAX_EDGE_CONCEPTS", "12"))
LABEL_CONCEPTS = int(os.environ.get("LABEL_CONCEPTS", "1"))
SNIPPET = 600

DROP_TYPES = {
    "UNKNOWN", "SECTION", "FIGURE", "CHARACTER", "TOKEN", "MEDIA",
    "VIDEO EXAMPLE", "IMAGE", "TABLE", "LIST", "PAGE", "EXAMPLE",
}

JUNK_TITLE = re.compile(
    r"^(?:\d+|[A-Z]|[A-Z]+(?:\s+\d+){1,2}|"
    r"(?:ALGORITHM|THEOREM|LEMMA|COROLLARY|PROPOSITION|DEFINITION|EQUATION|"
    r"FORMULA|SECTION|CHAPTER|TABLE|FIGURE|LIST|STEP|CASE|PART|LEVEL)\s*\d*)$"
)


def is_useful(e) -> bool:
    title = e.title.strip()
    return (
        len(title) >= 3
        and not JUNK_TITLE.match(title.upper())
        and len(e.description or "") >= 40
        and "corrupted" not in (e.description or "").lower()
        and "nonsensical" not in (e.description or "").lower()
    )

PAPER_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>RELPER — paper graph</title>
<style>
  * { box-sizing: border-box; }
  body { margin: 0; font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         background: #0f1115; color: #e6e6e6; }
  #graph { position: absolute; inset: 0 380px 0 0; }
  #panel { position: absolute; top: 0; right: 0; bottom: 0; width: 380px;
           background: #171a21; border-left: 1px solid #2a2f3a; overflow-y: auto; padding: 18px; }
  #panel h1 { font-size: 15px; margin: 0 0 4px; color: #9fb3c8; font-weight: 600; }
  #panel .hint { color: #6b7686; font-size: 13px; }
  #panel h2 { font-size: 17px; margin: 10px 0 6px; line-height: 1.35; }
  .meta { color: #8b97a8; font-size: 13px; margin: 2px 0; }
  .meta a { color: #6cb6ff; text-decoration: none; }
  .meta a:hover { text-decoration: underline; }
  .abstract { background: #10131a; border: 1px solid #262b36; border-radius: 6px;
              padding: 10px 12px; margin-top: 10px; white-space: pre-wrap; font-size: 13px; }
  .chips { margin-top: 8px; }
  .chip { display: inline-block; background: #232a36; border: 1px solid #333b4a;
          border-radius: 10px; padding: 1px 8px; margin: 2px 3px 0 0; font-size: 12px; }
  .concept { background: #10131a; border: 1px solid #262b36; border-radius: 6px;
             padding: 8px 10px; margin-top: 8px; font-size: 13px; }
  .concept .cname { font-weight: 600; color: #ffd479; }
  .concept .ctype { color: #6cb6ff; font-size: 11px; text-transform: uppercase;
                    letter-spacing: .05em; margin-left: 6px; }
  .concept .cdesc { color: #b9c2cf; margin-top: 3px; }
  .sect { margin-top: 16px; font-size: 12px; color: #8b97a8; text-transform: uppercase;
          letter-spacing: .08em; border-top: 1px solid #262b36; padding-top: 10px; }
  .badge { display: inline-block; background: #1c3a5e; color: #9fd0ff; border-radius: 4px;
           padding: 0 6px; font-size: 12px; margin-left: 6px; }
</style>
</head>
<body>
<div id="graph"></div>
<div id="panel">
  <h1>RELPER paper graph</h1>
  <div class="hint">Click a paper for its summary, authors, and top concepts.<br>
  Click a connection to see what the papers share and why.<br>
  Drag to rearrange, scroll to zoom, drag the background to pan.</div>
</div>
<script>__VIS_JS__</script>
<script>
const DATA = __DATA__;
const byId = Object.fromEntries(DATA.nodes.map(n => [n.id, n]));
const edgeById = Object.fromEntries(DATA.edges.map(e => [e.id, e]));
const esc = s => String(s ?? "").replace(/[&<>"']/g,
  c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

const nodes = new vis.DataSet(DATA.nodes.map(n => ({
  id: n.id, label: n.label, title: n.title,
  value: n.links, color: { background: "#1f6feb", border: "#8ec2ff",
    highlight: { background: "#388bfd", border: "#ffffff" } },
  font: { color: "#e6edf3", size: 13 }, borderWidth: 1,
})));
const edges = new vis.DataSet(DATA.edges.map(e => ({
  id: e.id, from: e.from, to: e.to, label: e.label, value: e.count,
  title: e.count + " shared concepts",
  font: { color: "#9fb3c8", size: 11, strokeWidth: 3, strokeColor: "#0f1115" },
  color: { color: "#4b5563", highlight: "#ffd479" },
  smooth: { type: "continuous" },
})));

const net = new vis.Network(document.getElementById("graph"),
  { nodes, edges },
  { nodes: { scaling: { min: 18, max: 46 } },
    edges: { scaling: { min: 1, max: 8 }, selectionWidth: 2 },
    physics: { barnesHut: { gravitationalConstant: -3200, springLength: 170 },
               stabilization: { iterations: 300 } },
    interaction: { hover: true, tooltipDelay: 120 } });

const panel = document.getElementById("panel");
const emptyPanel = panel.innerHTML;

function showPaper(n) {
  const authors = n.authors.length
    ? n.authors.map(a => `<span class="chip">${esc(a)}</span>`).join("")
    : `<span class="meta">no authors recorded</span>`;
  const subjects = n.subjects.map(s => `<span class="chip">${esc(s)}</span>`).join("");
  const concepts = n.top_concepts.map(c =>
    `<span class="chip" title="${esc(c.d)}">${esc(c.t)}</span>`).join("");
  const link = n.url ? `<div class="meta"><a href="${esc(n.url)}" target="_blank" rel="noopener">${esc(n.handle || "source")}</a> · ${esc(n.date || "")}</div>` : "";
  panel.innerHTML = `
    <h1>Paper</h1>
    <h2>${esc(n.title)}</h2>
    <div class="meta"><b>Authors:</b></div><div class="chips">${authors}</div>
    ${link}
    ${n.subjects.length ? `<div class="sect">Subjects</div><div class="chips">${subjects}</div>` : ""}
    <div class="sect">Summary</div>
    <div class="abstract">${esc(n.summary)}</div>
    <div class="sect">Top concepts in this paper (${n.top_concepts.length})</div>
    <div class="chips">${concepts}</div>
    <div class="sect">Connections</div>
    <div class="meta">${n.links} paper${n.links === 1 ? "" : "s"} in the corpus share concepts with this one.</div>`;
}

function showEdge(e) {
  const items = e.concepts.map(c => `
    <div class="concept">
      <span class="cname">${esc(c.t)}</span><span class="ctype">${esc(c.ty)}</span>
      <div class="cdesc">${esc(c.d)}</div>
    </div>`).join("");
  panel.innerHTML = `
    <h1>Connection</h1>
    <h2>${esc(byId[e.from].title)}</h2>
    <div class="meta" style="text-align:center">↓ shares ${e.count} concept${e.count === 1 ? "" : "s"} with ↓</div>
    <h2>${esc(byId[e.to].title)}</h2>
    <div class="sect">Connected by — shared concepts</div>
    ${items}
    ${e.concepts.length < e.count ? `<div class="meta">+ ${e.count - e.concepts.length} more</div>` : ""}`;
}

net.on("click", p => {
  if (p.nodes.length) showPaper(byId[p.nodes[0]]);
  else if (p.edges.length) showEdge(edgeById[p.edges[0]]);
  else panel.innerHTML = emptyPanel;
});
</script>
</body>
</html>
"""


def parse_authors(raw: str) -> list[str]:
    out = []
    for part in re.split(r"\s*;\s*", raw or ""):
        part = part.strip()
        if not part:
            continue
        if "," in part:
            last, _, first = part.partition(",")
            part = f"{first.strip()} {last.strip()}".strip()
        out.append(part)
    return out


def build():
    docs = pd.read_parquet(os.path.join(GRAPH_DIR, "documents.parquet"))
    ents = pd.read_parquet(os.path.join(GRAPH_DIR, "entities.parquet"))
    units = pd.read_parquet(os.path.join(GRAPH_DIR, "text_units.parquet"))

    ents = ents[~ents.type.str.upper().isin(DROP_TYPES)]
    ents = ents[ents.apply(is_useful, axis=1)]
    meta = {
        r.id: {"t": r.title, "ty": r.type, "d": r.description, "r": int(r.degree)}
        for r in ents.itertuples()
    }

    doc_entities: dict[str, set[str]] = {}
    for r in units.itertuples():
        doc_entities.setdefault(r.document_id, set()).update(
            e for e in r.entity_ids if e in meta
        )

    nodes, edges = [], []
    for d in docs.itertuples():
        raw = d.raw_data or {}
        text = raw.get("text") or d.text or ""
        abstract = (raw.get("abstract") or "").strip()
        summary = abstract if len(abstract) >= 60 else text.strip()[:SNIPPET] + "…"
        own = sorted(doc_entities.get(d.id, ()),
                     key=lambda e: meta[e]["r"], reverse=True)
        nodes.append({
            "id": d.id,
            "title": raw.get("title") or d.title,
            "label": (raw.get("title") or d.title)[:60],
            "authors": parse_authors(raw.get("authors", "")),
            "date": raw.get("date", ""),
            "subjects": [s.strip() for s in (raw.get("subject") or "").split(";") if s.strip()],
            "handle": raw.get("handle_id", ""),
            "url": raw.get("source_url", ""),
            "summary": summary,
            "top_concepts": [{"t": meta[e]["t"], "ty": meta[e]["ty"], "d": meta[e]["d"]}
                             for e in own[:12]],
            "link_ids": own,
            "links": 0,
        })

    ids = [n["id"] for n in nodes]
    sets = {n["id"]: set(n.pop("link_ids")) for n in nodes}
    index = {n["id"]: n for n in nodes}
    edge_n = 0
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            shared = sorted(sets[a] & sets[b], key=lambda e: meta[e]["r"], reverse=True)
            if len(shared) < MIN_SHARED:
                continue
            top = shared[:MAX_EDGE_CONCEPTS]
            label = " + ".join(meta[e]["t"][:24] for e in shared[:LABEL_CONCEPTS])
            if len(shared) > LABEL_CONCEPTS:
                label += f" +{len(shared) - LABEL_CONCEPTS}"
            edges.append({
                "id": f"e{edge_n}", "from": a, "to": b,
                "count": len(shared), "label": label[:60],
                "concepts": [meta[e] for e in top],
            })
            edge_n += 1
            index[a]["links"] += 1
            index[b]["links"] += 1

    return {"nodes": nodes, "edges": edges}


def main():
    data = build()
    vis = open(VIS_JS, encoding="utf-8").read()
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    html = PAPER_HTML.replace("__VIS_JS__", vis).replace("__DATA__", payload)
    with open(HTML_OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"{len(data['nodes'])} papers, {len(data['edges'])} connections -> {HTML_OUT}")


if __name__ == "__main__":
    main()
