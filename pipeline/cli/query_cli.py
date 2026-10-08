"""CLI wrapper around graphrag query search.

One-shot:
    python query_cli.py kw=basic What is the relationship with paper x, y, z
    python query_cli.py local "Which papers address stochastic optimal control?"
    python query_cli.py --root ./ragproject global "What themes dominate the corpus?"

Interactive (no arguments): opens a REPL — type
    kw=basic <prompt>      or   basic <prompt>
or just a bare prompt (defaults to basic); visualize opens the graph;
exit/quit/Ctrl-D to leave.
"""

import argparse
import sys
import webbrowser
from pathlib import Path

from graphrag.cli.query import (
    run_basic_search,
    run_drift_search,
    run_global_search,
    run_local_search,
)

METHODS = ("basic", "local", "global", "drift")

BANNER = f"""\
RELPER — graphrag query CLI
  kw=<{'|'.join(METHODS)}> <prompt>      (kw= prefix optional, defaults to basic)
  visualize                  open the 3D entity graph in your browser
  exit / Ctrl-D to quit"""

USAGE = (
    "query_cli.py [--root DIR] [--data DIR] [--no-stream] "
    "kw=<basic|local|global|drift> <prompt>\n"
    "       query_cli.py [...] [<basic|local|global|drift>] <prompt>   (default: basic)"
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="query_cli.py",
        description="Run a graphrag query (basic, local, global, or drift search).",
        usage=USAGE,
    )
    parser.add_argument("--root", default="ragproject", help="graphrag project root (default: ragproject)")
    parser.add_argument("-d", "--data", default=None, help="index output directory override")
    parser.add_argument("--community-level", type=int, default=2)
    parser.add_argument("--response-type", default="Multiple Paragraphs")
    parser.add_argument("--dynamic-community-selection", action="store_true")
    parser.add_argument("--stream", dest="stream", action="store_true", default=True)
    parser.add_argument("--no-stream", dest="stream", action="store_false")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("words", nargs="*", metavar="kw=<method>|<method> <prompt>")
    args = parser.parse_args(argv)
    args.root = str(Path(args.root).resolve())
    if args.data:
        args.data = str(Path(args.data).resolve())
    return args


def split_method(words: list[str]) -> tuple[str, str]:
    first = words[0]
    if first.lower().startswith("kw="):
        method = first[3:].strip().lower()
        prompt_words = words[1:]
    elif first.lower().rstrip(":") in METHODS:
        method = first.lower().rstrip(":")
        prompt_words = words[1:]
    else:
        method = "basic"
        prompt_words = words

    if method not in METHODS:
        print(f"error: unknown search method '{method}'", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        raise SystemExit(2)

    prompt = " ".join(prompt_words).strip()
    if not prompt:
        print("error: empty prompt", file=sys.stderr)
        raise SystemExit(2)
    return method, prompt


def run_search(args: argparse.Namespace, method: str, prompt: str) -> None:
    common = {
        "data_dir": Path(args.data) if args.data else None,
        "root_dir": Path(args.root),
        "response_type": args.response_type,
        "streaming": args.stream,
        "query": prompt,
        "verbose": args.verbose,
    }

    print(f"[{method}] {prompt}\n", file=sys.stderr)

    if method == "basic":
        run_basic_search(**common)
    elif method == "local":
        run_local_search(community_level=args.community_level, **common)
    elif method == "global":
        run_global_search(
            community_level=args.community_level,
            dynamic_community_selection=args.dynamic_community_selection,
            **common,
        )
    else:  # drift
        run_drift_search(community_level=args.community_level, **common)


def open_viz(args: argparse.Namespace) -> int:
    html = Path(args.data if args.data else Path(args.root) / "output") / "graph_visualizer.html"
    if not html.is_file():
        print(f"error: no visualization at {html}", file=sys.stderr)
        print("build one first: python pipeline/viz/visualize_graph.py", file=sys.stderr)
        return 1
    webbrowser.open(html.resolve().as_uri())
    print(f"[visualize] opening {html}")
    return 0


def interactive(args: argparse.Namespace) -> int:
    print(BANNER)
    while True:
        try:
            line = input("kw= ")
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        line = line.strip()
        if not line:
            continue
        if line.lower() in ("exit", "quit", "q"):
            return 0
        if line.lower() == "visualize":
            open_viz(args)
            continue
        try:
            method, prompt = split_method(line.split())
        except SystemExit:
            continue
        try:
            run_search(args, method, prompt)
        except Exception as err:  # noqa: BLE001 — keep the loop alive
            print(f"error: {err}\n", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    if args.words:
        if len(args.words) == 1 and args.words[0].lower() == "visualize":
            return open_viz(args)
        method, prompt = split_method(args.words)
        run_search(args, method, prompt)
    else:
        return interactive(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
