"""
Minimal FastAPI server that exposes @osy.tool functions over HTTP on port 8001.
The OSymandias runtime calls these tools via the existing webhook protocol.
"""
import json
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from osymandias.decorator import _TOOL_REGISTRY

app = FastAPI(title="osy-tool-server", docs_url=None, redoc_url=None)


class CallRequest(BaseModel):
    arguments: dict[str, Any] = {}


@app.get("/tools")
async def list_tools():
    return [
        {
            "name": e.name,
            "description": e.description,
            "parameters": e.parameters,
        }
        for e in _TOOL_REGISTRY.values()
    ]


@app.post("/tools/{name}/call")
async def call_tool(name: str, req: CallRequest):
    entry = _TOOL_REGISTRY.get(name)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Tool '{name}' not found")
    try:
        result = entry.fn(**req.arguments)
        # Handle coroutines (async tools)
        if hasattr(result, "__await__"):
            import asyncio
            result = await result
        return {"result": result}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})
