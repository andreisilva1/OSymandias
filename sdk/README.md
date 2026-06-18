# osymandias

> This directory is the `osymandias` PyPI package.

```bash
pip install -e .   # editable install for development
osy init           # scaffold config files
osy serve          # start runtime + register agents/tools
```

Exposes `@osy.tool` (built-in tool functions), `@osy.agent` (external agent registration), and `OsyContext` (shared memory, events, sub-tasks).

See the [root README](../README.md) for full documentation.
