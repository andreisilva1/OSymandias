from typing import Optional
from osymandias.schema import infer_schema


def test_primitive_types():
    def fn(name: str, count: int, ratio: float, flag: bool) -> dict: ...
    s = infer_schema(fn)
    assert s["properties"]["name"] == {"type": "string"}
    assert s["properties"]["count"] == {"type": "integer"}
    assert s["properties"]["ratio"] == {"type": "number"}
    assert s["properties"]["flag"] == {"type": "boolean"}


def test_required_vs_optional_params():
    def fn(required: str, optional: str = "default") -> dict: ...
    s = infer_schema(fn)
    assert "required" in s and s["required"] == ["required"]
    assert s["properties"]["optional"]["default"] == "default"


def test_list_of_primitives():
    def fn(items: list[str]) -> dict: ...
    s = infer_schema(fn)
    assert s["properties"]["items"] == {"type": "array", "items": {"type": "string"}}


def test_dict_param():
    def fn(data: dict) -> dict: ...
    s = infer_schema(fn)
    assert s["properties"]["data"] == {"type": "object"}


def test_optional_type():
    def fn(value: Optional[str] = None) -> dict: ...
    s = infer_schema(fn)
    prop = s["properties"]["value"]
    assert prop["type"] == "string"
    assert prop["nullable"] is True


def test_no_annotation_defaults_to_string():
    def fn(x) -> dict: ...
    s = infer_schema(fn)
    assert s["properties"]["x"] == {"type": "string"}


def test_empty_function():
    def fn() -> dict: ...
    s = infer_schema(fn)
    assert s["properties"] == {}
    assert "required" not in s
