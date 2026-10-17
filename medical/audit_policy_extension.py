"""Independent recomputation of cap-sweep outputs from saved allocations."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from analyze_medical import scores
from decision_stress import load_models, measure
from policy_extension import dong_metrics, BUDGET

ROOT = Path(__file__).resolve().parent


def main():
    out = ROOT / "results"
    origins, models = load_models()
    alloc = pd.read_csv(out / "cap_allocations.csv", dtype={"route": str})
    summary = pd.read_csv(out / "cap_equity_summary.csv")
    fixed = pd.read_csv(out / "cap_fixed_scenarios.csv")
    dong_saved = pd.read_csv(out / "cap_dong_changes.csv", dtype={"code": str})
    exception = set(json.loads((ROOT / "raw/exception_routes_2026.json").read_text(
        encoding="utf-8"))["routes"])
    n_checked = 0
    model = models["기본"]
    routes = model["f"].route.astype(str).tolist()
    for row in summary.itertuples():
        records = alloc[alloc.policy == row.policy]
        assert not records.route.duplicated().any()
        assert records.added.ge(1).all()
        assert (records.added <= records.fleet - records.low_before).all()
        assert set(records.route).issubset(routes)
        cap = row.cap_per_route
        if row.policy != "의료연결 우선":
            assert not set(records.route).intersection(exception)
            if str(cap) != "unrestricted":
                assert records.added.max() <= int(cap)
        mapping = records.set_index("route").added.to_dict()
        a = np.array([mapping.get(r, 0) for r in routes], int)
        assert int(a.sum()) == int(row.spent) <= BUDGET
        assert int(row.unspent) == BUDGET - int(a.sum())
        detail, eq = dong_metrics(model, origins, routes, a)
        assert eq["changed_dongs"] == row.changed_dongs
        assert eq["changed_dongs_ge_0p01"] == row.changed_dongs_ge_0p01
        assert eq["changed_dongs_ge_0p05"] == row.changed_dongs_ge_0p05
        assert abs(eq["bottom_20pct_seniors_weighted_delta"] -
                   row.bottom_20pct_seniors_weighted_delta) < 1e-12
        stored = dong_saved[dong_saved.policy == row.policy].sort_values("code")
        actual = detail.sort_values("code")
        assert len(stored) == len(actual) == len(origins)
        assert stored.code.astype(str).tolist() == actual.code.astype(str).tolist()
        np.testing.assert_allclose(stored.delta_index, actual.delta_index, atol=1e-12)
        for scenario, mm in models.items():
            calculated = measure(mm, origins, routes, a)
            result = fixed[(fixed.policy == row.policy) & (fixed.scenario == scenario)]
            assert len(result) == 1
            r = result.iloc[0]
            assert abs(calculated["delta_index"] - r.delta_index) < 1e-12
            assert calculated["changed_dongs"] == r.changed_dongs
            n_checked += 1
    report = {
        "passed": True, "policies_audited": int(len(summary)),
        "policy_scenario_recomputations": n_checked,
        "dong_rows_checked": int(len(dong_saved)),
        "no_live_timetable_validation": True,
        "no_verified_real_passenger_benefit": True,
        "scope": "Independent recomputation with the same static source data and index definition; not external or empirical verification."
    }
    (out / "cap_equity_audit.json").write_text(json.dumps(
        report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
