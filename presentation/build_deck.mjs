import fs from 'node:fs/promises';

const FONT='Heiti TC';
const BLUE='#17678A', ORANGE='#CB7435', TEXT='#162B36', MUTED='#536975';
const LINKS={divvy:'https://divvybikes.com/system-data',taxi:'https://data.cityofchicago.org/d/ajtu-isnz',
  weather:'https://www.ncei.noaa.gov/access/search/data-search/daily-summaries/',
  holiday:'https://www.opm.gov/policy-data-oversight/pay-leave/federal-holidays/',
  geo:'https://data.cityofchicago.org/d/igwz-8jzy'};
const num=n=>Math.round(n).toLocaleString('en-US');

function text(slide,value,x,y,w,h,size=28,color=TEXT,bold=false){
  const shape=slide.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
  shape.text=value;shape.text.style={typeface:FONT,fontSize:size,color,bold};return shape;
}
function add(presentation,title,note=''){
  const s=presentation.slides.add({width:1280,height:720});s.background.fill='#FFFFFF';
  text(s,title,64,42,1152,title.includes('\n')?170:76,title.includes('\n')?60:44,TEXT,true);
  if(note)text(s,note,64,652,1152,45,19,MUTED);
  return s;
}
function node(slide,value,x,y,w=260,h=58){
  const s=slide.shapes.add({geometry:'rect',position:{left:x,top:y,width:w,height:h},fill:'#FFFFFF',line:{fill:'#A7B6BE',width:1}});
  s.text=value;s.text.style={typeface:FONT,fontSize:25,color:TEXT,alignment:'center',verticalAlignment:'middle'};return s;
}
function link(s,a,b){s.shapes.connect(a,b,{kind:'elbow',fromSide:'right',toSide:'left',line:{fill:'#7B8F9A',width:1.5},tail:{type:'arrow',width:'med',length:'med'}});}
function table(slide,values,x,y,w,h,widths){
  const t=slide.tables.add({rows:values.length,columns:values[0].length,left:x,top:y,width:w,height:h,values,columnWidths:widths});
  t.borders.assign({style:'solid',fill:'#D9E0E4',width:1});
  t.cells.block({row:0,column:0,rowCount:values.length,columnCount:values[0].length}).assign({
    textStyle:{typeface:FONT,fontSize:24,color:TEXT},margins:{left:12,right:12,top:12,bottom:12},anchor:'center'});
  t.cells.block({row:0,column:0,rowCount:1,columnCount:values[0].length}).assign({fill:'#DCE9EF',textStyle:{typeface:FONT,fontSize:24,color:TEXT,bold:true}});
  return t;
}
function chart(slide,type,categories,series,position,options={}){
  // Excel chart workbooks use 15 significant digits; retain useful display
  // precision here while full statistical precision stays in results tables.
  series=series.map(s=>({...s,values:s.values.map(v=>Number(v.toFixed(6)))}));
  const c=slide.charts.add(type,{position,categories,series,hasLegend:true,
    lineOptions:{smooth:false},
    legend:{position:'bottom',textStyle:{typeface:FONT,fontSize:21}},
    chartFill:'#FFFFFF',chartLine:{fill:'none',width:0},
    xAxis:{textStyle:{typeface:FONT,fontSize:21}},
    yAxis:{textStyle:{typeface:FONT,fontSize:21},numberFormatCode:'#,##0',majorGridlines:{fill:'#E2E8EC',width:1}},...options});
  return c;
}

export function setup(presentation){
  if(presentation.slides.items.length)throw new Error('setup requires a new presentation');
  let s=add(presentation,'芝加哥天气和节假日\n与城市出行的关系');
  text(s,'共享单车与出租车的多源数据分析',64,240,1120,65,34,BLUE);
  text(s,'研究范围  2024 年全年\n课程  大数据原理与应用',64,420,1120,120,28,MUTED);
  s.speakerNotes.text='研究围绕天气、节假日与社区差异展开。原始数据来自官方公开入口。\n'+Object.values(LINKS).join('\n');
  s=add(presentation,'三个问题与四类独立信源');
  text(s,'天气与日记录量',64,157,640,46,32,BLUE,true);
  text(s,'两种出行记录与 NOAA 天气共同回答',64,208,650,55,26);
  text(s,'节假日与出行时段',64,305,640,46,32,BLUE,true);
  text(s,'两种出行记录与 OPM 日历共同回答',64,356,650,55,26);
  text(s,'社区分布与降水日差异',64,453,650,46,32,BLUE,true);
  text(s,'运营记录与社区边界 天气共同回答',64,504,650,55,26);
  text(s,'Divvy / Lyft\n芝加哥市\nNOAA NCEI\n美国 OPM',850,177,350,320,30,TEXT);
  text(s,'CSV  API  网页  GeoJSON',850,535,350,70,22,MUTED);
  s.speakerNotes.text='独立性按底层记录的形成过程判断：共享单车运营、出租车监管报送、NOAA气象观测、OPM官方日历。共享单车与出租车是独立系统的记录，社区边界作为地理辅助源。Divvy的运营发布方为Lyft，数据所有权归芝加哥市。\n'+Object.values(LINKS).join('\n');
  s=add(presentation,'日期与社区是实际使用的关联键','先分别清洗和聚合，再连接，避免两类订单逐行相乘');
  const sourceLabels=['Divvy 骑行 CSV','出租车记录 JSON','NOAA 日天气','OPM 节假日网页','社区边界 GeoJSON'];
  const sources=sourceLabels.map((v,i)=>node(s,v,64,150+i*88));
  const center=node(s,'清洗与统一键\n当地日期及社区编号',480,300,300,120);
  const daily=node(s,'日级融合表\n天气与日历比较',930,205,285,110);
  const spatial=node(s,'社区日期融合表\n空间分布及降水比较',930,435,285,110);
  for(const n of sources)link(s,n,center);
  link(s,center,daily);link(s,center,spatial);
  s.speakerNotes.text='单车坐标经点落区匹配社区。出租车使用官方社区编号。各自按日期或社区日期聚合后连接，保持键唯一。天气和日历以日期关联。\n'+Object.values(LINKS).join('\n');
}

export async function complete(presentation,root){
  if(presentation.slides.items.length!==3)throw new Error('complete expects the three setup slides');
  const data=JSON.parse(await fs.readFile(root+'/results/deck_data.json','utf8'));
  const audit=JSON.parse(await fs.readFile(root+'/docs/scale_audit.json','utf8'));
  const d=data.summary;
  if(!audit.all_scale_checks_pass)throw new Error('Scale audit must pass before authoring findings');
  const rain=m=>d.models[m].precip_10mm;
  const holiday=m=>d.models[m].holiday;
  const pct=n=>(n>=0?'+':'')+n.toFixed(1)+'%';
  const ci=r=>`${pct(r.percent)}，区间 ${pct(r.low_percent)} 至 ${pct(r.high_percent)}`;
  let s=add(presentation,'数据规模与连接对账','有效规模扣除滑板车与重复记录，ZIP 分页缓存和衍生表不重复计算');
  table(s,[['来源','原始记录','清洗后记录','保留率','社区匹配率'],
    ...[['divvy','Divvy 来源'],['taxi','出租车']].map(([m,label])=>[label,num(d.counts[m].raw),num(d.counts[m].cleaned),d.counts[m].retained_pct.toFixed(2)+'%',(100*d.spatial_match_rates[m]).toFixed(2)+'%'])],64,155,1152,250,[155,255,255,230,257]);
  text(s,`${audit.total_decimal_GB.toFixed(3)} GB 有效原始明细`,64,445,1152,65,37,BLUE,true);
  text(s,`最大单源占比 ${(100*audit.max_source_fraction).toFixed(1)}%。366 个日期，77 个社区。\n日级与小时级总量均与清洗明细对账，空间统计扣除未匹配记录。`,64,525,1152,100,26);
  s.speakerNotes.text='实际统计源：docs/scale_audit.json、docs/integration_checks.json、results/summary.json。每主要源均超过 200 MB。\n'+LINKS.divvy+'\n'+LINKS.taxi;
  s=add(presentation,'天气与两种出行方式的日记录量','来源 Divvy、芝加哥市出租车记录、NOAA，2024 年。单位 千次/日');
  chart(s,'line',data.monthly.map(r=>r.month+'月'),[
    {name:'共享单车',values:data.monthly.map(r=>r.divvy_trips/1000),line:{fill:BLUE,width:3}},
    {name:'出租车',values:data.monthly.map(r=>r.taxi_trips/1000),line:{fill:ORANGE,width:3}}],{left:64,top:145,width:1152,height:350});
  text(s,'每增加 10 mm 日降水的关联变化',64,515,1152,40,27,TEXT,true);
  text(s,`单车 ${ci(rain('divvy'))}\n出租车 ${ci(rain('taxi'))}`,64,565,1152,75,25);
  s.speakerNotes.text='折线为月内平均每日记录量。降水估计来自 log(1+日记录量) 的回归，控制月份、星期、温度一次和二次项、风速、节假日。区间为 HAC 7 日近似95%区间。观察性关联，不解释为因果。\n'+LINKS.divvy+'\n'+LINKS.taxi+'\n'+LINKS.weather;
  s=add(presentation,'节假日与普通工作日的出行时段','来源 Divvy、芝加哥市、OPM，2024。横轴当地小时，纵轴日均每小时记录量（次）');
  const types=[['Weekday','工作日',BLUE],['Weekend','周末',ORANGE],['Federal holiday','联邦节假日','#669773']];
  for(const [i,m] of ['divvy','taxi'].entries()){
    text(s,m==='divvy'?'共享单车':'出租车',64+i*590,140,550,45,29,TEXT,true);
    chart(s,'line',Array.from({length:24},(_,j)=>String(j)),types.map(([type,label,color])=>({name:label,
      values:data.hour_profiles.filter(r=>r.day_type===type).map(r=>r[m+'_trips']),line:{fill:color,width:2.5}})),
      {left:56+i*590,top:195,width:570,height:340});
  }
  text(s,`节假日单车估计 ${pct(holiday('divvy').percent)}（区间跨零），出租车 ${pct(holiday('taxi').percent)}\n全年仅 11 个联邦节假日，不能代表所有居民的实际休假`,64,555,1152,85,26);
  s.speakerNotes.text='小时单位为当地小时，纵轴为每类日期平均每小时记录量。出租车时刻由发布者取整至15分钟。回归节假日区间：单车'+ci(holiday('divvy'))+'；出租车'+ci(holiday('taxi'))+'。\n'+LINKS.divvy+'\n'+LINKS.taxi+'\n'+LINKS.holiday;
  s=add(presentation,'两种方式的起点分布存在社区差异','来源 Divvy、出租车记录、芝加哥社区边界，2024 年。社区起点记录量，单位 万次');
  const top=[...data.community_totals].sort((a,b)=>(b.divvy_trips+b.taxi_trips)-(a.divvy_trips+a.taxi_trips)).slice(0,7);
  chart(s,'bar',top.map(r=>r.community_name),[
    {name:'共享单车',values:top.map(r=>r.divvy_trips/10000),fill:BLUE},
    {name:'出租车',values:top.map(r=>r.taxi_trips/10000),fill:ORANGE}],{left:64,top:145,width:1152,height:410},
    {barOptions:{direction:'bar',grouping:'clustered'},xAxis:{textStyle:{typeface:FONT,fontSize:20}},yAxis:{textStyle:{typeface:FONT,fontSize:20},numberFormatCode:'0'}});
  text(s,'显示两类合计记录最多的 7 个社区。社区日级表支持降水日比较。\n地图及社区标准化结果见报告，不把记录占比解释为全市交通方式占比。',64,565,1152,80,25);
  s.speakerNotes.text='单车通过起点坐标落区，出租车使用上车社区编号。社区对比仅包含成功匹配空间的记录。两种方式全年各至少1万次的社区参与降水日对比，先按社区、月份、星期均值标准化。\n'+LINKS.divvy+'\n'+LINKS.taxi+'\n'+LINKS.geo;
  s=add(presentation,'出租车与天气的三个日级类别','来源 芝加哥市、NOAA，2024。柱形为出租车平均每日记录量，千次；聚类仅作探索');
  chart(s,'bar',data.clusters.map(r=>r.cluster),[
    {name:'出租车',values:data.clusters.map(r=>r.taxi_trips/1000),fill:ORANGE}],{left:64,top:170,width:690,height:350},
    {barOptions:{direction:'column',grouping:'clustered'}});
  table(s,[['类别','天数','均温 ℃'],...data.clusters.map(r=>[r.cluster,String(r.days),r.tavg_c.toFixed(1)])],800,180,410,320,[145,120,145]);
  text(s,`出租车日量、温度、降水和风速，先标准化再做 KMeans\nk=3，随机种子 42，20 次初始化，轮廓系数 ${d.clustering.silhouette.toFixed(3)}`,64,555,1152,85,26);
  s.speakerNotes.text='柱形单位为千次/日。类别按均温由低至高命名A、B、C，固定k=3，没有为了提高指标搜索类别数。轮廓系数只描述当前特征下的类别分离。聚类仅使用出租车和天气，不将Divvy数据放入数据挖掘步骤。\n'+LINKS.taxi+'\n'+LINKS.weather;
  s=add(presentation,'结论与适用范围');
  text(s,`天气\n每 10 mm 降水，单车 ${pct(rain('divvy').percent)}，出租车 ${pct(rain('taxi').percent)}（区间跨零）\n控制日历与天气变量后仍只解释观察性关联`,64,150,1152,125,29);
  text(s,`节假日\n出租车记录量较少，单车的估计区间跨过零\n联邦日历仅有 11 天，代表性有限`,64,320,1152,125,29);
  text(s,'社区\n两种方式的空间集中程度不同\n运营覆盖、车辆供应、人口和局部天气尚未充分校正',64,490,1152,125,29);
  s.speakerNotes.text='具体区间和社区结果见报告。两类记录没有共同乘客ID，不能证明个体发生出行方式替代。出租车有未报送记录，公开记录不能代表全部城市需求。';
  s=add(presentation,'复现流程与 AI 使用');
  text(s,'采集  清洗与关联  分析与绘图  校验与交付',64,155,1152,60,31,BLUE,true);
  text(s,'代码、代表性样本、元数据和 SHA-256 校验清单支持复现\n完整原始运营数据保存在本机，仓库提供重建脚本',64,245,1152,105,28);
  text(s,'AI 参与选题、代码、分析和材料制作\n已记录工具使用、错误修正与核验方法，详见 AI_USAGE.md',64,405,1152,105,28);
  text(s,'项目成员负责理解核心代码、核验结论并如实说明使用经历',64,560,1152,60,27,MUTED);
  s.speakerNotes.text='README 给出采集至结果的运行顺序。AI_USAGE.md 如实记录自动程序检查，不声称学生已完成尚未进行的人工审核。';
  try{
    const repo=JSON.parse(await fs.readFile(root+'/docs/repository.json','utf8'));
    text(s,'仓库 私有  '+repo.url,64,640,1152,42,20,MUTED);
  }catch(error){if(error.code!=='ENOENT')throw error;}
}
