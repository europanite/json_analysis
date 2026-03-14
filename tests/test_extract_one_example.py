import importlib.util
import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "src" / "extract_one_example.py"


def _primitive_event(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float, Decimal)):
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
        data = json.load(fp, parse_float=Decimal)
        yield from _emit_events(data)


sys.modules.setdefault("ijson", _FakeIjsonModule())


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


extract_one_example = _load_module("extract_one_example", MODULE_PATH)


def _write_json(tmp_path: Path, name: str, payload_text: str):
    path = tmp_path / name
    path.write_text(payload_text, encoding="utf-8")
    return path


def test_normalize_number_converts_decimal_int_and_float():
    assert extract_one_example.normalize_number(Decimal("2")) == 2
    assert extract_one_example.normalize_number(Decimal("2.5")) == 2.5
    assert extract_one_example.normalize_number("x") == "x"


def test_load_reduced_json_reduces_only_top_level_arrays(tmp_path, monkeypatch):
    monkeypatch.setattr(extract_one_example, "ijson", _FakeIjsonModule())
    input_path = _write_json(
        tmp_path,
        "input.json",
        json.dumps(
            {
                "numbers": [1, 2, 3],
                "objects": [{"b": 2, "a": [10, 11]}, {"ignored": True}],
                "meta": {"keep": "all", "nested": ["x", "y"]},
                "flag": True,
            },
            ensure_ascii=False,
        ),
    )

    reduced = extract_one_example.load_reduced_json(input_path)

    assert reduced == {
        "numbers": [1],
        "objects": [{"b": 2, "a": [10, 11]}],
        "meta": {"keep": "all", "nested": ["x", "y"]},
        "flag": True,
    }


def test_load_reduced_json_for_root_array_keeps_first_element(tmp_path, monkeypatch):
    monkeypatch.setattr(extract_one_example, "ijson", _FakeIjsonModule())
    input_path = _write_json(
        tmp_path,
        "input.json",
        json.dumps(
            [
                {"k": [1, 2], "name": "first"},
                {"ignored": 1},
            ],
            ensure_ascii=False,
        ),
    )

    reduced = extract_one_example.load_reduced_json(input_path)

    assert reduced == [{"k": [1, 2], "name": "first"}]


def test_main_writes_sorted_json_output(tmp_path, monkeypatch):
    monkeypatch.setattr(extract_one_example, "ijson", _FakeIjsonModule())
    input_path = _write_json(
        tmp_path,
        "input.json",
        json.dumps({"b": [2, 3], "a": {"z": 1, "y": 2}}, ensure_ascii=False),
    )
    output_path = tmp_path / "out.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "extract_one_example.py",
            str(input_path),
            "--output",
            str(output_path),
            "--sort-keys",
            "--indent",
            "2",
        ],
    )

    extract_one_example.main()

    assert output_path.read_text(encoding="utf-8") == (
        '{\n'
        '  "a": {\n'
        '    "y": 2,\n'
        '    "z": 1\n'
        '  },\n'
        '  "b": [\n'
        '    2\n'
        '  ]\n'
        '}\n'
    )


def test_main_missing_file_exits_with_error(tmp_path, capsys, monkeypatch):
    missing_path = tmp_path / "missing.json"
    monkeypatch.setattr(sys, "argv", ["extract_one_example.py", str(missing_path)])

    with pytest.raises(SystemExit) as exc_info:
        extract_one_example.main()

    assert exc_info.value.code == 1
    assert f"Error: file not found: {missing_path}" in capsys.readouterr().err