import fs from 'node:fs/promises';

const C={navy:'#102A33',paper:'#F7F3EA',ink:'#16373D',muted:'#60797D',teal:'#168A7A',gold:'#D79A2D',grid:'#D9E0D8',pale:'#C5D8D5',white:'#FFFFFF',slate:'#69899A'};
const F='Heiti TC',N='Helvetica Neue';
const URL={bike:'https://divvybikes.com/system-data',taxi:'https://data.cityofchicago.org/d/ajtu-isnz',weather:'https://www.ncei.noaa.gov/access/search/data-search/daily-summaries/',holiday:'https://www.opm.gov/policy-data-oversight/pay-leave/federal-holidays/',geo:'https://data.cityofchicago.org/d/igwz-8jzy'};
const pct=v=>(v<0?'−':'+')+Math.abs(v).toFixed(1)+'%';
const short=v=>Math.round(v).toLocaleString('en-US');

function txt(s,value,x,y,w,h,size=28,color=C.ink,bold=false,number=false,align='left'){
  const a=s.shapes.add({name:value.slice(0,35),geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
  a.text=value;
  a.text.style={typeface:number?N:F,fontSize:size,color,bold,alignment:align,insets:0,verticalAlignment:'top',wrap:'square'};
  return a;
}
function rect(s,x,y,w,h,fill,line='none',lw=0){
  return s.shapes.add({geometry:'rect',position:{left:x,top:y,width:w,height:h},fill,line:{fill:line,width:lw}});
}
function line(s,x1,y1,x2,y2,color=C.grid,width=1,dash='solid'){
  return s.shapes.add({geometry:'line',position:{left:Math.min(x1,x2),top:Math.min(y1,y2),width:Math.abs(x2-x1),height:Math.abs(y2-y1)},fill:'none',line:{fill:color,width,style:dash}});
}
function page(p,title,index,{dark=false,source=''}={}){
  const s=p.slides.add({width:1280,height:720});s.background.fill=dark?C.navy:C.paper;
  txt(s,title,64,51,1150,86,44,dark?C.paper:C.ink,true);
  if(source)txt(s,source,64,673,1070,30,17,dark?C.pale:C.muted);
  txt(s,String(index).padStart(2,'0'),1150,672,66,28,17,dark?C.pale:C.muted,false,true,'right');
  return s;
}
function notes(s,text,links=[]){s.speakerNotes.text=text+'\n'+links.join('\n');}
function nativeChart(s,type,categories,series,frame,{max=undefined,major=undefined,labels=false,legend=false,format='#,##0',font=21}={}){
  const data=series.map(a=>({...a,values:a.values.map(v=>Number(v.toFixed(6)))}));
  return s.charts.add(type,{
    position:frame,categories,series:data,hasLegend:legend,
    legend:{position:'bottom',textStyle:{typeface:F,fontSize:font,color:C.muted}},
    chartFill:C.paper,plotAreaFill:C.paper,chartLine:{fill:'none',width:0},plotAreaLine:{fill:'none',width:0},
    lineOptions:{smooth:false},barOptions:{direction:'column',grouping:'clustered',gapWidth:110},
    xAxis:{textStyle:{typeface:F,fontSize:font,color:C.muted},line:{fill:C.grid,width:1},majorGridlines:null},
    yAxis:{min:0,...(max!==undefined?{max}:{}),...(major!==undefined?{majorUnit:major}:{}),numberFormatCode:format,
      textStyle:{typeface:N,fontSize:font,color:C.muted},line:{fill:'none',width:0},majorGridlines:{fill:C.grid,width:1}},
    dataLabels:{showValue:labels,position:'outEnd',numberFormatCode:'0.0',textStyle:{typeface:N,fontSize:23,color:C.ink,bold:true}}
  });
}
function colorMix(a,b,t){
  const aa=a.replace('#',''),bb=b.replace('#','');
  const cc=[0,2,4].map(i=>Math.round(parseInt(aa.slice(i,i+2),16)*(1-t)+parseInt(bb.slice(i,i+2),16)*t).toString(16).padStart(2,'0'));
  return '#'+cc.join('');
}
function nativeTable(s,values,frame,widths,{size=24,header=true}={}){
  const t=s.tables.add({rows:values.length,columns:values[0].length,...frame,columnWidths:widths,values});
  t.borders.assign({fill:C.grid,width:1,style:'solid'});
  t.cells.block({row:0,column:0,rowCount:values.length,columnCount:values[0].length}).assign({fill:C.paper,
    textStyle:{typeface:F,fontSize:size,color:C.ink},margins:{left:12,right:12,top:14,bottom:14},anchor:'center'});
  if(header)t.cells.block({row:0,column:0,rowCount:1,columnCount:values[0].length}).assign({fill:C.navy,textStyle:{typeface:F,fontSize:size,color:C.paper,bold:true}});
  return t;
}
function legend(s,items,x,y,{gap=170,size=22}={}){
  items.forEach(([label,color],i)=>{line(s,x+i*gap,y+14,x+i*gap+30,y+14,color,4);txt(s,label,x+41+i*gap,y,130,34,size,C.muted);});
}
async function photo(s,path,frame){return s.images.add({path,alt:'芝加哥雨夜交通氛围示意图，AI生成',fit:'cover',position:frame});}

function forest(s,models){
  const left=621,right=1198,top=219,bottom=497,lo=-32,hi=8;
  const px=v=>left+(v-lo)/(hi-lo)*(right-left);
  for(const v of [-30,-20,-10,0,5]){
    line(s,px(v),top,px(v),bottom,v===0?C.muted:C.grid,v===0?1.7:1);
    txt(s,String(v),px(v)-26,bottom+21,52,30,21,C.muted,false,true,'center');
  }
  [['divvy','共享单车',C.teal,297],['taxi','出租车',C.gold,427]].forEach(([id,label,color,y])=>{
    const r=models[id].precip_10mm;
    txt(s,label,473,y-18,135,40,26,C.ink,true);
    line(s,px(r.low_percent),y,px(r.high_percent),y,color,5);
    for(const v of [r.low_percent,r.high_percent])line(s,px(v),y-11,px(v),y+11,color,2);
    s.shapes.add({geometry:'ellipse',name:label+'关联估计 '+r.percent,position:{left:px(r.percent)-8,top:y-8,width:16,height:16},fill:color,line:{fill:C.paper,width:2}});
  });
  txt(s,'记录量关联变化（%）',720,558,380,38,23,C.muted,false,false,'center');
  txt(s,'线段为近似 95% 区间',729,603,360,32,21,C.muted,false,false,'center');
}

function maps(s,geo,totals){
  const all=geo.features.flatMap(f=>f.polygons.flatMap(p=>p.flatMap(r=>r)));
  const cos=Math.cos(41.9*Math.PI/180);
  const minX=Math.min(...all.map(p=>p[0]*cos)),maxX=Math.max(...all.map(p=>p[0]*cos));
  const minY=Math.min(...all.map(p=>-p[1])),maxY=Math.max(...all.map(p=>-p[1]));
  const lookup=new Map(totals.map(r=>[r.community_id,r]));
  const bounds=[];
  for(const [mode,x,color,base] of [['divvy',455,C.teal,'#E4EEE8'],['taxi',845,C.gold,'#F5E9D2']]){
    const frame={left:x,top:190,width:350,height:381};
    const scale=Math.min(frame.width/(maxX-minX),frame.height/(maxY-minY));
    const ox=frame.left+(frame.width-(maxX-minX)*scale)/2,oy=frame.top;
    const convert=p=>[(p[0]*cos-minX)*scale+ox,(-p[1]-minY)*scale+oy];
    for(const f of geo.features){
      const rings=f.polygons.flatMap(p=>p.map(r=>r.map(convert)));
      const points=rings.flat();
      const x0=Math.min(...points.map(p=>p[0])),x1=Math.max(...points.map(p=>p[0]));
      const y0=Math.min(...points.map(p=>p[1])),y1=Math.max(...points.map(p=>p[1]));
      const commands=[];
      for(const ring of rings){
        ring.forEach((p,i)=>commands.push(i?{lineTo:{x:p[0]-x0,y:p[1]-y0}}:{moveTo:{x:p[0]-x0,y:p[1]-y0}}));
        commands.push({close:{}});
      }
      const n=lookup.get(f.id)?.[mode+'_trips']??0;
      s.shapes.add({name:`${mode} ${f.id} ${f.name} ${n} 次`,geometry:'custom',position:{left:x0,top:y0,width:x1-x0,height:y1-y0},
        fill:colorMix(base,color,Math.min(1,Math.log10(1+n)/6.2)),line:{fill:C.paper,width:.65},customPaths:[{width:x1-x0,height:y1-y0,commands}]});
      if(mode==='taxi'&&f.id===76){const p=convert(f.label_point);bounds.push(p);}
    }
    txt(s,mode==='divvy'?'共享单车':'出租车',x,145,350,38,28,color,true,false,'center');
    rect(s,x+70,594,210,10,`linear(0deg, ${base} 0%, ${color} 100%)`);
    for(const [v,label] of [[0,'0'],[3,'1千'],[6,'100万']])txt(s,label,x+70+210*v/6.2-24,612,60,26,18,C.muted,false,false,'center');
  }
  if(bounds.length){const [x,y]=bounds[0];txt(s,'O’Hare',x-38,y-30,95,28,19,C.ink,true);}
}

export async function buildRedesign(p,root){
  const data=JSON.parse(await fs.readFile(root+'/results/deck_data.json','utf8'));
  const audit=JSON.parse(await fs.readFile(root+'/docs/scale_audit.json','utf8'));
  const geo=JSON.parse(await fs.readFile(root+'/presentation/assets/community-display.json','utf8'));
  const visual=JSON.parse(await fs.readFile(root+'/presentation/assets/visual_data.json','utf8'));
  const repo=JSON.parse(await fs.readFile(root+'/docs/repository.json','utf8'));
  const d=data.summary;
  if(!audit.all_scale_checks_pass)throw new Error('Verified study data required');
  if(p.slides.items.length)throw new Error('Redesign requires an empty presentation copy');

  // 1 The generated image is cover atmosphere only. All title text is editable.
  let s=p.slides.add({width:1280,height:720});s.background.fill=C.navy;
  await photo(s,root+'/presentation/assets/chicago-rain-cover.png',{left:0,top:0,width:1280,height:720});
  txt(s,'CHICAGO  2024',64,74,570,44,25,C.pale,false,true);
  txt(s,'天气、节假日\n与城市出行',64,202,640,177,66,C.paper,true);
  txt(s,'共享单车与出租车的多源数据分析',68,425,650,57,28,C.paper);
  txt(s,'大数据原理与应用  课程中期项目',68,632,690,35,22,C.pale);
  txt(s,'封面示意图',1070,674,146,28,16,C.pale,false,false,'right');
  notes(s,'封面由内置 image_gen 生成，仅为氛围示意，不是特定事件的实拍记录。统计数据与此前核验版本一致。完整提示词与资产来源见 presentation/assets/README.md。',Object.values(URL));

  // 2 Questions use a typographic composition rather than repeated panels.
  s=page(p,'研究问题与数据范围',2,{source:'四类独立形成过程，另附社区边界；研究对象为普通和电助力单车。'});
  txt(s,'366',64,172,350,135,116,C.teal,false,true);
  txt(s,'天',279,247,60,48,32,C.ink);
  txt(s,'2024 年全年',68,328,330,48,32,C.ink,true);
  txt(s,'按日期和社区对齐\n两种运营系统的记录',68,399,355,94,27,C.muted);
  const qs=[['01','天气与日记录量','单车、出租车与 NOAA 天气'],['02','节假日与出行时段','两类运营记录与 OPM 日历'],['03','社区分布与降水日变化','运营记录、社区边界与天气']];
  qs.forEach(([n,title,sub],i)=>{const y=177+i*145;txt(s,n,485,y-3,74,52,37,C.gold,false,true);txt(s,title,579,y,620,49,31,C.ink,true);txt(s,sub,580,y+61,620,44,25,C.muted);});
  notes(s,'四类来源按底层记录形成过程识别：单车运营、出租车监管报送、NOAA 气象观测、OPM 官方日历。Divvy 由 Lyft 运营发布，数据所有权归芝加哥市；两个运营系统不是同一底层数据的镜像。每个核心问题至少依赖两个来源。',Object.values(URL));

  // 3 Editable evidence diagram, with only the actual join stage framed.
  s=page(p,'日期与社区的融合方法',3,{dark:true,source:'先分别清洗和聚合，再作唯一键连接，避免订单逐行相乘。'});
  const labels=[['Divvy','单车运营 CSV'],['Taxi','出租车 JSON'],['NOAA','两站日天气'],['OPM','联邦节假日'],['社区边界','GeoJSON 多边形']];
  const src=labels.map(([a,b],i)=>{const y=160+i*86;const t=txt(s,a,64,y,265,38,31,C.paper,true,a==='Divvy'||a==='Taxi'||a==='NOAA'||a==='OPM');txt(s,b,66,y+42,265,30,20,C.pale);return t;});
  const join=rect(s,444,291,342,153,'#1B3B43','#547B7B',1);
  txt(s,'清洗与聚合',473,315,282,49,33,C.paper,true,false,'center');
  txt(s,'日期  +  社区编号',467,376,295,38,25,C.pale,false,false,'center');
  const a=txt(s,'366',928,207,280,63,52,C.paper,false,true);
  txt(s,'日级融合表',930,276,280,41,28,C.pale);
  const b=txt(s,'28,182',928,449,280,63,52,C.paper,false,true);
  txt(s,'社区日期融合表',930,518,280,41,28,C.pale);
  for(const x of src)s.shapes.connect(x,join,{fromSide:'right',toSide:'left',kind:'elbow',line:{fill:'#628987',width:1.6},tail:{type:'arrow',width:'sm',length:'sm'}});
  for(const [target,col] of [[a,C.teal],[b,C.gold]])s.shapes.connect(join,target,{fromSide:'right',toSide:'left',kind:'elbow',line:{fill:col,width:2.4},tail:{type:'arrow',width:'med',length:'med'}});
  notes(s,'单车起点通过空间落区获得社区编号，出租车使用官方上车社区编号。按日期或社区日期聚合后连接，天气和日历按日期匹配。日级366行，社区日级28182行。',Object.values(URL));

  // 4 Exact measured size and editable quality table.
  s=page(p,'数据规模与清洗质量',4,{source:'2024 年。有效规模扣除滑板车与重复记录，ZIP、分页缓存和衍生表不重复计量。'});
  txt(s,audit.total_decimal_GB.toFixed(3),64,184,345,128,108,C.teal,false,true);
  txt(s,'GB',70,321,180,48,33,C.ink,true,true);
  txt(s,'有效原始记录字节',68,385,330,42,27,C.ink,true);
  txt(s,'每个主要源均超过 200 MB\n最大单源占比 '+(100*audit.max_source_fraction).toFixed(1)+'%',68,449,339,91,24,C.muted);
  nativeTable(s,[['来源','原始条数','清洗后','保留率','社区匹配'],
    ...[['divvy','Divvy'],['taxi','出租车']].map(([m,l])=>[l,short(d.counts[m].raw),short(d.counts[m].cleaned),d.counts[m].retained_pct.toFixed(2)+'%',(d.spatial_match_rates[m]*100).toFixed(2)+'%'])],
    {left:440,top:198,width:776,height:270},[120,205,205,120,126]);
  txt(s,'144,337',442,525,300,64,45,C.ink,false,true);txt(s,'排除的滑板车记录',443,591,330,35,24,C.muted);
  txt(s,'211',918,525,230,64,45,C.ink,false,true);txt(s,'重复的单车 ID',919,591,280,35,24,C.muted);
  notes(s,'数据来自已核验的scale_audit.json、cleaning_quality.json、integration_checks.json。Divvy原始来源含电动滑板车，清洗仅保留普通和电助力单车。原始单车来源5860568条，清洗后5583690；出租车6480350条，清洗后6107775。日级和小时总量精确对账。',[URL.bike,URL.taxi]);

  // 5 A large chart with a precise seasonal amplitude comparison.
  const bikeValues=data.monthly.map(r=>r.divvy_trips),taxiValues=data.monthly.map(r=>r.taxi_trips);
  const bikeRatio=Math.max(...bikeValues)/Math.min(...bikeValues),taxiRatio=Math.max(...taxiValues)/Math.min(...taxiValues);
  s=page(p,'单车的季节波动更大',5,{source:'2024 年月内平均每日记录量，千次/日。来源：Divvy、芝加哥市出租车记录。'});
  txt(s,bikeRatio.toFixed(1),64,205,300,134,113,C.teal,false,true);txt(s,'倍',275,277,63,54,33,C.ink);
  txt(s,'单车月内日均量\n最大值 / 最小值',69,356,316,92,28,C.ink);
  txt(s,'出租车对应比值',69,495,316,39,25,C.muted);
  txt(s,taxiRatio.toFixed(1),69,545,120,65,43,C.gold,true,true);txt(s,'倍',158,554,72,52,31,C.gold,true);
  legend(s,[['共享单车',C.teal],['出租车',C.gold]],470,155,{gap:270,size:24});
  nativeChart(s,'line',data.monthly.map(r=>String(r.month)),[
    {name:'共享单车',values:bikeValues.map(v=>v/1000),line:{fill:C.teal,width:4},marker:{symbol:'circle',size:5,fill:C.teal}},
    {name:'出租车',values:taxiValues.map(v=>v/1000),line:{fill:C.gold,width:4},marker:{symbol:'circle',size:5,fill:C.gold}}],
    {left:393,top:215,width:825,height:405},{max:25,major:5,font:23});
  txt(s,'月份',755,628,140,30,21,C.muted,false,false,'center');
  notes(s,'月内日均量按该月实际日数求均值。幅度比值来自12个月日均量的最大值与最小值，不把月份长度差异当作季节差异。单车图中已排除滑板车。',[URL.bike,URL.taxi]);

  // 6 Editable confidence-interval chart, including the zero-crossing caveat.
  s=page(p,'降水与单车记录量下降相关',6,{source:'2024，366 天，控制日历和天气变量。来源：Divvy、芝加哥市、NOAA、OPM。'});
  const br=d.models.divvy.precip_10mm,tr=d.models.taxi.precip_10mm;
  txt(s,pct(br.percent),64,203,390,139,96,C.teal,false,true);
  txt(s,'每增加 10 mm 日降水',68,351,360,41,27,C.ink,true);
  txt(s,`95% 区间\n${pct(br.low_percent)} 至 ${pct(br.high_percent)}`,68,411,360,86,25,C.muted);
  txt(s,'出租车 '+pct(tr.percent),68,550,380,49,32,C.gold,true);
  txt(s,'区间跨零，方向不确定',68,608,380,38,24,C.muted);
  forest(s,d.models);
  notes(s,'估计来自log(1+日记录量)回归，控制月份、星期、温度一次和二次项、平均风速与联邦节假日，区间使用7日滞后的HAC协方差。每10mm降水的单车估计-18.8304%，区间[-27.4764,-9.1536]；出租车+1.8328%，区间[-0.2219,3.9298]。只作观察性关联解释，不证明个体转乘。原生图形按照真实数值映射置信区间坐标，可编辑。',[URL.bike,URL.taxi,URL.weather,URL.holiday]);

  // 7 Paired native hourly charts and a carefully qualified holiday estimate.
  s=page(p,'单车的工作日双峰在节假日减弱',7,{source:'2024。横轴当地小时，纵轴日均每小时记录量（次）。来源：Divvy、芝加哥市、OPM。'});
  const calendars=[['Weekday','工作日',C.navy],['Weekend','周末',C.slate],['Federal holiday','联邦节假日',C.gold]];
  txt(s,'共享单车',64,148,540,42,30,C.teal,true);txt(s,'出租车',674,148,540,42,30,C.gold,true);
  for(const [i,m] of ['divvy','taxi'].entries())nativeChart(s,'line',Array.from({length:24},(_,i)=>String(i)),
    calendars.map(([id,label,color])=>({name:label,values:data.hour_profiles.filter(r=>r.day_type===id).map(r=>r[m+'_trips']),line:{fill:color,width:3}})),
    {left:55+i*610,top:210,width:560,height:305},{max:m==='divvy'?2000:1500,major:m==='divvy'?500:500,font:20});
  legend(s,calendars.map(([,l,c])=>[l,c]),342,529,{gap:210,size:22});
  txt(s,'节假日出租车记录量关联估计',64,592,720,39,29,C.ink,true);
  txt(s,pct(d.models.taxi.holiday.percent),924,570,290,74,56,C.gold,false,true,'right');
  txt(s,'单车估计区间跨零；联邦节假日仅 11 天',64,635,900,31,22,C.muted);
  notes(s,'按251个普通工作日、104个周末和11个联邦节假日的实际天数计算平均小时量。出租车时间由发布者取整到15分钟，只做小时级比较。节假日回归：单车-25.7326%，95%区间[-45.4840,+1.1748]，方向不稳定；出租车-38.9554%，区间[-50.6500,-24.4896]。无法据峰形判断每次出行目的，也不能把联邦假日等同所有居民实际休假。',[URL.bike,URL.taxi,URL.holiday]);

  // 8 Quantitative map polygons and their editable, shared log-scale legend.
  s=page(p,'空间分布与降水日变化并不一致',8,{source:'2024，77 个社区；地图为全年记录量的对数色阶，未按人口校正。来源：Divvy、芝加哥市、NOAA。'});
  const sc=d.community_precip_counts;
  txt(s,`${sc.bicycle_lower}/${sc.compared}`,64,199,375,109,82,C.teal,false,true);
  txt(s,'共同高覆盖社区中\n单车降水日指数均更低',68,324,345,88,27,C.ink,true);
  txt(s,`${sc.taxi_higher} 升 / ${sc.taxi_lower} 降`,68,458,352,60,37,C.gold,true);
  txt(s,'出租车变化方向不一致',68,529,350,40,25,C.muted);
  txt(s,'按社区、月份与星期标准化',68,588,350,34,21,C.muted);
  maps(s,geo,data.community_totals);
  notes(s,'地图为77个社区的全年匹配起点总量，原生可编辑多边形来自原始GeoJSON的保拓扑展示简化，容差0.00003度，不改变分析数据。地图共享log10(1+记录量)颜色范围0至6.2。左侧降水比较仅取两种方式年记录均至少1万次的22个社区，按社区、月份和星期均值标准化。单车22个较低；出租车10个较高、12个较低。温度、车辆供给等混杂仍然存在。',[URL.bike,URL.taxi,URL.geo,URL.weather]);

  // 9 Native chart and heat table show the original four-feature clustering.
  s=page(p,'出租车与天气的三类日级模式',9,{source:'2024。KMeans 仅用出租车和天气，固定 k=3、随机种子 42、20 次初始化。'});
  txt(s,'出租车日均记录量（千次）',64,155,535,42,26,C.muted);
  nativeChart(s,'bar',data.clusters.map(r=>r.cluster.replace('类别 ','')),[
    {name:'出租车',values:data.clusters.map(r=>r.taxi_trips/1000),fill:C.gold}],{left:55,top:218,width:530,height:325},{max:25,major:5,labels:true,font:23});
  txt(s,'特征均值相对全年均值（标准差）',650,155,566,42,25,C.muted);
  const hv=[['类别','出租车量','温度','降水','风速'],...data.clusters.map((r,i)=>[r.cluster.replace('类别 ','')+' '+r.days+'天',...visual.cluster_standardized_centers[i].map(v=>(v>0?'+':'')+v.toFixed(1))])];
  const heat=nativeTable(s,hv,{left:650,top:220,width:566,height:282},[130,114,100,110,112],{size:22});
  for(let i=0;i<3;i++)for(let j=0;j<4;j++){
    const z=visual.cluster_standardized_centers[i][j],weight=Math.min(1,Math.abs(z)/3);
    heat.getCell(i+1,j+1).fill=colorMix(C.paper,z>=0?C.gold:C.teal,weight);
    heat.getCell(i+1,j+1).text.style={typeface:N,fontSize:24,color:C.ink};
  }
  txt(s,'低于均值',652,524,220,33,22,C.teal);txt(s,'高于均值',920,524,220,33,22,C.gold);
  txt(s,'0.290',64,582,250,66,51,C.teal,false,true);
  txt(s,'轮廓系数，类别仅用于探索联合模式',320,598,860,44,27,C.ink);
  notes(s,'四个标准化特征为出租车日量、温度、降水、风速。类别A162天、B36天、C168天，按均温排序命名。轮廓系数0.2902097527。图表和热力表显示真实类别均值，聚类在同一数据上探索，不评价预测能力，不将日期类别视为客观人群。全精度结果见results。',[URL.taxi,URL.weather]);

  // 10 Closing statement keeps uncertainty, limitations, AI and reproducibility.
  s=page(p,'结论与适用范围',10,{dark:true});
  const closing=[['天气','单车下降关联更明确，出租车区间跨零'],['节假日','出租车记录较少，单车估计不稳定'],['社区','22 个社区中单车均较低，出租车有升有降']];
  closing.forEach(([title,body],i)=>{const y=178+i*137;txt(s,title,64,y,635,42,31,C.gold,true);txt(s,body,64,y+59,680,54,27,C.paper);});
  txt(s,'适用边界',826,181,365,41,27,C.gold,true);
  txt(s,'公开运营记录\n两个机场天气代理\n联邦节假日仅 11 天\n关联不等同因果',826,242,365,168,25,C.pale);
  txt(s,'AI 使用与复现',826,445,365,41,27,C.gold,true);
  txt(s,'AI 参与代码、分析与封面。\n通过原始条数、校验值和\n聚合对账核验结果。',826,505,365,110,24,C.pale);
  const rlink=txt(s,'代码与完整报告  '+repo.url,64,658,1152,38,20,C.pale);
  rlink.text.get(repo.url).link={uri:repo.url,isExternal:true};rlink.text.get(repo.url).color=C.pale;
  notes(s,'数据和结论保持此前核验版本。两类记录没有共同乘客ID，不能证明个体转乘。模型控制了部分日历和天气因素，仍是观察性关联。AI_USAGE.md记录AI参与方式，封面示意图来自内置image_gen，不能作为真实事件记录。',Object.values(URL));
}
