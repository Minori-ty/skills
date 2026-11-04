#!/usr/bin/env python3
"""Parse a Figma URL into fileKey, nodeId, branchKey and fileType.

Usage:
    python figma_url.py "https://www.figma.com/design/<key>/<name>?node-id=0-1"
    python figma_url.py "<url>" --json

Only the Python standard library is required.
"""

from __future__ import annotations

import argparse
import json
import sys
from urllib.parse import parse_qs, unquote, urlparse


def parse_figma_url(url: str) -> dict:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if "figma.com" not in host:
        raise ValueError(f"Not a figma.com URL: {url}")

    parts = [p for p in parsed.path.split("/") if p]
    if not parts:
        raise ValueError(f"No path in URL: {url}")

    kind = parts[0].lower()
    file_key = None
    root_file_key = None
    branch_key = None
    file_type = None

    if kind in ("design", "file", "proto"):
        if len(parts) < 2:
            raise ValueError("Missing file key")
        file_key = parts[1]
        root_file_key = file_key
        file_type = "design"
        # Support both:
        #   /design/:fileKey/branch/:branchKey/:name
        #   /design/:fileKey/:fileName/branch/:branchKey/:name
        lower_parts = [part.lower() for part in parts]
        if "branch" in lower_parts[2:]:
            branch_index = lower_parts.index("branch", 2)
            if branch_index + 1 < len(parts):
                branch_key = parts[branch_index + 1]
                file_key = branch_key
    elif kind == "board":
        if len(parts) < 2:
            raise ValueError("Missing file key")
        file_key = root_file_key = parts[1]
        file_type = "figjam"
    elif kind == "slides":
        if len(parts) < 2:
            raise ValueError("Missing file key")
        file_key = root_file_key = parts[1]
        file_type = "slides"
    elif kind == "make":
        if len(parts) < 2:
            raise ValueError("Missing make file key")
        file_key = root_file_key = parts[1]
        file_type = "make"
    else:
        raise ValueError(
            f"Unsupported Figma URL path '{kind}'. "
            "Expected design, file, board, slides, make or proto."
        )

    query = parse_qs(parsed.query)
    node_id = query.get("node-id", [None])[0]
    if node_id:
        # URL uses 0-1; MCP expects 0:1.
        node_id = unquote(node_id).replace("-", ":")

    return {
        "fileKey": file_key,
        "rootFileKey": root_file_key,
        "branchKey": branch_key,
        "nodeId": node_id,
        "fileType": file_type,
        "url": url,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse a Figma URL")
    parser.add_argument("url", help="Figma share URL")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print compact JSON instead of a table",
    )
    args = parser.parse_args()

    try:
        result = parse_figma_url(args.url)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
        return 0

    for key in ("fileKey", "rootFileKey", "branchKey", "nodeId", "fileType"):
        print(f"{key}: {result[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
