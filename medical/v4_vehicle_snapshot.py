"""Optional one-shot vehicle-type observation collector for three hospital trip examples.

DEFAULT: dry-run request manifest, NO API calls. --capture requires environment:
  SEOUL_BUS_API_KEY=... V4_VEHICLE_SALT=... python medical/v4_vehicle_snapshot.py --capture --output /private/observations.jsonl

Real responses must be explicitly acquired and audited. Never include private
keys or raw vehicle/plate identifiers in the git repo. A single location
snapshot cannot prove a vehicle ACTUALLY stops, a low-floor boarding succeeds,
or a passenger waits a given number of minutes.

The official Seoul bus position endpoints support vehicle type "busType"
0 ordinary / 1 low-floor per 2025-12-02 portal specification.
"""
from pathlib import Path
import argparse
from datetime import datetime,timezone
import hashlib
import hmac
import json
import os
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import pandas as pd

ROOT=Path(__file__).resolve().parent
API_BY_SCOPE={
    "full":"http://ws.bus.go.kr/api/rest/buspos/getBusPosByRtid",
    "section":"http://ws.bus.go.kr/api/rest/buspos/getBusPosByRouteSt",
}
ROUTES=("662","343","3413")


def _leg(s):
    return json.loads(s) if isinstance(s,str) and s.strip() else {}


def manifest(data,scope="full"):
    """One full-route request per route by default; section windows are optional."""
    if scope not in API_BY_SCOPE:
        raise ValueError("Unknown capture scope")
    data=data[(data.route.isin(ROUTES)) & (data.both_directions == True)].copy()
    data=data.sort_values(["route","base_dong_index_gain"],ascending=[True,False])
    data=data.drop_duplicates("route")
    requests=[]
    for row in data.itertuples():
        common={"route":str(row.route),"route_id":str(row.route_id),
                "dong":str(row.dong),"hospital":str(row.hospital)}
        if scope=="full":
            requests.append({**common,"scope":"full","direction":"route_all",
                             "purpose":"whole-route position snapshot; direction NOT established"})
            continue
        for direction,key in [("outbound","outbound_leg"),("return","return_leg")]:
            leg=_leg(getattr(row,key))
            if not leg:
                continue
            board=int(leg["board_seq"])
            requests.append({**common,"scope":"section","direction":direction,
                "boarding_station":str(leg["board"]),"boarding_seq":board,
                "startOrd":max(1,board-1),"endOrd":board+1,
                "purpose":"narrow section snapshot; NOT proof of boarding/arrival"})
    return requests

def normalize_xml(payload,request,observed_at,salt):
    root=ET.fromstring(payload)
    header=root.find(".//msgHeader")
    if header is not None:
        cd=header.findtext("headerCd")
        if cd not in ("0","00"):
            raise ValueError("API response not successful; no observations accepted")
    items=root.findall(".//itemList")
    rows=[]
    for item in items:
        typ=item.findtext("busType")
        veh=item.findtext("vehId")
        if typ not in ("0","1"):
            label="unknown"
        else:
            label="low_floor" if typ=="1" else "ordinary"
        # Absence of unique vehicle ID means it cannot be de-duplicated.
        if not veh or not veh.strip():
            continue
        pseudonym=hmac.new(salt.encode("utf-8"),
                           (observed_at[:10]+"|"+request["route_id"]+"|"+veh.strip()).encode("utf-8"),
                           hashlib.sha256).hexdigest()[:20]
        rows.append({
            "request_time_utc":observed_at,
            "route":request["route"],"route_id":request["route_id"],
            "direction":request["direction"],
            "boarding_seq":request.get("boarding_seq"),
            "query_scope":request.get("scope","section"),
            "section_seq":item.findtext("sectOrd"),
            "provider_observation_time":item.findtext("dataTm"),
            "vehicle_type":label,
            "reported_stop_flag":item.findtext("stopFlag"),
            "vehicle_pseudonym":pseudonym,
            "evidence_level":"vehicle_position_snapshot_only",
            "confirmed_at_boarding_stop":False,
            "confirmed_boarding":False
        })
    return rows


def collect(requests,api_key,salt,output):
    if not api_key or not salt or len(salt)<16:
        raise ValueError("API key and a local random V4_VEHICLE_SALT of at least 16 chars are required")
    output=output.resolve()
    if output.is_relative_to(ROOT.parent):
        raise ValueError("Use a private output path OUTSIDE the entire git repository")
    output.parent.mkdir(parents=True,exist_ok=True)
    records=[]
    failures=[]
    for request in requests:
        scope=request.get("scope","section")
        if scope not in API_BY_SCOPE:
            raise ValueError("Unknown request scope")
        fields={"serviceKey":urllib.parse.unquote(api_key.strip()),
                "busRouteId":request["route_id"]}
        if scope=="section":
            fields.update({"startOrd":request["startOrd"],"endOrd":request["endOrd"]})
        params=urllib.parse.urlencode(fields)
        timestamp=datetime.now(timezone.utc).isoformat()
        provider_code=None
        try:
            # Official provider endpoint is HTTP; never log its credential-bearing URL.
            with urllib.request.urlopen(API_BY_SCOPE[scope]+"?"+params,timeout=15) as response:
                payload=response.read(2_000_000)
            header=ET.fromstring(payload).find(".//msgHeader")
            provider_code=header.findtext("headerCd") if header is not None else None
            if provider_code not in ("0","00"):
                raise ValueError("Successful provider header required")
            records.extend(normalize_xml(payload,request,timestamp,salt))
        except (OSError,ValueError,ET.ParseError) as exc:
            failures.append({"route":request["route"],"direction":request["direction"],
                             "status":"api_error_or_missing","scope":scope,
                             "exception_type":type(exc).__name__,
                             "http_status":exc.code if isinstance(exc,urllib.error.HTTPError) else None,
                             "provider_code":provider_code if provider_code and provider_code.isdigit() and len(provider_code)<=4 else None})
    with output.open("a",encoding="utf-8") as fh:
        for row in records:
            fh.write(json.dumps(row,ensure_ascii=False)+"\n")
    # Do not report raw requests/headers with secrets.
    return {"requests":len(requests),"request_manifest":requests,
            "query_scope":requests[0].get("scope","section") if requests else None,
            "vehicle_snapshots":len(records),
            "failed_requests":failures,"private_file":str(output),
            "actual_stops_or_boardings_confirmed":0,
            "note":"An API request failure or no returned vehicles is NOT a no-service observation"}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--capture",action="store_true",
                   help="Perform explicit official HTTP API calls; requires environment credentials")
    p.add_argument("--output",type=Path,help="Private JSONL output outside medical/")
    p.add_argument("--scope",choices=("full","section"),default="full",
                   help="full: entire routes (default); section: narrow outbound/return stop windows")
    args=p.parse_args()
    data=pd.read_csv(ROOT/"results/cap5_route_pilot_candidates.csv",dtype={"route":str})
    requests=manifest(data,scope=args.scope)
    if not args.capture:
        (ROOT/"results/v4_capture_manifest.json").write_text(
            json.dumps({"mode":"NO_CAPTURE_PERFORMED","scope":args.scope,
                        "requests":requests,
                        "real_vehicle_observations":0,
                        "no_credentials_embedded":True},ensure_ascii=False,indent=2),encoding="utf-8")
        print(json.dumps({"mode":"DRY_RUN_NO_CALLS","scope":args.scope,
                          "requests":[{k:v for k,v in r.items() if k!="purpose"} for r in requests],
                          "queries_executed":0,
                          "real_vehicle_observations":0},ensure_ascii=False,indent=2))
        return
    if args.output is None:
        p.error("--capture requires --output /private/observations.jsonl")
    try:
        summary=collect(requests,os.environ.get("SEOUL_BUS_API_KEY"),
                        os.environ.get("V4_VEHICLE_SALT"),args.output.resolve())
    except ValueError as err:
        p.error(str(err))
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
