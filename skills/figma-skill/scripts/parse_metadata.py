#!/usr/bin/env python3
"""Parse a saved Figma MCP metadata result and print a compact node tree.

The result may be raw JSON, an MCP content wrapper, XML, or a text blob.
Only the Python standard library is required.

Usage:
    python parse_metadata.py result.json
    python parse_metadata.py result.txt --max-depth 3
    python parse_metadata.py result.txt --type FRAME,COMPONENT
    python parse_metadata.py result.txt --id 1:2 --json
    python parse_metadata.py result.txt --count
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from typing import Any


def parse_text_blob(text: str) -> list[Any]:
    text = text.strip()
    if not text:
        return []

    try:
        return [json.loads(text)]
    except json.JSONDecodeError:
        pass

    # Concatenated JSON values (one per line or back-to-back).
    values: list[Any] = []
    decoder = json.JSONDecoder()
    index = 0
    while index < len(text):
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            break
        try:
            value, end = decoder.raw_decode(text, index)
        except json.JSONDecodeError:
            break
        values.append(value)
        index = end
    if values:
        return values

    try:
        return [ET.fromstring(text)]
    except ET.ParseError:
        return [text]


def unwrap(value: Any, depth: int = 0) -> list[Any]:
    """Unwrap MCP content wrappers and text blobs into node roots."""
    if depth > 8:
        return [value]
    if isinstance(value, ET.Element):
        return [value]
    if isinstance(value, str):
        parsed = parse_text_blob(value)
        out: list[Any] = []
        for item in parsed:
            # Avoid infinite recursion when the blob is not JSON/XML.
            if isinstance(item, str) and item.strip() == value.strip():
                out.append(item)
            else:
                out.extend(unwrap(item, depth + 1))
        return out
    if isinstance(value, dict):
        content = value.get("content")
        if isinstance(content, list):
            out: list[Any] = []
            for item in content:
                out.extend(unwrap(item, depth + 1))
            return out
        if value.get("type") == "text" and isinstance(value.get("text"), str):
            return parse_text_blob(value["text"])
        if "text" in value and "id" not in value and "name" not in value:
            return parse_text_blob(str(value["text"]))
        return [value]
    if isinstance(value, list):
        out = []
        for item in value:
            out.extend(unwrap(item, depth + 1))
        return out
    return [value]


def is_node(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and "type" in value
        and ("id" in value or "name" in value)
    )


def bounds_of(node: dict) -> tuple[Any, Any, Any, Any] | None:
    for key in ("absoluteBoundingBox", "absoluteRenderBounds", "bounds", "bbox"):
        box = node.get(key)
        if isinstance(box, dict):
            return (
                box.get("x"),
                box.get("y"),
                box.get("width"),
                box.get("height"),
            )
    if all(key in node for key in ("x", "y", "width", "height")):
        return (node.get("x"), node.get("y"), node.get("width"), node.get("height"))
    return None


def format_bounds(box: tuple[Any, Any, Any, Any] | None) -> str:
    if not box:
        return ""
    x, y, width, height = box

    def number(value: Any) -> str:
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        return str(value)

    return f"  {number(width)}x{number(height)} @({number(x)},{number(y)})"


class Printer:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.types = {
            t.strip().upper() for t in (args.type or "").split(",") if t.strip()
        }
        self.records: list[dict] = []
        self.counts: Counter[str] = Counter()
        self.seen: set[str] = set()

    def matches(self, node_type: str, node_id: str) -> bool:
        if self.types and node_type.upper() not in self.types:
            return False
        if self.args.id and self.args.id not in node_id:
            return False
        return True

    def emit(self, depth: int, node_type: str, name: str, node_id: str, box: Any) -> None:
        self.counts[node_type or "UNKNOWN"] += 1
        if not self.matches(node_type, node_id):
            return
        if self.args.json:
            record = {
                "depth": depth,
                "id": node_id,
                "name": name,
                "type": node_type,
            }
            if box:
                record["bounds"] = {
                    "x": box[0],
                    "y": box[1],
                    "width": box[2],
                    "height": box[3],
                }
            self.records.append(record)
            return
        indent = "  " * depth
        label = f"{node_type:<12}".rstrip()
        name_part = f"  {name}" if name else ""
        id_part = f"  [{node_id}]" if node_id else ""
        print(f"{indent}{label}{name_part}{id_part}{format_bounds(box)}")

    def walk_json(self, node: Any, depth: int) -> None:
        if isinstance(node, list):
            for item in node:
                self.walk_json(item, depth)
            return
        if not isinstance(node, dict):
            return

        node_id = str(node.get("id") or "")
        node_type = str(node.get("type") or "")
        name = str(node.get("name") or "")

        if is_node(node):
            key = node_id or f"obj:{id(node)}"
            if key in self.seen:
                return
            self.seen.add(key)
            self.emit(depth, node_type, name, node_id, bounds_of(node))

            if depth >= self.args.max_depth:
                children = node.get("children")
                if isinstance(children, list) and children and not self.args.json:
                    print(f"{'  ' * (depth + 1)}...")
                return

        children = node.get("children")
        if isinstance(children, list):
            for child in children:
                self.walk_json(child, depth + 1)
            return

        nodes = node.get("nodes")
        if isinstance(nodes, dict):
            for child in nodes.values():
                self.walk_json(child, depth + 1)
            return

        if not is_node(node):
            # Wrapper object: recurse into child lists/dicts, but not scalars.
            for key, value in node.items():
                if key in ("content", "text", "children", "nodes"):
                    continue
                if isinstance(value, (list, dict)):
                    self.walk_json(value, depth)

    def walk_xml(self, element: ET.Element, depth: int) -> None:
        node_id = element.attrib.get("id", "")
        node_type = element.attrib.get("type", element.tag)
        name = element.attrib.get("name", "")
        box = None
        if all(key in element.attrib for key in ("x", "y", "width", "height")):
            box = (
                element.attrib.get("x"),
                element.attrib.get("y"),
                element.attrib.get("width"),
                element.attrib.get("height"),
            )
        self.emit(depth, node_type, name, node_id, box)
        if depth >= self.args.max_depth:
            return
        for child in list(element):
            self.walk_xml(child, depth + 1)

    def print_counts(self) -> None:
        if not self.counts:
            return
        print("\nCounts:", file=sys.stderr)
        for node_type, count in self.counts.most_common():
            print(f"  {node_type:<16} {count}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse saved Figma MCP metadata")
    parser.add_argument("file", help="Path to a saved metadata result")
    parser.add_argument("--max-depth", type=int, default=6, help="Maximum tree depth (default 6)")
    parser.add_argument("--type", help="Comma-separated node types to print, e.g. FRAME,COMPONENT")
    parser.add_argument("--id", help="Only print node IDs containing this substring")
    parser.add_argument("--json", action="store_true", help="Print JSON records")
    parser.add_argument("--count", action="store_true", help="Print node type counts to stderr")
    args = parser.parse_args()

    with open(args.file, "r", encoding="utf-8", errors="replace") as handle:
        raw = handle.read()

    if not raw.strip():
        print("error: empty file", file=sys.stderr)
        return 2

    printer = Printer(args)
    roots = unwrap(raw)

    if args.json:
        # Collect records before printing so stdout stays valid JSON.
        for root in roots:
            if isinstance(root, ET.Element):
                printer.walk_xml(root, 0)
            else:
                printer.walk_json(root, 0)
        print(json.dumps(printer.records, ensure_ascii=False, indent=2))
    else:
        for root in roots:
            if isinstance(root, ET.Element):
                printer.walk_xml(root, 0)
            elif isinstance(root, str):
                head = root.strip().replace("\n", " ")[:200]
                print(f"(unparsed text, {len(root)} chars): {head}")
            else:
                printer.walk_json(root, 0)

    if args.count:
        printer.print_counts()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
