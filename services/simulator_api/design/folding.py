"""Reproducible ViennaRNA 2.7.2 folding summaries for RNA design candidates."""
from __future__ import annotations

import math
from typing import Any

PROFILE = {
    "name": "vienna_turner2004_v1", "viennarna_version": "2.7.2",
    "temperature_c": 22.0, "dangles": 2, "salt_m": 0.07,
    "salt_note": "explicit monovalent salt convention; not LUCID saltcorr",
    "parameters": "Turner2004",
}


class FoldingError(ValueError):
    pass


def _rna_module():
    try:
        import RNA
    except ImportError as exc:
        raise FoldingError("ViennaRNA 2.7.2 is required") from exc
    if getattr(RNA, "__version__", None) != PROFILE["viennarna_version"]:
        raise FoldingError("unexpected ViennaRNA version")
    return RNA


def fold_candidate(sequence_rna: str) -> dict[str, Any]:
    RNA = _rna_module()
    sequence = sequence_rna.upper().replace("T", "U")
    if len(sequence) < 21 or any(base not in "ACGU" for base in sequence):
        raise FoldingError("candidate must contain at least 21 unambiguous RNA bases")
    RNA.params_load_RNA_Turner2004()
    md = RNA.md()
    md.temperature = PROFILE["temperature_c"]
    md.dangles = PROFILE["dangles"]
    md.salt = PROFILE["salt_m"]
    antisense = sequence.translate(str.maketrans("ACGU", "UGCA"))[::-1]
    strands = {"sense": sequence, "antisense": antisense}
    monomers = {}
    for name, strand in strands.items():
        fc = RNA.fold_compound(strand, md)
        structure, mfe = fc.mfe()
        fc.exp_params_rescale(mfe)
        pf_structure, ensemble_energy = fc.pf()
        centroid, centroid_distance = fc.centroid()
        bpp = fc.bpp()
        paired = [sum(float(bpp[i][j]) for j in range(1, len(strand) + 1) if j != i)
                  for i in range(1, len(strand) + 1)]
        monomers[name] = {"sequence_rna": strand, "mfe_structure": structure,
                          "mfe_kcal_mol": float(mfe), "partition_structure": pf_structure,
                          "ensemble_free_energy_kcal_mol": float(ensemble_energy),
                          "centroid_structure": centroid,
                          "centroid_mean_bp_distance": float(centroid_distance),
                          "paired_probability_by_position": paired}
    dimer = RNA.fold_compound(sequence + "&" + antisense, md)
    dimer_structure, dimer_mfe = dimer.mfe_dimer()
    # Dimer fold_compound uses '&' in its input, but eval_structure expects
    # the separator-free concatenated dot-bracket representation.
    perfect = "(" * len(sequence) + ")" * len(sequence)
    perfect_dg = float(dimer.eval_structure(perfect))
    values = [dimer_mfe, perfect_dg, *(monomers[s]["mfe_kcal_mol"] for s in monomers)]
    if not all(math.isfinite(float(value)) for value in values):
        raise FoldingError("ViennaRNA returned a non-finite energy")
    gap_kcal_mol = perfect_dg - float(dimer_mfe)
    gap = gap_kcal_mol / len(sequence)
    if gap < -1e-7:
        raise FoldingError("dimer MFE is less stable than the perfect duplex evaluation")
    # Keep the unrounded energy difference for interpretation. A zero P is
    # expected when the full-length perfect duplex is the MFE structure.
    perfect_duplex_is_mfe = dimer_structure.replace("&", "") == perfect
    return {"profile": dict(PROFILE), "monomers": monomers,
            "dimer": {"sequence_order": "sense&antisense_5to3",
                      "mfe_structure": dimer_structure, "mfe_kcal_mol": float(dimer_mfe),
                      "perfect_duplex_structure": perfect,
                      "perfect_duplex_kcal_mol": perfect_dg,
                      "gap_kcal_mol": gap_kcal_mol,
                      "perfect_duplex_is_mfe": perfect_duplex_is_mfe,
                      "gap_per_nt": max(0.0, gap)}}
