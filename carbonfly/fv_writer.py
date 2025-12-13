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

# carbonfly/fv_writer.py
from pathlib import Path
import re
import shutil
from typing import Literal, Optional, Tuple


Mode = Literal["transient", "steadystate"]


def _normalize_mode(mode_in: str | None) -> Mode:
    """
    Normalize user mode string to a supported template mode.

    Args:
        mode_in (str | None): Input mode string.

    Returns:
        Mode: "transient" or "steadystate".
    """
    if not mode_in:
        return "transient"
    s = str(mode_in).strip().lower()
    if s in ("unsteady", "transient", "trans"):
        return "transient"
    if s in ("steady", "steadystate", "steady-state"):
        return "steadystate"
    # default: transient
    return "transient"


def _fmt_sci(x: float) -> str:
    """Format a float in OpenFOAM-like scientific notation (e.g., 1e-5)."""
    s = f"{x:.0e}"
    # 1e+05 -> 1e5 / 1e-05 -> 1e-5
    s = s.replace("e+0", "e").replace("e+", "e").replace("e-0", "e-")
    return s


def get_template_path(
    kind: Literal["fvSchemes", "fvSolution"], mode: str | None
) -> Path:
    """Return the absolute path to a built-in fv template file.

    Args:
        kind (Literal["fvSchemes","fvSolution"]): Template filename.
        mode (str | None): Mode selector (e.g., "transient", "steady", ...).

    Returns:
        Path: Absolute template path under `templates/<mode>/<kind>`.
    """
    norm = _normalize_mode(mode)
    here = Path(__file__).resolve().parent
    root = here / "templates" / norm
    return root / kind


def copy_fv_templates_to_case(
    case_root: Path,
    *,
    fvSchemes_src: Path,
    fvSolution_src: Path,
    overwrite: bool = True,
) -> dict[str, Path]:
    """
    Copy fvSchemes and fvSolution templates into `case_root/system/`.

    Args:
        case_root (Path): Case root directory.
        fvSchemes_src (Path): Source file for fvSchemes.
        fvSolution_src (Path): Source file for fvSolution.
        overwrite (bool): If False, keep existing destination files.

    Returns:
        dict[str, Path]: Paths of copied files: {"fvSchemes": ..., "fvSolution": ...}.

    Raises:
        FileNotFoundError: If any template source file does not exist.
    """
    case_root = Path(case_root)
    sysdir = case_root / "system"
    sysdir.mkdir(parents=True, exist_ok=True)

    fvSchemes_src = Path(fvSchemes_src)
    fvSolution_src = Path(fvSolution_src)

    if not fvSchemes_src.exists():
        raise FileNotFoundError(f"fvSchemes template not found: {fvSchemes_src}")
    if not fvSolution_src.exists():
        raise FileNotFoundError(f"fvSolution template not found: {fvSolution_src}")

    dst_schemes = sysdir / "fvSchemes"
    dst_solution = sysdir / "fvSolution"

    if dst_schemes.exists() and not overwrite:
        pass
    else:
        shutil.copy2(fvSchemes_src, dst_schemes)

    if dst_solution.exists() and not overwrite:
        pass
    else:
        shutil.copy2(fvSolution_src, dst_solution)

    return {"fvSchemes": dst_schemes, "fvSolution": dst_solution}


def patch_fvSolution_pimple(
    fvsolution_path: Path,
    pRefPoint: Optional[Tuple[float, float, float]],
    residual_value: Optional[float],
) -> Path:
    """
    Patch `PIMPLE{}` entries in an fvSolution file.

    Modifies (if present) within the `PIMPLE { ... }` block:
        - `pRefPoint` (if pRefPoint is provided)
        - `residualControl { ... }` (if residual_value is provided)

    Args:
        fvsolution_path (Path): Path to an fvSolution file to patch in-place.
        pRefPoint (tuple[float, float, float] | None): Target pRefPoint (x, y, z).
        residual_value (float | None): Target residualControl value.

    Returns:
        Path: The same fvsolution_path (patched in-place).
    """
    text = fvsolution_path.read_text(encoding="utf-8", errors="ignore")

    # find PIMPLE section
    m = re.search(r"\bPIMPLE\s*\{", text)
    if not m:
        return fvsolution_path

    start = m.start()
    i = m.end()
    depth = 0
    brace_pos = text.find("{", i - 1)
    if brace_pos == -1:
        return fvsolution_path
    i = brace_pos + 1
    depth = 1
    while i < len(text) and depth > 0:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    end = i

    pimple_block = text[start:end]
    new_block = pimple_block

    # pRefPoint
    if pRefPoint is not None:
        x, y, z = pRefPoint
        new_block = re.sub(
            r"(pRefPoint\s*)\([\s\dEe+\-\.]*\)\s*;",
            rf"\1({x:.6g} {y:.6g} {z:.6g});",
            new_block,
            flags=re.IGNORECASE,
        )

    # residualControl
    if residual_value is not None:
        val = _fmt_sci(float(residual_value))
        residual_snippet = f"""
            residualControl
            {{
                rho     {val};
                p       {val};
                p_rgh   {val};
                U       {val};
                h       {val};
                T       {val};
                G       {val};
                air     {val};
                CO2     {val};
                "(k|epsilon|omega)" {val};
            }}
        """.rstrip()

        def _replace_residual(match: re.Match) -> str:
            return residual_snippet

        new_block = re.sub(
            r"residualControl\s*\{[^}]*\}",
            _replace_residual,
            new_block,
            flags=re.IGNORECASE | re.DOTALL,
        )

    new_text = text[:start] + new_block + text[end:]
    fvsolution_path.write_text(new_text, encoding="utf-8")

    return fvsolution_path
