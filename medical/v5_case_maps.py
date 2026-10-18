"""Generate three 2025-static-stop coordinate diagrams for 2026 archived medical cases.

Usage:
  python medical/v5_case_maps.py
These schematic figures are NOT road network maps, GPS tracks, or wheelchair
accessible paths. 2025 stop sequence and 2026 archived order must NOT be merged
as one certified contemporaneous route.
"""
from pathlib import Path
import csv,json,math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse

BASE=Path(__file__).resolve().parent
TARGETS={
"343":("대치2동","삼성서울병원"),
"662":("개봉1동","서울특별시서남병원"),
"3413":("천호1동","강동경희대학교병원")
}

def rows(path):
    with Path(path).open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def source_cases():
    stops=rows(BASE/"data/route_stops.csv")
    origins=rows(BASE/"data/origins.csv")
    hospitals=rows(BASE/"data/hospitals.csv")
    directional=rows(BASE/"results/v4_directional_pairs.csv")
    for route,(dong,name) in TARGETS.items():
        route_stops=sorted((s for s in stops if s["route"]==route),key=lambda s:int(s["seq"]))
        origin=next(x for x in origins if x["dong"]==dong)
        hospital=next(x for x in hospitals if x["name"]==name)
        example=next(x for x in directional if x["route"]==route and x["dong"]==dong and x["hospital"]==name)
        out=json.loads(example["outward_leg"])
        back=json.loads(example["return_leg"])
        if not(example["forward_direct"]=="True" and example["return_direct"]=="True"):
            raise ValueError("Not a bidirectional archived static example: "+route)
        anchors=[]
        for label,ars in (
            ("A 병원행 승차",out["board_ars"]),("B 병원행 하차",out["alight_ars"]),
            ("C 귀가행 승차",back["board_ars"]),("D 귀가행 하차",back["alight_ars"])
        ):
            matches=[x for x in route_stops if x["ARS_ID"].lstrip("0")==str(ars).lstrip("0")]
            if not matches:raise ValueError("ARS missing from 2025 stop inventory: "+str((route,ars)))
            anchors.append((label,(float(matches[0]["lon"]),float(matches[0]["lat"]))))
        yield route,dong,name,route_stops,origin,hospital,anchors

def draw(destination):
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    plt.rcParams["font.family"]="NanumGothic";plt.rcParams["axes.unicode_minus"]=False
    colors=["#236d9b","#6ba4c5","#995d8b","#b58ba8"]
    for route,dong,name,stops,origin,hosp,anchors in source_cases():
        o=(float(origin["lon"]),float(origin["lat"]))
        h=(float(hosp["lon"]),float(hosp["lat"]))
        pts=[o,h]+[p for label,p in anchors]
        xlo=min(x for x,y in pts)-.008;xhi=max(x for x,y in pts)+.008
        ylo=min(y for x,y in pts)-.007;yhi=max(y for x,y in pts)+.007
        fig,ax=plt.subplots(figsize=(10,5.1))
        xs=[float(s["lon"]) for s in stops];ys=[float(s["lat"]) for s in stops]
        ax.plot(xs,ys,lw=1.6,c="#a9b5c1",label="2025 정류장 순서 연결(간략 개념)")
        ax.scatter([o[0]],[o[1]],c="#087c87",marker="s",s=130,zorder=6,label="행정동 대표점")
        ax.scatter([h[0]],[h[1]],c="#d47330",marker="*",s=220,zorder=7,label="종합병원 등록 좌표")
        ax.add_patch(Ellipse(h,width=1000/(111320*math.cos(math.radians(h[1]))),
                              height=1000/111320,fill=False,edgecolor="#d47330",linestyle="--",lw=1.6))
        for (label,pt),color in zip(anchors,colors):
            ax.scatter([pt[0]],[pt[1]],s=80,color=color,edgecolor="white",zorder=8,label=label)
        for p,q,col in ((o,anchors[0][1],"#087c87"),(anchors[1][1],h,"#d47330"),
                        (h,anchors[2][1],"#d47330"),(anchors[3][1],o,"#087c87")):
            ax.plot([p[0],q[0]],[p[1],q[1]],ls=":",lw=1.5,color=col)
        ax.annotate(dong,o,xytext=(5,5),textcoords="offset points")
        ax.annotate(name,h,xytext=(5,9),textcoords="offset points")
        ax.set_xlim(xlo,xhi);ax.set_ylim(ylo,yhi)
        ax.set_aspect(1/math.cos(math.radians(h[1])))
        ax.ticklabel_format(useOffset=False,style="plain")
        ax.set_xlabel("경도 / WGS84");ax.set_ylabel("위도 / WGS84")
        ax.set_title(route+"번 · "+dong+" — "+name)
        ax.legend(fontsize=8,ncol=3,loc="lower left")
        ax.grid(alpha=.15)
        fig.text(.06,.01,"경로는 2025 정적 좌표 순서 선분; 점선은 직선 보행거리 설명. 실제 도로·무장애 경로 아님.",fontsize=9)
        fig.tight_layout(rect=[0,.04,1,1])
        fig.savefig(destination/("v5_case_"+route+".png"),dpi=200)
        plt.close(fig)

if __name__=="__main__":
    draw(BASE/"results/submission_v5")
