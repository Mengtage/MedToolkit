"""Explicit local deduplication: source -> new artifact; never overwrite source."""
import argparse
import json
import uuid
from .core import Store
from .deduplication import deduplicate

def main():
    p=argparse.ArgumentParser(description='标题/PMID/DOI去重，保留原始记录与合并事件；无LLM')
    p.add_argument('--data',default='runtime');p.add_argument('--conflict-policy',default='review',choices=['review','title_wins'],help='默认review：冲突保留待人工核对')
    p.add_argument('project');p.add_argument('artifact');a=p.parse_args();store=Store(a.data)
    source=json.loads(store.artifact(a.project,a.artifact).read_text())
    result=deduplicate(source['records'],conflict_policy=a.conflict_policy)
    result['source_artifact']=a.artifact
    name=store.save(a.project,uuid.uuid4().hex+'-dedup.json',result)
    print(json.dumps({'artifact':name,'unique_count':result['unique_count'],'duplicates_removed':result['duplicates_removed'],'pending_review_pairs':len(result['review_candidates'])},ensure_ascii=False))
if __name__=='__main__':main()
