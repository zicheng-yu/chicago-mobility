"""Create the Chinese course report directly from checked run outputs."""
from pathlib import Path
import json
import csv
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH

ROOT=Path(__file__).resolve().parents[1]


def load(name):return json.loads((ROOT/name).read_text(encoding='utf-8'))


def main():
    s=load('results/summary.json');a=load('docs/scale_audit.json');q=load('docs/cleaning_quality.json');checks=load('docs/integration_checks.json')
    bicycle_profile=load('docs/divvy_source_profile.json')
    if not a['all_scale_checks_pass']:raise ValueError('Scale audit has not passed')
    doc=Document();sec=doc.sections[0]
    sec.page_width=Inches(8.27);sec.page_height=Inches(11.69)
    sec.top_margin=Inches(.75);sec.bottom_margin=Inches(.7);sec.left_margin=Inches(.82);sec.right_margin=Inches(.82)
    for sty in ['Normal','Title','Heading 1','Heading 2','Caption']:
        st=doc.styles[sty];st.font.name='Arial';st.font.color.rgb=RGBColor(0,0,0)
        st._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'Songti SC' if sty in ['Normal','Caption'] else 'Heiti SC')
        st.paragraph_format.space_after=Pt(6)
    doc.styles['Normal'].font.size=Pt(11)
    doc.styles['Normal'].paragraph_format.line_spacing=1.22
    doc.styles['Title'].font.size=Pt(21)
    doc.styles['Heading 1'].font.size=Pt(15)
    doc.styles['Heading 1'].paragraph_format.space_before=Pt(13)
    doc.styles['Heading 2'].font.size=Pt(12)
    doc.styles['Caption'].font.size=Pt(9)
    md=[]
    def para(text,style=None):
        p=doc.add_paragraph(text,style)
        md.append(text+'\n')
        return p
    def heading(text):
        doc.add_heading(text,level=1);md.append('## '+text+'\n')
    def table(headers,rows,widths=None):
        t=doc.add_table(rows=1,cols=len(headers));t.alignment=WD_TABLE_ALIGNMENT.CENTER;t.autofit=False
        md.append('| '+' | '.join(headers)+' |\n'+'| '+' | '.join(['---']*len(headers))+' |')
        for i,text in enumerate(headers):t.rows[0].cells[i].text=str(text)
        for row in rows:
            cs=t.add_row().cells
            for i,value in enumerate(row):cs[i].text=str(value)
            md.append('| '+' | '.join(map(str,row))+' |')
        md.append('')
        for ri,row in enumerate(t.rows):
            for ci,cell in enumerate(row.cells):
                if widths:cell.width=Inches(widths[ci])
                cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
                tcPr=cell._tc.get_or_add_tcPr()
                shading=OxmlElement('w:shd');shading.set(qn('w:fill'),'DAE7EF' if ri==0 else ('F5F8FA' if ri%2==0 else 'FFFFFF'));tcPr.append(shading)
                margins=OxmlElement('w:tcMar')
                for side in ['top','left','bottom','right']:
                    el=OxmlElement('w:'+side);el.set(qn('w:w'),'85');el.set(qn('w:type'),'dxa');margins.append(el)
                tcPr.append(margins)
                borders=OxmlElement('w:tcBorders')
                for side in ['top','left','bottom','right']:
                    el=OxmlElement('w:'+side);el.set(qn('w:val'),'single');el.set(qn('w:sz'),'4');el.set(qn('w:color'),'D9D9D9');borders.append(el)
                tcPr.append(borders)
                for p in cell.paragraphs:
                    p.paragraph_format.space_after=Pt(2);p.paragraph_format.line_spacing=1.12
                    for run in p.runs:run.font.size=Pt(9);run.bold=ri==0
        repeat=OxmlElement('w:tblHeader');t.rows[0]._tr.get_or_add_trPr().append(repeat)
        doc.add_paragraph().paragraph_format.space_after=Pt(0)
    def figure(stem,caption,width=6.5):
        p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        p.add_run().add_picture(str(ROOT/'results/figures'/f'{stem}.png'),width=Inches(width))
        p.paragraph_format.line_spacing=1.0
        p.paragraph_format.space_before=Pt(0)
        p.paragraph_format.space_after=Pt(0)
        p.paragraph_format.keep_with_next=True
        para(caption,'Caption')
        md.append(f'![{caption}](../results/figures/{stem}.png)\n')
    def association(mode,term):
        r=s['models'][mode][term]
        return f"{r['percent']:+.1f}%（近似 95% 区间 {r['low_percent']:+.1f}% 至 {r['high_percent']:+.1f}%）"

    title='芝加哥天气和节假日与城市出行的关系'
    doc.add_paragraph(title,'Title');md.append('# '+title+'\n')
    para('基于 2024 年共享单车 出租车 天气 日历与社区边界的多源数据分析')
    para('《大数据原理与应用》课程中期项目')
    heading('研究范围与核心问题')
    para(f"本项目将两个运营数据源与天气、日历和地理边界关联，分析芝加哥 2024 年全年出行记录。Divvy 原始运营记录 {s['counts']['divvy']['raw']:,} 条，原始出租车记录 {s['counts']['taxi']['raw']:,} 条。Divvy 中含滑板车，分析仅保留普通和电助力单车。融合后的日级表覆盖 {s['days']} 天。")
    para('研究问题一是降水和温度与两种出行方式的日记录量有什么关系。问题二是联邦节假日与普通工作日的出行量和小时分布有何差异。问题三是两种方式的社区分布及社区内降水日变化是否一致。三个问题分别需要运营记录与天气、日历或社区边界共同回答，单一来源无法完成这些比较。')
    para('记录量表示各公开系统实际收录的出行次数，不能等同于全市居民的全部需求。两种出行记录没有共同乘客 ID，因此本项目研究共同变化，不能识别个体在两种方式之间的替代。')
    para(f"主要结果中，日降水量增加 10 mm 对应的单车记录量关联变化为 {association('divvy','precip_10mm')}，出租车为 {association('taxi','precip_10mm')}。这些估计来自控制月份、星期、温度与风速的观察性比较。")

    heading('数据来源与实际规模')
    table(['数据','发布者','获取及范围','关联字段'],[
        ['共享单车','Divvy / Lyft','2024 全年月度 CSV','开始日期 起点坐标'],
        ['出租车','芝加哥市','2024 全年逐日 JSON API','开始日期 社区编号'],
        ['日天气','NOAA NCEI','两站 732 个站日观测','观测日期'],
        ['联邦节假日','美国 OPM','官方 2024 年表 11 天','日期'],
        ['社区边界','芝加哥市','77 个社区 GeoJSON','社区编号 点落区']
    ],[1.0,1.0,2.6,1.9])
    para('按底层记录的形成过程识别四类独立信源：共享单车运营系统、出租车监管报送、NOAA 气象观测和 OPM 官方日历。社区边界另作地理辅助。Divvy 由 Lyft 运营发布，数据所有权归芝加哥市；其骑行记录与出租车记录由不同系统独立形成，不是同一底层数据的转载。数据形态覆盖运营明细文件、公开 API、官方网页与地理空间数据。')
    table(['主要源','原始有效字节','十进制 GB','占两主要源比例'],[
        [name,f"{a['source_bytes'][mode]:,}",f"{a['source_bytes'][mode]/1e9:.3f}",f"{a['source_bytes'][mode]/a['total_bytes']:.1%}"]
        for mode,name in [('divvy','共享单车'),('taxi','出租车')]
    ],[1.2,2.2,1.3,1.8])
    para(f"两主要源共 {a['total_decimal_GB']:.3f} GB，即 {a['total_binary_GiB']:.3f} GiB。两源均超过 200 MB，最大单源占比 {a['max_source_fraction']:.1%}。天气、日历和边界为规模较小的辅助数据，没有依靠它们补足总量。")
    para(f"有效规模按原 CSV 的实际记录字节扣除滑板车、无效年份和重复 ID，不计 CSV 表头；单车完整原文件 {a['source_original_file_bytes']['divvy']/1e9:.3f} GB，计入规模的记录 {bicycle_profile['eligible_rows']:,} 条。出租车归档经原始 ID 与日期检查。分页缓存、ZIP 和衍生表不重复计算。JSON 包含字段名开销，不同格式与压缩方式会影响字节规模，因此同时提供记录数、原始校验值和采集记录。完整原始文件保存在本机，仓库保留样本、元数据和重建脚本。")

    heading('清洗与跨源融合')
    figure('00_data_lineage','图 1 多源数据关联与处理流程')
    para('先分别清洗两类出行明细，再按当地日期以及“当地日期、社区编号”聚合，最后连接天气和日历。聚合后的一对一连接避免将同一天的单车与出租车订单直接相乘。时间和空间是两个实际使用的关联维度。')
    para(f"Divvy 先排除 {bicycle_profile['excluded_scope_rows'].get('non_bicycle',0):,} 条非单车记录，再去除缺少 ID 或开始时间、非研究年份、重复 ID、时长缺失及不在 60 秒至 24 小时范围的记录。异常金额和里程仅置为空，不删除整次记录。单车起点以精确点落区匹配社区；出租车使用官方上车社区编号。空间未匹配记录保留在系统日级统计，只从社区分析中排除。日级总量包含社区未知或市域以外的部分起点，应解释为两个系统的有效记录量。")
    rows=[]
    for mode,name in [('divvy','共享单车'),('taxi','出租车')]:
        rs=[r for r in q if r['mode']==mode]
        rows.append(['Divvy 来源' if mode=='divvy' else name,f"{s['counts'][mode]['raw']:,}",f"{s['counts'][mode]['cleaned']:,}",f"{s['counts'][mode]['retained_pct']:.2f}%",f"{s['spatial_match_rates'][mode]:.2%}"])
    table(['数据','原始条数','清洗后条数','保留率','社区匹配率'],rows,[.85,1.5,1.5,1.1,1.55])
    para(f"最终日级表 {checks['daily_rows']} 行、小时表 {checks['hourly_rows']:,} 行、社区日级表 {checks['community_daily_rows']:,} 行。清洗条数与日级总量、小时总量相等；社区总量与清洗条数减去未匹配社区记录相等。完整排除原因保存在 cleaning_quality.json，连接对账保存在 integration_checks.json。")
    para('天气使用奥黑尔和中途机场两站，每天对有效观测求平均。温度是日最高与最低温的均值代理，降水日阈值为至少 1 mm，含降雪液态当量。两站天气无法代表每个社区的局地变化。出租车时间由发布者取整到 15 分钟，因此只比较小时和日级分布。')

    heading('天气与出行的共同变化')
    figure('01_monthly','图 2 两种方式月内平均每日记录量的季节变化')
    figure('02_weather_scatter','图 3 不同温度和降水条件下的日记录量')
    para('月均和散点图用于识别季节性，不能直接把冷暖季差异解释为温度造成的变化。为区分日历因素，补充一个简单回归：以 log(1＋日记录量) 为因变量，解释变量为每 10 mm 降水、温度一次项和二次项、风速、节假日标记、月份与星期类别。采用 7 日滞后的 Newey–West 协方差给出近似区间。')
    figure('03_adjusted_associations','图 4 控制日历和天气变量后的关联估计')
    para(f"问题一的回答是：在上述控制条件下，每增加 10 mm 日降水，单车记录量的关联变化为 {association('divvy','precip_10mm')}，出租车为 {association('taxi','precip_10mm')}。有效回归样本 {s['model_rows']} 天。区间包含零时，不能据此确定稳定的方向。")

    heading('节假日与出行时段')
    figure('04_daytype_hours','图 5 普通工作日 周末与联邦节假日的平均小时分布')
    para(f"问题二的回答是：控制其他变量后，联邦节假日的单车记录量关联变化为 {association('divvy','holiday')}，出租车为 {association('taxi','holiday')}。小时曲线按每类日期实际天数计算平均，避免把 11 个节假日的总量直接与大量工作日比较。")
    para('单车节假日估计的区间跨过零，方向尚不稳定；出租车估计区间全部位于零以下。样本内的工作日单车曲线有早晚峰，周末及节假日更多集中在日间，但不能据此推断每条记录的实际出行目的。')
    para('联邦节假日仅是统一日历标记，不能代表所有人的实际休假。全年仅 11 个节假日，小样本、旅游活动和未观测事件都会影响结果，不能将差异推广到所有假期。')

    heading('社区分布与降水日差异')
    figure('05_community_maps','图 6 两种方式在 77 个社区的全年起点分布',width=5.8)
    figure('06_community_precip','图 7 社区内按月份和星期标准化后的降水日比较')
    totals=list(csv.DictReader((ROOT/'results/community_totals.csv').open()))
    divvy_top=sorted(totals,key=lambda r:float(r['divvy_trips']),reverse=True)[:3]
    taxi_top=sorted(totals,key=lambda r:float(r['taxi_trips']),reverse=True)[:3]
    para('问题三的回答是：两种方式的社区分布存在可见差异。单车记录最多的三个社区为'+ '、'.join(r['community_name'] for r in divvy_top)+'；出租车为'+ '、'.join(r['community_name'] for r in taxi_top)+'。图中两幅地图使用同一 log10(1＋次数) 色标，显示的是记录量，不是人口校正后的出行率。')
    para(f"降水日比较仅保留两类全年记录都至少 1 万次的 {s['spatial_comparable_communities']} 个社区，先以社区、月份和星期对应的均值标准化。横纵轴分别是两种方式降水日与非降水日的相对差异。该比较仍可能受温度、可用车辆和未观测活动影响，不作社区层面的因果推断。")
    spatial_counts=s['community_precip_counts']
    para(f"在这 {spatial_counts['compared']} 个社区中，{spatial_counts['bicycle_lower']} 个社区的单车降水日指数低于非降水日；出租车有 {spatial_counts['taxi_higher']} 个社区较高、{spatial_counts['taxi_lower']} 个较低。两类系统的样本内变化并不一致，也不能证明同一批人由单车转乘出租车。")

    heading('联合特征的简单聚类')
    figure('07_day_clusters','图 8 出租车与天气联合特征的 KMeans 聚类')
    para(f"数据挖掘环节使用标准化后的出租车日量、温度、降水和风速四个特征做 KMeans，固定 k＝3、随机种子 42、20 次初始化。轮廓系数为 {s['clustering']['silhouette']:.3f}。类别按平均温度排序命名 A、B、C，便于解释，不将类别视为客观存在的出行人群。结合 Divvy 许可的使用范围，聚类步骤只使用市政府出租车数据与 NOAA 天气，单车用于常规统计比较。")
    table(['类别','天数','出租车日均 次','温度 ℃','降水 mm','风速 m/s'],[
        [r['cluster'],int(r['days']),f"{r['taxi_trips']:,.0f}",f"{r['tavg_c']:.1f}",f"{r['precip_mm']:.1f}",f"{r['wind_mps']:.1f}"]
        for r in s['clustering']['profiles']],[.7,.6,1.6,1.0,1.0,1.0])
    para('聚类在同一组数据上进行探索，没有独立测试集，也不用于预测性能评价。类别分离的一部分来自季节性与所选特征，不能根据聚类直接判断某种天气造成了某种行为。')

    heading('结论 局限与复现')
    para('本项目通过日期关联、社区编号映射与单车坐标落区，构建了可以共同分析的多源数据体系，并回答了天气、节假日和社区差异三个问题。分析刻意采用分组统计、简单回归和聚类，主要工程工作集中在真实数据获取、清洗记录和连接对账。')
    para('局限包括：公开运营记录不覆盖全部交通方式，出租车存在未报送记录，两个机场站的天气只是城市代理，社区未按人口或车辆供应量校正，节假日样本较少，观察性关联仍有未观测混杂。两类记录中出现相反变化，也不能证明同一批人发生了方式替代。')
    para('复现顺序为采集、清洗融合、分析、规模检查。完整命令位于 README.md。原始文件的 SHA-256、字节数和采集日志可核对采集快照；历史源若发生修订，结果可能变化。仓库交付代码、代表性样本、完整融合表、图表和元数据，不上传完整原始运营数据。')
    heading('AI 使用说明')
    para('项目从 2026 年 11 月 10 日起使用 OpenAI Codex，参与选题、数据源核查、采集与清洗代码、分析、可视化及材料整理。当前会话没有提供可核验的底层模型版本字符串，因此未推测填写。代表性指令是“定一个选题然后目标是完成，不用太复杂的”，据此采用公开数据、明确的日期和社区键，以及简单统计与聚类。')
    para('采用了 AI 起草的代码框架，但根据真实字段与许可修改了方案：将单车会员与出租车支付方式分列，排除滑板车，将聚类限定为出租车与天气，并为不稳定传输增加分页缓存。核验方式包括官方逐月 count 对账、SHA-256、独立流式字节核算与数据框清洗结果比较，以及清洗明细与各聚合层总量对账。图表和本报告的数字均读取运行结果。')
    para('AI 提高了接口查找和初稿实现的效率，也把较多工作转向了字段语义、范围与结果核验。实际问题包括证书链、网络中断、源文件跨月、时间精度及来源名称与真实车型不完全一致，均据原始数据或官方说明修正。完整代表指令、采用和放弃情况、错误与反思见 AI_USAGE.md；本项目没有把程序检查写成学生人工审核经历，成员仍需理解核心逻辑并对最终提交内容负责。')
    heading('数据来源')
    for text in ['[1] Divvy 数据及许可 https://divvybikes.com/system-data',
                 '[2] 芝加哥 Taxi Trips 2024 https://data.cityofchicago.org/d/ajtu-isnz',
                 '[3] NOAA 日汇总数据 https://www.ncei.noaa.gov/access/search/data-search/daily-summaries/',
                 '[4] OPM 联邦节假日 https://www.opm.gov/policy-data-oversight/pay-leave/federal-holidays/',
                 '[5] 芝加哥社区边界 https://data.cityofchicago.org/d/igwz-8jzy']:
        p=para(text);p.paragraph_format.space_after=Pt(3)
        for run in p.runs:run.font.size=Pt(9)
    repo_path=ROOT/'docs/repository.json'
    if repo_path.exists():
        repo=load('docs/repository.json')
        heading('代码与数据复现')
        p=para('代码仓库 '+repo['url']+'（私有，评阅人需授权）')
        for run in p.runs:run.font.size=Pt(9)
    footer=sec.footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.CENTER
    r=footer.add_run();r.font.size=Pt(9);field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGE');r._r.addnext(field)
    out=ROOT/'deliverables';out.mkdir(exist_ok=True)
    for container in [doc._element,doc.styles._element]:
        for border in container.xpath('.//w:pBdr'):
            border.getparent().remove(border)
    doc.save(out/'芝加哥城市出行多源分析报告.docx')
    (out/'项目报告.md').write_text('\n'.join(md),encoding='utf-8')
    print(out/'芝加哥城市出行多源分析报告.docx')


if __name__=='__main__':main()
