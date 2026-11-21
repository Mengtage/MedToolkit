"""Start the local-only workbench; blank model settings for this release."""
import argparse,os,secrets,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from workbench.core import Store
from workbench.server import serve

def main():
    parser=argparse.ArgumentParser(description='Start MedToolkit local desktop workbench')
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--data',type=Path,default=ROOT/'runtime')
    parser.add_argument('--disable-llm',action='store_true',help='Blank out external LLM API keys and use local deterministic engines only')
    args=parser.parse_args()
    if not 1<=args.port<=65535:parser.error('port must be 1..65535')
    token=os.environ.get('WORKBENCH_ACCESS_TOKEN','')
    if token and len(token)<32:parser.error('WORKBENCH_ACCESS_TOKEN must contain at least 32 characters')
    if not token:
        token=secrets.token_urlsafe(32);os.environ['WORKBENCH_ACCESS_TOKEN']=token
        print('本次访问令牌（仅在本机浏览器输入，不分享终端截图）：'+token,flush=True)
    else:print('使用环境变量中的工作台访问令牌。',flush=True)
    if args.disable_llm:
        os.environ['GEMINI_API_KEY']='';os.environ['GEMINI_MODEL']='';os.environ['OPENAI_API_KEY']=''
    else:
        os.environ.setdefault('GEMINI_API_KEY','');os.environ.setdefault('GEMINI_MODEL','')
    print(f'工作台 http://127.0.0.1:{args.port}/  |  写作 /writer  |  来源 /sources  |  筛选 /screening',flush=True)
    print('数据目录：'+str(args.data.resolve()),flush=True)
    serve(Store(args.data),args.port)

if __name__=='__main__':main()
