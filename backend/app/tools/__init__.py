"""Tool registry.

Tools are plain async Python functions in this package. The orchestrator imports
them directly. When wiring Qwen-Agent in, we'll wrap each function with the
framework's tool-registration decorator and expose them as a single registry
the LLM can pick from.

Pattern for adding a new tool:
1. Add the function in the right category file (geocoding, reachability, …).
2. Make it `async`. Accept Pydantic-typed inputs, return JSON-serialisable output.
3. When `get_settings().demo_mode` is True, short-circuit to `app.mock.canned`.
"""
