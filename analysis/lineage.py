from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from analysis.analyze import configure

ROOT=Path(__file__).resolve().parents[1]

def main():
    configure()
    c=json.loads((ROOT/'docs/integration_checks.json').read_text())
    fig,ax=plt.subplots(figsize=(11.5,5.2))
    ax.set(xlim=(0,1),ylim=(0,1));ax.axis('off')
    def node(x,y,text,w=.20,h=.11):
        ax.add_patch(plt.Rectangle((x-w/2,y-h/2),w,h,facecolor='white',edgecolor='#788A95',lw=1))
        ax.text(x,y,text,ha='center',va='center',fontsize=11)
    def arrow(a,b,text='',offset=0):
        ax.annotate('',xy=b,xytext=a,arrowprops=dict(arrowstyle='->',color='#667781',lw=1.2))
        if text:ax.text((a[0]+b[0])/2,(a[1]+b[1])/2+offset,text,ha='center',va='bottom',fontsize=9,color='#42545E',bbox=dict(facecolor='white',edgecolor='none',pad=1))
    sources=[(.87,'Divvy 骑行 CSV'),(.69,'出租车 JSON'),(.51,'NOAA 日天气'),(.33,'OPM 节假日'),(.15,'社区边界 GeoJSON')]
    for y,text in sources:node(.13,y,text)
    node(.47,.80,'清洗后出行明细\n去重与时长检查',w=.25,h=.16)
    node(.47,.48,'统一日期与社区键\n坐标落区及编号映射',w=.25,h=.16)
    node(.83,.73,f'日级融合表\n{c["daily_rows"]} 个日期',w=.23,h=.16)
    node(.83,.34,f'社区日期融合表\n{c["community_daily_rows"]:,} 行',w=.23,h=.16)
    arrow((.23,.87),(.345,.84));arrow((.23,.69),(.345,.76))
    arrow((.47,.72),(.47,.56))
    arrow((.23,.51),(.345,.51),'日期',.015)
    arrow((.23,.33),(.345,.45),'日期',-.035)
    arrow((.23,.15),(.345,.42),'空间',0)
    arrow((.595,.52),(.715,.73),'日期',.01)
    arrow((.595,.44),(.715,.34),'日期及社区',-.025)
    ax.text(.83,.57,'天气和节假日比较',ha='center',fontsize=10,color='#42545E')
    ax.text(.83,.18,'社区分布及降水日比较',ha='center',fontsize=10,color='#42545E')
    fig.tight_layout()
    out=ROOT/'results/figures';out.mkdir(parents=True,exist_ok=True)
    fig.savefig(out/'00_data_lineage.png',dpi=180,bbox_inches='tight')
    fig.savefig(out/'00_data_lineage.svg',bbox_inches='tight')
    plt.close(fig)

if __name__=='__main__':main()
