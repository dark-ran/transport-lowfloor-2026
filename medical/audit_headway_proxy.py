"""Independently recompute reported headway proxy scores from saved allocations."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from decision_stress import load_models

ROOT=Path(__file__).resolve().parent


def verify():
    out=ROOT/"results"
    origins, models=load_models()
    m=models["기본"]
    f=m["f"]
    n=f.fleet.to_numpy(int)
    old=f.low.to_numpy(int)
    routes=f.route.astype(str).tolist()
    matched=pd.read_csv(out/"headway_matched_routes.csv",dtype={"route":str}).set_index("route")
    h=np.array([matched.loc[r,"nominal_weekday_headway_min"] for r in routes],float)
    rows=pd.read_csv(out/"headway_proxy_sensitivity.csv")
    allocation=pd.read_csv(out/"headway_policy_coverage.csv",dtype={"route":str})
    known=np.isfinite(h)
    observable=m["walk"] | m["C"][:,known].any(axis=1)
    w=m["weights"].copy()
    w[~observable]=0
    assert w.sum()>0
    w/=w.sum()
    checks=0
    for policy,group in allocation.groupby("policy"):
        amap=group.set_index("route").replacements.to_dict()
        a=np.array([amap.get(r,0) for r in routes],int)
        assert a.sum()==50 and (a<=n-old).all()
        for mins in [10,15,20]:
            factor=np.zeros(len(h))
            factor[known]=np.minimum(1.,mins/h[known])
            def calc(v):
                v=(v/n)*factor
                z=np.max(np.where(m["C"],v[None,:],0),axis=1)
                z[m["walk"]]=1
                return z
            a0=calc(old)
            a1=calc(old+a)
            delta=float(np.maximum(0,a1-a0)@w)
            r=rows[(rows.policy==policy)&(rows.reference_min==mins)]
            assert len(r)==1
            assert abs(delta-r.iloc[0].proxy_gain_observable)<1e-12
            checks+=1
    assert checks==len(rows)
    receipt={
        "passed":True,
        "fixed_policy_reference_checks":checks,
        "published_weekday_headways_only":True,
        "unmatched_headways_not_imputed":True,
        "observed_vehicle_level_departures":False,
        "scope":"Independent formula recomputation from saved allocations and matched headways; not a real-world travel-time validation."
    }
    (out/"headway_proxy_audit.json").write_text(
        json.dumps(receipt,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(receipt,ensure_ascii=False,indent=2))


if __name__=="__main__":
    verify()
