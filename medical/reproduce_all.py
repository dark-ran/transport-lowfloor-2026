"""One-command offline reconstruction of every published medical analysis stage.

Usage from the repository root:
    python medical/reproduce_all.py

This needs the versioned raw snapshots already in medical/raw and the dependencies
in requirements.txt. It does not query current bus services or simulate passengers.
"""
from pathlib import Path
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
    "feasibility_assumptions.py",
    "route_marginal.py",
    "allocated_route_pilot.py",
    "route_case_brief.py"
]


def main():
    for script in STAGES:
        print(f"\n>>> {script}", flush=True)
        subprocess.run([sys.executable, str(ROOT / "medical" / script)],
                       cwd=ROOT, check=True)
    print("\n>>> full medical unit test suite", flush=True)
    subprocess.run([sys.executable, "-m", "unittest", "discover",
                    "-s", "medical", "-p", "test_*.py", "-v"],
                   cwd=ROOT, check=True)
    subprocess.run([sys.executable, str(ROOT / "medical" / "validation_receipt.py")],
                   cwd=ROOT, check=True)
    print("\nAll offline stages and tests finished. Validation receipt saved in "
          "medical/results/validation_v2_receipt.json.")


if __name__ == "__main__":
    main()
