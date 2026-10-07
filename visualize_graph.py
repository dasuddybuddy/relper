import json
import os
import re
from collections import Counter

import pandas as pd

GRAPH_DIR = os.environ.get("GRAPH_DIR", "ragproject/output")
HTML_OUT = os.environ.get("VISUALIZER_OUT", os.path.join(GRAPH_DIR, "graph_visualizer.html"))
VIS_JS = os.environ.get("VIS_JS", "/tmp/3d-force-graph.min.js")
MIN_SHARED = int(os.environ.get("MIN_SHARED", "1"))
MAX_EDGE_CONCEPTS = int(os.environ.get("MAX_EDGE_CONCEPTS", "12"))
LABEL_CONCEPTS = int(os.environ.get("LABEL_CONCEPTS", "1"))
SNIPPET = 600

DROP_TYPES = {
    "UNKNOWN", "SECTION", "FIGURE", "CHARACTER", "TOKEN", "MEDIA",
    "VIDEO EXAMPLE", "IMAGE", "TABLE", "LIST", "PAGE", "EXAMPLE",
}

PALETTE = [
    "#f4a261", "#2a9d8f", "#e76f51", "#8ecae6", "#c77dff", "#90be6d",
    "#ffd166", "#ef476f", "#06d6a0", "#118ab2", "#bc6c25", "#b5179e",
]
OTHER_COLOR = "#6c757d"

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
         background: #0f1115; color: #e6e6e6; overflow: hidden; }
  #graph { position: absolute; inset: 0 380px 0 0; background:
           radial-gradient(#161a22 1px, transparent 1px) 0 0 / 34px 34px, #0f1115; }
  #sidebar { position: absolute; top: 0; right: 0; bottom: 0; width: 380px;
             background: #171a21; border-left: 1px solid #2a2f3a; overflow-y: auto; }
  #settings { padding: 14px 18px; border-bottom: 1px solid #262b36; }
  #settings h1 { font-size: 15px; margin: 0 0 8px; color: #9fb3c8; font-weight: 600; }
  #panel { padding: 14px 18px 24px; }
  #panel h1 { font-size: 15px; margin: 0 0 4px; color: #9fb3c8; font-weight: 600; }
  #panel h2 { font-size: 17px; margin: 8px 0 6px; line-height: 1.35; }
  .hint { color: #6b7686; font-size: 13px; }
  .meta { color: #8b97a8; font-size: 13px; margin: 2px 0; }
  .meta a { color: #6cb6ff; text-decoration: none; }
  .meta a:hover { text-decoration: underline; }
  .abstract { background: #10131a; border: 1px solid #262b36; border-radius: 6px;
              padding: 10px 12px; margin-top: 10px; white-space: pre-wrap; font-size: 13px; }
  .chips { margin-top: 6px; }
  .chip { display: inline-block; background: #232a36; border: 1px solid #333b4a;
          border-radius: 10px; padding: 1px 8px; margin: 2px 3px 0 0; font-size: 12px; }
  .concept { background: #10131a; border: 1px solid #262b36; border-radius: 6px;
             padding: 8px 10px; margin-top: 8px; font-size: 13px; }
  .concept .cname { font-weight: 600; color: #ffd479; }
  .concept .ctype { color: #6cb6ff; font-size: 11px; text-transform: uppercase;
                    letter-spacing: .05em; margin-left: 6px; }
  .concept .cdesc { color: #b9c2cf; margin-top: 3px; }
  .sect { margin-top: 14px; font-size: 12px; color: #8b97a8; text-transform: uppercase;
          letter-spacing: .08em; border-top: 1px solid #262b36; padding-top: 10px; }
  .slider { margin: 8px 0 0; }
  .slider label { display: flex; justify-content: space-between; font-size: 12px; color: #a9b4c2; }
  .slider label b { color: #ffd479; font-weight: 600; }
  .slider input { width: 100%; margin-top: 3px; accent-color: #f4a261; }
  .legend { display: flex; flex-wrap: wrap; gap: 4px 10px; margin-top: 8px; }
  .lg { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #b9c2cf; }
  .sw { width: 11px; height: 11px; border-radius: 50%; display: inline-block; }
</style>
</head>
<body>
<div id="graph"></div>
<div id="sidebar">
  <div id="settings">
    <h1>RELPER — paper graph</h1>
    <div class="slider"><label>Edge length / link distance <b id="v_len">140</b></label>
      <input type="range" id="s_len" min="40" max="500" step="10" value="140"></div>
    <div class="slider"><label>Link strength <b id="v_str">0.20</b></label>
      <input type="range" id="s_str" min="0.01" max="1" step="0.01" value="0.2"></div>
    <div class="slider"><label>Node repulsion <b id="v_rep">-140</b></label>
      <input type="range" id="s_rep" min="-500" max="-20" step="10" value="-140"></div>
    <div class="sect">Node color = dominant entity type</div>
    <div class="legend" id="legend"></div>
  </div>
  <div id="panel">
    <div class="hint">Sphere size = number of connections.<br>
    Click a paper for its summary, authors, and top concepts.<br>
    Click a connection to see what the papers share and why.</div>
  </div>
</div>
<script>__VIS_JS__</script>
<script>
const DATA = __DATA__;
const byId = Object.fromEntries(DATA.nodes.map(n => [n.id, n]));
const esc = s => String(s ?? "").replace(/[&<>"']/g,
  c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

const panel = document.getElementById("panel");
const emptyPanel = panel.innerHTML;
function resetPanel() { panel.innerHTML = emptyPanel; }

function showPaper(n) {
    const authors = n.authors.length
    ? n.authors.map(a => `<span class="chip">${esc(a)}</span>`).join("")
    : `<span class="meta">no authors recorded</span>`;
  const subjects = n.subjects.map(s => `<span class="chip">${esc(s)}</span>`).join("");
  const concepts = n.top_concepts.map(c =>
    `<span class="chip" title="${esc(c.d)}">${esc(c.t)}</span>`).join("");
  const link = n.url
    ? `<div class="meta"><a href="${esc(n.url)}" target="_blank" rel="noopener">${esc(n.handle || "source")}</a> · ${esc(n.date || "")}</div>`
    : "";
  panel.innerHTML = `
    <h1>Paper <span class="sw" style="background:${n.color};vertical-align:middle"></span> ${esc(n.dominant)}</h1>
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

document.getElementById("legend").innerHTML = DATA.legend.map(x =>
  `<span class="lg"><span class="sw" style="background:${x.color}"></span>${esc(x.type)} (${x.count})</span>`
).join("");

let graph = null;

function applySettings() {
  if (!graph) return;
  const len = +document.getElementById("s_len").value;
  const str = +document.getElementById("s_str").value;
  const rep = +document.getElementById("s_rep").value;
  document.getElementById("v_len").textContent = len;
  document.getElementById("v_str").textContent = str.toFixed(2);
  document.getElementById("v_rep").textContent = rep;
  graph.d3Force("link").distance(len).strength(str);
  graph.d3Force("charge").strength(rep);
  graph.resumeAnimation();
}
["s_len", "s_str", "s_rep"].forEach(id =>
  document.getElementById(id).addEventListener("input", applySettings));

try {
  graph = ForceGraph3D({ rendererConfig: { antialias: true } })
    (document.getElementById("graph"))
    .backgroundColor("#0f1115")
    .showNavInfo(false)
    .nodeId("id")
    .nodeVal(n => 1 + n.links * 2.5)
    .nodeColor(n => n.color)
    .nodeLabel(n => `<div style="font:13px/1.45 sans-serif;background:#171a21;color:#e6e6e6;
        padding:8px 10px;border:1px solid #333b4a;border-radius:6px;max-width:340px">
        <b>${esc(n.title)}</b><br><span style="color:#8b97a8">${esc(n.authors.join(", "))}</span>
        <br><span style="color:#ffd479">${n.links} connection${n.links === 1 ? "" : "s"}</span></div>`)
    .linkWidth(l => 0.5 + Math.sqrt(l.count))
    .linkColor(() => "rgba(140,160,190,0.35)")
    .linkLabel(l => `<div style="font:12px/1.4 sans-serif;background:#171a21;color:#e6e6e6;
        padding:6px 9px;border:1px solid #333b4a;border-radius:6px;max-width:300px">
        <b>${l.count} shared concept${l.count === 1 ? "" : "s"}</b><br>${esc(l.label)}</div>`)
    .onNodeClick(n => showPaper(n))
    .onLinkClick(l => showEdge(l))
    .onBackgroundClick(() => resetPanel())
    .graphData({ nodes: DATA.nodes, links: DATA.edges });
  graph.width(window.innerWidth - 380).height(window.innerHeight);
} catch (err) {
  panel.innerHTML = `<div class="hint">3D view unavailable — WebGL could not start
    in this browser.<br>${esc(err)}</div>`;
}

window.addEventListener("resize", () => {
  if (graph) graph.width(window.innerWidth - 380).height(window.innerHeight);
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

    nodes = []
    for d in docs.itertuples():
        raw = d.raw_data or {}
        text = raw.get("text") or d.text or ""
        abstract = (raw.get("abstract") or "").strip()
        summary = abstract if len(abstract) >= 60 else text.strip()[:SNIPPET] + "…"
        own = sorted(doc_entities.get(d.id, ()),
                     key=lambda e: meta[e]["r"], reverse=True)
        weights: Counter = Counter()
        for e in own:
            weights[meta[e]["ty"]] += meta[e]["r"]
        dominant = weights.most_common(1)[0][0] if weights else "UNKNOWN"
        nodes.append({
            "id": d.id,
            "title": raw.get("title") or d.title,
            "authors": parse_authors(raw.get("authors", "")),
            "date": raw.get("date", ""),
            "subjects": [s.strip() for s in (raw.get("subject") or "").split(";") if s.strip()],
            "handle": raw.get("handle_id", ""),
            "url": raw.get("source_url", ""),
            "summary": summary,
            "dominant": dominant,
            "top_concepts": [{"t": meta[e]["t"], "ty": meta[e]["ty"], "d": meta[e]["d"]}
                             for e in own[:12]],
            "link_ids": own,
            "links": 0,
        })

    counts = Counter(n["dominant"] for n in nodes)
    palette = {}
    for i, (t, _) in enumerate(counts.most_common()):
        palette[t] = PALETTE[i] if i < len(PALETTE) else OTHER_COLOR
    legend = [{"type": t, "color": palette[t], "count": c}
              for t, c in counts.most_common()]
    for n in nodes:
        n["color"] = palette[n["dominant"]]

    ids = [n["id"] for n in nodes]
    sets = {n["id"]: set(n.pop("link_ids")) for n in nodes}
    index = {n["id"]: n for n in nodes}
    edges = []
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
                "source": a, "target": b,
                "count": len(shared), "label": label[:60],
                "concepts": [meta[e] for e in top],
            })
            edge_n += 1
            index[a]["links"] += 1
            index[b]["links"] += 1

    return {"nodes": nodes, "edges": edges, "legend": legend}


def main():
    data = build()
    vis = open(VIS_JS, encoding="utf-8").read()
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    html = PAPER_HTML.replace("__VIS_JS__", vis).replace("__DATA__", payload)
    with open(HTML_OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"{len(data['nodes'])} papers, {len(data['edges'])} connections, "
          f"{len(data['legend'])} colors -> {HTML_OUT}")


if __name__ == "__main__":
    main()
