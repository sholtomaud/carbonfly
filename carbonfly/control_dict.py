"""
Writers and helpers for OpenFOAM `system/controlDict`.

This module provides utilities to generate and customize `controlDict`
files for OpenFOAM cases, supporting both steady-state and transient
simulations.
"""

from __future__ import annotations

# carbonfly/control_dict.py
from pathlib import Path
from typing import Dict, Any, Optional
import json

from .utils import foam_header

# Defaults
STEADY_DEFAULT: Dict[str, Any] = {
    "application": "buoyantReactingFoam",
    "startFrom": "latestTime",
    "startTime": 0,
    "stopAt": "endTime",
    "endTime": 1000,  # 1000 iterations
    "deltaT": 1,
    "writeControl": "timeStep",
    "writeInterval": 100,  # 100 iterations
    "purgeWrite": 0,
    "writeFormat": "ascii",
    "writePrecision": 8,
    "writeCompression": "off",
    "timeFormat": "general",
    "timePrecision": 6,
    "runTimeModifiable": True,
    "functions": {"residuals": {"include": "#includeFunc residuals"}},
}

TRANSIENT_DEFAULT: Dict[str, Any] = {
    "application": "buoyantReactingFoam",
    "startFrom": "latestTime",
    "startTime": 0,
    "stopAt": "endTime",
    "endTime": 120,  # 120s = 2min
    "deltaT": 0.01,
    "writeControl": "runTime",
    "writeInterval": 10,  # 10s
    "purgeWrite": 0,
    "writeFormat": "ascii",
    "writePrecision": 8,
    "writeCompression": "off",
    "timeFormat": "general",
    "timePrecision": 6,
    "runTimeModifiable": True,
    "adjustTimeStep": "yes",  # yes/no
    "maxCo": 1,
    "maxDeltaT": 0.2,
    "functions": {
        "residuals": {"include": "#includeFunc residuals"},
        "CoNum": {
            "type": "CourantNo",
            "libs": '("libfieldFunctionObjects.so")',
            "writeControl": "runTime",
            "writeInterval": 10,
        },
    },
}


# Helpers
def _merge(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """Shallow-merge dict `b` into `a` (returns a new dict).

    Special-case:
        If key is "functions" and both values are dicts, merge by function name.

    Args:
        a (Dict[str, Any]): Base config.
        b (Dict[str, Any]): Override config.

    Returns:
        Dict[str, Any]: Merged config.
    """
    out = dict(a)
    for k, v in (b or {}).items():
        if (
            k == "functions"
            and isinstance(v, dict)
            and isinstance(out.get("functions"), dict)
        ):
            f = dict(out["functions"])
            f.update(v)
            out["functions"] = f
        else:
            out[k] = v
    return out


def _fmt_bool_or_token(key: str, val: Any) -> str:
    """Format values to OpenFOAM-style tokens.

    Rules:
        - For adjustTimeStep: bool -> yes/no, str -> passed through.
        - For other bools: true/false.
        - Otherwise: str(val).

    Args:
        key (str): Entry key (used for special-casing).
        val (Any): Value to format.

    Returns:
        str: Formatted OpenFOAM token string.
    """
    if key == "adjustTimeStep":
        if isinstance(val, bool):
            return "yes" if val else "no"
        if isinstance(val, str):
            return val
    if isinstance(val, bool):
        return "true" if val else "false"
    return str(val)


def _render_kv(lines, key: str, val: Any):
    """Append one `key value;` entry to output lines."""
    lines.append(f"{key}\t\t{_fmt_bool_or_token(key, val)};")


def _render_functions_block(lines, funcs: Dict[str, Any]):
    """
    Render a `functions { ... }` block.

    Supported specs:
        1) {"name": {"include": "#includeFunc residuals"}}
        2) {"CoNum": {"type": "...", "libs": "...", "writeControl": "...", ...}}

    Args:
        lines: List of output lines to append to.
        funcs (Dict[str, Any]): Functions mapping.
    """
    if not funcs:
        return
    lines.append("")
    lines.append("functions")
    lines.append("{")
    # support:
    # 1) {"name": {"include": "#includeFunc residuals"}}
    # 2) {"CoNum": {"type":"CourantNo", "libs":"(...)", "writeControl":"runTime", "writeInterval":10}}
    for name, spec in funcs.items():
        if isinstance(spec, dict) and "include" in spec:
            lines.append(f"  {spec['include']}")
            continue
        lines.append(f"  {name}")
        lines.append("  {")
        if isinstance(spec, dict):
            for k, v in spec.items():
                if k == "include":
                    lines.append(f"    {v}")
                else:
                    lines.append(f"    {k}\t\t{_fmt_bool_or_token(k, v)};")
        lines.append("  }")
    lines.append("}")


# API
def make_default(
    mode: str = "transient", application: Optional[str] = None
) -> Dict[str, Any]:
    """Return a default controlDict config dict.

    Args:
        mode (str): "transient"/"unsteady" or "steady".
        application (str, optional): Override `application` entry.

    Returns:
        Dict[str, Any]: controlDict config dict.
    """
    mode = (mode or "transient").strip().lower()
    base = TRANSIENT_DEFAULT if mode in ("transient", "unsteady") else STEADY_DEFAULT
    cfg = dict(base)
    if application:
        cfg["application"] = application
    return cfg


def write_control_dict_from_json(case_root: Path, cfg_json: str) -> Path:
    """
    Parse a JSON string and write `system/controlDict`.

    Args:
        case_root (Path): Case root directory.
        cfg_json (str): JSON string representing a config dict.

    Returns:
        Path: Written `system/controlDict` path.

    Raises:
        ValueError: If the parsed JSON is not a JSON object.
    """
    cfg = json.loads(cfg_json) if cfg_json else {}
    if not isinstance(cfg, dict):
        raise ValueError("controlDict JSON must be a JSON object.")
    return write_control_dict(case_root, cfg)


def write_control_dict(case_root: Path, cfg: Dict[str, Any]) -> Path:
    """
    Write `system/controlDict` using a config dict.

    Args:
        case_root (Path): Case root directory.
        cfg (Dict[str, Any]): controlDict configuration.

    Returns:
        Path: Written `system/controlDict` path.
    """
    case_root = Path(case_root)
    out = case_root / "system" / "controlDict"
    out.parent.mkdir(parents=True, exist_ok=True)

    # header
    lines = [foam_header("controlDict", location="system")]

    # scalar/token entries
    ordered_keys = [
        "application",
        "startFrom",
        "startTime",
        "stopAt",
        "endTime",
        "deltaT",
        "writeControl",
        "writeInterval",
        "purgeWrite",
        "writeFormat",
        "writePrecision",
        "writeCompression",
        "timeFormat",
        "timePrecision",
        "runTimeModifiable",
        "adjustTimeStep",
        "maxCo",
        "maxDeltaT",
    ]
    for k in ordered_keys:
        if k in cfg:
            _render_kv(lines, k, cfg[k])

    # functions
    funcs = cfg.get("functions")
    _render_functions_block(lines, funcs if isinstance(funcs, dict) else {})

    # write
    text = "\n".join(lines) + "\n"
    out.write_text(text, encoding="utf-8")
    return out
