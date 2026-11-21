const $=id=>document.getElementById(id);
async function api(path,data){const response=await fetch(path,{method:data?'POST':'GET',headers:{Authorization:'Bearer '+$('token').value,...(data?{'Content-Type':'application/json'}:{})},...(data?{body:JSON.stringify(data)}:{})});const result=await response.json();if(!response.ok)throw Error(result.error||'请求失败');return result;}
async function refresh(){const pid=$('projects').value;if(!pid)return;const jobs=await api('/api/jobs?project='+pid);$('jobs').replaceChildren();for(const j of jobs){const card=document.createElement('article'),title=document.createElement('p');title.textContent=j.kind+' · '+j.state+(j.error&&j.state==='failed'?' · '+j.error:'');card.append(title);if(j.state==='queued'){const b=document.createElement('button');b.textContent='运行';b.onclick=()=>action(async()=>{await api('/api/run',{id:j.id});for(let k=0;k<40;k++){await refresh();const cur=await api('/api/jobs?project='+pid);const item=cur.find(x=>x.id===j.id);if(!item||['completed','failed','needs_review'].includes(item.state)){await refresh();break;}await new Promise(r=>setTimeout(r,50));}});card.append(b);}if(['failed','needs_review'].includes(j.state)){const b=document.createElement('button');b.textContent='复核后重试';b.onclick=()=>action(async()=>{if(!confirm('确认旧任务已停止并需要重试？'))return;await api('/api/retry',{id:j.id,confirmed:true});await refresh();});card.append(b);}if(j.result){const result=JSON.parse(j.result);if(result.artifact){const b=document.createElement('button');b.textContent='查看产物';b.onclick=()=>action(async()=>{showArtifact(await api('/api/artifact?project='+pid+'&name='+encodeURIComponent(result.artifact)),{project:pid,name:result.artifact});});card.append(b);if(j.kind==='search'){const de=document.createElement('button');de.textContent='去重并复核';de.onclick=()=>action(async()=>{await api('/api/dedup',{project:pid,source_artifact:result.artifact});await refresh();});card.append(de);}if(['search','deduplicate','dedup_review'].includes(j.kind)){const ex=document.createElement('button');ex.textContent='导出 RIS';ex.onclick=()=>action(async()=>{const out=await api('/api/export-ris?project='+pid+'&name='+encodeURIComponent(result.artifact));const url=URL.createObjectURL(new Blob([out.content],{type:'application/x-research-info-systems;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=out.filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});card.append(ex);}}}$('jobs').append(card);}}
async function projects(){const p=await api('/api/projects');$('projects').replaceChildren();for(const x of p){const opt=document.createElement('option');opt.value=x.id;opt.textContent=x.question;$('projects').append(opt);}await refresh();}
async function action(fn){try{await fn();$('notice').textContent='已保存';}catch(e){$('notice').textContent=e.message;}}
$('connect').onclick=()=>action(projects);$('refresh').onclick=()=>action(refresh);$('projects').onchange=()=>action(async()=>{$('baseline-table').replaceChildren();$('artifact').textContent='';await refresh();});
$('create').onclick=()=>action(async()=>{await api('/api/projects',{question:$('question').value});await projects();});
$('search').onclick=()=>action(async()=>{await api('/api/jobs',{project:$('projects').value,kind:'search',payload:{query:$('query').value,limit:50}});await refresh();});

$('statistics').onclick=()=>action(async()=>{await api('/api/jobs',{project:$('projects').value,kind:'statistics',payload:{classification:'synthetic',method:$('method').value,x:'x',y:'y',rows:JSON.parse($('rows').value)}});await refresh();});

$('categorical').onclick=()=>action(async()=>{const input=JSON.parse($('contingency').value);await api('/api/jobs',{project:$('projects').value,kind:'statistics',payload:{...input,classification:'synthetic',method:$('categorical-method').value}});await refresh();});

$('group-statistics').onclick=()=>action(async()=>{const input=JSON.parse($('group-input').value);await api('/api/jobs',{project:$('projects').value,kind:'statistics',payload:{...input,classification:'synthetic',method:'group_numeric'}});await refresh();});

$('tableone').onclick=()=>action(async()=>{const input=JSON.parse($('tableone-input').value);await api('/api/jobs',{project:$('projects').value,kind:'statistics',payload:{...input,classification:'synthetic',method:'tableone'}});await refresh();});
function showArtifact(result,context){
  $('artifact').textContent=JSON.stringify(result,null,2);
  const host=$('baseline-table');host.replaceChildren();
  if(result.method==='prediction_evaluation_extended'){renderExtendedEvaluation(host,result);return;}
  if(result.method==='deduplication'){renderDedup(host,result,context);return;}
  if(['linear_regression','logistic_regression','poisson_regression','gamma_regression'].includes(result.method)){
    const info=document.createElement('p');info.textContent='完整样本 '+result.complete_rows+'；缺失剔除 '+result.excluded_missing_rows+'。系数区间尺度：'+result.coefficient_ci_scale+'。拟合值来自训练样本。';host.append(info);
    const table=document.createElement('table'),head=document.createElement('tr');
    for(const label of ['参数','系数','标准误','P值','系数区间下限','系数区间上限','OR']){const cell=document.createElement('th');cell.textContent=label;head.append(cell);}table.append(head);
    for(const name of result.parameter_order){const row=document.createElement('tr');for(const value of [name,result.coefficients[name],result.std_errors[name],result.p_values[name],result.conf_int_lower[name],result.conf_int_upper[name],result.odds_ratios?.[name]??'不适用']){const cell=document.createElement('td');cell.textContent=value;row.append(cell);}table.append(row);}host.append(table);return;
  }
  if(result.method!=='tableone')return;
  const policy=document.createElement('p');policy.textContent=result.test_policy;host.append(policy);
  const pmap={};for(const pv of result.p_values||[])pmap[pv.variable]=pv;
  const table=document.createElement('table');
  const header=document.createElement('tr');
  for(const name of ['变量','组','水平','描述','有效数','缺失数','检验方法','P值']){const cell=document.createElement('th');cell.textContent=name;header.append(cell);}table.append(header);
  for(const row of result.table){
    const missing=result.missingness[row.group]?.[row.variable]||{};
    const pv=pmap[row.variable];
    const tr=document.createElement('tr');
    for(const value of [row.variable,row.group,row.level??'',row.display,missing.n_valid,missing.n_missing,pv?.test??'—',pv?.p_value??'—']){const cell=document.createElement('td');cell.textContent=value??'不可估计';tr.append(cell);}table.append(tr);
  }host.append(table);
}

$('regression').onclick=()=>action(async()=>{const input=JSON.parse($('regression-input').value);await api('/api/jobs',{project:$('projects').value,kind:'statistics',payload:{...input,classification:'synthetic',method:$('regression-method').value}});await refresh();});

$('evaluation').onclick=()=>action(async()=>{const input=JSON.parse($('evaluation-input').value);await api('/api/jobs',{project:$('projects').value,kind:'statistics',payload:{...input,classification:'synthetic',method:'prediction_evaluation'}});await refresh();});

$('imputation').onclick=()=>action(async()=>{const input=JSON.parse($('imputation-input').value);await api('/api/jobs',{project:$('projects').value,kind:'statistics',payload:{...input,classification:'synthetic',method:'mice_imputation'}});await refresh();});

function renderDedup(host,result,context){
  const title=document.createElement('h3');title.textContent='去重与人工复核';host.append(title);
  const prepare=document.createElement('button');prepare.textContent='以此文献集准备筛选';prepare.disabled=result.pending_review_count!==0;prepare.onclick=()=>prepareScreening(context);host.append(prepare);
  const summary=document.createElement('p');summary.textContent=`原始 ${result.input_count} 条 → 当前 ${result.unique_count} 条；待复核 ${result.pending_review_count} 对。每次处理生成新任务与产物，请运行后查看最新结果；历史产物保留。`;host.append(summary);
  const evidence=document.createElement('details'),caption=document.createElement('summary');caption.textContent='自动合并依据与来源分组';evidence.append(caption);
  const pre=document.createElement('pre');pre.textContent=JSON.stringify({merge_events:result.merge_events,groups:result.groups},null,2);evidence.append(pre);host.append(evidence);
  result.review_candidates.forEach((candidate,index)=>{
    const card=document.createElement('article');card.dataset.candidate=index;
    const heading=document.createElement('h4');heading.textContent=`候选 ${index+1}：${({keep:'已保留',merge:'已人工合并',same_group_after_review:'已随关联记录合并'})[candidate.resolution]||'待复核'}`;card.append(heading);
    for(const i of [candidate.left,candidate.right]){
      const record=result.raw_records[i-1],text=document.createElement('p');text.textContent=`来源 #${i}：${record.title||'无标题'} | PMID ${record.pmid||'未提供'} | DOI ${record.doi||'未提供'}`;card.append(text);
    }
    const detail=document.createElement('p');detail.textContent='匹配字段：'+candidate.matched_fields.map(k=>({title:'标题',pmid:'PMID',doi:'DOI'})[k]||k).join('、')+'；冲突：'+JSON.stringify(candidate.identifier_conflicts);card.append(detail);
    if(!candidate.resolution){
      const representative=result.groups.find(g=>g.source_indices.includes(candidate.left));
      const policy=document.createElement('p');policy.textContent='确认合并后沿用左侧组的展示记录（来源 #'+representative.selected_source_index+'），所有原记录仍保留。';card.append(policy);
      const label=document.createElement('label');label.textContent='处理理由（必填）';const reason=document.createElement('textarea');reason.maxLength=2000;label.append(reason);card.append(label);
      for(const [decision,text] of [['keep','保留两条'],['merge','确认合并']]){
        const button=document.createElement('button');button.textContent=text;button.onclick=()=>action(async()=>{
          if(!reason.value.trim())throw Error('请填写处理理由');
          if($('projects').value!==context.project)throw Error('项目已切换，请重新查看产物');
          await api('/api/dedup',{project:context.project,source_artifact:context.name,candidate_index:index,decision,reason:reason.value});await refresh();
        });card.append(button);
      }
    }
    host.append(card);
  });
  const history=document.createElement('details'),caption2=document.createElement('summary');caption2.textContent='人工处理历史';history.append(caption2);
  const events=document.createElement('pre');events.textContent=JSON.stringify(result.review_events,null,2);history.append(events);host.append(history);
}

$('reviewer-create').onclick=()=>action(async()=>{const issued=await api('/api/reviewers',{actor:$('reviewer-id').value,role:$('reviewer-role').value});$('issued-token').value=issued.token;});
$('reviewer-revoke').onclick=()=>action(async()=>{await api('/api/reviewers/revoke',{actor:$('reviewer-id').value});$('issued-token').value='';});
$('issued-clear').onclick=()=>{$('issued-token').value='';};
function prepareScreening(context){
 const host=$('screening-prepare');host.replaceChildren();const title=document.createElement('h3');title.textContent='从已选产物准备筛选方案';host.append(title);
 const fields={};for(const [key,label] of [['question','研究问题'],['inclusion','纳入标准'],['exclusion','排除标准'],['human_reviewer','人类作者评审ID'],['llm_reviewer','模型评审ID'],['adjudicator','人类裁决者ID']]){const l=document.createElement('label');l.textContent=label;const input=document.createElement('textarea');input.dataset.protocol=key;l.append(input);host.append(l);fields[key]=input;}
 const source=document.createElement('p');source.textContent='选定文献产物：'+context.name;host.append(source);
 const b=document.createElement('button');b.textContent='创建待批准筛选批次';b.id='prepare-review';b.onclick=()=>action(async()=>{
 if($('projects').value!==context.project)throw Error('项目已切换，请重新选择产物');
 const protocol={stage:'title_abstract'};for(const [k,input] of Object.entries(fields))protocol[k]=input.value;
 const result=await api('/api/screening-prepare',{project:context.project,source_artifact:context.name,protocol});
 const link=document.createElement('a');link.textContent='打开本轮人工 checkpoint';link.href='/screening?review='+result.review;link.target='_blank';link.rel='noopener';link.id='prepared-review-link';host.append(link);
 });host.append(b);host.scrollIntoView({block:'center'});
}
