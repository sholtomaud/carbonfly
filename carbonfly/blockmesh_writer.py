"""
Writers for OpenFOAM blockMesh configuration files.

This module provides helper functions to generate `blockMeshDict`
files for OpenFOAM cases, based on structured geometry definitions
and user-defined mesh parameters.

The generated dictionaries are intended to be used as the base mesh
before further refinement steps (e.g. snappyHexMesh).
"""

from __future__ import annotations

# carbonfly/blockmesh_writer.py
from math import ceil
from pathlib import Path
from typing import Optional, Tuple

from .utils import foam_header


def _cells_from_size(
    Lx: float, Ly: float, Lz: float, cell_size: float
) -> Tuple[int, int, int]:
    """
    Compute (nx, ny, nz) from target cell size (meters).

    Args:
        Lx (float): Domain length in x (m).
        Ly (float): Domain length in y (m).
        Lz (float): Domain length in z (m).
        cell_size (float): Target cell size (m), must be > 0.

    Returns:
        Tuple[int, int, int]: Number of cells (nx, ny, nz).
    """
    if cell_size <= 0:
        raise ValueError("cell_size must be > 0.")
    nx = max(1, int(ceil(Lx / cell_size)))
    ny = max(1, int(ceil(Ly / cell_size)))
    nz = max(1, int(ceil(Lz / cell_size)))
    return nx, ny, nz


def write_blockmesh_dict(
    case_root: Path,
    *,
    min_xyz: Tuple[float, float, float],
    max_xyz: Tuple[float, float, float],
    cells: Optional[Tuple[int, int, int]] = None,
    cell_size: Optional[float] = None,
    grading: Tuple[float, float, float] = (1.0, 1.0, 1.0),
    convert_to_meters: float = 1.0,
) -> Path:
    """
    Write a minimal system/blockMeshDict with a single hex block.

    This helper writes a bounding-box blockMeshDict (no edges) with one patch
    named `boundingbox` (type wall) containing all six faces.

    Args:
        case_root (Path): Case root directory (the parent of `system/`).
        min_xyz (Tuple[float, float, float]): Domain min bounds (xmin, ymin, zmin) in meters.
        max_xyz (Tuple[float, float, float]): Domain max bounds (xmax, ymax, zmax) in meters.
        cells (Optional[Tuple[int, int, int]]): Explicit (nx, ny, nz). If None, computed from `cell_size`.
        cell_size (Optional[float]): Target cell size (m). Used only when `cells` is None.
        grading (Tuple[float, float, float]): simpleGrading factors (gx, gy, gz).
        convert_to_meters (float): OpenFOAM `convertToMeters` (default 1.0).

    Returns:
        Path: Path to the written `system/blockMeshDict`.

    Raises:
        ValueError: If bounds are invalid or cell_size <= 0.
    """
    (xmin, ymin, zmin) = min_xyz
    (xmax, ymax, zmax) = max_xyz
    Lx, Ly, Lz = (xmax - xmin, ymax - ymin, zmax - zmin)
    if Lx <= 0 or Ly <= 0 or Lz <= 0:
        raise ValueError("Block dimensions must be positive (check bounds).")

    if cells is None:
        if cell_size is None:
            # fallback: ~20 cells per shortest edge
            s = max(min(Lx, Ly, Lz) / 20.0, 1e-3)
            cells = _cells_from_size(Lx, Ly, Lz, s)
        else:
            cells = _cells_from_size(Lx, Ly, Lz, cell_size)
    nx, ny, nz = map(int, cells)

    gx, gy, gz = grading

    # OpenFOAM vertex order for a hex (0..7)
    # bottom: 0(xmin,ymin,zmin) 1(xmax,ymin,zmin) 2(xmax,ymax,zmin) 3(xmin,ymax,zmin)
    # top:    4(xmin,ymin,zmax) 5(xmax,ymin,zmax) 6(xmax,ymax,zmax) 7(xmin,ymax,zmax)
    V = [
        (xmin, ymin, zmin),
        (xmax, ymin, zmin),
        (xmax, ymax, zmin),
        (xmin, ymax, zmin),
        (xmin, ymin, zmax),
        (xmax, ymin, zmax),
        (xmax, ymax, zmax),
        (xmin, ymax, zmax),
    ]

    lines = []
    lines.append(foam_header("blockMeshDict", location="system"))
    lines.append(f"convertToMeters {convert_to_meters};\n")

    # vertices
    lines.append("vertices")
    lines.append("(")
    for x, y, z in V:
        lines.append(f"    ({x:.6g} {y:.6g} {z:.6g})")
    lines.append(");\n")

    # single block
    lines.append("blocks")
    lines.append("(")
    lines.append(
        f"    hex (0 1 2 3 4 5 6 7) ({nx} {ny} {nz}) simpleGrading ({gx} {gy} {gz})"
    )
    lines.append(");\n")

    # edges (none)
    lines.append("edges")
    lines.append("(")
    lines.append(");\n")

    # boundary patches
    lines.append("boundary")
    lines.append("(")
    lines.append("    boundingbox")
    lines.append("    {")
    lines.append("        type wall;")
    lines.append("        faces")
    lines.append("        (")
    lines.append("            (0 3 2 1)")
    lines.append("            (4 5 6 7)")
    lines.append("            (1 2 6 5)")
    lines.append("            (3 0 4 7)")
    lines.append("            (0 1 5 4)")
    lines.append("            (2 3 7 6)")
    lines.append("        );")
    lines.append("    }")
    lines.append(");\n")

    # mergePatchPairs (empty)
    lines.append("mergePatchPairs")
    lines.append("(")
    lines.append(");\n")

    out = case_root / "system" / "blockMeshDict"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")

    return out
