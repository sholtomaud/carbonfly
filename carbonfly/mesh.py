"""
Mesh utilities for Rhino-based OpenFOAM workflows.

This module provides helper functions to convert Rhino geometries into
triangle meshes and export them in formats suitable for OpenFOAM.

.. note::
   This module depends on the RhinoCommon API and can only be used
   inside Rhino / Grasshopper. The ``Rhino`` module is provided by Rhino.
"""

from __future__ import annotations

# carbonfly/mesh.py
try:
    import Rhino
except ImportError:
    Rhino = None

from typing import Iterable, Tuple, List


def _require_rhino() -> None:
    """Raise a clear error if RhinoCommon is not available."""
    if Rhino is None:
        raise RuntimeError("Rhino is required for geometry operations.")


def brep_to_mesh(brep: Rhino.Geometry.Brep) -> Rhino.Geometry.Mesh:
    """
    Convert a Rhino Brep into a single unified Mesh.

    Args:
        brep (Rhino.Geometry.Brep): Input Brep geometry.

    Returns:
        Rhino.Geometry.Mesh: A unified, triangulated mesh, or None if meshing failed.
    """
    _require_rhino()
    mp = Rhino.Geometry.MeshingParameters.Default
    lst = Rhino.Geometry.Mesh.CreateFromBrep(brep, mp)
    if not lst:
        return None
    m = Rhino.Geometry.Mesh()
    for x in lst:
        m.Append(x)
    m.UnifyNormals()
    m.Compact()
    if m.Faces.QuadCount > 0:
        m.Faces.ConvertQuadsToTriangles()
    m.Normals.ComputeNormals()

    return m


def mesh_triangles(mesh):
    """
    Iterate over all triangular faces of a Rhino Mesh and yield triangle vertices + normals.
    If a face is a quad, it will be triangulated using MeshFace.Triangulate().

    Args:
        mesh (Rhino.Geometry.Mesh): Input mesh (ideally triangulated).

    Yields:
        tuple: ((ax,ay,az), (bx,by,bz), (cx,cy,cz), (nx,ny,nz))
               where (a,b,c) are vertex coordinates and (n) is the face normal.
    """
    _require_rhino()
    V, F = mesh.Vertices, mesh.Faces
    for i in range(F.Count):
        f = F[i]
        tris = [(f.A, f.B, f.C)] if f.IsTriangle else list(f.Triangulate())
        for a, b, c in tris:
            pa, pb, pc = V[a], V[b], V[c]
            v1 = Rhino.Geometry.Vector3f(pb.X - pa.X, pb.Y - pa.Y, pb.Z - pa.Z)
            v2 = Rhino.Geometry.Vector3f(pc.X - pa.X, pc.Y - pa.Y, pc.Z - pa.Z)
            n = Rhino.Geometry.Vector3f.CrossProduct(v1, v2)
            if n.Length > 1e-20:
                n.Unitize()
            yield (
                (pa.X, pa.Y, pa.Z),
                (pb.X, pb.Y, pb.Z),
                (pc.X, pc.Y, pc.Z),
                (n.X, n.Y, n.Z),
            )


def _scale_factor(unit: str) -> float:
    """
    Return scale factor converting input geometry units to meters.

    Args:
        unit: Unit label. Supported: "mm", "cm", "m".

    Returns:
        Scale factor to convert coordinates to meters.

    Raises:
        ValueError: If unit is not one of "mm", "cm", "m".
    """
    u = (unit or "mm").lower()
    if u == "mm":
        return 1e-3
    if u == "cm":
        return 1e-2
    if u == "m":
        return 1.0
    raise ValueError("unit must be 'mm'|'cm'|'m'")


def write_multi_solid_ascii_stl(
    out_path, named_meshes: Iterable[Tuple[str, Rhino.Geometry.Mesh]], unit: str
):
    """
    Write a multi-solid ASCII STL file.

    Each entry in `named_meshes` becomes one `solid <name> ... endsolid <name>`
    block. Geometry is scaled to meters using `unit`.

    Args:
        out_path: Output path (Path or str).
        named_meshes: Iterable of (name, mesh) pairs.
        unit: Unit label for input meshes ("mm" | "cm" | "m").

    Returns:
        Path to the written STL file.
    """
    from pathlib import Path

    sf = _scale_factor(unit)
    lines: List[str] = []
    for nm, mesh in named_meshes:
        name = str(nm).replace(" ", "_")
        lines.append(f"solid {name}")
        for (ax, ay, az), (bx, by, bz), (cx, cy, cz), (nx, ny, nz) in mesh_triangles(
            mesh
        ):
            lines.append(f"  facet normal {nx:.6e} {ny:.6e} {nz:.6e}")
            lines.append("    outer loop")
            lines.append(f"      vertex {ax*sf:.6e} {ay*sf:.6e} {az*sf:.6e}")
            lines.append(f"      vertex {bx*sf:.6e} {by*sf:.6e} {bz*sf:.6e}")
            lines.append(f"      vertex {cx*sf:.6e} {cy*sf:.6e} {cz*sf:.6e}")
            lines.append("    endloop")
            lines.append("  endfacet")
        lines.append(f"endsolid {name}")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path
