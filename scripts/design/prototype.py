"""Small, real Go + nearest-neighbor integration smoke prototype."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services.simulator_api.design.thermo import energy_profile, window_weight


GO_SOURCE = ROOT / "vendor" / "dsrnamax"


def run(targets: Path, lambda_value: int) -> dict[str, object]:
    go = os.environ.get("DICER_GO") or shutil.which("go")
    if not go:
        raise RuntimeError("Go toolchain not found; set DICER_GO to its executable path")
    with tempfile.TemporaryDirectory(prefix="dicer-design-prototype-") as tmp:
        workspace = Path(tmp)
        binary = workspace / ("dsrnamax.exe" if os.name == "nt" else "dsrnamax")
        subprocess.run([go, "build", "-o", str(binary), "."], cwd=GO_SOURCE,
                       check=True, capture_output=True, text=True, timeout=90)
        discovered = subprocess.run(
            [str(binary), "discover", "--targets", str(targets.resolve()), "--k", "21"],
            check=True, capture_output=True, text=True, timeout=20,
        )
        discovery = json.loads(discovered.stdout)
        profiles = {
            item["sequence_rna"]: energy_profile(item["sequence_rna"])
            for item in discovery["kmers"]
        }
        weights = {
            sequence: window_weight(profile["delta"], lambda_value=lambda_value)
            for sequence, profile in profiles.items()
        }
        kmers_path = workspace / "kmers.json"
        request_path = workspace / "request.json"
        kmers_path.write_text(json.dumps(discovery, sort_keys=True), encoding="utf-8")
        request_path.write_text(json.dumps({
            "schema_version": 1, "lambda": lambda_value, "weights": weights,
        }, sort_keys=True), encoding="utf-8")
        assembled = subprocess.run(
            [str(binary), "assemble", "--kmers", str(kmers_path), "--request", str(request_path)],
            check=True, capture_output=True, text=True, timeout=20,
        )
        result = json.loads(assembled.stdout)
        return {
            "design_schema_version": 1,
            "dsRNAmax_source_commit": "674b5b513248ea551dcc9217f1059d593f827766",
            "dsRNAmax_version": "1.1.15",
            "thermo_profile": "lucid_end3_v1",
            "thermo_implementation": "independent nearest-neighbor; LUCID GPL source not copied",
            "lambda": lambda_value,
            "genes": discovery["genes"],
            "discovered_kmers": len(discovery["kmers"]),
            "energies": profiles,
            "weights": weights,
            "selection": result,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("targets", type=Path, help="DNA FASTA with targets of at least 21 nt")
    parser.add_argument("--lambda", dest="lambda_value", type=int, choices=(0, 1), default=1)
    args = parser.parse_args()
    print(json.dumps(run(args.targets, args.lambda_value), ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
