import inspect
import typing
from typing import Callable, get_args, get_origin


def infer_schema(fn: Callable) -> dict:
    sig = inspect.signature(fn)
    properties: dict = {}
    required: list[str] = []

    for name, param in sig.parameters.items():
        annotation = param.annotation
        if annotation is inspect.Parameter.empty:
            prop = {"type": "string"}
        else:
            prop = _annotation_to_schema(annotation)

        if param.default is not inspect.Parameter.empty:
            prop["default"] = param.default
        else:
            required.append(name)

        properties[name] = prop

    schema: dict = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _annotation_to_schema(annotation) -> dict:
    origin = get_origin(annotation)
    args = get_args(annotation)

    # Optional[X] → union with None
    if origin is typing.Union:
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            prop = _annotation_to_schema(non_none[0])
            prop["nullable"] = True
            return prop
        return {"type": "string"}

    if origin is list:
        item_schema = _annotation_to_schema(args[0]) if args else {"type": "string"}
        return {"type": "array", "items": item_schema}

    if origin is dict:
        return {"type": "object"}

    _MAP = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
    }
    return {"type": _MAP.get(annotation, "string")}
