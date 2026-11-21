"""Local audit prototype. python -m workbench.screening_cli --data DIR request.json"""
import argparse
import json
from pathlib import Path
from .core import Store
from .screening import ScreeningLedger

def main():
    p=argparse.ArgumentParser(description='本地筛选审计；actor为声明身份，不提供多人认证')
    p.add_argument('--data',default='runtime');p.add_argument('request')
    args=p.parse_args();request=json.loads(Path(args.request).read_text())
    if not isinstance(request,dict) or set(request)!={'operation','arguments'}:raise ValueError('需要operation与arguments')
    operation=request['operation']
    if operation not in ('prepare','approve','ballot','submit','reveal','adjudicate','export'):raise ValueError('操作无效')
    ledger=ScreeningLedger(Store(args.data))
    print(json.dumps(getattr(ledger,operation)(**request['arguments']),ensure_ascii=False,indent=2,allow_nan=False))
if __name__=='__main__':main()
