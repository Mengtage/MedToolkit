const el=id=>document.getElementById(id);
let principal=null,current=null,epoch=0;
async function request(path,data){const r=await fetch('/api/review/'+path,{method:data?'POST':'GET',headers:{Authorization:'Bearer '+el('review-token').value,...(data?{'Content-Type':'application/json'}:{})},...(data?{body:JSON.stringify(data)}:{})});const out=await r.json();if(!r.ok){if(r.status===401){clear();el('review-token').value='';el('review-notice').textContent='评审令牌失效，请重新连接';}throw Error(out.error||'请求失败');}return out;}
async function action(fn){const started=epoch;try{await fn();if(started===epoch)el('review-notice').textContent='已完成';}catch(e){if(started===epoch)el('review-notice').textContent=e.message;}}
function text(host,tag,value){const n=document.createElement(tag);n.textContent=value;host.append(n);return n;}
function button(host,label,fn,id){const b=text(host,'button',label);if(id)b.id=id;b.onclick=()=>action(fn);return b;}
function field(host,label,tag='textarea'){const l=text(host,'label',label),n=document.createElement(tag);l.append(n);return n;}
function clear(){epoch++;principal=null;current=null;el('review-identity').textContent='';el('review-list').replaceChildren();el('review-state').replaceChildren();el('review-work').replaceChildren();}
el('review-token').oninput=clear;
el('review-logout').onclick=()=>{clear();el('review-token').value='';el('review-notice').textContent='已退出';};
el('review-connect').onclick=()=>action(async()=>{clear();const started=epoch;const identity=await request('identity');const batches=await request('list');if(started!==epoch)return;principal=identity;el('review-identity').textContent=identity.actor+' · '+(identity.role==='human'?'人类评审':'模型结果提交身份');for(const batch of batches){const option=text(el('review-list'),'option',batch.question+' · '+batch.review.slice(0,8));option.value=batch.review;}const wanted=new URLSearchParams(location.search).get('review');if(batches.some(b=>b.review===wanted))el('review-list').value=wanted;if(batches.length)await refresh();});
el('review-list').onchange=()=>action(refresh);el('review-refresh').onclick=()=>action(refresh);
async function refresh(){
 const review=el('review-list').value;if(!review)return;const started=epoch;el('review-work').replaceChildren();
 const state=await request('state',{review});if(started!==epoch||el('review-list').value!==review)return;current=state;const host=el('review-state');host.replaceChildren();
 text(host,'h2',state.protocol.question);text(host,'p',state.protocol.stage==='full_text'?'全文筛选':'题名摘要筛选');
 if(state.parent_changed)text(host,'p','父批次在本全文快照创建后已有修订。本批次仍绑定原版本；请核对变更是否需要重新准备。');
 if(state.protocol.stage==='full_text'){text(host,'p',`父批次 ${state.lineage.parent_review_id}；拟获取报告 ${state.lineage.reports_sought}；已取得 ${state.lineage.reports_retrieved}；未取得 ${state.lineage.reports_sought-state.lineage.reports_retrieved}`);for(const item of state.checkpoint_records||[])fulltextMaterial(host,item,review);}
 text(host,'p','纳入：'+state.protocol.inclusion);text(host,'p','排除：'+state.protocol.exclusion);
 if(state.protocol.reason_codes){const codes=document.createElement('details');text(codes,'summary','本轮排除原因词表 · '+state.protocol.reason_codebook_version);for(const [code,label] of Object.entries(state.protocol.reason_codes))text(codes,'p',code+'：'+label);host.append(codes);}
 text(host,'p',`固定文献集 ${state.record_count} 条；来源 ${state.source_artifact}`);text(host,'p','方案指纹：'+state.protocol_sha256+'；文献集指纹：'+state.source_sha256);
 const material=document.createElement('details');text(material,'summary','核对本轮固定文献题名');for(const row of state.material_titles)text(material,'p',row.record_id+' · '+(row.title||'无标题'));host.append(material);
 text(host,'p',!state.approved?'等待人类作者批准':state.revealed?'已揭盲':state.own_submitted?'你的判断已锁定，等待揭盲':'可独立筛选');
 if(!state.approved&&principal.actor===state.protocol.human_reviewer){const l=text(host,'label','我确认上述纳排标准和固定材料用于本轮'+(state.protocol.stage==='full_text'?'全文':'题名摘要')+'筛选');const c=document.createElement('input');c.type='checkbox';c.id='checkpoint-confirm';l.prepend(c);button(host,'批准并冻结本轮筛选',async()=>{if(!c.checked)throw Error('请先明确确认筛选方案');await request('approve',{review,confirmed:true});await refresh();},'checkpoint-approve');}
 if(state.approved&&!state.own_submitted&&[state.protocol.human_reviewer,state.protocol.llm_reviewer].includes(principal.actor))button(host,'开始独立筛选',()=>loadBallot(review),'load-ballot');
 if(principal.actor===state.protocol.adjudicator){const b=button(host,state.revealed?'查看双方判断与裁决':'双方提交完成后揭盲',()=>reveal(review),'reveal');b.disabled=!state.ready_to_reveal;
 if(state.revealed&&state.protocol.stage==='full_text')button(host,'确认报告与研究关联',()=>loadStudies(review),'load-studies');
 if(state.revealed)button(host,'预览 PRISMA 计数',()=>loadPrisma(review),'load-prisma');
 if(state.revealed&&state.protocol.stage==='title_abstract')button(host,'登记全文并准备下一阶段',()=>loadFulltext(review),'load-fulltext');
 if(state.revealed)button(host,'下载完整审计 JSON',async()=>{const out=await request('export',{review});const url=URL.createObjectURL(new Blob([JSON.stringify(out,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='screening-audit-'+review+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);},'export-review');
 if(state.revealed)for(const [index,label] of [[0,'下载逐条决定 CSV'],[1,'下载判断历史 CSV']])button(host,label,async()=>{const out=await request('export_csv',{review});const file=out.files[index],url=URL.createObjectURL(new Blob([file.content],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=file.filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);},'export-csv-'+index);}
}
async function loadBallot(review){
 const started=epoch,ballot=await request('ballot',{review});if(started!==epoch||el('review-list').value!==review)return;
 const host=el('review-work');host.replaceChildren();const rows=[];
 for(const item of ballot.records){const card=document.createElement('article');card.dataset.record=item.record_id;host.append(card);text(card,'h3',item.record.title||'无标题');text(card,'p',item.record.abstract||'无摘要');
 const decision=field(card,'独立判断','select');decision.dataset.field='decision';for(const [value,label] of [['','请选择'],['include','纳入'],['exclude','排除'],['uncertain','不确定，需复核']]){const o=text(decision,'option',label);o.value=value;}
 const reasonCode=reasonSelector(card,ballot.protocol,decision);
 const isFull=ballot.protocol.stage==='full_text';if(isFull)fulltextMaterial(card,item,review);
 const reason=field(card,'判断理由'),locator=field(card,isFull?'依据位置（p:页号，例如p:1）':'依据位置（题名/摘要具体句段）');locator.dataset.field='locator';const quote=isFull?field(card,'逐字摘录（须出现在所填页快照中）'):null;if(quote)quote.dataset.field='quote';rows.push({id:item.record_id,decision,reasonCode,reason,locator,quote});}
 let provenance;if(principal.role==='model'){text(host,'p','本页仅导入已有模型结果，不调用模型。请记录实际型号、参数、提示及原始响应；测试结果须明确标为合成。');provenance=field(host,'模型运行来源 JSON');provenance.id='model-provenance';}
 button(host,'提交全部判断并锁定',async()=>{const decisions=rows.map(r=>({record_id:r.id,decision:r.decision.value,...(r.reasonCode?{reason_code:r.reasonCode.value}:{}),reason:r.reason.value,locator:r.locator.value,...(r.quote?{quote:r.quote.value}:{})}));if(decisions.some(r=>!r.decision||!r.reason.trim()||!r.locator.trim()))throw Error('每条文献需选择判断并填写理由和依据位置');await request('submit',{review,decisions,provenance:provenance?JSON.parse(provenance.value):{type:'human_manual'}});await refresh();},'submit-ballot');
}
async function reveal(review){
 const started=epoch,pair=await request('reveal',{review}),audit=await request('export',{review});if(started!==epoch||el('review-list').value!==review)return;await refresh();if(started!==epoch||el('review-list').value!==review)return;const host=el('review-work');host.replaceChildren();const identities=Object.keys(pair);
 for(const row of pair[identities[0]]){const card=document.createElement('article');card.dataset.record=row.record_id;host.append(card);const item=audit.events[0].data.records.find(r=>r.record_id===row.record_id);text(card,'h3',row.record_id+' · '+(item?.record.title||'无标题'));text(card,'p',item?.record.abstract||'无摘要');const previous=audit.final_decisions.find(r=>r.record_id===row.record_id);if(previous)text(card,'p','已保存的最终结论：'+({include:'纳入',exclude:'排除'})[previous.decision]+'；'+previous.reason);
 for(const who of identities){const d=pair[who].find(r=>r.record_id===row.record_id);text(card,'p',who+'：'+({include:'纳入',exclude:'排除',uncertain:'不确定'})[d.decision]+'；'+d.reason+'；依据：'+d.locator+(d.quote?'；摘录：'+d.quote:''));}
 const result=field(card,'人工最终结论','select');result.dataset.field='decision';for(const [value,label] of [['','请选择'],['include','纳入'],['exclude','排除']]){const o=text(result,'option',label);o.value=value;}
 const reasonCode=reasonSelector(card,audit.events[0].data.protocol,result);
 const isFull=audit.events[0].data.protocol.stage==='full_text';if(isFull)fulltextMaterial(card,item,review);const locator=isFull?field(card,'裁决依据位置（p:页号）'):null,quote=isFull?field(card,'裁决逐字摘录'):null;if(locator)locator.dataset.field='locator';if(quote)quote.dataset.field='quote';
 const reason=field(card,'最终理由（修订时说明原因）');button(card,'保存最终裁决',async()=>{await request('adjudicate',{review,record_id:row.record_id,decision:result.value,reason:reason.value,...(isFull?{locator:locator.value,quote:quote.value}:{}),...(reasonCode?{reason_code:reasonCode.value}:{})});text(card,'p','已保存，原始意见及修订历史保留。');});}
}

function reasonSelector(host,protocol,decision){
 if(!protocol.reason_codes)return null;
 const select=field(host,'排除原因代码（仅排除时必选；具体理由仍须填写）','select');select.dataset.field='reason_code';const blank=text(select,'option','请选择');blank.value='';
 for(const [code,label] of Object.entries(protocol.reason_codes)){const option=text(select,'option',label);option.value=code;}
 const update=()=>{select.disabled=decision.value!=='exclude';if(select.disabled)select.value='';};decision.addEventListener('change',update);update();return select;
}
