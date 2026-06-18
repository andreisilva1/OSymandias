import inspect
from dataclasses import dataclass, field
from typing import Any, Callable

from osymandias.schema import infer_schema

_TOOL_REGISTRY: dict[str, "_ToolEntry"] = {}
_AGENT_REGISTRY: dict[str, "_AgentEntry"] = {}


@dataclass
class _ToolEntry:
    name: str
    description: str
    parameters: dict
    fn: Callable


@dataclass
class _AgentEntry:
    name: str
    description: str
    fn: Callable
    callable_ref: str          # "module.qualname" for discovery
    output_schema: dict        # JSON Schema or {}
    input_schema: dict         # JSON Schema or {}
    tools: list[str]
    llm_model: str | None
    llm_provider: str | None


def _extract_description(fn: Callable) -> str:
    doc = inspect.getdoc(fn)
    if not doc:
        return fn.__name__
    return doc.split("\n")[0].strip()


def _pydantic_to_jsonschema(model) -> dict:
    try:
        return model.model_json_schema()
    except AttributeError:
        return model.schema()


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

    def agent(
        self,
        name: str,
        *,
        description: str = "",
        output_schema=None,
        input_schema=None,
        tools: list[str] | None = None,
        llm_model: str | None = None,
        llm_provider: str | None = None,
    ) -> Callable:
        """Register a callable as an external OSymandias agent.

        Usage::

            @osy.agent("MyAgent")
            def my_agent(task: str, ctx: OsyContext) -> dict:
                ...
        """
        def decorator(fn: Callable) -> Callable:
            out_schema: dict = {}
            if output_schema is not None:
                if isinstance(output_schema, dict):
                    out_schema = output_schema
                else:
                    out_schema = _pydantic_to_jsonschema(output_schema)

            in_schema: dict = {}
            if input_schema is not None:
                if isinstance(input_schema, dict):
                    in_schema = input_schema
                else:
                    in_schema = _pydantic_to_jsonschema(input_schema)

            entry = _AgentEntry(
                name=name,
                description=description or _extract_description(fn),
                fn=fn,
                callable_ref=f"{fn.__module__}.{fn.__qualname__}",
                output_schema=out_schema,
                input_schema=in_schema,
                tools=tools or [],
                llm_model=llm_model,
                llm_provider=llm_provider,
            )
            _AGENT_REGISTRY[name] = entry
            return fn

        return decorator
