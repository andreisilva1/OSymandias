import textwrap
from pathlib import Path
from osymandias.decorator import _TOOL_REGISTRY
from osymandias.discovery import discover


def _write(path: Path, src: str) -> None:
    path.write_text(textwrap.dedent(src), encoding="utf-8")


def test_discovers_tool_in_file(tmp_path):
    before = set(_TOOL_REGISTRY.keys())
    _write(tmp_path / "my_tools.py", """\
        from osymandias import osy

        @osy.tool
        def discovered_tool(x: str) -> dict:
            \"\"\"A discovered tool.\"\"\"
            return {}
    """)

    count = discover(tmp_path)
    assert count >= 1
    assert "discovered_tool" in _TOOL_REGISTRY

    # cleanup
    for k in list(_TOOL_REGISTRY.keys()):
        if k not in before:
            del _TOOL_REGISTRY[k]


def test_skips_file_without_osymandias_import(tmp_path):
    before = set(_TOOL_REGISTRY.keys())
    _write(tmp_path / "unrelated.py", """\
        def plain_function(x: str) -> dict:
            return {}
    """)

    count = discover(tmp_path)
    assert count == 0
    assert set(_TOOL_REGISTRY.keys()) == before


def test_skips_venv_directory(tmp_path):
    before = set(_TOOL_REGISTRY.keys())
    venv = tmp_path / ".venv" / "lib"
    venv.mkdir(parents=True)
    _write(venv / "sneaky.py", """\
        from osymandias import osy

        @osy.tool
        def should_be_skipped(x: str) -> dict:
            \"\"\"Should not be found.\"\"\"
            return {}
    """)

    discover(tmp_path)
    assert "should_be_skipped" not in _TOOL_REGISTRY
    assert set(_TOOL_REGISTRY.keys()) == before


def test_returns_count_of_new_tools(tmp_path):
    before = set(_TOOL_REGISTRY.keys())
    _write(tmp_path / "two_tools.py", """\
        from osymandias import osy

        @osy.tool
        def tool_alpha(x: str) -> dict:
            \"\"\"Alpha.\"\"\"
            return {}

        @osy.tool
        def tool_beta(x: str) -> dict:
            \"\"\"Beta.\"\"\"
            return {}
    """)

    count = discover(tmp_path)
    assert count == 2

    for k in list(_TOOL_REGISTRY.keys()):
        if k not in before:
            del _TOOL_REGISTRY[k]
