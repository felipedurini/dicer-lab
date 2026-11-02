"""Worker entry point and bounded artifact publication for sequence design."""
from __future__ import annotations
import hashlib, json, os, shutil
from pathlib import Path
from .dsrnamax import DsRNAMaxAdapter
from .pipeline import DesignPipeline
from .references import ReferenceCatalog
from .schemas import DesignRequest

def execute_design(request_data: dict, data_dir: str, job_id: str, attempt: int, store=None, stop_event=None) -> dict:
    root = Path(data_dir).resolve()
    work = root / "design" / job_id / str(attempt)
    catalog = ReferenceCatalog(root / "references")
    is_cancelled = (lambda: (store is not None and store.is_cancel_requested(job_id)) or
                    (stop_event is not None and stop_event.is_set()))
    report = (lambda progress: store.set_design_progress(job_id, progress)) if store else None
    result = DesignPipeline(DsRNAMaxAdapter(cancel_check=is_cancelled), catalog).run(
        DesignRequest.model_validate(request_data), work_dir=work, cancel_check=is_cancelled, progress=report)
    exports = {
        "design-manifest.json": json.dumps(result, sort_keys=True, indent=2, allow_nan=False).encode(),
        "kmers.jsonl": "".join(json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
                                 for row in json.loads((work / "eligible-kmers.json").read_text(encoding="utf-8"))["kmers"]).encode(),
        "candidates.fasta": "".join(f">{c['candidate_id']}\n{c['sequence_rna']}\n" for c in result["candidates"]).encode(),
        "ranking.csv": ("rank,candidate_id,minimum_gene_coverage,high_stability_window_fraction,dimer_gap_per_nt\n" + "".join(f"{c['rank']},{c['candidate_id']},{c['metrics']['minimum_gene_coverage']},{c['metrics']['high_stability_window_fraction']},{c['metrics']['dimer_gap_per_nt']}\n" for c in result["candidates"])).encode()
    }
    artifact_dir = root / "artifacts" / job_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    records = []
    total_bytes = sum(len(payload) for payload in exports.values())
    if total_bytes > 20 * 1024 * 1024:
        raise ValueError("design artifacts exceed the 20 MiB job limit")
    for name, payload in exports.items():
        temp = artifact_dir / (name + ".tmp")
        temp.write_bytes(payload); os.replace(temp, artifact_dir / name)
        records.append({"name": name, "relative_path": str((Path("artifacts") / job_id / name).as_posix()),
                        "sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)})
    result["artifacts"] = [{"name": r["name"], "sha256": r["sha256"], "bytes": r["bytes"]} for r in records]
    return {"result": result, "artifacts": records}

def verify_artifact(data_dir: str, record: dict) -> bytes:
    root = Path(data_dir).resolve()
    relative = Path(record["relative_path"])
    raw_path = root / relative
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("artifact path invalid")
    current = raw_path
    while current != root:
        if current.is_symlink():
            raise ValueError("artifact path invalid")
        current = current.parent
    try:
        path = raw_path.resolve(strict=True)
    except OSError as exc:
        raise ValueError("artifact path invalid") from exc
    if root not in path.parents or not path.is_file():
        raise ValueError("artifact path invalid")
    payload = path.read_bytes()
    if len(payload) != record["bytes"] or hashlib.sha256(payload).hexdigest() != record["sha256"]:
        raise ValueError("artifact checksum mismatch")
    return payload

def delete_job_artifacts(data_dir: str, job_id: str) -> None:
    root = (Path(data_dir).resolve() / "artifacts").resolve()
    target = (root / job_id).resolve()
    if root not in target.parents:
        raise ValueError("artifact path invalid")
    shutil.rmtree(target, ignore_errors=True)
