"""One-command offline reconstruction of the core analysis and executable later-stage audits.

Usage from the repository root:
    python medical/reproduce_all.py

This needs the versioned raw snapshots already in medical/raw and the dependencies
in requirements.txt. It does not query current bus services or simulate passengers.
"""
from pathlib import Path
import argparse
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
STAGES = [
    "prepare.py",
    "analyze_medical.py",
    "validate_cases.py",
    "audit_cases.py",
    "plot_cases.py",
    "decision_stress.py",
    "audit_decision.py",
    "plot_decision.py",
    "policy_extension.py",
    "audit_policy_extension.py",
    "plot_policy_extension.py",
    "headway_proxy.py",
    "audit_headway_proxy.py",
    "v3_denominator_multiroute.py",
    "audit_v3_denominator.py",
    "feasibility_assumptions.py",
    "benchmark_greedy_small.py",
    "route_marginal.py",
    "allocated_route_pilot.py",
    "route_case_brief.py",
    "v4_directional_audit.py",
    "v4_implementation_gates.py",
    "v4_vehicle_snapshot.py",
    "v4_evidence_audit.py",
    "v4_decision_brief.py",
    "v3_policy_brief.py",
    "v5_case_maps.py",
    "v6_evidence_audit.py",
    "v4_feasibility.py",
    "v10_conditional_wait.py",
    "v11_23route_gis.py",
    "v13_position_evidence_audit.py",
    "v14_source_position_audit.py"
]


def main():
    parser=argparse.ArgumentParser(description="Offline core and later-stage evidence replay; never calls live APIs")
    parser.add_argument('--may-2025',type=Path)
    parser.add_argument('--may-2026',type=Path)
    args=parser.parse_args()
    if bool(args.may_2025)!=bool(args.may_2026):parser.error('Both original monthly CSVs are required together')
    for script in STAGES:
        print(f"\n>>> {script}", flush=True)
        subprocess.run([sys.executable, str(ROOT / "medical" / script)],
                       cwd=ROOT, check=True)
    if args.may_2025:
        for script in ['historical_policy_demand.py','historical_policy_spatial_v3.py','v8_alias_audit.py']:
            subprocess.run([sys.executable,str(ROOT/'medical'/script),'--may-2025',str(args.may_2025.resolve()),'--may-2026',str(args.may_2026.resolve())],cwd=ROOT,check=True)
        subprocess.run([sys.executable,str(ROOT/'medical/v5_temporal_linkage.py'),'--may-2026',str(args.may_2026.resolve())],cwd=ROOT,check=True)
        subprocess.run([sys.executable,str(ROOT/'medical/v9_lineage_audit.py'),'--may-2026',str(args.may_2026.resolve())],cwd=ROOT,check=True)
        subprocess.run([sys.executable,str(ROOT/'medical/v11_23route_gis.py'),'--may26',str(args.may_2026.resolve())],cwd=ROOT,check=True)
    else:
        print('Monthly source replay SKIPPED: pass --may-2025 and --may-2026. See docs/REPRODUCTION.md.',flush=True)
    print("\n>>> full medical unit test suite", flush=True)
    subprocess.run([sys.executable, "-m", "unittest", "discover",
                    "-s", "medical", "-p", "test_*.py", "-v"],
                   cwd=ROOT, check=True)
    subprocess.run([sys.executable, str(ROOT / "medical" / "validation_receipt.py")],
                   cwd=ROOT, check=True)
    print("\nAll offline stages and tests finished. Validation receipt saved in "
          "medical/results/validation_v4_receipt.json.")


if __name__ == "__main__":
    main()
