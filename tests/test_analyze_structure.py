import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "src" / "analyze_structure.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


analyze_structure = _load_module("analyze_structure", MODULE_PATH)


def _primitive_event(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    return "string"


def _emit_events(value):
    if isinstance(value, dict):
        yield "", "start_map", None
        for key, child in value.items():
            yield "", "map_key", key
            yield from _emit_events(child)
        yield "", "end_map", None
    elif isinstance(value, list):
        yield "", "start_array", None
        for child in value:
            yield from _emit_events(child)
        yield "", "end_array", None
    else:
        yield "", _primitive_event(value), value


class _FakeIjsonModule:
    @staticmethod
    def parse(fp):
        data = json.load(fp)
        yield from _emit_events(data)


def _schema_to_plain(node):
    if node is None:
        return None
    if node.kind == "value":
        return "value"
    if node.kind == "array":
        return [_schema_to_plain(node.element)]
    return {key: _schema_to_plain(child) for key, child in sorted(node.children.items())}


def _write_json(tmp_path: Path, name: str, payload):
    path = tmp_path / name
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_extract_schema_stream_matches_in_memory_schema(monkeypatch):
    payload = {
        "z": {"b": 1, "a": [{"d": 1}, {"ignored": 2}]},
        "a": [{"x": 1, "nested": [{"y": 2}, {"ignored": 3}]}, {"skip": True}],
        "m": "text",
    }
    monkeypatch.setitem(sys.modules, "ijson", _FakeIjsonModule())

    root_from_memory = analyze_structure.build_schema_in_memory(payload)
    root_from_stream = analyze_structure.extract_schema_stream(io.StringIO(json.dumps(payload)))

    assert _schema_to_plain(root_from_stream) == _schema_to_plain(root_from_memory)


def test_print_tree_sorts_keys_and_formats_arrays():
    payload = {
        "z": {"b": 1, "a": [{"d": 1}]},
        "a": [{"x": 1, "nested": [{"y": 2}]}],
        "m": "text",
    }
    root = analyze_structure.build_schema_in_memory(payload)
    out = io.StringIO()

    analyze_structure.print_tree(root, out)

    assert out.getvalue() == (
        "root\n"
        "├── a []\n"
        "│   ├── nested []\n"
        "│   │   └── y\n"
        "│   └── x\n"
        "├── m\n"
        "└── z\n"
        "    ├── a []\n"
        "    │   └── d\n"
        "    └── b\n"
    )


def test_main_force_json_load_writes_output_file(tmp_path, monkeypatch):
    input_path = _write_json(tmp_path, "input.json", {"b": 1, "a": [{"x": 1}]})
    output_path = tmp_path / "tree.txt"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "analyze_structure.py",
            str(input_path),
            "--force-json-load",
            "--output",
            str(output_path),
        ],
    )

    analyze_structure.main()

    assert output_path.read_text(encoding="utf-8") == (
        "root\n"
        "├── a []\n"
        "│   └── x\n"
        "└── b\n"
    )


def test_main_missing_file_exits_with_error(tmp_path, capsys, monkeypatch):
    missing_path = tmp_path / "missing.json"
    monkeypatch.setattr(sys, "argv", ["analyze_structure.py", str(missing_path)])

    with pytest.raises(SystemExit) as exc_info:
        analyze_structure.main()

    assert exc_info.value.code == 1
    assert f"Error: file not found: {missing_path}" in capsys.readouterr().err