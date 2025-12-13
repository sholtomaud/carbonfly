"""
Writers for OpenFOAM `constant/` configuration files.

This module provides helper functions to populate the `constant/` directory
of an OpenFOAM case using template dictionaries shipped with carbonfly.
"""

from __future__ import annotations

# carbonfly/constant_writer.py
from pathlib import Path


def write_constant_files(case_root: Path):
    """
    Copy standard `constant/` dictionaries into the case folder.

    This writes a minimal set of OpenFOAM dicts under `case_root/constant/`,
    using template files shipped with carbonfly. Existing files are not
    overwritten.

    Args:
        case_root (Path): Case root directory.
    """
    const_dir = case_root / "constant"
    const_dir.mkdir(parents=True, exist_ok=True)

    resources = {
        "fvModels": "templates/constant/fvModels",
        "g": "templates/constant/g",
        "momentumTransport": "templates/constant/momentumTransport",
        "physicalProperties": "templates/constant/physicalProperties",
        "pRef": "templates/constant/pRef",
        "radiationProperties": "templates/constant/radiationProperties",
        "combustionProperties": "templates/constant/combustionProperties",
    }

    for name, rel_path in resources.items():
        src = Path(__file__).parent / rel_path
        dst = const_dir / name
        if not dst.exists():
            dst.write_text(src.read_text())


def write_residuals_file(case_root: Path):
    """
    Copy the standard `system/residuals` file into the case folder.

    Uses the template shipped with carbonfly. If the destination exists,
    it is not overwritten.

    Args:
        case_root (Path): Case root directory.

    Raises:
        FileNotFoundError: If the residuals template file cannot be found.
    """
    sys_dir = case_root / "system"
    sys_dir.mkdir(parents=True, exist_ok=True)

    src = Path(__file__).parent / "templates" / "residuals" / "residuals"
    dst = sys_dir / "residuals"

    if not src.exists():
        raise FileNotFoundError(f"Residuals template not found: {src}")

    if not dst.exists():
        dst.write_text(src.read_text())
