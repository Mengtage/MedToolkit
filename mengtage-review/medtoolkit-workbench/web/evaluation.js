/* Read-only presentation of explicit statistical results; no model calls. */
const evfmt=v=>typeof v==='number'&&Number.isFinite(v)?String(Number(v.toPrecision(6))):'不可计算';
function evtext(host,tag,value){const n=document.createElement(tag);n.textContent=value;host.append(n);return n;}
function evtable(host,headers,rows,id){const table=document.createElement('table');if(id)table.id=id;const head=document.createElement('tr');for(const label of headers)evtext(head,'th',label);table.append(head);for(const values of rows){const tr=document.createElement('tr');for(const value of values)evtext(tr,'td',typeof value==='number'?evfmt(value):value??'不可计算');table.append(tr);}host.append(table);return table;}
$('extended-evaluation').onclick=()=>action(async()=>{const input=JSON.parse($('extended-evaluation-input').value);const cls=$('stat-classification')?$('stat-classification').value:'synthetic';await api('/api/jobs',{project:$('projects').value,kind:'statistics',payload:{...input,classification:cls,method:'prediction_evaluation_extended'}});await refresh();});
function renderExtendedEvaluation(host,r){
 evtext(host,'h3','扩展预测评估');evtext(host,'p',`n=${r.n}；事件=${r.events}；非事件=${r.non_events}；评估来源=${r.evaluation_scope}（用户声明）`);
 for(const warning of r.warnings)evtext(host,'p',warning);
 const hl=r.hosmer_lemeshow;evtext(host,'h4','HL：等宽分箱近似诊断');evtable(host,['统计量','p值','非空组数','自由度','状态'],[[hl.statistic,hl.p_value,hl.occupied_bins,hl.df,hl.status]],'hl-summary');
 evtable(host,['组','样本数','观察事件','期望事件','观察非事件','期望非事件'],hl.group_sizes.map((n,i)=>[r.calibration_curve[i].bin,n,hl.observed_events[i],hl.expected_events[i],n-hl.observed_events[i],n-hl.expected_events[i]]),'hl-groups');
 evtext(host,'h4','DCA：指定阈值下的净获益');const d=r.dca,old=r.comparison?.old_model_dca;
 drawDCA(host,d,old);evtable(host,['阈值','当前模型','全部治疗','不治疗',...(old?['旧模型']:[])],d.thresholds.map((t,i)=>[t,d.net_benefit[i],d.net_benefit_all[i],d.net_benefit_none[i],...(old?[old.net_benefit[i]]:[])]),'dca-values');
 if(r.comparison){const c=r.comparison;evtext(host,'h4','NRI：逐阈值二分类');evtable(host,['阈值','事件↑ / ↓','非事件↑ / ↓','事件NRI','非事件NRI','总NRI'],Object.values(c.nri).map(v=>[v.threshold,v.event_up+' / '+v.event_down,v.non_event_up+' / '+v.non_event_down,v.nri_event,v.nri_non_event,v.nri_total]),'nri-values');
 evtext(host,'h4','IDI：固定配对预测');evtable(host,['IDI','标准误','Z（近似）','状态'],[[c.idi.idi,c.idi.se,c.idi.z_score,c.idi.inference_status]],'idi-values');}
 for(const limitation of r.limitations)evtext(host,'p',limitation);
 const download=evtext(host,'button','下载评估结果 JSON');download.onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(r,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='medstat-extended-evaluation.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
}
function drawDCA(host,d,old){
 const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.id='dca-plot';svg.setAttribute('viewBox','0 0 700 350');svg.setAttribute('width','100%');svg.setAttribute('role','img');svg.setAttribute('aria-label','DCA净获益曲线，阈值1未定义点不连线');
 const series=[['当前模型',d.net_benefit,'#126b64'],['全部治疗',d.net_benefit_all,'#b43838'],['不治疗',d.net_benefit_none,'#646464'],...(old?[['旧模型',old.net_benefit,'#7056a6']]:[])];
 const values=series.flatMap(s=>s[1]).filter(v=>typeof v==='number'&&Number.isFinite(v));let low=Math.min(0,...values),high=Math.max(0,...values);if(low===high){low-=.05;high+=.05;}const pad=(high-low)*.08;low-=pad;high+=pad;
 const sx=x=>75+x*590,sy=y=>270-(y-low)/(high-low)*215;
 function node(tag,attrs,text){const n=document.createElementNS(ns,tag);for(const [k,v]of Object.entries(attrs))n.setAttribute(k,v);if(text!==undefined)n.textContent=text;svg.append(n);return n;}
 node('rect',{x:0,y:0,width:700,height:350,fill:'white'});
 node('path',{d:'M75 50 V270 H665',stroke:'#555',fill:'none'});
 for(let i=0;i<=4;i++){const y=low+(high-low)*i/4;node('text',{x:4,y:sy(y)+5,'font-size':12},y.toPrecision(3));const x=i/4;node('text',{x:sx(x)-10,y:292,'font-size':12},String(x));}
 node('text',{x:310,y:317,'font-size':14},'阈值概率');node('text',{x:8,y:35,'font-size':14},'净获益');
 for(const [index,[label,points,color]] of series.entries()){let path='',connected=false;for(let i=0;i<points.length;i++){const value=points[i];if(value===null||!Number.isFinite(value)){connected=false;continue;}path+=(connected?' L':' M')+sx(d.thresholds[i])+' '+sy(value);connected=true;const dot=node('circle',{cx:sx(d.thresholds[i]),cy:sy(value),r:3,fill:color});const title=document.createElementNS(ns,'title');title.textContent=label+'：阈值 '+d.thresholds[i]+'，净获益 '+value;dot.append(title);}node('path',{d:path,fill:'none',stroke:color,'stroke-width':2});node('text',{x:80+index*145,y:20,'font-size':13,fill:color},label);}
 host.append(svg);
}
