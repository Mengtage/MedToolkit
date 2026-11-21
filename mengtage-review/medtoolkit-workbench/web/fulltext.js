/* Full-text registration and frozen materials; no external fetch/model calls. */
function fulltextMaterial(host,item,review){
 const doc=item.record.fulltext;if(!doc)return;
 const details=document.createElement('details');text(details,'summary','全文快照 · '+doc.filename+' · '+doc.pages.length+' 页/段');host.append(details);
 text(details,'p',doc.extraction.page_numbering==='physical_pdf_pages_1_based'?'定位使用PDF物理页号（从1开始），可能不同于印刷页码。':'TXT定位使用换页符分段编号，不代表原PDF页码。');
 text(details,'p','文件 SHA256：'+doc.file_sha256+'；文本 SHA256：'+doc.text_sha256);
 for(const page of doc.pages){text(details,'h4','p:'+page.page);text(details,'pre',page.text);}
 button(details,'下载冻结原件',async()=>{const started=epoch,out=await request('fulltext_file',{review,record_id:item.record_id});if(started!==epoch)return;const bytes=Uint8Array.from(atob(out.content_base64),c=>c.charCodeAt(0)),url=URL.createObjectURL(new Blob([bytes]));const a=document.createElement('a');a.href=url;a.download=out.filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
}
async function loadFulltext(review){
 const started=epoch,status=await request('fulltext_status',{review});if(started!==epoch||el('review-list').value!==review)return;
 const protocol=current.protocol,host=el('review-work');host.replaceChildren();text(host,'h2','登记全文取得情况');text(host,'p','仅处理父批次最终纳入记录。未取得全文单独留痕；登记修订追加历史。原裁决改变后须重新登记。');
 button(host,'一键为全部待登记记录生成结构化全文快照',async()=>{await request('fulltext_batch_register',{review});await loadFulltext(review);},'batch-register-fulltext');
 button(host,'下载全文取得登记 JSON',async()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(status,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='fulltext-retrieval-'+review+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);},'export-retrieval');
 for(const row of status.records){const card=document.createElement('article');card.dataset.retrieval=row.record_id;host.append(card);text(card,'h3',row.record_id+' · '+row.title);text(card,'p','当前状态：'+({pending:'待登记',retrieved:'已取得',not_retrieved:'未取得'})[row.status]);
 if(row.event){text(card,'p',row.event.reason);if(row.event.document)text(card,'p',row.event.document.filename+'；'+row.event.document.pages.length+'页/段；SHA256 '+row.event.document.file_sha256);}
 const select=field(card,'取得状态','select');select.dataset.field='retrieval-status';for(const [value,label] of [['retrieved','已取得全文'],['not_retrieved','未取得全文']]){const o=text(select,'option',label);o.value=value;}
 const file=field(card,'全文原件（PDF或UTF-8 TXT，最大5MB）','input');file.type='file';file.accept='.pdf,.txt';select.onchange=()=>{file.disabled=select.value==='not_retrieved';if(file.disabled)file.value='';};
 const reason=field(card,'取得说明或未取得原因');reason.dataset.field='retrieval-reason';
 button(card,'保存取得记录',async()=>{const body={review,record_id:row.record_id,status:select.value,reason:reason.value};if(select.value==='retrieved'){const f=file.files[0];if(!f||f.size>5000000)throw Error('请选择不超过5MB的PDF或TXT');body.filename=f.name;body.content_base64=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=()=>reject(Error('文件读取失败'));reader.readAsDataURL(f);});}if(started!==epoch||el('review-list').value!==review)return;await request('fulltext_register',body);await loadFulltext(review);});}
 text(host,'h3','准备全文筛选批次');text(host,'p','逐条登记后，冻结本次取得记录与全文；新的全文标准仍需指定人类作者批准。可保留原评审分工，也可填写已存在的评审ID。');const fields={};
 for(const [key,label] of [['question','研究问题'],['inclusion','全文纳入标准'],['exclusion','全文排除标准'],['human_reviewer','人类评审ID'],['llm_reviewer','模型结果提交身份ID'],['adjudicator','人类裁决者ID']]){fields[key]=field(host,label);fields[key].value=protocol[key];}
 button(host,'冻结材料并创建全文待批准批次',async()=>{const next={...protocol,stage:'full_text'};for(const [key,node] of Object.entries(fields))next[key]=node.value;const out=await request('fulltext_prepare',{review,protocol:next});if(started!==epoch)return;const a=text(host,'a','打开全文批次，完成新的人工checkpoint');a.href='/screening?review='+out.review;a.id='fulltext-child-link';text(host,'p','已创建 '+out.review+'；未取得全文 '+out.reports_not_retrieved+' 篇。');},'prepare-fulltext');
}
