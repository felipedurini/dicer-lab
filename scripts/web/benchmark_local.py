"""Measure local API queue wall-clock time for the documented synthetic 315 nt.

Start the API and Next app first. This uses only synthetic constructs and saves no
result unless --output is supplied. The server retains jobs in its local SQLite DB.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import platform
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import uuid

import numpy as np


def request_json(url: str, *, method: str = "GET", payload: dict | None = None,
                 idempotency_key: str | None = None) -> tuple[int, dict]:
    body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode()
    headers = {"content-type": "application/json", "origin": "http://127.0.0.1:3000"}
    if idempotency_key:
        headers["idempotency-key"] = idempotency_key
    request = Request(url, data=body, method=method, headers=headers)
    try:
        with urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        return error.code, json.loads(error.read())


def run_case(base_url: str, molecules: int) -> dict:
    construct = {"length_nt":315,"phase_origin_nt":0,"segments":[
        {"segment_id":f"seg_{name}","gene_id":f"gene_{name}","start":index*105,"end":(index+1)*105}
        for index,name in enumerate("abc")
    ]}
    request = {
        "web_schema_version":1,"label":f"Benchmark sintético {molecules}","construct":construct,
        "n_molecules":molecules,"f_left":0.5,"p22":0.5,
        "scenarios":[
            {"id":"baseline","label":"Epsilon constante 0.10","seed":101,
             "epsilon":{"type":"constant","schema_version":1,"epsilon":0.1}},
            {"id":"variable","label":"Epsilon por tramos","seed":202,
             "epsilon":{"type":"piecewise","schema_version":1,"breakpoints":[106,211],"values":[0.2,0.1,0.05]}},
        ],
        "baseline_id":"baseline","alpha_family":0.05,"compute_exact":False,
    }
    start = time.perf_counter()
    status, job = request_json(base_url+"/api/v1/jobs", method="POST", payload=request,
                              idempotency_key=str(uuid.uuid4()))
    if status != 202:
        raise RuntimeError(f"No se pudo encolar el benchmark: HTTP {status}: {job}")
    while time.perf_counter() - start < 1800:
        time.sleep(0.5)
        status, job = request_json(base_url+f"/api/v1/jobs/{job['id']}")
        if status != 200:
            raise RuntimeError(f"No se pudo consultar el trabajo: HTTP {status}: {job}")
        if job["state"] in {"succeeded","failed","cancelled"}:
            break
    elapsed = time.perf_counter() - start
    if job["state"] != "succeeded":
        raise RuntimeError(f"Trabajo {job['state']}: {job.get('error')}")
    _, result = request_json(base_url+f"/api/v1/jobs/{job['id']}/results")
    scenarios = []
    for scenario in result["scenarios"]:
        summary = scenario["summary"]
        counts = dict((int(k), v) for k, v in summary["length_counts"])
        gene_crossing = next((metric for metric in scenario["metrics"]
                              if metric["key"] == "gene_crossing" and metric["scope"] == "global"), None)
        scenarios.append({
            "id":scenario["id"],"label":scenario["label"],"seed":scenario["config"]["seed"],
            "molecules":summary["n_molecules"],"products":summary["n_products"],
            "length_counts":counts,
            "proportion_21":counts[21]/summary["n_products"] if summary["n_products"] else None,
            "gene_crossing_products":gene_crossing["numerator"] if gene_crossing else None,
            "gene_crossing_proportion":gene_crossing["value"] if gene_crossing else None,
        })
    return {"n_molecules_per_scenario":molecules,"scenario_count":2,"wall_seconds":elapsed,
            "throughput_molecules_per_second":(molecules*2)/elapsed,"scenarios":scenarios,
            "comparison":result["comparisons"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--web-url", default="http://127.0.0.1:3000")
    parser.add_argument("--output")
    args = parser.parse_args()
    report = {"measured_at_utc":datetime.now(timezone.utc).isoformat(),
              "python":platform.python_version(),"numpy":np.__version__,
              "node":"Node.js 24 (project environment)","host":"local development machine",
              "method":"HTTP BFF + FastAPI + spawned SQLite worker; polling until terminal result",
              "construct":"315 nt; three contiguous segments of 105 nt; genes A/B/C",
              "cases":[run_case(args.web_url, count) for count in (5000,50000)]}
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        with open(args.output,"w",encoding="utf-8",newline="\n") as stream:
            stream.write(text+"\n")


if __name__ == "__main__":
    main()
