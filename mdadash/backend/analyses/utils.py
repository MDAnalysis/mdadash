"""
Common utils for all analyses
"""

import numpy as np
from MDAnalysis.lib.mdamath import triclinic_vectors


def get_box_matrices(unitcells, compute_inverse=True):
    """Get box matrices for an array of unitcells"""
    if (
        unitcells is None or unitcells.size == 0 or np.allclose(unitcells[:, :3], 0)
    ):  # pragma: no cover
        return None, None, False

    is_orthogonal = np.allclose(unitcells[:, 3:], 90.0)

    box_matrices = np.array([triclinic_vectors(b) for b in unitcells])

    inv_box_matrices = None
    if compute_inverse and not is_orthogonal:
        inv_box_matrices = np.linalg.inv(box_matrices)

    return box_matrices, inv_box_matrices, is_orthogonal
