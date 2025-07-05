import types
from typing import Dict, Any


def run_tool(code: str, item: Dict[str, Any]) -> Dict[str, Any]:
    ns: Dict[str, Any] = {}
    exec(code, {}, ns)
    if "run" not in ns or not isinstance(ns["run"], types.FunctionType):
        raise ValueError("Tool code must define a 'run' function")
    return ns["run"](item)
