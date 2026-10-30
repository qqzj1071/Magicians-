"""Build a fresh offline offline Windows v1.2 release package."""
from pathlib import Path
import argparse, hashlib, json, shutil, subprocess, zipfile
ROOT = Path(__file__).resolve().parents[2]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser()
    for name in ('godot','template','python-runtime','licenses','output'): p.add_argument('--'+name, type=Path, required=True)
    a=p.parse_args(); out=a.output.resolve()
    if out.exists(): raise RuntimeError('Choose a new output folder')
    out.mkdir(parents=True)
    presets=ROOT/'export_presets.cfg'; old=presets.read_bytes()
    lines=old.decode('utf-8-sig').splitlines()
    lines=[line for line in lines if not line.startswith('custom_template/release=')]
    lines.insert(lines.index('[preset.0.options]')+1,'custom_template/release='+json.dumps(a.template.resolve().as_posix()))
    presets.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    try:
        with Path(str(out)+'.export.log').open('w',encoding='utf-8') as log:
            for cmd in ([str(a.godot),'--headless','--editor','--path',str(ROOT),'--import','--quit'],
                        [str(a.godot),'--headless','--path',str(ROOT),'--export-release','Windows Portable',str(out/'Magicians.exe')]):
                subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
    finally: presets.write_bytes(old)
    export_log = Path(str(out)+'.export.log').read_text(encoding='utf-8')
    if 'Export .NET Project: Failed' in export_log or 'Failed to export project' in export_log:
        raise RuntimeError('Export did not rebuild the .NET client; do not distribute this output')
    data=out/'runtime-data'
    for relative in ('Data','docs/cards-v1.2','tools/sim_v12','tools/client_v12','releases/v1.2','releases/ai-v1.2-six-styles-20261029'):
        src=ROOT/relative; dst=data/relative; dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copytree(src,dst,ignore=shutil.ignore_patterns('__pycache__','*.pyc','test_*.py'))
    shutil.copytree(a.python_runtime,data/'python')
    (data/'python/python312._pth').chmod(0o666)
    (data/'python/python312._pth').write_text('python312.zip\n.\n..\n',encoding='ascii')
    shutil.copytree(a.licenses,out/'licenses')
    info=dict(version='1.2',cards=183,pool=677,python='bundled 3.12.10',cards_sha256=sha(data/'releases/v1.2/cards.json'),models_sha256=sha(data/'releases/ai-v1.2-six-styles-20261029/manifest.json'))
    (out/'BUILD-INFO.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
    (out/'README.txt').write_text('Magicians! v1.2 正式客户端\n双击 Magicians.exe，选择开始单人赛事。自带Python与AI模型，无需安装依赖。\n卡面、路线与日志采用五系定稿显示名，规则运行ID保留。小字暂不在局内显示。支持当前牌组、抽牌堆、弃牌堆弹窗。\n',encoding='utf-8')
    hashes={f.relative_to(out).as_posix():sha(f) for f in sorted(out.rglob('*')) if f.is_file()}
    (out/'integrity.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(client=str(out/'Magicians.exe')),ensure_ascii=False))
if __name__=='__main__': main()
