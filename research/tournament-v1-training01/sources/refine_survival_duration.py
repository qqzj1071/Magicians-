"""Duration-only repair after failed first holdout; AI stays completely frozen.

New calibration seeds choose between two predeclared tables; fresh 200-room
holdout follows. No fourth AI learning phase, no reuse of failed holdout seeds.
"""
import argparse
import copy
import gzip
import hashlib
import json
import multiprocessing
import shutil
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import train_survival as R
from tournament_inference import load_model
S=R.S


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);ap.add_argument('--calibrate',type=int,default=40)
    ap.add_argument('--final',type=int,default=200);args=ap.parse_args();parent=S.C.ROOT/'research'/args.run
    out=parent/'duration-refinement'
    if out.exists():raise FileExistsError(out)
    out.mkdir();(out/'sources').mkdir();cfg=json.loads((parent/'config.json').read_text(encoding='utf-8'))
    model=load_model(parent/'selected-model.json');old=R.initial_model();ns=parent.name+'-duration-repair'
    hashes={}
    for path in (parent/'sources').iterdir():
        if path.suffix not in ('.py','.json'):continue
        current=Path(__file__).parent/path.name;source=current if current.exists() else path
        shutil.copyfile(source,out/'sources'/path.name);hashes[path.name]=hashlib.sha256(source.read_bytes()).hexdigest()
    source=Path(__file__);shutil.copyfile(source,out/'sources'/source.name);hashes[source.name]=hashlib.sha256(source.read_bytes()).hexdigest()
    S.save(out/'experiment.json',dict(args=vars(args),source_hashes=hashes,card_sha256=hashlib.sha256(S.C.CARD_LIBRARY_PATH.read_bytes()).hexdigest(),
        purpose='frozen-AI duration-only correction; original 200-room failure retained; fresh seeds',
        original_observation=json.loads((parent/'sealed-final-summary.json').read_text(encoding='utf-8')),
        model_sha256=hashlib.sha256((parent/'selected-model.json').read_bytes()).hexdigest(),training_phases=0,
        late_closure='m17=m18=100 ensures <=2 survivors after17 and tournament ends by18, since HP never exceeds100',
        predeclared_candidates=[28,30],calibration='matched names/seeds; choose closest to50% alive15'))
    S.save(out/'config.json',cfg);shutil.copyfile(parent/'selected-model.json',out/'selected-model.json')
    with ProcessPoolExecutor(max_workers=4) as executor,gzip.open(out/'episodes.jsonl.gz','wt',encoding='utf-8') as raw:
        candidates=[]
        for base,label in [(28,'calibration-before'),(30,'calibration-after')]:
            table=R.make_table(4,1.6,base,1.6,100)
            eps,stats=R.batch(executor,label,args.calibrate,model,table,cfg,False,ns+'-calibration',raw,out)
            candidates.append(dict(base=base,table=table,stats=stats))
        selected=min(candidates,key=lambda c:(abs(c['stats']['alive15']-.5),c['base']))
        table=selected['table'];S.save(out/'calibration.json',dict(candidates=candidates,selected=selected['base']))
        S.save(out/'selected-table.json',dict(table=table,selection='new real-tournament calibration; no trace proxy; frozen model'))
        eps,stats=R.batch(executor,'sealed-final',args.final,model,table,cfg,False,ns+'-new-holdout',raw,out)
        matrix=R.benchmark(executor,eps,model,old,ns+'-champion',out,'champion-matrix',True)
        S.save(out/'summary.json',dict(history=[],final=stats,matrix=matrix,table=table,training_phases=0,
            parent_run=args.run,calibration=candidates,selected_midgame_base=selected['base']))
        print('REFINED FINAL '+json.dumps(stats),flush=True)


if __name__=='__main__':multiprocessing.freeze_support();main()
