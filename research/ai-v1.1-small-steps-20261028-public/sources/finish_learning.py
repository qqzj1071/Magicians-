"""After training completes, run sealed diagnostics, audit and publish the learned AI."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,time,zipfile
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
from learning_core import OUT
def call(name,*args):
 print('RUN '+name,flush=True)
 subprocess.run([sys.executable,str(HERE/name),*args],cwd=ROOT,check=True)
def main():
 print('Waiting for all six training rounds and sealed league/factorial tests.',flush=True)
 while not (OUT/'completion.json').exists():time.sleep(10)
 c=json.loads((OUT/'completion.json').read_text(encoding='utf-8'));assert c['completed'] and c['rounds']>=6
 c['elapsed_scope']='elapsed_seconds starts at latest resume; see wall_since_experiment_start_seconds for full wall time'
 c['wall_since_experiment_start_seconds']=(OUT/'completion.json').stat().st_mtime-(OUT/'experiment.json').stat().st_mtime
 (OUT/'completion.json').write_text(json.dumps(c,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('Frozen selection ready; independent offer and hierarchical tests start.',flush=True)
 required=[]
 if not (OUT/'draft-final-summary.json').exists():required.append('draft_learning.py')
 if not (OUT/'hierarchy-summary.json').exists() or not (OUT/'trace-audit.json').exists():required.append('learning_diagnostics.py')
 children=[subprocess.Popen([sys.executable,str(HERE/name),'--workers','10'],cwd=ROOT) for name in required]
 for p in children:
  if p.wait()!=0:raise RuntimeError('A sealed diagnostic failed; do not publish partial knowledge.')
 call('audit_learning.py');call('publish_learning.py');call('verify_v1.py')
 subprocess.run([sys.executable,'-m','unittest','-q','test_learning','test_draft_learning'],cwd=HERE,check=True)
 # The published card ZIP stays untouched. AI knowledge gets its own small package.
 package=OUT/'ai-knowledge-v1.0.zip'
 paths=list((ROOT/'docs/ai').rglob('*.md'))+[ROOT/'docs/ai/construction-model.json',ROOT/'decks/trained-v1.0.json',ROOT/'tools/round_robin/policies.json',OUT/'integrity-audit.json']
 with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for p in paths:z.write(p,p.relative_to(ROOT).as_posix())
 with zipfile.ZipFile(package) as z:assert z.testzip() is None
 result=dict(completed=True,knowledge_zip=str(package.relative_to(ROOT)),knowledge_bytes=package.stat().st_size,card_sha256=hashlib.sha256((ROOT/'releases/v1.0/cards.json').read_bytes()).hexdigest())
 (OUT/'ready.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('READY '+json.dumps(result,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
