"""V12 acquire primary GIS from immutable commit, verify Git blob SHA.

The original geodata is in this repository's medical/data directory.
This script is for stand-alone ZIP users who need to reproduce raw geometry.
Usage: python medical/v12_fetch_primary_gis.py --target <directory>
"""
import argparse,hashlib,urllib.request
from pathlib import Path
COMMIT="c93b9cf04aae023d9b2b9a9b4c1dc6af90f26b52"
SHA={"route_stops.csv":"b70e310e42598ce5bb6a0d0bf6237a63f71b4c76",
     "hospitals.csv":"73800b19e320b9fcba2b1a481f7866267a71d278"}
def blob(data):return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
def obtain(destination):
    dest=Path(destination);dest.mkdir(parents=True,exist_ok=True)
    for file,sha in SHA.items():
        p=dest/file
        if p.exists():content=p.read_bytes()
        else:
            url=f"https://raw.githubusercontent.com/dark-ran/transport-lowfloor-2026/{COMMIT}/medical/data/{file}"
            content=urllib.request.urlopen(url,timeout=30).read()
        if blob(content)!=sha:raise ValueError("Pinned source hash mismatch: "+file)
        p.write_bytes(content)
    return tuple(dest/name for name in SHA)
if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument("--target",type=Path,required=True)
    args=a.parse_args()
    for p in obtain(args.target):print(str(p))
