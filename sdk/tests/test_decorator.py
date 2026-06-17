import pytest
from osymandias.decorator import _TOOL_REGISTRY, _Osy


@pytest.fixture(autouse=True)
def clean_registry():
    before = set(_TOOL_REGISTRY.keys())
    yield
    for key in list(_TOOL_REGISTRY.keys()):
        if key not in before:
            del _TOOL_REGISTRY[key]


def test_tool_registered():
    osy = _Osy()

    @osy.tool
    def my_tool(query: str) -> dict:
        """Search for something."""
        return {}

    assert "my_tool" in _TOOL_REGISTRY


def test_tool_description_from_docstring():
    osy = _Osy()

    @osy.tool
    def described(x: str) -> dict:
        """First line description.

        Second line ignored.
        """
        return {}

    assert _TOOL_REGISTRY["described"].description == "First line description."


def test_tool_description_fallback_to_name():
    osy = _Osy()

    @osy.tool
    def no_doc(x: str) -> dict:
        return {}

    assert _TOOL_REGISTRY["no_doc"].description == "no_doc"


def test_tool_parameters_inferred():
    osy = _Osy()

    @osy.tool
    def typed_tool(name: str, count: int = 1) -> dict:
        """A tool."""
        return {}

    params = _TOOL_REGISTRY["typed_tool"].parameters
    assert params["properties"]["name"]["type"] == "string"
    assert params["properties"]["count"]["type"] == "integer"
    assert "name" in params["required"]
    assert "count" not in params.get("required", [])


def test_decorator_returns_original_function():
    osy = _Osy()

    @osy.tool
    def identity(x: int) -> int:
        """Return x."""
        return x

    assert identity(42) == 42
