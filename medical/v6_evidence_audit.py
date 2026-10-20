"""V6: archived V3/V5 route-stop discrepancy and observed vehicle-type audit.

Without the official May 2026 CP949 CSV, derived results cannot be fully
recalculated. A vehicle-location response is not an arrival or a boarding.
Run: python medical/v6_evidence_audit.py
     python medical/v6_evidence_audit.py --may-2026 LOCAL_202605.csv
"""
import argparse
import csv
import json
import math
from pathlib import Path
from collections import defaultdict

ROUTES = ("343", "662", "1124", "3413")
BASE = Path(__file__).resolve().parent


def read(path, encoding="utf-8-sig"):
    with Path(path).open(encoding=encoding, newline="") as f:
        return list(csv.DictReader(f))


def static_sets(data):
    allids, geoids = defaultdict(set), defaultdict(set)
    for x in data:
        r = x["route"].strip()
        if r not in ROUTES:
            continue
        sid = x["stop_id"].strip()
        allids[r].add(sid)
        try:
            lon, lat = float(x["lon"]), float(x["lat"])
        except (TypeError, ValueError):
            continue
        if 125 < lon < 129 and 36 < lat < 39:
            geoids[r].add(sid)
    return allids, geoids


def audit(old, latest, allids, geoids):
    older = {x["route"]: x for x in old}
    newer = {x["route"]: x for x in latest}
    result = []
    for r in ROUTES:
        a, b = older[r], newer[r]
        total = int(a["2026_board"])
        if total != int(b["monthly_boardings_2026"]):
            raise ValueError("Incompatible ridership denominators: " + r)
        v3 = int(a["2026_board_geolinked"])
        v5 = int(b["boardings_matching_2025_static_stop_id"])
        result.append({
            "route": r, "monthly_boardings": total,
            "v3_legacy_geo_linked": v3,
            "v5_route_stop_id_linked": v5,
            "gap": v5 - v3,
            "legacy_pct": round(100 * v3 / total, 4),
            "new_pct": round(100 * v5 / total, 4),
            "static_unique_ids": len(allids[r]),
            "coordinate_valid_unique_ids": len(geoids[r]),
            "same_static_id_sets": allids[r] == geoids[r],
            "decision": "RECALCULATION_REQUIRED" if v3 != v5 else "ALIGNED"
        })
    return result


def recheck_original(raw, allids, geoids):
    totals, idmatched, geomatched = defaultdict(int), defaultdict(int), defaultdict(int)
    with Path(raw).open(encoding="cp949", newline="") as f:
        reader = csv.DictReader(f)
        hours = [x for x in reader.fieldnames if x.endswith("시승차총승객수")]
        if len(hours) != 24:
            raise ValueError("24 hourly columns required")
        for x in reader:
            if x["사용년월"] != "202605":
                raise ValueError("Input is not 2026-05")
            route = x["노선번호"].strip()
            if route not in ROUTES:
                continue
            n = sum(int(x[h].replace(",", "")) for h in hours)
            if n < 0:
                raise ValueError("Negative boarding data")
            sid = x["표준버스정류장ID"].strip()
            totals[route] += n
            if sid in allids[route]:
                idmatched[route] += n
            if sid in geoids[route]:
                geomatched[route] += n
    return {r: (totals[r], idmatched[r], geomatched[r]) for r in ROUTES}


def observations(windows):
    result = []
    for route in ROUTES:
        items = [x for x in windows if x["route"] == route
                 and x["day_kind"] == "weekend" and x["query_scope"] == "full"]
        result.append({
            "route": route,
            "polls": sum(int(x["polls"]) for x in items),
            "location_records": sum(int(x["snapshots"]) for x in items),
            "low_floor_type_records": sum(int(x["low_floor_snapshots"]) for x in items),
            "ordinary_type_records": sum(int(x["ordinary_snapshots"]) for x in items),
            "measured_accessible_boardings": "NOT_MEASURED",
            "interpretation": "INSTANTANEOUS_PROVIDER_RECORDS_NOT_SERVICE_PROBABILITY"
        })
    return result


def write_csv(path, contents):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(contents[0]))
        writer.writeheader()
        writer.writerows(contents)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--may-2026", type=Path, default=None)
    parser.add_argument("--output", type=Path,
                        default=BASE / "results" / "submission_v6")
    opts = parser.parse_args()
    a, b = static_sets(read(BASE / "data" / "route_stops.csv"))
    cases = audit(
        read(BASE / "raw" / "v3_legacy_spatial_evidence.csv"),
        read(BASE / "results" / "submission_v5" / "v5_temporal_linkage_audit.csv"), a, b)
    windows = observations(read(BASE.parent / "observations" / "vehicle_window_summary.csv"))
    original = recheck_original(opts.may_2026, a, b) if opts.may_2026 else None
    if original:
        for item in cases:
            v = original[item["route"]]
            item["fresh_total"] = v[0]
            item["fresh_id_matched"] = v[1]
            item["fresh_geo_matched"] = v[2]
            item["fresh_matches_v3"] = v[2] == item["v3_legacy_geo_linked"]
            item["fresh_matches_v5"] = v[1] == item["v5_route_stop_id_linked"]
    status = "RECALCULATION_REQUIRED" if any(x["gap"] for x in cases) else "ALIGNED"
    if original:
        status = "ORIGINAL_RECALCULATED_REVIEW_DISCREPANCIES"
    bundle = {"version": 6, "status": status,
              "original_2026_05_provided": original is not None,
              "cases": cases, "observations": windows,
              "limitations": [
                "An old geo-linked count cannot be renamed a hospital-radius percentage.",
                "All four archived stop-ID sets have valid 2025 coordinates; historical differences are not explained solely by coordinate missingness.",
                "A provider location snapshot does not identify actual stop arrivals or boarding outcomes.",
                "A CI success without the official monthly CSV does not independently reproduce the historical inputs."
              ]}
    opts.output.mkdir(parents=True, exist_ok=True)
    (opts.output / "v6_evidence_status.json").write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_csv(opts.output / "v6_stop_id_discrepancies.csv", cases)
    write_csv(opts.output / "v6_observation_baseline.csv", windows)
    assert len(cases) == 4 and all(x["static_unique_ids"] > 0 for x in cases)
    print(json.dumps({"status": status, "cases": len(cases)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
