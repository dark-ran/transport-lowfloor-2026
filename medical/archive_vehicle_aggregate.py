"""Archive only allowlisted aggregate bus counts; never persist vehicle identifiers or API keys."""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

KST = timezone(timedelta(hours=9))
FIELDS = (
    "route", "direction", "query_scope", "status", "snapshots",
    "low_floor_snapshots", "ordinary_snapshots", "unknown_type_snapshots",
    "fresh_low_floor_snapshots", "fresh_ordinary_snapshots",
    "fresh_unknown_type_snapshots", "stale_provider_snapshots",
    "unknown_time_snapshots", "future_time_snapshots",
)
CSV_FIELDS = (
    "observed_at_utc", "observed_at_kst", "run_id", "run_attempt", "event",
    "query_scope", "route", "direction", "status", "snapshots",
    "low_floor_snapshots", "ordinary_snapshots", "unknown_type_snapshots",
    "fresh_low_floor_snapshots", "fresh_ordinary_snapshots",
    "fresh_unknown_type_snapshots", "stale_provider_snapshots",
    "unknown_time_snapshots", "future_time_snapshots",
    "http_status", "provider_code",
)


def _whitelist(source, run_id, attempt, event):
    dt = datetime.fromisoformat(source["created_at_utc"].replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Capture timestamp must include a timezone")
    groups = source["query_groups"]
    if not isinstance(groups, list) or not groups:
        raise ValueError("Expected nonempty query groups")
    allowed_scopes = {"full", "section"}
    if source.get("query_scope") not in allowed_scopes:
        raise ValueError("Unknown scope")
    out_groups = []
    for group in groups:
        if group.get("query_scope") != source["query_scope"]:
            raise ValueError("Group scope mismatch")
        clean = {key:group.get(key,0) for key in FIELDS}
        for key in ("snapshots", "low_floor_snapshots", "ordinary_snapshots", "unknown_type_snapshots",
                    "fresh_low_floor_snapshots", "fresh_ordinary_snapshots", "fresh_unknown_type_snapshots",
                    "stale_provider_snapshots", "unknown_time_snapshots", "future_time_snapshots"):
            clean[key] = int(clean[key])
            if clean[key] < 0:
                raise ValueError("Negative observation count")
        if sum(clean[key] for key in ("low_floor_snapshots", "ordinary_snapshots", "unknown_type_snapshots")) != clean["snapshots"]:
            raise ValueError("Vehicle type counts do not sum to observations")
        available_qc = any(key in group for key in (
            "fresh_low_floor_snapshots","stale_provider_snapshots","unknown_time_snapshots"))
        if available_qc:
            quality_keys=("fresh_low_floor_snapshots","fresh_ordinary_snapshots",
                          "fresh_unknown_type_snapshots","stale_provider_snapshots",
                          "unknown_time_snapshots","future_time_snapshots")
            if sum(clean[key] for key in quality_keys)!=clean["snapshots"]:
                raise ValueError("Fresh/stale/missing timestamp counts do not match snapshots")
        else:
            # Old runs predate provider timestamp quality accounting. Do not count as fresh.
            clean["unknown_time_snapshots"]=clean["snapshots"]
        err = group.get("error") or {}
        clean["http_status"] = err.get("http_status")
        clean["provider_code"] = err.get("provider_code")
        out_groups.append(clean)
    counts = {"api_requests_executed": int(source["api_requests_executed"]),
              "successful_requests": int(source["successful_requests"]),
              "vehicle_snapshots": int(source["vehicle_snapshots"])}
    if not (0 <= counts["successful_requests"] <= counts["api_requests_executed"] == len(groups)):
        raise ValueError("Inconsistent API request counts")
    if sum(g["snapshots"] for g in out_groups) != counts["vehicle_snapshots"]:
        raise ValueError("Aggregate row counts do not match")
    return {
        "schema_version": 1, "run_id": str(run_id), "run_attempt": str(attempt),
        "event": event, "created_at_utc": dt.astimezone(timezone.utc).isoformat(),
        "created_at_kst": dt.astimezone(KST).isoformat(),
        "source_git_commit": source["source_git_commit"],
        "query_scope": source["query_scope"], **counts,
        "query_groups": out_groups,
        "interpretation": "Position snapshots, not confirmed arrivals/boardings, observed headways, or actual passenger access.",
    }


def regenerate_csv(output_dir):
    rows = []
    for path in sorted(output_dir.glob("aggregate-*.json")):
        receipt = json.loads(path.read_text(encoding="utf-8"))
        for group in receipt["query_groups"]:
            rows.append({
                "observed_at_utc": receipt["created_at_utc"],
                "observed_at_kst": receipt["created_at_kst"],
                "run_id": receipt["run_id"],
                "run_attempt": receipt["run_attempt"],
                "event": receipt["event"],
                "query_scope": receipt["query_scope"],
                **{key: group.get(key) for key in FIELDS},
                "http_status": group["http_status"],
                "provider_code": group["provider_code"],
            })
    rows.sort(key=lambda x: (x["observed_at_utc"], x["run_id"], x["run_attempt"], x["route"], x["direction"]))
    destination = output_dir.parent / "vehicle_timeseries.csv"
    with destination.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return destination, len(rows)


def archive(source, output_dir, run_id, attempt, event):
    if not str(run_id).isdigit() or not str(attempt).isdigit():
        raise ValueError("Run IDs and attempts must be numeric")
    output_dir = Path(output_dir)
    receipt = _whitelist(source, run_id, attempt, event)
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / f"aggregate-{run_id}-{attempt}.json"
    archive_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    trend_path, count = regenerate_csv(output_dir)
    return archive_path, trend_path, count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--attempt", default="1")
    parser.add_argument("--event", default="schedule")
    args = parser.parse_args()
    raw = json.loads(args.input.read_text(encoding="utf-8"))
    archive_path, trends, count = archive(raw, args.output_dir, args.run_id, args.attempt, args.event)
    print(f"Archived safe aggregate: {archive_path}; trend rows: {count} ({trends})")


if __name__ == "__main__":
    main()
