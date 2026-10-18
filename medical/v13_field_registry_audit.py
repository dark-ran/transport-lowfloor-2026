"""V13 stop-observation contract: destination/direction/ARS are mandatory.

Syntax-valid rows are CANDIDATES ONLY. Approval-reference strings are not
signature verification, and no empirical wheelchair benefit is established.
"""
from datetime import date, time
SITES={("343","122000133"):("hospital_outbound","23236","삼성서울병원"),
("343","122000288"):("return","23392","삼성서울병원"),
("662","116000144"):("hospital_outbound","17235","서울특별시서남병원"),
("662","114000221"):("return","15325","서울특별시서남병원"),
("3413","124000126"):("hospital_outbound","25237","강동경희대학교병원"),
("3413","124000078"):("return","25178","강동경희대학교병원")}
REG_FIELDS={"route","boarding_stop_id","direction","ars_id","hospital_destination",
"period","preregistered_date","physical_site_verified","collection_authorized",
"independent_reviewer","review_evidence_reference","authorization_evidence_reference"}
OBS_FIELDS={"route","boarding_stop_id","direction","ars_id","hospital_destination",
"observation_date","vehicle_arrival_local"}
PERIOD={"09:00-11:00":(time(9,0),time(11,0)),
"13:00-15:00":(time(13,0),time(15,0))}

def validate(registration,observations=()):
    seen=set()
    for r in registration:
        if not REG_FIELDS.issubset(r):raise ValueError("MISSING_REGISTRY_FIELDS")
        key=(r["route"],r["boarding_stop_id"])
        target=SITES.get(key)
        if not target:raise ValueError("UNKNOWN_SITE")
        direction,ars,hospital=target
        if not r["hospital_destination"].strip():raise ValueError("MISSING_HOSPITAL_DESTINATION")
        if (r["direction"],r["ars_id"],r["hospital_destination"])!=(direction,ars,hospital):
            raise ValueError("REGISTRY_SITE_CONTRACT_MISMATCH")
        if r["period"] not in PERIOD:raise ValueError("UNKNOWN_WINDOW")
        if r["preregistered_date"]!="NOT_SCHEDULED":
            try:date.fromisoformat(r["preregistered_date"])
            except ValueError:raise ValueError("INVALID_PREREG_DATE")
        k=(*key,r["period"],r["preregistered_date"])
        if k in seen:raise ValueError("DUPLICATE_PREREGISTRATION")
        seen.add(k)
        if r["collection_authorized"]=="YES":
            if (r["physical_site_verified"]!="YES" or
                not r["independent_reviewer"].strip() or
                r["independent_reviewer"]=="NOT_ASSIGNED" or
                not r["review_evidence_reference"].strip() or
                not r["authorization_evidence_reference"].strip()):
                raise ValueError("UNSUPPORTED_AUTHORIZATION")
    for x in observations:
        if not OBS_FIELDS.issubset(x):raise ValueError("MISSING_OBSERVATION_FIELDS")
        site=SITES.get((x["route"],x["boarding_stop_id"]))
        if not site or (x["direction"],x["ars_id"],x["hospital_destination"])!=site:
            raise ValueError("WRONG_OBSERVATION_DIRECTION_ARS_OR_HOSPITAL")
        try:date.fromisoformat(x["observation_date"])
        except ValueError:raise ValueError("INVALID_OBSERVATION_DATE")
        try:time.fromisoformat(x["vehicle_arrival_local"])
        except ValueError:raise ValueError("INVALID_OBSERVATION_TIME")
    return {"preregistered_cells":len(registration),
      "input_observations":len(observations),"independently_verified_observation_count":0,
      "wheelchair_boarding_success_rate":None,"patient_wait_minutes":None,
      "empirical_policy_effect":None,"evidence_status":"REQUIRES_EXTERNAL_EVIDENCE_AUTHENTICATION"}

if __name__=="__main__":
    print("V13 schema: import validate(registration,observations); never authenticate by schema alone")
