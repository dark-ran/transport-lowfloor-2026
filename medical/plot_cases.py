from font_compat import korean_font
from pathlib import Path
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
r=Path(__file__).resolve().parent
plt.rcParams.update({'font.family':korean_font(),'axes.unicode_minus':False})
fig,ax=plt.subplots(figsize=(10,6));fig.patch.set_facecolor('white');ax.set_xlim(0,1);ax.set_ylim(0,1);ax.axis('off')
cards=[('#e9f4ff','오류2동 ↔ 구로성심병원 | 분기 노선의 직결 예시', ['병원행 6640B: 오류2동주민센터 → 동양미래대학.구로성심병원','귀가행 6640A: 반대편 승강장에서 출발 · 평일 공시 배차 각 14분','분기별 저상비율 미확인 → 기본 모형 제외가 경로 부재는 아님']),('#edf8f2','오금동 ↔ 경찰병원 | 동일 승강장 1회 환승 예시',['병원행 3317 → 가락동미륭아파트 → 301 → 건너말공원입구','귀가행 301 → 가락현대1차아파트정문 → 3317 → 우창아파트','평일 공시 배차 3317 10분 / 301 7분 · 양 끝 직선거리 424m / 422m']),('#fff4e7','내곡동 ↔ 삼성서울병원 | 마을버스 연계 환승 예시',['병원행 452 → 은곡마을.강남신동아파밀리에 → 강남06 → 병원 후문','귀가행 강남06 → 은곡마을.LH이편한세상 → 452 → 샘마을','평일 공시 배차 452 12분 / 강남06 9분 · 양 끝 직선거리 50m / 267m'])]
for k,(color,title,lines) in enumerate(cards):
 y=.97-k*.305;ax.add_patch(FancyBboxPatch((.01,y-.27),.98,.265,boxstyle='round,pad=0.008',facecolor=color,edgecolor='#cbd5df',linewidth=.8));ax.text(.03,y-.035,title,fontsize=14,weight='bold',va='top',color='#18334b')
 for i,line in enumerate(lines):ax.text(.03,y-.105-i*.057,line,fontsize=11.6,va='top',color='#253d4b')
ax.text(.01,.018,'서울시 TOPIS·BIS 노선정보 2026.10.17 취득 | 69개 수집 노선의 순서·회차지 교차검증 예시',fontsize=10,color='#526171');plt.subplots_adjust(left=.01,right=.99,bottom=.01,top=.99);fig.savefig(r/'results/case_validation.png',dpi=200,facecolor='white');plt.close(fig)
