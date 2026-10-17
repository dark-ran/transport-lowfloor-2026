"""Auditable receipt created only AFTER the full pipeline and tests succeed."""
from pathlib import Path
import hashlib
import importlib.metadata as md
import json
import os
import platform
import sys
import pandas as pd

ROOT=Path(__file__).resolve().parent
RESULTS=ROOT/"results"
REQUIRED=[
 "cap_equity_summary.csv","cap_equity_audit.json","headway_matched_routes.csv",
 "headway_proxy_sensitivity.csv","headway_proxy_metadata.json",
 "headway_proxy_audit.json",
 "headway_policy_coverage.csv","feasibility_assumption_stress.csv",
 "feasibility_assumption_allocations.csv","feasibility_assumption_metadata.json",
 "toy_greedy_exact.csv","toy_greedy_exact_summary.json",
 "route_case_brief.md","cap5_route_pilot_candidates.csv",
 "cap5_route_marginal_pairs.csv",
 "v3_denominator_multiroute.csv","v3_pair_classification.csv",
 "v3_denominator_metadata.json","v3_denominator_audit.json",
 "v3_policy_brief.md"
]


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    files=[RESULTS/name for name in REQUIRED]
    for file in files:
        assert file.is_file() and file.stat().st_size>0, str(file)
    eq=json.loads((RESULTS/"cap_equity_audit.json").read_text(encoding="utf-8"))
    assert eq["passed"] is True
    v3=json.loads((RESULTS/"v3_denominator_audit.json").read_text(encoding="utf-8"))
    assert v3["passed"] is True
    cap=pd.read_csv(RESULTS/"cap_equity_summary.csv")
    head=pd.read_csv(RESULTS/"headway_proxy_sensitivity.csv")
    feasibility=pd.read_csv(RESULTS/"feasibility_assumption_stress.csv")
    assert len(cap)>=7 and len(head)>0 and len(feasibility)==3
    assert head.proxy_gain_observable.ge(-1e-12).all()
    assert ((feasibility.spent+feasibility.unspent)==50).all()
    src=sorted(p for p in (ROOT/"raw").iterdir() if p.is_file())
    receipt={
      "status":"passed",
      "note":"Passing offline reproducibility tests; NOT independent validation of real-world bus accessibility.",
      "source_git_commit_environment":os.environ.get("GITHUB_SHA","not supplied"),
      "python":sys.version.split()[0],
      "platform":platform.platform(),
      "packages":{k:md.version(k) for k in
                  ["numpy","pandas","matplotlib","scikit-learn","shapely","pyproj"]},
      "raw_snapshot_sha256":{p.name:digest(p) for p in src},
      "required_analysis_output_sha256":{p.name:digest(p) for p in files},
      "test_policy_scenario_recalculations":eq.get("policy_scenario_recomputations"),
      "outputs":len(files),
      "method_limits":[
          "Mixed 2025/2026 archived public sources",
          "Nominal headway penalty is not actual low-floor bus waiting time",
          "Eligibility shares 25/50/100% are sensitivity assumptions",
          "No observed wheelchair trip, real walking route or financial costing"
      ]
    }
    (RESULTS/"validation_v3_receipt.json").write_text(json.dumps(
        receipt,ensure_ascii=False,indent=2),encoding="utf-8")
    print("V3 RECEIPT PASSED; files:",len(files),"raw sources:",len(src))


if __name__=="__main__":
    main()
