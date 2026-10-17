from font_compat import korean_font
from pathlib import Path
import pandas as pd,json
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
ROOT=Path(__file__).resolve().parent

def main():
 r=ROOT/'results';d=pd.read_csv(r/'fixed_allocation_stress.csv');pol=['예외제외 비례','의료연결 우선','예외제외·노선당5대 의료우선','예외제외·5조건 강건5대'];labels=['비례','의료우선','분산형 5대','강건형 5대'];colors=['#99a7b8','#23859c','#227852','#ab804b'];base=d[d.scenario=='기본'].set_index('policy');agg=d.groupby('policy').delta_index.agg(['min','max'])
 plt.rcParams.update({'font.family':korean_font(),'axes.unicode_minus':False,'font.size':10});fig,ax=plt.subplots(1,2,figsize=(10,4.6));y=np.arange(4)
 for i,p in enumerate(pol):
  ax[0].plot([agg.loc[p,'min']*100,agg.loc[p,'max']*100],[i,i],color=colors[i],linewidth=6,alpha=.45);ax[0].plot(base.loc[p,'delta_index']*100,i,'o',color=colors[i],markersize=8)
  ax[1].scatter(base.loc[p,'changed_dongs'],base.loc[p,'delta_index']*100,s=90,c=colors[i]);ax[1].annotate(labels[i],(base.loc[p,'changed_dongs'],base.loc[p,'delta_index']*100),xytext=(4,5),textcoords='offset points',fontsize=9)
 ax[0].set_yticks(y,labels);ax[0].invert_yaxis();ax[0].set(xlabel='공급지수 증가 ×100 (선: 8설정 범위 / 점: 기본)',title='같은 배분표를 조건별로 재평가');ax[0].set_xlim(0,2.5)
 ax[1].set(xlabel='기본 조건에서 지수가 증가한 동 수',ylabel='기본 공급지수 증가 ×100',title='효율과 개선 지역 수의 교환관계',xlim=(15,90),ylim=(0,2.15));ax[1].grid(alpha=.2)
 fig.text(.02,.012,'모형상 비교이며 실제 수혜·통행시간 효과가 아님. 5대 상한은 분산 배분 가정, 실제 노선별 교체 가능 대수와 다름.',fontsize=9);fig.tight_layout(rect=(0,.05,1,1));fig.savefig(r/'decision_stress.png',dpi=200);plt.close(fig)
if __name__=='__main__':main()
