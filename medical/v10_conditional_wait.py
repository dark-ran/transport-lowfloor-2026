"""V10 deterministic conditional time-to-first-low-floor-bus bounds.
Not observed passenger wait or measured policy effect. Uses fixed cyclic fleet
slots, no cancellation, exactly periodic all-bus headway H, uniform arrivals,
and all low-floor vehicles usable. Run directly without external libraries.
"""
import csv, itertools, math
from pathlib import Path

CASES={
 "343":(15,18,12,5,"Samsung Medical Center"),
 "662":(12,17,13,4,"Seonam Hospital"),
 "3413":(9,26,21,5,"Gangdong Kyung Hee University Hospital")
}
def bounds(h,n,l):
    if not(h>0 and n>=l>=1):raise ValueError("H>0 and 1<=L<=N")
    q,r=divmod(n,l)
    mn=h*((l-r)*q*q+r*(q+1)**2)/(2*n)
    mx=h*((n-l+1)**2+l-1)/(2*n)
    return mn,mx

def exact_from_positions(h,n,slots):
    s=sorted(set(slots))
    if not s or s[0]<0 or s[-1]>=n:raise ValueError("Invalid slots")
    gaps=[(s[(i+1)%len(s)]-s[i])%n or n for i in range(len(s))]
    if sum(gaps)!=n:raise AssertionError("Bad cycle")
    return h*sum(g*g for g in gaps)/(2*n)

def audit():
    for n in range(1,9):
        for low in range(1,n+1):
            values=[exact_from_positions(1,n,c) for c in itertools.combinations(range(n),low)]
            a,b=bounds(1,n,low)
            assert abs(min(values)-a)<1e-10 and abs(max(values)-b)<1e-10
    return 36

def build():
    rows=[]
    for route,(h,n,l,added,clinic) in CASES.items():
        old=bounds(h,n,l);new=bounds(h,n,l+added)
        rows.append({"route":route,"hospital":clinic,"nominal_all_bus_headway_min":h,
          "assumed_fixed_bus_slots":n,"baseline_assumed_lowfloor":l,
          "hypothetical_added_lowfloor":added,
          "baseline_min_wait_min":round(old[0],6),
          "baseline_max_wait_min":round(old[1],6),
          "post_min_wait_min":round(new[0],6),
          "post_max_wait_min":round(new[1],6),
          "hypothetical_change_lower_min":round(old[0]-new[1],6),
          "hypothetical_change_upper_min":round(old[1]-new[0],6)})
    return rows

if __name__=="__main__":
    assert audit()==36
    for x in build():print(x)
