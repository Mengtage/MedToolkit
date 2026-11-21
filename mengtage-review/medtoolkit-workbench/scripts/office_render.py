"""Render a DOCX with installed LibreOffice or the local validation-only runtime."""
import os,shutil,subprocess,sys,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=Path(sys.argv[1]).resolve();target=Path(sys.argv[2]).resolve();target.mkdir(parents=True,exist_ok=True)
env=dict(os.environ);engine=shutil.which('libreoffice') or shutil.which('soffice');extra=[]
if not engine:
    local=root/'.office-tools';program=local/'sysroot/usr/lib/libreoffice/program';engine=str(program/'soffice')
    if not Path(engine).exists():raise SystemExit('Install LibreOffice Writer or prepare the documented local runtime')
    env['LD_LIBRARY_PATH']=str(program)+':'+str(local/'sysroot/usr/lib/x86_64-linux-gnu')
    extra=['-env:BRAND_BASE_DIR='+program.parent.as_uri()]
    if (local/'langtag-path.so').exists():
        env['LD_PRELOAD']=str(local/'langtag-path.so');env['MEDTOOLKIT_LANGTAG_DATA']=str(local/'sysroot/usr/share/liblangtag')
with tempfile.TemporaryDirectory(prefix='medtoolkit-office-render-') as tmp:
    folder=Path(tmp);profile=(folder/'profile').as_uri()
    cmd=[engine,*extra,'-env:UserInstallation='+profile,'--headless','--convert-to','pdf','--outdir',str(folder),str(source)]
    result=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=120)
    (target/(source.stem+'-render.log')).write_text(result.stdout+result.stderr)
    pdf=folder/(source.stem+'.pdf')
    if result.returncode or not pdf.exists():raise SystemExit('Office rendering failed; inspect render log')
    shutil.copy2(pdf,target/pdf.name)
print(target/pdf.name)
