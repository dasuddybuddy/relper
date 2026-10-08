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
  #ring { position: absolute; display: none; border: 2.5px solid #ffffff;
          border-radius: 50%; pointer-events: none; z-index: 5;
          box-shadow: 0 0 14px rgba(255,255,255,.65), inset 0 0 8px rgba(255,255,255,.35); }
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
  #search { width: 100%; margin-top: 8px; padding: 7px 10px; background: #10131a;
            border: 1px solid #333b4a; border-radius: 6px; color: #e6e6e6; font-size: 13px; }
  #search:focus { outline: none; border-color: #f4a261; }
  #search::placeholder { color: #6b7686; }
  .status { margin-top: 6px; font-size: 12px; color: #8b97a8; }
  .btn { display: block; width: 100%; margin-top: 8px; padding: 7px 10px; background: #232a36;
         border: 1px solid #333b4a; border-radius: 6px; color: #e6e6e6; cursor: pointer;
         font: 600 13px/1.3 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
  .btn:hover { background: #2c3546; border-color: #f4a261; color: #ffd479; }
  .results { margin-top: 6px; }
  .res { display: block; width: 100%; text-align: left; padding: 7px 10px; margin-top: 4px;
         background: #10131a; border: 1px solid #333b4a; border-radius: 6px;
         color: #e6e6e6; cursor: pointer;
         font: 13px/1.35 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
  .res:first-child { margin-top: 0; }
  .res:hover, .res.active { background: #1b2130; border-color: #f4a261; }
  .res .rt { display: block; font-weight: 600; }
  .res .ra { display: block; color: #8b97a8; font-size: 11.5px; margin-top: 2px; }
  .res mark { background: transparent; color: #ffd479; }
  .res_more { padding: 6px 2px 0; font-size: 12px; color: #6b7686; }
  .legend { display: flex; flex-wrap: wrap; gap: 4px 10px; margin-top: 8px; }
  .lg { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #b9c2cf; }
  .sw { width: 11px; height: 11px; border-radius: 50%; display: inline-block; }
</style>
</head>
<body>
<div id="graph"><div id="ring"></div></div>
<div id="sidebar">
  <div id="settings">
    <h1>RELPER — paper graph</h1>
    <input id="search" type="search" placeholder="Search papers by title or author…"
           autocomplete="off" spellcheck="false">
    <div class="results" id="results"></div>
    <div class="status" id="search_status"></div>
    <button class="btn" id="clear_view" style="display:none">Show all papers</button>
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
    Search above for a paper — pick a suggestion to jump to its node.<br>
    Click a paper for its summary, authors, and top concepts —
    use <b>Isolate</b> to show only that paper and its connections.<br>
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
  const isoBtn = `<button class="btn" id="iso_btn">${
    isolateId === n.id ? "Show all papers" : "Isolate this paper & its connections"}</button>`;
  panel.innerHTML = `
    <h1>Paper <span class="sw" style="background:${n.color};vertical-align:middle"></span> ${esc(n.dominant)}</h1>
    <h2>${esc(n.title)}</h2>
    ${isoBtn}
    <div class="meta"><b>Authors:</b></div><div class="chips">${authors}</div>
    ${link}
    ${n.subjects.length ? `<div class="sect">Subjects</div><div class="chips">${subjects}</div>` : ""}
    <div class="sect">Summary</div>
    <div class="abstract">${esc(n.summary)}</div>
    <div class="sect">Top concepts in this paper (${n.top_concepts.length})</div>
    <div class="chips">${concepts}</div>
    <div class="sect">Connections</div>
    <div class="meta">${n.links} paper${n.links === 1 ? "" : "s"} in the corpus share concepts with this one.</div>`;
  document.getElementById("iso_btn").addEventListener("click", () => {
    isolateId = isolateId === n.id ? null : n.id;
    applyView();
    showPaper(n);
  });
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

let isolateId = null;
let searchQ = "";

function matchesQuery(n, q) {
  return n.title.toLowerCase().includes(q)
    || n.authors.some(a => a.toLowerCase().includes(q));
}

function viewData() {
  let nodes;
  if (isolateId !== null) {
    const keep = new Set([isolateId]);
    for (const l of DATA.edges)
      if (l.from === isolateId) keep.add(l.to);
      else if (l.to === isolateId) keep.add(l.from);
    nodes = DATA.nodes.filter(n => keep.has(n.id));
  } else {
    const q = searchQ.trim().toLowerCase();
    nodes = q ? DATA.nodes.filter(n => matchesQuery(n, q)) : DATA.nodes;
  }
  const vis = new Set(nodes.map(n => n.id));
  return { nodes, links: DATA.edges.filter(l => vis.has(l.from) && vis.has(l.to)) };
}

function updateStatus(shown) {
  const status = document.getElementById("search_status");
  const clear = document.getElementById("clear_view");
  if (isolateId !== null) {
    status.textContent = `Isolated — showing ${shown} paper${shown === 1 ? "" : "s"}`;
    clear.style.display = "block";
  } else if (searchQ.trim()) {
    status.textContent = shown
      ? `${shown} match${shown === 1 ? "" : "es"}`
      : "no matching papers";
    clear.style.display = "block";
  } else {
    status.textContent = `${shown} papers`;
    clear.style.display = "none";
  }
}

function applyView() {
  if (!graph) return;
  const v = viewData();
  const vis = new Set(v.nodes.map(n => n.id));
  if (selectedId !== null && !vis.has(selectedId)) {
    selectedId = null;
    ring.style.display = "none";
  }
  graph.graphData({ nodes: v.nodes, links: v.links });
  updateStatus(v.nodes.length);
}

document.getElementById("legend").innerHTML = DATA.legend.map(x =>
  `<span class="lg"><span class="sw" style="background:${x.color}"></span>${esc(x.type)} (${x.count})</span>`
).join("");

let graph = null;
let selectedId = null;
const ring = document.getElementById("ring");

function activeLink(l) {
  return selectedId !== null && (l.from === selectedId || l.to === selectedId);
}

function applyHighlight() {
  if (!graph) return;
  graph.linkColor(l => activeLink(l) ? "rgba(255,236,170,1)" : "rgba(140,160,190,0.14)")
    .linkWidth(l => activeLink(l) ? 2.5 + Math.sqrt(l.count) : 0.5 + Math.sqrt(l.count));
  graph.graphData(graph.graphData());
  if (selectedId === null) ring.style.display = "none";
}

function selectNode(n) {
  selectedId = n.id;
  applyHighlight();
  showPaper(n);
}

function clearSelection() {
  if (selectedId === null) return;
  selectedId = null;
  applyHighlight();
}

function project(x, y, z) {
  const cam = graph.camera();
  const v = cam.matrixWorldInverse.elements, p = cam.projectionMatrix.elements;
  const vx = v[0] * x + v[4] * y + v[8] * z + v[12];
  const vy = v[1] * x + v[5] * y + v[9] * z + v[13];
  const vz = v[2] * x + v[6] * y + v[10] * z + v[14];
  const vw = v[3] * x + v[7] * y + v[11] * z + v[15];
  const cx = p[0] * vx + p[4] * vy + p[8] * vz + p[12] * vw;
  const cy = p[1] * vx + p[5] * vy + p[9] * vz + p[13] * vw;
  const cw = p[3] * vx + p[7] * vy + p[11] * vz + p[15] * vw;
  const box = document.getElementById("graph");
  return {
    x: (cx / cw * 0.5 + 0.5) * box.clientWidth,
    y: (-cy / cw * 0.5 + 0.5) * box.clientHeight,
    ok: cw > 0,
  };
}

function trackRing() {
  if (graph && selectedId !== null) {
    const n = graph.graphData().nodes.find(x => x.id === selectedId);
    const o = n && n.__threeObj;
    if (n && o && Number.isFinite(n.x)) {
      const r = (o.geometry.parameters.radius || 1) * o.scale.x;
      const m = graph.camera().matrixWorld.elements;
      const s1 = project(n.x, n.y, n.z);
      const s2 = project(n.x + r * m[0], n.y + r * m[1], n.z + r * m[2]);
      const d = Math.hypot(s2.x - s1.x, s2.y - s1.y) * 2;
      if (s1.ok && d > 2 && d < 4000) {
        ring.style.display = "block";
        ring.style.width = d + "px";
        ring.style.height = d + "px";
        ring.style.left = (s1.x - d / 2) + "px";
        ring.style.top = (s1.y - d / 2) + "px";
      } else {
        ring.style.display = "none";
      }
    }
  }
}
function ringLoop() { trackRing(); requestAnimationFrame(ringLoop); }
requestAnimationFrame(ringLoop);
setInterval(trackRing, 50);


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
  graph.d3ReheatSimulation();
  graph.resumeAnimation();
}
["s_len", "s_str", "s_rep"].forEach(id =>
  document.getElementById(id).addEventListener("input", applySettings));

try {
  graph = ForceGraph3D({ rendererConfig: { antialias: true } })
    (document.getElementById("graph"))
    .backgroundColor("#0f1115")
    .showNavInfo(false)
    .d3VelocityDecay(0.95)
    .d3AlphaDecay(0.06)
    .d3AlphaMin(0.001)
    .nodeId("id")
    .nodeVal(n => 1 + n.links * 2.5)
    .nodeColor(n => n.color)
    .nodeLabel(n => `<div style="font:13px/1.45 sans-serif;background:#171a21;color:#e6e6e6;
        padding:8px 10px;border:1px solid #333b4a;border-radius:6px;max-width:340px">
        <b>${esc(n.title)}</b><br><span style="color:#8b97a8">${esc(n.authors.join(", "))}</span>
        <br><span style="color:#ffd479">${n.links} connection${n.links === 1 ? "" : "s"}</span></div>`)
    .linkWidth(l => activeLink(l) ? 2.5 + Math.sqrt(l.count) : 0.5 + Math.sqrt(l.count))
    .linkColor(l => activeLink(l) ? "rgba(255,236,170,1)" : "rgba(140,160,190,0.14)")
    .linkOpacity(1)
    .linkLabel(l => `<div style="font:12px/1.4 sans-serif;background:#171a21;color:#e6e6e6;
        padding:6px 9px;border:1px solid #333b4a;border-radius:6px;max-width:300px">
        <b>${l.count} shared concept${l.count === 1 ? "" : "s"}</b><br>${esc(l.label)}</div>`)
    .onNodeClick(n => selectNode(n))
    .onLinkClick(l => showEdge(l))
    .onBackgroundClick(() => { clearSelection(); resetPanel(); })
    .graphData({ nodes: DATA.nodes, links: DATA.edges });
  graph.width(window.innerWidth - 380).height(window.innerHeight);
  const ctrl = graph.controls();
  ctrl.zoomSpeed = 3;
  ctrl.enableDamping = false;
  ctrl.maxDistance = Infinity;
} catch (err) {
  panel.innerHTML = `<div class="hint">3D view unavailable — WebGL could not start
    in this browser.<br>${esc(err)}</div>`;
}

window.addEventListener("resize", () => {
  if (graph) graph.width(window.innerWidth - 380).height(window.innerHeight);
});

const searchInput = document.getElementById("search");
const resultsBox = document.getElementById("results");
let suggestions = [];
let activeIdx = -1;

function hl(text, q) {
  const i = (text || "").toLowerCase().indexOf(q);
  if (i < 0) return esc(text);
  return esc(text.slice(0, i)) + "<mark>" + esc(text.slice(i, i + q.length))
    + "</mark>" + esc(text.slice(i + q.length));
}

function matchScore(n, q) {
  const t = n.title.toLowerCase();
  if (t.startsWith(q)) return 0;
  if (t.includes(q)) return 1;
  if (n.authors.some(a => a.toLowerCase().startsWith(q))) return 2;
  return 3;
}

function renderResults() {
  const q = searchQ.trim().toLowerCase();
  if (!q) {
    resultsBox.innerHTML = "";
    suggestions = [];
    activeIdx = -1;
    return;
  }
  const hits = DATA.nodes.filter(n => matchesQuery(n, q))
    .sort((a, b) => matchScore(a, q) - matchScore(b, q));
  suggestions = hits.slice(0, 8);
  activeIdx = suggestions.length ? 0 : -1;
  const more = hits.length - suggestions.length;
  resultsBox.innerHTML = suggestions.length
    ? suggestions.map((n, i) => `
      <button class="res${i === activeIdx ? " active" : ""}" data-i="${i}">
        <span class="rt">${hl(n.title, q)}</span>
        <span class="ra">${esc(n.authors.join(", "))}</span>
      </button>`).join("")
      + (more > 0 ? `<div class="res_more">+${more} more — keep typing</div>` : "")
    : `<div class="res_more">no matching papers</div>`;
}

function setActive(i) {
  activeIdx = i;
  [...resultsBox.querySelectorAll(".res")].forEach((el, k) =>
    el.classList.toggle("active", k === i));
  const el = resultsBox.querySelector(".res.active");
  if (el) el.scrollIntoView({ block: "nearest" });
}

function focusNode(n) {
  if (!graph || !Number.isFinite(n.x)) return;
  let radius = 300;
  const bb = graph.getGraphBbox();
  if (bb) {
    radius = Math.max(
      Math.abs(bb.x[0]), Math.abs(bb.x[1]),
      Math.abs(bb.y[0]), Math.abs(bb.y[1]),
      Math.abs(bb.z[0]), Math.abs(bb.z[1]), 1);
  }
  const dist = Math.max(radius * 1.3, 200);
  const norm = Math.hypot(n.x, n.y, n.z) || 1;
  const ratio = dist / norm;
  graph.cameraPosition(
    { x: n.x * ratio, y: n.y * ratio, z: n.z * ratio },
    n, 1200);
}

function pickSuggestion(i) {
  const n = suggestions[i];
  if (!n) return;
  searchInput.value = "";
  searchQ = "";
  isolateId = null;
  resultsBox.innerHTML = "";
  suggestions = [];
  activeIdx = -1;
  applyView();
  selectNode(n);
  focusNode(n);
}

searchInput.addEventListener("input", () => {
  searchQ = searchInput.value;
  isolateId = null;
  applyView();
  renderResults();
  if (selectedId !== null) {
    const n = byId[selectedId];
    if (n) showPaper(n);
  }
});
searchInput.addEventListener("keydown", e => {
  if (e.key === "ArrowDown" && suggestions.length) {
    e.preventDefault();
    setActive((activeIdx + 1) % suggestions.length);
  } else if (e.key === "ArrowUp" && suggestions.length) {
    e.preventDefault();
    setActive((activeIdx - 1 + suggestions.length) % suggestions.length);
  } else if (e.key === "Enter" && suggestions.length) {
    e.preventDefault();
    pickSuggestion(activeIdx < 0 ? 0 : activeIdx);
  } else if (e.key === "Escape") {
    searchInput.value = "";
    searchQ = "";
    applyView();
    renderResults();
  }
});
resultsBox.addEventListener("mousedown", e => {
  const b = e.target.closest(".res");
  if (b) {
    e.preventDefault();
    pickSuggestion(+b.dataset.i);
  }
});
searchInput.addEventListener("blur", () => {
  setTimeout(() => {
    resultsBox.innerHTML = "";
    suggestions = [];
    activeIdx = -1;
  }, 150);
});
document.getElementById("clear_view").addEventListener("click", () => {
  isolateId = null;
  searchQ = "";
  searchInput.value = "";
  resultsBox.innerHTML = "";
  suggestions = [];
  applyView();
});
updateStatus(DATA.nodes.length);
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
