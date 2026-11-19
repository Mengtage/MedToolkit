"""Deterministic interchange for reference managers; no library writes."""
def clean(value):
    return ' '.join(str(value or '').split())

def ris(records):
    blocks=[]
    for r in records:
        if not r.get('title'):raise ValueError('文献缺少标题，不能导出')
        lines=['TY  - JOUR','TI  - '+clean(r['title'])]
        authors=r.get('authors',[])
        if isinstance(authors,str):authors=[authors]
        for a in authors:lines.append('AU  - '+clean(a))
        for key,tag in [('journal','JO'),('pub_date','PY'),('doi','DO'),('abstract','AB'),('pmid','AN')]:
            if r.get(key):lines.append(tag+'  - '+clean(r[key]))
        if r.get('pmid'):lines.append('UR  - https://pubmed.ncbi.nlm.nih.gov/'+clean(r['pmid'])+'/')
        lines.append('ER  - ');blocks.append('\n'.join(lines))
    return '\n\n'.join(blocks)+'\n'
