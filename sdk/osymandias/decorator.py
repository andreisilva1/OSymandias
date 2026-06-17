from dataclasses import dataclass, field
from typing import Callable

from osymandias.schema import infer_schema

_TOOL_REGISTRY: dict[str, "_ToolEntry"] = {}


@dataclass
class _ToolEntry:
    name: str
    description: str
    parameters: dict
    fn: Callable


def _extract_description(fn: Callable) -> str:
    doc = inspect.getdoc(fn)
    if not doc:
        return fn.__name__
    return doc.split("\n")[0].strip()


import inspect  # noqa: E402 (after dataclass to avoid circular at module load)


class _Osy:
    def tool(self, fn: Callable) -> Callable:
        entry = _ToolEntry(
            name=fn.__name__,
            description=_extract_description(fn),
            parameters=infer_schema(fn),
            fn=fn,
        )
        _TOOL_REGISTRY[fn.__name__] = entry
        return fn
