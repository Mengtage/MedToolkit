"""Frozen exclusion vocabulary and spreadsheet-safe, UTF-8 CSV audit views."""
import csv
import io

REASON_CODES={
    'population':'研究对象不符', 'intervention':'干预或暴露不符',
    'comparator':'对照不符', 'outcome':'结局不符', 'design':'研究设计不符',
    'publication_type':'文献类型不符', 'duplicate_report':'重复报告，需注明关联记录',
    'other':'其他，须说明具体原因'}
REASON_VERSION='medhunter-exclusion-v1'

def validate_reason(decision,code,protocol):
    codes=protocol.get('reason_codes')
    if not isinstance(code,str):raise ValueError('排除原因代码须为文本')
    if decision!='exclude' and code:raise ValueError('仅排除决定可填写排除原因代码')
    if codes is not None and decision=='exclude' and code not in codes:raise ValueError('请选择方案中已冻结的排除原因代码，并保留具体理由')
    if codes is None and code:raise ValueError('旧批次未冻结原因词表，请保留原自由文本；新批次可使用原因代码')

def safe_cell(value):
    value='' if value is None else str(value)
    # Spreadsheet formula prefixes, including after whitespace/control characters.
    if value.lstrip().startswith(('=','+','-','@')) or (bool(value) and ord(value[0])<32):
        return "'"+value
    return value

def csv_text(fields,rows):
    output=io.StringIO(newline='');writer=csv.DictWriter(output,fieldnames=fields,lineterminator='\r\n')
    writer.writeheader()
    for row in rows:writer.writerow({k:safe_cell(row.get(k,'')) for k in fields})
    return '\ufeff'+output.getvalue()

def export_csv(audit):
    events=audit['events'];draft=events[0]['data'];protocol=draft['protocol']
    submissions={e['actor']:e for e in events if e['kind']=='submitted'}
    final_events={e['data']['record_id']:e for e in events if e['kind']=='adjudicated'}
    decisions={who:{r['record_id']:r for r in e['data']['decisions']} for who,e in submissions.items()}
    rows=[];history=[];codes=protocol.get('reason_codes',{})
    common={'review_id':audit['review_id'],'stage':protocol['stage'],'protocol_sha256':draft['protocol_sha256'],
            'source_artifact':draft['source_artifact'],'source_sha256':draft['source_sha256'],'reason_codebook_version':protocol.get('reason_codebook_version','legacy_free_text')}
    for item in draft['records']:
        rid=item['record_id'];record=item['record'];last=final_events.get(rid);final=last['data'] if last else {}
        row={**common,'record_id':rid,'title':record.get('title',''),'pmid':record.get('pmid',''),'doi':record.get('doi',''),
             'record_sha256':item['record_sha256'],'final_status':'confirmed' if last else 'pending',
             'final_decision':final.get('decision',''),'final_reason_code':final.get('reason_code',''),
             'final_reason_label':codes.get(final.get('reason_code',''),''),'final_reason':final.get('reason',''),
             'final_actor':last['actor'] if last else '', 'final_timestamp':last['timestamp'] if last else '',
             'final_event_hash':last['event_hash'] if last else ''}
        row.update({k:record.get(k,'') for k in ('parent_review_id','parent_record_id','report_id','retrieval_event_hash')})
        row.update({k:record.get('fulltext',{}).get(k,'') for k in ('file_sha256','text_sha256')})
        row['page_numbering']=record.get('fulltext',{}).get('extraction',{}).get('page_numbering','')
        row['final_locator']=final.get('locator','');row['final_quote']=final.get('quote','')
        for side,key in [('human','human_reviewer'),('model','llm_reviewer')]:
            actor=protocol[key];entry=decisions.get(actor,{}).get(rid,{})
            row[side+'_actor']=actor
            row[side+'_submission_event_hash']=submissions.get(actor,{}).get('event_hash','')
            for field in ('decision','reason_code','reason','locator','quote'):row[side+'_'+field]=entry.get(field,'')
        model_provenance=submissions.get(protocol['llm_reviewer'],{}).get('data',{}).get('provenance',{})
        row['model_name']=model_provenance.get('model','');row['model_run_id']=model_provenance.get('run_id','')
        row['reviewer_disagreement']=str(row['human_decision']!=row['model_decision']).lower()
        rows.append(row)
    for event in events:
        if event['kind']=='submitted':entries=event['data']['decisions']
        elif event['kind']=='adjudicated':entries=[event['data']]
        else:continue
        for entry in entries:
            history.append({**common,'event_id':event['event_id'],'event_hash':event['event_hash'],
                'previous_hash':event['previous_hash'],'event_kind':event['kind'],'actor':event['actor'],
                'timestamp':event['timestamp'],**{k:entry.get(k,'') for k in ('record_id','decision','reason_code','reason','locator','quote')}})
    summary_fields=list(rows[0]) if rows else list(common)+['record_id','final_status']
    history_fields=list(common)+['event_id','event_hash','previous_hash','event_kind','actor','timestamp','record_id','decision','reason_code','reason','locator','quote']
    return {'review_id':audit['review_id'],'pending_final':audit['pending_final'],
        'spreadsheet_safety':'formula-like cells prefixed with apostrophe; JSON retains original text',
        'files':[{'filename':'screening-decisions.csv','content':csv_text(summary_fields,rows)},
                 {'filename':'screening-history.csv','content':csv_text(history_fields,history)}]}
