// Real Chromium clicks against an isolated Python server. No model or live PubMed calls.
const {chromium}=require('../../.browser-tools/node_modules/playwright-core');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),crypto=require('node:crypto');
const {spawn}=require('node:child_process');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../..'), out=path.join(root,'reports/browser');
fs.mkdirSync(out,{recursive:true});
const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'medtoolkit-browser-'));
const token=crypto.randomBytes(32).toString('hex');
const port=Number(process.env.BROWSER_TEST_PORT||18765),base=`http://127.0.0.1:${port}`;
const server=spawn(path.join(root,'.venv/bin/python'),[path.join(__dirname,'server.py'),tmp,String(port)],{cwd:root,env:{...process.env,WORKBENCH_ACCESS_TOKEN:token,GEMINI_API_KEY:'',GEMINI_MODEL:''},stdio:['ignore','pipe','pipe']});
let browser,serverErrors='',results=[],errors=[];server.stderr.on('data',d=>serverErrors+=d);
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function check(name,fn){await fn();results.push({name,status:'PASS'});console.log('PASS '+name);}
(async()=>{try{
  await new Promise((resolve,reject)=>{server.stdout.once('data',resolve);server.once('exit',c=>reject(Error('Fixture server exited '+c)));setTimeout(()=>reject(Error('Server startup timeout')),10000).unref();});
  browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/home/labhub/.cache/ms-playwright/chromium-1255/chrome-linux64/chrome',headless:true,env:{...process.env,XDG_CONFIG_HOME:path.join(tmp,'config'),XDG_CACHE_HOME:path.join(tmp,'cache')},args:['--no-sandbox']});
  const context=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});
  context.setDefaultTimeout(12000);const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base);
  const notice=()=>page.locator('#notice').innerText();
  async function clickRequest(selector,url){const response=page.waitForResponse(r=>r.url().includes(url)&&r.request().method()==='POST');await page.locator(selector).click();return await (await response).json();}
  async function refresh(){const r=page.waitForResponse(r=>r.url().includes('/api/jobs?'));await page.locator('#refresh').click();await r;await sleep(60);}
  async function runArtifact(button,endpoint='/api/jobs'){
    const {id}=await clickRequest(button,endpoint);assert.ok(id,await notice());
    await refresh();const card=page.locator('#jobs article').filter({has:page.getByRole('button',{name:'运行',exact:true})});assert.equal(await card.count(),1);
    await card.getByRole('button',{name:'运行',exact:true}).click();
    for(let i=0;i<100;i++){await refresh();if(await page.locator('#jobs article').filter({hasText:'completed'}).count()===completed+1)break;assert.equal(await page.locator('#jobs article').filter({hasText:'failed'}).count(),0);await sleep(100);}
    completed++;assert.equal(await page.locator('#jobs article').filter({hasText:'completed'}).count(),completed);
    const artifactResponse=page.waitForResponse(r=>r.url().includes('/api/artifact?'));
    await page.locator('#jobs article').last().getByRole('button',{name:'查看产物'}).click();
    const expected=await (await artifactResponse).json();
    await page.waitForFunction(value=>document.querySelector('#artifact').textContent===JSON.stringify(value,null,2),expected);
    return JSON.parse(await page.locator('#artifact').innerText());
  }
  let completed=0;
  await check('empty and incorrect token rejected',async()=>{for(const value of ['', 'incorrect']){await page.locator('#token').fill(value);await page.locator('#connect').click();await page.waitForFunction(()=>document.querySelector('#notice').textContent==='需要访问令牌');}});
  await check('connect; create project; literal user text',async()=>{await page.locator('#token').fill(token);await page.locator('#connect').click();await page.waitForFunction(()=>document.querySelector('#notice').textContent==='已保存');await page.locator('#question').fill('Synthetic <b>desktop</b>');await clickRequest('#create','/api/projects');await page.waitForFunction(()=>document.querySelector('#projects').options.length===1);assert.equal(await page.locator('#projects option').innerText(),'Synthetic <b>desktop</b>');});
  await check('invalid JSON and invalid payload show errors without new job',async()=>{await page.locator('#rows').fill('{');await page.locator('#statistics').click();await sleep(100);assert.notEqual(await notice(),'已保存');await page.locator('#rows').fill('[]');const r=await clickRequest('#statistics','/api/jobs');assert.ok(r.error);assert.equal(await page.locator('#jobs article').count(),0);});
  const specs=[['pearson','statistics.json','#rows','#statistics','#method'],['spearman','statistics.json','#rows','#statistics','#method'],...['categorical_auto','chi2','fisher','yates'].map(m=>[m,'categorical.json','#contingency','#categorical','#categorical-method']),['group_numeric','groups.json','#group-input','#group-statistics'],['tableone','tableone.json','#tableone-input','#tableone'],...['linear','logistic','poisson','gamma'].map(m=>[m+'_regression',m+'.json','#regression-input','#regression','#regression-method']),['prediction_evaluation','evaluation.json','#evaluation-input','#evaluation'],['mice_imputation','imputation.json','#imputation-input','#imputation']];
  for(const [method,file,input,button,select] of specs)await check(method+' submit/run/refresh/artifact',async()=>{
    let data=JSON.parse(fs.readFileSync(path.join(root,'examples',file)));delete data.classification;delete data.method;
    if(input==='#rows')data=data.rows;
    if(select)await page.locator(select).selectOption(method);
    await page.locator(input).fill(JSON.stringify(data));
    const result=await runArtifact(button);assert.equal(result.requested_method||result.method,method);
    if(method==='tableone'||method.endsWith('_regression')){assert.ok(await page.locator('#baseline-table tr').count()>1);assert.ok(!(await page.locator('#baseline-table').innerText()).includes('undefined'));assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await page.locator('#baseline-table').screenshot({path:path.join(out,method+'.png')});if(method.endsWith('_regression')){await page.locator('#baseline-table').evaluate(el=>{el.scrollLeft=el.scrollWidth});await page.locator('#baseline-table').screenshot({path:path.join(out,method+'-right.png')});await page.locator('#baseline-table').evaluate(el=>{el.scrollLeft=0});}}
    else assert.equal(await page.locator('#baseline-table table').count(),0);
  });
  let extendedNullResult;
  await check('extended prediction evaluation tables DCA and JSON download',async()=>{
    const result=await runArtifact('#extended-evaluation');assert.equal(result.method,'prediction_evaluation_extended');assert.ok(Math.abs(result.hosmer_lemeshow.statistic-496/63)<1e-10);
    await page.locator('#hl-summary').waitFor();assert.match(await page.locator('#hl-summary').innerText(),/approximate/);assert.equal(await page.locator('#nri-values tr').count(),3);assert.equal(await page.evaluate(()=>document.querySelector('#nri-values').scrollWidth<=document.querySelector('#baseline-table').clientWidth),true);assert.equal(await page.locator('#dca-plot circle').count(),17);
    assert.match(await page.locator('#dca-values tr').last().innerText(),/不可计算/);await page.locator('#baseline-table').screenshot({path:path.join(out,'medstat-extended-evaluation.png')});
    const event=page.waitForEvent('download');await page.getByRole('button',{name:'下载评估结果 JSON'}).click();const d=await event;await d.saveAs(path.join(out,'medstat-extended-evaluation.json'));const downloaded=JSON.parse(fs.readFileSync(path.join(out,'medstat-extended-evaluation.json'),'utf8'));assert.equal(downloaded.input_sha256,result.input_sha256);assert.equal(downloaded.llm_calls,0);
  });
  await check('extended evaluation undefined values remain visible without errors',async()=>{
    const input=JSON.parse(await page.locator('#extended-evaluation-input').inputValue());input.n_bins=2;input.rows=[{observed:0,probability:0,old_probability:0},{observed:1,probability:1,old_probability:1}];await page.locator('#extended-evaluation-input').fill(JSON.stringify(input));extendedNullResult=await runArtifact('#extended-evaluation');
    assert.equal(extendedNullResult.hosmer_lemeshow.p_value,null);assert.equal(extendedNullResult.comparison.idi.se,null);assert.equal(extendedNullResult.comparison.idi.z_score,null);
    await page.locator('#hl-summary').waitFor();assert.match(await page.locator('#hl-summary').innerText(),/不可计算/);assert.match(await page.locator('#idi-values').innerText(),/insufficient_group_size/);assert.ok(!(await page.locator('#baseline-table').innerText()).includes('NaN'));
    await page.locator('#baseline-table').screenshot({path:path.join(out,'medstat-undefined-values.png')});
  });
  await check('legacy MedStat template display functions accept null HL and IDI',async()=>{
    const legacy=fs.readFileSync(path.join(root,'modules/MedStat/templates/index.html'),'utf8'),start=legacy.indexOf('        function evaluationNumber('),end=legacy.indexOf('        switchPanel =',start);assert.ok(start>0&&end>start);
    const legacyPage=await context.newPage();await legacyPage.setContent('<div id="metricBrier"></div><div id="metricHL"></div><div id="calibrationChart"></div><div id="dcaChart"></div><table id="nriTable"><tbody></tbody></table><div id="metricIDI"></div><div id="metricZ"></div>');
    const result=await legacyPage.evaluate(({script,r})=>{const plots={};window.Plotly={newPlot:(id,series)=>{plots[id]=series;}};const display=new Function(script+';return {displayCalibration,displayDCA,displayNRI,displayIDI};')();display.displayCalibration(r);display.displayDCA(r.dca);display.displayNRI(r.comparison.nri);display.displayIDI(r.comparison.idi);const output={hl:document.getElementById('metricHL').textContent,z:document.getElementById('metricZ').textContent,endpoint:plots.dcaChart[0].y.at(-1)};display.displayNRI(undefined);display.displayIDI(undefined);return output;},{script:legacy.slice(start,end),r:extendedNullResult});
    assert.equal(result.hl,'N/A');assert.equal(result.z,'N/A');assert.equal(result.endpoint,null);await legacyPage.close();
  });
  await check('PubMed fixture search and RIS download',async()=>{await page.locator('#query').fill('synthetic browser fixture');const result=await runArtifact('#search');assert.equal(result.retrieved,1);assert.equal(result.complete,false);const download=page.waitForEvent('download');await page.getByRole('button',{name:'导出 RIS'}).click();const d=await download;assert.equal(d.suggestedFilename(),'references.ris');await d.saveAs(path.join(out,'references.ris'));assert.match(fs.readFileSync(path.join(out,'references.ris'),'utf8'),/TI  - Synthetic browser fixture/);});
  let dedupParent;
  await check('desktop dedup task and duplicate submission',async()=>{
    await page.locator('#query').fill('dedup-fixture');await runArtifact('#search');
    const button='#jobs article:last-child button:text-is("去重并复核")';
    const out=await runArtifact(button,'/api/dedup');assert.equal(out.unique_count,2);assert.equal(out.raw_records.length,3);assert.ok(out.pending_review_count>0);dedupParent=out;
    const n=await page.locator('#jobs article').count();
    await page.locator('#jobs article').filter({hasText:'search'}).last().getByRole('button',{name:'去重并复核'}).click();await refresh();assert.equal(await page.locator('#jobs article').count(),n);
  });
  await check('desktop human keep, required reason and immutable parent',async()=>{
    const first=page.locator('#baseline-table article').first();
    await first.getByRole('button',{name:'保留两条'}).click();assert.equal(await notice(),'请填写处理理由');
    await first.locator('textarea').fill('不同标识，保留待全文核对');
    const out=await runArtifact('#baseline-table article:first-of-type button:text-is("保留两条")','/api/dedup');assert.equal(out.unique_count,2);assert.equal(out.review_events[0].decision,'keep');
    await page.locator('#jobs article').filter({hasText:'deduplicate · completed'}).last().getByRole('button',{name:'查看产物'}).click();
    await page.waitForFunction(()=>JSON.parse(document.querySelector('#artifact').textContent).review_events?.length===0);
    assert.deepEqual(JSON.parse(await page.locator('#artifact').innerText()),dedupParent);
  });
  await check('desktop human merge branch and result persistence',async()=>{
    await page.locator('#baseline-table article').first().locator('textarea').fill('合成测试：人工核对为同一报告');
    const out=await runArtifact('#baseline-table article:first-of-type button:text-is("确认合并")','/api/dedup');assert.equal(out.unique_count,1);assert.equal(out.pending_review_count,0);assert.equal(out.raw_records.length,3);
    await page.locator('#baseline-table').screenshot({path:path.join(root,'reports/browser/dedup-review.png')});
  });
  let humanToken,modelToken,reviewURL,humanPage,modelPage;
  await check('screening reviewer setup and frozen checkpoint',async()=>{
    for(const [actor,role] of [['browser-human','human'],['browser-model','model']]){
      await page.locator('#reviewer-id').fill(actor);await page.locator('#reviewer-role').selectOption(role);
      await clickRequest('#reviewer-create','/api/reviewers');await page.waitForFunction(()=>document.querySelector('#issued-token').value.length>20);
      const issued=await page.locator('#issued-token').inputValue();if(role==='human')humanToken=issued;else modelToken=issued;await page.locator('#issued-clear').click();
    }
    await page.getByRole('button',{name:'以此文献集准备筛选'}).click();
    for(const [key,value] of Object.entries({question:'Synthetic blinded review',inclusion:'Include synthetic adults',exclusion:'Exclude wrong population',human_reviewer:'browser-human',llm_reviewer:'browser-model',adjudicator:'browser-human'}))await page.locator(`[data-protocol="${key}"]`).fill(value);
    await clickRequest('#prepare-review','/api/screening-prepare');await page.locator('#prepared-review-link').waitFor();reviewURL=await page.locator('#prepared-review-link').getAttribute('href');
    const hc=await browser.newContext({viewport:{width:1440,height:1000}}),mc=await browser.newContext({viewport:{width:1440,height:1000}});hc.setDefaultTimeout(12000);mc.setDefaultTimeout(12000);humanPage=await hc.newPage();modelPage=await mc.newPage();
    for(const [p,t] of [[humanPage,humanToken],[modelPage,modelToken]]){p.on('pageerror',e=>errors.push(e.message));await p.goto(base+reviewURL);await p.locator('#review-token').fill(t);await p.locator('#review-connect').click();await p.locator('#review-state h2').waitFor();}
    assert.equal(await modelPage.locator('#checkpoint-approve').count(),0);assert.equal(await modelPage.locator('#load-ballot').count(),0);
    await humanPage.locator('#checkpoint-approve').click();await humanPage.waitForFunction(()=>document.querySelector('#review-notice').textContent.includes('请先明确确认'));
    await humanPage.locator('#checkpoint-confirm').check();await humanPage.locator('#checkpoint-approve').click();await humanPage.locator('#load-ballot').waitFor();
  });
  await check('independent human submission hides rationale from model',async()=>{
    await humanPage.locator('#load-ballot').click();await humanPage.locator('#review-work article select[data-field=decision]').selectOption('include');
    await humanPage.locator('#review-work article textarea').nth(0).fill('HUMAN_PRIVATE_REASON');await humanPage.locator('#review-work article textarea').nth(1).fill('title');await humanPage.locator('#submit-ballot').click();
    await humanPage.waitForFunction(()=>document.querySelector('#review-state').textContent.includes('你的判断已锁定'));
    assert.equal(await humanPage.locator('#reveal').isDisabled(),true);
    await modelPage.locator('#review-refresh').click();await modelPage.locator('#load-ballot').waitFor();await modelPage.locator('#load-ballot').click();await modelPage.locator('#submit-ballot').waitFor();
    assert.ok(!(await modelPage.locator('body').innerText()).includes('HUMAN_PRIVATE_REASON'));
    assert.equal(await modelPage.locator('#reveal').count(),0);
  });
  await check('model fixture submission, reveal, adjudicate and audit download',async()=>{
    await modelPage.locator('#review-work article select[data-field=decision]').selectOption('uncertain');await modelPage.locator('#review-work article textarea').nth(0).fill('Synthetic model uncertainty');await modelPage.locator('#review-work article textarea').nth(1).fill('title');
    await modelPage.locator('#model-provenance').fill(JSON.stringify({model:'synthetic-fixture-no-call',parameters:{},prompt:'synthetic prompt',raw_response:'synthetic uncertain response',run_id:'browser-fixture'}));await modelPage.locator('#submit-ballot').click();await modelPage.waitForFunction(()=>document.querySelector('#review-state').textContent.includes('你的判断已锁定'));
    await humanPage.locator('#review-refresh').click();await humanPage.waitForFunction(()=>!document.querySelector('#reveal').disabled);await humanPage.locator('#reveal').click();await humanPage.locator('#review-work article select[data-field=decision]').waitFor();
    assert.match(await humanPage.locator('#review-work').innerText(),/Synthetic model uncertainty/);
    await humanPage.locator('#review-work article select[data-field=decision]').selectOption('include');await humanPage.locator('#review-work article textarea').fill('Human adjudication after comparing both independent decisions');await humanPage.getByRole('button',{name:'保存最终裁决'}).click();await humanPage.waitForFunction(()=>document.querySelector('#review-work').textContent.includes('已保存，原始意见'));
    await humanPage.locator('#review-work').screenshot({path:path.join(out,'screening-adjudication.png')});
    const download=humanPage.waitForEvent('download');await humanPage.locator('#export-review').click();const d=await download;const file=path.join(out,'screening-audit.json');await d.saveAs(file);const raw=fs.readFileSync(file,'utf8'),audit=JSON.parse(raw);
    assert.equal(audit.pending_final,0);assert.equal(audit.events.filter(e=>e.kind==='submitted').length,2);assert.ok(!raw.includes(humanToken)&&!raw.includes(modelToken));
    assert.equal(await humanPage.evaluate(()=>localStorage.length+sessionStorage.length),0);
  });
  await check('coded exclusion revision and both CSV downloads',async()=>{
    await humanPage.locator('#review-work article select[data-field=decision]').selectOption('exclude');
    await humanPage.locator('#review-work article textarea').fill('Synthetic exclusion: wrong population');
    await humanPage.getByRole('button',{name:'保存最终裁决'}).click();await humanPage.waitForFunction(()=>document.querySelector('#review-notice').textContent.includes('排除原因代码'));
    await humanPage.locator('#review-work article select[data-field=reason_code]').selectOption('population');
    const saved=humanPage.waitForResponse(r=>r.url().endsWith('/api/review/adjudicate')&&r.status()===200);await humanPage.getByRole('button',{name:'保存最终裁决'}).click();await saved;
    for(const [index,name] of [[0,'screening-decisions.csv'],[1,'screening-history.csv']]){
      const event=humanPage.waitForEvent('download');await humanPage.locator('#export-csv-'+index).click();const d=await event;assert.equal(d.suggestedFilename(),name);const file=path.join(out,name);await d.saveAs(file);const raw=fs.readFileSync(file,'utf8');assert.ok(raw.startsWith('\ufeff'));assert.match(raw,/population/);assert.match(raw,/Synthetic exclusion: wrong population/);assert.ok(!raw.includes(humanToken)&&!raw.includes(modelToken));
      if(index===1){assert.match(raw,/include/);assert.match(raw,/exclude/);}
    }
    const finalDownload=humanPage.waitForEvent('download');await humanPage.locator('#export-review').click();const finalFile=await finalDownload;await finalFile.saveAs(path.join(out,'screening-audit.json'));const finalAudit=JSON.parse(fs.readFileSync(path.join(out,'screening-audit.json'),'utf8'));assert.equal(finalAudit.final_decisions[0].reason_code,'population');assert.equal(finalAudit.events.filter(e=>e.kind==='adjudicated').length,2);
    await humanPage.locator('#review-work').screenshot({path:path.join(out,'screening-coded-exclusion.png')});
  });
  let childURL;
  const fulltextBytes=Buffer.from('Synthetic adult randomized trial.\fSynthetic outcome measured at 30 days.');
  await check('fulltext retrieval registration and child checkpoint',async()=>{
    await humanPage.locator('#review-work article select[data-field=decision]').selectOption('include');await humanPage.locator('#review-work article textarea').fill('Synthetic correction for fulltext test');
    const saved=humanPage.waitForResponse(r=>r.url().endsWith('/api/review/adjudicate')&&r.status()===200);await humanPage.getByRole('button',{name:'保存最终裁决'}).click();await saved;
    await humanPage.locator('#load-fulltext').click();await humanPage.locator('article[data-retrieval] input[type=file]').setInputFiles({name:'synthetic-fulltext.txt',mimeType:'text/plain',buffer:fulltextBytes});await humanPage.locator('[data-field=retrieval-reason]').fill('Author supplied synthetic document');
    await humanPage.getByRole('button',{name:'保存取得记录'}).click();await humanPage.waitForFunction(()=>document.querySelector('#review-work').textContent.includes('当前状态：已取得'));
    await humanPage.locator('#prepare-fulltext').click();await humanPage.locator('#fulltext-child-link').waitFor();childURL=await humanPage.locator('#fulltext-child-link').getAttribute('href');
    for(const [p,t] of [[humanPage,humanToken],[modelPage,modelToken]]){await p.goto(base+childURL);await p.locator('#review-token').fill(t);await p.locator('#review-connect').click();await p.locator('#review-state h2').waitFor();}
    assert.equal(await modelPage.locator('#load-ballot').count(),0);assert.match(await humanPage.locator('#review-state').innerText(),/全文筛选/);
    await humanPage.locator('#review-state details').filter({has:humanPage.locator('summary').filter({hasText:'全文快照'})}).locator('summary').click();
    const event=humanPage.waitForEvent('download');await humanPage.getByRole('button',{name:'下载冻结原件'}).click();const d=await event,file=path.join(out,'synthetic-fulltext.txt');await d.saveAs(file);assert.deepEqual(fs.readFileSync(file),fulltextBytes);
    await humanPage.locator('#checkpoint-confirm').check();await humanPage.locator('#checkpoint-approve').click();await humanPage.locator('#load-ballot').waitFor();
  });
  await check('fulltext exact quote validation and independent submissions',async()=>{
    for(const p of [humanPage,modelPage]){
      await p.locator('#review-refresh').click();await p.locator('#load-ballot').click();await p.locator('#review-work select[data-field=decision]').selectOption(p===humanPage?'include':'uncertain');
      await p.getByLabel('判断理由',{exact:true}).fill(p===humanPage?'FULLTEXT_HUMAN_PRIVATE':'Synthetic model uncertainty');await p.locator('[data-field=locator]').fill('p:1');await p.locator('[data-field=quote]').fill('Synthetic adult randomized trial.');
      if(p===humanPage){await p.locator('[data-field=quote]').fill('fabricated quote');await p.locator('#submit-ballot').click();await p.waitForFunction(()=>document.querySelector('#review-notice').textContent.includes('逐字核对'));await p.locator('[data-field=quote]').fill('Synthetic adult randomized trial.');}
      else{assert.ok(!(await p.locator('#review-work').innerText()).includes('FULLTEXT_HUMAN_PRIVATE'));await p.locator('#model-provenance').fill(JSON.stringify({model:'synthetic-no-call',parameters:{},prompt:'Synthetic fulltext fixture',raw_response:'uncertain',run_id:'synthetic-fulltext'}));}
      await p.locator('#submit-ballot').click();await p.waitForFunction(()=>document.querySelector('#review-state').textContent.includes('你的判断已锁定'));
    }
  });
  await check('fulltext adjudication lineage JSON and CSV exports',async()=>{
    await humanPage.locator('#review-refresh').click();await humanPage.waitForFunction(()=>!document.querySelector('#reveal').disabled);await humanPage.locator('#reveal').click();await humanPage.locator('#review-work select[data-field=decision]').selectOption('include');
    await humanPage.locator('[data-field=locator]').fill('p:1');await humanPage.locator('[data-field=quote]').fill('Synthetic adult randomized trial.');await humanPage.getByLabel('最终理由（修订时说明原因）').fill('Confirmed from frozen synthetic fulltext');
    const saved=humanPage.waitForResponse(r=>r.url().endsWith('/api/review/adjudicate')&&r.status()===200);await humanPage.getByRole('button',{name:'保存最终裁决'}).click();await saved;
    await humanPage.locator('#review-work').screenshot({path:path.join(out,'fulltext-adjudication.png')});
    const event=humanPage.waitForEvent('download');await humanPage.locator('#export-review').click();const d=await event,file=path.join(out,'fulltext-audit.json');await d.saveAs(file);const raw=fs.readFileSync(file,'utf8'),audit=JSON.parse(raw);
    assert.equal(audit.pending_final,0);assert.equal(audit.events[0].data.protocol.stage,'full_text');assert.equal(audit.events[0].data.lineage.reports_retrieved,1);assert.equal(audit.final_decisions[0].quote,'Synthetic adult randomized trial.');assert.ok(!raw.includes(humanToken)&&!raw.includes(modelToken));
    const csvEvent=humanPage.waitForEvent('download');await humanPage.locator('#export-csv-0').click();const csv=await csvEvent;await csv.saveAs(path.join(out,'fulltext-decisions.csv'));assert.match(fs.readFileSync(path.join(out,'fulltext-decisions.csv'),'utf8'),/file_sha256/);
  });
  await check('study mapping requires human confirmation and preserves revisions',async()=>{
    await humanPage.locator('#load-prisma').click();await humanPage.locator('#prisma-counts').waitFor();assert.match(await humanPage.locator('[data-metric=studies_included]').innerText(),/未知/);
    await humanPage.locator('#load-studies').click();await humanPage.locator('[data-field=study-ids]').fill('synthetic-trial-a');await humanPage.locator('[data-field=mapping-reason]').fill('Synthetic report assigned by human');await humanPage.locator('[data-field=mapping-locator]').fill('p:1');await humanPage.locator('[data-field=mapping-quote]').fill('Synthetic adult randomized trial.');
    await humanPage.locator('#save-studies').click();await humanPage.waitForFunction(()=>document.querySelector('#review-notice').textContent.includes('明确确认研究映射'));
    await humanPage.locator('#mapping-confirm').check();await humanPage.locator('#save-studies').click();await humanPage.waitForFunction(()=>document.querySelector('#review-work').textContent.includes('当前映射已确认'));
    await humanPage.locator('[data-field=study-ids]').fill('synthetic-trial-revised');await humanPage.locator('[data-field=mapping-reason]').fill('Synthetic identifier correction, preserving previous mapping');await humanPage.locator('#mapping-confirm').check();await humanPage.locator('#save-studies').click();await humanPage.waitForFunction(()=>document.querySelector('#review-work').textContent.includes('映射历史（2 版）'));
    await humanPage.locator('#review-work').screenshot({path:path.join(out,'study-mapping.png')});
  });
  await check('selected-lineage PRISMA counts and JSON CSV SVG exports',async()=>{
    await humanPage.locator('#load-prisma').click();await humanPage.locator('#prisma-counts').waitFor();
    for(const [key,value] of Object.entries({records_identified:3,duplicates_removed:2,records_screened:1,records_excluded:0,reports_sought:1,reports_not_retrieved:0,reports_assessed:1,reports_included:1,studies_included:1}))assert.equal(await humanPage.locator('[data-metric='+key+']').innerText(),String(value));
    for(const [index,name] of [[0,'prisma-audit.json'],[1,'prisma-counts.csv'],[2,'prisma-flow.svg']]){const event=humanPage.waitForEvent('download');await humanPage.locator('#export-prisma-'+index).click();const d=await event;assert.equal(d.suggestedFilename(),name);await d.saveAs(path.join(out,name));const raw=fs.readFileSync(path.join(out,name),'utf8');assert.ok(!raw.includes(humanToken)&&!raw.includes(modelToken));}
    const audit=JSON.parse(fs.readFileSync(path.join(out,'prisma-audit.json'),'utf8'));assert.equal(audit.report.status,'selected_lineage_complete');assert.equal(audit.report.mapping.history.length,2);assert.equal(audit.report.counts.studies_included,1);
    assert.match(fs.readFileSync(path.join(out,'prisma-counts.csv'),'utf8'),new RegExp(audit.report_sha256));const svg=fs.readFileSync(path.join(out,'prisma-flow.svg'),'utf8');assert.match(svg,new RegExp(audit.report_sha256));assert.ok(!svg.includes('<script'));
    await humanPage.locator('#review-work').screenshot({path:path.join(out,'prisma-counts.png')});const figure=await context.newPage();await figure.setContent(svg);await figure.locator('svg').screenshot({path:path.join(out,'prisma-flow.png')});await figure.close();
    assert.equal(await modelPage.locator('#load-studies').count(),0);assert.equal(await modelPage.locator('#load-prisma').count(),0);
  });
  let sourcesPage,combinedArtifact;
  await check('source capture imports and immutable incremental collections',async()=>{
    sourcesPage=await context.newPage();sourcesPage.on('pageerror',e=>errors.push(e.message));await sourcesPage.goto(base+'/sources');await sourcesPage.locator('#source-token').fill(token);await sourcesPage.locator('#source-connect').click();await sourcesPage.locator('#native-search option').first().waitFor({state:'attached'});
    await sourcesPage.locator('#capture-source').click();await sourcesPage.waitForFunction(()=>document.querySelector('#source-notice').textContent.includes('请确认'));
    await sourcesPage.locator('#capture-confirm').check();await sourcesPage.locator('#capture-source').click();await sourcesPage.locator('#source-runs input').waitFor();await sourcesPage.locator('#source-runs input').check();await sourcesPage.locator('#collection-label').fill('Synthetic initial collection');await sourcesPage.locator('#collection-reason').fill('Freeze original PubMed run');await sourcesPage.locator('#collection-confirm').check();await sourcesPage.locator('#create-collection').click();await sourcesPage.locator('#source-collections article').waitFor();
    await sourcesPage.locator('#source-meta').fill(JSON.stringify({database:'Synthetic registry B',kind:'register',query:'synthetic registry query',searched_at:'2026-11-21',total_hits:2,complete:true,coverage_note:'Synthetic records, human-declared completeness'}));await sourcesPage.locator('#source-records').fill(JSON.stringify([{title:'Synthetic browser fixture',pmid:'99999999'},{title:'Synthetic registry report',pmid:'88888888'}]));await sourcesPage.locator('#import-confirm').check();await sourcesPage.locator('#import-source').click();await sourcesPage.waitForFunction(()=>document.querySelectorAll('#source-runs input').length===2);
    const parent=await sourcesPage.locator('#collection-parent option').nth(1).getAttribute('value');await sourcesPage.locator('#collection-parent').selectOption(parent);await sourcesPage.locator('#source-runs input').nth(1).check();await sourcesPage.locator('#collection-label').fill('Synthetic incremental collection');await sourcesPage.locator('#collection-reason').fill('Add registry; retain full original source selection');await sourcesPage.locator('#create-collection').click();await sourcesPage.waitForFunction(()=>document.querySelectorAll('#source-collections article').length===2);
    assert.match(await sourcesPage.locator('#source-collections article').first().innerText(),/原始记录 1/);assert.match(await sourcesPage.locator('#source-collections article').last().innerText(),/原始记录 3/);
    await sourcesPage.locator('#source-collections').screenshot({path:path.join(out,'source-collections.png')});assert.equal(await sourcesPage.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);assert.equal(await sourcesPage.evaluate(()=>localStorage.length+sessionStorage.length),0);
    const response=sourcesPage.waitForResponse(r=>r.url().endsWith('/api/dedup')&&r.status()===201);await sourcesPage.locator('#source-collections article').last().getByRole('button',{name:'从此集合发起去重'}).click();await response;
    await refresh();const queued=page.locator('#jobs article').filter({has:page.getByRole('button',{name:'运行',exact:true})});assert.equal(await queued.count(),1);await queued.getByRole('button',{name:'运行',exact:true}).click();
    for(let i=0;i<100;i++){await refresh();if(await page.locator('#jobs article').filter({hasText:'completed'}).count()===completed+1)break;await sleep(100);}completed++;
    const artifact=page.waitForResponse(r=>r.url().includes('/api/artifact?'));await page.locator('#jobs article').last().getByRole('button',{name:'查看产物'}).click();combinedArtifact=await (await artifact).json();assert.equal(combinedArtifact.input_count,3);assert.equal(combinedArtifact.unique_count,2);assert.equal(combinedArtifact.duplicates_removed,1);
  });
  await check('combined source screening produces partial PRISMA with source provenance',async()=>{
    await page.getByRole('button',{name:'以此文献集准备筛选'}).click();for(const [key,value] of Object.entries({question:'Synthetic multi-source review',inclusion:'Adults',exclusion:'Other',human_reviewer:'browser-human',llm_reviewer:'browser-model',adjudicator:'browser-human'}))await page.locator(`[data-protocol="${key}"]`).fill(value);
    await clickRequest('#prepare-review','/api/screening-prepare');await page.locator('#prepared-review-link').waitFor();const url=await page.locator('#prepared-review-link').getAttribute('href');
    for(const [p,t] of [[humanPage,humanToken],[modelPage,modelToken]]){await p.goto(base+url);await p.locator('#review-token').fill(t);await p.locator('#review-connect').click();await p.locator('#review-state h2').waitFor();}
    await humanPage.locator('#checkpoint-confirm').check();await humanPage.locator('#checkpoint-approve').click();await humanPage.locator('#load-ballot').waitFor();
    for(const p of [humanPage,modelPage]){await p.locator('#review-refresh').click();await p.locator('#load-ballot').click();await p.locator('#review-work article').first().waitFor();for(const card of await p.locator('#review-work article').all()){await card.locator('select[data-field=decision]').selectOption('exclude');await card.locator('select[data-field=reason_code]').selectOption('population');await card.locator('textarea').nth(0).fill('Synthetic exclusion');await card.locator('textarea').nth(1).fill('title');}if(p===modelPage)await p.locator('#model-provenance').fill(JSON.stringify({model:'synthetic',parameters:{},prompt:'Synthetic combined review',raw_response:'exclude',run_id:'synthetic-combined'}));await p.locator('#submit-ballot').click();await p.waitForFunction(()=>document.querySelector('#review-state').textContent.includes('你的判断已锁定'));}
    await humanPage.locator('#review-refresh').click();await humanPage.waitForFunction(()=>!document.querySelector('#reveal').disabled);await humanPage.locator('#reveal').click();await humanPage.locator('#review-work article').first().waitFor();
    for(const card of await humanPage.locator('#review-work article').all()){await card.locator('select[data-field=decision]').selectOption('exclude');await card.locator('select[data-field=reason_code]').selectOption('population');await card.locator('textarea').fill('Synthetic final exclusion');const saved=humanPage.waitForResponse(r=>r.url().endsWith('/api/review/adjudicate')&&r.status()===200);await card.getByRole('button',{name:'保存最终裁决'}).click();await saved;}
    await humanPage.locator('#load-prisma').click();await humanPage.locator('#prisma-counts').waitFor();assert.equal(await humanPage.locator('[data-metric=records_identified]').innerText(),'3');assert.equal(await humanPage.locator('[data-metric=duplicates_removed]').innerText(),'1');assert.equal(await humanPage.locator('[data-metric=records_not_downloaded]').innerText(),'1');assert.match(await humanPage.locator('#review-work').innerText(),/未取全/);
    for(const [index,name] of [[0,'sources-prisma-audit.json'],[2,'sources-prisma-flow.svg']]){const event=humanPage.waitForEvent('download');await humanPage.locator('#export-prisma-'+index).click();await (await event).saveAs(path.join(out,name));}
    const audit=JSON.parse(fs.readFileSync(path.join(out,'sources-prisma-audit.json'),'utf8'));assert.equal(audit.report.source_breakdown.length,2);assert.equal(audit.report.status,'partial_or_historical');assert.equal(audit.report.provenance.record_source_lineage.length,2);assert.equal(audit.report.counts.studies_included,0);
    await humanPage.locator('#review-work').screenshot({path:path.join(out,'sources-prisma-counts.png')});const figure=await context.newPage();await figure.setContent(fs.readFileSync(path.join(out,'sources-prisma-flow.svg'),'utf8'));await figure.locator('svg').screenshot({path:path.join(out,'sources-prisma-flow.png')});await figure.close();
    const denied=await fetch(base+'/api/sources?project='+await page.locator('#projects').inputValue(),{headers:{Authorization:'Bearer '+modelToken}});assert.equal(denied.status,401);await sourcesPage.locator('#source-logout').click();assert.equal(await sourcesPage.locator('#source-runs').innerText(),'');await sourcesPage.close();
  });
  await check('reviewer credential revocation clears screen',async()=>{
    await page.locator('#reviewer-id').fill('browser-human');await clickRequest('#reviewer-revoke','/api/reviewers/revoke');await humanPage.locator('#review-refresh').click();await humanPage.waitForFunction(()=>document.querySelector('#review-notice').textContent.includes('令牌失效'));assert.equal(await humanPage.locator('#review-work').innerText(),'');
    await modelPage.locator('#review-logout').click();assert.equal(await modelPage.locator('#review-token').inputValue(),'');
  });
  await check('project switching and reload persistence; token not persisted',async()=>{const first=await page.locator('#projects').inputValue();await page.locator('#question').fill('Second synthetic project');await clickRequest('#create','/api/projects');await page.waitForFunction(()=>document.querySelector('#projects').options.length===2);assert.equal(await page.locator('#jobs article').count(),0);await page.locator('#projects').selectOption(first);await refresh();assert.equal(await page.locator('#jobs article').count(),completed);await page.reload();assert.equal(await page.locator('#token').inputValue(),'');assert.equal(await page.evaluate(()=>localStorage.length+sessionStorage.length),0);await page.locator('#token').fill(token);await page.locator('#connect').click();await page.waitForFunction(()=>document.querySelector('#projects').options.length===2);await page.locator('#projects').selectOption(first);await refresh();assert.equal(await page.locator('#jobs article').count(),completed);});
  await check('desktop width and unconfigured writing',async()=>{assert.match(await page.locator('#writing').innerText(),/未配置/);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await page.locator('#token').fill('');await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});assert.deepEqual(errors,[]);});
}catch(e){results.push({name:'execution',status:'FAIL',error:e.stack});console.error(e.stack);process.exitCode=1;}finally{
 const hashes={};for(const file of ['web/index.html','web/app.js','web/style.css','web/screening.html','web/screening.js','web/fulltext.js','web/studies.js','web/sources.html','web/sources.js','web/evaluation.js','modules/MedStat/templates/index.html','scripts/browser/acceptance.cjs','scripts/browser/server.py'])hashes[file]=crypto.createHash('sha256').update(fs.readFileSync(path.join(root,file))).digest('hex');
 fs.writeFileSync(path.join(out,'summary.json'),JSON.stringify({status:results.some(r=>r.status==='FAIL')?'FAIL':'PASS',tested_at:new Date().toISOString(),browser:browser?browser.version():null,viewport:'1440x1000',pubmed:'synthetic transport fixture; real parser, store and HTTP',gemini:'blank; no calls',results,source_sha256:hashes,page_errors:errors},null,2));
 if(browser)await browser.close();server.kill();fs.rmSync(tmp,{recursive:true,force:true});
}})();
