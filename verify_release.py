"""One-command reproducible release checks; distinguishes tested from untested.

Runs without Streamlit or internet. 'Live public download' and 'Streamlit UI'
are explicitly NOT claimed as passed. Writes release_verification.json in root.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import subprocess
import sqlite3
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from fdd.sources import get_statsbomb_events
from fdd.service import analyze_statsbomb
from fdd.evaluation import evaluate_injection
from pipeline import run_statsbomb, run_metrica
from demo_report import build_html_report

ROOT=Path(__file__).resolve().parent


def verify(*, run_tests: bool=True, report_path: str | Path | None = None) -> dict:
    findings={"verified_at_utc":datetime.now(timezone.utc).isoformat(),
              "python_version":sys.version.split()[0], "checks":{},
              "unverified":["Live public StatsBomb downloads", "Live public Metrica downloads",
                            "Streamlit user-interface interaction", "Real-world QA precision/recall",
                            "Match-video validation"]}
    if run_tests:
        proc=subprocess.run([sys.executable,"-m","pytest","-q","--cov=fdd","--cov-report=term"],
                            cwd=ROOT, capture_output=True,text=True)
        findings["checks"]["pytest"]={"passed":proc.returncode==0,
                                     "exit_code":proc.returncode,
                                     "log_excerpt":(proc.stdout+proc.stderr)[-2400:]}
        if proc.returncode:
            raise RuntimeError("Pytest failed: "+(proc.stdout+proc.stderr)[-1200:])
    with TemporaryDirectory(prefix="fdd_verify_") as tmp:
        sa=run_statsbomb(demo=True,out=tmp)
        ma=run_metrica(demo=True,out=tmp)
        for run, table, minimum in ((sa,"events",150),(ma,"reconciliation",25)):
            db=Path(run["database"])
            if not db.exists():
                raise AssertionError(f"SQL file was not created: {db}")
            with sqlite3.connect(db) as conn:
                rows=conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                q=conn.execute('SELECT COUNT(*) FROM investigation_queue').fetchone()[0]
                m=conn.execute('SELECT COUNT(*) FROM dataset_metrics').fetchone()[0]
            if rows < minimum or m < 3:
                raise AssertionError(f"Expected SQL rows in {db}: {rows} {m}")
            findings["checks"][run["provider"]+"_pipeline"]={
                "passed":True,"events_or_comparisons":rows,"ranked_queue_items":q,
                "metrics":m, "sql":True,"csv":(db.parent/f"{table}.csv").exists(),
                "manifest":(db.parent/"manifest.json").exists(),
                "fixture_is_synthetic":True,
            }
        # The benchmark checks exact *newly fired* rules rather than any old flag.
        events=get_statsbomb_events(path=ROOT/"examples/statsbomb_demo.json")
        benchmark=evaluate_injection(events)
        if benchmark["injected"]<20 or benchmark["detected_expected_rule"]!=benchmark["injected"]:
            raise AssertionError("Mutation benchmark did not pass exact-rule checks")
        findings["checks"]["controlled_mutation_benchmark"]={
            "passed":True,"injected":benchmark["injected"],
            "exact_rule_detections":benchmark["detected_expected_rule"],
            "note":"Synthetic errors, not a claim of operational recall",
        }
    html=build_html_report(report_path or ROOT/"demo_report.html")
    contents=html.read_text(encoding="utf-8")
    required=("SYNTHETIC DATA ONLY","Event-to-tracking reconciliation","Football Data Detective", "plotly")
    if len(contents)<200_000 or not all(x in contents for x in required):
        raise AssertionError("Standalone HTML report is incomplete")
    findings["checks"]["standalone_report"]={"passed":True,"bytes":html.stat().st_size,
                                               "note":"HTML generated; browser rendering separately tested"}
    findings["result"]="PASS (offline core only)"
    return findings


if __name__=="__main__":
    parser=argparse.ArgumentParser(description="Verify the offline core, export pipeline and report")
    parser.add_argument("--skip-tests",action="store_true")
    args=parser.parse_args()
    result=verify(run_tests=not args.skip_tests)
    output=ROOT/"release_verification.json"
    output.write_text(json.dumps(result,indent=2),encoding="utf-8")
    print("PASS: Offline core and generated evidence report. Log:",output)
    for k,v in result["checks"].items():
        print(f"  {'PASS' if v['passed'] else 'FAIL'} {k}")
    print("NOT VERIFIED:", "; ".join(result["unverified"]))
