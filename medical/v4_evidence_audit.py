"""Independent cross-file V4 evidence consistency audit: no field validation claimed."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent


def verify(out):
    d=pd.read_csv(out/"v4_directional_pairs.csv",dtype={"route":str,"dong_code":str,"hospital_id":str})
    m=json.loads((out/"v4_directional_metadata.json").read_text(encoding="utf-8"))
    a=pd.read_csv(out/"cap5_route_marginal_pairs.csv",dtype={"route":str,"dong_code":str,"hospital_id":str})
    assert len(d)==len(a)==m["model_attributable_pairs"]
    assert set(zip(d.route,d.dong_code,d.hospital_id))==set(zip(a.route,a.dong_code,a.hospital_id))
    assert d.coverage.value_counts().to_dict()==m["status_counts"]
    covered=d[d.snapshot_route_available]
    assert covered.coverage.isin(["bidirectional","one_direction","no_ordered_direct_in_snapshot"]).all()
    for row in covered.itertuples():
        fore=(row.coverage in ("bidirectional","one_direction"))
        # For both-direction snapshots the two serialized ordered legs MUST exist.
        if row.coverage=="bidirectional":
            assert pd.notna(row.outward_leg) and pd.notna(row.return_leg)
            outleg=json.loads(row.outward_leg);backleg=json.loads(row.return_leg)
            assert outleg["board_seq"]<outleg["alight_seq"]
            assert backleg["board_seq"]<backleg["alight_seq"]
    gated=pd.read_csv(out/"v4_implementation_gates.csv",dtype={"route":str})
    states=json.loads((out/"v4_implementation_metadata.json").read_text(encoding="utf-8"))
    assert len(gated)==15 and gated.route.is_unique
    assert gated.proposed_replacements.sum()==50
    assert states["field_verified_operational_approvals"]==0
    assert set(gated.operational_decision)=={"hold_for_field_verification"}
    for col in ["bus_vehicle_level_age_or_decommission_verified",
                "bus_vehicle_level_lowfloor_departures_verified",
                "depot_or_charging_capacity_verified",
                "accessible_pedestrian_access_verified",
                "actual_unit_cost_or_maintenance_cost_verified",
                "real_patient_boarding_or_benefit_verified"]:
        assert not gated[col].astype(bool).any()
    manifest=json.loads((out/"v4_capture_manifest.json").read_text(encoding="utf-8"))
    assert manifest["mode"]=="NO_CAPTURE_PERFORMED"
    assert manifest["real_vehicle_observations"]==0
    assert manifest["no_credentials_embedded"] is True
    for row in manifest["requests"]:
        assert "serviceKey" not in row and "vehicle_id" not in row
    result={
        "passed":True,"validated_model_attributable_pairs":len(d),
        "policy_candidate_routes":len(gated),"hypothetical_replacements":50,
        "verified_vehicle_arrivals":0,"verified_boardings":0,
        "verified_operational_approvals":0,
        "source":"Archived static bus-stop order and 2025 fleet, NOT observations of real passenger trips"
    }
    (out/"v4_evidence_audit.json").write_text(json.dumps(
        result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return result


if __name__=="__main__":
    verify(ROOT/"results")
