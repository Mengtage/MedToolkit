/* Human study mapping and explicit selected-lineage flow exports. */
function saveStudyFile(file){const url=URL.createObjectURL(new Blob([file.content],{type:file.filename.endsWith('.svg')?'image/svg+xml':file.filename.endsWith('.csv')?'text/csv;charset=utf-8':'application/json'}));const a=document.createElement('a');a.href=url;a.download=file.filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
async function loadStudies(review){
 const started=epoch,state=await request('study_state',{review});if(started!==epoch||el('review-list').value!==review)return;
 const host=el('review-work');host.replaceChildren();text(host,'h2','人工确认报告—研究映射');
 text(host,'p','同一研究的多篇报告填写相同研究ID。一篇报告含多个研究时用逗号分隔。ID仅用于当前选定批次；不根据题名自动合并，也不把报告数当研究数。');
 text(host,'p',state.mapping_valid?'当前映射已确认；修改会追加新版本。':state.history.length?'全文裁决已有修订，旧映射已失效，请重新核对。':'尚未确认映射。');
 if(state.pending_final){text(host,'p','仍有 '+state.pending_final+' 篇报告未最终裁决，请先完成。');return;}
 const rows=[];
 button(host,'智能识别试验注册号并预填全部研究映射与逐字证据',async()=>{const out=await request('study_auto_suggest',{review});for(const s of out.suggestions){const r=rows.find(x=>x.item.record_id===s.record_id);if(!r)continue;r.ids.value=s.study_ids.join(', ');r.reason.value=s.reason;r.locator.value=s.locator;r.quote.value=s.quote;}},'auto-suggest-studies');
 for(const item of state.records){const card=document.createElement('article');host.append(card);card.dataset.studyRecord=item.record_id;text(card,'h3',item.title);text(card,'p','报告ID：'+item.report_id);fulltextMaterial(card,item,review);
 const ids=field(card,'研究ID（多项用逗号分隔）','input');ids.dataset.field='study-ids';const reason=field(card,'关联依据或修订理由');reason.dataset.field='mapping-reason';const locator=field(card,'依据位置（p:页号）');locator.dataset.field='mapping-locator';const quote=field(card,'用于判断研究归属的逐字摘录');quote.dataset.field='mapping-quote';
 const old=state.mappings.find(r=>r.record_id===item.record_id);if(old){ids.value=old.study_ids.join(', ');reason.value=old.reason;locator.value=old.locator;quote.value=old.quote;}rows.push({item,ids,reason,locator,quote});}
 const details=document.createElement('details');text(details,'summary','映射历史（'+state.history.length+' 版）');for(const event of state.history)text(details,'p',event.timestamp+' · '+event.actor+' · '+event.event_hash);host.append(details);
 const label=text(host,'label','我已逐篇核对研究归属及证据，确认本版映射');const confirm=document.createElement('input');confirm.type='checkbox';confirm.id='mapping-confirm';label.prepend(confirm);
 button(host,'确认并保存映射版本',async()=>{if(!confirm.checked)throw Error('请明确确认研究映射');const mappings=rows.map(r=>({record_id:r.item.record_id,study_ids:r.ids.value.split(/[,，]/).map(s=>s.trim()).filter(Boolean),reason:r.reason.value,locator:r.locator.value,quote:r.quote.value}));await request('study_save',{review,mappings,screening_event_hash:state.screening_event_hash,mapping_event_hash:state.mapping_event_hash,confirmed:true});await loadStudies(review);},'save-studies');
 button(host,'查看本版 PRISMA 计数',()=>loadPrisma(review));
}
async function loadPrisma(review){
 const started=epoch,out=await request('prisma_preview',{review});if(started!==epoch||el('review-list').value!==review)return;
 const host=el('review-work');host.replaceChildren();const report=out.report;text(host,'h2',report.source_breakdown?.length?'PRISMA · 选定来源集合':'PRISMA · 单一选定来源链');text(host,'p','本视图仅统计此批次及其明确来源版本。来源集合内的检索已合并后重新去重、筛选；不直接相加既有筛选分支，也不证明整个综述检索完整。');
 for(const source of report.source_breakdown||[]){const detail=document.createElement('details');text(detail,'summary',source.database+' · '+source.kind+' · 导入 '+source.retrieved+' 条');text(detail,'p','检索式：'+source.query+'；时间：'+source.searched_at+'；命中：'+(source.total_hits??'未知')+'；完整：'+source.complete);text(detail,'p',source.coverage_note+'；覆盖依据：'+source.coverage_assurance);host.append(detail);}
 for(const issue of report.issues)text(host,'p','待核对：'+issue);
 const labels={records_identified:'已导入检索记录',duplicates_removed:'移除重复记录',search_total_hits:report.source_breakdown?.length?'各次检索命中之和（未去重）':'检索命中',records_not_downloaded:'未下载记录',records_screened:'题名摘要筛选记录',records_excluded:'题名摘要排除记录',reports_sought:'拟取得报告',reports_not_retrieved:'未取得报告',reports_assessed:'全文评估报告',reports_excluded:'全文排除报告',reports_pending:'待裁决报告',reports_included:'纳入报告',studies_included:'人工确认的研究'};
 const table=document.createElement('table');table.id='prisma-counts';host.append(table);for(const [key,value] of Object.entries(report.counts)){const row=document.createElement('tr');text(row,'th',labels[key]||key);const cell=text(row,'td',value===null?'未知 / 待确认':String(value));cell.dataset.metric=key;table.append(row);}
 for(const row of report.exclusion_reasons)text(host,'p','全文排除：'+row.label+'（'+row.code+'） '+row.count);
 text(host,'p','版本指纹：'+out.sha256);const source=text(host,'a','PRISMA 2020 官方流程图说明');source.href=report.reference;source.target='_blank';source.rel='noopener';
 for(const [index,label] of [[0,'下载 PRISMA 审计 JSON'],[1,'下载 PRISMA 计数 CSV'],[2,'下载 PRISMA 流程图 SVG']])button(host,label,async()=>{const result=await request('prisma_export',{review,expected_sha256:out.sha256});if(started!==epoch||el('review-list').value!==review)return;saveStudyFile(result.files[index]);},'export-prisma-'+index);
}
