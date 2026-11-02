"""Independent nearest-neighbor adapter for the fixed LUCID design profile.

The calculation is independently implemented as a nearest-neighbor
enthalpy/entropy sum. The hybrid table has been reconstructed from licensed
Zuber (2022) and Biopython sources; see docs/RNA_NN4_PROVENANCE.md.
This module is not a validated reproduction of the full LUCID pipeline.
"""

from __future__ import annotations

from hashlib import sha256
import math
from typing import Final


PROFILE_ID: Final = "lucid_end3_v1"
TEMPERATURE_C: Final = 22.0
_R: Final = 1.987
_GAS_MOLAR: Final = (20.0 + 50.0) / 1000.0
_SALT_CORRECTION: Final = 5

# RNA/RNA parameters, independently checked against the sources below.
# 21 entries: Zuber et al. (2022), doi:10.1093/nar/gkac261, Tables 1-2,
# Copyright The Author(s) 2022, CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
# CT/GA and GA/CT: Biopython 1.86 MeltingTemp.RNA_NN3, BSD-3-Clause option.
# Copyright 1999-2024 The Biopython Contributors; 2004-2008 Sebastian Bassi;
# 2013-2018 Markus Piotrowski. See vendor/licenses/Biopython-1.86-LICENSE.txt.
# Adaptations: subset, U->T notation, equivalent strand orientations; uncertainties omitted.
# Units: kcal/mol and cal/(mol*K), sequence/partner order. Full mapping,
# credits and hybrid/end-context limitations: docs/RNA_NN4_PROVENANCE.md.
_NN: Final[dict[str, tuple[float, float]]] = {
    "init": (4.66, 1.78), "init_at": (4.36, 13.35),
    "AA/TT": (-7.44, -20.98), "AT/TA": (-8.91, -25.22),
    "TA/AT": (-9.16, -25.40), "CA/GT": (-10.47, -27.08),
    "GT/CA": (-11.98, -31.37), "CT/GA": (-10.90, -28.50),
    "GA/CT": (-13.21, -34.90), "CG/GC": (-9.61, -23.46),
    "GC/CG": (-16.52, -42.13), "GG/CC": (-13.94, -34.41),
    "GT/TG": (-7.66, -24.11), "GG/TT": (-9.06, -28.57),
    "AG/TT": (-5.10, -16.53), "TG/AT": (-2.72, -8.08),
    "TT/AG": (-10.58, -32.19), "TG/GT": (-8.76, -27.04),
    "AT/TG": (-9.23, -27.32), "CG/GT": (-5.64, -14.83),
    "CT/GG": (-9.26, -23.64), "GG/CT": (-12.41, -34.23),
    "GT/CG": (-14.73, -40.32),
}


def _normalize(sequence: str) -> str:
    if not isinstance(sequence, str):
        raise ValueError("sequence must be text")
    normalized = "".join(sequence.split()).upper().replace("T", "U")
    if len(normalized) < 2 or any(base not in "ACGU" for base in normalized):
        raise ValueError("sequence must contain at least two unambiguous A/C/G/U bases")
    return normalized


def _paired_partner(sequence: str) -> str:
	return sequence.translate(str.maketrans("ACGT", "TGCA"))


def _duplex_delta_g(sequence: str) -> float:
    dna_notation = sequence.replace("U", "T")
    partner = _paired_partner(dna_notation)
    enthalpy, entropy = _NN["init"]

    at_ends = sum(base in "AT" for base in (dna_notation[0], dna_notation[-1]))
    enthalpy += at_ends * _NN["init_at"][0]
    entropy += at_ends * _NN["init_at"][1]

    for index in range(len(dna_notation) - 1):
        key = f"{dna_notation[index:index + 2]}/{partner[index:index + 2]}"
        reverse_key = f"{partner[index:index + 2][::-1]}/{dna_notation[index:index + 2][::-1]}"
        params = _NN.get(key) or _NN.get(reverse_key)
        if params is None:
            raise ValueError(f"unsupported nearest-neighbor step at position {index}")
        enthalpy += params[0]
        entropy += params[1]

    # LUCID saltcorr=5 adjusts entropy using monovalent salt concentration.
    entropy += 0.368 * (len(dna_notation) - 1) * math.log(_GAS_MOLAR)
    energy = enthalpy - (273.15 + TEMPERATURE_C) * entropy / 1000.0
    if not math.isfinite(energy):
        raise ValueError("nearest-neighbor calculation was not finite")
    return float(energy)


def energy_profile(sequence: str) -> dict[str, object]:
    """Return exploratory duplex/end energies under the local lucid_end3_v1 profile."""
    normalized = _normalize(sequence)
    if len(normalized) != 21:
        raise ValueError("energy_profile requires exactly one 21-nt k-mer")
    sense = _duplex_delta_g(normalized[:3])
    antisense_start = max(0, len(normalized) - 5)
    antisense_end = max(antisense_start + 2, len(normalized) - 2)
    antisense = _duplex_delta_g(normalized[antisense_start:antisense_end])
    return {
        "profile_id": PROFILE_ID,
        "parameter_set": "LUCID RNA_NN4; nearest-neighbor data, independent implementation",
        "temperature_c": TEMPERATURE_C,
        "sodium_mm": 20,
        "potassium_mm": 50,
        "magnesium_mm": 0,
        "salt_correction": _SALT_CORRECTION,
        "concentration_dnac1_nm": 25,
        "concentration_dnac2_nm": 0,
        "duplex_dg": _duplex_delta_g(normalized),
        "sense_end_dg": sense,
        "antisense_end_dg": antisense,
        "delta": antisense - sense,
        "sequence_sha256": sha256(normalized.encode("ascii")).hexdigest(),
    }


def window_weight(delta: float, *, lambda_value: int) -> int:
    """Apply the explicit exploratory LUCID end-stability weighting hypothesis."""
    if lambda_value not in (0, 1):
        raise ValueError("lambda_value must be 0 or 1")
    if not math.isfinite(delta):
        raise ValueError("delta must be finite")
    return 1 + lambda_value * int(delta >= 1.0)
