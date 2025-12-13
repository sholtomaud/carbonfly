"""
carbonfly
    a lightweight, easy-to-use Python API and
    toolbox for indoor CO2 CFD simulations in Grasshopper
    based on OpenFOAM and WSL

- Author: Qirui Huang
- License: LGPL-3.0
- Website: https://github.com/RWTH-E3D/carbonfly
"""

from __future__ import annotations

# carbonfly/field_writer.py
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple, Any
from .utils import foam_header


# Utilities
def _is_vec3(v: Any) -> bool:
    """Return True if v looks like a 3D vector (len == 3)."""
    return isinstance(v, (list, tuple)) and len(v) == 3


def _default_dimensions(field_name: str) -> str:
    """
    Return default OpenFOAM dimensions string for common fields.

    Args:
        field_name (str): Field name (e.g., "U", "T", "p", "CO2").

    Returns:
        str: OpenFOAM dimensions string.
    """
    fn = field_name.strip()
    if fn == "U":  # velocity [m s^-1]
        return "[0 1 -1 0 0 0 0]"
    if fn == "T":  # temperature [K]
        return "[0 0 0 1 0 0 0]"
    if fn == "p":  # pressure [Pa]
        return "[1 -1 -2 0 0 0 0]"
    if fn == "p_rgh":
        return "[1 -1 -2 0 0 0 0]"
    if fn == "alphat":
        return "[1 -1 -1 0 0 0 0]"
    if fn == "epsilon":
        return "[0 2 -3 0 0 0 0]"
    if fn == "G":
        return "[1 0 -3 0 0 0 0]"
    if fn == "k":
        return "[0 2 -2 0 0 0 0]"
    if fn == "nut":
        return "[0 2 -1 0 0 0 0]"

    # CO2 or other passive scalar (dimensionless by default)
    return "[0 0 0 0 0 0 0]"


def _write_value_line(prefix: str, v: Any) -> str:
    """Render a single OpenFOAM entry line for common boundary condition keys.

    Note:
        For some keys (e.g., value, inletValue, p0), OpenFOAM usually expects
        `uniform` for scalar/vector literals. String values are written as-is.

    Args:
        prefix (str): Dictionary key (e.g., "value", "inletValue").
        v (Any): Value (scalar, vec3, or OpenFOAM token/string).

    Returns:
        str: One formatted line (with indentation) ending in ';'.
    """
    _FIELD_VALUE_KEYS = {
        "value",
        "inletValue",
        "outletValue",
        "initialValue",
        "emissivity",
        "h",
        "Ta",
        "q",
        "p0",
    }
    key = prefix.strip()

    if _is_vec3(v):
        return f"        {prefix} {'uniform ' if key in _FIELD_VALUE_KEYS else ''}({v[0]} {v[1]} {v[2]});"
    if isinstance(v, (int, float)):
        return f"        {prefix} {'uniform ' if key in _FIELD_VALUE_KEYS else ''}{v};"
    if isinstance(v, str):
        s = v.strip()
        return f"        {prefix} {s};"

    return f"        {prefix} uniform 0;"


def _field_block_text(spec: Any) -> str:
    """
    Render a patchField block from a spec object.

    Expects `spec` to provide `to_dict()` compatible with carbonfly.boundary.Field*.

    Args:
        spec (Any): Field spec object with `to_dict()`.

    Returns:
        str: Multi-line text for the patch block (indented for insertion).
    """
    d = spec.to_dict()
    typ = d.get("type")
    lines = [f"        type {typ};"]
    if typ in ("fixedValue", "calculated"):
        lines.append(_write_value_line("value", d.get("value")))

    elif typ == "inletOutlet":
        lines.append(_write_value_line("inletValue", d.get("inletValue")))
        lines.append(_write_value_line("value", d.get("value")))

    elif typ == "compressible::alphatJayatillekeWallFunction":
        lines.append(_write_value_line("value", d.get("value")))
        lines.append(_write_value_line("Prt", 0.85))

    elif typ in ("epsilonWallFunction", "kqRWallFunction", "nutkWallFunction"):
        lines.append(_write_value_line("value", d.get("value")))

    elif typ == "turbulentMixingLengthDissipationRateInlet":
        lines.append(_write_value_line("value", d.get("value")))
        lines.append(_write_value_line("mixingLength", 0.0168))

    elif typ == "turbulentIntensityKineticEnergyInlet":
        lines.append(_write_value_line("intensity", 0.14))
        lines.append(_write_value_line("value", d.get("value")))

    elif typ == "MarshakRadiation":
        lines.append(_write_value_line("emissivityMode", "lookup"))
        lines.append(_write_value_line("emissivity", 0.98))
        lines.append(_write_value_line("value", d.get("value")))

    elif typ == "totalPressure":
        lines.append(_write_value_line("p0", d.get("p0")))
        lines.append(_write_value_line("value", d.get("value")))

    elif typ == "fixedFluxPressure":
        lines.append(_write_value_line("value", d.get("value")))

    elif typ == "pressureInletOutletVelocity":
        lines.append(_write_value_line("inletValue", d.get("inletValue")))
        lines.append(_write_value_line("value", d.get("value")))

    elif typ == "externalWallHeatFluxTemperature":
        lines.append(_write_value_line("mode", "coefficient"))
        lines.append(_write_value_line("h", d.get("h")))
        lines.append(_write_value_line("Ta", d.get("Ta")))
        lines.append(_write_value_line("value", d.get("value")))

    elif typ == "codedFixedValue":
        lines.append(_write_value_line("value", d.get("value")))
        lines.append(_write_value_line("name", d["name"]))
        code_block = (d.get("code") or "").rstrip("\n")
        if code_block:
            lines.append("        code")
        for cl in code_block.splitlines():
            lines.append("        " + cl)

    # zeroGradient requires no extra keys
    return "\n".join(lines)


def _infer_internal_from_patches(
    patch_specs: Dict[str, Any], field_name: str
) -> Optional[Any]:
    """
    Infer an internalField value from the first available patch spec.

    Args:
        patch_specs (Dict[str, Any]): Mapping patch_name -> spec.
        field_name (str): Field name (currently unused; reserved for future rules).

    Returns:
        Optional[Any]: Inferred value (scalar or vec3), or None if not inferable.
    """
    for spec in patch_specs.values():
        if spec is None:
            continue
        d = spec.to_dict()
        t = d.get("type")
        if t == "fixedValue":
            return d.get("value")
        if t == "inletOutlet":
            # prefer inletValue, fallback to value
            return d.get("inletValue", d.get("value"))

    return None


# 0/ fields
def write_0_field(
    case_root: Path,
    field_name: str,
    internal_value: Optional[Any],
    patch_specs: Dict[str, Any],
    *,
    dimensions: Optional[str] = None,
    infer_internal_when_none: bool = False,
) -> Path:
    """
    Write a single field file under 0/ (e.g. 0/U, 0/T, 0/CO2 ...).

    Args:
        case_root (Path): Case root path.
        field_name (str): Field name (e.g., "U", "T", "CO2").
        internal_value (Any, optional): Internal field value (scalar or vec3).
        patch_specs (Dict[str, Any]): Mapping patch_name -> field spec object.
        dimensions (str, optional): Override dimensions string. If None, uses defaults by name.
        infer_internal_when_none (bool): If True and internal_value is None, infer from patch specs.

    Returns:
        Path: Path to the written `0/<field_name>` file.
    """
    is_vec = field_name == "U"
    out = Path(case_root) / "0" / field_name
    out.parent.mkdir(parents=True, exist_ok=True)

    OFclass = "volVectorField" if is_vec else "volScalarField"
    lines = [foam_header(field_name, OFclass, location="0")]

    # dimensions
    if dimensions is None:
        # get default dimensions if not given
        dims = _default_dimensions(field_name)
    else:
        dims = dimensions
    lines.append(f"dimensions      {dims};")

    # internalField
    if internal_value is None and infer_internal_when_none:
        internal_value = _infer_internal_from_patches(patch_specs, field_name)

    # default internalField value
    if internal_value is None:
        if field_name == "U":
            internal_value = (0.0, 0.0, 0.0)
        elif field_name == "T":
            internal_value = 295.15  # 22 degC
        elif field_name == "p":
            internal_value = 1e5
        elif field_name == "epsilon":
            internal_value = 0.01
        elif field_name == "k":
            internal_value = 0.1
        else:
            internal_value = 0.0

    if is_vec and _is_vec3(internal_value):
        lines.append(
            f"internalField   uniform ({internal_value[0]} {internal_value[1]} {internal_value[2]});"
        )
    else:
        lines.append(f"internalField   uniform {internal_value};")

    # boundaryField
    lines.append("\nboundaryField\n{")
    for patch, spec in patch_specs.items():
        lines.append(f"    {patch}\n    {{")
        if spec is None:
            lines.append("        type zeroGradient;")
        else:
            lines.append(_field_block_text(spec))
        lines.append("    }")
    lines.append("}")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return out


def write_fields_batch(
    case_root: Path,
    fields: Dict[str, Dict[str, Any]],
    internal_values: Optional[Dict[str, Any]] = None,
    *,
    dimensions_map: Optional[Dict[str, str]] = None,
    infer_internal_when_none: bool = False,
) -> Dict[str, Path]:
    """
    Convenience function to write multiple 0/ field files at once.

    Args:
        case_root (Path): Case root path.
        fields (Dict[str, Dict[str, Any]]): Mapping field_name -> (patch_name -> spec).
        internal_values (Dict[str, Any], optional): Mapping field_name -> internalField value.
        dimensions_map (Dict[str, str], optional): Mapping field_name -> dimensions string.
        infer_internal_when_none (bool): If True, infer internal values when missing.

    Example:
        fields = {
            "U": {"inlet": FieldFV((0, 0, -1)), "wall": FieldFV((0, 0, 0))},
            "T": {"inlet": FieldFV(293.15), "wall": FieldZG()},
            "CO2": {"inlet": FieldFV(4.5e-4)},
        }
        write_fields_batch(case_root, fields)

    Returns:
        Dict[str, Path]: Mapping field_name -> written file path.
    """
    paths: Dict[str, Path] = {}
    internal_values = internal_values or {}
    dimensions_map = dimensions_map or {}

    for field_name, patch_specs in fields.items():
        paths[field_name] = write_0_field(
            case_root=case_root,
            field_name=field_name,
            internal_value=internal_values.get(field_name),
            patch_specs=patch_specs,
            dimensions=dimensions_map.get(field_name),
            infer_internal_when_none=infer_internal_when_none,
        )

    return paths
