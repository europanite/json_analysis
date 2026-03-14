#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
json_key_tree.py

Print the key structure of a JSON file as a tree.

Features:
- Prints keys only
- Ignores values
- For arrays, inspects only the first element
- Displays object keys in ascending alphabetical order
- Uses streaming parsing with ijson for large files
"""

import argparse
import json
import sys
from pathlib import Path

PRIMITIVE_EVENTS = {"string", "number", "boolean", "null"}


class SchemaNode:
    """A minimal schema tree node."""

    def __init__(self, kind: str):
        # kind: "object" | "array" | "value"
        self.kind = kind
        self.children = {}   # for object nodes: {key: SchemaNode}
        self.element = None  # for array nodes: SchemaNode | None

    def ensure_child(self, key: str, kind: str):
        """Create or return a child node for an object key."""
        if key is None:
            key = "<unknown>"
        node = self.children.get(key)
        if node is None:
            node = SchemaNode(kind)
            self.children[key] = node
        return node

    def ensure_element(self, kind: str):
        """Create or return the representative element node for an array."""
        if self.element is None:
            self.element = SchemaNode(kind)
        return self.element


def build_schema_in_memory(obj):
    """
    Build a schema tree using normal in-memory JSON loading.
    Arrays are reduced to their first element only.
    """
    if isinstance(obj, dict):
        node = SchemaNode("object")
        for key, value in obj.items():
            node.children[key] = build_schema_in_memory(value)
        return node

    if isinstance(obj, list):
        node = SchemaNode("array")
        if obj:
            node.element = build_schema_in_memory(obj[0])
        return node

    return SchemaNode("value")


def extract_schema_stream(fp):
    """
    Build a schema tree by streaming through the JSON file with ijson.
    Arrays are reduced to their first element only.
    """
    try:
        import ijson
    except ImportError as exc:
        raise RuntimeError(
            "ijson is required for this tool. Install it with: pip install -r requirements.txt"
        ) from exc

    root = None
    stack = []

    for _, event, value in ijson.parse(fp):
        # If we are skipping repeated array items, only track nesting depth.
        if stack and stack[-1]["type"] == "skip":
            if event == "start_map":
                stack.append({"type": "skip", "container": "map"})
            elif event == "start_array":
                stack.append({"type": "skip", "container": "array"})
            elif event == "end_map":
                stack.pop()
            elif event == "end_array":
                stack.pop()
            continue

        if event == "start_map":
            if not stack:
                root = SchemaNode("object")
                stack.append({"type": "obj", "node": root, "pending_key": None})
            else:
                parent = stack[-1]

                if parent["type"] == "obj":
                    child = parent["node"].ensure_child(parent["pending_key"], "object")
                    parent["pending_key"] = None
                    stack.append({"type": "obj", "node": child, "pending_key": None})

                elif parent["type"] == "arr":
                    if parent["item_index"] == 0:
                        child = parent["node"].ensure_element("object")
                        parent["item_index"] += 1
                        stack.append({"type": "obj", "node": child, "pending_key": None})
                    else:
                        parent["item_index"] += 1
                        stack.append({"type": "skip", "container": "map"})

        elif event == "end_map":
            if stack and stack[-1]["type"] == "obj":
                stack.pop()

        elif event == "map_key":
            if stack and stack[-1]["type"] == "obj":
                stack[-1]["pending_key"] = value

        elif event == "start_array":
            if not stack:
                root = SchemaNode("array")
                stack.append({"type": "arr", "node": root, "item_index": 0})
            else:
                parent = stack[-1]

                if parent["type"] == "obj":
                    child = parent["node"].ensure_child(parent["pending_key"], "array")
                    parent["pending_key"] = None
                    stack.append({"type": "arr", "node": child, "item_index": 0})

                elif parent["type"] == "arr":
                    if parent["item_index"] == 0:
                        child = parent["node"].ensure_element("array")
                        parent["item_index"] += 1
                        stack.append({"type": "arr", "node": child, "item_index": 0})
                    else:
                        parent["item_index"] += 1
                        stack.append({"type": "skip", "container": "array"})

        elif event == "end_array":
            if stack and stack[-1]["type"] == "arr":
                stack.pop()

        elif event in PRIMITIVE_EVENTS:
            if not stack:
                root = SchemaNode("value")
            else:
                parent = stack[-1]

                if parent["type"] == "obj":
                    parent["node"].ensure_child(parent["pending_key"], "value")
                    parent["pending_key"] = None

                elif parent["type"] == "arr":
                    if parent["item_index"] == 0:
                        parent["node"].ensure_element("value")
                    parent["item_index"] += 1

    return root


def render_named_node(name, node, prefix="", is_last=True, out=sys.stdout):
    """Render a named node with tree branches."""
    connector = "└── " if is_last else "├── "

    if node.kind == "array":
        print(prefix + connector + f"{name} []", file=out)
        next_prefix = prefix + ("    " if is_last else "│   ")
        render_array_contents(node, next_prefix, out)
    else:
        print(prefix + connector + name, file=out)
        if node.kind == "object":
            next_prefix = prefix + ("    " if is_last else "│   ")
            render_object_children(node, next_prefix, out)


def render_object_children(node, prefix="", out=sys.stdout):
    """Render all children of an object node in ascending key order."""
    items = sorted(node.children.items(), key=lambda item: item[0])
    for index, (key, child) in enumerate(items):
        render_named_node(key, child, prefix, index == len(items) - 1, out)


def render_array_contents(array_node, prefix="", out=sys.stdout):
    """Render the representative contents of an array node."""
    elem = array_node.element

    if elem is None or elem.kind == "value":
        return

    if elem.kind == "object":
        render_object_children(elem, prefix, out)
    elif elem.kind == "array":
        print(prefix + "└── []", file=out)
        render_array_contents(elem, prefix + "    ", out)


def print_tree(root, out=sys.stdout):
    """Print the full schema tree."""
    if root is None:
        print("(empty)", file=out)
        return

    if root.kind == "object":
        print("root", file=out)
        render_object_children(root, "", out)
    elif root.kind == "array":
        print("root []", file=out)
        render_array_contents(root, "", out)
    else:
        print("root", file=out)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Print the key structure of a JSON file as a tree."
    )
    parser.add_argument("json_file", help="Path to the input JSON file.")
    parser.add_argument(
        "-o",
        "--output",
        help="Optional output file path. If omitted, prints to stdout.",
    )
    parser.add_argument(
        "--force-json-load",
        action="store_true",
        help="Disable streaming mode and use json.load() instead.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    input_path = Path(args.json_file)

    if not input_path.exists():
        print(f"Error: file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    root = None

    if args.force_json_load:
        with input_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        root = build_schema_in_memory(data)
    else:
        with input_path.open("rb") as f:
            root = extract_schema_stream(f)

    if args.output:
        output_path = Path(args.output)
        with output_path.open("w", encoding="utf-8") as out:
            print_tree(root, out)
    else:
        print_tree(root, sys.stdout)


if __name__ == "__main__":
    main()
