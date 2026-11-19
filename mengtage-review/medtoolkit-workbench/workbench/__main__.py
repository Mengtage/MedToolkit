import argparse,json
from pathlib import Path
from .core import Store

def main():
    parser=argparse.ArgumentParser(description='Mengtage 科研工作台')
    parser.add_argument('--data',default='runtime')
    commands=parser.add_subparsers(dest='command',required=True)
    c=commands.add_parser('create');c.add_argument('question')
    commands.add_parser('projects')
    c=commands.add_parser('jobs');c.add_argument('project')
    c=commands.add_parser('enqueue');c.add_argument('project');c.add_argument('kind',choices=['search','statistics','write']);c.add_argument('payload')
    c=commands.add_parser('run');c.add_argument('id')
    commands.add_parser('recover')
    c=commands.add_parser('retry');c.add_argument('id');c.add_argument('--confirmed',action='store_true')
    c=commands.add_parser('export-ris');c.add_argument('project');c.add_argument('artifact');c.add_argument('output')
    c=commands.add_parser('serve');c.add_argument('--port',type=int,default=8765)
    args=parser.parse_args();store=Store(args.data)
    if args.command=='create':result={'project':store.create(args.question)}
    elif args.command=='projects':result=store.projects()
    elif args.command=='jobs':result=store.jobs(args.project)
    elif args.command=='enqueue':result={'job':store.enqueue(args.project,args.kind,json.loads(Path(args.payload).read_text()))}
    elif args.command=='run':result=store.run(args.id)
    elif args.command=='recover':result={'needs_review':store.recover()}
    elif args.command=='retry':result={'job':store.retry(args.id,args.confirmed)}
    elif args.command=='export-ris':
        from .exports import ris
        data=json.loads(store.artifact(args.project,args.artifact).read_text())
        out=Path(args.output)
        with out.open('x',encoding='utf-8') as f:f.write(ris(data['records']))
        result={'file':str(out.resolve()),'records':len(data['records'])}
    else:
        from .server import serve
        return serve(store,args.port)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
