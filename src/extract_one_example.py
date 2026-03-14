#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
extract_top_first_items.py

Keep only the first item for each top-level JSON element.

Behavior:
- If the root is an object:
  - top-level array values -> keep only the first element, but keep that element in full
  - top-level object values -> keep the full object unchanged
  - top-level primitive values -> keep unchanged
- If the root is an array:
  - keep only the first element, in full
- If the root is a primitive:
  - keep it unchanged

This script is designed for large JSON files and uses ijson for streaming.
"""

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

import ijson


PRIMITIVE_EVENTS = {"string", "number", "boolean", "null"}
CONTAINER_START_EVENTS = {"start_map", "start_array"}
CONTAINER_END_EVENTS = {"end_map", "end_array"}


def normalize_number(value):
    """Convert Decimal values from ijson into int or float."""
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    return value


def normalize_primitive(value):
    """Normalize primitive values for json.dump()."""
    return normalize_number(value)


def skip_from_event(event, events):
    """
    Skip the current value starting from an already-consumed event.
    If the event is primitive, nothing remains to be consumed.
    """
    if event not in CONTAINER_START_EVENTS:
        return

    depth = 1
    for _, next_event, _ in events:
        if next_event in CONTAINER_START_EVENTS:
            depth += 1
        elif next_event in CONTAINER_END_EVENTS:
            depth -= 1
            if depth == 0:
                return


def read_full_value_from_event(event, value, events):
    """Read a full JSON value from the current event."""
    if event == "start_map":
        return read_full_map(events)
    if event == "start_array":
        return read_full_array(events)
    if event in PRIMITIVE_EVENTS:
        return normalize_primitive(value)
    raise ValueError(f"Unsupported event while reading full value: {event}")


def read_full_map(events):
    """Read a full JSON object."""
    result = {}

    for _, event, value in events:
        if event == "end_map":
            return result

        if event != "map_key":
            raise ValueError(f"Unexpected event inside object: {event}")

        key = value
        _, value_event, value_value = next(events)
        result[key] = read_full_value_from_event(value_event, value_value, events)

    raise ValueError("Unexpected end of stream while reading object")


def read_full_array(events):
    """Read a full JSON array."""
    result = []

    for _, event, value in events:
        if event == "end_array":
            return result

        result.append(read_full_value_from_event(event, value, events))

    raise ValueError("Unexpected end of stream while reading array")


def read_first_array_only(events):
    """
    Read an array and keep only its first element, in full.
    """
    result = []
    first_taken = False

    for _, event, value in events:
        if event == "end_array":
            return result

        if not first_taken:
            result.append(read_full_value_from_event(event, value, events))
            first_taken = True
        else:
            skip_from_event(event, events)

    raise ValueError("Unexpected end of stream while reading array")


def reduce_root_object(events):
    """
    Read a root object.

    Reduction rule is applied only to the root's direct children:
    - top-level arrays -> keep first element only
    - top-level objects -> keep full object
    - top-level primitives -> keep as-is
    """
    result = {}

    for _, event, value in events:
        if event == "end_map":
            return result

        if event != "map_key":
            raise ValueError(f"Unexpected event at root object level: {event}")

        key = value
        _, value_event, value_value = next(events)

        if value_event == "start_array":
            result[key] = read_first_array_only(events)
        else:
            result[key] = read_full_value_from_event(value_event, value_value, events)

    raise ValueError("Unexpected end of stream while reading root object")


def reduce_root_array(events):
    """
    Read a root array and keep only its first element, in full.
    """
    return read_first_array_only(events)


def load_reduced_json(input_path):
    """Load and reduce the input JSON file."""
    with input_path.open("rb") as f:
        events = iter(ijson.parse(f))
        _, first_event, first_value = next(events)

        if first_event == "start_map":
            return reduce_root_object(events)
        if first_event == "start_array":
            return reduce_root_array(events)
        if first_event in PRIMITIVE_EVENTS:
            return normalize_primitive(first_value)

        raise ValueError(f"Unsupported root event: {first_event}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Keep only the first item for each top-level JSON element."
    )
    parser.add_argument("input_json", help="Path to the input JSON file.")
    parser.add_argument(
        "-o",
        "--output",
        help="Path to the output JSON file. If omitted, prints to stdout.",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="Indent size for output JSON. Default: 2",
    )
    parser.add_argument(
        "--sort-keys",
        action="store_true",
        help="Sort keys in output JSON.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    input_path = Path(args.input_json)

    if not input_path.exists():
        print(f"Error: file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    reduced = load_reduced_json(input_path)

    if args.output:
        output_path = Path(args.output)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(
                reduced,
                f,
                ensure_ascii=False,
                indent=args.indent,
                sort_keys=args.sort_keys,
            )
            f.write("\n")
    else:
        json.dump(
            reduced,
            sys.stdout,
            ensure_ascii=False,
            indent=args.indent,
            sort_keys=args.sort_keys,
        )
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
