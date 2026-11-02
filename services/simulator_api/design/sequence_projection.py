"""Project ideal, aligned RNA fragments onto a candidate's two 5-to-3 strands."""
from __future__ import annotations

def project_interval(sequence_rna: str, start: int, end: int) -> dict:
    if not (0 <= start < end <= len(sequence_rna)):
        raise ValueError("fragment interval lies outside the candidate")
    fragment = sequence_rna[start:end]
    antisense = fragment.translate(str.maketrans("ACGU", "UGCA"))[::-1]
    return {"sense_5to3": fragment, "antisense_5to3": antisense,
            "sense_coordinates": [start, end],
            "antisense_coordinates": [len(sequence_rna)-end, len(sequence_rna)-start],
            "alignment_model": "ideal_aligned_fragment"}

def annotate_trajectory(payload: dict, sequence_rna: str) -> dict:
    if len(sequence_rna) != payload["config"]["construct"]["length_nt"]:
        raise ValueError("sequence snapshot length does not match trajectory geometry")
    for event in payload["events"]:
        if event["kind"] == "cut":
            event["sequence"] = project_interval(sequence_rna, event["start"], event["end"])
    remainder = payload["remainder"]
    if remainder["start"] < remainder["end"]:
        remainder["sequence"] = project_interval(sequence_rna, remainder["start"], remainder["end"])
    return payload
