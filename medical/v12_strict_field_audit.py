"""V12 strict field-observation guard; no synthetic pass can establish real-world benefit.

Unlike earlier V11 audit, a plausible row is only a review CANDIDATE, never a
verified empirical record. Running this module requires an existing observation
CSV; the empty template yields NA, not a 0% success rate.
"""
import csv,datetime as dt,re
from pathlib import Path
SITES={("343","122000133"),("343","122000288"),("662","116000144"),
       ("662","114000221"),("3413","124000126"),("3413","124000078")}
PERIOD={"09:00-11:00":("09:00","11:00"),"13:00-15:00":("13:00","15:00")}
REQUIRED={"record_id","route","boarding_stop_id","observation_date","period",
"observation_start_local","observation_end_local","vehicle_arrival_local",
"bus_type_observed_Y_N_UNKNOWN","wheelchair_boarding_attempt_Y_N_UNKNOWN",
"wheelchair_boarding_success_Y_N_NA_UNKNOWN","field_observer","source_evidence_reference"}
def date(x):
    if not re.fullmatch(r"\d{4}-\d\d-\d\d",x):raise ValueError("INVALID_ISO_DATE")
    return dt.date.fromisoformat(x)
def time(x):
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d",x):raise ValueError("INVALID_TIME")
    return dt.time.fromisoformat(x)
def audit(path,preregistered=()):
    with Path(path).open(encoding="utf-8-sig",newline="") as f:
        rdr=csv.DictReader(f)
        if not REQUIRED.issubset(set(rdr.fieldnames or ())):raise ValueError("MISSING_REQUIRED_COLUMNS")
        rows=list(rdr)
    out={"status":"NO_OBSERVATIONS" if not rows else "FORMAT_VALID_REVIEW_REQUIRED",
         "input_rows":len(rows),"verified_observations":0,
         "wheelchair_boarding_success_rate":None,"observed_lowfloor_wait_min":None,
         "empirical_policy_effect":None,"field_evidence_ready":False}
    allowed={(x["route"],x["boarding_stop_id"],x["period"],x["preregistered_date"]):x
             for x in preregistered}
    used=set();events=set()
    for row in rows:
        r=row["route"].strip();sid=row["boarding_stop_id"].strip()
        if (r,sid) not in SITES:raise ValueError("INVALID_ROUTE_STOP")
        d=date(row["observation_date"].strip());window=row["period"].strip()
        if window not in PERIOD:raise ValueError("UNREGISTERED_WINDOW")
        lo,hi=PERIOD[window];start=time(row["observation_start_local"]);end=time(row["observation_end_local"]);arrival=time(row["vehicle_arrival_local"])
        if not time(lo)<=start<=arrival<end<=time(hi):raise ValueError("TIME_OUTSIDE_WINDOW")
        g=allowed.get((r,sid,window,d.isoformat()))
        if not g:raise ValueError("DATE_NOT_PREREGISTERED")
        if g.get("physical_site_verified")!="YES" or g.get("collection_authorized")!="YES" or not g.get("independent_reviewer"):raise ValueError("FIELD_AUTHORIZATION_NOT_CONFIRMED")
        if not row["source_evidence_reference"] or not re.fullmatch(r"[A-Za-z0-9_.\-/]{6,128}",row["source_evidence_reference"]):raise ValueError("SOURCE_EVIDENCE_INVALID")
        if not row["field_observer"].strip():raise ValueError("OBSERVER_MISSING")
        rid=row["record_id"].strip()
        if not rid or rid in used:raise ValueError("DUPLICATE_OR_BLANK_RECORD_ID")
        used.add(rid)
        event=(r,sid,d.isoformat(),arrival.isoformat())
        if event in events:raise ValueError("POSSIBLE_DUPLICATE_EVENT")
        events.add(event)
        typ=row["bus_type_observed_Y_N_UNKNOWN"].strip().upper()
        attempt=row["wheelchair_boarding_attempt_Y_N_UNKNOWN"].strip().upper()
        success=row["wheelchair_boarding_success_Y_N_NA_UNKNOWN"].strip().upper()
        if typ not in {"Y","N","UNKNOWN"} or attempt not in {"Y","N","UNKNOWN"} or success not in {"Y","N","NA","UNKNOWN"}:raise ValueError("INVALID_FLAG")
        if attempt=="N" and success!="NA":raise ValueError("IMPOSSIBLE_BOARDING_SUCCESS")
        if attempt=="Y" and success not in {"Y","N","UNKNOWN"}:raise ValueError("MISSING_SUCCESS_OUTCOME")
        if attempt=="UNKNOWN" and success not in {"UNKNOWN","NA"}:raise ValueError("INCONSISTENT_UNKNOWN")
    return out
