"""Encrypt vehicle-level position evidence; publish only aggregate section and movement counts."""
import argparse, base64, csv, hashlib, hmac, json, os, zlib
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

DETAIL=("request_time_utc","route","route_id","direction","query_scope","section_seq",
        "provider_observation_time","vehicle_type","reported_stop_flag","longitude",
        "latitude","route_distance","section_distance","reported_running_flag",
        "next_station_id","vehicle_pseudonym")
AADS=b"transport-lowfloor-2026-vehicle-evidence-v1"
SECTION=["run_id","observed_at_utc","route","section_seq","vehicle_type","observed_vehicles"]
MOVE=["run_id","observed_at_utc","previous_run_id","route","vehicle_type",
      "matched_vehicles","forward","stationary","backward","unknown","elapsed_minutes"]


def key(secret):
    if not secret: raise ValueError("Secret required to decrypt or encrypt")
    return hmac.new(unquote(secret.strip()).encode(),b"bus-evidence-encryption-v1",hashlib.sha256).digest()


def encrypt(rows,secret):
    clean=[{k:r.get(k) for k in DETAIL} for r in rows]
    if any(not r["vehicle_pseudonym"] for r in clean):raise ValueError("Missing pseudonym")
    nonce=os.urandom(12)
    data=zlib.compress(json.dumps(clean,ensure_ascii=False,separators=(",",":")).encode(),9)
    return {"version":1,"nonce":base64.b64encode(nonce).decode(),
            "ciphertext":base64.b64encode(AESGCM(key(secret)).encrypt(nonce,data,AADS)).decode()}


def decrypt(pack,secret):
    if pack.get("version")!=1:raise ValueError("Unknown record version")
    nonce=base64.b64decode(pack["nonce"],validate=True)
    if len(nonce)!=12:raise ValueError("Invalid nonce")
    payload=base64.b64decode(pack["ciphertext"],validate=True)
    return json.loads(zlib.decompress(AESGCM(key(secret)).decrypt(nonce,payload,AADS)))


def section(x):
    try:return int(x.get("section_seq"))
    except (TypeError,ValueError):return None


def timestamp(value):
    dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    if dt.tzinfo is None:raise ValueError("Timestamp must have timezone")
    return dt.astimezone(timezone.utc)


def public_sections(records,run_id,now):
    groups=defaultdict(set)
    for r in records:
        seq=section(r)
        if seq is not None:
            groups[(str(r["route"]),str(seq),str(r["vehicle_type"]))].add(str(r["vehicle_pseudonym"]))
    return [dict(zip(SECTION,(str(run_id),now,*k,len(v)))) for k,v in sorted(groups.items())]


def public_movements(records,prior,run_id,prior_id,now,prior_at):
    if not prior:return []
    gap=(timestamp(now)-timestamp(prior_at)).total_seconds()/60
    if not 0<gap<=25 or timestamp(now).date()!=timestamp(prior_at).date():return []
    before={(r["route"],r["vehicle_pseudonym"]):r for r in prior}
    grouped=defaultdict(Counter)
    for r in records:
        old=before.get((r["route"],r["vehicle_pseudonym"]))
        if old is None:continue
        c=grouped[(str(r["route"]),str(r["vehicle_type"]))]
        c["matched_vehicles"]+=1
        a,b=section(old),section(r)
        c["unknown" if a is None or b is None else
          "forward" if b>a else "backward" if b<a else "stationary"]+=1
    return [dict(zip(MOVE,(str(run_id),now,str(prior_id),route,typ,
                           c["matched_vehicles"],c["forward"],c["stationary"],
                           c["backward"],c["unknown"],round(gap,2))))
            for (route,typ),c in sorted(grouped.items())]


def merge_csv(path,fields,add):
    old=[]
    if path.exists():
        with path.open(encoding="utf-8",newline="") as f:old=list(csv.DictReader(f))
    known={(r["run_id"],r["route"],r.get("section_seq",""),r["vehicle_type"]) for r in old}
    for r in add:
        ident=(r["run_id"],r["route"],r.get("section_seq",""),r["vehicle_type"])
        if ident not in known:old.append(r);known.add(ident)
    old.sort(key=lambda x:(x["observed_at_utc"],x["run_id"],x["route"],
                           x.get("section_seq",""),x["vehicle_type"]))
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(old)


def archive(enc_path,summary,output_dir,secret,run_id):
    folder=Path(output_dir);folder.mkdir(parents=True,exist_ok=True)
    pack=json.loads(Path(enc_path).read_text(encoding="utf-8"))
    current=decrypt(pack,secret)
    if len(current)!=int(summary["vehicle_snapshots"]):
        raise ValueError("Encrypted and aggregate vehicle counts disagree")
    now=summary["created_at_utc"]
    newest=None
    for p in folder.glob("vehicle-*.enc"):
        prior=json.loads(p.read_text(encoding="utf-8"))
        gap=(timestamp(now)-timestamp(prior["observed_at_utc"])).total_seconds()/60
        if 0<gap<=25 and (newest is None or timestamp(prior["observed_at_utc"])>timestamp(newest[1]["observed_at_utc"])):
            newest=(p,prior)
    prior_rows=decrypt(newest[1],secret) if newest else []
    rows_s=public_sections(current,run_id,now)
    rows_m=public_movements(current,prior_rows,run_id,newest[1]["run_id"] if newest else None,
                            now,newest[1]["observed_at_utc"] if newest else now)
    merge_csv(folder.parent/"vehicle_section_timeseries.csv",SECTION,rows_s)
    merge_csv(folder.parent/"vehicle_transitions.csv",MOVE,rows_m)
    pack.update({"run_id":str(run_id),"observed_at_utc":now})
    (folder/f"vehicle-{run_id}.enc").write_text(json.dumps(pack,separators=(",",":"))+"\n",encoding="utf-8")
    return len(rows_s),len(rows_m)


def main():
    p=argparse.ArgumentParser()
    sub=p.add_subparsers(dest="action",required=True)
    a=sub.add_parser("seal");a.add_argument("--input",type=Path,required=True);a.add_argument("--output",type=Path,required=True)
    a=sub.add_parser("archive");a.add_argument("--input",type=Path,required=True)
    a.add_argument("--summary",type=Path,required=True);a.add_argument("--directory",type=Path,required=True)
    a.add_argument("--run-id",required=True)
    args=p.parse_args()
    secret=os.environ.get("SEOUL_BUS_API_KEY")
    if args.action=="seal":
        rows=[json.loads(x) for x in args.input.read_text(encoding="utf-8").splitlines() if x.strip()]
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(encrypt(rows,secret),separators=(",",":"))+"\n",encoding="utf-8")
        print("Encrypted position observations:",len(rows))
    else:
        receipt=json.loads(args.summary.read_text(encoding="utf-8"))
        section_n,move_n=archive(args.input,receipt,args.directory,secret,args.run_id)
        print("Public section/movement groups:",section_n,move_n)


if __name__=="__main__":main()
