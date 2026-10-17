"""Exhaustive toy-instance sanity benchmark for greedy allocation.

Small synthetic instances only. Verifies that greedy is feasible and measures
its gap relative to EXACT enumeration in these toys, NOT production global
optimality for the Seoul network.
"""
from pathlib import Path
from itertools import product
import json
import numpy as np
import pandas as pd
from analyze_medical import scores
from decision_stress import capped_greedy

ROOT=Path(__file__).resolve().parent


def objective(m,a):
    f=m["f"];n=f.fleet.to_numpy(int);l=f.low.to_numpy(int)
    before=scores(m["C"],m["walk"],l/n)
    after=scores(m["C"],m["walk"],(l+a)/n)
    return float((after-before)@m["weights"])


def brute(m,budget,cap):
    f=m["f"];rest=f.fleet.to_numpy(int)-f.low.to_numpy(int)
    limits=np.minimum(rest,cap)
    best=(-1.0,None)
    for seq in product(*(range(int(c)+1) for c in limits)):
        a=np.array(seq,int)
        if a.sum()>budget:
            continue
        val=objective(m,a)
        if val>best[0]+1e-12:
            best=val,a
    return best


def main():
    rng=np.random.default_rng(20261018)
    rows=[]
    for i in range(25):
        size=4
        n=rng.integers(4,13,size=size)
        low=np.array([rng.integers(0,int(x)) for x in n])
        C=rng.random((9,size))<.44
        walk=np.zeros(9,bool)
        w=rng.random(9);w/=w.sum()
        m={"f":pd.DataFrame({"route":["TOYA","TOYB","TOYC","TOYD"],
                              "fleet":n,"low":low}),
           "C":C,"walk":walk,"weights":w}
        a,_=capped_greedy([m],budget=5,cap_per_route=2)
        exact,aa=brute(m,5,2)
        got=objective(m,a)
        assert got<=exact+1e-10 and a.sum()<=5 and (a<=np.minimum(n-low,2)).all()
        rows.append({
            "seed_case":i+1, "greedy_gain":got, "exhaustive_best_gain":exact,
            "relative_gain":float(got/exact) if exact>1e-12 else 1.,
            "greedy_spent":int(a.sum()),"optimal_spent":int(aa.sum())
        })
    out=ROOT/"results"
    pd.DataFrame(rows).to_csv(out/"toy_greedy_exact.csv",index=False,encoding="utf-8-sig")
    df=pd.DataFrame(rows)
    receipt={
        "passed":True,"toy_instance_count":len(df),
        "worst_relative_gain_vs_exhaustive":float(df.relative_gain.min()),
        "average_relative_gain_vs_exhaustive":float(df.relative_gain.mean()),
        "any_suboptimal_toy_case":bool((df.relative_gain<1-1e-9).any()),
        "cannot_generalize_to_real_network_optimum":True,
        "method":"Exact exhaustive enumeration for 4 routes with ≤2 replacements/route and budget 5, compared with existing greedy."
    }
    (out/"toy_greedy_exact_summary.json").write_text(
        json.dumps(receipt,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(receipt,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
