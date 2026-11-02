"""Safe, versioned JSON subprocess adapter for the pinned dsRNAmax Go fork."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import tempfile
import time
from typing import Any


class DsRNAMaxError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class DsRNAMaxAdapter:
    binary_path: Path | str | None = None
    cancel_check: Any = None

    @property
    def source_dir(self) -> Path:
        return Path(__file__).resolve().parents[3] / "vendor" / "dsrnamax"

    def _source_hash(self) -> str:
        digest = hashlib.sha256()
        for path in sorted(self.source_dir.glob("*.go")) + [self.source_dir / "go.mod", self.source_dir / "go.sum"]:
            digest.update(path.name.encode("utf-8"))
            digest.update(path.read_bytes())
        return digest.hexdigest()

    def executable(self) -> Path:
        configured = self.binary_path or os.environ.get("DSRNAMAX_BINARY")
        if configured:
            binary = Path(configured).resolve()
            if not binary.is_file():
                raise DsRNAMaxError("dsrnamax_unavailable", "configured dsRNAmax binary does not exist")
            return binary
        source = self.source_dir
        if not source.is_dir():
            raise DsRNAMaxError("dsrnamax_unavailable", "pinned dsRNAmax source is missing")
        go = os.environ.get("DICER_GO") or shutil.which("go")
        if not go:
            raise DsRNAMaxError("dsrnamax_unavailable", "Go is required to build the dsRNAmax adapter")
        suffix = ".exe" if os.name == "nt" else ""
        cache = Path(tempfile.gettempdir()) / "dicer-lab-dsrnamax"
        cache.mkdir(parents=True, exist_ok=True)
        binary = cache / f"dsrnamax-{self._source_hash()[:20]}{suffix}"
        if binary.is_file():
            return binary
        staging_dir = Path(tempfile.mkdtemp(prefix="build-", dir=cache))
        staging = staging_dir / binary.name
        try:
            completed = self._execute([str(go), "build", "-trimpath", "-o", str(staging), "."], cwd=source)
            if completed.returncode != 0:
                raise DsRNAMaxError("dsrnamax_build_failed", (completed.stderr.strip() or "go build failed")[:1000])
            os.replace(staging, binary)
        except (OSError, subprocess.SubprocessError) as exc:
            stderr = getattr(exc, "stderr", "") or ""
            raise DsRNAMaxError("dsrnamax_build_failed", (stderr.strip() or str(exc))[:1000]) from exc
        finally:
            shutil.rmtree(staging_dir, ignore_errors=True)
        return binary

    @staticmethod
    def _write_json(directory: Path, name: str, data: dict[str, Any]) -> Path:
        path = directory / name
        path.write_text(json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False), encoding="utf-8")
        return path

    def _run_json(self, mode: str, paths: list[Path], references: list[Path] = ()) -> dict[str, Any]:
        command = [str(self.executable()), mode]
        if mode == "discover":
            command.extend(("--targets", str(paths[0].resolve())))
            command.extend(("--k", "21"))
        elif mode == "assemble":
            command.extend(("--kmers", str(paths[0].resolve()), "--request", str(paths[1].resolve())))
        else:
            raise DsRNAMaxError("dsrnamax_invalid_mode", "unsupported adapter mode")
        if mode in {"discover", "screen"}:
            for path in references:
                command.extend(("--offtargets", str(path.resolve())))
        completed = self._execute(command)
        if completed.returncode != 0:
            detail = (completed.stderr or "dsRNAmax failed")[-1000:]
            raise DsRNAMaxError("dsrnamax_failed", detail)
        try:
            result = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise DsRNAMaxError("dsrnamax_invalid_json", "dsRNAmax returned invalid JSON") from exc
        if not isinstance(result, dict) or result.get("schema_version") != 1:
            raise DsRNAMaxError("dsrnamax_invalid_schema", "dsRNAmax returned an unsupported schema")
        return result

    def discover(self, targets_fasta: Path, reference_fastas: list[Path] = ()) -> dict[str, Any]:
        return self._run_json("discover", [targets_fasta], reference_fastas)

    def assemble(self, directory: Path, request: dict[str, Any]) -> dict[str, Any]:
        request_path = self._write_json(directory, "kmer-assembly-request.json", request)
        return self._run_json("assemble", [directory / "eligible-kmers.json", request_path])

    def build_blocks(self, directory: Path, request: dict[str, Any]) -> dict[str, Any]:
        request_path = self._write_json(directory, "block-assembly-request.json", request)
        command = [str(self.executable()), "blocks", "--request", str(request_path.resolve())]
        return self._run_explicit_json(command)

    def screen(self, directory: Path, candidates: list[dict[str, str]], reference_fastas: list[Path]) -> dict[str, Any]:
        request_path = self._write_json(directory, "candidate-screen-request.json", {
            "schema_version": 1, "candidates": candidates,
        })
        command = [str(self.executable()), "screen", "--request", str(request_path.resolve())]
        for path in reference_fastas:
            command.extend(("--offtargets", str(path.resolve())))
        return self._run_explicit_json(command)

    def _run_explicit_json(self, command: list[str]) -> dict[str, Any]:
        completed = self._execute(command)
        if completed.returncode != 0:
            raise DsRNAMaxError("dsrnamax_failed", (completed.stderr or "dsRNAmax failed")[-1000:])
        try:
            result = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise DsRNAMaxError("dsrnamax_invalid_json", "dsRNAmax returned invalid JSON") from exc
        if not isinstance(result, dict) or result.get("schema_version") != 1:
            raise DsRNAMaxError("dsrnamax_invalid_schema", "dsRNAmax returned an unsupported schema")
        return result

    def _execute(self, command: list[str], *, cwd: Path | None = None):
        with (tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as stdout,
              tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as stderr):
            try:
                child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stdout,
                                         stderr=stderr, shell=False, cwd=cwd,
                                         creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0),
                                         start_new_session=(os.name != "nt"))
            except OSError as exc:
                raise DsRNAMaxError("dsrnamax_execution_failed", str(exc)) from exc
            while child.poll() is None:
                if self.cancel_check is not None and self.cancel_check():
                    self._kill_child(child)
                    child.wait()
                    raise DsRNAMaxError("job_cancelled", "dsRNAmax was cancelled")
                # Polling keeps manual cancellation responsive; it imposes no
                # execution deadline on the scientific subprocess.
                time.sleep(0.2)
            child.wait()
            stdout.seek(0)
            stderr.seek(0)
            return subprocess.CompletedProcess(command, child.returncode, stdout.read(), stderr.read())

    @staticmethod
    def _kill_child(child: subprocess.Popen):
        try:
            if os.name == "nt":
                child.kill()
            else:
                os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
