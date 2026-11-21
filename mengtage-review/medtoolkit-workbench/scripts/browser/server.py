"""Isolated browser fixture: real server/store/adapters; synthetic PubMed transport only."""
import json
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from workbench import adapters
from workbench.core import Store
from workbench.server import serve

def fixture_get(url):
    if 'esearch.fcgi?' in url:
        return json.dumps({'esearchresult': {'count': '3', 'idlist': ['111','111','222']}} if 'dedup-fixture' in url else {'esearchresult': {'count': '2', 'idlist': ['99999999']}}).encode()
    if 'efetch.fcgi?' in url and '111' in url:
        return ('<PubmedArticleSet>'+''.join(f'<PubmedArticle><MedlineCitation><PMID>{pmid}</PMID><Article><ArticleTitle>Synthetic conflict paper</ArticleTitle></Article></MedlineCitation></PubmedArticle>' for pmid in ['111','111','222'])+'</PubmedArticleSet>').encode()
    if 'efetch.fcgi?' in url:
        return b'<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>99999999</PMID><Article><ArticleTitle>Synthetic browser fixture</ArticleTitle><Abstract><AbstractText>Not a real study.</AbstractText></Abstract></Article></MedlineCitation></PubmedArticle></PubmedArticleSet>'
    raise AssertionError('Unexpected external request')
adapters.get = fixture_get
os.environ['GEMINI_API_KEY'] = ''
os.environ['GEMINI_MODEL'] = ''
serve(Store(sys.argv[1]), int(sys.argv[2]))
